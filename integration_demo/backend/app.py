import base64
import json
import os
from pathlib import Path
from urllib.parse import quote

import requests
from flask import Flask, Response, jsonify, request, session, stream_with_context
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = os.environ.get('INTEGRATION_DEMO_SECRET', 'integration-demo-secret')
CORS(app, supports_credentials=True)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKAGE_PATH = str(PROJECT_ROOT / '数据包')
DEFAULT_CORE_BACKEND = os.environ.get('SIMUREPORT_BACKEND_URL', 'http://127.0.0.1:5000')
DEFAULT_CORE_FRONTEND = os.environ.get('SIMUREPORT_FRONTEND_URL', 'http://localhost:3001')
REQUEST_TIMEOUT = 300
STREAM_TIMEOUT = 3600


def current_core_backend():
    return (session.get('core_backend_base') or DEFAULT_CORE_BACKEND).rstrip('/')


def current_core_frontend():
    return (session.get('core_frontend_base') or DEFAULT_CORE_FRONTEND).rstrip('/')


def current_auth_headers():
    token = session.get('backend_token')
    if not token:
        return {}
    return {'Authorization': f'Bearer {token}'}


def current_user_payload():
    return session.get('backend_user') or {}


def require_login_state():
    if not session.get('backend_token'):
        return False, (jsonify({'success': False, 'error': '请先登录 SimuReport'}), 401)
    return True, None


def upstream_json(method, path, payload=None, extra_headers=None, timeout=REQUEST_TIMEOUT):
    headers = {'Content-Type': 'application/json'}
    headers.update(current_auth_headers())
    if extra_headers:
        headers.update(extra_headers)
    url = f"{current_core_backend()}{path}"
    try:
        response = requests.request(method=method.upper(), url=url, json=payload, headers=headers, timeout=timeout)
    except requests.exceptions.ConnectionError:
        # 主后端未启动 / 端口未就绪（启动期间常见）—— 返回 503 + 友好提示
        return 503, {'success': False, 'error': 'SimuReport 后端尚未就绪，请稍候重试（通常需等待知识库索引加载完成）'}
    except requests.exceptions.Timeout:
        return 504, {'success': False, 'error': 'SimuReport 后端响应超时'}
    except requests.exceptions.RequestException as exc:
        return 502, {'success': False, 'error': f'上游请求失败：{exc}'}
    try:
        data = response.json()
    except Exception:
        data = {'success': False, 'error': response.text}
    return response.status_code, data


def extract_tool_payload(result):
    if not isinstance(result, dict):
        return {}
    payload = result.get('result')
    return payload if isinstance(payload, dict) else {}


def infer_auto_configure_arguments(run_info, derived_info):
    dataset_type = str(run_info.get('dataset_type') or '').lower()
    derived_quantities = derived_info.get('derived_quantities') if isinstance(derived_info, dict) else {}
    flow_analysis = derived_info.get('flow_analysis') if isinstance(derived_info, dict) else {}
    findings = flow_analysis.get('key_findings') or []
    mach = derived_quantities.get('estimated_mach')

    domain = 'external_aero' if ('plot3d' in dataset_type or (isinstance(mach, (int, float)) and mach > 0.3)) else 'general_cfd'
    phenomena = []
    for finding in findings:
        finding_text = str(finding)
        finding_lower = finding_text.lower()
        if 'shock' in finding_lower or '激波' in finding_text:
            phenomena.append('shock_wave')
        if 'separation' in finding_lower or '分离' in finding_text:
            phenomena.append('flow_separation')
        if 'compressible' in finding_lower or '可压缩' in finding_text:
            phenomena.append('compressible_flow')
        if 'high_speed' in finding_lower or '高速' in finding_text:
            phenomena.append('high_speed_flow')

    normalized = []
    for item in phenomena:
        if item not in normalized:
            normalized.append(item)

    if not normalized:
        normalized = ['compressible_flow'] if isinstance(mach, (int, float)) and mach > 0.3 else ['flow_separation']

    return {
        'domain': domain,
        'phenomena': normalized,
        'purpose': 'performance_evaluation',
        'inference_level': 'may_infer',
        'enable_web_search': False,
        'enable_system_kb': True,
        'enable_personal_kb': True,
        'enable_org_kb': True,
    }


