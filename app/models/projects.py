from datetime import datetime
from ..extensions import db


class RoboticsProjectSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    location = db.Column(db.String(100))
    education_level = db.Column(db.String(50), nullable=False)

    project_title = db.Column(db.String(200), nullable=False)
    project_description = db.Column(db.Text, nullable=False)
    problem_solved = db.Column(db.Text)
    components = db.Column(db.Text)
    progress = db.Column(db.Text)
    project_goal = db.Column(db.Text)

    help_needed = db.Column(db.Text)
    additional_comments = db.Column(db.Text)
    uploaded_files = db.Column(db.Text)

    status = db.Column(db.String(20), default='pending')
    admin_notes = db.Column(db.Text)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    reviewed_at = db.Column(db.DateTime)

    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
