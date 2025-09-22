
import os
from flask import Flask
from flask_mail import Mail
from .config import Config
import warnings

# Suppress all warnings
warnings.filterwarnings("ignore")

mail = Mail()

def create_app():
    # Base project directory (one level up from app/)
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    app = Flask(__name__,
                template_folder=os.path.join(base_dir, "templates"),
                static_folder=os.path.join(base_dir, "static"),
                static_url_path="/static")

    # Load configuration
    app.config.from_object(Config)

    # Define storage folders
    app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, "uploads")
    app.config['PREVIEW_FOLDER'] = os.path.join(app.static_folder, "previews")
    app.config['OUTPUT_FOLDER'] = os.path.join(app.static_folder, "outputs")

    # Ensure folders exist
    for folder in [app.config['UPLOAD_FOLDER'], app.config['PREVIEW_FOLDER'], app.config['OUTPUT_FOLDER']]:
        os.makedirs(folder, exist_ok=True)

    # File size limit (200 MB)
    app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

    # Initialize extensions
    mail.init_app(app)

    # Register routes blueprint
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app
