import os
from flask import Flask
from .extensions import db, login_manager


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

    secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')
    app.config['SECRET_KEY'] = secret_key

    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///learning_management.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    upload_folder = os.path.join(app.root_path, '..', 'static', 'uploads')
    app.config['UPLOAD_FOLDER'] = os.path.abspath(upload_folder)
    app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

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

    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'videos'), exist_ok=True)
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'materials'), exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create upload directories: {e}")

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    from .models.users import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except Exception:
            return None

    # Optional: validate Cloudinary config for serverless readiness
    try:
        from .services.cloudinary_service import validate_cloudinary_config
        validate_cloudinary_config()
    except Exception:
        pass

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
    )
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(store_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(integrations_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(materials_bp)
    app.register_blueprint(student_projects_bp)

    # Alias common endpoints without blueprint prefix to match existing templates
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

    return app
