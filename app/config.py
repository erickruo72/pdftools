import os
from dotenv import load_dotenv

# Load environment variables from .env if available
load_dotenv()

class Config:
    """
    Base configuration class for the Flask application.
    Holds settings for Flask-Mail, file uploads, and PDF tool paths.
    """

    # ----------------------------------------------------------------------
    # Security
    # ----------------------------------------------------------------------
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-hard-to-guess-string'

    # ----------------------------------------------------------------------
    # Flask-Mail Configuration
    # ----------------------------------------------------------------------
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'erickruo72@gmail.com'
    MAIL_PASSWORD = 'eeia kqvn qbhg obly'   # NEW APP PASSWORD
    MAIL_DEFAULT_SENDER = 'erickruo72@gmail.com'

    # ----------------------------------------------------------------------
    # File Upload Configuration
    # ----------------------------------------------------------------------
    BASE_STATIC = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'static')

    UPLOAD_FOLDER = os.path.join(BASE_STATIC, 'uploads')   # Raw uploaded PDFs
    PREVIEW_FOLDER = os.path.join(BASE_STATIC, 'previews') # Preview images / thumbnails
    OUTPUT_FOLDER = os.path.join(BASE_STATIC, 'outputs')   # Final processed files

    # Ensure folders exist
    for folder in [UPLOAD_FOLDER, PREVIEW_FOLDER, OUTPUT_FOLDER]:
        os.makedirs(folder, exist_ok=True)

    # Maximum size for uploaded files (200 MB to match __init__.py)
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024

    # Allowed file extensions
    ALLOWED_EXTENSIONS = {'pdf'}

    # ----------------------------------------------------------------------
    # Platform-specific Binary Paths for Poppler and Ghostscript
    # ----------------------------------------------------------------------
    VERAPDF_PATH = r"C:\Users\Erick Ruo\verapdf\verapdf.bat"
    POPPLER_PATH = os.environ.get('POPPLER_PATH') or (r"C:\poppler-24.08.0\Library\bin" if os.name == 'nt' else None)
    GHOSTSCRIPT_PATH = os.environ.get('GHOSTSCRIPT_PATH') or (r"C:\gs10.05.1\bin\gswin64c.exe" if os.name == 'nt' else None)
