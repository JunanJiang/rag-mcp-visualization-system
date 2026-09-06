"""SQLite 数据库模型

提供用户管理、组织管理、报告历史持久化和审计日志。
使用 Python 内置 sqlite3，无需额外数据库服务。

角色体系：
  - user:     普通用户，可生成报告、查看自己和组织内的报告
  - admin:    管理员，可管理组织成员、查看审计日志、管理 API 密钥
"""

import sqlite3
import os
import hashlib
import secrets
import json
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from werkzeug.security import generate_password_hash

from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    """获取数据库连接（启用 WAL 模式提升并发性能）"""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row  # 返回字典风格的行
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    """数据库连接上下文管理器"""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# 合法角色
VALID_ROLES = ('user', 'admin')


def init_db():
    """初始化数据库表结构"""
    with get_db() as conn:
        conn.executescript("""
            -- 用户表
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                display_name TEXT DEFAULT '',
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            );

            -- 组织表
            CREATE TABLE IF NOT EXISTS organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT '',
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id)
            );

            -- 组织成员表
            CREATE TABLE IF NOT EXISTS org_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                org_id INTEGER NOT NULL,
                role TEXT DEFAULT 'member',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, org_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (org_id) REFERENCES organizations(id)
            );

            -- API 密钥表（开发者用于外部平台集成）
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                key_hash TEXT NOT NULL,
                key_prefix TEXT NOT NULL,
                name TEXT DEFAULT '',
                permissions TEXT DEFAULT 'read,write',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            -- 审计日志表（数据安全）
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                resource_type TEXT,
                resource_id TEXT,
                details TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- 报告历史表
            CREATE TABLE IF NOT EXISTS report_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                org_id INTEGER,
                title TEXT DEFAULT '',
                data_package_path TEXT,
                output_dir TEXT,
                domain TEXT DEFAULT '',
                purpose TEXT DEFAULT '',
                slot_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'generating',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (org_id) REFERENCES organizations(id)
            );

            CREATE INDEX IF NOT EXISTS idx_report_user ON report_history(user_id);
            CREATE INDEX IF NOT EXISTS idx_report_status ON report_history(status);
            CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);
            CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
            CREATE INDEX IF NOT EXISTS idx_org_members_user ON org_members(user_id);
            CREATE INDEX IF NOT EXISTS idx_org_members_org ON org_members(org_id);

            -- 知识库文档元信息表
            CREATE TABLE IF NOT EXISTS kb_documents (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                org_id      INTEGER,
                filename    TEXT NOT NULL,
                file_path   TEXT NOT NULL,
                file_type   TEXT DEFAULT 'unknown',
                chunk_count INTEGER DEFAULT 0,
                scope       TEXT DEFAULT 'personal',
                tags_json   TEXT DEFAULT '[]',
                report_modules_json TEXT DEFAULT '[]',
                sources_json TEXT DEFAULT '[]',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (org_id)  REFERENCES organizations(id)
            );

            -- 知识库变更日志表
            CREATE TABLE IF NOT EXISTS kb_change_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER,
                user_id     INTEGER NOT NULL,
                org_id      INTEGER,
                action      TEXT NOT NULL,
                filename    TEXT NOT NULL,
                details     TEXT DEFAULT '',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES kb_documents(id),
                FOREIGN KEY (user_id)     REFERENCES users(id),
                FOREIGN KEY (org_id)      REFERENCES organizations(id)
            );

            CREATE INDEX IF NOT EXISTS idx_kb_docs_user  ON kb_documents(user_id);
            CREATE INDEX IF NOT EXISTS idx_kb_docs_org   ON kb_documents(org_id);
            CREATE INDEX IF NOT EXISTS idx_kb_log_user   ON kb_change_log(user_id);
            CREATE INDEX IF NOT EXISTS idx_kb_log_org    ON kb_change_log(org_id);
            CREATE INDEX IF NOT EXISTS idx_kb_log_doc    ON kb_change_log(document_id);

            -- 用户 AI 配置表（已废弃，保留以兼容旧库；现由管理员在 system_ai_config 中统一管理）
            CREATE TABLE IF NOT EXISTS user_ai_config (
                user_id   INTEGER PRIMARY KEY REFERENCES users(id),
                provider  TEXT    NOT NULL DEFAULT 'deepseek',
                api_key   TEXT    NOT NULL DEFAULT '',
                base_url  TEXT    NOT NULL DEFAULT '',
                model     TEXT    NOT NULL DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- 系统级 AI 配置表（由管理员统一维护，所有 LLM 调用共用）
            CREATE TABLE IF NOT EXISTS system_ai_config (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL DEFAULT '',
                provider   TEXT    NOT NULL DEFAULT 'deepseek',
                api_key    TEXT    NOT NULL DEFAULT '',
                base_url   TEXT    NOT NULL DEFAULT '',
                model      TEXT    NOT NULL DEFAULT '',
                is_active  INTEGER NOT NULL DEFAULT 0,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used  TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id)
            );
        """)
        # 迁移：为旧 report_history 表添加新列（如果尚不存在）
        _migrate_db(conn)


