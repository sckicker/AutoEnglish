# NCE Vocabulary Quiz Platform

An AI-driven web application to automatically generate vocabulary quizzes from New Concept English PDF files.

## Features

* Upload/Process NCE PDF (Book 2 initially).
* Extract "New words and expressions" using automated parsing.
* Store vocabulary in a database.
* Generate quizzes based on selected lessons (CN->EN, EN->CN).
* Web interface for taking quizzes and viewing results.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd nce-project
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    # On Windows:
    # venv\Scripts\activate
    # On macOS/Linux:
    # source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Prepare PDF:**
    * Place your legally obtained `nce_book2.pdf` (or similar) into the `uploads/` directory. **Ensure you comply with copyright laws.**

5.  **Initialize the database:**
    * The database and tables should be created automatically the first time you run the app via `run.py` (due to `db.create_all()` in `app/__init__.py`). Check the console output. The DB file (`nce_vocab.db`) will appear in the `instance/` folder.

6.  **Process the PDF to populate the database:**
    * You can trigger this via an admin endpoint (like the example `/admin/process_pdf` - make sure to secure this for production) or run a separate script. For the example route:
        * Start the Flask server: `python run.py`
        * Send a POST request to `http://127.0.0.1:5000/admin/process_pdf` (e.g., using `curl` or a tool like Postman):
          ```bash
          curl -X POST [http://127.0.0.1:5000/admin/process_pdf](http://127.0.0.1:5000/admin/process_pdf)
          ```
        * Check the console output of the Flask server for progress and results.

7.  **Run the application:**
    ```bash
    python run.py
    ```
    * Access the application in your browser, typically at `http://127.0.0.1:5000`.

## Important Notes

* **PDF Parsing:** The `pdf_parser.py` contains placeholder logic. Robust PDF parsing, especially for varied layouts and OCR needs, is complex and requires significant effort and refinement.
* **Copyright:** Using copyrighted materials like *New Concept English* requires permission for anything beyond personal, private use. Be responsible.
* **Security:** The provided structure is basic. For production, implement proper security measures (e.g., user authentication, input validation, secure admin functions, environment variables for secrets).

## Next Steps / Potential Enhancements

* Implement robust PDF parsing in `pdf_parser.py`.
* Add user authentication and progress tracking.
* Implement different quiz types (multiple choice, etc.).
* Add error handling and user feedback.
* Improve UI/UX.
* Secure the admin functions.
* Use Flask-Migrate for database schema migrations.