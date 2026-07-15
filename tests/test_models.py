from datetime import datetime, timedelta

from app.models import Ticket, SLA_HOURS


def make_ticket(db, users, priority="medium", status="open", created_hours_ago=0, resolved_hours_after=None):
    created_at = datetime.utcnow() - timedelta(hours=created_hours_ago)
    ticket = Ticket(
        title="Test ticket",
        description="Something broke",
        priority=priority,
        status=status,
        created_by_id=users["requester"].id,
        assigned_to_id=users["agent"].id,
        created_at=created_at,
        updated_at=created_at,
    )
    if resolved_hours_after is not None:
        ticket.resolved_at = created_at + timedelta(hours=resolved_hours_after)
        ticket.updated_at = ticket.resolved_at
    db.session.add(ticket)
    db.session.commit()
    return ticket


def test_ticket_can_be_created(db, users):
    ticket = make_ticket(db, users, priority="high")
    fetched = Ticket.query.get(ticket.id)

    assert fetched is not None
    assert fetched.title == "Test ticket"
    assert fetched.status == "open"
    assert fetched.priority == "high"
    assert fetched.created_by_id == users["requester"].id
    assert fetched.assigned_to_id == users["agent"].id


def test_sla_deadline_matches_priority_hours(db, users):
    for priority, hours in SLA_HOURS.items():
        ticket = make_ticket(db, users, priority=priority, created_hours_ago=0)
        expected = ticket.created_at + timedelta(hours=hours)
        assert ticket.sla_deadline == expected


def test_sla_status_on_time_when_freshly_created(db, users):
    # High priority (4h SLA), created 30 minutes ago -> well within window.
    ticket = make_ticket(db, users, priority="high", created_hours_ago=0.5)
    assert ticket.sla_status == "on_time"
    assert ticket.is_overdue is False


def test_sla_status_at_risk_past_threshold(db, users):
    # High priority (4h SLA), created 3.5h ago -> 87.5% of window elapsed.
    ticket = make_ticket(db, users, priority="high", created_hours_ago=3.5)
    assert ticket.sla_status == "at_risk"
    assert ticket.is_overdue is False


def test_sla_status_breached_after_deadline(db, users):
    # High priority (4h SLA), created 5h ago -> past the deadline.
    ticket = make_ticket(db, users, priority="high", created_hours_ago=5)
    assert ticket.sla_status == "breached"
    assert ticket.is_overdue is True


def test_sla_status_ignores_current_time_once_resolved_on_time(db, users):
    # Created 100h ago (way past any deadline *now*), but resolved after
    # just 2 of its 4 allotted hours -> should read as on_time, not breached,
    # because what matters is whether it was resolved within the window.
    ticket = make_ticket(
        db, users, priority="high", status="resolved",
        created_hours_ago=100, resolved_hours_after=2,
    )
    assert ticket.sla_status == "on_time"


def test_sla_status_breached_if_resolved_after_deadline(db, users):
    # Resolved, but only after 6 hours against a 4-hour SLA.
    ticket = make_ticket(
        db, users, priority="high", status="resolved",
        created_hours_ago=100, resolved_hours_after=6,
    )
    assert ticket.sla_status == "breached"


def test_resolution_time_hours_is_none_until_resolved(db, users):
    ticket = make_ticket(db, users, priority="medium", created_hours_ago=1)
    assert ticket.resolution_time_hours is None

    ticket.resolved_at = ticket.created_at + timedelta(hours=3)
    assert ticket.resolution_time_hours == 3.0