def _migrate_db(conn: sqlite3.Connection):
    """数据库迁移：安全地为旧表添加新列（幂等操作）"""
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(report_history)")}

    if 'org_id' not in existing_cols:
        conn.execute("ALTER TABLE report_history ADD COLUMN org_id INTEGER REFERENCES organizations(id)")

    if 'content_snapshot' not in existing_cols:
        conn.execute("ALTER TABLE report_history ADD COLUMN content_snapshot TEXT DEFAULT ''")

    if 'version' not in existing_cols:
        conn.execute("ALTER TABLE report_history ADD COLUMN version INTEGER DEFAULT 1")

    kb_doc_cols = {row[1] for row in conn.execute("PRAGMA table_info(kb_documents)")}
    if 'tags_json' not in kb_doc_cols:
        conn.execute("ALTER TABLE kb_documents ADD COLUMN tags_json TEXT DEFAULT '[]'")
    if 'report_modules_json' not in kb_doc_cols:
        conn.execute("ALTER TABLE kb_documents ADD COLUMN report_modules_json TEXT DEFAULT '[]'")
    if 'sources_json' not in kb_doc_cols:
        conn.execute("ALTER TABLE kb_documents ADD COLUMN sources_json TEXT DEFAULT '[]'")

    # 确保索引存在（idx 操作是幂等的）
    conn.execute("CREATE INDEX IF NOT EXISTS idx_report_org ON report_history(org_id)")

    # 迁移：确保 user_ai_config 表存在（旧库兼容）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_ai_config (
            user_id   INTEGER PRIMARY KEY REFERENCES users(id),
            provider  TEXT    NOT NULL DEFAULT 'deepseek',
            api_key   TEXT    NOT NULL DEFAULT '',
            base_url  TEXT    NOT NULL DEFAULT '',
            model     TEXT    NOT NULL DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 迁移：修复旧版 system_ai_config 表结构
    # 早期版本使用 (config_id, provider, api_key, base_url, model, updated_at)，
    # 现在统一改为带 id / name / is_active / created_by / created_at / last_used 的新结构。
    sys_ai_cols = {row[1] for row in conn.execute("PRAGMA table_info(system_ai_config)")}
    if sys_ai_cols and 'is_active' not in sys_ai_cols:
        # 旧结构 → 备份数据 → 重建新表 → 回迁数据
        legacy_rows = list(conn.execute("SELECT provider, api_key, base_url, model FROM system_ai_config"))
        conn.execute("DROP TABLE system_ai_config")
        conn.execute("""
            CREATE TABLE system_ai_config (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL DEFAULT '',
                provider   TEXT    NOT NULL DEFAULT 'deepseek',
                api_key    TEXT    NOT NULL DEFAULT '',
                base_url   TEXT    NOT NULL DEFAULT '',
                model      TEXT    NOT NULL DEFAULT '',
                is_active  INTEGER NOT NULL DEFAULT 0,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used  TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """)
        # 只把首条旧记录设为启用，其余保持停用
        for idx, (provider, api_key, base_url, model) in enumerate(legacy_rows):
            conn.execute("""
                INSERT INTO system_ai_config (name, provider, api_key, base_url, model, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (f'旧版迁移配置 #{idx + 1}', provider, api_key, base_url, model, 1 if idx == 0 else 0))

    # 迁移：确保 system_ai_config 表存在（全新库兼容）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS system_ai_config (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL DEFAULT '',
            provider   TEXT    NOT NULL DEFAULT 'deepseek',
            api_key    TEXT    NOT NULL DEFAULT '',
            base_url   TEXT    NOT NULL DEFAULT '',
            model      TEXT    NOT NULL DEFAULT '',
            is_active  INTEGER NOT NULL DEFAULT 0,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used  TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_system_ai_active ON system_ai_config(is_active)")
    conn.commit()


def seed_test_accounts() -> str | None:
    """按需创建本地演示管理员，未配置密码时不创建任何账号。"""
    username = os.environ.get('SIMUREPORT_DEMO_ADMIN_USERNAME', 'demo_admin').strip()
    password = os.environ.get('SIMUREPORT_DEMO_ADMIN_PASSWORD', '')
    if not password:
        return None
    if len(password) < 8:
        raise ValueError('SIMUREPORT_DEMO_ADMIN_PASSWORD 至少需要 8 个字符')

    _accounts = [
        (username, password, 'Demo Admin', 'admin'),
    ]
    with get_db() as conn:
        for username, password, display_name, role in _accounts:
            exists = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if not exists:
                pw_hash = generate_password_hash(password)
                conn.execute(
                    "INSERT INTO users (username, password_hash, display_name, role) VALUES (?, ?, ?, ?)",
                    (username, pw_hash, display_name, role)
                )
                print(f"[seed] 已创建账号: {username}  角色: {role}")
            else:
                pass  # 已存在，跳过
    return username


# ── 用户 AI 配置 ──

def get_user_ai_config(user_id: int) -> dict:
    """获取用户 AI 配置，不存在时返回空配置"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT provider, api_key, base_url, model FROM user_ai_config WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        if row:
            return dict(row)
        return {'provider': 'deepseek', 'api_key': '', 'base_url': '', 'model': ''}


def save_user_ai_config(user_id: int, provider: str, api_key: str,
                        base_url: str = '', model: str = '') -> None:
    """保存用户 AI 配置（UPSERT）"""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO user_ai_config (user_id, provider, api_key, base_url, model, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                provider   = excluded.provider,
                api_key    = excluded.api_key,
                base_url   = excluded.base_url,
                model      = excluded.model,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, provider, api_key, base_url, model))


