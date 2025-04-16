# app/decorators.py
from functools import wraps
from flask import abort, current_app
from flask_login import current_user

def admin_required(f):
    """检查用户是否登录且拥有管理员权限 (根或普通)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            # 使用 Flask-Login 的未授权处理（通常重定向到登录页）
            return current_app.login_manager.unauthorized()
        if not current_user.has_admin_privileges:
            abort(403) # Forbidden - 禁止访问
        return f(*args, **kwargs)
    return decorated_function

def root_admin_required(f):
    """检查用户是否登录且是根管理员"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if not current_user.is_root:
            abort(403) # Forbidden
        return f(*args, **kwargs)
    return decorated_function