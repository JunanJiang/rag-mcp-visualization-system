"""Flask API 服务器 V2 - 支持槽位交互和Browser集成"""

import os
import sys
import json
import uuid
import shutil
import zipfile

from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_file, send_from_directory, Response, stream_with_context, g
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

# 添加 server 目录和项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_PACKAGE_DIR = PROJECT_ROOT / '数据包'

from database import (
    init_db, seed_test_accounts, create_report_record, update_report_record, get_user_reports,
    create_organization, get_organization, get_user_organizations,
    get_org_members, add_org_member, remove_org_member, is_org_member,
    get_org_member_role, get_org_reports, update_user_role, list_all_users,
    list_org_users_for_admin, is_user_in_admin_orgs,
    create_api_key, get_user_api_keys, deactivate_api_key,
    get_audit_logs, get_audit_logs_for_admin,
    get_user_by_username, add_audit_log,
    get_report_by_id, get_report_versions, get_report_snapshot,
    kb_get_document, kb_list_org, kb_update_document,
    update_user_profile, update_user_password, get_user_stats,
    list_joinable_organizations, count_org_members, list_all_organizations,
    normalize_org_member_roles, update_organization, delete_organization,
    get_user_ai_config, save_user_ai_config, seed_all_users_ai_config,
    list_system_ai_configs, get_system_ai_config_by_id, get_active_system_ai_config,
    create_system_ai_config, activate_system_ai_config, deactivate_system_ai_config,
    delete_system_ai_config, seed_default_system_ai_config,
    update_system_ai_config_last_used,
)
from auth import (
    login_required, admin_required,
    register_user, login_user, decode_token, get_user_by_id, audit
)
from reportgen.io.standard_schema import (
    validate_standard_input, normalize_to_facts, STANDARD_SCHEMA, EXAMPLE_INPUT
)
from reportgen.io.datapackage_spec import (
    validate_data_package, get_spec_summary, SPEC_VERSION as DP_SPEC_VERSION
)

from reportgen.io.load_dataset import parse_data_package
from reportgen.pipeline.build_facts import build_run_facts
from reportgen.kb.md_loader import load_knowledge_cards, cards_to_documents
from reportgen.kb.index import build_vector_index
from reportgen.llm.deepseek_client import DeepSeekClient, DryRunClient
from reportgen.pipeline.build_md import build_markdown_report
from reportgen.pipeline.build_docx import build_docx_report
from reportgen.pipeline.build_pdf import build_pdf_report

# 新模块
from reportgen.draft.schema import Draft, Slot, Policy, SlotStatus, DOMAINS, PHENOMENA, PURPOSES
from reportgen.draft.manager import DraftManager
from reportgen.clarification.questions import ClarificationGenerator
from reportgen.clarification.policy import PolicyBuilder
from reportgen.browser.search import WebSearcher, MockWebSearcher
from reportgen.pipeline.slot_filler import SlotFiller, BatchSlotFiller
from reportgen.templates import list_templates as list_report_templates
from reportgen.mcp.observer import tool_observer, init_observer
from reportgen.mcp.registry import mcp_registry

from config import (
    UPLOAD_FOLDER, OUTPUT_FOLDER, KB_FOLDER, MAX_CONTENT_LENGTH, DEEPSEEK_API_KEY,
    KB_UPLOAD_FOLDER, CHROMA_PERSIST_DIR, TAVILY_API_KEY
)
from task_queue import task_manager

app = Flask(__name__, static_folder='../frontend/dist', static_url_path='')
CORS(app)

_DEBUG_MODE = os.environ.get('FLASK_DEBUG', '0') == '1'


def _err(e: Exception, *, msg: str | None = None) -> dict:
    """统一错误响应：生产环境隐藏 traceback"""
    import traceback as _tb
    resp = {'success': False, 'error': msg or str(e)}
    if _DEBUG_MODE:
        resp['traceback'] = _tb.format_exc()
    return resp

app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH


# ── SessionStore: 会话级状态隔离 + 线程安全 ──
import threading as _threading

class SessionStore:
    """管理会话级别的数据包和 DraftManager，保证多用户隔离和线程安全"""
    
    DEFAULT = "__default__"
    
    def __init__(self):
        self._lock = _threading.RLock()
        self._sessions: dict = {}
    
    def _ensure(self, sid: str):
        if sid not in self._sessions:
            self._sessions[sid] = {
                "data_package": None,
                "draft_manager": DraftManager(),
            }
    
    def get_data_package(self, sid: str = DEFAULT):
        with self._lock:
            self._ensure(sid)
            return self._sessions[sid]["data_package"]
    
    def set_data_package(self, pkg, sid: str = DEFAULT):
        with self._lock:
            self._ensure(sid)
            self._sessions[sid]["data_package"] = pkg
    
    def get_draft_manager(self, sid: str = DEFAULT) -> DraftManager:
        with self._lock:
            self._ensure(sid)
            return self._sessions[sid]["draft_manager"]


_session_store = SessionStore()

# 兼容性属性 — 已有代码通过 global 访问的变量现在路由到 SessionStore
current_data_package = None
current_kb_cards = []
vector_index = None
draft_manager = _session_store.get_draft_manager()
web_searcher = None

# 多租户知识库管理器（延迟初始化，避免启动时阻塞）
_kb_manager = None


def get_kb_manager():
    """获取或初始化 KBManager（懒加载）"""
    global _kb_manager
    if _kb_manager is None:
        from reportgen.kb.manager import KBManager
        _kb_manager = KBManager(
            chroma_persist_dir=str(CHROMA_PERSIST_DIR),
            kb_files_dir=str(KB_FOLDER),
        )
    return _kb_manager


def _reset_current_workflow_state():
    global current_data_package, draft_manager
    current_data_package = None
    draft_manager.current_draft = None


def _set_current_data_package(pkg_path: str):
    global current_data_package, draft_manager
    current_data_package = pkg_path
    draft_manager.current_draft = None


def _needs_org_profile_upgrade(name: str) -> bool:
    text = (name or '').strip()
    lowered = text.lower()
    return (
        not text
        or text.isdigit()
        or len(text) <= 3
        or 'test' in lowered
        or 'debug' in lowered
        or 'tmp' in lowered
        or '_' in text
    )


def _professional_org_profiles() -> list[dict]:
    return [
        {'name': '工业可视分析协同中心', 'description': '聚焦工业仿真数据治理、结果解读与可视化报告协同。'},
        {'name': '多源数据融合研究组', 'description': '面向多源异构数据的整理、融合建模与知识增强分析。'},
        {'name': '场景设计与评估实验室', 'description': '围绕复杂场景设计、评估指标构建与自动化报告输出开展协作。'},
        {'name': '智能知识工程中心', 'description': '负责知识库建设、语义检索优化与场景问答支撑。'},
        {'name': '仿真报告质量保障组', 'description': '聚焦报告模板规范、结果复核与交付质量保障。'},
        {'name': '决策可视化应用团队', 'description': '面向业务决策场景开展图表编排、结论表达与报告展示。'},
    ]


def _pick_professional_org_profile(index: int, used_names: set[str]) -> dict:
    profiles = _professional_org_profiles()
    if index < len(profiles):
        profile = dict(profiles[index])
    else:
        profile = {
            'name': f'智能可视化协同组织{index + 1:02d}',
            'description': '面向复杂场景分析与知识协作的综合型组织。'
        }
    base_name = profile['name']
    suffix = 1
    while profile['name'] in used_names:
        suffix += 1
        profile['name'] = f'{base_name}{suffix}'
    used_names.add(profile['name'])
    return profile


def _build_org_seed_documents(org: dict) -> list[tuple[str, str]]:
    org_name = org.get('name') or '专业组织'
    description = org.get('description') or '负责共享知识沉淀与场景报告协同。'
    return [
        (
            f'{org_name}-组织定位与协作规范.md',
            f'# {org_name} 组织定位与协作规范\n\n## 组织定位\n{description}\n\n## 核心职责\n- 维护组织共享知识库与文档标签体系。\n- 沉淀典型场景分析方法与业务术语。\n- 统一可视化报告的结构、表达与质量标准。\n\n## 协作要求\n- 新增文档需说明来源、版本和适用范围。\n- 关键结论需附带证据依据和可视化建议。\n- 每周完成一次共享知识库整理与内容复核。\n'
        ),
        (
            f'{org_name}-典型场景需求清单.md',
            f'# {org_name} 典型场景需求清单\n\n1. 建立多源数据接入后的指标口径说明。\n2. 形成场景目标、对象、约束条件的结构化模板。\n3. 支持对异常波动、趋势变化、对比分析进行标准化描述。\n4. 在报告中突出结论摘要、证据链和后续建议。\n\n本清单用于指导组织成员在新增知识文档时保持一致表达。\n'
        ),
        (
            f'{org_name}-报告编制规范.md',
            f'# {org_name} 报告编制规范\n\n## 内容组织\n报告正文应包含背景、数据说明、分析过程、关键发现、结论建议五个部分。\n\n## 表达要求\n- 标题命名清晰，避免口语化。\n- 图表说明与正文结论保持一致。\n- 对不确定信息进行边界说明。\n\n## 交付要求\n最终报告应保证结构完整、语言专业、图文对应明确。\n'
        ),
        (
            f'{org_name}-质量评估要点.md',
            f'# {org_name} 质量评估要点\n\n- 知识引用是否与当前组织场景一致。\n- 关键数据是否来源明确、口径统一。\n- 可视化表达是否支撑核心结论。\n- 报告建议是否具备可执行性。\n- 文档版本是否最新且便于团队复用。\n\n以上要点用于组织共享知识库持续维护和报告质量复核。\n'
        ),
    ]


def _seed_demo_organizations() -> None:
    orgs = list_all_organizations()
    if not orgs:
        return
    used_names = {org.get('name') for org in orgs if org.get('name') and not _needs_org_profile_upgrade(org.get('name', ''))}
    normalized_orgs = []
    for index, org in enumerate(orgs):
        current_name = (org.get('name') or '').strip()
        current_desc = (org.get('description') or '').strip()
        if _needs_org_profile_upgrade(current_name):
            profile = _pick_professional_org_profile(index, used_names)
            update_organization(org['id'], profile['name'], profile['description'])
            org['name'] = profile['name']
            org['description'] = profile['description']
        elif not current_desc:
            profile = _pick_professional_org_profile(index, used_names)
            update_organization(org['id'], current_name, profile['description'])
            org['description'] = profile['description']
        normalized_orgs.append(org)
    for org in normalized_orgs:
        existing_names = {doc.get('filename') for doc in kb_list_org(org['id'])}
        uploader_id = org.get('created_by') or 1
        for filename, content in _build_org_seed_documents(org):
            if filename in existing_names:
                continue
            seed_path = KB_UPLOAD_FOLDER / _safe_filename(filename)
            seed_path.write_text(content, encoding='utf-8')
            get_kb_manager().upload_to_org(org['id'], uploader_id, str(seed_path))


def _build_org_export_archive(org: dict) -> Path:
    export_dir = OUTPUT_FOLDER / 'org_exports'
    export_dir.mkdir(parents=True, exist_ok=True)
    archive_name = _safe_filename(f"{org['name']}_知识库备份_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip")
    archive_path = export_dir / archive_name
    docs = kb_list_org(org['id'])
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        exported_count = 0
        for doc in docs:
            file_path = Path(doc.get('file_path') or '')
            if not file_path.exists() or not file_path.is_file():
                continue
            zip_file.write(file_path, arcname=_safe_filename(doc.get('filename') or file_path.name))
            exported_count += 1
        zip_file.writestr(
            '导出说明.txt',
            f"组织名称: {org['name']}\n导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n导出文档数: {exported_count}\n"
        )
    return archive_path


def _destroy_org_assets(org_id: int) -> int:
    docs = kb_list_org(org_id)
    for doc in docs:
        file_path = Path(doc.get('file_path') or '')
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass
    get_kb_manager().delete_org_collection(org_id)
    if not delete_organization(org_id):
        raise ValueError('组织删除失败')
    return len(docs)


def _build_user_context() -> dict:
    """从当前请求中提取 user_context，供 SlotFiller 使用"""
    try:
        user = getattr(g, 'current_user', None)
        if not user:
            uid = _get_optional_user_id()
            if not uid:
                return {}
            from auth import get_user_by_id
            user = get_user_by_id(uid)
        if not user:
            return {}
        orgs = get_user_organizations(user['id'])
        return {
            'user_id': user['id'],
            'org_ids': [o['id'] for o in orgs],
            'role': user['role'],
        }
    except Exception:
        return {}


def _make_slot_filler(dry_run: bool = False):
    """构建带 KBManager + user_context 的 SlotFiller"""
    llm_client = get_llm_client(dry_run)
    searcher = get_web_searcher(use_mock=dry_run)
    user_ctx = _build_user_context()
    return SlotFiller(
        llm_client, searcher, vector_index,
        use_mock=dry_run,
        kb_manager=get_kb_manager(),
        user_context=user_ctx,
    )


def _get_optional_user_id() -> int | None:
    """尝试从请求头获取用户ID（不强制要求登录）"""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        payload = decode_token(token)
        if payload:
            return payload.get('user_id')
    return None


def _auto_load_kb():
    """启动时自动加载知识库并构建向量索引"""
    global current_kb_cards, vector_index
    if not KB_FOLDER.exists():
        return
    cards = []
    for folder in KB_FOLDER.iterdir():
        if folder.is_dir():
            try:
                loaded = load_knowledge_cards(folder)
                cards.extend(loaded)
            except Exception as e:
                print(f"[KB] 加载 {folder.name} 失败: {e}")
    if cards:
        current_kb_cards = cards
        try:
            documents = cards_to_documents(cards)
            vector_index = build_vector_index(documents)
            print(f"[KB] 自动加载知识库成功：{len(cards)} 张卡片，向量索引已构建")
        except Exception as e:
            print(f"[KB] 构建向量索引失败: {e}")
    else:
        print("[KB] 未找到知识卡片")


def _resolve_active_llm_config() -> dict:
    """读取管理员当前生效的系统级 AI 配置；若未配置则回退到环境变量默认值"""
    cfg = get_active_system_ai_config() or {}
    api_key = (cfg.get('api_key') or '').strip() or DEEPSEEK_API_KEY
    base_url = (cfg.get('base_url') or '').strip() or "https://api.deepseek.com/v1"
    model = (cfg.get('model') or '').strip() or "deepseek-chat"
    provider = (cfg.get('provider') or 'deepseek').strip() or 'deepseek'
    return {
        'id': cfg.get('id'),
        'provider': provider,
        'api_key': api_key,
        'base_url': base_url,
        'model': model,
    }


def get_llm_client(dry_run: bool = False):
    """获取 LLM 客户端（读取管理员在系统级配置表中启用的凭证）"""
    cfg = _resolve_active_llm_config()
    if dry_run or not cfg['api_key']:
        return DryRunClient()
    return DeepSeekClient(api_key=cfg['api_key'], base_url=cfg['base_url'], model=cfg['model'])


def get_web_searcher(use_mock: bool = True):
    """获取 Web 搜索器（优先 Tavily API，回退 Mock；LLM 凭证来自系统级 AI 配置）"""
    global web_searcher
    if web_searcher is None:
        cfg = _resolve_active_llm_config()
        web_searcher = WebSearcher(
            use_mock=use_mock,
            llm_api_key=cfg['api_key'],
            tavily_api_key=TAVILY_API_KEY,
        )
    return web_searcher


# ============ 基础路由 ============

@app.route('/')
def index():
    """前端入口"""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'version': '2.0.0',
        'features': ['browser', 'slots', 'clarification']
    })


# ============ 用户认证 ============

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    """用户注册"""
    data = request.get_json() or {}
    result, status = register_user(
        username=data.get('username', ''),
        password=data.get('password', ''),
        display_name=data.get('displayName', '')
    )
    return jsonify(result), status


@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """用户登录"""
    data = request.get_json() or {}
    result, status = login_user(
        username=data.get('username', ''),
        password=data.get('password', '')
    )
    return jsonify(result), status


@app.route('/api/auth/profile', methods=['GET'])
@login_required
def api_profile():
    """获取当前用户信息"""
    user = g.current_user
    stats = get_user_stats(user['id'])
    return jsonify({
        'success': True,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'display_name': user['display_name'],
            'role': user['role'],
            'created_at': user['created_at'],
            'last_login': user['last_login']
        },
        'stats': stats
    })


@app.route('/api/auth/profile', methods=['PUT'])
@login_required
def api_update_profile():
    """更新个人信息（显示名称）"""
    data = request.get_json() or {}
    display_name = data.get('display_name', '').strip()
    if not display_name:
        return jsonify({'success': False, 'error': '显示名称不能为空'}), 400
    if len(display_name) > 30:
        return jsonify({'success': False, 'error': '显示名称不能超过30个字符'}), 400

    me = g.current_user
    update_user_profile(me['id'], display_name)
    audit('profile_update', 'user', str(me['id']), f'修改显示名称为: {display_name}')

    updated_user = get_user_by_id(me['id'])
    return jsonify({
        'success': True,
        'message': '个人信息已更新',
        'user': {
            'id': updated_user['id'],
            'username': updated_user['username'],
            'display_name': updated_user['display_name'],
            'role': updated_user['role']
        }
    })


