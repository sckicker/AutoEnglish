# config.py
import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
dotenv_path = os.path.join(basedir, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f".env file loaded from: {dotenv_path}")
else:
    print(".env file not found, relying on system environment variables or defaults.")

class Config:
    # --- 指定管理员用户名 ---
    ADMIN_USERNAMES = os.environ.get('ADMIN_USERNAMES') or 'root'
    print(f"Configured ADMIN_USERNAMES: {ADMIN_USERNAMES}")

    # --- TTS 相关配置 (使用 Tacotron 2) ---
    TTS_MODEL = os.environ.get('TTS_MODEL') or "tts_models/en/ljspeech/tacotron2-DDC"
    TTS_USE_CUDA = os.environ.get('TTS_USE_CUDA', 'false').lower() == 'true'
    TTS_AUDIO_CACHE_DIR = 'tts_cache' # 相对于 instance 文件夹
    print(f"Using TTS Model: {TTS_MODEL}")
    print(f"Attempt to use CUDA: {TTS_USE_CUDA}")
    print(f"TTS Audio Cache Directory (relative to instance path): {TTS_AUDIO_CACHE_DIR}")
    # --- 结束 TTS 配置 ---

    # --- 其他配置 ---
    ROOT_ADMIN_USERNAME = os.environ.get('ROOT_ADMIN_USERNAME') or 'root'
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-secret-key-CHANGE-ME!'
    default_db_path = os.path.join(basedir, 'instance', 'nce_vocab.db')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + default_db_path
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    default_pdf_path = os.path.join(basedir, 'uploads', 'nce_book2.pdf') # 检查此路径
    NCE_PDF_PATH = os.environ.get('NCE_PDF_PATH') or default_pdf_path
    POSTS_PER_PAGE = int(os.environ.get('POSTS_PER_PAGE') or 10)

    if SECRET_KEY == 'a-very-secret-key-CHANGE-ME!':
        print("警告：正在使用默认的 SECRET_KEY，极不安全！")