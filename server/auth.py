"""JWT 认证模块

提供用户注册、登录、token 生成与验证功能。
支持 JWT token 和 API Key 两种认证方式。
包含基于角色的访问控制（RBAC）和审计日志记录。

角色体系：
  - user:      普通用户
  - admin:     管理员（管理组织、查看审计日志、API Key 管理）
"""

import os
import jwt
import functools
from datetime import datetime, timedelta, timezone
from flask import request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash

from config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_HOURS
from database import (
    create_user, get_user_by_username, get_user_by_id, update_last_login,
    verify_api_key, add_audit_log
)


def generate_token(user_id: int, username: str) -> str:
    """生成 JWT token"""
    payload = {
        'user_id': user_id,
        'username': username,
        'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
        'iat': datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """解码 JWT token，失败返回 None"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def _authenticate_request():
    """内部函数：从请求中解析用户身份（支持 JWT token 和 API Key）
    
    Returns:
        (user_dict, error_msg, status_code)
    """
    auth_header = request.headers.get('Authorization', '')

    # 方式1：Bearer JWT token
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        payload = decode_token(token)
        if not payload:
            return None, '令牌无效或已过期', 401
        user = get_user_by_id(payload['user_id'])
        if not user:
            return None, '用户不存在', 401
        return user, None, 200

    # 方式2：API Key（外部平台集成）
    if auth_header.startswith('ApiKey '):
        raw_key = auth_header[7:]
        key_info = verify_api_key(raw_key)
        if not key_info:
            return None, 'API Key 无效或已停用', 401
        user = get_user_by_id(key_info['user_id'])
        if not user:
            return None, '关联用户不存在', 401
        return user, None, 200

    return None, '未提供认证令牌', 401


def login_required(f):
    """认证装饰器 —— 保护需要登录的 API（支持 JWT + API Key）"""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user, error, status = _authenticate_request()
        if error:
            return jsonify({'success': False, 'error': error}), status
        g.current_user = user
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """管理员权限装饰器（仅 admin 可访问）"""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user, error, status = _authenticate_request()
        if error:
            return jsonify({'success': False, 'error': error}), status
        if user['role'] != 'admin':
            return jsonify({'success': False, 'error': '需要管理员权限'}), 403
        g.current_user = user
        return f(*args, **kwargs)
    return decorated


def audit(action: str, resource_type: str = '', resource_id: str = '', details: str = ''):
    """记录审计日志（在请求上下文中调用）"""
    user_id = getattr(g, 'current_user', {}).get('id')
    ip = request.remote_addr or ''
    add_audit_log(user_id, action, resource_type, resource_id, details, ip)


def register_user(username: str, password: str, display_name: str = '') -> tuple[dict, int]:
    """注册新用户
    
    Returns:
        (response_dict, status_code)
    """
    # 验证输入
    if not username or len(username) < 3:
        return {'success': False, 'error': '用户名至少3个字符'}, 400
    if not password or len(password) < 6:
        return {'success': False, 'error': '密码至少6个字符'}, 400

    # 检查用户名是否已存在
    if get_user_by_username(username):
        return {'success': False, 'error': '用户名已存在'}, 409

    # 创建用户
    password_hash = generate_password_hash(password)
    user_id = create_user(username, password_hash, display_name)

    # 审计日志
    add_audit_log(user_id, 'user_register', 'user', str(user_id), f'新用户注册: {username}')

    # 生成 token
    token = generate_token(user_id, username)

    return {
        'success': True,
        'message': '注册成功',
        'token': token,
        'user': {
            'id': user_id,
            'username': username,
            'display_name': display_name or username,
            'role': 'user'
        }
    }, 201


def login_user(username: str, password: str) -> tuple[dict, int]:
    """用户登录
    
    Returns:
        (response_dict, status_code)
    """
    if not username or not password:
        return {'success': False, 'error': '请输入用户名和密码'}, 400

    user = get_user_by_username(username)
    if not user:
        return {'success': False, 'error': '用户名或密码错误'}, 401

    if not check_password_hash(user['password_hash'], password):
        return {'success': False, 'error': '用户名或密码错误'}, 401

    # 更新最后登录时间
    update_last_login(user['id'])

    # 生成 token
    token = generate_token(user['id'], user['username'])

    # 审计日志
    add_audit_log(user['id'], 'user_login', 'user', str(user['id']), f'用户登录: {username}')

    return {
        'success': True,
        'message': '登录成功',
        'token': token,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'display_name': user['display_name'],
            'role': user['role']
        }
    }, 200