@app.route('/api/auth/password', methods=['PUT'])
@login_required
def api_change_password():
    """修改密码"""
    data = request.get_json() or {}
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')

    if not old_password or not new_password:
        return jsonify({'success': False, 'error': '请输入旧密码和新密码'}), 400
    if len(new_password) < 6:
        return jsonify({'success': False, 'error': '新密码至少6个字符'}), 400

    me = g.current_user
    if not check_password_hash(me['password_hash'], old_password):
        return jsonify({'success': False, 'error': '旧密码不正确'}), 400

    new_hash = generate_password_hash(new_password)
    update_user_password(me['id'], new_hash)
    audit('password_change', 'user', str(me['id']), '修改密码')
    return jsonify({'success': True, 'message': '密码已修改'})


@app.route('/api/auth/reports', methods=['GET'])
@login_required
def api_user_reports():
    """获取当前用户的报告历史"""
    reports = get_user_reports(g.current_user['id'])
    return jsonify({'success': True, 'reports': reports})


# ============ 组织管理 ============

@app.route('/api/orgs', methods=['GET'])
@login_required
def api_list_orgs():
    """获取当前用户所属的组织列表"""
    orgs = get_user_organizations(g.current_user['id'])
    for org in orgs:
        normalize_org_member_roles(org['id'])
    orgs = get_user_organizations(g.current_user['id'])
    return jsonify({'success': True, 'organizations': orgs})


@app.route('/api/orgs/discover', methods=['GET'])
@login_required
def api_discover_orgs():
    """获取当前用户可加入的组织列表"""
    orgs = list_joinable_organizations(g.current_user['id'])
    return jsonify({'success': True, 'organizations': orgs})


@app.route('/api/orgs', methods=['POST'])
@login_required
def api_create_org():
    """创建组织"""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name or len(name) < 2:
        return jsonify({'success': False, 'error': '组织名称至少2个字符'}), 400
    try:
        org_id = create_organization(name, data.get('description', ''), g.current_user['id'])
        audit('create_org', 'organization', str(org_id), f'创建组织: {name}')
        return jsonify({'success': True, 'org_id': org_id, 'message': '组织创建成功'}), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/orgs/<int:org_id>/join', methods=['POST'])
@login_required
def api_join_org(org_id):
    """加入组织（面向普通成员开放）"""
    me = g.current_user
    org = get_organization(org_id)
    if not org:
        return jsonify({'success': False, 'error': '组织不存在'}), 404
    if is_org_member(org_id, me['id']):
        return jsonify({'success': False, 'error': '你已加入该组织'}), 409
    ok = add_org_member(org_id, me['id'], 'member')
    if not ok:
        return jsonify({'success': False, 'error': '加入失败'}), 400
    audit('join_org', 'organization', str(org_id), f'加入组织: {org["name"]}')
    return jsonify({'success': True, 'message': f'已加入 {org["name"]}'})


@app.route('/api/orgs/<int:org_id>/leave', methods=['POST'])
@login_required
def api_leave_org(org_id):
    """退出组织"""
    me = g.current_user
    org = get_organization(org_id)
    if not org:
        return jsonify({'success': False, 'error': '组织不存在'}), 404
    if not is_org_member(org_id, me['id']):
        return jsonify({'success': False, 'error': '你不在该组织中'}), 400
    if count_org_members(org_id) <= 1:
        deleted_doc_count = _destroy_org_assets(org_id)
        audit('delete_org', 'organization', str(org_id), f'最后一名成员退出并删除组织: {org["name"]}')
        return jsonify({
            'success': True,
            'deleted_org': True,
            'deleted_doc_count': deleted_doc_count,
            'message': f'你是最后一名成员，组织 {org["name"]} 已删除'
        })
    ok = remove_org_member(org_id, me['id'])
    if not ok:
        return jsonify({'success': False, 'error': '退出失败'}), 400
    audit('leave_org', 'organization', str(org_id), f'退出组织: {org["name"]}')
    return jsonify({'success': True, 'deleted_org': False, 'message': f'已退出 {org["name"]}'})


@app.route('/api/orgs/<int:org_id>/export', methods=['GET'])
@login_required
def api_export_org(org_id):
    """导出组织知识库"""
    org = get_organization(org_id)
    if not org:
        return jsonify({'success': False, 'error': '组织不存在'}), 404
    if not is_org_member(org_id, g.current_user['id']):
        return jsonify({'success': False, 'error': '无权限'}), 403
    archive_path = _build_org_export_archive(org)
    audit('export_org_archive', 'organization', str(org_id), f'导出组织知识库: {org["name"]}')
    return send_file(str(archive_path), as_attachment=True, download_name=archive_path.name)


@app.route('/api/orgs/<int:org_id>/members', methods=['GET'])
@login_required
def api_org_members(org_id):
    """获取组织成员列表（需为组织成员）"""
    normalize_org_member_roles(org_id)
    if not is_org_member(org_id, g.current_user['id']) and g.current_user['role'] == 'user':
        return jsonify({'success': False, 'error': '无权限'}), 403
    members = get_org_members(org_id)
    return jsonify({'success': True, 'members': members})


@app.route('/api/orgs/<int:org_id>/members', methods=['POST'])
@login_required
def api_add_org_member(org_id):
    """添加组织成员（组织成员同权）"""
    normalize_org_member_roles(org_id)
    if not is_org_member(org_id, g.current_user['id']):
        return jsonify({'success': False, 'error': '无权限'}), 403
    data = request.get_json() or {}
    username = data.get('username', '')
    target_user = get_user_by_username(username)
    if not target_user:
        return jsonify({'success': False, 'error': f'用户 {username} 不存在'}), 404
    ok = add_org_member(org_id, target_user['id'], 'member')
    if not ok:
        return jsonify({'success': False, 'error': '该用户已在组织中'}), 409
    audit('add_org_member', 'organization', str(org_id), f'添加成员: {username}')
    return jsonify({'success': True, 'message': f'已添加 {username}'})


@app.route('/api/orgs/<int:org_id>/members/<int:user_id>/role', methods=['PUT'])
@login_required
def api_update_org_member(org_id, user_id):
    """组织成员同权，保留接口兼容旧前端"""
    normalize_org_member_roles(org_id)
    if not is_org_member(org_id, g.current_user['id']):
        return jsonify({'success': False, 'error': '无权限'}), 403
    if not get_org_member_role(org_id, user_id):
        return jsonify({'success': False, 'error': '成员不存在'}), 404
    return jsonify({'success': True, 'message': '组织成员同权，无需设置角色'})


@app.route('/api/orgs/<int:org_id>/members/<int:user_id>', methods=['DELETE'])
@login_required
def api_remove_org_member(org_id, user_id):
    """移除组织成员"""
    normalize_org_member_roles(org_id)
    if not is_org_member(org_id, g.current_user['id']):
        return jsonify({'success': False, 'error': '无权限'}), 403
    if count_org_members(org_id) <= 1:
        return jsonify({'success': False, 'error': '组织至少保留 1 名成员'}), 400
    ok = remove_org_member(org_id, user_id)
    if not ok:
        return jsonify({'success': False, 'error': '成员不存在'}), 404
    audit('remove_org_member', 'organization', str(org_id), f'移除成员ID: {user_id}')
    return jsonify({'success': True, 'message': '已移除'})


@app.route('/api/orgs/<int:org_id>/reports', methods=['GET'])
@login_required
def api_org_reports(org_id):
    """获取组织内的报告（组织成员共享可见）"""
    if not is_org_member(org_id, g.current_user['id']) and g.current_user['role'] == 'user':
        return jsonify({'success': False, 'error': '无权限'}), 403
    reports = get_org_reports(org_id)
    return jsonify({'success': True, 'reports': reports})


# ============ 管理员接口 ============

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def api_admin_users():
    """列出用户（管理员可查看所有用户）"""
    me = g.current_user
    users = list_all_users()
    scope = 'all'
    if False:
        users = list_org_users_for_admin(me['id'])
        scope = 'org'
    return jsonify({'success': True, 'users': users, 'scope': scope})


@app.route('/api/admin/users/<int:user_id>/role', methods=['PUT'])
@admin_required
def api_admin_set_role(user_id):
    """设置用户角色。"""
    me = g.current_user
    data = request.get_json() or {}
    role = data.get('role', '')

    if not update_user_role(user_id, role):
        return jsonify({'success': False, 'error': f'无效角色: {role}，可选: user/admin'}), 400
    audit('change_role', 'user', str(user_id), f'角色变更为: {role}，操作者: {me["username"]}')
    return jsonify({'success': True, 'message': f'角色已更新为 {role}'})


@app.route('/api/admin/audit-logs', methods=['GET'])
@admin_required
def api_admin_audit_logs():
    """审计日志（管理员可查看所有日志）"""
    me = g.current_user
    limit = request.args.get('limit', 100, type=int)
    action = request.args.get('action')
    uid = request.args.get('user_id', type=int)
    logs = get_audit_logs(limit=limit, user_id=uid, action=action)
    if False:
        logs = get_audit_logs_for_admin(me['id'], limit=limit, action=action)
    return jsonify({'success': True, 'logs': logs})


# ============ API Key 管理（管理员） ============

@app.route('/api/admin/api-keys', methods=['GET'])
@admin_required
def api_list_keys():
    """列出当前管理员的 API 密钥"""
    keys = get_user_api_keys(g.current_user['id'])
    return jsonify({'success': True, 'keys': keys})


@app.route('/api/admin/api-keys', methods=['POST'])
@admin_required
def api_create_key():
    """创建新的 API 密钥（创建后仅展示一次）"""
    data = request.get_json() or {}
    key_id, raw_key = create_api_key(
        g.current_user['id'],
        name=data.get('name', ''),
        permissions=data.get('permissions', 'read,write')
    )
    audit('create_api_key', 'api_key', str(key_id), f'创建API密钥: {data.get("name", "")}')
    return jsonify({
        'success': True,
        'key_id': key_id,
        'api_key': raw_key,
        'message': '请妥善保存此密钥，它不会再次显示'
    }), 201


@app.route('/api/admin/api-keys/<int:key_id>', methods=['DELETE'])
@admin_required
def api_delete_key(key_id):
    """停用 API 密钥"""
    ok = deactivate_api_key(key_id, g.current_user['id'])
    if not ok:
        return jsonify({'success': False, 'error': '密钥不存在'}), 404
    audit('deactivate_api_key', 'api_key', str(key_id))
    return jsonify({'success': True, 'message': '密钥已停用'})


# ============ 标准数据 Schema（通用性 API） ============

@app.route('/api/schema', methods=['GET'])
def api_get_schema():
    """获取标准数据输入 Schema 定义和示例"""
    return jsonify({
        'success': True,
        'schema': STANDARD_SCHEMA,
        'example': EXAMPLE_INPUT,
        'description': '任何外部平台按此 Schema 提交 JSON 数据即可调用报告生成 API'
    })


@app.route('/api/schema/validate', methods=['POST'])
def api_validate_schema():
    """验证提交的数据是否符合标准 Schema"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请提交 JSON 数据'}), 400
    is_valid, error = validate_standard_input(data)
    return jsonify({'success': is_valid, 'error': error if not is_valid else None})


@app.route('/api/ingest', methods=['POST'])
@login_required
def api_ingest_data():
    """通过标准 Schema 直接提交数据（通用 API，外部平台集成入口）
    
    支持认证方式：
      - Bearer JWT token（前端用户）
      - ApiKey sr_xxx...（外部平台）
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请提交 JSON 数据'}), 400

    is_valid, error = validate_standard_input(data)
    if not is_valid:
        return jsonify({'success': False, 'error': f'数据格式错误: {error}'}), 400

    global current_data_package

    # 将标准 Schema 数据转换为内部 facts 格式
    facts = normalize_to_facts(data)

    # 存入全局状态供后续报告生成使用
    current_data_package = f"[API] {facts['manifest'].get('dataset_name', 'unnamed')}"

    audit('ingest_data', 'data_package', current_data_package,
          f"平台: {facts['manifest'].get('source_platform')}, 变量数: {len(facts['variables'])}")

    # 异步模式：如果请求包含 async=true，启动后台任务
    if data.get('async'):
        def _async_ingest_task(_task_id, _task_manager, **kw):
            _task_manager.update_progress(_task_id, 50, '数据已接收，正在处理…')
            # 此处可扩展：自动触发报告生成等后续流程
            _task_manager.update_progress(_task_id, 100, '处理完成')
            return {
                'source_platform': facts['manifest'].get('source_platform'),
                'dataset_name': facts['manifest'].get('dataset_name'),
                'variables_count': len(facts['variables']),
            }

        tid = task_manager.submit(_async_ingest_task)
        return jsonify({
            'success': True,
            'async': True,
            'task_id': tid,
            'message': '数据已提交异步处理',
        }), 202

    return jsonify({
        'success': True,
        'message': '数据已接收',
        'summary': {
            'source_platform': facts['manifest'].get('source_platform'),
            'dataset_name': facts['manifest'].get('dataset_name'),
            'variables_count': len(facts['variables']),
            'block_count': facts['datasets'].get('block_count', 0),
        }
    })


# ============ 异步任务查询 ============

@app.route('/api/tasks/<task_id>', methods=['GET'])
@login_required
def api_task_status(task_id):
    """查询异步任务状态"""
    status = task_manager.get_status(task_id)
    if status is None:
        return jsonify({'success': False, 'error': '任务不存在'}), 404
    return jsonify({'success': True, 'task': status})


@app.route('/api/tasks', methods=['GET'])
@login_required
def api_list_tasks():
    """列出最近的异步任务"""
    limit = request.args.get('limit', 20, type=int)
    return jsonify({'success': True, 'tasks': task_manager.list_tasks(limit)})


# ============ 报告模板 ============

@app.route('/api/templates', methods=['GET'])
def api_list_templates():
    """列出所有可用的报告模板"""
    return jsonify({
        'success': True,
        'templates': list_report_templates()
    })


# ============ MCP 标准开放 API ============

@app.route('/mcp/tools/list', methods=['GET', 'POST'])
@login_required
def mcp_tools_list():
    """MCP 标准端点 — 列出所有可用工具（JSON Schema 格式）"""
    tools = []
    for t in MCP_TOOLS:
        func = t.get('function', t)
        tools.append({
            'name': func['name'],
            'description': func['description'],
            'inputSchema': func.get('parameters', {}),
        })
    return jsonify({'tools': tools})


@app.route('/mcp/tools/call', methods=['POST'])
@login_required
def mcp_tools_call():
    """MCP 标准端点 — 调用指定工具

    Body: { "name": "get_run_info", "arguments": {} }
    """
    data = request.get_json() or {}
    tool_name = data.get('name', '')
    arguments = data.get('arguments', {})

    if not tool_name:
        return jsonify({'error': '缺少 name 参数'}), 400

    # 检查工具是否存在
    valid_names = {t.get('function', t)['name'] for t in MCP_TOOLS}
    if tool_name not in valid_names:
        return jsonify({'error': f'未知工具: {tool_name}', 'available': sorted(valid_names)}), 404

    audit('mcp_tool_call', 'tool', tool_name, json.dumps(arguments, ensure_ascii=False)[:200])

    result_str = _execute_mcp_tool(tool_name, arguments)
    try:
        result = json.loads(result_str)
    except Exception:
        result = {'raw': result_str}

    return jsonify({
        'tool': tool_name,
        'result': result,
        'isError': 'error' in result,
    })


@app.route('/api/tools/<tool_name>', methods=['POST'])
@login_required
def api_tool_shortcut(tool_name):
    """便捷端点 — 直接调用指定 MCP 工具（/api/tools/{name}）

    Body: 工具参数 JSON
    """
    valid_names = {t.get('function', t)['name'] for t in MCP_TOOLS}
    if tool_name not in valid_names:
        return jsonify({'error': f'未知工具: {tool_name}', 'available': sorted(valid_names)}), 404

    arguments = request.get_json() or {}
    audit('api_tool_call', 'tool', tool_name, json.dumps(arguments, ensure_ascii=False)[:200])

    result_str = _execute_mcp_tool(tool_name, arguments)
    try:
        result = json.loads(result_str)
    except Exception:
        result = {'raw': result_str}

    return jsonify({'tool': tool_name, 'result': result})


@app.route('/mcp/resources/list', methods=['GET', 'POST'])
@login_required
def mcp_resources_list():
    """MCP 标准端点 — 列出可用资源"""
    resources = []
    if current_data_package:
        resources.append({
            'uri': f'datapackage://{current_data_package}',
            'name': '当前数据包',
            'mimeType': 'application/json',
        })
    if draft_manager.current_draft:
        resources.append({
            'uri': 'draft://current',
            'name': '当前 Draft',
            'mimeType': 'application/json',
        })
    resources.append({
        'uri': 'kb://cards',
        'name': '知识库卡片列表',
        'mimeType': 'application/json',
    })
    return jsonify({'resources': resources})


@app.route('/mcp/resources/read', methods=['GET', 'POST'])
@login_required
def mcp_resources_read():
    """MCP 标准端点 — 读取指定资源"""
    uri = request.args.get('uri') or (request.get_json() or {}).get('uri', '')
    if not uri:
        return jsonify({'error': '缺少 uri 参数'}), 400

    if uri.startswith('datapackage://'):
        if not current_data_package:
            return jsonify({'error': '未加载数据包'}), 400
        facts, err = _get_current_facts()
        if err:
            return jsonify({'error': err}), 400
        return jsonify({'uri': uri, 'mimeType': 'application/json', 'text': json.dumps(facts, ensure_ascii=False, default=str)})

    if uri == 'draft://current':
        if not draft_manager.current_draft:
            return jsonify({'error': '未创建 Draft'}), 400
        return jsonify({'uri': uri, 'mimeType': 'application/json', 'text': json.dumps(draft_manager.current_draft.to_dict(), ensure_ascii=False, default=str)})

    if uri == 'kb://cards':
        cards = [{'id': c.id, 'title': c.title, 'tags': c.tags} for c in current_kb_cards]
        return jsonify({'uri': uri, 'mimeType': 'application/json', 'text': json.dumps(cards, ensure_ascii=False)})

    return jsonify({'error': f'未知资源: {uri}'}), 404


