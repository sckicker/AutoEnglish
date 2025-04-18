# app/__init__.py

import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, current_app # Import current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from datetime import datetime # Import datetime

from config import Config # Import your Config class

# Instantiate extensions (globally accessible within the app package)
db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
csrf = CSRFProtect()

# Configure Flask-Login settings
login.login_view = 'login' # The endpoint name of your login route
login.login_message = '请先登录以访问此页面。(Please log in to access this page.)'
login.login_message_category = 'info' # Bootstrap alert class

# --- Application Factory ---
def create_app(config_class=Config):
    """Creates and configures the Flask application instance."""
    app = Flask(__name__, instance_relative_config=True)

    # Load configuration from the specified class
    app.config.from_object(config_class)

    # Ensure SECRET_KEY is set (critical check)
    if not app.config.get('SECRET_KEY') or \
       app.config['SECRET_KEY'] == 'a-very-insecure-default-key-CHANGE-THIS-IMMEDIATELY!':
        app.logger.critical("FATAL: SECRET_KEY is not set or is using the insecure default!")
        # Optionally raise an error to prevent startup in production
        # raise ValueError("SECRET_KEY not set or is insecure.")

    # Ensure instance folder exists (for SQLite DB, logs, etc.)
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError as e:
        app.logger.error(f"Could not create instance folder at {app.instance_path}: {e}")

    # Initialize extensions with the app instance
    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    csrf.init_app(app)

    # --- Configure Logging ---
    log_dir = os.path.join(app.instance_path, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    )

    if app.debug or app.testing:
        # Development/Testing Logging (Console primarily)
        app.logger.setLevel(logging.DEBUG)
        # Flask's default handler usually logs to console in debug mode
        app.logger.info('Flask App Startup - Debug/Testing Mode - Logging to console.')
    else:
        # Production Logging (File-based)
        app.logger.setLevel(logging.INFO)
        log_file = os.path.join(log_dir, 'app.log')
        file_handler = RotatingFileHandler(
            log_file, maxBytes=1024*1024*5, backupCount=10, encoding='utf-8'
        )
        file_handler.setFormatter(log_formatter)
        file_handler.setLevel(logging.INFO)

        # Clear existing handlers and add our file handler
        app.logger.handlers.clear()
        app.logger.addHandler(file_handler)
        app.logger.info('Flask App Startup - Production Mode - Logging to app.log.')

    # --- Context Processors and Global Template Variables ---
    @app.context_processor
    def inject_current_time():
        """Make current UTC time available to all templates."""
        return {'current_time': datetime.utcnow()}

    # --- Import Blueprints, Models, Routes ---
    with app.app_context():
        # Import models here is crucial for Flask-Migrate and Flask-Login
        from . import models # Loads model definitions
        # Import routes (which define view functions and endpoints)
        from . import routes # Loads route definitions
        # Import CLI commands if defined in a separate file/blueprint
        # from . import commands # Example if commands were in app/commands.py

        # Optional: Initial DB creation check for development ease
        # Note: Use Flask-Migrate ('flask db upgrade') for production/schema changes
        try:
            # Check if DB file exists before calling create_all, maybe?
            # Or just let create_all be idempotent
            # db.create_all() # This only creates tables if they don't exist
            # app.logger.debug("db.create_all() checked for table existence.")
            pass # Rely on 'flask db upgrade' workflow
        except Exception as e:
            app.logger.error(f"Error during initial db setup check: {e}", exc_info=True)

    app.logger.info("Flask app instance created successfully.")
    return app

# --- Flask-Login User Loader ---
# This MUST be defined at the module level or imported where login manager can find it
from .models import User # Import User model again for the loader

@login.user_loader
def load_user(id):
    """Callback function required by Flask-Login to load a user by ID."""
    try:
        user_id = int(id)
        user = User.query.get(user_id)
        if not user:
            current_app.logger.warning(f"User ID {user_id} not found in user_loader.")
        return user
    except ValueError:
        current_app.logger.error(f"Invalid non-integer user ID passed to user_loader: {id}")
        return None
    except Exception as e:
        # Use current_app.logger here as 'app' isn't in scope
        current_app.logger.error(f"Error loading user {id} in user_loader: {e}", exc_info=True)
        return None