# app/__init__.py

from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
import os
import logging
from logging.handlers import RotatingFileHandler
import sys # Import sys for potential console encoding checks/fixes
import secrets

secret_key = secrets.token_hex(32)  # 生成一个 64 字符的十六进制密钥（256 位）
print(secret_key)
db = SQLAlchemy()

def create_app(config_class=Config):
    """Application Factory Pattern"""
    app = Flask(__name__, instance_relative_config=True)
    app.secret_key = secret_key
    app.config.from_object(config_class)

    # --- Logging Setup Start ---
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        log_dir = os.path.join(app.instance_path, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        print(f"Instance path: {app.instance_path}")
        print(f"Log directory: {log_dir}")
    except OSError as e:
        # Use basic print here as logger might not be fully ready
        print(f"ERROR: Error creating instance or log directory: {e}")

    # Define formatter early to reuse it
    log_formatter = logging.Formatter(
         '%(asctime)s - %(name)s - %(levelname)s - %(message)s [in %(pathname)s:%(lineno)d]'
    )

    if not app.debug and not app.testing: # Production logging
        # --- File Handler (Production) ---
        log_file = os.path.join(log_dir, 'app.log')
        # Rotate logs: 5 files, 5MB each, **ADD encoding='utf-8'**
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=1024*1024*5,
            backupCount=5,
            encoding='utf-8' # <-- Explicitly set UTF-8 encoding for the log file
        )
        file_handler.setFormatter(log_formatter)
        file_handler.setLevel(logging.DEBUG) # Production file logs at INFO level
        app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.DEBUG) # Overall logger level for production
        app.logger.info('App startup - Production Logging Enabled (File: app.log, Encoding: UTF-8).')

    else: # Development/Debug mode logging
        # Set overall app logger level to DEBUG first
        app.logger.setLevel(logging.DEBUG)

        # --- Console Handler (Debug) ---
        # Flask's default debug handler *should* respect UTF-8 in modern terminals/PyCharm console.
        # If console output is still garbled, ensure your terminal/PyCharm console itself is set to UTF-8.
        # You can also try setting the PYTHONIOENCODING environment variable:
        # On Linux/macOS: export PYTHONIOENCODING=utf-8 && python run.py
        # On Windows (cmd): set PYTHONIOENCODING=utf-8 && python run.py
        # On Windows (PowerShell): $env:PYTHONIOENCODING = "utf-8"; python run.py
        # Or configure it in PyCharm's Run/Debug configuration environment variables.

        # --- File Handler (Debug) ---
        debug_log_file = os.path.join(log_dir, 'debug.log')
         # Rotate logs: 3 files, 10MB each, **ADD encoding='utf-8'**
        debug_file_handler = RotatingFileHandler(
            debug_log_file,
            maxBytes=1024*1024*10,
            backupCount=3,
            encoding='utf-8' # <-- Explicitly set UTF-8 encoding for the debug log file
        )
        debug_file_handler.setFormatter(log_formatter)
        debug_file_handler.setLevel(logging.DEBUG) # Capture all DEBUG messages in the file
        app.logger.addHandler(debug_file_handler)

        app.logger.info('App startup - Debug Logging Enabled (Console + File: debug.log, Encoding: UTF-8).')

    # --- Logging Setup End ---

    # Initialize Flask extensions here
    db.init_app(app)

    # Register blueprints etc.
    with app.app_context():
        from . import routes
        from . import models

        try:
            db.create_all()
            app.logger.info("Database tables checked/created.")
        except Exception as e:
            app.logger.error(f"Error creating database tables: {e}", exc_info=True)

    app.logger.info("Flask app created successfully.")
    return app