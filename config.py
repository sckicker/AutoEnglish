import os

# Find the base directory of the project
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-secret-key' # Change this!
    # Define the path for the SQLite database within the 'instance' folder
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'nce_vocab.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Optional: Configure upload folder
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    ALLOWED_EXTENSIONS = {'pdf'}