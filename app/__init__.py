import os
from flask import Flask
from .extensions import db, login_manager


def create_app():
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=os.path.join('..', 'templates'),
        static_folder=os.path.join('..', 'static'),
    )

    # Core configuration (from environment with sensible defaults)
    secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')
    app.config['SECRET_KEY'] = secret_key

    # Database configuration (Render postgres url compatibility)
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///learning_management.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # File uploads
    upload_folder = os.path.join(app.root_path, '..', 'static', 'uploads')
    app.config['UPLOAD_FOLDER'] = os.path.abspath(upload_folder)
    app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB

    # AI Assistant
    app.config['DEEPINFRA_API_KEY'] = os.environ.get('DEEPINFRA_API_KEY')
    app.config['DEEPINFRA_API_URL'] = os.environ.get('DEEPINFRA_API_URL', 'https://api.deepinfra.com/v1/openai/chat/completions')

    # Mail
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', '587'))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

    # Misc
    app.config['WHATSAPP_WEB_URL'] = os.environ.get('WHATSAPP_WEB_URL', 'https://web.whatsapp.com/send?phone=+919319038312')
    app.config['RESET_TOKEN_SALT'] = os.environ.get('RESET_TOKEN_SALT', 'password-reset-salt-change-in-production')

    # Create upload directories if they don't exist
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'videos'), exist_ok=True)
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'materials'), exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create upload directories: {e}")

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    # User loader for Flask-Login (import here to avoid circular imports)
    from .models.users import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except Exception:
            return None

    # Register blueprints
    from .routes import main as main_bp, auth as auth_bp, projects as projects_bp, materials as materials_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(materials_bp)

    return app