def seed_all_users_ai_config(default_api_key: str) -> int:
    """为所有尚未配置 API key 的用户写入默认 key，返回写入数量"""
    with get_db() as conn:
        user_ids = [row[0] for row in conn.execute("SELECT id FROM users").fetchall()]
        count = 0
        for uid in user_ids:
            exists = conn.execute(
                "SELECT api_key FROM user_ai_config WHERE user_id = ?", (uid,)
            ).fetchone()
            if not exists or not exists[0]:
                conn.execute("""
                    INSERT INTO user_ai_config (user_id, provider, api_key, base_url, model)
                    VALUES (?, 'deepseek', ?, '', '')
                    ON CONFLICT(user_id) DO UPDATE SET
                        api_key = excluded.api_key,
                        updated_at = CURRENT_TIMESTAMP
                """, (uid, default_api_key))
                count += 1
        return count


# ── 系统级 AI 配置（管理员统一管理） ──

def _mask_api_key(api_key: str) -> str:
    """脱敏显示 API 密钥：保留前 8 位与后 4 位"""
    if not api_key:
        return ''
    if len(api_key) <= 12:
        return '***'
    return api_key[:8] + '***' + api_key[-4:]


def _row_to_system_ai_config(row: sqlite3.Row, include_secret: bool = False) -> dict:
    """将 system_ai_config 行转为字典，默认脱敏 api_key"""
    data = dict(row)
    data['is_active'] = bool(data.get('is_active'))
    data['api_key_masked'] = _mask_api_key(data.get('api_key', ''))
    if not include_secret:
        data.pop('api_key', None)
    return data


def list_system_ai_configs(include_secret: bool = False) -> list:
    """列出全部系统级 AI 配置（默认脱敏 api_key，按 is_active 降序、创建时间倒序）"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, name, provider, api_key, base_url, model,
                   is_active, created_by, created_at, last_used
            FROM system_ai_config
            ORDER BY is_active DESC, datetime(created_at) DESC, id DESC
        """).fetchall()
        return [_row_to_system_ai_config(r, include_secret=include_secret) for r in rows]


def get_system_ai_config_by_id(config_id: int, include_secret: bool = False) -> dict | None:
    """按主键获取某条系统级 AI 配置"""
    with get_db() as conn:
        row = conn.execute("""
            SELECT id, name, provider, api_key, base_url, model,
                   is_active, created_by, created_at, last_used
            FROM system_ai_config
            WHERE id = ?
        """, (config_id,)).fetchone()
        if not row:
            return None
        return _row_to_system_ai_config(row, include_secret=include_secret)


