import pytest

from app import create_app, db as _db
from app.models import User, Ticket


@pytest.fixture
def app():
    """A fresh Flask app with an in-memory SQLite DB for each test."""
    application = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,  # simplifies posting forms directly in tests
    })

    with application.app_context():
        yield application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    return _db


def make_user(db, username, role, password="testpass123"):
    user = User(username=username, email=f"{username}@example.com", role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def users(db):
    """One user per role, all sharing the same password."""
    return {
        "admin": make_user(db, "test_admin", "admin"),
        "agent": make_user(db, "test_agent", "agent"),
        "other_agent": make_user(db, "test_agent2", "agent"),
        "requester": make_user(db, "test_requester", "requester"),
        "other_requester": make_user(db, "test_requester2", "requester"),
    }


def login(client, username, password="testpass123"):
    return client.post(
        "/auth/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )
