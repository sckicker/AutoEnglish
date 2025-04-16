# app/__init__.py - Updated for Auth and Extensions

import os
import logging
from logging.handlers import RotatingFileHandler
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate # 新增
from flask_login import LoginManager # 新增
from flask_wtf.csrf import CSRFProtect # 新增

from config import Config # 从 config.py 导入配置

# --- 实例化扩展 ---
db = SQLAlchemy()
migrate = Migrate() # 用于数据库迁移
login = LoginManager() # 用于用户登录管理
# 配置 Flask-Login:
# 'login' 是指处理登录的路由函数(endpoint)的名称 (在 routes.py 中定义)
login.login_view = 'login'
# 当未登录用户访问需要登录的页面时，显示的 flash 消息
login.login_message = '请先登录以访问此页面。(Please log in to access this page.)'
# flash 消息的类别 (通常用于 Bootstrap 的 alert 样式)
login.login_message_category = 'info'

csrf = CSRFProtect() # 用于 CSRF 保护

# --- 应用工厂函数 ---
def create_app(config_class=Config):
    """Application Factory Pattern"""
    app = Flask(__name__, instance_relative_config=True)
    # --- 从配置对象加载配置 (包括 SECRET_KEY) ---
    app.config.from_object(config_class)
    # 确保 SECRET_KEY 已在 config.py 或环境变量中设置！
    if not app.config.get('SECRET_KEY'):
        raise ValueError("No SECRET_KEY set for Flask application")


    # --- 初始化 Flask 扩展 ---
    db.init_app(app)
    migrate.init_app(app, db) # 关联 app 和 db
    login.init_app(app)       # 关联 app
    csrf.init_app(app)        # 关联 app


    # --- 日志设置 (调整级别和 Debug 模式处理) ---
    try:
        # Ensure instance path exists for log files etc.
        instance_path = app.instance_path
        log_dir = os.path.join(instance_path, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        # print(f"Instance path: {instance_path}") # Print 语句在生产中可能不适用
        # print(f"Log directory: {log_dir}")
    except OSError as e:
        app.logger.error(f"Error creating instance or log directory: {e}")

    log_formatter = logging.Formatter(
         '%(asctime)s - %(name)s - %(levelname)s - %(message)s [in %(pathname)s:%(lineno)d]'
    )

    if not app.debug and not app.testing:
        # --- 生产环境日志配置 (非 Debug 模式) ---
        app.logger.setLevel(logging.INFO) # ** 设置为 INFO **

        log_file = os.path.join(log_dir, 'app.log')
        file_handler = RotatingFileHandler(
            log_file, maxBytes=1024*1024*5, backupCount=5, encoding='utf-8'
        )
        file_handler.setFormatter(log_formatter)
        file_handler.setLevel(logging.INFO) # ** 文件也设为 INFO **

        # 只添加我们自己的文件处理器 (如果 Flask 默认有其他处理器，它们可能仍然工作)
        # 如果想完全控制，需要先清空 app.logger.handlers
        if not app.logger.handlers: # 避免重复添加（虽然 Flask 可能自己处理）
             app.logger.addHandler(file_handler)
        else:
             # 如果已有 handler, 可以选择替换或只添加我们的
             # 为安全起见，这里只添加，但生产中可能需要更精细控制
             app.logger.addHandler(file_handler)


        app.logger.info('Flask App Startup - Production Logging Enabled (INFO level to app.log).')

    else:
        # --- 开发环境日志配置 (Debug 模式) ---
        app.logger.setLevel(logging.DEBUG) # ** Debug 模式下级别设为 DEBUG **
        # 通常 Flask 开发服务器会配置一个 StreamHandler 输出到控制台
        # 我们不再添加 RotatingFileHandler 来避免文件锁问题
        app.logger.info('Flask App Startup - Debug Logging Enabled (DEBUG level, primarily to console).')
        # 如果需要 debug 文件日志，可取消下面的注释 (使用 FileHandler)
        # try:
        #     debug_log_file = os.path.join(log_dir, 'debug_dev.log')
        #     debug_file_handler = logging.FileHandler(debug_log_file, mode='a', encoding='utf-8')
        #     debug_file_handler.setFormatter(log_formatter)
        #     debug_file_handler.setLevel(logging.DEBUG)
        #     app.logger.addHandler(debug_file_handler)
        #     app.logger.info('Debug file logging also enabled (debug_dev.log).')
        # except Exception as log_ex:
        #      app.logger.error(f"Failed to setup debug file logging: {log_ex}")


    # --- 注册 Blueprint 或导入路由/模型 ---
    with app.app_context():
        # 导入模型非常重要，特别是 User 模型，因为 user_loader 需要它
        from . import models
        # 导入路由定义
        from . import routes

        # --- 数据库创建/迁移 ---
        # 对于开发，db.create_all() 可以快速创建表
        # !!! 警告: 这不会处理后续模型的更改 !!!
        # !!! 生产环境或需要管理模型变更时，请使用 Flask-Migrate !!!
        # flask db init (仅一次)
        # flask db migrate -m "Some description"
        # flask db upgrade
        try:
            # 可以暂时保留 create_all 用于快速启动开发
            db.create_all()
            app.logger.info("Database tables checked/created via db.create_all(). REMINDER: Use Flask-Migrate for production/updates.")
        except Exception as e:
            app.logger.error(f"Error during db.create_all(): {e}", exc_info=True)

    app.logger.info("Flask app instance created and configured successfully.")
    return app

# --- Flask-Login user_loader 回调函数 ---
# 这个函数必须在全局作用域或者可以通过 login manager 找到的地方定义
# 它告诉 Flask-Login 如何根据存储在 session 中的用户 ID 找到对应的用户对象
from .models import User # 确保 User 模型已导入
@login.user_loader
def load_user(id):
    """Flask-Login required callback to load a user by ID."""
    try:
        return User.query.get(int(id))
    except Exception as e:
        current_app.logger.error(f"Error loading user {id}: {e}", exc_info=True)
        return None