def get_active_system_ai_config() -> dict | None:
    """获取当前生效的系统级 AI 配置（原始 api_key，不脱敏）"""
    with get_db() as conn:
        row = conn.execute("""
            SELECT id, name, provider, api_key, base_url, model,
                   is_active, created_by, created_at, last_used
            FROM system_ai_config
            WHERE is_active = 1
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT 1
        """).fetchone()
        if not row:
            return None
        data = dict(row)
        data['is_active'] = bool(data.get('is_active'))
        return data


def create_system_ai_config(
    name: str,
    provider: str,
    api_key: str,
    base_url: str = '',
    model: str = '',
    activate: bool = False,
    created_by: int | None = None,
) -> int:
    """创建系统级 AI 配置，返回新记录 id。activate=True 时自动设为当前生效"""
    with get_db() as conn:
        if activate:
            conn.execute("UPDATE system_ai_config SET is_active = 0 WHERE is_active = 1")
        cursor = conn.execute("""
            INSERT INTO system_ai_config (name, provider, api_key, base_url, model, is_active, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, provider, api_key, base_url, model, 1 if activate else 0, created_by))
        return cursor.lastrowid


def activate_system_ai_config(config_id: int) -> bool:
    """启用某条系统级 AI 配置，并将其它记录置为停用状态"""
    with get_db() as conn:
        exists = conn.execute(
            "SELECT id FROM system_ai_config WHERE id = ?", (config_id,)
        ).fetchone()
        if not exists:
            return False
        conn.execute("UPDATE system_ai_config SET is_active = 0 WHERE is_active = 1")
        conn.execute("UPDATE system_ai_config SET is_active = 1 WHERE id = ?", (config_id,))
        return True


def deactivate_system_ai_config(config_id: int) -> bool:
    """停用某条系统级 AI 配置（不删除记录）"""
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE system_ai_config SET is_active = 0 WHERE id = ?", (config_id,)
        )
        return cursor.rowcount > 0


def delete_system_ai_config(config_id: int) -> bool:
    """永久删除某条系统级 AI 配置（建议先停用再删除）"""
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM system_ai_config WHERE id = ?", (config_id,)
        )
        return cursor.rowcount > 0


def update_system_ai_config_last_used(config_id: int) -> None:
    """更新某条配置的最后使用时间（调用 LLM 后可选更新）"""
    with get_db() as conn:
        conn.execute(
            "UPDATE system_ai_config SET last_used = CURRENT_TIMESTAMP WHERE id = ?",
            (config_id,)
        )


def seed_default_system_ai_config(default_api_key: str,
                                  default_base_url: str = '',
                                  default_model: str = '',
                                  created_by: int | None = None) -> bool:
    """若系统级 AI 配置表为空，则写入一条默认 DeepSeek 配置并设为当前生效。
    返回 True 表示写入了新记录，False 表示表非空、已跳过。"""
    if not default_api_key:
        return False
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(1) FROM system_ai_config").fetchone()
        if row and row[0] > 0:
            return False
        conn.execute("""
            INSERT INTO system_ai_config (name, provider, api_key, base_url, model, is_active, created_by)
            VALUES (?, 'deepseek', ?, ?, ?, 1, ?)
        """, ('默认 DeepSeek 配置', default_api_key, default_base_url, default_model, created_by))
        return True


# ── 用户操作 ──

def create_user(username: str, password_hash: str, display_name: str = '') -> int:
    """创建用户，返回用户ID"""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
            (username, password_hash, display_name or username)
        )
        return cursor.lastrowid


def get_user_by_username(username: str) -> dict | None:
    """根据用户名查询用户"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    """根据ID查询用户"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def update_last_login(user_id: int):
    """更新最后登录时间"""
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.now().isoformat(), user_id)
        )


def update_user_profile(user_id: int, display_name: str) -> bool:
    """更新用户显示名称"""
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE users SET display_name = ? WHERE id = ?",
            (display_name, user_id)
        )
        return cursor.rowcount > 0


def update_user_password(user_id: int, new_password_hash: str) -> bool:
    """更新用户密码"""
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_password_hash, user_id)
        )
        return cursor.rowcount > 0


def get_user_stats(user_id: int) -> dict:
    """获取用户统计信息（报告数量、知识库文档数量等）"""
    with get_db() as conn:
        report_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM report_history WHERE user_id = ?",
            (user_id,)
        ).fetchone()['cnt']

        kb_doc_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM kb_documents WHERE user_id = ? AND scope = 'personal'",
            (user_id,)
        ).fetchone()['cnt']

        org_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM org_members WHERE user_id = ?",
            (user_id,)
        ).fetchone()['cnt']

        return {
            'report_count': report_count,
            'kb_doc_count': kb_doc_count,
            'org_count': org_count
        }


