from datetime import datetime
from ..extensions import db


individual_class_students = db.Table(
    'individual_class_students',
    db.Column('class_id', db.Integer, db.ForeignKey('individual_class.id'), primary_key=True),
    db.Column('student_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
)

group_class_students = db.Table(
    'group_class_students',
    db.Column('class_id', db.Integer, db.ForeignKey('group_class.id'), primary_key=True),
    db.Column('student_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
)


class ClassEnrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    class_id = db.Column(db.Integer, nullable=False)
    class_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    payment_method = db.Column(db.String(50))
    transaction_id = db.Column(db.String(100))
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    customer_name = db.Column(db.String(100))
    customer_phone = db.Column(db.String(20))
    customer_email = db.Column(db.String(120))
    customer_address = db.Column(db.Text)
    payment_proof = db.Column(db.String(255))


class IndividualClass(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to students through association table
    students = db.relationship('User', secondary=individual_class_students, 
                               lazy='select', backref='individual_classes')


class GroupClass(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    max_students = db.Column(db.Integer, default=100)
    class_type = db.Column(db.String(20), nullable=False, default='group')  # 'individual', 'group', 'family', 'school'
    instructor_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to students through association table
    students = db.relationship('User', secondary=group_class_students, 
                              lazy='select', backref='group_classes')


class Attendance(db.Model):
    """Model for tracking student attendance"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    class_id = db.Column(db.Integer, nullable=False)  # Can be IndividualClass or GroupClass ID
    class_type = db.Column(db.String(20), nullable=False)  # 'individual', 'group', 'family', 'school'
    attendance_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    status = db.Column(db.String(20), nullable=False, default='present')  # 'present', 'absent', 'late'
    marked_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Who marked it (student or admin)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    student = db.relationship('User', foreign_keys=[student_id], lazy='select')
    marker = db.relationship('User', foreign_keys=[marked_by], lazy='select')
    
    # Unique constraint: one attendance record per student per class per day
    __table_args__ = (db.UniqueConstraint('student_id', 'class_id', 'attendance_date', name='unique_attendance'),)


class SchoolStudent(db.Model):
    """Model for students registered by schools within a classroom"""
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('class_enrollment.id'), nullable=False)
    class_id = db.Column(db.Integer, nullable=False)
    school_name = db.Column(db.String(200), nullable=False)
    student_name = db.Column(db.String(100), nullable=False)
    student_age = db.Column(db.Integer)
    student_image_url = db.Column(db.String(500))
    student_email = db.Column(db.String(120))
    student_phone = db.Column(db.String(20))
    parent_name = db.Column(db.String(100))
    parent_phone = db.Column(db.String(20))
    parent_email = db.Column(db.String(120))
    additional_info = db.Column(db.Text)  # Any other information about the student
    registered_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # The school admin who registered
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    enrollment = db.relationship('ClassEnrollment', lazy='select')
    registrar = db.relationship('User', foreign_keys=[registered_by], lazy='select')


class FamilyMember(db.Model):
    """Model for family members registered within a family class"""
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('class_enrollment.id'), nullable=False)
    class_id = db.Column(db.Integer, nullable=False)
    member_name = db.Column(db.String(100), nullable=False)
    member_age = db.Column(db.Integer)
    member_image_url = db.Column(db.String(500))
    member_email = db.Column(db.String(120))
    member_phone = db.Column(db.String(20))
    relationship = db.Column(db.String(50))  # e.g., 'Son', 'Daughter', 'Brother', 'Sister', etc.
    additional_info = db.Column(db.Text)
    registered_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # The family head who registered
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    enrollment = db.relationship('ClassEnrollment', lazy='select')
    registrar = db.relationship('User', foreign_keys=[registered_by], lazy='select')
    
    # Note: Maximum 4 family members per enrollment is enforced in application code
    # (PostgreSQL doesn't support subqueries in CHECK constraints)


# ID Generation functions for Group, Family, and Individual classes
import secrets
import string

def generate_student_id_for_class(class_type='individual'):
    """
    Generate a unique Student ID for Group, Family, or Individual classes
    Format: STU-XXXXX (5-digit number)
    """
    from .users import User
    
    # Get all existing student IDs
    existing_ids = [u.student_id for u in User.query.filter(
        User.student_id.isnot(None)
    ).all() if u.student_id and u.student_id.startswith('STU-')]
    
    if existing_ids:
        # Extract numbers from existing IDs and find the max
        numbers = []
        for sid in existing_ids:
            try:
                num = int(sid.split('-')[1])
                numbers.append(num)
            except (ValueError, IndexError):
                continue
        
        if numbers:
            next_number = max(numbers) + 1
        else:
            next_number = 1
    else:
        next_number = 1
    
    # Format as 5-digit number with leading zeros
    student_id = f"STU-{next_number:05d}"
    
    # Double-check uniqueness (shouldn't happen, but safety check)
    while User.query.filter_by(student_id=student_id).first():
        next_number += 1
        student_id = f"STU-{next_number:05d}"
    
    return student_id