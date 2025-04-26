"""
@Author: Tianyi Zhang
@Date: 2025/4/26
@Description: 
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_apscheduler import APScheduler
from config import Config
import datetime
import os


# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
scheduler = APScheduler()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)


    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    scheduler.init_app(app)


    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.reservation import reservation_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(reservation_bp)
    app.register_blueprint(admin_bp)

    # Initialize task scheduler
    with app.app_context():
        from app.tasks.scheduler import initialize_scheduler
        initialize_scheduler(scheduler)
        scheduler.start()

    @app.context_processor
    def inject_now():
        from flask import current_app
        return {
            'now': datetime.datetime.now(),
            'current_app': current_app
        }

    return app