def sse_event(payload):
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.get('/api/config')
def get_config():
    return jsonify({
        'success': True,
        'coreBackendBase': current_core_backend(),
        'coreFrontendBase': current_core_frontend(),
        'defaultPackagePath': DEFAULT_PACKAGE_PATH,
        'loggedIn': bool(session.get('backend_token')),
        'user': current_user_payload(),
        'packagePath': session.get('package_path', ''),
        'packageInfo': session.get('package_info'),
        'lastOutputDir': session.get('last_output_dir', '')
    })


@app.post('/api/config')
def update_config():
    data = request.get_json(silent=True) or {}
    core_backend = str(data.get('coreBackendBase') or '').strip()
    core_frontend = str(data.get('coreFrontendBase') or '').strip()
    if core_backend:
        session['core_backend_base'] = core_backend.rstrip('/')
    if core_frontend:
        session['core_frontend_base'] = core_frontend.rstrip('/')
    return jsonify({
        'success': True,
        'coreBackendBase': current_core_backend(),
        'coreFrontendBase': current_core_frontend()
    })


@app.get('/api/auth/session')
def get_auth_session():
    return jsonify({
        'success': True,
        'loggedIn': bool(session.get('backend_token')),
        'user': current_user_payload(),
        'packagePath': session.get('package_path', ''),
        'packageInfo': session.get('package_info'),
        'lastOutputDir': session.get('last_output_dir', '')
    })


@app.post('/api/auth/login')
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get('username') or '').strip()
    password = str(data.get('password') or '')
    if not username or not password:
        return jsonify({'success': False, 'error': '请输入用户名和密码'}), 400

    response = requests.post(
        f"{current_core_backend()}/api/auth/login",
        json={'username': username, 'password': password},
        headers={'Content-Type': 'application/json'},
        timeout=REQUEST_TIMEOUT,
    )
    try:
        result = response.json()
    except Exception:
        result = {'success': False, 'error': response.text}

    if response.status_code != 200 or not result.get('success'):
        return jsonify({'success': False, 'error': result.get('error', '登录失败')}), response.status_code or 500

    session['backend_token'] = result.get('token', '')
    session['backend_user'] = result.get('user') or {}
    return jsonify({
        'success': True,
        'user': result.get('user') or {},
        'loggedIn': True
    })


@app.post('/api/auth/logout')
def logout():
    session.pop('backend_token', None)
    session.pop('backend_user', None)
    session.pop('package_path', None)
    session.pop('package_info', None)
    session.pop('last_output_dir', None)
    return jsonify({'success': True})


@app.post('/api/package/upload-path')
def upload_package_path():
    ok, error_response = require_login_state()
    if not ok:
        return error_response

    data = request.get_json(silent=True) or {}
    package_path = str(data.get('path') or '').strip()
    if not package_path:
        return jsonify({'success': False, 'error': '请提供数据包路径'}), 400

    status, result = upstream_json('POST', '/api/upload-folder', {'path': package_path})
    if status != 200 or not result.get('success'):
        return jsonify({'success': False, 'error': result.get('error', '数据包上传失败')}), status or 500

    session['package_path'] = result.get('path', package_path)
    session['package_info'] = result.get('info')
    return jsonify({
        'success': True,
        'path': result.get('path', package_path),
        'info': result.get('info'),
        'validation': result.get('validation'),
        'message': result.get('message', '数据包已上传')
    })


@app.post('/api/session/reset')
def reset_session():
    ok, error_response = require_login_state()
    if not ok:
        return error_response

    status, result = upstream_json('POST', '/api/session/reset', {})
    if status != 200 or not result.get('success'):
        return jsonify({'success': False, 'error': result.get('error', '重置会话失败')}), status or 500

    session.pop('package_path', None)
    session.pop('package_info', None)
    session.pop('last_output_dir', None)
    return jsonify({
        'success': True,
        'message': result.get('message', '当前数据包与 Draft 已清空'),
        'recommendedStep': result.get('recommendedStep', 'upload')
    })


