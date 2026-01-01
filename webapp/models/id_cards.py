from datetime import datetime
import qrcode
import io
import base64
from flask import url_for, current_app
from ..extensions import db


class IDCard(db.Model):
    """Model for storing generated ID cards"""
    __tablename__ = 'id_card'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Entity type and reference
    entity_type = db.Column(db.String(20), nullable=False)  # 'individual', 'group', 'family', 'school', 'school_student'
    entity_id = db.Column(db.Integer, nullable=False)  # ID of the entity (user_id, enrollment_id, school_id, etc.)
    
    # ID Card data
    system_id = db.Column(db.String(20), nullable=False)  # System ID (STU-XXXXX, FAM-XXXXX, SCH-XXXXX, etc.)
    name = db.Column(db.String(200), nullable=False)  # Name of the entity
    photo_url = db.Column(db.String(500), nullable=True)  # Profile photo or school logo URL
    
    # Additional information (stored as JSON-like fields for flexibility)
    class_name = db.Column(db.String(200), nullable=True)  # Class name (for students)
    school_name = db.Column(db.String(200), nullable=True)  # School name (for school students)
    school_system_id = db.Column(db.String(20), nullable=True)  # School System ID (for school students)
    group_system_id = db.Column(db.String(20), nullable=True)  # Group System ID (for group students)
    family_system_id = db.Column(db.String(20), nullable=True)  # Family System ID (for family members)
    
    # Contact information
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    
    # Guardian/Parent info (for students)
    guardian_name = db.Column(db.String(100), nullable=True)
    guardian_contact = db.Column(db.String(20), nullable=True)
    
    # Registration/Approval info
    registration_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    approved_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # QR Code (future-ready)
    qr_code_data = db.Column(db.Text, nullable=True)  # QR code data/URL
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_locked = db.Column(db.Boolean, default=False)  # Locked after initial generation (except photo/logo)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    approver = db.relationship('User', foreign_keys=[approved_by], lazy='select')
    
    def __repr__(self):
        return f'<IDCard {self.entity_type}: {self.system_id}>'
    
    def get_display_name(self):
        """Get display name based on entity type"""
        if self.entity_type == 'school':
            return f"{self.name} (School)"
        elif self.entity_type == 'school_student':
            return f"{self.name} (School Student)"
        elif self.entity_type == 'individual':
            return f"{self.name} (Individual Student)"
        elif self.entity_type == 'group':
            return f"{self.name} (Group Student)"
        elif self.entity_type == 'family':
            return f"{self.name} (Family)"
        return self.name
    
    def generate_qr_code_url(self, base_url='https://edu.techbuxin.com'):
        """Generate QR code URL that redirects to student dashboard"""
        from flask import url_for
        # Generate URL that will set session and redirect to dashboard
        return f"{base_url}/qr/{self.id}"


# ID Card Generation Functions
def generate_individual_student_id_card(enrollment, user, class_obj, approved_by_user_id):
    """Generate ID card for individual student after approval"""
    from .users import User
    
    # Check if ID card already exists
    existing_card = IDCard.query.filter_by(
        entity_type='individual',
        entity_id=user.id,
        system_id=user.student_id
    ).first()
    
    if existing_card:
        # Update QR code if missing
        if not existing_card.qr_code_data:
            with current_app.app_context():
                qr_url = url_for('main.qr_code_redirect', id_card_id=existing_card.id, _external=True)
                existing_card.qr_code_data = qr_url
                db.session.add(existing_card)
                db.session.commit()
        # Update system_id if it was 'N/A' or missing
        if existing_card.system_id == 'N/A' or not existing_card.system_id:
            existing_card.system_id = user.student_id or 'N/A'
            db.session.add(existing_card)
            db.session.commit()
        return existing_card
    
    # Get class name
    class_name = class_obj.name if class_obj else 'Individual Class'
    
    # CRITICAL: Ensure student_id is set before creating ID card
    if not user.student_id:
        raise ValueError(f"User {user.id} does not have a student_id. Cannot create ID card.")
    
    # Create ID card
    id_card = IDCard(
        entity_type='individual',
        entity_id=user.id,
        system_id=user.student_id,  # Never use 'N/A' - student_id must be set
        name=f"{user.first_name} {user.last_name}",
        photo_url=user.profile_picture,
        class_name=class_name,
        email=user.email,
        phone=user.whatsapp_number,
        registration_date=enrollment.enrolled_at,
        approved_at=datetime.utcnow(),
        approved_by=approved_by_user_id,
        is_active=True,
        is_locked=False,
        qr_code_data=None  # Will be set after we get the ID
    )
    
    db.session.add(id_card)
    db.session.flush()  # Get ID without committing
    
    # Generate QR code URL now that we have the ID
    # Use url_for within app context
    try:
        with current_app.app_context():
            qr_url = url_for('main.qr_code_redirect', id_card_id=id_card.id, _external=True)
        id_card.qr_code_data = qr_url
    except Exception as e:
        print(f"Error generating QR code URL: {e}")
        # Continue without QR code - it can be added later
    
    db.session.commit()
    return id_card


