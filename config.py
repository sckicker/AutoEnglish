# config.py
import os
from dotenv import load_dotenv

# Calculate absolute path for the project directory
basedir = os.path.abspath(os.path.dirname(__file__))

# Load environment variables from .env file, if it exists
dotenv_path = os.path.join(basedir, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f"INFO: .env file loaded from: {dotenv_path}")
else:
    print("INFO: .env file not found. Relying on system environment variables or defaults.")

class Config:
    """
    Flask application configuration class.
    Prioritizes environment variables, falling back to defaults.
    """
    # --- Admin Usernames Configuration ---
    # Usernames listed here will have their is_admin flag set to True
    # in the database when the 'flask sync-admins' command is run.
    # Use a comma-separated string (suitable for environment variables).
    ADMIN_USERNAMES = os.environ.get('ADMIN_USERNAMES') or 'root'
    # Example: ADMIN_USERNAMES='root,another_admin,testuser'
    # ------------------------------------

    # --- Secret Key (Essential for Security) ---
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        SECRET_KEY = 'a-very-insecure-default-key-CHANGE-THIS-IMMEDIATELY!'
        print("CRITICAL WARNING: Using default SECRET_KEY! Set a strong SECRET_KEY in .env or environment variables.")
        # Consider raising an error in production if SECRET_KEY is not set:
        # raise ValueError("No SECRET_KEY set for Flask application")

    # --- Database Configuration ---
    default_db_path = os.path.join(basedir, 'instance', 'nce_vocab.db')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + default_db_path
    SQLALCHEMY_TRACK_MODIFICATIONS = False # Recommended to disable

    # --- PDF File Path ---
    # Default location: project_root/data/nce_book2.pdf
    default_pdf_path = os.path.join(basedir, 'data', 'nce_book2.pdf')
    NCE_PDF_PATH = os.environ.get('NCE_PDF_PATH') or default_pdf_path

    # --- Other Configurations ---
    POSTS_PER_PAGE = int(os.environ.get('POSTS_PER_PAGE') or 10)
    ROOT_ADMIN_USERNAME = os.environ.get('ROOT_ADMIN_USERNAME') or 'root' # Can be used for super-admin checks

    # Print key config values for verification during startup
    print(f"INFO: Using database -> {SQLALCHEMY_DATABASE_URI}")
    print(f"INFO: Using NCE PDF Path -> {NCE_PDF_PATH}")
    print(f"INFO: Configured ADMIN_USERNAMES -> {ADMIN_USERNAMES}")

# You can add other config classes here (DevelopmentConfig, ProductionConfig, etc.) if needed