@app.route('/api/v1/report/generate', methods=['POST'])
@login_required
def api_v1_report_generate():
    """开放 API — 一键生成报告（同步/异步）

    Body: {
      "data": { ... 标准 Schema 数据或文件夹路径 ... },
      "config": { "domain": "external_aero", "phenomena": ["shock_wave"], ... },
      "async": false
    }
    """
    body = request.get_json() or {}
    global current_data_package

    # ── 1. 数据接入 ──
    data_input = body.get('data', {})
    config = body.get('config', {})
    is_async = body.get('async', False)

    # 如果提供 path 字段 → 本地文件夹
    if 'path' in data_input:
        folder_path = Path(data_input['path'])
        if not folder_path.exists():
            return jsonify({'success': False, 'error': f'路径不存在: {folder_path}'}), 400
        current_data_package = str(folder_path)
    elif 'manifest' in data_input:
        # 标准 Schema 数据
        is_valid, error = validate_standard_input(data_input)
        if not is_valid:
            return jsonify({'success': False, 'error': f'数据格式错误: {error}'}), 400
        facts_from_schema = normalize_to_facts(data_input)
        current_data_package = f"[API] {facts_from_schema['manifest'].get('dataset_name', 'unnamed')}"
    elif not current_data_package:
        return jsonify({'success': False, 'error': '请提供 data.path 或 data.manifest'}), 400

    # ── 2. 解析+配置+生成+导出 ──
    def _do_generate():
        pkg_data = parse_data_package(Path(current_data_package)) if not current_data_package.startswith('[API]') else None
        if pkg_data:
            facts = build_run_facts(pkg_data, config.get('engine_model_name', ''), config.get('project_code', ''))
        else:
            facts = facts_from_schema  # noqa: F821

        answers = {
            'domain': config.get('domain', 'general_cfd'),
            'phenomena': config.get('phenomena', []),
            'purpose': config.get('purpose', 'performance_evaluation'),
            'inference_level': config.get('inference_level', 'may_infer'),
            'enable_web_search': config.get('enable_web_search', False),
        }
        policy = PolicyBuilder.build_from_answers(answers)
        draft = draft_manager.create_draft(facts, policy=policy)

        filler = _make_slot_filler(False)
        batch_filler = BatchSlotFiller(filler)
        results = batch_filler.fill_all_slots(draft.slots, draft.facts, draft.policy)
        for r in results:
            draft_manager.update_slot_content(
                r['slot_id'], r['content'],
                claims=r.get('claims', []),
                evidence_pack=r.get('evidence_pack', {}),
                status=SlotStatus.DRAFT,
            )
        for s in draft.slots:
            if s.status == SlotStatus.DRAFT:
                draft_manager.accept_slot(s.slot_id, force=True)

        # 导出
        export_result_str = _execute_mcp_tool('export_report', {})
        return json.loads(export_result_str)

    if is_async:
        def _async_task(_task_id, _task_manager, **kw):
            _task_manager.update_progress(_task_id, 10, '正在生成报告…')
            result = _do_generate()
            _task_manager.update_progress(_task_id, 100, '完成')
            return result

        tid = task_manager.submit(_async_task)
        return jsonify({'success': True, 'async': True, 'task_id': tid}), 202

    try:
        result = _do_generate()
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify(_err(e)), 500


# ============ 数据包规范 ============

@app.route('/api/data-package/spec', methods=['GET'])
def api_data_package_spec():
    """获取数据包格式规范（DataPackage Spec）"""
    return jsonify({
        'success': True,
        'spec': get_spec_summary()
    })


@app.route('/api/data-package/validate', methods=['POST'])
@login_required
def api_validate_data_package():
    """验证当前已加载的数据包是否符合 DataPackage Spec"""
    if not current_data_package:
        return jsonify({'success': False, 'error': '请先上传数据包'}), 400

    # 通过 /api/ingest 接口加载的 API 数据不是本地路径，无法做文件验证
    if current_data_package.startswith('[API]'):
        return jsonify({
            'success': True,
            'validation': {
                'is_valid': True,
                'errors': [],
                'warnings': ['API 数据包无需路径验证，格式已通过 Schema 校验']
            }
        })

    pkg_path = Path(current_data_package)
    is_valid, errors, warnings = validate_data_package(pkg_path)

    return jsonify({
        'success': True,
        'is_valid': is_valid,
        'spec_version': DP_SPEC_VERSION,
        'errors': errors,
        'warnings': warnings,
        'path': str(pkg_path)
    })


# ============ 数据包上传 ============

@app.route('/api/upload-folder', methods=['POST'])
@login_required
def upload_folder():
    """设置本地文件夹路径作为数据包"""

    data = request.get_json()
    if not data or 'path' not in data:
        return jsonify({'success': False, 'error': '请提供文件夹路径'}), 400

    folder_path = Path(data['path'])
    if not folder_path.exists():
        return jsonify({'success': False, 'error': f'路径不存在: {folder_path}'}), 400

    _set_current_data_package(str(folder_path))

    try:
        # 自动验证数据包合规性
        is_valid, spec_errors, spec_warnings = validate_data_package(folder_path)

        pkg_data = parse_data_package(folder_path)
        manifest = pkg_data.get('manifest', {})
        datasets = pkg_data.get('datasets', {})
        variables = pkg_data.get('variables', [])
        return jsonify({
            'success': True,
            'message': f'数据包已加载: {folder_path.name}',
            'path': str(folder_path),
            'info': {
                'datasetType': manifest.get('dataset_type', 'Unknown'),
                'blockCount': manifest.get('block_count', datasets.get('block_count', 0)),
                'totalPoints': manifest.get('total_points', datasets.get('total_points', 0)),
                'totalCells': manifest.get('total_cells', datasets.get('total_cells', 0)),
                'variableCount': len(variables),
                'variables': [v.get('name') for v in variables]
            },
            'validation': {
                'spec_version': DP_SPEC_VERSION,
                'is_valid': is_valid,
                'errors': spec_errors,
                'warnings': spec_warnings
            }
        })
    except Exception as e:
        return jsonify({
            'success': True,
            'message': f'数据包已加载（部分解析失败）: {folder_path.name}',
            'path': str(folder_path),
            'warning': str(e)
        })


@app.route('/api/upload', methods=['POST'])
@login_required
def upload_data_package():
    """上传数据包（ZIP文件）"""

    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '未找到文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': '未选择文件'}), 400

    filename = secure_filename(file.filename)
    save_path = UPLOAD_FOLDER / filename
    file.save(str(save_path))

    if filename.endswith('.zip'):
        import zipfile
        extract_dir = UPLOAD_FOLDER / filename.replace('.zip', '')
        with zipfile.ZipFile(str(save_path), 'r') as zip_ref:
            zip_ref.extractall(str(extract_dir))
        _set_current_data_package(str(extract_dir))
    else:
        _set_current_data_package(str(save_path))

    return jsonify({
        'success': True,
        'message': f'数据包上传成功: {filename}',
        'path': current_data_package
    })


@app.route('/api/session/context', methods=['GET'])
@login_required
def get_session_context():
    package_info = None
    if current_data_package:
        folder_path = Path(current_data_package)
        package_info = {
            'path': str(folder_path),
            'name': folder_path.name,
        }
        try:
            pkg_data = parse_data_package(folder_path)
            manifest = pkg_data.get('manifest', {})
            datasets = pkg_data.get('datasets', {})
            variables = pkg_data.get('variables', [])
            package_info['info'] = {
                'datasetType': manifest.get('dataset_type', 'Unknown'),
                'blockCount': manifest.get('block_count', datasets.get('block_count', 0)),
                'totalPoints': manifest.get('total_points', datasets.get('total_points', 0)),
                'totalCells': manifest.get('total_cells', datasets.get('total_cells', 0)),
                'variableCount': len(variables),
                'variables': [v.get('name') for v in variables]
            }
        except Exception as e:
            package_info['warning'] = str(e)

    has_draft = draft_manager.current_draft is not None
    progress = draft_manager.get_progress() if has_draft else None

    if has_draft:
        recommended_step = 'generate'
    elif package_info:
        recommended_step = 'clarification'
    else:
        recommended_step = 'upload'

    return jsonify({
        'success': True,
        'user': {
            'id': g.current_user.get('id'),
            'username': g.current_user.get('username'),
            'role': g.current_user.get('role'),
        },
        'defaultPackagePath': str(DEFAULT_DATA_PACKAGE_DIR),
        'hasDataPackage': package_info is not None,
        'dataPackage': package_info,
        'hasDraft': has_draft,
        'progress': progress,
        'recommendedStep': recommended_step
    })


@app.route('/api/session/reset', methods=['POST'])
@login_required
def reset_session_context():
    _reset_current_workflow_state()
    return jsonify({
        'success': True,
        'message': '当前数据包与 Draft 已清空',
        'recommendedStep': 'upload'
    })


# ============ Clarification Gate ============

@app.route('/api/clarification/questions', methods=['GET'])
def get_clarification_questions():
    """获取 Clarification 问题。"""
    global current_data_package

    if not current_data_package:
        return jsonify({'success': False, 'error': '请先上传数据包'}), 400
    
    try:
        pkg_data = parse_data_package(Path(current_data_package))
        facts = build_run_facts(pkg_data, "", "")
        generator = ClarificationGenerator()
        questions = generator.generate_questions(facts)
        return jsonify({
            'success': True,
            'questions': [q.to_dict() for q in questions],
            'domains': DOMAINS,
            'phenomena': PHENOMENA,
            'purposes': PURPOSES
        })
    except Exception as e:
        return jsonify(_err(e)), 500


@app.route('/api/clarification/submit', methods=['POST'])
def submit_clarification_answers():
    """提交 Clarification 答案并创建 Draft。"""
    global current_data_package, draft_manager

    data = request.get_json() or {}
    answers = data.get('answers', {})

    if not answers:
        return jsonify({'success': False, 'error': '请提供答案'}), 400

    if not current_data_package:
        return jsonify({'success': False, 'error': '请先上传数据包'}), 400

    try:
        # 解析数据包
        pkg_data = parse_data_package(Path(current_data_package))
        facts = build_run_facts(pkg_data, 
                               data.get('engineModelName', ''),
                               data.get('projectCode', ''))
        
        # 转换图片路径为API URL
        images = facts.get('images', {})
        for category in images:
            images[category] = [
                f"/api/images/{Path(p).relative_to(Path(current_data_package))}"
                for p in images[category]
            ]
        
        # 转换automation_ops中的图片路径
        automation_ops = facts.get('automation_ops', [])
        for op in automation_ops:
            if 'images' in op and op['images']:
                op['images'] = [
                    f"/api/images/{Path(img).relative_to(Path(current_data_package))}"
                    if Path(img).is_absolute() else f"/api/images/automation/ops/{op['folder']}/images/{Path(img).name}"
                    for img in op['images']
                ]
        
        # 构建策略
        policy = PolicyBuilder.build_from_answers(answers)
        
        # 创建Draft
        draft = draft_manager.create_draft(facts, policy=policy)
        draft_manager.set_clarification_answers(answers)
        
        # 返回facts供前端使用
        response_data = {
            'success': True,
            'draft_id': draft.draft_id,
            'policy': policy.to_dict(),
            'slots': [s.to_dict() for s in draft.slots],
            'facts': facts,
            'progress': draft_manager.get_progress()
        }
        
        return jsonify(response_data)
    except Exception as e:
        return jsonify(_err(e)), 500


# ============ 图片服务 ============

@app.route('/api/images/<path:image_path>')
def serve_image(image_path):
    """提供数据包中的图片"""
    if not current_data_package:
        return jsonify({'error': '未加载数据包'}), 400
    
    # 构建完整路径
    full_path = Path(current_data_package) / image_path
    if not full_path.exists():
        # 尝试在images目录下查找
        full_path = Path(current_data_package) / 'images' / image_path
    
    if full_path.exists() and full_path.is_file():
        return send_file(str(full_path), mimetype='image/png')
    
    return jsonify({'error': f'图片不存在: {image_path}'}), 404


@app.route('/api/data-package/facts', methods=['GET'])
def get_data_package_facts():
    """获取当前数据包的完整facts"""
    if not current_data_package:
        return jsonify({'success': False, 'error': '未加载数据包'}), 400
    
    try:
        pkg_data = parse_data_package(Path(current_data_package))
        facts = build_run_facts(pkg_data, '', '')
        
        # 转换图片路径为API URL
        images = facts.get('images', {})
        for category in images:
            images[category] = [
                f"/api/images/{Path(p).relative_to(Path(current_data_package))}"
                for p in images[category]
            ]
        
        # 转换automation_ops中的图片路径
        automation_ops = facts.get('automation_ops', [])
        for op in automation_ops:
            if 'images' in op and op['images']:
                op['images'] = [
                    f"/api/images/{Path(img).relative_to(Path(current_data_package))}"
                    if Path(img).is_absolute() else f"/api/images/automation/ops/{op['folder']}/images/{Path(img).name}"
                    for img in op['images']
                ]
        
        return jsonify({
            'success': True,
            'facts': facts
        })
    except Exception as e:
        return jsonify(_err(e)), 500


# ============ Draft管理 ============

@app.route('/api/draft', methods=['GET'])
def get_current_draft():
    """获取当前Draft"""
    if draft_manager.current_draft is None:
        return jsonify({'success': False, 'error': '未创建Draft'}), 400
    
    # 转换图片路径为API URL
    draft_dict = draft_manager.current_draft.to_dict()
    if current_data_package and 'facts' in draft_dict:
        images = draft_dict['facts'].get('images', {})
        for category in images:
            new_list = []
            for p in images[category]:
                p_str = str(p)
                if p_str.startswith('/api/images/'):
                    new_list.append(p_str)  # 已经是 API 路径，不再转换
                elif Path(p_str).is_absolute():
                    try:
                        new_list.append(f"/api/images/{Path(p_str).relative_to(Path(current_data_package))}")
                    except ValueError:
                        new_list.append(p_str)
                else:
                    new_list.append(f"/api/images/{p_str}")
            images[category] = new_list
    
    return jsonify({
        'success': True,
        'draft': draft_dict,
        'progress': draft_manager.get_progress()
    })