def generate_group_student_id_card(enrollment, user, class_obj, approved_by_user_id):
    """Generate ID card for group student after approval"""
    # CRITICAL: Group students use group_system_id (GRO-XXXXX), NOT individual student_id (STU-XXXXX)
    if not enrollment.group_system_id:
        raise ValueError(f"Enrollment {enrollment.id} does not have a group_system_id. Cannot create ID card.")
    
    # Check if ID card already exists (using group_system_id as system_id)
    existing_card = IDCard.query.filter_by(
        entity_type='group',
        entity_id=user.id,
        system_id=enrollment.group_system_id
    ).first()
    
    if existing_card:
        # Update QR code if missing
        if not existing_card.qr_code_data:
            with current_app.app_context():
                qr_url = url_for('main.qr_code_redirect', id_card_id=existing_card.id, _external=True)
                existing_card.qr_code_data = qr_url
                db.session.add(existing_card)
                db.session.commit()
        # Update system_id if it was wrong (should be group_system_id, not student_id)
        if existing_card.system_id != enrollment.group_system_id:
            existing_card.system_id = enrollment.group_system_id
            db.session.add(existing_card)
            db.session.commit()
        return existing_card
    
    # Get class name
    class_name = class_obj.name if class_obj else 'Group Class'
    
    # Create ID card - use group_system_id as the system_id
    id_card = IDCard(
        entity_type='group',
        entity_id=user.id,
        system_id=enrollment.group_system_id,  # Use group_system_id, NOT individual student_id
        name=f"{user.first_name} {user.last_name}",
        photo_url=user.profile_picture,
        class_name=class_name,
        group_system_id=enrollment.group_system_id,
        email=user.email,
        phone=user.whatsapp_number,
        registration_date=enrollment.enrolled_at,
        approved_at=datetime.utcnow(),
        approved_by=approved_by_user_id,
        is_active=True,
        is_locked=False,
        qr_code_data=None  # Will be set after we get the ID
    )
    
    db.session.add(id_card)
    db.session.flush()  # Get ID without committing
    
    # Generate QR code URL now that we have the ID
    try:
        with current_app.app_context():
            qr_url = url_for('main.qr_code_redirect', id_card_id=id_card.id, _external=True)
        id_card.qr_code_data = qr_url
    except Exception as e:
        print(f"Error generating QR code URL: {e}")
        # Continue without QR code - it can be added later
    
    db.session.commit()
    return id_card


def generate_family_id_card(enrollment, user, class_obj, approved_by_user_id):
    """Generate ID card for family after approval"""
    from .classes import FamilyMember
    
    # Check if ID card already exists
    existing_card = IDCard.query.filter_by(
        entity_type='family',
        entity_id=enrollment.id,
        system_id=enrollment.family_system_id
    ).first()
    
    if existing_card:
        return existing_card
    
    # Get class name
    class_name = class_obj.name if class_obj else 'Family Class'
    
    # Get family members
    family_members = FamilyMember.query.filter_by(enrollment_id=enrollment.id).all()
    
    # Create ID card
    id_card = IDCard(
        entity_type='family',
        entity_id=enrollment.id,
        system_id=enrollment.family_system_id or 'N/A',
        name=f"{user.first_name} {user.last_name}'s Family",
        photo_url=user.profile_picture,
        class_name=class_name,
        family_system_id=enrollment.family_system_id,
        email=user.email,
        phone=user.whatsapp_number,
        guardian_name=user.first_name + ' ' + user.last_name,
        guardian_contact=user.whatsapp_number,
        registration_date=enrollment.enrolled_at,
        approved_at=datetime.utcnow(),
        approved_by=approved_by_user_id,
        is_active=True,
        is_locked=False,
        qr_code_data=None  # Will be set after we get the ID
    )
    
    db.session.add(id_card)
    db.session.flush()  # Get ID without committing
    
    # Generate QR code URL now that we have the ID
    # Use url_for within app context
    with current_app.app_context():
        qr_url = url_for('main.qr_code_redirect', id_card_id=id_card.id, _external=True)
    id_card.qr_code_data = qr_url
    
    db.session.commit()
    return id_card


