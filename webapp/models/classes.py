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
    family_system_id = db.Column(db.String(20), nullable=True)  # Family System ID for family classes (e.g., FAM-XXXXX)
    group_system_id = db.Column(db.String(20), nullable=True)  # Group System ID for group classes (e.g., GRO-XXXXX)


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
    student_system_id = db.Column(db.String(20), nullable=True)  # Student System ID for login (e.g., STU-00452)
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
    CRITICAL: Ensures true uniqueness with database-level checking
    """
    from .users import User
    from ..extensions import db
    
    # Use a transaction to ensure atomicity
    max_attempts = 100  # Prevent infinite loop
    attempt = 0
    
    while attempt < max_attempts:
        # Get all existing student IDs in a single query
        existing_users = User.query.filter(
            User.student_id.isnot(None),
            User.student_id.like('STU-%')
        ).all()
        
        existing_ids = [u.student_id for u in existing_users if u.student_id and u.student_id.startswith('STU-')]
        
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
        
        # CRITICAL: Check uniqueness at database level before returning
        existing_user = User.query.filter_by(student_id=student_id).first()
        if not existing_user:
            # This ID is available - return it
            return student_id
        
        # If we get here, the ID exists - try next number
        next_number += 1
        attempt += 1
    
    # Fallback: If we've tried 100 times, something is very wrong
    # Generate a random suffix to ensure uniqueness
    import random
    random_suffix = random.randint(10000, 99999)
    student_id = f"STU-{random_suffix:05d}"
    
    # Final check
    if User.query.filter_by(student_id=student_id).first():
        # Last resort: use timestamp-based ID
        from datetime import datetime
        timestamp = int(datetime.utcnow().timestamp()) % 100000
        student_id = f"STU-{timestamp:05d}"
    
    return student_id


def generate_family_system_id():
    """
    Generate a unique Family System ID for family class enrollments
    Format: FAM-XXXXX (5-digit number)
    """
    # Get all existing family system IDs
    existing_ids = [e.family_system_id for e in ClassEnrollment.query.filter(
        ClassEnrollment.family_system_id.isnot(None)
    ).all() if e.family_system_id and e.family_system_id.startswith('FAM-')]
    
    if existing_ids:
        # Extract numbers from existing IDs and find the max
        numbers = []
        for fid in existing_ids:
            try:
                num = int(fid.split('-')[1])
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
    family_id = f"FAM-{next_number:05d}"
    
    # Double-check uniqueness
    while ClassEnrollment.query.filter_by(family_system_id=family_id).first():
        next_number += 1
        family_id = f"FAM-{next_number:05d}"
    
    return family_id


class ClassTime(db.Model):
    """Model for storing class time slots for different class types"""
    id = db.Column(db.Integer, primary_key=True)
    class_type = db.Column(db.String(20), nullable=False)  # 'individual', 'family', 'group', 'school'
    class_id = db.Column(db.Integer, nullable=True)  # Specific class ID (optional, can be None for general slots)
    day = db.Column(db.String(20), nullable=False)  # Monday, Tuesday, etc.
    start_time = db.Column(db.Time, nullable=False)  # e.g., 16:00
    end_time = db.Column(db.Time, nullable=False)  # e.g., 17:30
    timezone = db.Column(db.String(50), nullable=False, default='Asia/Kolkata')  # Admin's timezone (e.g., 'Asia/Kolkata', 'Africa/Banjul', 'Europe/London')
    is_selectable = db.Column(db.Boolean, default=True)  # True for Individual/Family, False for Group/School
    is_active = db.Column(db.Boolean, default=True)
    max_capacity = db.Column(db.Integer, nullable=True)  # Optional: max students for this time slot
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    def __repr__(self):
        return f'<ClassTime {self.day} {self.start_time}-{self.end_time} ({self.class_type})>'
    
    def get_display_time(self, target_timezone=None):
        """Format time as HH:MM - HH:MM, optionally converted to target timezone"""
        from datetime import time as dt_time
        import pytz
        
        start_time = self.start_time
        end_time = self.end_time
        
        # Convert to target timezone if provided
        if target_timezone and self.timezone:
            try:
                # Create datetime objects for conversion (using today's date)
                from datetime import datetime, date
                today = date.today()
                admin_tz = pytz.timezone(self.timezone)
                target_tz = pytz.timezone(target_timezone)
                
                # Combine date and time
                start_dt = admin_tz.localize(datetime.combine(today, start_time))
                end_dt = admin_tz.localize(datetime.combine(today, end_time))
                
                # Convert to target timezone
                start_dt_target = start_dt.astimezone(target_tz)
                end_dt_target = end_dt.astimezone(target_tz)
                
                start_time = start_dt_target.time()
                end_time = end_dt_target.time()
            except Exception:
                # If conversion fails, use original time
                pass
        
        if isinstance(start_time, dt_time):
            start_str = start_time.strftime('%H:%M')
        else:
            start_str = str(start_time) if start_time else 'N/A'
        
        if isinstance(end_time, dt_time):
            end_str = end_time.strftime('%H:%M')
        else:
            end_str = str(end_time) if end_time else 'N/A'
        
        return f"{start_str} – {end_str}"
    
    def get_full_display(self, target_timezone=None):
        """Format as 'Day HH:MM – HH:MM', optionally converted to target timezone"""
        return f"{self.day} {self.get_display_time(target_timezone)}"
    
    def get_timezone_name(self):
        """Get human-readable timezone name"""
        import pytz
        try:
            tz = pytz.timezone(self.timezone)
            # Get common timezone names
            tz_names = {
                'Asia/Kolkata': 'India (IST)',
                'Africa/Banjul': 'Gambia (GMT)',
                'Europe/London': 'UK (GMT/BST)',
                'America/New_York': 'USA Eastern (EST/EDT)',
                'America/Los_Angeles': 'USA Pacific (PST/PDT)',
            }
            return tz_names.get(self.timezone, self.timezone.replace('_', ' '))
        except Exception:
            return self.timezone


class StudentClassTimeSelection(db.Model):
    """Model for storing student time selections (Individual and Family only)"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('class_enrollment.id'), nullable=False)
    class_time_id = db.Column(db.Integer, db.ForeignKey('class_time.id'), nullable=False)
    class_type = db.Column(db.String(20), nullable=False)  # 'individual' or 'family'
    selected_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', lazy='select')
    enrollment = db.relationship('ClassEnrollment', lazy='select')
    class_time = db.relationship('ClassTime', lazy='select')
    
    # Unique constraint: one selection per enrollment
    __table_args__ = (db.UniqueConstraint('enrollment_id', name='unique_enrollment_time_selection'),)
    
    def __repr__(self):
        return f'<StudentClassTimeSelection user_id={self.user_id} time_id={self.class_time_id}>'


