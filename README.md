# NCE Vocabulary Learning Platform (新概念英语词汇学习平台)

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Flask Version](https://img.shields.io/badge/flask-2.x%2B-green.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Security Rating](https://img.shields.io/badge/security-scanning_active-brightgreen)](https://github.com/sckicker/AutoEnglish/security/dependabot)

一个基于 Flask 的 Web 应用，旨在帮助用户学习和测试《新概念英语》（NCE）第二册的词汇。

## ✨ 主要功能 (Features)

*   **课文浏览:** 查看 NCE 第二册各课的原文文本。
*   **词汇测试:**
    *   可选择特定课程进行词汇测验。
    *   支持中译英 (写英文) 和英译中 (写中文) 两种模式。
    *   可自定义测验的题目数量。
    *   支持**语音朗读**课文 (依赖浏览器 Web Speech API)。
    *   支持**跟读录音**练习 (依赖浏览器 MediaRecorder API)。
*   **用户认证:** 基于 Flask-Login 的安全用户注册与登录系统。
*   **学习记录:**
    *   **测试历史:** 追踪过往的测验记录、得分和日期。
    *   **错题本:** 自动记录答错的词汇，支持标记重点和分类管理，便于针对性复习。
*   **管理面板:**
    *   **PDF 处理:** 自动从 NCE Book 2 PDF 文件提取课文和词汇表，并存入数据库。
    *   **词汇管理:** 查看数据库中所有词汇（增删改功能规划中）。
    *   **用户管理 (可选):** 基于配置或数据库标志，区分管理员和普通用户。
*   **响应式设计:** 使用 Bootstrap 5 构建，适配不同尺寸的设备屏幕。

## ⚙️ 技术栈 (Technology Stack)

*   **后端 (Backend):** Python 3.11+, Flask
*   **数据库 (Database):** SQLAlchemy ORM, Flask-SQLAlchemy, Flask-Migrate (默认使用 SQLite)
*   **认证 (Authentication):** Flask-Login
*   **表单 (Forms):** Flask-WTF, WTForms (包含 email-validator)
*   **环境配置 (Environment):** python-dotenv
*   **前端 (Frontend):** Jinja2 Templates, Bootstrap 5, JavaScript (Fetch API, Web Speech API, MediaRecorder API)
*   **PDF 解析 (PDF Parsing):** pdfminer.six (或其他 PDF 处理库，在 `pdf_parser.py` 中实现)
*   **(可选) 文本转语音 (TTS):** Coqui TTS (通过 `tts` 命令行工具生成音频文件)

## 📋 环境要求 (Prerequisites)

*   **Python:** 推荐 3.11 或更高版本。
*   **pip:** Python 包管理器。
*   **Git:** 版本控制工具。
*   **(核心) NCE Book 2 PDF:** 需要一份可被应用访问的《新概念英语》第二册 PDF 文件。
*   **(可选) Coqui TTS 命令行工具:** 如果需要**预生成**课文音频文件，需要单独安装和配置 [Coqui TTS](https://github.com/coqui-ai/TTS)。
*   **(可选) `espeak-ng`:** Coqui TTS 通常需要此系统依赖来进行文本处理 (特别是多语言)。

## 🚀 安装与设置 (Installation & Setup)

1.  **克隆仓库:**
    ```bash
    git clone https://github.com/sckicker/AutoEnglish.git
    cd AutoEnglish
    ```

2.  **创建并激活虚拟环境:**
    *   **Linux/macOS:**
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    *   **Windows (CMD/PowerShell):**
        ```bash
        python -m venv venv
        .\venv\Scripts\activate
        ```

3.  **安装 Python 依赖:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **配置环境变量:**
    *   复制 `.env.example` (如果存在) 为 `.env`，或者手动创建 `.env` 文件在项目根目录。
    *   **编辑 `.env` 文件**，至少设置以下变量:

        ```dotenv
        # .env (示例)

        # !!! 必须: 生成一个强随机密钥 !!!
        # 运行: python -c 'import secrets; print(secrets.token_hex(32))'
        SECRET_KEY='你的复杂随机密钥'

        # --- 数据库 URL (可选, 默认使用 instance/nce_vocab.db) ---
        # DATABASE_URL='postgresql://user:password@host:port/dbname'

        # --- NCE PDF 路径 (必须，用于管理员处理PDF功能) ---
        # 使用绝对路径指向你的 NCE Book 2 PDF 文件
        NCE_PDF_PATH='C:/path/to/your/nce_book2.pdf'
        # 或者，如果 config.py 中使用了相对路径逻辑，确保文件在对应位置
        # NCE_PDF_PATH='data/nce_book2.pdf'

        # --- 指定管理员用户名 (可选, 用于 flask sync-admins 命令) ---
        # 用逗号分隔多个用户名，默认为 'root'
        ADMIN_USERNAMES='root,your_other_admin_username'

        # --- Flask 开发设置 (可选) ---
        FLASK_ENV='development' # 或者 'production'
        FLASK_DEBUG=True        # 或者 False
        FLASK_APP='run.py'      # 你的 Flask 应用入口文件
        ```
    *   **安全警告:** **永远不要** 将包含真实密钥的 `.env` 文件提交到 Git。确保 `.gitignore` 文件包含 `.env`。

5.  **数据库初始化与迁移:**
    *   **初始化迁移环境 (仅需一次):**
        ```bash
        flask db init
        ```
    *   **生成迁移脚本 (模型更改后):**
        ```bash
        flask db migrate -m "描述你的模型更改，例如 Initial schema 或 Add category to WrongAnswer"
        ```
    *   **应用迁移到数据库 (创建或更新表):**
        ```bash
        flask db upgrade
        ```

6.  **(可选) 同步管理员状态:**
    *   确保你在 `.env` 或 `config.py` 中指定的 `ADMIN_USERNAMES` 对应的用户**已经通过注册存在**于数据库中。
    *   运行 CLI 命令将这些用户的 `is_admin` 标志设置为 `True`:
        ```bash
        flask sync-admins
        ```

## ▶️ 运行应用 (Running the Application)

1.  **确保虚拟环境已激活。**
2.  **设置 `FLASK_APP` 环境变量 (如果尚未在 `.env` 或 `.flaskenv` 中设置):**
    *   `export FLASK_APP=run.py` (Linux/macOS)
    *   `set FLASK_APP=run.py` (Windows CMD)
    *   `$env:FLASK_APP = "run.py"` (Windows PowerShell)
3.  **启动 Flask 开发服务器:**
    ```bash
    flask run
    ```
4.  在浏览器中打开: `http://127.0.0.1:5000` (或 Flask 提示的地址)。

## 👤 使用说明 (Usage)

### 普通用户

1.  **注册/登录:** 创建或登录账户。
2.  **浏览/学习:** 查看课程列表，点击进入课文页面。
3.  **听/读:** 使用页面上的控件听预生成音频或浏览器朗读，进行跟读录音练习。
4.  **测验:**
    *   在首页勾选课程，设置选项后点击“开始单词测试”。
    *   或在课文页面点击“测试本课词汇”直接开始当前课程的测验。
5.  **复习:** 查看测试历史和带有标记/分类功能的错题本。

### 🔒 管理员 (Admin User)

1.  **登录:** 使用被设置为管理员的账户登录 (例如 `root`)。
2.  **访问管理面板:** 点击导航栏中的“管理面板”链接。
3.  **处理 PDF:**
    *   确保 `NCE_PDF_PATH` 配置正确。
    *   在管理面板点击“开始处理 PDF 文件”按钮，将课文和词汇导入数据库。
4.  **管理词汇:** 查看数据库中的词汇列表。
5.  **(如果需要) 同步管理员:** 如果修改了配置文件中的 `ADMIN_USERNAMES`，可再次运行 `flask sync-admins` 命令更新数据库。

## 🔑 管理员密码重置 (Password Reset)

如果忘记管理员密码：

1.  访问服务器终端。
2.  进入项目目录并激活虚拟环境。
3.  运行 `flask shell`。
4.  执行以下 Python 命令 (替换 `'root'` 为需要重置的用户名):
    ```python
    from app import db
    from app.models import User
    user = User.query.filter_by(username='root').first()
    if user:
      new_pass = '设置一个强临时密码' # 替换掉!
      user.set_password(new_pass)
      db.session.add(user)
      db.session.commit()
      print(f"用户 '{user.username}' 的密码已重置。请立即用新密码登录并修改。")
    else:
      print("用户未找到。")
    exit()
    ```
5.  使用临时密码登录并尽快修改为最终密码。

## 📄 版权与许可 (License)

*   本项目代码基于 [MIT License](https://opensource.org/licenses/MIT) (如果选择)。
*   **请注意:** 本项目使用的《新概念英语》教材内容本身受版权保护，请在符合相关法律法规和版权要求的前提下使用本项目。本项目仅为学习和技术交流目的。