@app.route('/api/draft/policy', methods=['PUT'])
def update_policy():
    """更新策略"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请提供策略更新'}), 400
    
    affected_slots = draft_manager.update_policy(data)
    current_draft = draft_manager.current_draft
    
    return jsonify({
        'success': True,
        'affected_slots': affected_slots,
        'policy': current_draft.policy.to_dict() if current_draft else data,
        'draft_exists': current_draft is not None
    })


# ============ 槽位操作 ============

@app.route('/api/slots', methods=['GET'])
def get_slots():
    """获取所有槽位"""
    if draft_manager.current_draft is None:
        return jsonify({'success': False, 'error': '未创建Draft'}), 400
    
    return jsonify({
        'success': True,
        'slots': [s.to_dict() for s in draft_manager.current_draft.slots],
        'progress': draft_manager.get_progress()
    })


@app.route('/api/slots/generate-next', methods=['POST'])
def generate_next_slot():
    """生成下一个槽位"""
    if draft_manager.current_draft is None:
        return jsonify({'success': False, 'error': '未创建Draft'}), 400
    
    data = request.get_json(force=True, silent=True) or {}
    dry_run = data.get('dryRun', False)
    
    try:
        draft = draft_manager.current_draft
        pending_slots = draft.get_pending_slots()
        
        if not pending_slots:
            return jsonify({
                'success': True,
                'message': '所有槽位已生成',
                'completed': True
            })
        
        slot = pending_slots[0]
        
        # 创建填充器
        filler = _make_slot_filler(dry_run)
        
        # 填充槽位
        result = filler.fill_slot(slot, draft.facts, draft.policy)
        
        # 更新槽位
        draft_manager.update_slot_content(
            slot.slot_id,
            result['content'],
            claims=result.get('claims', []),
            evidence_pack=result.get('evidence_pack', {}),
            status=SlotStatus.DRAFT
        )
        
        return jsonify({
            'success': True,
            'slot': draft.get_slot(slot.slot_id).to_dict(),
            'progress': draft_manager.get_progress()
        })
        
    except Exception as e:
        return jsonify(_err(e)), 500


@app.route('/api/slots/generate-all', methods=['POST'])
def generate_all_slots():
    """生成所有槽位"""
    if draft_manager.current_draft is None:
        return jsonify({'success': False, 'error': '未创建Draft'}), 400
    
    data = request.get_json(force=True, silent=True) or {}
    dry_run = data.get('dryRun', False)
    
    try:
        draft = draft_manager.current_draft
        
        filler = _make_slot_filler(dry_run)
        batch_filler = BatchSlotFiller(filler)
        
        results = batch_filler.fill_all_slots(
            draft.slots,
            draft.facts,
            draft.policy
        )
        
        # 更新所有槽位
        for result in results:
            draft_manager.update_slot_content(
                result['slot_id'],
                result['content'],
                claims=result.get('claims', []),
                evidence_pack=result.get('evidence_pack', {}),
                status=SlotStatus.DRAFT
            )
        
        return jsonify({
            'success': True,
            'generated': len(results),
            'slots': [s.to_dict() for s in draft.slots],
            'progress': draft_manager.get_progress()
        })
        
    except Exception as e:
        return jsonify(_err(e)), 500


@app.route('/api/slots/<slot_id>/accept', methods=['POST'])
def accept_slot(slot_id):
    """接受槽位"""
    if draft_manager.current_draft is None:
        return jsonify({'success': False, 'error': '未创建Draft'}), 400
    
    success = draft_manager.accept_slot(slot_id)
    
    if success:
        return jsonify({
            'success': True,
            'slot': draft_manager.current_draft.get_slot(slot_id).to_dict(),
            'progress': draft_manager.get_progress()
        })
    else:
        return jsonify({'success': False, 'error': '槽位不存在'}), 404


@app.route('/api/slots/accept-all', methods=['POST'])
def accept_all_slots():
    """全部确认（接受所有draft状态的槽位）"""
    if draft_manager.current_draft is None:
        return jsonify({'success': False, 'error': '未创建Draft'}), 400
    
    draft = draft_manager.current_draft
    draft_slots = draft.get_draft_slots()
    
    if not draft_slots:
        return jsonify({
            'success': False,
            'error': '没有待确认的槽位'
        }), 400
    
    accepted_count = 0
    for slot in draft_slots:
        if draft_manager.accept_slot(slot.slot_id):
            accepted_count += 1
    
    return jsonify({
        'success': True,
        'accepted_count': accepted_count,
        'slots': [s.to_dict() for s in draft.slots],
        'progress': draft_manager.get_progress()
    })


@app.route('/api/slots/<slot_id>/reject', methods=['POST'])
def reject_slot(slot_id):
    """拒绝槽位"""
    if draft_manager.current_draft is None:
        return jsonify({'success': False, 'error': '未创建Draft'}), 400
    
    data = request.get_json() or {}
    reason = data.get('reason', 'general')
    feedback = data.get('feedback', '')
    
    slot = draft_manager.current_draft.get_slot(slot_id)
    if slot is None:
        return jsonify({'success': False, 'error': '槽位不存在'}), 404
    
    slot.reject_reason = reason
    slot.user_feedback = feedback
    slot.status = SlotStatus.REJECTED
    
    return jsonify({
        'success': True,
        'slot': slot.to_dict(),
        'progress': draft_manager.get_progress()
    })


@app.route('/api/slots/<slot_id>/rewrite', methods=['POST'])
def rewrite_slot(slot_id):
    """改写被拒绝的槽位"""
    if draft_manager.current_draft is None:
        return jsonify({'success': False, 'error': '未创建Draft'}), 400
    
    data = request.get_json(force=True, silent=True) or {}
    dry_run = data.get('dryRun', False)
    
    draft = draft_manager.current_draft
    slot = draft.get_slot(slot_id)
    
    if slot is None:
        return jsonify({'success': False, 'error': '槽位不存在'}), 404
    
    if slot.status != SlotStatus.REJECTED:
        return jsonify({'success': False, 'error': '槽位未被拒绝'}), 400
    
    try:
        filler = _make_slot_filler(dry_run)
        
        result = filler.rewrite_slot(slot, draft.facts, draft.policy, slot.reject_reason)
        cleaned_content = result.get('content', '')
        if hasattr(filler, '_strip_json_wrapper'):
            cleaned_content = filler._strip_json_wrapper(cleaned_content)
        if hasattr(filler, '_strip_source_tags'):
            cleaned_content = filler._strip_source_tags(cleaned_content)
        
        draft_manager.update_slot_content(
            slot_id,
            cleaned_content,
            claims=result.get('claims', []),
            status=SlotStatus.DRAFT
        )
        
        return jsonify({
            'success': True,
            'slot': draft.get_slot(slot_id).to_dict(),
            'progress': draft_manager.get_progress()
        })
        
    except Exception as e:
        return jsonify(_err(e)), 500


@app.route('/api/slots/<slot_id>/edit', methods=['PUT'])
def edit_slot(slot_id):
    """用户编辑槽位"""
    if draft_manager.current_draft is None:
        return jsonify({'success': False, 'error': '未创建Draft'}), 400
    
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({'success': False, 'error': '请提供内容'}), 400
    
    success = draft_manager.edit_slot(slot_id, data['content'])
    
    if success:
        return jsonify({
            'success': True,
            'slot': draft_manager.current_draft.get_slot(slot_id).to_dict(),
            'progress': draft_manager.get_progress()
        })
    else:
        return jsonify({'success': False, 'error': '槽位不存在'}), 404


# ============ 报告质量评估 ============

@app.route('/api/report/quality-check', methods=['POST'])
def api_quality_check():
    """对当前 Draft 进行质量自检评估（Self-Reflection）
    
    支持两种模式：
    1. 服务端 Draft 存在时：使用 draft_manager
    2. 前端传来 slots 数据时：构建临时 draft_dict 进行评估
    """
    data = request.get_json(force=True, silent=True) or {}
    frontend_slots = data.get('slots', [])

    if draft_manager.current_draft is not None:
        draft_dict = draft_manager.current_draft.to_dict()
        filled = [s for s in draft_manager.current_draft.slots if s.content]
    elif frontend_slots:
        # 从前端数据构建临时 draft dict
        filled = [s for s in frontend_slots if s.get('content')]
        draft_dict = {
            'draft_id': 'frontend-fallback',
            'slots': frontend_slots,
            'facts': data.get('facts', {}),
            'policy': data.get('policy', {}),
        }
    else:
        return jsonify({'success': False, 'error': '未创建Draft'}), 400

    if not filled:
        return jsonify({'success': False, 'error': '所有槽位均无内容，无法评估'}), 400

    try:
        from reportgen.pipeline.quality_check import QualityChecker, MockQualityChecker
        llm_client = get_llm_client(dry_run=False)
        if isinstance(llm_client, DryRunClient):
            checker = MockQualityChecker()
        else:
            checker = QualityChecker(llm_client)

        result = checker.check(draft_dict)
        return jsonify({'success': True, 'quality': result})
    except Exception as e:
        return jsonify(_err(e)), 500


@app.route('/api/report/quality-improve', methods=['POST'])
def api_quality_improve():
    """根据质量评估建议自动改进低分槽位
    
    支持两种模式：
    1. 服务端 Draft 存在时：直接操作 draft_manager
    2. 服务端 Draft 不存在时：从前端传来的 slots 数据中读取并改进
    """
    data = request.get_json(force=True) or {}
    suggestions = data.get('suggestions', [])
    low_dimensions = data.get('low_dimensions', [])
    frontend_slots = data.get('slots', [])  # 前端传来的槽位数据

    if not suggestions and not low_dimensions:
        return jsonify({'success': False, 'error': '无改进建议'}), 400

    # 优先使用 draft_manager，否则使用前端传来的 slots
    use_draft = draft_manager.current_draft is not None
    if use_draft:
        slot_list = [
            {'slot_id': s.slot_id, 'content': s.content, 'status': s.status if isinstance(s.status, str) else s.status.value}
            for s in draft_manager.current_draft.slots
            if s.content and (s.status in ('draft', 'accepted') or (hasattr(s.status, 'value') and s.status.value in ('draft', 'accepted')))
        ]
    elif frontend_slots:
        slot_list = [
            {'slot_id': s.get('slot_id', ''), 'content': s.get('content', ''), 'status': s.get('status', '')}
            for s in frontend_slots
            if s.get('content') and s.get('status') in ('draft', 'accepted')
        ]
    else:
        return jsonify({'success': False, 'error': '未创建Draft且前端未提供槽位数据'}), 400

    if not slot_list:
        return jsonify({'success': False, 'error': '没有可改进的槽位'}), 400

    improved_count = 0

    try:
        llm_client = get_llm_client(dry_run=False)
        improvement_prompt = "请根据以下质量评估建议，改进报告内容。\n\n"
        if low_dimensions:
            improvement_prompt += "低分维度：\n"
            for dim in low_dimensions:
                improvement_prompt += f"- {dim.get('name', '')}（当前评分: {dim.get('score', 'N/A')}）\n"
        if suggestions:
            improvement_prompt += "\n改进建议：\n"
            for i, s in enumerate(suggestions, 1):
                improvement_prompt += f"{i}. {s}\n"

        result_slots = []

        for slot_info in slot_list:
            slot_id = slot_info['slot_id']
            content = slot_info['content']
            prompt = (
                f"{improvement_prompt}\n"
                f"以下是槽位「{slot_id}」的当前内容：\n"
                f"{content}\n\n"
                f"请改进以上内容，使其更好地满足质量要求。只输出改进后的内容，不要加任何解释。"
            )
            if isinstance(llm_client, DryRunClient):
                new_content = content + "\n[已根据AI建议优化]"
            else:
                resp = llm_client.chat(
                    messages=[
                        {"role": "system", "content": "你是一个专业的仿真报告改进助手。请根据给出的质量评估建议改进报告内容，保持专业严谨的语言风格。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=2000,
                )
                new_content = resp.get("content", "").strip()
                if resp.get("error"):
                    print(f"[quality-improve] slot {slot_id} error: {resp['error']}")
                    continue

            if new_content:
                # 如果 draft_manager 可用，同步更新
                if use_draft:
                    slot_obj = draft_manager.current_draft.get_slot(slot_id)
                    if slot_obj:
                        slot_obj.content = new_content
                        slot_obj.status = SlotStatus.DRAFT
                result_slots.append({'slot_id': slot_id, 'content': new_content})
                improved_count += 1

        # 返回结果
        if use_draft:
            return jsonify({
                'success': True,
                'improved_count': improved_count,
                'slots': [s.to_dict() for s in draft_manager.current_draft.slots],
                'progress': draft_manager.get_progress()
            })
        else:
            return jsonify({
                'success': True,
                'improved_count': improved_count,
                'improved_slots': result_slots
            })
    except Exception as e:
        return jsonify(_err(e)), 500


# ============ 导出 ============

@app.route('/api/export/draft', methods=['GET'])
def export_draft():
    """导出Draft JSON"""
    if draft_manager.current_draft is None:
        return jsonify({'success': False, 'error': '未创建Draft'}), 400
    
    output_dir = OUTPUT_FOLDER / datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    draft_path = draft_manager.save_draft(str(output_dir / 'draft.json'))
    
    return jsonify({
        'success': True,
        'path': draft_path,
        'draft': draft_manager.current_draft.to_dict()
    })


@app.route('/api/export/report', methods=['POST'])
def export_report():
    """导出报告（Markdown + DOCX）"""
    if draft_manager.current_draft is None:
        return jsonify({'success': False, 'error': '未创建Draft'}), 400
    
    draft = draft_manager.current_draft
    
    # 检查是否所有槽位都已处理
    pending = draft.get_pending_slots()
    if pending:
        return jsonify({
            'success': False,
            'error': f'还有{len(pending)}个槽位未生成',
            'pending_slots': [s.slot_id for s in pending]
        }), 400
    
    try:
        output_dir = OUTPUT_FOLDER / datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 构建filled_slots
        filled_slots = {}
        for slot in draft.slots:
            filled_slots[slot.slot_id] = slot.content
        
        # 复制图片资源
        assets_dir = output_dir / 'assets'
        assets_dir.mkdir(exist_ok=True)
        
        if current_data_package:
            src_images = Path(current_data_package) / 'images'
            if src_images.exists():
                shutil.copytree(src_images, assets_dir, dirs_exist_ok=True)
        
        # 生成Markdown（使用现有函数）
        from reportgen.pipeline.build_md import generate_report_content
        
        # 构建图片映射：原始路径 -> assets相对路径
        image_mapping = {}
        if current_data_package:
            images_dir = Path(current_data_package) / 'images'
            if images_dir.exists():
                for img_file in images_dir.rglob('*.png'):
                    # 原始路径（可能是API路径或相对路径）
                    rel_to_pkg = img_file.relative_to(Path(current_data_package))
                    rel_to_images = img_file.relative_to(images_dir)
                    # 映射到assets目录下的相对路径
                    asset_path = f"assets/{rel_to_images}".replace('\\', '/')
                    # 添加多种可能的原始路径格式
                    image_mapping[str(rel_to_pkg)] = asset_path
                    image_mapping[str(rel_to_pkg).replace('\\', '/')] = asset_path
                    image_mapping[f"/api/images/{rel_to_pkg}"] = asset_path
                    image_mapping[f"/api/images/{str(rel_to_pkg).replace(chr(92), '/')}"] = asset_path
        
        # 修复facts中的图片路径（从API路径转为assets路径）
        export_facts = json.loads(json.dumps(draft.facts))  # 深拷贝
        if 'images' in export_facts:
            for category in export_facts['images']:
                export_facts['images'][category] = [
                    image_mapping.get(p, p) for p in export_facts['images'][category]
                ]
        
        md_content = generate_report_content(export_facts, filled_slots, image_mapping)
        
        md_path = output_dir / 'report.md'
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        # 生成DOCX
        docx_path = output_dir / 'report.docx'
        build_docx_report(md_content, str(docx_path), str(assets_dir))
        
        # 生成PDF（可选，依赖 weasyprint 或 pdfkit）
        pdf_path = output_dir / 'report.pdf'
        pdf_ok = build_pdf_report(md_content, str(pdf_path), str(assets_dir))
        
        # 保存Draft
        draft_path = output_dir / 'draft.json'
        draft_manager.save_draft(str(draft_path))
        
        # 持久化报告历史（如果用户已登录）
        user_id = _get_optional_user_id()
        report_id = None
        if user_id:
            policy = draft.policy
            report_id = create_report_record(
                user_id=user_id,
                title=policy.domain + ' - ' + policy.purpose if policy else '报告',
                data_package_path=current_data_package or '',
                domain=policy.domain if policy else '',
                purpose=policy.purpose if policy else ''
            )
            update_report_record(
                report_id,
                output_dir=str(output_dir),
                slot_count=len(draft.slots),
                status='completed',
                completed_at=datetime.now().isoformat(),
                content_snapshot=md_content
            )

        files_info = {
            'markdown': str(md_path),
            'docx': str(docx_path),
            'draft': str(draft_path)
        }
        if pdf_ok:
            files_info['pdf'] = str(pdf_path)

        return jsonify({
            'success': True,
            'outputDir': str(output_dir),
            'reportId': report_id,
            'files': files_info
        })
        
    except Exception as e:
        return jsonify(_err(e)), 500


@app.route('/api/download/<file_type>', methods=['GET'])
@login_required
def download_file(file_type):
    """下载生成的文件"""
    output_dir = request.args.get('dir')
    if not output_dir:
        return jsonify({'success': False, 'error': '未指定输出目录'}), 400
    
    output_path = Path(output_dir)
    
    file_map = {
        'md': 'report.md',
        'docx': 'report.docx',
        'pdf': 'report.pdf',
        'draft': 'draft.json'
    }
    
    filename = file_map.get(file_type)
    if not filename:
        return jsonify({'success': False, 'error': '不支持的文件类型'}), 400
    
    file_path = output_path / filename
    if not file_path.exists():
        return jsonify({'success': False, 'error': '文件不存在'}), 404
    
    return send_file(str(file_path), as_attachment=True)


# ============ 报告版本对比 ============

@app.route('/api/reports/<int:report_id>/versions', methods=['GET'])
@login_required
def api_report_versions(report_id):
    """获取同一数据包的所有报告版本"""
    report = get_report_by_id(report_id)
    if not report:
        return jsonify({'success': False, 'error': '报告不存在'}), 404

    versions = get_report_versions(
        g.current_user['id'],
        report.get('data_package_path', '')
    )
    return jsonify({'success': True, 'versions': versions})


@app.route('/api/reports/<int:report_id>/diff', methods=['GET'])
@login_required
def api_report_diff(report_id):
    """对比两个版本的报告内容差异
    
    Query params:
        compare_with: 要对比的另一个报告 ID
    """
    compare_id = request.args.get('compare_with', type=int)
    if not compare_id:
        return jsonify({'success': False, 'error': '请提供 compare_with 参数'}), 400

    snapshot_a = get_report_snapshot(report_id)
    snapshot_b = get_report_snapshot(compare_id)

    if snapshot_a is None:
        return jsonify({'success': False, 'error': f'报告 {report_id} 不存在或无快照'}), 404
    if snapshot_b is None:
        return jsonify({'success': False, 'error': f'报告 {compare_id} 不存在或无快照'}), 404

    # 逐行 diff
    import difflib
    lines_a = (snapshot_a or '').splitlines(keepends=True)
    lines_b = (snapshot_b or '').splitlines(keepends=True)

    diff_lines = list(difflib.unified_diff(
        lines_a, lines_b,
        fromfile=f'report_{report_id}',
        tofile=f'report_{compare_id}',
        lineterm=''
    ))

    # 构建结构化 diff
    changes = []
    for line in diff_lines:
        if line.startswith('+++') or line.startswith('---') or line.startswith('@@'):
            changes.append({'type': 'header', 'content': line})
        elif line.startswith('+'):
            changes.append({'type': 'added', 'content': line[1:]})
        elif line.startswith('-'):
            changes.append({'type': 'removed', 'content': line[1:]})
        else:
            changes.append({'type': 'context', 'content': line})

    return jsonify({
        'success': True,
        'report_id': report_id,
        'compare_with': compare_id,
        'diff': changes,
        'stats': {
            'added': sum(1 for c in changes if c['type'] == 'added'),
            'removed': sum(1 for c in changes if c['type'] == 'removed'),
            'total_changes': sum(1 for c in changes if c['type'] in ('added', 'removed')),
        }
    })


# ============ 知识库管理（保留原有功能） ============

@app.route('/api/kb/cards', methods=['GET'])
def list_kb_cards():
    """列出所有知识卡片，支持搜索和标签筛选
    
    Query params:
        q       - 关键词搜索（匹配标题和内容）
        tag     - 按标签筛选（精确匹配，可多次传递）
        module  - 按报告模块筛选
    """
    global current_kb_cards
    
    current_kb_cards = []
    if KB_FOLDER.exists():
        for folder in KB_FOLDER.iterdir():
            if folder.is_dir():
                cards = load_knowledge_cards(folder)
                current_kb_cards.extend(cards)
    
    # 查询参数
    query = (request.args.get('q') or '').strip().lower()
    filter_tags = request.args.getlist('tag') or request.args.getlist('tag[]')
    filter_module = request.args.get('module', '').strip()
    
    # 收集所有标签（用于前端筛选器）
    all_tags = set()
    all_modules = set()
    
    cards_summary = []
    for card in current_kb_cards:
        content = card.content if hasattr(card, 'content') else ''
        tags = card.tags if hasattr(card, 'tags') else []
        modules = card.report_modules if hasattr(card, 'report_modules') else []
        sources = card.sources if hasattr(card, 'sources') else []
        title = card.title if hasattr(card, 'title') else ''
        
        all_tags.update(tags)
        all_modules.update(modules)
        
        # 关键词过滤
        if query and query not in title.lower() and query not in content.lower():
            continue
        # 标签过滤
        if filter_tags and not any(t in tags for t in filter_tags):
            continue
        # 模块过滤
        if filter_module and filter_module not in modules:
            continue
        
        cards_summary.append({
            'id': card.id if hasattr(card, 'id') else '',
            'title': title,
            'tags': tags,
            'report_modules': modules,
            'source_file': card.file_path if hasattr(card, 'file_path') else '',
            'sources': sources,
            'content_preview': content[:200] + '...' if len(content) > 200 else content
        })
    
    return jsonify({
        'success': True,
        'count': len(cards_summary),
        'cards': cards_summary,
        'all_tags': sorted(all_tags),
        'all_modules': sorted(all_modules)
    })


@app.route('/api/kb/cards/<card_id>', methods=['GET'])
def get_kb_card(card_id):
    """获取单个知识卡片详情"""
    for card in current_kb_cards:
        if card.id == card_id:
            return jsonify({
                'success': True,
                'card': {
                    'id': card.id,
                    'title': card.title,
                    'content': card.content,
                    'tags': card.tags,
                    'report_modules': card.report_modules if hasattr(card, 'report_modules') else [],
                    'sources': card.sources if hasattr(card, 'sources') else [],
                    'source_file': card.file_path if hasattr(card, 'file_path') else ''
                }
            })
    
    return jsonify({'success': False, 'error': '卡片不存在'}), 404


@app.route('/api/kb/cards', methods=['POST'])
@admin_required
def create_kb_card():
    """创建新的知识卡片"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请提供卡片数据'}), 400
    
    required_fields = ['title', 'content']
    for field in required_fields:
        if field not in data:
            return jsonify({'success': False, 'error': f'缺少必填字段: {field}'}), 400
    
    card_id = data.get('id') or f"custom-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    import yaml
    front_matter = {
        'id': card_id,
        'title': data['title'],
        'tags': data.get('tags', []),
        'report_modules': data.get('report_modules', []),
        'sources': data.get('sources', [])
    }
    
    md_content = f"---\n{yaml.dump(front_matter, allow_unicode=True, default_flow_style=False)}---\n\n{data['content']}"
    
    custom_kb_folder = KB_FOLDER / 'custom_cards'
    custom_kb_folder.mkdir(exist_ok=True)
    
    file_path = custom_kb_folder / f"{card_id}.md"
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    global vector_index
    vector_index = None
    
    return jsonify({
        'success': True,
        'message': '卡片创建成功',
        'card_id': card_id,
        'file_path': str(file_path)
    })


