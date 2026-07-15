from datetime import datetime, timedelta
from flask_login import UserMixin
from app import db, bcrypt

# Plain strings instead of native DB enums, so this schema works identically
# on SQLite (dev) and Postgres (prod) without enum migration headaches.
ROLES = ("requester", "agent", "admin")
STATUSES = ("open", "in_progress", "resolved", "closed")
PRIORITIES = ("low", "medium", "high", "critical")
CATEGORIES = ("hardware", "software", "network", "account", "other")

# Once a ticket has used up this fraction of its SLA window without being
# resolved, it's flagged "at risk" even though it hasn't technically breached
# yet. Gives agents a warning instead of only finding out after the fact.
SLA_AT_RISK_THRESHOLD = 0.75

# SLA target (in hours) per priority level - the whole SLA feature is
# driven by this one dictionary.
SLA_HOURS = {
    "critical": 2,
    "high": 4,
    "medium": 24,
    "low": 72,
}


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="requester")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tickets_created = db.relationship(
        "Ticket", foreign_keys="Ticket.created_by_id", backref="creator", lazy="dynamic"
    )
    tickets_assigned = db.relationship(
        "Ticket", foreign_keys="Ticket.assigned_to_id", backref="assignee", lazy="dynamic"
    )

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    @property
    def is_agent(self):
        return self.role == "agent"

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_requester(self):
        return self.role == "requester"

    @property
    def is_staff(self):
        """Agents and admins are both 'staff' - they work tickets rather than just file them."""
        return self.role in ("agent", "admin")

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open")
    priority = db.Column(db.String(20), nullable=False, default="medium")
    category = db.Column(db.String(30), nullable=False, default="other")

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    comments = db.relationship(
        "Comment", backref="ticket", lazy="dynamic", cascade="all, delete-orphan"
    )

    @property
    def sla_deadline(self):
        target_hours = SLA_HOURS.get(self.priority, 24)
        return self.created_at + timedelta(hours=target_hours)

    @property
    def sla_status(self):
        """Three-tier SLA status: 'on_time', 'at_risk', or 'breached'.

        - Closed/resolved tickets are judged against when they were actually
          resolved, so a ticket that was fixed in time stays 'on_time' forever
          even after the clock keeps ticking.
        - Open tickets past their deadline are 'breached'.
        - Open tickets that have used up most of their SLA window (default:
          75%) without being resolved are 'at_risk', so agents get a warning
          before they blow the deadline rather than after.
        """
        if self.status in ("resolved", "closed"):
            check_time = self.resolved_at or self.updated_at
            return "breached" if check_time > self.sla_deadline else "on_time"

        now = datetime.utcnow()
        if now > self.sla_deadline:
            return "breached"

        window_seconds = (self.sla_deadline - self.created_at).total_seconds()
        elapsed_seconds = (now - self.created_at).total_seconds()
        if window_seconds > 0 and (elapsed_seconds / window_seconds) >= SLA_AT_RISK_THRESHOLD:
            return "at_risk"
        return "on_time"

    @property
    def is_overdue(self):
        """Kept for backward compatibility / simple boolean checks (e.g. dashboard counts)."""
        return self.sla_status == "breached"

    @property
    def resolution_time_hours(self):
        if not self.resolved_at:
            return None
        delta = self.resolved_at - self.created_at
        return round(delta.total_seconds() / 3600, 1)

    def __repr__(self):
        return f"<Ticket #{self.id} {self.title} [{self.status}]>"


class Comment(db.Model):
    __tablename__ = "ticket_comments"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship("User")


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=True)
    action = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")