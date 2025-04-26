# app/__init__.py - Refined Version

import os
import logging
from logging.handlers import RotatingFileHandler
import sys # sys is imported but not used, consider removing if not needed elsewhere
from flask import Flask, current_app # Import current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from datetime import datetime # Import datetime

from config import Config # Import your Config class

# --- Instantiate extensions ---
# Define extension instances at the module level so they can be imported elsewhere if needed
db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
csrf = CSRFProtect()

# --- Configure Flask-Login settings ---
login.login_view = 'login' # The endpoint name of your login view function (in routes.py)
login.login_message = '请先登录以访问此页面。(Please log in to access this page.)'
login.login_message_category = 'info' # Bootstrap alert class (info, warning, danger, success)

# --- Flask-Login User Loader ---
# This MUST be defined after 'login' is instantiated but can be before create_app
# It needs access to the User model, which will be imported later
# We define it here, and the necessary import happens within create_app context later
@login.user_loader
def load_user(id):
    """Callback function required by Flask-Login to load a user by ID from the session."""
    # Import User model here, inside the function, or ensure it's available globally after models are imported
    # Importing here avoids potential circular import issues if models import 'login'
    from .models import User
    try:
        user_id = int(id) # Ensure ID is an integer
        user = User.query.get(user_id)
        if not user:
            # Use logger, but need app context. Logged within request context anyway.
            # Use print for now if logger is tricky outside request context, or just return None
            print(f"WARNING: User ID {user_id} not found in user_loader.") # Logger might not work reliably here yet
        return user
    except ValueError:
        print(f"ERROR: Invalid non-integer user ID passed to user_loader: {id}") # Logger might not work reliably here yet
        return None
    except Exception as e:
        # Use current_app context if available, otherwise print as fallback
        try:
            current_app.logger.error(f"Error loading user {id} in user_loader: {e}", exc_info=True)
        except RuntimeError: # If called outside application context
             print(f"ERROR: Error loading user {id} in user_loader (no app context): {e}")
        return None

# --- Application Factory Function ---
def create_app(config_class=Config):
    """Creates and configures the Flask application instance using the factory pattern."""
    app = Flask(__name__, instance_relative_config=True) # Enable instance folder config

    # Load configuration from the specified config object
    app.config.from_object(config_class)
    app.logger.info(f"App configured using {config_class.__name__}")

    # --- Critical Configuration Checks ---
    secret_key = app.config.get('SECRET_KEY')
    insecure_default = 'a-very-secret-key-CHANGE-ME!' # Match the default in config.py
    if not secret_key or secret_key == insecure_default:
        app.logger.critical("FATAL: SECRET_KEY is not set or is using the insecure default value!")
        # Optionally raise an error in production environments to halt startup
        if not app.debug and not app.testing:
             raise ValueError("Insecure or missing SECRET_KEY in production environment.")
        else:
             app.logger.warning("Using default/insecure SECRET_KEY in debug/testing mode.")
    # ------------------------------------

    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError as e:
        app.logger.error(f"Could not create instance folder at {app.instance_path}: {e}")

    # --- 新增：确保用户录音文件夹存在 ---
    try:
        recordings_folder = app.config['USER_RECORDINGS_FOLDER']
        os.makedirs(recordings_folder, exist_ok=True)
        app.logger.info(f"User recordings folder checked/created: {recordings_folder}")
    except OSError as e:
        app.logger.error(f"Could not create user recordings folder '{app.config.get('USER_RECORDINGS_FOLDER')}': {e}")

    # --- Initialize Flask extensions with the 'app' instance ---
    db.init_app(app)
    migrate.init_app(app, db) # Migrate needs both app and db
    login.init_app(app)       # Initialize Flask-Login
    csrf.init_app(app)        # Initialize CSRF protection
    # ---------------------------------------------------------

    # --- Configure Logging ---
    log_dir = os.path.join(app.instance_path, 'logs')
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_formatter = logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        )

        if app.debug or app.testing:
            # Development/Testing: Log DEBUG level to console (Flask default usually handles this)
            app.logger.setLevel(logging.DEBUG)
            app.logger.info('Flask App Startup - Debug/Testing Mode - Logging primarily to console.')
            # Add console handler explicitly if Flask's default isn't sufficient
            # console_handler = logging.StreamHandler(sys.stdout)
            # console_handler.setFormatter(log_formatter)
            # app.logger.addHandler(console_handler)
        else:
            # Production: Log INFO level to a rotating file
            app.logger.setLevel(logging.INFO)
            log_file = os.path.join(log_dir, 'app.log')
            file_handler = RotatingFileHandler(
                log_file, maxBytes=1024*1024*5, backupCount=10, encoding='utf-8'
            )
            file_handler.setFormatter(log_formatter)
            file_handler.setLevel(logging.INFO)

            # Use Flask's built-in logger; remove default handlers if necessary before adding ours
            # For simplicity, we'll just add ours. If duplicate logs appear, investigate app.logger.handlers.
            app.logger.addHandler(file_handler)
            app.logger.info('Flask App Startup - Production Mode - Logging to app.log.')

    except Exception as log_setup_error:
         app.logger.error(f"Failed to configure logging: {log_setup_error}", exc_info=True)
    # ------------------------

    # --- Context Processors (Inject variables into all templates) ---
    @app.context_processor
    def inject_current_time():
        """Make current UTC time available to all templates via 'current_time'."""
        return {'current_time': datetime.utcnow()}
    # -------------------------------------------------------------

    # --- Import Blueprints, Models, Routes within App Context ---
    # Using 'with app.app_context()' ensures extensions can be accessed during import
    with app.app_context():
        # Import models first - crucial for relationships, migrations, user_loader
        from . import models
        app.logger.debug("Models imported.")

        # Import routes (defines view functions)
        from . import routes
        app.logger.debug("Routes imported.")

        # Import and register CLI commands if defined in run.py or commands.py
        # This part might be better placed in run.py where 'app' is directly available
        # Example (assuming commands are defined in run.py using @app.cli):
        # from run import * # Or wherever your commands are defined relative to app creation

        # --- Database Initialization (Development/Testing Only) ---
        # REMOVE or comment out db.create_all() for production! Use Migrations.
        if app.config.get('SQLALCHEMY_DATABASE_URI', '').startswith('sqlite'):
             try:
                 # Check if DB file exists only makes sense for SQLite potentially
                 db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
                 # if not os.path.exists(db_path): # Create only if DB file doesn't exist
                 db.create_all() # create_all is safe; only creates non-existent tables
                 app.logger.info("db.create_all() checked/created tables (use 'flask db upgrade' for production/migrations).")
             except Exception as e:
                 app.logger.error(f"Error during db.create_all(): {e}", exc_info=True)
        # ----------------------------------------------------------

    app.logger.info("Flask app instance initialization complete.")
    return app