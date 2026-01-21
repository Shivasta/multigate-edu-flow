import os
from flask import Flask
from app.extensions import login_manager, limiter, csrf
from app.database import init_app as init_db_app
from app.models import load_user

def create_app(test_config=None):
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=os.path.join(base_dir, 'templates'),
        static_folder=os.path.join(base_dir, 'static')
    )
    
    # Configuration
    # Fallback secret key logic similar to original app.py
    secret_from_env = (
        os.environ.get('MEF_SECRET_KEY')
        or os.environ.get('FLASK_SECRET_KEY')
        or os.environ.get('SECRET_KEY')
    )
    
    app.config.from_mapping(
        SECRET_KEY=secret_from_env or os.urandom(32).hex(),
        DEBUG=os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes'),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=8 * 60 * 60 # 8 hours
    )

    app.config['SESSION_COOKIE_SECURE'] = not app.debug

    if test_config:
        app.config.from_mapping(test_config)

    # Initialize Extensions
    login_manager.init_app(app)
    limiter.init_app(app)
    csrf.init_app(app)
    init_db_app(app)

    # User Loader
    @login_manager.user_loader
    def user_loader(user_id):
        return load_user(user_id)

    # Register Blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.requests import bp as requests_bp
    app.register_blueprint(requests_bp)

    from app.staff import bp as staff_bp
    app.register_blueprint(staff_bp)
    
    return app