def generate_group_system_id():
    """
    Generate a unique Group System ID for group class enrollments
    Format: GRO-XXXXX (6-character alphanumeric, similar to FAM-8KD29A format)
    """
    import secrets
    import string
    
    # Generate a 6-character alphanumeric code
    alphabet = string.ascii_uppercase + string.digits
    # Exclude similar-looking characters: 0, O, I, 1
    alphabet = ''.join(c for c in alphabet if c not in '0O1I')
    
    # Get all existing group system IDs
    existing_ids = [e.group_system_id for e in ClassEnrollment.query.filter(
        ClassEnrollment.group_system_id.isnot(None)
    ).all() if e.group_system_id and e.group_system_id.startswith('GRO-')]
    
    # Generate a unique ID
    max_attempts = 1000
    for _ in range(max_attempts):
        # Generate 6-character code
        code = ''.join(secrets.choice(alphabet) for _ in range(6))
        group_id = f"GRO-{code}"
        
        # Check if it's unique
        if group_id not in existing_ids and not ClassEnrollment.query.filter_by(group_system_id=group_id).first():
            return group_id
    
    # Fallback: use numeric format if random generation fails
    existing_numeric = []
    for gid in existing_ids:
        try:
            # Try to extract numeric part if it's numeric format
            if len(gid) == 10 and gid.startswith('GRO-'):
                num = int(gid.split('-')[1])
                existing_numeric.append(num)
        except (ValueError, IndexError):
            continue
    
    next_number = max(existing_numeric) + 1 if existing_numeric else 1
    group_id = f"GRO-{next_number:05d}"
    
    # Double-check uniqueness
    while ClassEnrollment.query.filter_by(group_system_id=group_id).first():
        next_number += 1
        group_id = f"GRO-{next_number:05d}"
    
    return group_id