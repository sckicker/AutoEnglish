from app import create_app
import os

# Optional: Load environment variables if needed (e.g., from a .env file)
# from dotenv import load_dotenv
# load_dotenv()

app = create_app()

if __name__ == '__main__':
    # Ensure the instance folder exists where the DB might be stored
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    # Note: For production, use a proper WSGI server like Gunicorn or uWSGI
    app.run(debug=True) # debug=True is helpful for development