@app.get('/api/mcp/tools/list')
def proxy_mcp_tools_list():
    ok, error_response = require_login_state()
    if not ok:
        return error_response

    status, result = upstream_json('GET', '/mcp/tools/list')
    if status != 200:
        return jsonify({'success': False, 'error': result.get('error', '获取 MCP 工具列表失败')}), status or 500
    return jsonify({'success': True, 'tools': result.get('tools', [])})


@app.post('/api/mcp/tools/call')
def proxy_mcp_tools_call():
    ok, error_response = require_login_state()
    if not ok:
        return error_response

    data = request.get_json(silent=True) or {}
    tool_name = str(data.get('name') or '').strip()
    arguments = data.get('arguments') if isinstance(data.get('arguments'), dict) else {}
    if not tool_name:
        return jsonify({'success': False, 'error': '缺少工具名称'}), 400

    status, result = upstream_json('POST', '/mcp/tools/call', {'name': tool_name, 'arguments': arguments})
    payload = extract_tool_payload(result)
    if tool_name == 'export_report' and payload.get('output_dir'):
        session['last_output_dir'] = payload.get('output_dir')

    if status != 200:
        return jsonify({'success': False, 'error': result.get('error', 'MCP 工具调用失败'), 'tool': tool_name, 'result': payload}), status or 500

    return jsonify({
        'success': not result.get('isError', False),
        'tool': result.get('tool', tool_name),
        'result': payload or result.get('result') or {},
        'isError': result.get('isError', False),
    })


@app.post('/api/workflow/one-click-stream')
def one_click_stream():
    ok, error_response = require_login_state()
    if not ok:
        return error_response

    def generate():
        try:
            yield sse_event({'type': 'progress', 'percent': 3, 'message': '正在发现外部可调用的 MCP 工具…'})
            status, tool_list_result = upstream_json('GET', '/mcp/tools/list')
            if status != 200:
                yield sse_event({'type': 'error', 'error': tool_list_result.get('error', '获取 MCP 工具列表失败')})
                return

            tools = tool_list_result.get('tools', [])
            tool_names = [tool.get('name') for tool in tools if tool.get('name')]
            required_tools = ['get_run_info', 'list_signals', 'get_derived_quantities', 'auto_configure', 'generate_all_slots', 'accept_all_slots', 'export_report']
            missing_tools = [name for name in required_tools if name not in tool_names]
            if missing_tools:
                yield sse_event({'type': 'error', 'error': f'MCP 工具缺失: {", ".join(missing_tools)}'})
                return

            yield sse_event({'type': 'tool_catalog', 'count': len(tool_names), 'tools': tool_names})
            yield sse_event({'type': 'progress', 'percent': 8, 'message': f'已发现 {len(tool_names)} 个 MCP 工具，开始外部编排执行'})

            tool_results = {}
            workflow_steps = [
                ('get_run_info', {}, 16, '读取数据包元信息'),
                ('list_signals', {}, 26, '列出可用流场变量'),
                ('get_derived_quantities', {}, 38, '分析派生物理量与流动状态'),
            ]

            for tool_name, arguments, percent, message in workflow_steps:
                yield sse_event({'type': 'tool_call', 'name': tool_name, 'args': arguments, 'message': message})
                status, result = upstream_json('POST', '/mcp/tools/call', {'name': tool_name, 'arguments': arguments}, timeout=STREAM_TIMEOUT)
                payload = extract_tool_payload(result)
                if status != 200 or result.get('isError') or payload.get('error'):
                    yield sse_event({'type': 'error', 'error': payload.get('error') or result.get('error', f'{tool_name} 调用失败'), 'tool': tool_name})
                    return
                tool_results[tool_name] = payload
                yield sse_event({'type': 'tool_result', 'name': tool_name, 'content': payload})
                yield sse_event({'type': 'progress', 'percent': percent, 'message': message})

            auto_configure_args = infer_auto_configure_arguments(
                tool_results.get('get_run_info', {}),
                tool_results.get('get_derived_quantities', {}),
            )

            remaining_steps = [
                ('auto_configure', auto_configure_args, 55, '按分析结果配置报告结构'),
                ('generate_all_slots', {}, 74, '批量生成报告槽位内容'),
                ('accept_all_slots', {}, 86, '确认全部生成结果'),
                ('export_report', {}, 100, '导出最终报告文件'),
            ]

            export_payload = {}
            for tool_name, arguments, percent, message in remaining_steps:
                yield sse_event({'type': 'tool_call', 'name': tool_name, 'args': arguments, 'message': message})
                status, result = upstream_json('POST', '/mcp/tools/call', {'name': tool_name, 'arguments': arguments}, timeout=STREAM_TIMEOUT)
                payload = extract_tool_payload(result)
                if status != 200 or result.get('isError') or payload.get('error'):
                    yield sse_event({'type': 'error', 'error': payload.get('error') or result.get('error', f'{tool_name} 调用失败'), 'tool': tool_name})
                    return
                if tool_name == 'export_report' and payload.get('output_dir'):
                    session['last_output_dir'] = payload.get('output_dir')
                    export_payload = payload
                yield sse_event({'type': 'tool_result', 'name': tool_name, 'content': payload})
                yield sse_event({'type': 'progress', 'percent': percent, 'message': message})

            yield sse_event({
                'type': 'done',
                'message': '外部系统已通过 MCP 工具链完成报告生成与导出。',
                'output_dir': export_payload.get('output_dir', ''),
                'files': export_payload.get('files', []),
                'tool_chain': required_tools,
            })
        except Exception as exc:
            yield sse_event({'type': 'error', 'error': str(exc)})

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


