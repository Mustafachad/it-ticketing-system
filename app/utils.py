import secrets

from app import db
from app.models import User, AuditLog


def seed_admin_if_missing():
    """Create a default admin account on first run so there's always a way in.

    The password is randomly generated each time this fires and printed to
    the console/server logs once - it is NOT hardcoded, since this file is
    public source code. Whoever controls the deploy's logs is the only one
    who sees it. In normal use, seed.py (which creates its own clearly-
    labeled demo accounts) runs before anyone would ever rely on this.
    """
    if User.query.filter_by(role="admin").first() is None:
        temp_password = secrets.token_urlsafe(12)
        admin = User(username="admin", email="admin@example.com", role="admin")
        admin.set_password(temp_password)
        db.session.add(admin)
        db.session.commit()
        print("=" * 60)
        print("Created default admin account (no admin existed yet):")
        print("  username: admin")
        print(f"  password: {temp_password}")
        print("  -> this was randomly generated and only shown here once.")
        print("  -> change it after logging in, or just run seed.py instead.")
        print("=" * 60)


def log_action(user_id, action, ticket_id=None):
    entry = AuditLog(user_id=user_id, action=action, ticket_id=ticket_id)
    db.session.add(entry)
    db.session.commit()