def generate_school_id_card(school, approved_by_user_id):
    """Generate ID card for school after approval"""
    # Check if ID card already exists
    existing_card = IDCard.query.filter_by(
        entity_type='school',
        entity_id=school.id,
        system_id=school.school_system_id
    ).first()
    
    if existing_card:
        return existing_card
    
    # Get school logo (if available)
    school_logo = None  # TODO: Add school logo field to School model if needed
    
    # Create ID card
    id_card = IDCard(
        entity_type='school',
        entity_id=school.id,
        system_id=school.school_system_id,
        name=school.school_name,
        photo_url=school_logo,
        email=school.school_email,
        phone=school.contact_phone,
        guardian_name=school.admin_name,  # Using admin_name as mentor/admin
        guardian_contact=school.admin_phone,
        registration_date=school.created_at,
        approved_at=school.approved_at or datetime.utcnow(),
        approved_by=approved_by_user_id,
        is_active=True,
        is_locked=False,
        qr_code_data=None  # Will be set after we get the ID
    )
    
    db.session.add(id_card)
    db.session.flush()  # Get ID without committing
    
    # Generate QR code URL now that we have the ID
    # Use url_for within app context
    with current_app.app_context():
        qr_url = url_for('main.qr_code_redirect', id_card_id=id_card.id, _external=True)
    id_card.qr_code_data = qr_url
    
    db.session.commit()
    return id_card


def generate_school_student_id_card(registered_student, school, approved_by_user_id):
    """Generate ID card for school student after approval
    Works with both SchoolStudent and RegisteredSchoolStudent models
    """
    from .classes import ClassEnrollment, SchoolStudent
    
    # Check if ID card already exists
    existing_card = IDCard.query.filter_by(
        entity_type='school_student',
        entity_id=registered_student.id,
        system_id=registered_student.student_system_id
    ).first()
    
    if existing_card:
        return existing_card
    
    # Get class name(s) from enrollment
    # Try to get enrollment from student's enrollment_id if it's a SchoolStudent
    enrollment = None
    if hasattr(registered_student, 'enrollment_id') and registered_student.enrollment_id:
        # This is a SchoolStudent with direct enrollment_id
        enrollment = ClassEnrollment.query.get(registered_student.enrollment_id)
    else:
        # This is a RegisteredSchoolStudent - get enrollment from school
        enrollment = ClassEnrollment.query.filter_by(
            user_id=school.user_id,
            class_type='school',
            status='completed'
        ).first()
    
    class_name = None
    if enrollment:
        from .classes import GroupClass
        class_obj = GroupClass.query.get(enrollment.class_id)
        if class_obj:
            class_name = class_obj.name
    
    # Create ID card
    id_card = IDCard(
        entity_type='school_student',
        entity_id=registered_student.id,
        system_id=registered_student.student_system_id,
        name=registered_student.student_name,
        photo_url=registered_student.student_image_url,
        class_name=class_name,
        school_name=school.school_name,
        school_system_id=school.school_system_id,
        email=registered_student.student_email,
        phone=registered_student.student_phone,
        guardian_name=registered_student.parent_name,
        guardian_contact=registered_student.parent_phone,
        registration_date=registered_student.created_at,
        approved_at=datetime.utcnow(),
        approved_by=approved_by_user_id,
        is_active=True,
        is_locked=False,
        qr_code_data=None  # Will be set after we get the ID
    )
    
    db.session.add(id_card)
    db.session.flush()  # Get ID without committing
    
    # Generate QR code URL now that we have the ID
    # Use url_for within app context
    with current_app.app_context():
        qr_url = url_for('main.qr_code_redirect', id_card_id=id_card.id, _external=True)
    id_card.qr_code_data = qr_url
    
    db.session.commit()
    return id_card

