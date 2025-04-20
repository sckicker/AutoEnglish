# app/decorators.py
from functools import wraps
from flask import abort, current_app
from flask_login import current_user

def admin_required(f):
    """Decorator to ensure user is logged in and is an admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            # 如果需要，可以重定向到登录页而不是直接 403
            # from flask import redirect, url_for
            # return redirect(url_for('login', next=request.url))
            abort(403)
        if not current_user.is_admin: # 检查数据库中的 is_admin 标志
            abort(403) # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def root_admin_required(f):
    """Decorator to ensure user is logged in, is an admin, AND matches the ROOT_ADMIN_USERNAME."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        root_username = current_app.config.get('ROOT_ADMIN_USERNAME', 'root') # 从配置获取根用户名

        # --- 修改这里的判断逻辑 ---
        is_root = (current_user.is_authenticated and
                   current_user.is_admin and # 确保也是普通管理员
                   current_user.username == root_username) # 检查用户名是否匹配

        if not is_root:
            current_app.logger.warning(f"Access denied for user '{current_user.username}' to root admin required route. User is_admin={current_user.is_admin}, Required username='{root_username}'")
            abort(403) # Forbidden
        # -------------------------
        return f(*args, **kwargs)
    return decorated_function