# ── 报告历史操作 ──

def create_report_record(user_id: int, title: str = '', data_package_path: str = '',
                         domain: str = '', purpose: str = '') -> int:
    """创建报告记录，返回记录ID"""
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO report_history 
               (user_id, title, data_package_path, domain, purpose) 
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, title, data_package_path, domain, purpose)
        )
        return cursor.lastrowid


def update_report_record(report_id: int, **kwargs):
    """更新报告记录"""
    allowed_fields = {'title', 'output_dir', 'slot_count', 'status', 'completed_at', 'content_snapshot', 'version'}
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
    if not updates:
        return

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [report_id]

    with get_db() as conn:
        conn.execute(
            f"UPDATE report_history SET {set_clause} WHERE id = ?",
            values
        )


def get_user_reports(user_id: int, limit: int = 50) -> list[dict]:
    """获取用户的报告历史"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM report_history 
               WHERE user_id = ? 
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]


def get_report_by_id(report_id: int) -> dict | None:
    """根据ID获取报告记录"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM report_history WHERE id = ?", (report_id,)
        ).fetchone()
        return dict(row) if row else None


def get_report_versions(user_id: int, data_package_path: str, limit: int = 20) -> list[dict]:
    """获取同一数据包的所有版本历史（按时间倒序）"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, title, version, status, created_at, completed_at,
                      LENGTH(content_snapshot) as snapshot_length
               FROM report_history
               WHERE user_id = ? AND data_package_path = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, data_package_path, limit)
        ).fetchall()
        return [dict(r) for r in rows]


def get_report_snapshot(report_id: int) -> str | None:
    """获取指定报告的 content_snapshot"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT content_snapshot FROM report_history WHERE id = ?", (report_id,)
        ).fetchone()
        return row['content_snapshot'] if row else None


def get_org_reports(org_id: int, limit: int = 50) -> list[dict]:
    """获取组织内的报告历史（组织成员共享可见）"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT rh.*, u.username, u.display_name as author_name
               FROM report_history rh
               JOIN users u ON rh.user_id = u.id
               WHERE rh.org_id = ?
               ORDER BY rh.created_at DESC LIMIT ?""",
            (org_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]


# ── 用户角色操作 ──

def update_user_role(user_id: int, role: str) -> bool:
    """更新用户角色"""
    if role not in VALID_ROLES:
        return False
    with get_db() as conn:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        return True


def list_all_users(limit: int = 200) -> list[dict]:
    """列出所有用户（管理员专用）"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, username, display_name, role, created_at, last_login
               FROM users ORDER BY created_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def list_org_users_for_admin(admin_user_id: int) -> list[dict]:
    """列出管理员管辖组织内的所有成员（admin 专用）。
    
    只返回该管理员担任 owner 或 admin 的组织中的成员，去重后返回。
    """
    with get_db() as conn:
        rows = conn.execute(
            """SELECT DISTINCT u.id, u.username, u.display_name, u.role,
                      u.created_at, u.last_login
               FROM users u
               JOIN org_members om_member ON om_member.user_id = u.id
               JOIN org_members om_admin  ON om_admin.org_id = om_member.org_id
               WHERE om_admin.user_id = ?
                 AND om_admin.role IN ('owner', 'admin')
               ORDER BY u.created_at DESC""",
            (admin_user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def is_user_in_admin_orgs(admin_user_id: int, target_user_id: int) -> bool:
    """检查 target_user 是否在 admin 管辖的任何组织中"""
    with get_db() as conn:
        row = conn.execute(
            """SELECT 1
               FROM org_members om_member
               JOIN org_members om_admin ON om_admin.org_id = om_member.org_id
               WHERE om_member.user_id = ?
                 AND om_admin.user_id  = ?
                 AND om_admin.role IN ('owner', 'admin')
               LIMIT 1""",
            (target_user_id, admin_user_id)
        ).fetchone()
        return row is not None


# ── 组织操作 ──

def create_organization(name: str, description: str, created_by: int) -> int:
    """创建组织，返回组织ID。创建者自动成为 member。"""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO organizations (name, description, created_by) VALUES (?, ?, ?)",
            (name, description, created_by)
        )
        org_id = cursor.lastrowid
        # 创建者自动成为 member
        conn.execute(
            "INSERT INTO org_members (user_id, org_id, role) VALUES (?, ?, 'member')",
            (created_by, org_id)
        )
        return org_id


def get_organization(org_id: int) -> dict | None:
    """获取组织信息"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
        return dict(row) if row else None