@app.route('/api/kb/cards/<card_id>', methods=['PUT'])
@admin_required
def update_kb_card(card_id):
    """更新知识卡片"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请提供更新数据'}), 400
    
    card = None
    for c in current_kb_cards:
        if c.id == card_id:
            card = c
            break
    
    if not card:
        return jsonify({'success': False, 'error': '卡片不存在'}), 404
    
    source_file = card.file_path if hasattr(card, 'file_path') else None
    if not source_file or not Path(source_file).exists():
        return jsonify({'success': False, 'error': '源文件不存在'}), 404
    
    import yaml
    front_matter = {
        'id': card_id,
        'title': data.get('title', card.title),
        'tags': data.get('tags', card.tags),
        'report_modules': data.get('report_modules', card.report_modules if hasattr(card, 'report_modules') else []),
        'sources': data.get('sources', card.sources if hasattr(card, 'sources') else [])
    }
    
    content = data.get('content', card.content)
    md_content = f"---\n{yaml.dump(front_matter, allow_unicode=True, default_flow_style=False)}---\n\n{content}"
    
    with open(source_file, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    global vector_index
    vector_index = None
    
    return jsonify({
        'success': True,
        'message': '卡片更新成功'
    })


@app.route('/api/kb/cards/<card_id>', methods=['DELETE'])
@admin_required
def delete_kb_card(card_id):
    """删除知识卡片"""
    global vector_index, current_kb_cards
    
    card = None
    for c in current_kb_cards:
        if c.id == card_id:
            card = c
            break
    
    if not card:
        return jsonify({'success': False, 'error': '卡片不存在'}), 404
    
    source_file = card.file_path if hasattr(card, 'file_path') else None
    if source_file and Path(source_file).exists():
        Path(source_file).unlink()
    
    current_kb_cards = [c for c in current_kb_cards if c.id != card_id]
    vector_index = None
    
    return jsonify({
        'success': True,
        'message': '卡片删除成功'
    })


# ============ 多租户知识库 API ============

ALLOWED_KB_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt', '.md'}


def _safe_filename(filename: str) -> str:
    """安全文件名：保留中文字符，去除路径分隔符和危险字符"""
    import re
    # 去除路径部分，只保留文件名
    name = Path(filename).name
    # 去掉危险字符，但保留中文、字母、数字、下划线、连字符、点
    name = re.sub(r'[^\w\u4e00-\u9fff.\-]', '_', name)
    # 防止空文件名
    if not name or name.startswith('.'):
        name = f"upload_{datetime.now().strftime('%Y%m%d%H%M%S')}{Path(filename).suffix}"
    return name


def _save_kb_upload(file_obj, filename: str) -> str:
    """保存上传文件到 kb_uploads 目录，返回绝对路径"""
    safe_name = _safe_filename(filename)
    dest = KB_UPLOAD_FOLDER / safe_name
    # 若文件名冲突则加时间戳
    if dest.exists():
        stem = Path(safe_name).stem
        suffix = Path(safe_name).suffix
        safe_name = f"{stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}{suffix}"
        dest = KB_UPLOAD_FOLDER / safe_name
    file_obj.save(str(dest))
    return str(dest)


def _copy_kb_file_to_uploads(source_path: str, filename: str) -> str:
    """复制已有知识库文件到 kb_uploads 目录，返回副本路径"""
    safe_name = _safe_filename(filename)
    dest = KB_UPLOAD_FOLDER / safe_name
    if dest.exists():
        stem = Path(safe_name).stem
        suffix = Path(safe_name).suffix
        safe_name = f"{stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}{suffix}"
        dest = KB_UPLOAD_FOLDER / safe_name
    shutil.copy2(source_path, dest)
    return str(dest)


def _normalize_kb_meta_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass
        return [item.strip() for item in raw.replace('，', ',').replace('\r', '').replace('\n', ',').split(',') if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _parse_kb_upload_metadata(req):
    tags = _normalize_kb_meta_list(req.form.get('tags'))
    report_modules = _normalize_kb_meta_list(req.form.get('report_modules'))
    sources = _normalize_kb_meta_list(req.form.get('sources'))
    if not tags:
        raise ValueError('请至少填写一个标签')
    if not report_modules:
        raise ValueError('请至少选择一个报告模块')
    if not sources:
        raise ValueError('请至少填写一个来源')
    return tags, report_modules, sources


@app.route('/api/kb/upload', methods=['POST'])
@login_required
def api_kb_upload_personal():
    """上传文件到个人知识库"""
    me = g.current_user
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '未提供文件'}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({'success': False, 'error': '文件名为空'}), 400
    ext = Path(f.filename).suffix.lower()
    if ext not in ALLOWED_KB_EXTENSIONS:
        return jsonify({'success': False, 'error': f'不支持的文件类型 {ext}，支持: {", ".join(ALLOWED_KB_EXTENSIONS)}'}), 400
    try:
        tags, report_modules, sources = _parse_kb_upload_metadata(request)
        file_path = _save_kb_upload(f, f.filename)
        doc_id = get_kb_manager().upload_personal(
            me['id'], file_path,
            tags=tags,
            report_modules=report_modules,
            sources=sources,
        )
        return jsonify({'success': True, 'message': '上传成功', 'doc_id': doc_id})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify(_err(e, msg='上传失败')), 500


@app.route('/api/kb/orgs/<int:org_id>/upload', methods=['POST'])
@login_required
def api_kb_upload_org(org_id):
    """上传文件到组织知识库（组织成员可上传）"""
    me = g.current_user
    if not is_org_member(org_id, me['id']):
        return jsonify({'success': False, 'error': '您不是该组织成员'}), 403
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '未提供文件'}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({'success': False, 'error': '文件名为空'}), 400
    ext = Path(f.filename).suffix.lower()
    if ext not in ALLOWED_KB_EXTENSIONS:
        return jsonify({'success': False, 'error': f'不支持的文件类型 {ext}'}), 400
    try:
        tags, report_modules, sources = _parse_kb_upload_metadata(request)
        file_path = _save_kb_upload(f, f.filename)
        doc_id = get_kb_manager().upload_to_org(
            org_id, me['id'], file_path,
            tags=tags,
            report_modules=report_modules,
            sources=sources,
        )
        return jsonify({'success': True, 'message': '上传成功', 'doc_id': doc_id})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify(_err(e, msg='上传失败')), 500


@app.route('/api/kb/orgs/<int:org_id>/import-personal', methods=['POST'])
@login_required
def api_kb_import_personal_to_org(org_id):
    """将个人知识库文档复制导入到组织知识库"""
    me = g.current_user
    if not is_org_member(org_id, me['id']):
        return jsonify({'success': False, 'error': '您不是该组织成员'}), 403
    data = request.get_json() or {}
    doc_id = data.get('doc_id')
    if not doc_id:
        return jsonify({'success': False, 'error': '缺少文档 ID'}), 400
    doc = kb_get_document(doc_id)
    if not doc:
        return jsonify({'success': False, 'error': '文档不存在'}), 404
    if doc.get('scope') != 'personal' or doc.get('user_id') != me['id']:
        return jsonify({'success': False, 'error': '只能导入你自己的个人知识库文档'}), 403
    source_path = doc.get('file_path')
    if not source_path or not Path(source_path).exists():
        return jsonify({'success': False, 'error': '源文件不存在'}), 404
    try:
        copied_path = _copy_kb_file_to_uploads(source_path, doc.get('filename') or Path(source_path).name)
        new_doc_id = get_kb_manager().upload_to_org(
            org_id, me['id'], copied_path,
            tags=doc.get('tags'),
            report_modules=doc.get('report_modules'),
            sources=doc.get('sources'),
        )
        return jsonify({'success': True, 'message': '已导入到组织知识库', 'doc_id': new_doc_id})
    except Exception as e:
        return jsonify(_err(e, msg='导入失败')), 500


@app.route('/api/kb/documents', methods=['GET'])
@login_required
def api_kb_list_personal():
    """列出当前用户的个人知识库文档"""
    me = g.current_user
    docs = get_kb_manager().list_personal(me['id'])
    return jsonify({'success': True, 'documents': docs})


@app.route('/api/kb/orgs/<int:org_id>/documents', methods=['GET'])
@login_required
def api_kb_list_org(org_id):
    """列出组织知识库文档（成员可见）"""
    me = g.current_user
    if not is_org_member(org_id, me['id']):
        return jsonify({'success': False, 'error': '无权限'}), 403
    docs = get_kb_manager().list_org(org_id)
    return jsonify({'success': True, 'documents': docs})


@app.route('/api/kb/documents/<int:doc_id>', methods=['GET'])
@login_required
def api_kb_get_personal_doc(doc_id):
    """获取个人知识库文档详情（含完整内容）"""
    me = g.current_user
    doc = kb_get_document(doc_id)
    if not doc:
        return jsonify({'success': False, 'error': '文档不存在'}), 404
    if doc['scope'] != 'personal' or doc['user_id'] != me['id']:
        return jsonify({'success': False, 'error': '无权限'}), 403
    doc = get_kb_manager().hydrate_document_metadata(doc)
    content = get_kb_manager().get_personal_doc_content(me['id'], doc_id)
    return jsonify({'success': True, 'document': dict(doc), 'content': content})


@app.route('/api/kb/orgs/<int:org_id>/documents/<int:doc_id>', methods=['GET'])
@login_required
def api_kb_get_org_doc(org_id, doc_id):
    """获取组织知识库文档详情（组织成员可见）"""
    me = g.current_user
    if not is_org_member(org_id, me['id']):
        return jsonify({'success': False, 'error': '无权限'}), 403
    doc = kb_get_document(doc_id)
    if not doc or doc.get('org_id') != org_id or doc.get('scope') != 'org':
        return jsonify({'success': False, 'error': '文档不存在'}), 404
    doc = get_kb_manager().hydrate_document_metadata(doc)
    content = get_kb_manager().get_org_doc_content(org_id, doc_id)
    return jsonify({'success': True, 'document': dict(doc), 'content': content})


@app.route('/api/kb/documents/<int:doc_id>', methods=['PUT'])
@login_required
def api_kb_update_personal(doc_id):
    """更新个人知识库文档（属性 + 可选正文，仅文档所有者）"""
    me = g.current_user
    doc = kb_get_document(doc_id)
    if not doc:
        return jsonify({'success': False, 'error': '文档不存在'}), 404
    if doc['scope'] != 'personal' or doc['user_id'] != me['id']:
        return jsonify({'success': False, 'error': '无权限编辑此文档'}), 403
    try:
        payload = request.get_json() or {}
        tags = _normalize_kb_meta_list(payload.get('tags'))
        report_modules = _normalize_kb_meta_list(payload.get('report_modules'))
        sources = _normalize_kb_meta_list(payload.get('sources'))
        if not tags:
            raise ValueError('请至少填写一个标签')
        if not report_modules:
            raise ValueError('请至少选择一个报告模块')
        if not sources:
            raise ValueError('请至少填写一个来源')

        # 可选：正文内容更新（仅 md / markdown / txt）
        new_content = payload.get('content')
        content_updated = False
        new_chunk_count = None
        if isinstance(new_content, str) and new_content.strip():
            new_chunk_count = get_kb_manager().replace_document_content(doc_id, me['id'], new_content)
            content_updated = True

        kb_update_document(doc_id, tags=tags, report_modules=report_modules, sources=sources)
        message = '文档已更新（属性 + 正文）' if content_updated else '属性更新成功'
        resp = {'success': True, 'message': message, 'document': kb_get_document(doc_id)}
        if content_updated:
            resp['chunk_count'] = new_chunk_count
        return jsonify(resp)
    except PermissionError as e:
        return jsonify({'success': False, 'error': str(e)}), 403
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify(_err(e, msg='更新失败')), 500


@app.route('/api/kb/orgs/<int:org_id>/documents/<int:doc_id>', methods=['PUT'])
@login_required
def api_kb_update_org(org_id, doc_id):
    """更新组织知识库文档（属性 + 可选正文，组织成员同权）"""
    me = g.current_user
    doc = kb_get_document(doc_id)
    if not doc or doc.get('org_id') != org_id or doc.get('scope') != 'org':
        return jsonify({'success': False, 'error': '文档不存在'}), 404
    if not is_org_member(org_id, me['id']):
        return jsonify({'success': False, 'error': '无权限编辑此文档'}), 403
    try:
        payload = request.get_json() or {}
        tags = _normalize_kb_meta_list(payload.get('tags'))
        report_modules = _normalize_kb_meta_list(payload.get('report_modules'))
        sources = _normalize_kb_meta_list(payload.get('sources'))
        if not tags:
            raise ValueError('请至少填写一个标签')
        if not report_modules:
            raise ValueError('请至少选择一个报告模块')
        if not sources:
            raise ValueError('请至少填写一个来源')

        # 可选：正文内容更新（仅 md / markdown / txt）
        new_content = payload.get('content')
        content_updated = False
        new_chunk_count = None
        if isinstance(new_content, str) and new_content.strip():
            new_chunk_count = get_kb_manager().replace_document_content(doc_id, me['id'], new_content)
            content_updated = True

        kb_update_document(doc_id, tags=tags, report_modules=report_modules, sources=sources)
        message = '文档已更新（属性 + 正文）' if content_updated else '属性更新成功'
        resp = {'success': True, 'message': message, 'document': kb_get_document(doc_id)}
        if content_updated:
            resp['chunk_count'] = new_chunk_count
        return jsonify(resp)
    except PermissionError as e:
        return jsonify({'success': False, 'error': str(e)}), 403
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify(_err(e, msg='更新失败')), 500


@app.route('/api/kb/documents/<int:doc_id>', methods=['DELETE'])
@login_required
def api_kb_delete_personal(doc_id):
    """删除个人知识库文档（仅文档所有者）"""
    me = g.current_user
    doc = kb_get_document(doc_id)
    if not doc:
        return jsonify({'success': False, 'error': '文档不存在'}), 404
    if doc['scope'] != 'personal' or doc['user_id'] != me['id']:
        return jsonify({'success': False, 'error': '无权限删除此文档'}), 403
    try:
        get_kb_manager().delete_document(doc_id, me['id'])
        return jsonify({'success': True, 'message': '已删除'})
    except Exception as e:
        return jsonify(_err(e, msg='删除失败')), 500


@app.route('/api/kb/orgs/<int:org_id>/documents/<int:doc_id>', methods=['DELETE'])
@login_required
def api_kb_delete_org(org_id, doc_id):
    """删除组织知识库文档（组织成员同权）"""
    me = g.current_user
    doc = kb_get_document(doc_id)
    if not doc or doc['org_id'] != org_id:
        return jsonify({'success': False, 'error': '文档不存在'}), 404
    if not is_org_member(org_id, me['id']):
        return jsonify({'success': False, 'error': '无权限删除此文档'}), 403
    try:
        get_kb_manager().delete_document(doc_id, me['id'])
        return jsonify({'success': True, 'message': '已删除'})
    except Exception as e:
        return jsonify(_err(e, msg='删除失败')), 500


@app.route('/api/kb/changelog', methods=['GET'])
@login_required
def api_kb_personal_log():
    """个人知识库变更日志（仅自己可见）"""
    me = g.current_user
    limit = request.args.get('limit', 100, type=int)
    logs = get_kb_manager().get_personal_log(me['id'], limit)
    return jsonify({'success': True, 'logs': logs})


@app.route('/api/kb/orgs/<int:org_id>/changelog', methods=['GET'])
@login_required
def api_kb_org_log(org_id):
    """组织知识库变更日志（组织成员均可见）"""
    me = g.current_user
    if not is_org_member(org_id, me['id']):
        return jsonify({'success': False, 'error': '无权限'}), 403
    limit = request.args.get('limit', 100, type=int)
    logs = get_kb_manager().get_org_log(org_id, limit)
    return jsonify({'success': True, 'logs': logs})


# ============ 一键生成报告（全自动流式接口） ============

def _sse_event(data: dict) -> str:
    """格式化 SSE 事件"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.route('/api/workflow/auto-generate-stream', methods=['POST'])
