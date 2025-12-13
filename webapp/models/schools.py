from datetime import datetime
import secrets
import string
from ..extensions import db


class School(db.Model):
    """Model for registered schools"""
    __tablename__ = 'school'
    
    id = db.Column(db.Integer, primary_key=True)
    school_system_id = db.Column(db.String(20), unique=True, nullable=False)
    school_name = db.Column(db.String(200), nullable=False)
    school_email = db.Column(db.String(120), nullable=False)
    contact_phone = db.Column(db.String(20))
    contact_address = db.Column(db.Text)
    
    # Admin information
    admin_name = db.Column(db.String(100), nullable=False)
    admin_email = db.Column(db.String(120), nullable=False)
    admin_phone = db.Column(db.String(20))
    
    # Status and payment
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, active, rejected
    payment_status = db.Column(db.String(20), default='pending')  # pending, completed, failed
    payment_proof = db.Column(db.String(500))
    
    # User account (the school admin user account)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], lazy='select')
    approver = db.relationship('User', foreign_keys=[approved_by], lazy='select')
    students = db.relationship('RegisteredSchoolStudent', backref='school', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<School {self.school_system_id}: {self.school_name}>'
    
    def is_active(self):
        return self.status == 'active'
    
    def is_pending(self):
        return self.status == 'pending'


class RegisteredSchoolStudent(db.Model):
    """Model for students registered within a school (with School System ID)"""
    __tablename__ = 'school_student_registered'
    
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=False)
    student_system_id = db.Column(db.String(20), nullable=False)  # e.g., STU-00452
    student_number = db.Column(db.Integer, nullable=False)  # Sequential number within school
    
    # Student information
    student_name = db.Column(db.String(100), nullable=False)
    student_email = db.Column(db.String(120))
    student_phone = db.Column(db.String(20))
    student_age = db.Column(db.Integer)
    student_image_url = db.Column(db.String(500))
    
    # Parent/Guardian information
    parent_name = db.Column(db.String(100))
    parent_email = db.Column(db.String(120))
    parent_phone = db.Column(db.String(20))
    
    # Additional info
    additional_info = db.Column(db.Text)
    
    # User account (if student creates an account)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    registered_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], lazy='select')
    registrar = db.relationship('User', foreign_keys=[registered_by], lazy='select')
    
    # Unique constraint: student_system_id must be unique within a school
    __table_args__ = (db.UniqueConstraint('school_id', 'student_system_id', name='unique_school_student_id'),)
    
    def __repr__(self):
        return f'<RegisteredSchoolStudent {self.student_system_id}: {self.student_name}>'


# ID Generation functions (defined after models to avoid circular imports)
def generate_school_id():
    """Generate a unique School System ID (e.g., SCH-9F3A21)"""
    while True:
        # Generate 6-character alphanumeric code
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        school_id = f"SCH-{code}"
        # Check if it already exists
        if not School.query.filter_by(school_system_id=school_id).first():
            return school_id


def generate_student_id(school_id):
    """Generate a unique Student System ID for a school (e.g., STU-00452)"""
    # Get the last student number for this school
    last_student = RegisteredSchoolStudent.query.filter_by(school_id=school_id).order_by(RegisteredSchoolStudent.student_number.desc()).first()
    
    if last_student and last_student.student_number:
        next_number = last_student.student_number + 1
    else:
        next_number = 1
    
    # Format as 5-digit number with leading zeros
    student_id = f"STU-{next_number:05d}"
    
    # Ensure uniqueness
    while RegisteredSchoolStudent.query.filter_by(student_system_id=student_id, school_id=school_id).first():
        next_number += 1
        student_id = f"STU-{next_number:05d}"
    
    return student_id, next_number

