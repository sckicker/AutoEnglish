# config.py
import os
from dotenv import load_dotenv

# 获取当前文件所在的目录
basedir = os.path.abspath(os.path.dirname(__file__))
# 构建 .env 文件的完整路径
dotenv_path = os.path.join(basedir, '.env')

# 检查 .env 文件是否存在并加载
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f".env file loaded from: {dotenv_path}")
else:
    print(".env file not found, relying on system environment variables or defaults.")

class Config:
    # --- Flask 应用核心配置 ---
    # 密匙，用于保护 Web 表单免受 CSRF 攻击等。务必从环境变量设置或改为随机值。
    # 警告：正在使用默认的 SECRET_KEY，极不安全！请务必在 .env 文件中设置 SECRET_KEY。
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-secret-key-CHANGE-ME!'
    if SECRET_KEY == 'a-very-secret-key-CHANGE-ME!':
        print("\n" + "="*60)
        print("!! 警告：正在使用默认的 SECRET_KEY，极不安全！")
        print("!! 请在项目根目录的 .env 文件中设置 SECRET_KEY，例如：")
        print("!! SECRET_KEY='一个非常复杂和随机的字符串'")
        print("="*60 + "\n")

    # 数据库 URI
    default_db_path = os.path.join(basedir, 'instance', 'nce_vocab.db')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + default_db_path
    # 禁止 SQLAlchemy 发出修改跟踪信号，可以提高性能，通常不需要开启
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 分页设置
    POSTS_PER_PAGE = int(os.environ.get('POSTS_PER_PAGE') or 10)

    # --- 用户权限/角色相关配置 ---
    # 指定管理员用户名，从环境变量读取，默认为 'root'
    ADMIN_USERNAMES = os.environ.get('ADMIN_USERNAMES') or 'root'
    ROOT_ADMIN_USERNAME = os.environ.get('ROOT_ADMIN_USERNAME') or 'root' # 根管理员用户名，可能与 ADMIN_USERNAMES 区分
    print(f"Configured ADMIN_USERNAMES: {ADMIN_USERNAMES}")
    print(f"Configured ROOT_ADMIN_USERNAME: {ROOT_ADMIN_USERNAME}")


    # --- TTS 相关配置 (使用 Tacotron 2) ---
    # TTS 模型路径，从环境变量读取，默认为 Tacotron 2 DDC 模型
    TTS_MODEL = os.environ.get('TTS_MODEL') or "tts_models/en/ljspeech/tacotron2-DDC"
    # 是否尝试使用 CUDA 进行 TTS 推理，从环境变量读取布尔值
    TTS_USE_CUDA = os.environ.get('TTS_USE_CUDA', 'false').lower() == 'true'
    # TTS 音频缓存目录，相对于 instance 文件夹
    TTS_AUDIO_CACHE_DIR = 'tts_cache'
    print(f"Using TTS Model: {TTS_MODEL}")
    print(f"Attempt to use CUDA: {TTS_USE_CUDA}")
    print(f"TTS Audio Cache Directory (relative to instance path): {TTS_AUDIO_CACHE_DIR}")
    # --- 结束 TTS 配置 ---

    # --- 修改：预生成课程音频配置 ---
    # 指向 instance 文件夹下的 tts_cache 子目录
    PREGENERATED_AUDIO_FOLDER = os.environ.get('PREGENERATED_AUDIO_FOLDER') or os.path.join(basedir, 'instance',
                                                                                            'tts_cache')
    # 音频文件的命名模板 (保持不变或根据实际情况调整)
    PREGENERATED_AUDIO_FILENAME_TEMPLATE = os.environ.get(
        'PREGENERATED_AUDIO_FILENAME_TEMPLATE') or 'lesson_{lesson_number}.{ext}'
    # 尝试查找的音频文件扩展名列表 (确认你的文件都是 .wav)
    PREGENERATED_AUDIO_EXTENSIONS = ['.wav']  # 如果确定只有 wav，就只留这个
    # ----------------------------------
    # --- 新增：用户录音保存文件夹 ---
    # 放在 instance 文件夹下比较合适，因为它属于运行时生成的数据，且不应提交到 Git
    USER_RECORDINGS_FOLDER = os.environ.get('USER_RECORDINGS_FOLDER') or os.path.join(basedir, 'instance', 'user_recordings')

    # --- PDF 路径配置 ---
    # NCE 课程 PDF 文件的路径，从环境变量读取，提供默认路径
    default_pdf_path = os.path.join(basedir, 'uploads', 'nce_book2.pdf') # 检查此路径是否存在
    NCE_PDF_PATH = os.environ.get('NCE_PDF_PATH') or default_pdf_path
    print(f"Configured NCE_PDF_PATH: {NCE_PDF_PATH}")

    # --- Flask-Mail 配置 ---
    MAIL_SERVER = os.environ.get('MAIL_SERVER')  # 例如 'smtp.googlemail.com' 或 'smtp.163.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)  # TLS 通常用 587, SSL 用 465
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']  # 推荐使用 TLS
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ['true', 'on', '1']  # 通常 TLS 和 SSL 只启用一个
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')  # 你的邮箱账号
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')  # 你的邮箱密码或应用专用密码
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or MAIL_USERNAME  # 默认发件人邮箱地址
    ADMINS = [os.environ.get('ADMIN_EMAIL')] if os.environ.get('ADMIN_EMAIL') else [
        'your_admin_email@example.com']  # 用于接收错误报告等 (可选)
    # -----------------------

    # 在应用启动时检查邮件配置是否完整 (可选，但推荐)
    # if MAIL_SERVER is None or MAIL_USERNAME is None or MAIL_PASSWORD is None:
    #     print("\n" + "="*60)
    #     print("!! 警告：邮件发送配置不完整！")
    #     print("!! 请在 .env 文件中设置 MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD 等配置。")
    #     print("="*60 + "\n")

    # --- 结束邮件发送配置 ---