def auto_generate_stream():
    """一键生成报告 — 全自动流式接口（不经过 LLM，直接执行工作流）
    
    mode:
      - full_report  : 配置 → 生成全部槽位 → 确认 → 导出（默认）
      - config_only  : 仅完成配置即停止
    """
    data = request.get_json(silent=True) or {}
    mode = data.get('mode', 'full_report')

    def generate():
        try:
            # ── 1. 检查数据包 ──
            if not current_data_package:
                yield _sse_event({"type": "error", "error": "未加载数据包，请先上传数据包"})
                return

            yield _sse_event({"type": "progress", "percent": 2, "message": "正在分析数据包…"})

            # ── 2. 自动配置 (auto_configure) ──
            pkg_data = parse_data_package(Path(current_data_package))
            facts = build_run_facts(pkg_data, '', '')

            # 转换图片路径
            images = facts.get('images', {})
            for category in images:
                images[category] = [
                    f"/api/images/{Path(p).relative_to(Path(current_data_package))}"
                    for p in images[category]
                ]
            automation_ops = facts.get('automation_ops', [])
            for op in automation_ops:
                if 'images' in op and op['images']:
                    op['images'] = [
                        f"/api/images/{Path(img).relative_to(Path(current_data_package))}"
                        if Path(img).is_absolute() else f"/api/images/automation/ops/{op['folder']}/images/{Path(img).name}"
                        for img in op['images']
                    ]

            # 根据数据推断配置
            derived = facts.get('derived_quantities', {})
            mach = derived.get('estimated_mach')
            domain = 'external_aero' if (mach and mach > 0.3) else 'general_cfd'
            phenomena = []
            flow_analysis = facts.get('flow_analysis', {})
            for finding in flow_analysis.get('key_findings', []):
                f_lower = finding.lower()
                if 'shock' in f_lower or '激波' in finding:
                    phenomena.append('shock_wave')
                if 'separation' in f_lower or '分离' in finding:
                    phenomena.append('flow_separation')
                if 'compressible' in f_lower or '可压缩' in finding:
                    phenomena.append('compressible_flow')
                if 'high_speed' in f_lower or '高速' in finding:
                    phenomena.append('high_speed_flow')
            if not phenomena:
                phenomena = ['compressible_flow']

            answers = {
                'domain': domain,
                'phenomena': phenomena,
                'purpose': 'performance_evaluation',
                'inference_level': 'may_infer',
                'enable_web_search': False,
                'enable_system_kb': True,
                'enable_personal_kb': True,
                'enable_org_kb': True
            }

            yield _sse_event({"type": "tool_call", "name": "auto_configure", "args": {"domain": domain, "phenomena": phenomena}})

            policy = PolicyBuilder.build_from_answers(answers)
            draft = draft_manager.create_draft(facts, policy=policy)
            draft_manager.set_clarification_answers(answers)
            slot_count = len(draft.slots)

            yield _sse_event({"type": "tool_result", "name": "auto_configure", "content": {"slot_count": slot_count, "domain": domain}})
            yield _sse_event({"type": "progress", "percent": 15, "message": f"报告配置完成，共 {slot_count} 个槽位"})

            if mode == 'config_only':
                yield _sse_event({
                    "type": "done",
                    "mode": "config_only",
                    "message": f"已完成报告配置（{slot_count} 个槽位），按要求已停止。",
                    "slot_count": slot_count,
                    "domain": domain
                })
                return

            # ── 3. 逐个生成槽位 ──
            total_slots = slot_count
            generated_count = 0

            filler = _make_slot_filler(False)

            while True:
                pending_slots = draft.get_pending_slots()
                if not pending_slots:
                    break

                target_slot = pending_slots[0]
                
                yield _sse_event({"type": "tool_call", "name": "generate_next_slot", "args": {"slot_id": target_slot.slot_id}})

                result = filler.fill_slot(target_slot, draft.facts, draft.policy)
                
                draft_manager.update_slot_content(
                    result['slot_id'],
                    result['content'],
                    claims=result.get('claims', []),
                    evidence_pack=result.get('evidence_pack', {}),
                    status=SlotStatus.DRAFT
                )

                generated_count += 1
                pct = 15 + int((generated_count / total_slots) * 55)
                yield _sse_event({
                    "type": "tool_result",
                    "name": "generate_next_slot",
                    "content": {"slot_id": result['slot_id'], "generated": generated_count, "total": total_slots}
                })
                yield _sse_event({
                    "type": "progress",
                    "percent": pct,
                    "message": f"生成中：{generated_count}/{total_slots}"
                })

            # ── 4. 确认全部槽位 ──
            yield _sse_event({"type": "tool_call", "name": "accept_all_slots", "args": {}})
            accepted_count = 0
            for slot in draft.slots:
                if slot.status == SlotStatus.DRAFT:
                    draft_manager.accept_slot(slot.slot_id)
                    accepted_count += 1
            yield _sse_event({"type": "tool_result", "name": "accept_all_slots", "content": {"accepted": accepted_count}})
            yield _sse_event({"type": "progress", "percent": 80, "message": f"已确认 {accepted_count} 个槽位"})

            # ── 5. 导出报告 ──
            yield _sse_event({"type": "tool_call", "name": "export_report", "args": {}})
            export_result_str = _execute_mcp_tool("export_report", {})
            try:
                export_result = json.loads(export_result_str)
            except Exception:
                export_result = {}

            if export_result.get("error"):
                yield _sse_event({"type": "error", "error": f"导出失败: {export_result['error']}"})
                return

            yield _sse_event({"type": "tool_result", "name": "export_report", "content": export_result})
            yield _sse_event({"type": "progress", "percent": 100, "message": "报告导出完成"})
            yield _sse_event({
                "type": "done",
                "mode": "full_report",
                "message": "报告已自动生成并导出完成！",
                "output_dir": export_result.get("output_dir", ""),
                "files": export_result.get("files", []),
                "slot_count": total_slots
            })

        except Exception as exc:
            import traceback as _tb
            event = {"type": "error", "error": str(exc)}
            if _DEBUG_MODE:
                event["traceback"] = _tb.format_exc()
            yield _sse_event(event)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


def _get_slot_display_name(slot_id: str) -> str:
    """获取槽位的显示名称"""
    name_map = {
        'executive_summary': '执行摘要',
        'background': '研究背景',
        'problem_statement': '问题界定',
        'objectives': '研究目标',
        'methodology': '研究方法',
        'findings_main': '核心发现',
        'findings_analysis': '深入分析',
        'discussion': '讨论',
        'conclusion': '结论',
        'recommendations': '建议',
        'references': '参考资料',
        'analysis_purpose_1': '分析目的 1',
        'analysis_purpose_2': '分析目的 2',
        'geometry_description': '几何描述',
        'mesh_description': '网格描述',
    }
    if slot_id in name_map:
        return name_map[slot_id]
    # 处理动态槽位名
    if slot_id.startswith('section_'):
        return f"章节 {slot_id.replace('section_', '')}"
    return slot_id.replace('_', ' ').title()


# ============ MCP AI 对话接口 ============

# MCP 工具定义
MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_run_info",
            "description": "查询当前已加载数据包的元信息，包括数据类型、网格块数、节点数、变量列表等",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_signals",
            "description": "列出数据包中所有可用的流场变量（信号/通道），包括变量名、推断语义和数值范围",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "可选的过滤关键词，如 'Momentum' 或 'density'"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compute_metrics",
            "description": "计算指定变量的统计指标，包括最大值、最小值、均值、变化范围等",
            "parameters": {
                "type": "object",
                "properties": {
                    "signals": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要计算指标的变量名列表，如 ['F1V1', 'F1V2']"
                    }
                },
                "required": ["signals"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_mesh_info",
            "description": "获取网格结构的详细信息，包括各块的维度、节点数、纵横比分析等",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_derived_quantities",
            "description": "获取从守恒量推算的派生物理量，包括速度估算、马赫数估算、流动状态判断、密度比等",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rag_query",
            "description": "从专业知识库中检索与CFD仿真相关的技术资料，用于解释物理现象或提供背景知识",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索查询词，如 'Plot3D格式说明' 或 '多块结构网格'"},
                    "top_k": {"type": "integer", "description": "返回结果数量，默认3", "default": 3}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "联网搜索：从互联网搜索与问题相关的信息，适合补充专业背景知识、查找最新技术资料。仅在用户开启联网搜索时可用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词，如 'CFD网格独立性验证方法' 或 'Plot3D数据格式标准'"},
                    "max_results": {"type": "integer", "description": "返回结果数量，默认5", "default": 5}
                },
                "required": ["query"]
            }
        }
    },
    # ===== 自动化工作流工具 =====
    {
        "type": "function",
        "function": {
            "name": "auto_configure",
            "description": "自动提交报告配置（Clarification答案），创建Draft。需要提供领域(domain)、关注现象(phenomena)等配置。调用此工具后前端会自动跳转到生成页面。",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "仿真领域，可选: external_aero/turbomachinery/internal_flow/heat_transfer/structural/general_cfd", "default": "general_cfd"},
                    "phenomena": {"type": "array", "items": {"type": "string"}, "description": "关注的物理现象列表，如 ['flow_separation', 'shock_wave', 'vortex']"},
                    "purpose": {"type": "string", "description": "报告目的，可选: design_validation/performance_evaluation/troubleshooting/academic_research", "default": "design_validation"},
                    "inference_level": {"type": "string", "description": "推断强度: describe_only/may_infer", "default": "may_infer"},
                    "enable_web_search": {"type": "boolean", "description": "是否启用网络搜索", "default": False},
                    "engine_model_name": {"type": "string", "description": "模型名称（可选）", "default": ""},
                    "project_code": {"type": "string", "description": "项目代码（可选）", "default": ""}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_next_slot",
            "description": "生成下一个待处理的报告槽位内容。每次只生成一个槽位，前端会滚动到该槽位并展示动画。需要反复调用直到所有槽位生成完毕。",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_all_slots",
            "description": "一次性生成所有待处理的报告槽位内容。调用后前端文档预览会实时更新。",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "accept_all_slots",
            "description": "确认（接受）所有已生成的草稿槽位。调用后所有draft状态的槽位变为accepted。",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "export_report",
            "description": "导出报告为Markdown和Word文档。需要所有槽位都已确认后才能导出。",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    }
]


def _get_current_facts():
    """获取当前数据包的 facts（公共方法，避免重复解析）"""
    if not current_data_package:
        return None, "未加载数据包"
    try:
        pkg_data = parse_data_package(Path(current_data_package))
        facts = build_run_facts(pkg_data, 'AI查询', 'MCP-001')
        return facts, None
    except Exception as e:
        return None, str(e)


_TOOL_CATEGORIES = {
    'get_run_info': 'data', 'list_signals': 'data', 'compute_metrics': 'data',
    'get_mesh_info': 'data', 'get_derived_quantities': 'data',
    'rag_query': 'knowledge', 'web_search': 'knowledge',
    'auto_configure': 'workflow', 'generate_next_slot': 'workflow',
    'generate_all_slots': 'workflow', 'accept_all_slots': 'workflow', 'export_report': 'workflow',
}

# ── 将 MCP_TOOLS schema 注册到插件式 Registry ──
for _tool_def in MCP_TOOLS:
    _fn = _tool_def["function"]
    _name = _fn["name"]
    mcp_registry.register(
        name=_name,
        handler=None,
        description=_fn.get("description", ""),
        schema=_fn.get("parameters", {}),
        category=_TOOL_CATEGORIES.get(_name, "other"),
    )


def _execute_mcp_tool(tool_name: str, tool_args: dict) -> str:
    """执行MCP工具调用（带可观测性记录 + Registry分发）"""
    category = _TOOL_CATEGORIES.get(tool_name, 'other')
    return tool_observer.observe_call(
        tool_name, tool_args,
        lambda: _execute_mcp_tool_impl(tool_name, tool_args),
        category=category
    )


