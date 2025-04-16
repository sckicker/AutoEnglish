# config.py
import os
from dotenv import load_dotenv # 导入 python-dotenv

# 计算项目根目录的绝对路径
# __file__ 是 config.py 的路径
# os.path.dirname(__file__) 是 config.py 所在的目录
# 如果 config.py 在项目根目录，basedir 就是项目根目录
# 如果 config.py 在 app/ 目录下，你需要调整 basedir 的计算或 NCE_PDF_PATH 的 join 方式
# 假设 config.py 在项目根目录
basedir = os.path.abspath(os.path.dirname(__file__))

# --- 从 .env 文件加载环境变量 ---
# 这会查找项目根目录下的 .env 文件并加载其中的变量
# 如果环境变量已在系统级别设置，则不会被 .env 文件覆盖
# 通常将 .env 放在项目根目录
dotenv_path = os.path.join(basedir, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f".env file loaded from: {dotenv_path}") # 打印加载信息
else:
    print(".env file not found, relying on system environment variables or defaults.")
# -----------------------------

class Config:
    """
    Flask 应用配置类。
    优先从环境变量加载配置，如果没有则使用默认值。
    """
    # --- 新增：根管理员用户名 ---
    ROOT_ADMIN_USERNAME = os.environ.get('ROOT_ADMIN_USERNAME') or 'root'

    # --- 安全密钥 ---
    # !!! 极其重要 !!!
    # 用于保护 Session、CSRF 等。必须是一个复杂、随机且保密的字符串。
    # 强烈建议在 .env 文件或操作系统环境变量中设置 SECRET_KEY。
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        SECRET_KEY = 'a-very-secret-key-CHANGE-ME!'
        print("警告：正在使用默认的 SECRET_KEY，极不安全！请在环境变量或 .env 文件中设置一个强大的 SECRET_KEY。")
        # 在生产环境中，你可能希望在这里引发一个错误来阻止启动：
        # raise ValueError("SECRET_KEY not set in environment variables or .env file.")

    # --- 数据库配置 ---
    # 优先使用环境变量 DATABASE_URL (例如：postgresql://user:pass@host/db)
    # 否则，默认使用项目根目录下的 instance/ 文件夹中的 SQLite 文件
    # 确保 'instance' 文件夹存在或 SQLAlchemy 会自动创建它
    default_db_path = os.path.join(basedir, 'instance', 'nce_vocab.db')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + default_db_path
    print(f"Using database: {SQLALCHEMY_DATABASE_URI}") # 打印数据库路径

    # 关闭 SQLAlchemy 的事件追踪，减少开销
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- 文件上传配置 (可选，如果你的应用有上传功能) ---
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(basedir, 'uploads')
    ALLOWED_EXTENSIONS = {'pdf'} # 这个配置通常用于文件上传验证，与 NCE_PDF_PATH 无关

    # --- 分页配置 (例如用于 /history 页面) ---
    # 尝试从环境变量获取每页数量，否则默认为 10
    POSTS_PER_PAGE = int(os.environ.get('POSTS_PER_PAGE') or 10)

    # --- PDF 文件路径配置 (核心修改) ---
    # 优先从环境变量 NCE_PDF_PATH 获取
    # 如果环境变量没有设置，则构建一个相对于项目根目录的路径
    # 假设 PDF 文件放在 项目根目录/data/nce_book2.pdf
    default_pdf_path = os.path.join(basedir, 'uploads', 'nce_book2.pdf')
    NCE_PDF_PATH = os.environ.get('NCE_PDF_PATH') or default_pdf_path
    print(f"Using NCE PDF Path: {NCE_PDF_PATH}") # 打印 PDF 路径
    # --- 结束 PDF 路径配置 ---

    # --- 基础管理员凭证 (从环境变量加载 - 已被 User 模型和角色系统替代，可以考虑移除) ---
    # 这部分可能不再需要，因为你已经有了用户系统和 is_admin/root_admin 角色
    # 保留它可能会引起混淆，但如果仍有旧代码依赖，暂时保留
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'admin_legacy' # 改个名字避免冲突
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'password_legacy'


# --- 可以根据需要添加其他配置 ---
# 例如:
# MAIL_SERVER = os.environ.get('MAIL_SERVER')
# MAIL_PORT = int(os.environ.get('MAIL_PORT') or 25)
# MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
# MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
# MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
# ADMINS = ['your-email@example.com'] # 用于接收错误报告的邮箱列表