from datetime import datetime
from ..extensions import db


class StudentProject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500))
    youtube_url = db.Column(db.String(500))
    project_link = db.Column(db.String(500))

    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student = db.relationship('User', foreign_keys=[student_id], lazy='select')

    is_active = db.Column(db.Boolean, default=True)
    featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    likes = db.relationship('ProjectLike', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('ProjectComment', backref='project', lazy='dynamic', cascade='all, delete-orphan')

    def get_like_count(self):
        return self.likes.filter_by(is_like=True).count()

    def get_dislike_count(self):
        return self.likes.filter_by(is_like=False).count()

    def get_comment_count(self):
        return self.comments.count()

    def user_reaction(self, user_id):
        if not user_id:
            return None
        like = self.likes.filter_by(user_id=user_id).first()
        return like.is_like if like else None


class ProjectLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('student_project.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_like = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ProjectComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('student_project.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
