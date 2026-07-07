from functools import wraps
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app import db
from app.models import Ticket, User, Comment, STATUSES
from app.tickets.forms import TicketForm, TicketUpdateForm, CommentForm
from app.utils import log_action

tickets_bp = Blueprint("tickets", __name__, url_prefix="/tickets")


def tech_required(f):
    """Restrict a route to tech/admin accounts. Plain users get a 403."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_tech:
            abort(403)
        return f(*args, **kwargs)
    return wrapper


@tickets_bp.route("/")
@login_required
def dashboard():
    if current_user.is_tech:
        tickets = Ticket.query.order_by(Ticket.created_at.desc()).all()
    else:
        tickets = (
            Ticket.query.filter_by(created_by_id=current_user.id)
            .order_by(Ticket.created_at.desc())
            .all()
        )

    overdue_count = sum(1 for t in tickets if t.is_overdue)
    open_count = sum(1 for t in tickets if t.status not in ("resolved", "closed"))

    return render_template(
        "tickets/dashboard.html",
        tickets=tickets,
        overdue_count=overdue_count,
        open_count=open_count,
    )


@tickets_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = TicketForm()
    if form.validate_on_submit():
        ticket = Ticket(
            title=form.title.data,
            description=form.description.data,
            priority=form.priority.data,
            category=form.category.data,
            created_by_id=current_user.id,
        )
        db.session.add(ticket)
        db.session.commit()
        log_action(current_user.id, f"Created ticket #{ticket.id}", ticket.id)
        flash(f"Ticket #{ticket.id} submitted.", "success")
        return redirect(url_for("tickets.dashboard"))

    return render_template("tickets/create.html", form=form)


@tickets_bp.route("/<int:ticket_id>", methods=["GET", "POST"])
@login_required
def view(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)

    # A regular user may only view their own tickets.
    if not current_user.is_tech and ticket.created_by_id != current_user.id:
        abort(403)

    update_form = None
    if current_user.is_tech:
        update_form = TicketUpdateForm(obj=ticket)
        techs = User.query.filter(User.role.in_(("tech", "admin"))).all()
        update_form.assigned_to_id.choices = [(0, "Unassigned")] + [
            (t.id, t.username) for t in techs
        ]
        if update_form.validate_on_submit() and update_form.update_submit.data:
            old_status = ticket.status
            ticket.status = update_form.status.data
            ticket.priority = update_form.priority.data
            ticket.assigned_to_id = update_form.assigned_to_id.data or None

            if old_status != "resolved" and ticket.status == "resolved":
                ticket.resolved_at = datetime.utcnow()
            elif ticket.status not in ("resolved", "closed"):
                ticket.resolved_at = None

            db.session.commit()
            log_action(
                current_user.id,
                f"Updated ticket #{ticket.id} (status={ticket.status}, priority={ticket.priority})",
                ticket.id,
            )
            flash("Ticket updated.", "success")
            return redirect(url_for("tickets.view", ticket_id=ticket.id))

    comment_form = CommentForm()
    if comment_form.validate_on_submit() and comment_form.comment_submit.data:
        comment = Comment(
            ticket_id=ticket.id, user_id=current_user.id, body=comment_form.body.data
        )
        db.session.add(comment)
        db.session.commit()
        log_action(current_user.id, f"Commented on ticket #{ticket.id}", ticket.id)
        return redirect(url_for("tickets.view", ticket_id=ticket.id))

    comments = ticket.comments.order_by(Comment.created_at.asc()).all()

    return render_template(
        "tickets/view.html",
        ticket=ticket,
        update_form=update_form,
        comment_form=comment_form,
        comments=comments,
    )


@tickets_bp.route("/reports")
@login_required
@tech_required
def reports():
    all_tickets = Ticket.query.all()
    total = len(all_tickets)

    by_status = {s: sum(1 for t in all_tickets if t.status == s) for s in STATUSES}

    resolved = [t for t in all_tickets if t.resolution_time_hours is not None]
    avg_resolution = (
        round(sum(t.resolution_time_hours for t in resolved) / len(resolved), 1)
        if resolved
        else None
    )

    overdue = [t for t in all_tickets if t.is_overdue]

    by_category = {}
    for t in all_tickets:
        by_category[t.category] = by_category.get(t.category, 0) + 1

    return render_template(
        "tickets/reports.html",
        total=total,
        by_status=by_status,
        avg_resolution=avg_resolution,
        overdue=overdue,
        by_category=by_category,
    )