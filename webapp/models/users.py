from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from ..extensions import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_student = db.Column(db.Boolean, default=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    whatsapp_number = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # School System Integration
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=True)  # If user is associated with a school
    student_system_id = db.Column(db.String(20), nullable=True)  # Student System ID if registered as student in school
    is_school_admin = db.Column(db.Boolean, default=False)  # True if this user is a school admin
    is_school_student = db.Column(db.Boolean, default=False)  # True if this user is a registered school student
    
    # General Student ID for ID-based access (Group, Family, Individual classes)
    student_id = db.Column(db.String(20), unique=True, nullable=True)  # Auto-generated Student ID for class access
    class_type = db.Column(db.String(20), nullable=True)  # 'individual', 'group', 'family', 'school' - tracks enrollment type
    
    # Profile Picture
    profile_picture = db.Column(db.String(500), nullable=True)  # URL to profile picture stored in Cloudinary

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_school(self):
        """Get the school associated with this user"""
        if self.school_id:
            from .schools import School
            return School.query.get(self.school_id)
        return None
