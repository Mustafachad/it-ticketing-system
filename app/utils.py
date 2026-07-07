from app import db
from app.models import User, AuditLog


def seed_admin_if_missing():
    """Create a default admin account on first run so there's always a way in.

    Credentials are printed to the console once. Change the password after
    first login in a real deployment.
    """
    if User.query.filter_by(role="admin").first() is None:
        admin = User(username="admin", email="admin@example.com", role="admin")
        admin.set_password("changeme123")
        db.session.add(admin)
        db.session.commit()
        print("=" * 60)
        print("Created default admin account:")
        print("  username: admin")
        print("  password: changeme123")
        print("  -> change this immediately after logging in")
        print("=" * 60)


def log_action(user_id, action, ticket_id=None):
    entry = AuditLog(user_id=user_id, action=action, ticket_id=ticket_id)
    db.session.add(entry)
    db.session.commit()