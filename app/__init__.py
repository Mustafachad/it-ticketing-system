import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
limiter = Limiter(key_func=get_remote_address, default_limits=[])


def create_app(config_overrides=None):
    app = Flask(__name__)

    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    database_url = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(basedir, '..', 'ticketing.db')}"
    )
    # Render/Railway/Heroku-style providers hand out "postgres://" URLs, but
    # SQLAlchemy 1.4+ only accepts the "postgresql://" scheme for the same driver.
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"
    bcrypt.init_app(app)
    limiter.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.auth.routes import auth_bp
    from app.tickets.routes import tickets_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tickets_bp)

    from flask import redirect, url_for

    @app.route("/")
    def index():
        return redirect(url_for("tickets.dashboard"))

    with app.app_context():
        db.create_all()
        from app.utils import seed_admin_if_missing
        seed_admin_if_missing()

    return app