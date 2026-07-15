"""
Populates the database with realistic demo data: a handful of users across
all three roles, and ~18 tickets spread across priorities, statuses, and SLA
states (on-time / at-risk / breached), so the dashboard, reports page, and
SLA badges all have something real to show instead of an empty table.

This is destructive - it wipes and recreates all tables. That's intentional:
it's meant to give you (or a recruiter poking at the live demo) a clean,
consistent dataset every time it's run, not to preserve production data.

Usage:
    python seed.py
"""
from datetime import datetime, timedelta

from app import create_app, db
from app.models import User, Ticket, Comment, AuditLog

app = create_app()

# Clearly-labeled demo accounts - use these to log into the live demo.
# (Ordinary self-registration on the site always creates a "requester".)
DEMO_PASSWORD = "demopass123"

USERS = [
    # username,        email,                     role
    ("demo_admin",     "admin@demo.io",           "admin"),
    ("demo_agent",     "agent@demo.io",           "agent"),
    ("agent_priya",    "priya@demo.io",           "agent"),
    ("demo_requester", "requester@demo.io",       "requester"),
    ("req_marcus",     "marcus@demo.io",          "requester"),
    ("req_lena",       "lena@demo.io",            "requester"),
]

now = datetime.utcnow()


def hours_ago(h):
    return now - timedelta(hours=h)


def build_tickets(users):
    u = {name: user for name, user in users.items()}

    # Each tuple: title, description, priority, category, status, created_hours_ago,
    # created_by, assigned_to (or None), resolved_hours_after_creation (or None)
    return [
        # --- critical priority (2h SLA) ---
        ("Point-of-sale terminal down", "Register 3 at the front desk won't boot, showing a black screen.",
         "critical", "hardware", "open", 0.5, "req_marcus", "demo_agent", None),
        ("VPN gateway unreachable for remote staff", "Nobody working from home can connect since ~9am.",
         "critical", "network", "in_progress", 1.7, "demo_requester", "agent_priya", None),
        ("Payroll system throwing 500 errors", "Finance can't run payroll, deadline is today.",
         "critical", "software", "open", 5, "req_lena", None, None),

        # --- high priority (4h SLA) ---
        ("New hire laptop won't join domain", "Laptop for tomorrow's new hire won't authenticate against AD.",
         "high", "account", "open", 1, "req_marcus", "demo_agent", None),
        ("Shared drive permissions reset overnight", "Marketing folder is showing 'access denied' for the whole team.",
         "high", "account", "in_progress", 3.5, "demo_requester", "agent_priya", None),
        ("Conference room display won't mirror laptop", "HDMI works but no audio in the 4th floor conference room.",
         "high", "hardware", "open", 10, "req_lena", "demo_agent", None),
        ("Email delivery delayed by ~30 minutes", "Multiple users reporting slow inbound mail.",
         "high", "network", "resolved", 6, "req_marcus", "agent_priya", 3),

        # --- medium priority (24h SLA) ---
        ("Printer on 2nd floor out of toner", "HP LaserJet by the kitchen needs a new toner cartridge.",
         "medium", "hardware", "open", 2, "demo_requester", None, None),
        ("Slack notifications not coming through on mobile", "iOS app stopped pushing notifications this week.",
         "medium", "software", "in_progress", 20, "req_lena", "demo_agent", None),
        ("Request: second monitor for new desk", "Moved to a new desk, need a second monitor set up.",
         "medium", "hardware", "open", 30, "req_marcus", "agent_priya", None),
        ("Password reset for shared marketing account", "Locked out of the @company social media login.",
         "medium", "account", "resolved", 5, "demo_requester", "demo_agent", 4),
        ("Onboarding checklist software access delayed", "New analyst still waiting on CRM + BI tool access.",
         "medium", "account", "closed", 40, "req_lena", "agent_priya", 35),
        ("Laptop fan making loud noise", "Fan spins loudly under any load, might need a clean/replacement.",
         "medium", "hardware", "in_progress", 12, "req_marcus", "demo_agent", None),

        # --- low priority (72h SLA) ---
        ("Request: standing desk conversion", "Would like a sit-stand desk converter for ergonomics.",
         "low", "other", "open", 10, "demo_requester", None, None),
        ("Old ticketing macros need cleanup", "A few canned responses reference a vendor we no longer use.",
         "low", "software", "in_progress", 60, "req_lena", "agent_priya", None),
        ("Spare mouse requested for desk", "Current mouse's scroll wheel is intermittent.",
         "low", "hardware", "resolved", 50, "req_marcus", "demo_agent", 20),
        ("Guest wifi password rotation", "Routine quarterly rotation of the guest network password.",
         "low", "network", "open", 200, "demo_requester", None, None),
        ("Update office directory signage", "Two people listed have left, directory needs an update.",
         "low", "other", "closed", 100, "req_lena", "agent_priya", 40),

        # --- extra unassigned intake, for the admin triage view ---
        ("Can't access invoicing portal", "Getting a certificate warning when loading the vendor invoicing site.",
         "high", "software", "open", 0.25, "req_marcus", None, None),
    ]


