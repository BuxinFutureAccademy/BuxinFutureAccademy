import os
import logging
import traceback
from logging.handlers import RotatingFileHandler
import cloudinary
from flask import Flask, jsonify, request
from .extensions import db, login_manager, migrate


def create_app():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    templates_path = os.path.join(base_dir, 'templates')
    static_path = os.path.join(base_dir, 'static')

    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=templates_path,
        static_folder=static_path,
    )

    # Basic configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Fix database URL - handle various formats from Neon/Render
    db_url = os.environ.get('DATABASE_URL', '')
    if db_url.startswith('psql '):
        db_url = db_url[5:]  # Remove 'psql ' prefix
    db_url = db_url.strip("'\"")  # Remove surrounding quotes
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///learning_management.db'

    # Cloudinary configuration
    cloudinary.config(
        cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
        api_key=os.environ.get('CLOUDINARY_API_KEY'),
        api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
        secure=True
    )
    
    # File upload configuration
    app.config['UPLOAD_FOLDER'] = 'uploads'  # Virtual path for Cloudinary
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload (Cloudinary free tier limit)

    app.config['DEEPINFRA_API_KEY'] = os.environ.get('DEEPINFRA_API_KEY')
    app.config['DEEPINFRA_API_URL'] = os.environ.get('DEEPINFRA_API_URL', 'https://api.deepinfra.com/v1/openai/chat/completions')

    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', '587'))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

    app.config['WHATSAPP_WEB_URL'] = os.environ.get('WHATSAPP_WEB_URL', 'https://web.whatsapp.com/send?phone=+919319038312')
    app.config['WHATSAPP_ACCESS_TOKEN'] = os.environ.get('WHATSAPP_ACCESS_TOKEN')
    app.config['WHATSAPP_PHONE_NUMBER_ID'] = os.environ.get('WHATSAPP_PHONE_NUMBER_ID')
    app.config['RESET_TOKEN_SALT'] = os.environ.get('RESET_TOKEN_SALT', 'password-reset-salt-change-in-production')

    # No need to create upload directories in production (using Cloudinary)
    if os.environ.get('FLASK_ENV') != 'production':
        try:
            local_upload_path = os.path.join(static_path, 'uploads')
            os.makedirs(local_upload_path, exist_ok=True)
            os.makedirs(os.path.join(local_upload_path, 'videos'), exist_ok=True)
            os.makedirs(os.path.join(local_upload_path, 'materials'), exist_ok=True)
        except Exception as e:
            app.logger.warning(f"Could not create local upload directories: {e}")

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    
    # In production, tables are created via migrations (flask db upgrade)
    # db.create_all() is not used when using Flask-Migrate
    login_manager.login_view = 'auth.login'

    from .models.users import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except Exception:
            return None

    # Configure logging
    if not app.debug:
        file_handler = RotatingFileHandler('app.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('App startup')

    # Initialize Cloudinary service
    try:
        from .services import cloudinary_service
        app.cloudinary = cloudinary_service
        app.logger.info('Cloudinary service initialized')
    except Exception as e:
        app.logger.error(f"Failed to initialize Cloudinary service: {e}")
        app.cloudinary = None

    from .routes import (
        main as main_bp,
        auth as auth_bp,
        projects as projects_bp,
        store as store_bp,
        uploads as uploads_bp,
        integrations as integrations_bp,
        admin as admin_bp,
        materials as materials_bp,
        student_projects as student_projects_bp,
        file_uploads as file_uploads_bp,
        health as health_bp
    )
    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(store_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(integrations_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(materials_bp)
    app.register_blueprint(student_projects_bp)
    app.register_blueprint(file_uploads_bp, url_prefix='/api')
    app.register_blueprint(health_bp)

    # Alias common endpoints without blueprint prefix to match existing templates
    try:
        app.add_url_rule('/', endpoint='index', view_func=main_bp.view_functions['index'])
    except Exception:
        pass
    try:
        app.add_url_rule('/store', endpoint='store', view_func=store_bp.view_functions['store'])
        app.add_url_rule('/course/<int:course_id>', endpoint='course_detail', view_func=store_bp.view_functions['course_detail'])
    except Exception:
        pass
    try:
        app.add_url_rule('/student-projects', endpoint='student_projects', view_func=student_projects_bp.view_functions['student_projects'])
        app.add_url_rule('/student-projects/<int:project_id>', endpoint='view_project', view_func=student_projects_bp.view_functions['view_project'])
        app.add_url_rule('/my-projects', endpoint='my_projects', view_func=student_projects_bp.view_functions['my_projects'])
        app.add_url_rule('/admin/projects', endpoint='admin_projects', view_func=student_projects_bp.view_functions['admin_projects'])
    except Exception:
        pass
    try:
        app.add_url_rule('/login', endpoint='login', view_func=auth_bp.view_functions['login'])
        app.add_url_rule('/forgot-password', endpoint='forgot_password', view_func=auth_bp.view_functions['forgot_password'])
        app.add_url_rule('/logout', endpoint='logout', view_func=auth_bp.view_functions['logout'])
    except Exception:
        pass

    # Error handlers
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"500 Error: {str(error)}")
        app.logger.error(traceback.format_exc())
        return jsonify({"error": "Internal server error", "details": str(error)}), 500

    @app.before_request
    def log_request_info():
        app.logger.debug('Headers: %s', request.headers)
        app.logger.debug('Body: %s', request.get_data())

    @app.after_request
    def log_response(response):
        app.logger.debug('Response status: %s', response.status)
        return response

    return app
