from app.models import Ticket
from tests.conftest import login


def create_ticket(db, creator, assignee=None, **kwargs):
    ticket = Ticket(
        title=kwargs.get("title", "Sample ticket"),
        description="Something needs fixing",
        priority=kwargs.get("priority", "medium"),
        status=kwargs.get("status", "open"),
        created_by_id=creator.id,
        assigned_to_id=assignee.id if assignee else None,
    )
    db.session.add(ticket)
    db.session.commit()
    return ticket


def test_dashboard_requires_login(client):
    resp = client.get("/tickets/", follow_redirects=True)
    assert resp.status_code == 200
    # Redirected to the login page rather than shown the dashboard.
    assert b"Log In" in resp.data


def test_requester_cannot_view_another_requesters_ticket(client, db, users):
    other_ticket = create_ticket(db, creator=users["other_requester"])

    login(client, "test_requester")
    resp = client.get(f"/tickets/{other_ticket.id}")

    assert resp.status_code == 403


def test_requester_can_view_own_ticket(client, db, users):
    own_ticket = create_ticket(db, creator=users["requester"])

    login(client, "test_requester")
    resp = client.get(f"/tickets/{own_ticket.id}")

    assert resp.status_code == 200


def test_requester_dashboard_only_shows_own_tickets(client, db, users):
    mine = create_ticket(db, creator=users["requester"], title="Mine")
    create_ticket(db, creator=users["other_requester"], title="Not mine")

    login(client, "test_requester")
    resp = client.get("/tickets/")

    assert resp.status_code == 200
    assert b"Mine" in resp.data
    assert b"Not mine" not in resp.data


def test_agent_cannot_view_ticket_not_assigned_to_them(client, db, users):
    ticket = create_ticket(db, creator=users["requester"], assignee=users["other_agent"])

    login(client, "test_agent")
    resp = client.get(f"/tickets/{ticket.id}")

    assert resp.status_code == 403


def test_agent_can_view_ticket_assigned_to_them(client, db, users):
    ticket = create_ticket(db, creator=users["requester"], assignee=users["agent"])

    login(client, "test_agent")
    resp = client.get(f"/tickets/{ticket.id}")

    assert resp.status_code == 200


def test_agent_cannot_reassign_ticket(client, db, users):
    ticket = create_ticket(db, creator=users["requester"], assignee=users["agent"])

    login(client, "test_agent")
    resp = client.post(
        f"/tickets/{ticket.id}",
        data={
            "status": "in_progress",
            "priority": "medium",
            "assigned_to_id": users["other_agent"].id,  # attempt to hand it off
            "update_submit": "Update Ticket",
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    refreshed = Ticket.query.get(ticket.id)
    # Status change goes through, but the assignment must NOT change.
    assert refreshed.status == "in_progress"
    assert refreshed.assigned_to_id == users["agent"].id


def test_admin_can_view_any_ticket(client, db, users):
    ticket = create_ticket(db, creator=users["requester"], assignee=users["agent"])

    login(client, "test_admin")
    resp = client.get(f"/tickets/{ticket.id}")

    assert resp.status_code == 200


def test_admin_can_reassign_ticket(client, db, users):
    ticket = create_ticket(db, creator=users["requester"], assignee=users["agent"])

    login(client, "test_admin")
    resp = client.post(
        f"/tickets/{ticket.id}",
        data={
            "status": "open",
            "priority": "medium",
            "assigned_to_id": users["other_agent"].id,
            "update_submit": "Update Ticket",
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    refreshed = Ticket.query.get(ticket.id)
    assert refreshed.assigned_to_id == users["other_agent"].id


def test_reports_page_is_admin_only(client, db, users):
    create_ticket(db, creator=users["requester"])

    login(client, "test_agent")
    assert client.get("/tickets/reports").status_code == 403
    client.get("/auth/logout")

    login(client, "test_requester")
    assert client.get("/tickets/reports").status_code == 403
    client.get("/auth/logout")

    login(client, "test_admin")
    assert client.get("/tickets/reports").status_code == 200