def run():
    with app.app_context():
        print("Dropping and recreating all tables...")
        db.drop_all()
        db.create_all()

        users = {}
        for username, email, role in USERS:
            user = User(username=username, email=email, role=role)
            user.set_password(DEMO_PASSWORD)
            db.session.add(user)
            users[username] = user
        db.session.commit()

        rows = build_tickets(users)
        tickets = []
        audit_entries = []
        for (title, desc, priority, category, status, created_hrs, creator, assignee, resolved_hrs_after) in rows:
            created_at = hours_ago(created_hrs)
            ticket = Ticket(
                title=title,
                description=desc,
                priority=priority,
                category=category,
                status=status,
                created_by_id=users[creator].id,
                assigned_to_id=users[assignee].id if assignee else None,
                created_at=created_at,
                updated_at=created_at,
            )
            if resolved_hrs_after is not None:
                ticket.resolved_at = created_at + timedelta(hours=resolved_hrs_after)
                ticket.updated_at = ticket.resolved_at
            db.session.add(ticket)
            tickets.append(ticket)
        db.session.commit()

        for ticket, (title, desc, priority, category, status, created_hrs, creator, assignee, resolved_hrs_after) in zip(tickets, rows):
            audit_entries.append(AuditLog(
                user_id=users[creator].id,
                ticket_id=ticket.id,
                action=f"Created ticket #{ticket.id}",
                timestamp=ticket.created_at,
            ))
            if assignee:
                audit_entries.append(AuditLog(
                    user_id=users[creator].id,
                    ticket_id=ticket.id,
                    action=f"Assigned ticket #{ticket.id} to {assignee}",
                    timestamp=ticket.created_at,
                ))
            if ticket.resolved_at:
                audit_entries.append(AuditLog(
                    user_id=users[assignee].id if assignee else users[creator].id,
                    ticket_id=ticket.id,
                    action=f"Updated ticket #{ticket.id} (status={status})",
                    timestamp=ticket.resolved_at,
                ))

        # A few comments for realism on a handful of tickets.
        sample_comments = [
            (tickets[0], "demo_agent", "Heading over to check the register now."),
            (tickets[1], "agent_priya", "Escalated to the network vendor, waiting on their update."),
            (tickets[4], "agent_priya", "Reset the folder ACL, please confirm you can see it now."),
            (tickets[6], "req_marcus", "Looks resolved on my end, thanks!"),
            (tickets[10], "demo_agent", "Password reset and shared over the secure channel."),
        ]
        for ticket, username, body in sample_comments:
            comment_time = ticket.created_at + timedelta(minutes=20)
            db.session.add(Comment(
                ticket_id=ticket.id, user_id=users[username].id, body=body, created_at=comment_time,
            ))
            audit_entries.append(AuditLog(
                user_id=users[username].id,
                ticket_id=ticket.id,
                action=f"Commented on ticket #{ticket.id}",
                timestamp=comment_time,
            ))
        db.session.add_all(audit_entries)
        db.session.commit()

        print(f"Seeded {len(users)} users and {len(tickets)} tickets.")
        print()
        print("Demo login credentials (all use the same password):")
        print(f"  password: {DEMO_PASSWORD}")
        for username, _, role in USERS:
            print(f"  {username:16s} -> {role}")


if __name__ == "__main__":
    run()