def list_all_organizations() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM organizations ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]


def get_user_organizations(user_id: int) -> list[dict]:
    """获取用户所属的所有组织"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT o.*, om.role as member_role
              FROM organizations o
              JOIN org_members om ON o.id = om.org_id
              WHERE om.user_id = ?
              ORDER BY o.created_at DESC""",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def update_organization(org_id: int, name: str, description: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE organizations SET name = ?, description = ? WHERE id = ?",
            (name, description, org_id)
        )
        return cursor.rowcount > 0


def list_joinable_organizations(user_id: int) -> list[dict]:
    """获取用户尚未加入的组织列表"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT o.*, (
                       SELECT COUNT(*) FROM org_members om2 WHERE om2.org_id = o.id
                   ) AS member_count
               FROM organizations o
               WHERE NOT EXISTS (
                   SELECT 1 FROM org_members om
                   WHERE om.org_id = o.id AND om.user_id = ?
               )
               ORDER BY o.created_at DESC""",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_org_members(org_id: int) -> list[dict]:
    """获取组织成员列表"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT u.id, u.username, u.display_name, u.role as system_role,
                      om.role as org_role, om.joined_at
               FROM org_members om
               JOIN users u ON om.user_id = u.id
               WHERE om.org_id = ?
               ORDER BY om.joined_at""",
            (org_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def count_org_members(org_id: int) -> int:
    """获取组织成员数量"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total FROM org_members WHERE org_id = ?",
            (org_id,)
        ).fetchone()
        return int(row['total']) if row else 0


def normalize_org_member_roles(org_id: int | None = None) -> None:
    """将组织角色统一收口为 member，兼容旧数据中的 admin/owner。"""
    with get_db() as conn:
        if org_id is None:
            conn.execute(
                "UPDATE org_members SET role = 'member' WHERE role <> 'member'"
            )
        else:
            conn.execute(
                "UPDATE org_members SET role = 'member' WHERE org_id = ? AND role <> 'member'",
                (org_id,)
            )


def count_org_admins(org_id: int) -> int:
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total FROM org_members WHERE org_id = ? AND role = 'admin'",
            (org_id,)
        ).fetchone()
        return int(row['total']) if row else 0


def is_org_admin(org_id: int, user_id: int) -> bool:
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM org_members WHERE org_id = ? AND user_id = ? AND role = 'admin'",
            (org_id, user_id)
        ).fetchone()
        return row is not None


def add_org_member(org_id: int, user_id: int, role: str = 'member') -> bool:
    """添加组织成员"""
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO org_members (user_id, org_id, role) VALUES (?, ?, ?)",
                (user_id, org_id, role)
            )
            return True
    except sqlite3.IntegrityError:
        return False


def remove_org_member(org_id: int, user_id: int) -> bool:
    """移除组织成员"""
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM org_members WHERE org_id = ? AND user_id = ?",
            (org_id, user_id)
        )
        return cursor.rowcount > 0


def is_org_member(org_id: int, user_id: int) -> bool:
    """检查用户是否为组织成员"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM org_members WHERE org_id = ? AND user_id = ?",
            (org_id, user_id)
        ).fetchone()
        return row is not None