@app.post('/api/chat/stream')
def proxy_chat_stream():
    ok, error_response = require_login_state()
    if not ok:
        return error_response

    payload = request.get_json(silent=True) or {}

    def generate():
        upstream = requests.post(
            f"{current_core_backend()}/api/mcp-chat-stream",
            json=payload,
            headers={
                'Content-Type': 'application/json',
                **current_auth_headers(),
            },
            stream=True,
            timeout=STREAM_TIMEOUT,
        )
        upstream.raise_for_status()
        for line in upstream.iter_lines(decode_unicode=True):
            if line is None:
                continue
            yield f"{line}\n"
        yield '\n'

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


@app.get('/api/web/open-link')
def get_web_open_link():
    ok, error_response = require_login_state()
    if not ok:
        return error_response

    token = session.get('backend_token', '')
    user = current_user_payload()
    encoded_user = base64.b64encode(json.dumps(user, ensure_ascii=False).encode('utf-8')).decode('utf-8')
    if session.get('last_output_dir'):
        recommended_step = 'generate'
    elif session.get('package_info'):
        recommended_step = 'clarification'
    else:
        recommended_step = 'upload'
    integration_context = {
        'packagePath': session.get('package_path', ''),
        'packageInfo': session.get('package_info'),
        'recommendedStep': recommended_step,
        'lastOutputDir': session.get('last_output_dir', '')
    }
    encoded_context = base64.b64encode(json.dumps(integration_context, ensure_ascii=False).encode('utf-8')).decode('utf-8')
    url = (
        f"{current_core_frontend()}/integration-entry"
        f"?token={quote(token)}"
        f"&user={quote(encoded_user)}"
        f"&context={quote(encoded_context)}"
        f"&redirect={quote('/v2')}"
    )
    return jsonify({'success': True, 'url': url})


@app.get('/api/report/download/<file_type>')
def download_report(file_type):
    ok, error_response = require_login_state()
    if not ok:
        return error_response

    output_dir = str(request.args.get('dir') or session.get('last_output_dir') or '').strip()
    if not output_dir:
        return jsonify({'success': False, 'error': '缺少输出目录'}), 400

    upstream = requests.get(
        f"{current_core_backend()}/api/download/{file_type}",
        params={'dir': output_dir},
        headers=current_auth_headers(),
        stream=True,
        timeout=REQUEST_TIMEOUT,
    )
    content_type = upstream.headers.get('Content-Type', 'application/octet-stream')
    content_disposition = upstream.headers.get('Content-Disposition')

    def generate():
        for chunk in upstream.iter_content(chunk_size=8192):
            if chunk:
                yield chunk

    response = Response(generate(), status=upstream.status_code, content_type=content_type)
    if content_disposition:
        response.headers['Content-Disposition'] = content_disposition
    return response


@app.get('/api/health')
def health():
    return jsonify({'success': True, 'service': 'integration-demo-backend'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5100, debug=os.environ.get('FLASK_DEBUG', '0') == '1')