def _execute_mcp_tool_impl(tool_name: str, tool_args: dict) -> str:
    """MCP工具实际执行逻辑（Registry 优先，兜底 if/elif）"""
    global current_data_package, vector_index

    # 优先通过 Registry 分发（handler 非 None 的已注册工具）
    tool_info = mcp_registry.get_tool_info(tool_name)
    if tool_info and tool_info.get("handler") is not None:
        return mcp_registry.call(tool_name, tool_args)

    if tool_name == "get_run_info":
        facts, err = _get_current_facts()
        if err:
            return json.dumps({"error": err}, ensure_ascii=False)
        try:
            manifest = facts.get('manifest', {})
            datasets = facts.get('datasets', {})
            variables = facts.get('variables', [])
            return json.dumps({
                "dataset_type": manifest.get('dataset_type', 'Unknown'),
                "app_name": manifest.get('app_name', 'Unknown'),
                "block_count": manifest.get('block_count', datasets.get('block_count', 0)),
                "total_points": datasets.get('total_points', 0),
                "total_cells": datasets.get('total_cells', 0),
                "variable_count": len(variables),
                "variables": [{"name": v.get('name'), "semantic": v.get('guess_variableName')} for v in variables],
                "path": current_data_package
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    elif tool_name == "list_signals":
        facts, err = _get_current_facts()
        if err:
            return json.dumps({"error": err}, ensure_ascii=False)
        try:
            variables = facts.get('variables', [])
            pattern = tool_args.get('pattern', '').lower()
            result = []
            for v in variables:
                name = v.get('name', '')
                semantic = v.get('guess_variableName', '')
                if not pattern or pattern in name.lower() or pattern in semantic.lower():
                    result.append({
                        "name": name,
                        "semantic": semantic,
                        "components": v.get('num_components', 1),
                        "range_min": v.get('range_min'),
                        "range_max": v.get('range_max')
                    })
            return json.dumps({"signals": result, "total": len(result)}, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    elif tool_name == "compute_metrics":
        facts, err = _get_current_facts()
        if err:
            return json.dumps({"error": err}, ensure_ascii=False)
        try:
            variables = facts.get('variables', [])
            signals = tool_args.get('signals', [])
            metrics = {}
            for v in variables:
                if v.get('name') in signals or not signals:
                    vmin = v.get('range_min', 0)
                    vmax = v.get('range_max', 0)
                    span = vmax - vmin
                    metrics[v.get('name')] = {
                        "semantic": v.get('guess_variableName'),
                        "min": vmin,
                        "max": vmax,
                        "span": span,
                        "has_negative": vmin < 0,
                        "has_reverse_flow": vmin < 0 and vmax > 0
                    }
            return json.dumps({"metrics": metrics}, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    elif tool_name == "get_mesh_info":
        facts, err = _get_current_facts()
        if err:
            return json.dumps({"error": err}, ensure_ascii=False)
        try:
            mesh_analysis = facts.get('mesh_analysis', {})
            datasets = facts.get('datasets', {})
            blocks = datasets.get('blocks', [])
            return json.dumps({
                "block_count": len(blocks),
                "blocks": [{"name": b.get('name'), "dims": b.get('dims'), "points": b.get('points'), "cells": b.get('cells')} for b in blocks],
                "size_distribution": mesh_analysis.get('size_distribution'),
                "largest_block": mesh_analysis.get('largest_block'),
                "smallest_block": mesh_analysis.get('smallest_block'),
                "resolution_notes": mesh_analysis.get('resolution_notes', []),
                "aspect_ratio_concerns": mesh_analysis.get('aspect_ratio_concerns', [])
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    elif tool_name == "get_derived_quantities":
        facts, err = _get_current_facts()
        if err:
            return json.dumps({"error": err}, ensure_ascii=False)
        try:
            derived = facts.get('derived_quantities', {})
            flow_analysis = facts.get('flow_analysis', {})
            return json.dumps({
                "derived_quantities": derived,
                "flow_analysis": {
                    "key_findings": flow_analysis.get('key_findings', []),
                    "attention_points": flow_analysis.get('attention_points', []),
                    "limitations": flow_analysis.get('limitations', [])
                }
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    elif tool_name == "rag_query":
        query = tool_args.get('query', '')
        top_k = tool_args.get('top_k', 3)
        min_score = 0.25
        try:
            chunks = []
            # Prefer KBManager (same path as SlotFiller) for consistency
            user_ctx = _build_user_context()
            if user_ctx:
                try:
                    kb_mgr = get_kb_manager()
                    kb_results = kb_mgr.retrieve(
                        query=query,
                        user_id=user_ctx.get("user_id", 0),
                        org_ids=user_ctx.get("org_ids", []),
                        role=user_ctx.get("role", "user"),
                        top_k=top_k,
                        enable_system=getattr(draft_manager.current_draft.policy, 'enable_system_kb', True) if draft_manager.current_draft else True,
                        enable_personal=getattr(draft_manager.current_draft.policy, 'enable_personal_kb', True) if draft_manager.current_draft else True,
                        enable_org=getattr(draft_manager.current_draft.policy, 'enable_org_kb', True) if draft_manager.current_draft else True,
                    )
                    for r in kb_results:
                        score = r.get("score", 0)
                        if score >= min_score:
                            chunks.append({
                                "content": r.get("content", "")[:500],
                                "source": r.get("metadata", {}).get("filename", r.get("collection", "")),
                                "score": round(score, 3)
                            })
                except Exception:
                    pass
            
            # Fallback to global vector_index
            if not chunks and vector_index:
                results = vector_index.search(query, top_k=top_k)
                for r in results:
                    score = r.get('score', 0)
                    if score >= min_score:
                        chunks.append({
                            "content": r.get('content', '')[:500],
                            "source": r.get('source', ''),
                            "score": round(score, 3)
                        })
            
            if not chunks:
                return json.dumps({"query": query, "chunks": [], "total": 0, "note": "未检索到相关知识"}, ensure_ascii=False, indent=2)
            return json.dumps({"query": query, "chunks": chunks, "total": len(chunks)}, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    elif tool_name == "web_search":
        query = tool_args.get('query', '')
        max_results = tool_args.get('max_results', 5)
        if not query:
            return json.dumps({"error": "请提供搜索关键词"}, ensure_ascii=False)
        try:
            searcher = get_web_searcher(use_mock=False)
            raw_results = searcher.search(query, max_results=max_results)
            results = [
                {"url": r.url, "title": r.title, "snippet": r.snippet, "domain": r.domain, "relevance": r.relevance_score}
                for r in raw_results
            ]
            return json.dumps({
                "query": query,
                "results": results[:max_results],
                "total": len(results)
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": f"联网搜索失败: {str(e)}", "query": query}, ensure_ascii=False)

    # ===== 自动化工作流工具 =====
    elif tool_name == "auto_configure":
        if not current_data_package:
            return json.dumps({"error": "未加载数据包，请先上传数据包"}, ensure_ascii=False)
        try:
            # 构建答案
            domain = tool_args.get('domain', 'general_cfd')
            phenomena = tool_args.get('phenomena', [])
            purpose = tool_args.get('purpose', 'design_validation')
            inference_level = tool_args.get('inference_level', 'may_infer')
            enable_web_search = tool_args.get('enable_web_search', False)
            
            answers = {
                'domain': domain,
                'phenomena': phenomena,
                'purpose': purpose,
                'inference_level': inference_level,
                'enable_web_search': enable_web_search,
                'enable_system_kb': tool_args.get('enable_system_kb', True),
                'enable_personal_kb': tool_args.get('enable_personal_kb', True),
                'enable_org_kb': tool_args.get('enable_org_kb', True)
            }
            
            # 同时构建与 Clarification 问题 ID 对应的答案映射（供前端动画使用）
            question_answers = {
                'Q1_domain': domain,
                'Q2_purpose': purpose,
                'Q3_phenomena': phenomena,
                'Q4_inference': inference_level,
                'Q5_knowledge_source': 'web_and_rag' if enable_web_search else 'rag_only',
                'Q6_terminology': 'chinese',
            }
            
            # 解析数据包
            pkg_data = parse_data_package(Path(current_data_package))
            facts = build_run_facts(pkg_data,
                                    tool_args.get('engine_model_name', ''),
                                    tool_args.get('project_code', ''))
            
            # 转换图片路径
            images = facts.get('images', {})
            for category in images:
                images[category] = [
                    f"/api/images/{Path(p).relative_to(Path(current_data_package))}"
                    for p in images[category]
                ]
            
            automation_ops = facts.get('automation_ops', [])
            for op in automation_ops:
                if 'images' in op and op['images']:
                    op['images'] = [
                        f"/api/images/{Path(img).relative_to(Path(current_data_package))}"
                        if Path(img).is_absolute() else f"/api/images/automation/ops/{op['folder']}/images/{Path(img).name}"
                        for img in op['images']
                    ]
            
            # 构建策略并创建Draft
            policy = PolicyBuilder.build_from_answers(answers)
            draft = draft_manager.create_draft(facts, policy=policy)
            draft_manager.set_clarification_answers(answers)
            
            slot_count = len(draft.slots)
            progress = draft_manager.get_progress()
            
            return json.dumps({
                "success": True,
                "action": "auto_configure",
                "message": f"报告配置完成！已创建{slot_count}个槽位，领域：{domain}，可以开始生成报告。",
                "slot_count": slot_count,
                "progress": progress,
                "domain": domain,
                "phenomena": phenomena,
                "answers": question_answers
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            import traceback as _tb
            result = {"error": str(e)}
            if _DEBUG_MODE:
                result["traceback"] = _tb.format_exc()
            return json.dumps(result, ensure_ascii=False)

    elif tool_name == "generate_next_slot":
        if draft_manager.current_draft is None:
            return json.dumps({"error": "未创建Draft，请先调用auto_configure配置报告"}, ensure_ascii=False)
        try:
            draft = draft_manager.current_draft
            pending_slots = draft.get_pending_slots()
            
            if not pending_slots:
                progress = draft_manager.get_progress()
                return json.dumps({
                    "success": True,
                    "action": "generate_next_slot",
                    "message": "所有槽位已生成完毕！",
                    "all_done": True,
                    "slot_id": None,
                    "progress": progress
                }, ensure_ascii=False, indent=2)
            
            # 取第一个待生成的槽位
            target_slot = pending_slots[0]
            
            filler = _make_slot_filler(False)
            
            result = filler.fill_slot(target_slot, draft.facts, draft.policy)
            
            draft_manager.update_slot_content(
                result['slot_id'],
                result['content'],
                claims=result.get('claims', []),
                evidence_pack=result.get('evidence_pack', {}),
                status=SlotStatus.DRAFT
            )
            
            progress = draft_manager.get_progress()
            remaining = progress.get('pending', 0)
            
            # 获取槽位的可读名称
            slot_name_map = {
                'analysis_purpose_1': '分析目的(1)',
                'analysis_purpose_2': '分析目的(2)',
                'geometry_description': '几何结构描述',
                'mesh_description': '网格结构描述',
                'evaluation_criteria_1': '评定准则(1)',
                'evaluation_criteria_2': '评定准则(2)',
                'conclusion': '结论与总结',
            }
            slot_id = result['slot_id']
            display_name = slot_name_map.get(slot_id, slot_id)
            if slot_id.startswith('variable_'):
                display_name = f"变量分析 - {slot_id.replace('variable_', '')}"
            
            return json.dumps({
                "success": True,
                "action": "generate_next_slot",
                "message": f"已生成「{display_name}」槽位内容。",
                "slot_id": slot_id,
                "slot_name": display_name,
                "all_done": remaining == 0,
                "remaining": remaining,
                "progress": progress
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            import traceback as _tb
            result = {"error": str(e)}
            if _DEBUG_MODE:
                result["traceback"] = _tb.format_exc()
            return json.dumps(result, ensure_ascii=False)

    elif tool_name == "generate_all_slots":
        if draft_manager.current_draft is None:
            return json.dumps({"error": "未创建Draft，请先调用auto_configure配置报告"}, ensure_ascii=False)
        try:
            draft = draft_manager.current_draft
            pending_count = len(draft.get_pending_slots())
            
            if pending_count == 0:
                return json.dumps({
                    "success": True,
                    "action": "generate_all_slots",
                    "message": "所有槽位已生成，无需重复生成。",
                    "generated": 0,
                    "progress": draft_manager.get_progress()
                }, ensure_ascii=False, indent=2)
            
            filler = _make_slot_filler(False)
            batch_filler = BatchSlotFiller(filler)
            
            results = batch_filler.fill_all_slots(draft.slots, draft.facts, draft.policy)
            
            for result in results:
                draft_manager.update_slot_content(
                    result['slot_id'],
                    result['content'],
                    claims=result.get('claims', []),
                    evidence_pack=result.get('evidence_pack', {}),
                    status=SlotStatus.DRAFT
                )
            
            progress = draft_manager.get_progress()
            return json.dumps({
                "success": True,
                "action": "generate_all_slots",
                "message": f"已成功生成{len(results)}个槽位内容！所有内容为draft状态，等待确认。",
                "generated": len(results),
                "progress": progress
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            import traceback as _tb
            result = {"error": str(e)}
            if _DEBUG_MODE:
                result["traceback"] = _tb.format_exc()
            return json.dumps(result, ensure_ascii=False)

    elif tool_name == "accept_all_slots":
        if draft_manager.current_draft is None:
            return json.dumps({"error": "未创建Draft"}, ensure_ascii=False)
        try:
            draft = draft_manager.current_draft
            accepted_count = 0
            for slot in draft.slots:
                if slot.status == SlotStatus.DRAFT:
                    draft_manager.accept_slot(slot.slot_id)
                    accepted_count += 1
            
            progress = draft_manager.get_progress()
            return json.dumps({
                "success": True,
                "action": "accept_all_slots",
                "message": f"已确认{accepted_count}个槽位。",
                "accepted_count": accepted_count,
                "progress": progress
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    elif tool_name == "export_report":
        print("[MCP] export_report 工具被调用")
        if draft_manager.current_draft is None:
            return json.dumps({"error": "未创建Draft"}, ensure_ascii=False)
        try:
            from reportgen.pipeline.build_md import generate_report_content
            
            draft = draft_manager.current_draft
            progress = draft_manager.get_progress()
            print(f"[MCP] export_report: pending={progress.get('pending',0)}, draft={progress.get('draft',0)}, accepted={progress.get('accepted',0)}")
            
            if progress.get('pending', 0) > 0:
                return json.dumps({"error": f"还有{progress['pending']}个槽位未生成，请先生成所有槽位"}, ensure_ascii=False)
            
            # 如果还有 draft 状态的槽位，自动确认
            draft_count = progress.get('draft', 0)
            if draft_count > 0:
                print(f"[MCP] export_report: 自动确认 {draft_count} 个 draft 槽位")
                for slot in draft.slots:
                    if slot.status == SlotStatus.DRAFT:
                        draft_manager.accept_slot(slot.slot_id)
            
            # 复用 export_report 端点的逻辑
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = OUTPUT_FOLDER / timestamp
            output_dir.mkdir(parents=True, exist_ok=True)
            
            filled_slots = {}
            for slot in draft.slots:
                filled_slots[slot.slot_id] = slot.content or slot.placeholder_text
            
            # 复制资源文件
            assets_dir = output_dir / "assets"
            assets_dir.mkdir(exist_ok=True)
            image_mapping = {}
            
            if current_data_package:
                import shutil
                src_images_dir = Path(current_data_package) / "images"
                if src_images_dir.exists():
                    for category_dir in src_images_dir.iterdir():
                        if category_dir.is_dir():
                            dest_cat = assets_dir / category_dir.name
                            dest_cat.mkdir(exist_ok=True)
                            for img_file in category_dir.glob("*.png"):
                                shutil.copy2(str(img_file), str(dest_cat / img_file.name))
                                assets_path = f"assets/{category_dir.name}/{img_file.name}"
                                # 注册多种可能的原始路径格式
                                image_mapping[f"/api/images/images/{category_dir.name}/{img_file.name}"] = assets_path
                                image_mapping[f"images/{category_dir.name}/{img_file.name}"] = assets_path
                                image_mapping[f"/api/images/images\\{category_dir.name}\\{img_file.name}"] = assets_path
                
                src_auto_dir = Path(current_data_package) / "automation" / "ops"
                if src_auto_dir.exists():
                    for op_dir in src_auto_dir.iterdir():
                        if op_dir.is_dir():
                            op_images_dir = op_dir / "images"
                            if op_images_dir.exists():
                                for img_file in op_images_dir.glob("*.png"):
                                    dest_cat = assets_dir / "variables"
                                    dest_cat.mkdir(exist_ok=True)
                                    shutil.copy2(str(img_file), str(dest_cat / img_file.name))
                                    assets_path = f"assets/variables/{img_file.name}"
                                    image_mapping[f"/api/images/automation/ops/{op_dir.name}/images/{img_file.name}"] = assets_path
                                    image_mapping[f"automation/ops/{op_dir.name}/images/{img_file.name}"] = assets_path
            
            # 安全序列化 facts（处理 Path 等非标准类型）
            def _safe_default(obj):
                if isinstance(obj, Path):
                    return str(obj)
                return str(obj)
            export_facts = json.loads(json.dumps(draft.facts, default=_safe_default))
            # 将 facts 中的 /api/images/ 路径转为 assets/ 路径
            if 'images' in export_facts:
                for category in export_facts['images']:
                    export_facts['images'][category] = [
                        image_mapping.get(p, p) for p in export_facts['images'][category]
                    ]
            # 修复 automation_ops 中的图片路径
            if 'automation_ops' in export_facts:
                for op in export_facts['automation_ops']:
                    if 'images' in op and op['images']:
                        op['images'] = [
                            image_mapping.get(p, p) for p in op['images']
                        ]
            
            md_content = generate_report_content(export_facts, filled_slots, image_mapping)
            
            md_path = output_dir / "report.md"
            md_path.write_text(md_content, encoding='utf-8')
            
            docx_path = output_dir / "report.docx"
            build_docx_report(md_content, str(docx_path), str(assets_dir))
            
            pdf_path = output_dir / "report.pdf"
            pdf_ok = build_pdf_report(md_content, str(pdf_path), str(assets_dir))

            draft_json = output_dir / "draft.json"
            draft_json.write_text(json.dumps(draft.to_dict(), ensure_ascii=False, indent=2, default=_safe_default), encoding='utf-8')
            print(f"[MCP] export_report: 文件已写入 {output_dir}")

            files = ["report.md", "report.docx", "draft.json"]
            if pdf_ok:
                files.insert(2, "report.pdf")
            
            return json.dumps({
                "success": True,
                "action": "export_report",
                "message": f"报告导出成功！输出目录：{output_dir}",
                "output_dir": str(output_dir),
                "files": files
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            import traceback as _tb
            result = {"error": str(e)}
            if _DEBUG_MODE:
                result["traceback"] = _tb.format_exc()
            return json.dumps(result, ensure_ascii=False)

    return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)


@app.route('/api/mcp/analytics', methods=['GET'])
def mcp_analytics():
    """MCP 工具调用统计分析"""
    return jsonify(tool_observer.get_analytics())


@app.route('/api/mcp/logs', methods=['GET'])
def mcp_logs():
    """MCP 工具调用日志"""
    limit = request.args.get('limit', 50, type=int)
    return jsonify(tool_observer.get_recent_logs(limit))


@app.route('/api/mcp-chat-stream', methods=['POST'])
def mcp_chat_stream():
    """MCP AI 对话接口 - SSE 流式输出

    LLM 凭证统一取自管理员维护的系统级 AI 配置，前端不再传递 apiKey。
    """
    data = request.get_json()
    if not data or 'messages' not in data:
        return jsonify({'error': '请提供消息列表'}), 400

    messages = data['messages']
    active_cfg = _resolve_active_llm_config()
    api_key = active_cfg['api_key']
    stored_base_url = active_cfg['base_url']
    stored_model = active_cfg['model']
    web_search_enabled = data.get('webSearchEnabled', False)

    if not api_key:
        return jsonify({'error': '系统尚未配置 AI 模型密钥，请联系管理员在管理中心的"AI 密钥"中启用一条配置'}), 400

    # 记录该条系统级配置的最后使用时间（用于管理员审计）
    if active_cfg.get('id'):
        try:
            update_system_ai_config_last_used(active_cfg['id'])
        except Exception:
            pass

    def generate():
        try:
            from openai import OpenAI
            _base_url = stored_base_url or "https://api.deepseek.com/v1"
            _model = stored_model or "deepseek-chat"
            client = OpenAI(api_key=api_key, base_url=_base_url)

            _active_model = _model
            active_tools = [t for t in MCP_TOOLS if t['function']['name'] != 'web_search' or web_search_enabled]

            web_search_prompt = "\n- web_search: 联网搜索，从互联网获取相关技术资料和背景知识" if web_search_enabled else ""
            system_prompt = f"""你是一个专业的CFD仿真数据分析助手，采用 **Plan-Execute-Adapt** 架构工作。

## 可用 MCP 工具

**数据查询工具（可同一轮调用多个）：**
- get_run_info: 查询数据包元信息
- list_signals: 列出所有流场变量
- compute_metrics: 计算变量统计指标
- get_mesh_info: 获取网格结构信息
- get_derived_quantities: 获取派生物理量（速度、马赫数、流动状态等）
- rag_query: 从专业知识库检索技术资料（混合检索：BM25+向量+RRF融合）{web_search_prompt}

**工作流工具（每次只调用一个）：**
- auto_configure: 自动配置报告参数，创建Draft
- generate_next_slot: 生成下一个待处理槽位
- generate_all_slots: 批量生成所有槽位
- accept_all_slots: 确认所有草稿
- export_report: 导出报告（MD + Word）

## Plan-Execute-Adapt 工作模式

当用户提出复杂任务（如生成报告、分析数据）时，你应该：

**第1步 — Plan（制定计划）**
先分析任务需求，制定明确的工具调用计划。例如：
"我将按以下步骤完成报告生成：
 1. 查询数据包信息（get_run_info）
 2. 分析流场变量（list_signals + compute_metrics）
 3. 获取派生物理量（get_derived_quantities）
 4. 检索相关知识（rag_query）
 5. 配置报告参数（auto_configure）
 6. 逐步生成各章节内容
 7. 确认并导出"

**第2步 — Execute（执行计划）**
按计划逐步执行，每步完成后向用户汇报进展。

**第3步 — Adapt（动态调整）**
根据中间结果调整后续计划。例如：
- 发现是跨声速流动 → 增加激波分析的知识检索
- 发现网格质量问题 → 在评定准则中重点讨论网格独立性

## 工作流程

当用户要求生成报告时：
1. 先用 get_run_info + list_signals 了解数据，制定分析计划
2. 调用 auto_configure 配置报告，停下来向用户展示计划
3. 用户确认后，逐个调用 generate_next_slot 生成槽位
4. 每个槽位生成后简短说明内容，等用户说"继续"
5. 全部完成后询问是否确认导出

**重要规则**：
- 每次回复最多调用一个工作流工具
- 数据查询工具可在同一轮调用多个
- 每个关键断言标注来源：[DATA]数据事实 / [RAG-N]知识库 / [INFER]推断
- 回答要专业简洁，结合实际数据分析"""

            workflow_state = "\n\n**当前工作流状态：**\n"
            workflow_state += f"- 数据包已加载: {'是' if current_data_package else '否'}\n"
            if draft_manager.current_draft:
                progress = draft_manager.get_progress()
                workflow_state += f"- Draft已创建: 是\n"
                workflow_state += f"- 槽位总数: {progress.get('total', 0)}\n"
                workflow_state += f"- 待生成(pending): {progress.get('pending', 0)}\n"
                workflow_state += f"- 已生成草稿(draft): {progress.get('draft', 0)}\n"
                workflow_state += f"- 已确认(accepted): {progress.get('accepted', 0)}\n"
                if progress.get('pending', 0) > 0:
                    workflow_state += f"→ 下一步应调用: generate_next_slot（还剩{progress['pending']}个待生成）\n"
                elif progress.get('draft', 0) > 0 and progress.get('pending', 0) == 0:
                    workflow_state += "→ 所有槽位已生成完毕，应询问用户是否全部确认并导出\n"
                elif progress.get('accepted', 0) > 0 and progress.get('pending', 0) == 0 and progress.get('draft', 0) == 0:
                    workflow_state += "→ 下一步应调用: export_report\n"
            else:
                workflow_state += "- Draft已创建: 否\n"
                if current_data_package:
                    workflow_state += "→ 下一步应调用: auto_configure\n"

            system_prompt += workflow_state
            full_messages = [{"role": "system", "content": system_prompt}] + messages

            latest_user_text = ''
            for m in reversed(messages):
                if m.get('role') == 'user':
                    latest_user_text = (m.get('content') or '').strip()
                    break

            start_report_keywords = [
                '自动生成报告', '帮我自动生成', '重新生成报告', '从头生成报告', '开始生成报告', '新建报告'
            ]
            continue_or_export_keywords = [
                '继续', '下一步', '导出', '确认', 'accept', 'export', '暂停', '稍后'
            ]
            force_auto_configure = (
                bool(latest_user_text)
                and current_data_package is not None
                and any(k in latest_user_text for k in start_report_keywords)
                and not any(k in latest_user_text.lower() for k in continue_or_export_keywords)
            )
            initial_tool_choice = {"type": "function", "function": {"name": "auto_configure"}} if force_auto_configure else "auto"

            tool_calls_log = []
            WORKFLOW_ACTIONS = {'auto_configure', 'generate_next_slot', 'generate_all_slots', 'accept_all_slots', 'export_report'}
            workflow_paused = False
            hit_workflow_action = None

            MAX_TOOL_ITERATIONS = 10
            MAX_CONSECUTIVE_ERRORS = 3

            # ── Phase 1: 工具调用循环（非流式，确保可靠检测tool_calls）──
            response = client.chat.completions.create(
                model=_active_model,
                messages=full_messages,
                tools=active_tools,
                tool_choice=initial_tool_choice,
                temperature=0.5,
                max_tokens=2000
            )
            msg = response.choices[0].message

            tool_iteration = 0
            consecutive_errors = 0

            while msg.tool_calls:
                tool_iteration += 1
                if tool_iteration > MAX_TOOL_ITERATIONS:
                    print(f"[MCP-Stream] 工具调用循环达到上限 ({MAX_TOOL_ITERATIONS})，强制退出")
                    yield f"data: {json.dumps({'type': 'delta', 'content': '\\n\\n[系统提示：工具调用次数已达上限，自动停止]'}, ensure_ascii=False)}\n\n"
                    break

                tool_results = []
                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    try:
                        tool_args = json.loads(tc.function.arguments)
                    except Exception:
                        tool_args = {}

                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'args': tool_args}, ensure_ascii=False)}\n\n"

                    print(f"[MCP-Stream] 执行工具: {tool_name} (迭代 {tool_iteration}/{MAX_TOOL_ITERATIONS})")
                    tool_result = _execute_mcp_tool(tool_name, tool_args)
                    try:
                        parsed_result = json.loads(tool_result)
                    except Exception:
                        parsed_result = {}

                    is_error = "error" in parsed_result
                    if is_error:
                        consecutive_errors += 1
                    else:
                        consecutive_errors = 0

                    tool_calls_log.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result_preview": tool_result[:200],
                        "action": parsed_result.get("action"),
                        "result": parsed_result
                    })
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_result
                    })
                    if tool_name in WORKFLOW_ACTIONS:
                        hit_workflow_action = tool_name

                full_messages.append(msg)
                full_messages.extend(tool_results)

                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    print(f"[MCP-Stream] 连续 {MAX_CONSECUTIVE_ERRORS} 次工具错误，触发熔断")
                    yield f"data: {json.dumps({'type': 'delta', 'content': '\\n\\n[系统提示：工具连续出错，已自动停止]'}, ensure_ascii=False)}\n\n"
                    break

                if hit_workflow_action:
                    stream_resp = client.chat.completions.create(
                        model=_active_model,
                        messages=full_messages,
                        tools=active_tools,
                        tool_choice="none",
                        temperature=0.5,
                        max_tokens=500,
                        stream=True
                    )
                    workflow_paused = True
                    for chunk in stream_resp:
                        delta = chunk.choices[0].delta.content if chunk.choices[0].delta else None
                        if delta:
                            yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type': 'done', 'tool_calls': tool_calls_log, 'workflow_paused': True, 'workflow_action': hit_workflow_action, 'workflow_result': tool_calls_log[-1]['result'] if tool_calls_log else {}}, ensure_ascii=False)}\n\n"
                    return

                response = client.chat.completions.create(
                    model=_active_model,
                    messages=full_messages,
                    tools=active_tools,
                    tool_choice="auto",
                    temperature=0.5,
                    max_tokens=2000
                )
                msg = response.choices[0].message

            # ── Phase 2: 无工具调用 / 工具循环结束 → 真正流式输出最终答案 ──
            if msg.content:
                # 非流式调用已返回完整文本，丢弃它，改用stream=True重新调用获得真正流式输出
                # 不将msg加入full_messages，重新用相同的消息列表做流式调用
                stream_resp = client.chat.completions.create(
                    model=_active_model,
                    messages=full_messages,
                    tools=active_tools,
                    tool_choice="none",
                    temperature=0.5,
                    max_tokens=2000,
                    stream=True
                )
                for chunk in stream_resp:
                    delta = chunk.choices[0].delta.content if chunk.choices[0].delta else None
                    if delta:
                        yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
            else:
                # 工具循环结束后 msg 没有 content，需要再调一次 LLM 做总结
                full_messages.append(msg)
                stream_resp = client.chat.completions.create(
                    model=_active_model,
                    messages=full_messages,
                    tools=active_tools,
                    tool_choice="none",
                    temperature=0.5,
                    max_tokens=2000,
                    stream=True
                )
                for chunk in stream_resp:
                    delta = chunk.choices[0].delta.content if chunk.choices[0].delta else None
                    if delta:
                        yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'tool_calls': tool_calls_log, 'workflow_paused': False}, ensure_ascii=False)}\n\n"

        except Exception as e:
            import traceback as _tb
            event = {'type': 'error', 'error': str(e)}
            if _DEBUG_MODE:
                event['traceback'] = _tb.format_exc()
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


# ============ 静态文件服务 ============

@app.route('/api/preview/<path:filepath>')
def preview_file(filepath):
    """预览文件（仅允许访问输出目录内的文件）"""
    full_path = Path(filepath).resolve()
    allowed_root = OUTPUT_FOLDER.resolve()
    if not str(full_path).startswith(str(allowed_root)):
        return jsonify({'success': False, 'error': '禁止访问该路径'}), 403
    if not full_path.exists():
        return jsonify({'success': False, 'error': '文件不存在'}), 404
    
    return send_file(str(full_path))


# ── 系统级 AI 配置：只读视图（普通用户可查看由管理员维护的当前模型） ──

_VALID_AI_PROVIDERS = ('deepseek', 'openai', 'local', 'ollama')


def _mask_key_for_response(api_key: str) -> str:
    if not api_key:
        return ''
    return api_key[:8] + '***' + api_key[-4:] if len(api_key) > 12 else '***'


@app.route('/api/user/ai-config', methods=['GET'])
@login_required
def api_get_ai_config():
    """只读返回当前系统级 AI 配置（由管理员统一维护，普通用户仅可查看）"""
    cfg = get_active_system_ai_config()
    if not cfg:
        return jsonify({
            'success': True,
            'managed_by_admin': True,
            'configured': False,
            'config': {'provider': '', 'base_url': '', 'model': ''},
            'api_key_masked': '',
            'message': '系统尚未配置 AI 模型，请联系管理员在管理中心启用一条 AI 密钥'
        })
    return jsonify({
        'success': True,
        'managed_by_admin': True,
        'configured': True,
        'config': {
            'provider': cfg.get('provider', 'deepseek'),
            'base_url': cfg.get('base_url', ''),
            'model': cfg.get('model', ''),
        },
        'api_key_masked': _mask_key_for_response(cfg.get('api_key', '')),
    })


@app.route('/api/user/ai-config', methods=['PUT'])
@login_required
def api_save_ai_config():
    """普通用户不再可修改 AI 配置——系统 AI 密钥由管理员统一管理"""
    return jsonify({
        'success': False,
        'error': '系统 AI 密钥已由管理员统一管理，普通用户不可修改；如有需求请联系管理员'
    }), 403


# ── 管理员：系统级 AI 密钥管理 ──

@app.route('/api/admin/ai-keys', methods=['GET'])
@admin_required
def api_admin_list_ai_keys():
    """列出所有系统级 AI 密钥（api_key 字段已脱敏）"""
    return jsonify({'success': True, 'keys': list_system_ai_configs(include_secret=False)})


@app.route('/api/admin/ai-keys', methods=['POST'])
@admin_required
def api_admin_create_ai_key():
    """创建一条系统级 AI 密钥配置"""
    data = request.get_json() or {}
    name = str(data.get('name') or '').strip()
    provider = str(data.get('provider') or 'deepseek').strip() or 'deepseek'
    api_key_val = str(data.get('api_key') or '').strip()
    base_url_val = str(data.get('base_url') or '').strip()
    model_val = str(data.get('model') or '').strip()
    activate = bool(data.get('activate', False))

    if provider not in _VALID_AI_PROVIDERS:
        return jsonify({'success': False, 'error': f'不支持的 provider：{provider}'}), 400
    if provider in ('deepseek', 'openai') and not api_key_val:
        return jsonify({'success': False, 'error': '云端模型必须提供 API Key'}), 400
    if not name:
        name = f'{provider} 配置'

    new_id = create_system_ai_config(
        name=name,
        provider=provider,
        api_key=api_key_val,
        base_url=base_url_val,
        model=model_val,
        activate=activate,
        created_by=g.current_user['id'],
    )
    audit('create_ai_key', 'system_ai_config', str(new_id),
          f'新增 AI 密钥：name={name}, provider={provider}, activate={activate}')
    return jsonify({'success': True, 'id': new_id, 'message': 'AI 密钥已创建'})


@app.route('/api/admin/ai-keys/<int:config_id>/activate', methods=['POST'])
@admin_required
def api_admin_activate_ai_key(config_id: int):
    """启用指定 AI 密钥为当前生效配置"""
    if not activate_system_ai_config(config_id):
        return jsonify({'success': False, 'error': '未找到指定的 AI 密钥'}), 404
    # 启用后重置 Web 搜索器缓存，让新凭证在下一次调用时生效
    global web_searcher
    web_searcher = None
    audit('activate_ai_key', 'system_ai_config', str(config_id), '启用 AI 密钥')
    return jsonify({'success': True, 'message': 'AI 密钥已启用'})


@app.route('/api/admin/ai-keys/<int:config_id>/deactivate', methods=['POST'])
@admin_required
def api_admin_deactivate_ai_key(config_id: int):
    """停用指定 AI 密钥（不删除记录）"""
    if not deactivate_system_ai_config(config_id):
        return jsonify({'success': False, 'error': '未找到指定的 AI 密钥'}), 404
    global web_searcher
    web_searcher = None
    audit('deactivate_ai_key', 'system_ai_config', str(config_id), '停用 AI 密钥')
    return jsonify({'success': True, 'message': 'AI 密钥已停用'})


@app.route('/api/admin/ai-keys/<int:config_id>', methods=['DELETE'])
@admin_required
def api_admin_delete_ai_key(config_id: int):
    """删除指定 AI 密钥（建议先停用再删除）"""
    cfg = get_system_ai_config_by_id(config_id)
    if not cfg:
        return jsonify({'success': False, 'error': '未找到指定的 AI 密钥'}), 404
    if cfg.get('is_active'):
        return jsonify({'success': False, 'error': '请先停用该密钥再删除'}), 400
    delete_system_ai_config(config_id)
    audit('delete_ai_key', 'system_ai_config', str(config_id), f'删除 AI 密钥：name={cfg.get("name")}')
    return jsonify({'success': True, 'message': 'AI 密钥已删除'})


if __name__ == '__main__':
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    
    print("=" * 60)
    print("智能仿真报告生成工具 V2 - API 服务器")
    print("=" * 60)
    print(f"知识库路径: {KB_FOLDER}")
    print(f"上传目录: {UPLOAD_FOLDER}")
    print(f"输出目录: {OUTPUT_FOLDER}")
    print("新功能: Browser集成, 槽位交互, Clarification Gate, MCP对话")
    print("=" * 60)
    
    # 初始化数据库
    init_db()
    print("数据库已初始化 (SQLite)")

    # 仅在显式提供本地演示密码时创建管理员，避免默认弱口令。
    demo_admin = seed_test_accounts()
    if demo_admin:
        print(f"本地演示管理员已就绪: {demo_admin}")
        _seed_demo_organizations()
    else:
        print("未创建演示管理员；如需本地演示，请设置 SIMUREPORT_DEMO_ADMIN_PASSWORD")

    # 管理员统一维护 AI Key：若系统级配置表为空，则播种一条默认 DeepSeek 配置
    if seed_default_system_ai_config(DEEPSEEK_API_KEY):
        print(f"[AI配置] 已写入默认系统级 AI Key（管理员可在管理中心维护）")
    else:
        active_cfg = get_active_system_ai_config()
        if active_cfg:
            print(f"[AI配置] 当前生效的系统级 AI 密钥：{active_cfg.get('name')} (provider={active_cfg.get('provider')})")
        else:
            print("[AI配置] 系统级 AI 密钥未启用，请管理员在管理中心启用一条配置")
    
    # 初始化 MCP 工具可观测性（SQLite 持久化）
    _observer_db = str(Path(UPLOAD_FOLDER).parent / 'tool_call_logs.db')
    init_observer(_observer_db)
    print(f"MCP 工具可观测性已初始化 (SQLite: {_observer_db})")

    # 启动时自动加载知识库
    _auto_load_kb()
    
    app.run(host='0.0.0.0', port=5000, debug=os.environ.get('FLASK_DEBUG', '0') == '1')
