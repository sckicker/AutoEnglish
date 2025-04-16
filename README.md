# NCE Vocabulary Learning Platform (新概念英语词汇学习平台)

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Flask Version](https://img.shields.io/badge/flask-2.x%2B-green.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Flask-based web application designed to help users learn and test their vocabulary from New Concept English (NCE) Book 2.

## ✨ Features

*   **Lesson Text Viewing:** Browse and read the original texts for NCE Book 2 lessons.
*   **Vocabulary Quizzes:**
    *   Select specific lessons for testing.
    *   Choose quiz type: Chinese to English (中 -> 英) or English to Chinese (英 -> 中).
    *   Configure the number of questions per quiz.
*   **User Authentication:** Secure user registration and login system (powered by Flask-Login).
*   **Learning Records:**
    *   **Quiz History:** Track past quiz attempts, scores, and dates.
    *   **Wrong Answer List (错题本):** Automatically logs incorrectly answered vocabulary for focused review.
*   **Admin Panel:**
    *   Process NCE Book 2 PDF to automatically extract lesson texts and vocabulary lists into the database.
    *   View all vocabulary items in the database (Add/Edit/Delete functionality planned).
    *   Manage user roles (Assign/revoke admin privileges - basic implementation).
*   **Responsive Design:** Uses Bootstrap 5 for compatibility across different screen sizes.

## ⚙️ Technology Stack

*   **Backend:** Python 3, Flask
*   **Database:** SQLAlchemy ORM, Flask-SQLAlchemy, Flask-Migrate (Default: SQLite)
*   **Authentication:** Flask-Login
*   **Forms:** Flask-WTF, WTForms (with email validation)
*   **Environment Variables:** python-dotenv
*   **Frontend:** Jinja2 Templates, Bootstrap 5, JavaScript (Fetch API)
*   **PDF Parsing:** (Requires a library like `pdfminer.six` - assumed to be in `pdf_parser.py`)

## 📋 Prerequisites

*   **Python:** Version 3.9 or higher recommended.
*   **pip:** Python package installer (usually comes with Python).
*   **Git:** Version control system (for cloning the repository).
*   **NCE Book 2 PDF:** You need a copy of the New Concept English Book 2 PDF file accessible by the application.

## 🚀 Installation & Setup

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-directory-name>
    ```

2.  **Create and Activate a Virtual Environment:**
    *   **Linux/macOS:**
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    *   **Windows:**
        ```bash
        python -m venv venv
        .\venv\Scripts\activate
        ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: If `requirements.txt` doesn't exist yet, create it after installing packages locally: `pip freeze > requirements.txt`)*

4.  **Configure Environment Variables:**
    *   Copy the example environment file (if provided) or create a new file named `.env` in the project's root directory.
        ```
        cp .env.example .env
        ```
        (If no `.env.example` exists, create `.env` manually).
    *   **Edit the `.env` file** and set the following essential variables:

        ```dotenv
        # .env file

        # !!! REQUIRED: Generate a strong, random secret key !!!
        # Use Python: python -c 'import secrets; print(secrets.token_hex(32))'
        SECRET_KEY='your_generated_super_secret_key_here'

        # --- Database URL (Optional) ---
        # Default uses SQLite in 'instance/nce_vocab.db'
        # Example for PostgreSQL: DATABASE_URL='postgresql://user:password@host:port/dbname'
        # Example for MySQL: DATABASE_URL='mysql+pymysql://user:password@host:port/dbname'

        # --- NCE PDF Path (REQUIRED for PDF Processing) ---
        # Absolute path to your NCE Book 2 PDF file
        # Example (Linux/macOS): NCE_PDF_PATH='/home/user/documents/nce_book2.pdf'
        # Example (Windows): NCE_PDF_PATH='C:/Users/YourUser/Documents/nce_book2.pdf'
        # OR a path relative to the project root (managed by config.py), e.g., if placed in project_root/data/
        # NCE_PDF_PATH='data/nce_book2.pdf' # Ensure config.py uses os.path.join(basedir, ...)

        # --- Root Admin Username (Optional) ---
        # Default is 'root' if not set
        # ROOT_ADMIN_USERNAME='your_root_admin_username'

        # --- Flask Environment (Optional) ---
        # Set to 'development' for debug mode, 'production' for production
        FLASK_ENV='development'
        FLASK_DEBUG=True # Or False for production
        FLASK_APP='run.py' # Or your main flask app entry point file/module
        ```
    *   **SECURITY:** **Never commit your `.env` file to Git!** Ensure it's listed in your `.gitignore` file.

5.  **Database Setup (Using Flask-Migrate):**
    *   **Initialize (only if the `migrations` folder doesn't exist):**
        ```bash
        flask db init
        ```
    *   **Create Initial Migration (if starting fresh or after model changes):**
        ```bash
        flask db migrate -m "Initial database schema"
        ```
    *   **Apply Migrations to Create/Update Database:**
        ```bash
        flask db upgrade
        ```
    *(This will create the `instance/nce_vocab.db` SQLite file by default, based on the models defined in `app/models.py`)*

## ▶️ Running the Application

1.  **Ensure your virtual environment is activated.**
2.  **Start the Flask Development Server:**
    ```bash
    flask run
    ```
3.  Open your web browser and navigate to: `http://127.0.0.1:5000` (or the address provided by Flask).

## 👤 Usage

### Regular User

1.  **Register:** Create a new user account.
2.  **Login:** Sign in with your credentials.
3.  **Browse Lessons:** View the list of available lessons on the homepage or the dedicated "课程列表" page. Click to view lesson text.
4.  **Take a Quiz:** On the homepage, select one or more lessons using the checkboxes, choose the quiz type and number of questions, and click "开始单词测试".
5.  **Review Results:** After submitting the quiz, view your score and any incorrect answers.
6.  **Check History:** Visit the "测试历史" page to see past attempts.
7.  **Review Wrong Answers:** Visit the "错题本" page to see vocabulary you've previously answered incorrectly.

### 🔒 Admin User

1.  **Login:** Log in using the `root` account (or another account designated as admin). The default `root` password needs to be set (e.g., during initial setup or via the Flask shell - see "Password Reset" below).
2.  **Access Dashboard:** Click the "管理面板" link in the navbar.
3.  **Process PDF:**
    *   Ensure the `NCE_PDF_PATH` in your `.env` file or `config.py` points to the correct NCE Book 2 PDF file.
    *   On the Admin Dashboard, click the "开始处理 PDF 文件" button.
    *   Wait for the process to complete. Status messages will indicate success or failure, along with summaries of added/updated vocabulary and lessons. *(This populates the database)*
4.  **Manage Vocabulary:** Navigate to the "管理词汇" page to view all vocabulary extracted from the PDF. (Add/Edit/Delete are planned features).
5.  **Manage Users (Root Admin Only):** If implemented, access the user management page to grant/revoke admin privileges for other users.

## 🔑 Password Reset (for Admins)

If you forget the `root` (or any admin) password:

1.  Access your server's terminal.
2.  Navigate to the project directory and activate the virtual environment.
3.  Run `flask shell`.
4.  Inside the shell, execute the following Python commands (adjust imports if necessary):
    ```python
    from app import db
    from app.models import User
    user = User.query.filter_by(username='root').first() # Or the username you forgot
    if user:
      new_pass = 'your_secure_temporary_password'
      user.set_password(new_pass)
      db.session.add(user)
      db.session.commit()
      print(f"Password for '{user.username}' has been reset to '{new_pass}'. Log in and change it immediately.")
    else:
      print("User not found.")
    exit()
    ```
5.  Log in with the temporary password and change it through user settings if available, or repeat the process with a final password.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file (if included) for details. Please respect the copyright of the original New Concept English materials.