def get_org_member_role(org_id: int, user_id: int) -> str | None:
    """获取用户在组织中的角色"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT role FROM org_members WHERE org_id = ? AND user_id = ?",
            (org_id, user_id)
        ).fetchone()
        return row['role'] if row else None


def update_org_member_role(org_id: int, user_id: int, role: str) -> bool:
    if role not in ('admin', 'member'):
        return False
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE org_members SET role = ? WHERE org_id = ? AND user_id = ?",
            (role, org_id, user_id)
        )
        return cursor.rowcount > 0


def delete_organization(org_id: int) -> bool:
    with get_db() as conn:
        doc_rows = conn.execute(
            "SELECT id FROM kb_documents WHERE org_id = ? AND scope = 'org'",
            (org_id,)
        ).fetchall()
        doc_ids = [int(row['id']) for row in doc_rows]
        if doc_ids:
            placeholders = ','.join('?' for _ in doc_ids)
            conn.execute(
                f"UPDATE kb_change_log SET document_id = NULL WHERE document_id IN ({placeholders})",
                doc_ids
            )
        conn.execute("UPDATE kb_change_log SET org_id = NULL WHERE org_id = ?", (org_id,))
        conn.execute("UPDATE report_history SET org_id = NULL WHERE org_id = ?", (org_id,))
        conn.execute("DELETE FROM kb_documents WHERE org_id = ? AND scope = 'org'", (org_id,))
        conn.execute("DELETE FROM org_members WHERE org_id = ?", (org_id,))
        cursor = conn.execute("DELETE FROM organizations WHERE id = ?", (org_id,))
        return cursor.rowcount > 0


# ── API 密钥操作（开发者用于外部平台集成） ──

def generate_api_key() -> tuple[str, str, str]:
    """生成 API 密钥，返回 (raw_key, key_hash, key_prefix)"""
    raw_key = 'sr_' + secrets.token_hex(24)  # sr_<48 hex chars>
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:11]  # "sr_" + 前8位hex
    return raw_key, key_hash, key_prefix


def create_api_key(user_id: int, name: str = '', permissions: str = 'read,write') -> tuple[int, str]:
    """创建 API 密钥，返回 (key_id, raw_key)。raw_key 仅在创建时可见。"""
    raw_key, key_hash, key_prefix = generate_api_key()
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO api_keys (user_id, key_hash, key_prefix, name, permissions)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, key_hash, key_prefix, name, permissions)
        )
        return cursor.lastrowid, raw_key


def get_user_api_keys(user_id: int) -> list[dict]:
    """获取用户的 API 密钥列表（不含 hash）"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, key_prefix, name, permissions, created_at, last_used, is_active
               FROM api_keys WHERE user_id = ? ORDER BY created_at DESC""",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def verify_api_key(raw_key: str) -> dict | None:
    """验证 API 密钥，返回关联的用户信息"""
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    with get_db() as conn:
        row = conn.execute(
            """SELECT ak.*, u.id as uid, u.username, u.role
               FROM api_keys ak
               JOIN users u ON ak.user_id = u.id
               WHERE ak.key_hash = ? AND ak.is_active = 1""",
            (key_hash,)
        ).fetchone()
        if row:
            # 更新最后使用时间
            conn.execute(
                "UPDATE api_keys SET last_used = ? WHERE id = ?",
                (datetime.now().isoformat(), row['id'])
            )
            return dict(row)
        return None


def deactivate_api_key(key_id: int, user_id: int) -> bool:
    """停用 API 密钥"""
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE api_keys SET is_active = 0 WHERE id = ? AND user_id = ?",
            (key_id, user_id)
        )
        return cursor.rowcount > 0


# ── 审计日志操作（数据安全） ──

def add_audit_log(user_id: int | None, action: str, resource_type: str = '',
                  resource_id: str = '', details: str = '', ip_address: str = ''):
    """添加审计日志"""
    with get_db() as conn:
        conn.execute(
            """INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, action, resource_type, resource_id, details, ip_address)
        )


def get_audit_logs(limit: int = 100, user_id: int | None = None,
                   action: str | None = None) -> list[dict]:
    """查询全部审计日志（管理员专用）"""
    with get_db() as conn:
        query = """SELECT al.*, u.username, u.role as user_role
                   FROM audit_logs al
                   LEFT JOIN users u ON al.user_id = u.id
                   WHERE 1=1"""
        params = []
        if user_id is not None:
            query += " AND al.user_id = ?"
            params.append(user_id)
        if action:
            query += " AND al.action = ?"
            params.append(action)
        query += " ORDER BY al.created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_audit_logs_for_admin(admin_user_id: int, limit: int = 100,
                             action: str | None = None) -> list[dict]:
    """管理员审计日志：只返回自己管辖组织内 role='user' 账号的操作记录。
    
    管理员之间互不可见，开发者行为永远不可见。
    """
    with get_db() as conn:
        query = """
            SELECT DISTINCT al.*, u.username, u.role as user_role
            FROM audit_logs al
            JOIN users u ON al.user_id = u.id
            JOIN org_members om_target ON om_target.user_id = al.user_id
            JOIN org_members om_admin  ON om_admin.org_id  = om_target.org_id
            WHERE om_admin.user_id = ?
              AND om_admin.role IN ('owner', 'admin')
              AND u.role = 'user'
        """
        params: list = [admin_user_id]
        if action:
            query += " AND al.action = ?"
            params.append(action)
        query += " ORDER BY al.created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


# ── 知识库文档 CRUD ──

def _json_dumps_list(values: list[str] | None) -> str:
    items = [str(v).strip() for v in (values or []) if str(v).strip()]
    return json.dumps(items, ensure_ascii=False)


