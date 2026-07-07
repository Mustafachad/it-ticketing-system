from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length

from app.models import PRIORITIES, CATEGORIES, STATUSES


class TicketForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=140)])
    description = TextAreaField("Description", validators=[DataRequired()])
    priority = SelectField("Priority", choices=[(p, p.title()) for p in PRIORITIES])
    category = SelectField("Category", choices=[(c, c.title()) for c in CATEGORIES])
    submit = SubmitField("Submit Ticket")


class TicketUpdateForm(FlaskForm):
    status = SelectField("Status", choices=[(s, s.replace("_", " ").title()) for s in STATUSES])
    priority = SelectField("Priority", choices=[(p, p.title()) for p in PRIORITIES])
    assigned_to_id = SelectField("Assign To", coerce=int)
    update_submit = SubmitField("Update Ticket")


class CommentForm(FlaskForm):
    body = TextAreaField("Add a comment", validators=[DataRequired()])
    comment_submit = SubmitField("Post Comment")