def _json_loads_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(v).strip() for v in data if str(v).strip()]
    except Exception:
        pass
    return []


def _hydrate_kb_document(row: sqlite3.Row | dict | None) -> dict | None:
    if not row:
        return None
    doc = dict(row)
    doc['tags'] = _json_loads_list(doc.pop('tags_json', '[]'))
    doc['report_modules'] = _json_loads_list(doc.pop('report_modules_json', '[]'))
    doc['sources'] = _json_loads_list(doc.pop('sources_json', '[]'))
    return doc

def kb_add_document(user_id: int | None, org_id: int | None, filename: str,
                    file_path: str, file_type: str, chunk_count: int,
                    scope: str, tags: list[str] | None = None,
                    report_modules: list[str] | None = None,
                    sources: list[str] | None = None) -> int:
    """插入 kb_documents 记录，返回新文档 ID"""
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO kb_documents
               (user_id, org_id, filename, file_path, file_type, chunk_count, scope, tags_json, report_modules_json, sources_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id, org_id, filename, file_path, file_type, chunk_count, scope,
                _json_dumps_list(tags), _json_dumps_list(report_modules), _json_dumps_list(sources)
            )
        )
        return cursor.lastrowid


def kb_delete_document(doc_id: int) -> bool:
    """删除 kb_documents 记录"""
    with get_db() as conn:
        conn.execute("UPDATE kb_change_log SET document_id = NULL WHERE document_id = ?", (doc_id,))
        cursor = conn.execute("DELETE FROM kb_documents WHERE id = ?", (doc_id,))
        return cursor.rowcount > 0


def kb_get_document(doc_id: int) -> dict | None:
    """获取单条文档记录"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM kb_documents WHERE id = ?", (doc_id,)).fetchone()
        return _hydrate_kb_document(row)


def kb_update_document(doc_id: int, tags: list[str] | None = None,
                       report_modules: list[str] | None = None,
                       sources: list[str] | None = None) -> bool:
    """更新知识库文档元数据"""
    with get_db() as conn:
        cursor = conn.execute(
            """UPDATE kb_documents
               SET tags_json = ?, report_modules_json = ?, sources_json = ?
               WHERE id = ?""",
            (
                _json_dumps_list(tags),
                _json_dumps_list(report_modules),
                _json_dumps_list(sources),
                doc_id,
            )
        )
        return cursor.rowcount > 0


def kb_list_personal(user_id: int) -> list[dict]:
    """列出用户个人知识库文档"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM kb_documents
               WHERE user_id = ? AND scope = 'personal'
               ORDER BY created_at DESC""",
            (user_id,)
        ).fetchall()
        return [_hydrate_kb_document(r) for r in rows]


def kb_list_org(org_id: int) -> list[dict]:
    """列出组织知识库文档（含上传者信息）"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT kd.*, u.username as uploader_name, u.display_name as uploader_display
               FROM kb_documents kd
               LEFT JOIN users u ON kd.user_id = u.id
               WHERE kd.org_id = ? AND kd.scope = 'org'
               ORDER BY kd.created_at DESC""",
            (org_id,)
        ).fetchall()
        return [_hydrate_kb_document(r) for r in rows]


# ── 知识库变更日志 CRUD ──

def kb_log_change(document_id: int | None, user_id: int, org_id: int | None,
                  action: str, filename: str, details: str = "") -> None:
    """写入一条知识库变更日志"""
    with get_db() as conn:
        conn.execute(
            """INSERT INTO kb_change_log
               (document_id, user_id, org_id, action, filename, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (document_id, user_id, org_id, action, filename, details)
        )


def kb_get_personal_log(user_id: int, limit: int = 100) -> list[dict]:
    """获取用户个人 KB 变更日志（仅自己可见）"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT cl.*, u.username, u.display_name
               FROM kb_change_log cl
               LEFT JOIN users u ON cl.user_id = u.id
               WHERE cl.user_id = ? AND cl.org_id IS NULL
               ORDER BY cl.created_at DESC LIMIT ?""",
            (user_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]


def kb_get_org_log(org_id: int, limit: int = 100) -> list[dict]:
    """获取组织 KB 变更日志（该组织所有成员可见）"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT cl.*, u.username, u.display_name
               FROM kb_change_log cl
               LEFT JOIN users u ON cl.user_id = u.id
               WHERE cl.org_id = ?
               ORDER BY cl.created_at DESC LIMIT ?""",
            (org_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]
