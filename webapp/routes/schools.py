from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_required, current_user, login_user
from werkzeug.utils import secure_filename
import cloudinary
import cloudinary.uploader
from sqlalchemy.exc import ProgrammingError, InternalError
from sqlalchemy import text

from ..extensions import db
from ..models import User, School, RegisteredSchoolStudent
from ..models.schools import generate_school_id, generate_student_id

bp = Blueprint('schools', __name__)


def check_database_setup():
    """Check if school tables exist, return error message if not"""
    try:
        # Try a simple query to check if School table exists
        db.session.execute(text("SELECT 1 FROM school LIMIT 1"))
        return None
    except (ProgrammingError, InternalError) as e:
        db.session.rollback()
        return "Database tables not set up. Please visit /admin/setup-school-tables first."
    except Exception as e:
        db.session.rollback()
        return f"Database error: {str(e)}"


@bp.route('/school/register', methods=['GET', 'POST'])
@bp.route('/register-school', methods=['GET', 'POST'])
@bp.route('/register-school/<int:class_id>', methods=['GET', 'POST'])
def register_school(class_id=None):
    """School registration form"""
    if current_user.is_authenticated and not current_user.is_admin:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        # Check database setup first
        db_error = check_database_setup()
        if db_error:
            flash(db_error, 'danger')
            return render_template('register_school.html', class_id=class_id)
        
        # School information
        school_name = request.form.get('school_name', '').strip()
        school_email = request.form.get('school_email', '').strip().lower()
        contact_phone = request.form.get('contact_phone', '').strip()
        contact_address = request.form.get('contact_address', '').strip()
        
        # Admin information
        admin_name = request.form.get('admin_name', '').strip()
        admin_email = request.form.get('admin_email', '').strip().lower()
        admin_phone = request.form.get('admin_phone', '').strip()
        
        # User account credentials
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not all([school_name, school_email, admin_name, admin_email, username, password]):
            flash('All required fields must be filled.', 'danger')
            return render_template('register_school.html', class_id=class_id)
        
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('register_school.html', class_id=class_id)
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register_school.html', class_id=class_id)
        
        try:
            # Check existing user
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash('Username already taken.', 'danger')
                return render_template('register_school.html', class_id=class_id)
            
            existing_email = User.query.filter_by(email=admin_email).first()
            if existing_email:
                flash('Email already registered.', 'danger')
                return render_template('register_school.html', class_id=class_id)
            
            # Check if school email already exists
            existing_school = School.query.filter_by(school_email=school_email).first()
            if existing_school:
                flash('School email already registered.', 'danger')
                return render_template('register_school.html', class_id=class_id)
            
            # Create user account for school admin
            user = User(
                username=username,
                email=admin_email,
                first_name=admin_name.split()[0] if admin_name.split() else admin_name,
                last_name=' '.join(admin_name.split()[1:]) if len(admin_name.split()) > 1 else '',
                is_student=False,
                is_admin=False,
                is_school_admin=True,
                class_type='school'
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()  # Get user.id
            
            # Generate School System ID
            from ..models.schools import generate_school_id
            school_system_id = generate_school_id()
            
            # Create school record
            school = School(
                school_system_id=school_system_id,
                school_name=school_name,
                school_email=school_email,
                contact_phone=contact_phone,
                contact_address=contact_address,
                admin_name=admin_name,
                admin_email=admin_email,
                admin_phone=admin_phone,
                user_id=user.id,
                status='pending',
                payment_status='pending'
            )
            db.session.add(school)
            db.session.commit()
            
            # Store data in session for payment flow
            session['pending_school_id'] = school.id
            session['school_system_id'] = school_system_id
            if class_id:
                session['pending_school_class_id'] = class_id
            
            flash(f'School registration submitted! Your School System ID is: {school_system_id}', 'success')
            return redirect(url_for('schools.school_payment'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Registration failed: {str(e)}', 'danger')
            return render_template('register_school.html', class_id=class_id)
    
    return render_template('register_school.html', class_id=class_id)


@bp.route('/school/payment', methods=['GET', 'POST'])
def school_payment():
    """School payment page"""
    from ..models.classes import ClassEnrollment, GroupClass
    from ..models.gallery import ClassPricing
    
    school_id = session.get('pending_school_id')
    school_system_id = session.get('school_system_id')
    class_id = session.get('pending_school_class_id')
    
    # Also try to get class_id from form if not in session (fallback)
    if not class_id and request.method == 'POST':
        class_id = request.form.get('class_id', type=int)
        if class_id:
            session['pending_school_class_id'] = class_id
    
    if not school_id:
        flash('No pending school registration found.', 'danger')
        return redirect(url_for('schools.register_school'))
    
    school = School.query.get(school_id)
    if not school:
        flash('School registration not found.', 'danger')
        return redirect(url_for('schools.register_school'))
    
    # Get pricing for school plan
    pricing_data = ClassPricing.get_all_pricing()
    school_pricing = pricing_data.get('school', {'price': 500, 'name': 'School Plan'})
    amount = school_pricing.get('price', 500)
    
    if request.method == 'POST':
        # Handle payment proof upload
        payment_method = request.form.get('payment_method', '')
        payment_proof_url = None
        
        if 'payment_proof' in request.files:
            file = request.files['payment_proof']
            if file and file.filename:
                from ..services.cloudinary_service import CloudinaryService
                try:
                    success, result = CloudinaryService.upload_file(
                        file=file, 
                        folder='payment_proofs',
                        resource_type='auto'
                    )
                    if success and isinstance(result, dict) and result.get('url'):
                        payment_proof_url = result['url']
                except Exception as e:
                    flash(f'Error uploading payment proof: {str(e)}', 'warning')
        
        # Update school payment status
        school.payment_status = 'completed' if payment_proof_url else 'pending'
        school.payment_proof = payment_proof_url
        
        # CRITICAL FIX: Always create enrollment record to link school to class
        # This is required for admin material sharing and school dashboard to work
        import uuid
        
        # Try multiple sources for class_id (session, form, or check existing enrollments)
        if not class_id:
            # Check if school already has any enrollments (might have been created elsewhere)
            existing_enrollments = ClassEnrollment.query.filter_by(
                user_id=school.user_id,
                class_type='school'
            ).all()
            if existing_enrollments:
                # School already has enrollments, just update payment info
                for enrollment in existing_enrollments:
                    enrollment.payment_method = payment_method
                    enrollment.payment_proof = payment_proof_url
                    enrollment.amount = amount
                class_id = None  # Don't create new enrollment
            else:
                # No enrollments exist - try to get class_id from form or URL
                class_id = request.form.get('class_id', type=int)
                if not class_id:
                    # Last resort: if no class_id available, we can't create enrollment
                    # But we'll log this for admin to fix manually
                    flash('Warning: No class selected. Please contact admin to enroll this school in a class.', 'warning')
        
        # Create enrollment if class_id is available
        if class_id:
            # Verify class exists and is a school class
            class_obj = GroupClass.query.get(class_id)
            if not class_obj:
                flash(f'Error: Class ID {class_id} not found.', 'danger')
            elif getattr(class_obj, 'class_type', None) != 'school':
                flash(f'Error: Class ID {class_id} is not a school class.', 'danger')
            else:
                # Check if enrollment already exists (avoid duplicates)
                existing_enrollment = ClassEnrollment.query.filter_by(
                    user_id=school.user_id,
                    class_type='school',
                    class_id=class_id
                ).first()
                
                if not existing_enrollment:
                    enrollment = ClassEnrollment(
                        user_id=school.user_id,
                        class_type='school',
                        class_id=class_id,
                        amount=amount,
                        customer_name=school.school_name,
                        customer_email=school.school_email,
                        customer_phone=school.contact_phone,
                        customer_address=school.contact_address,
                        payment_method=payment_method,
                        payment_proof=payment_proof_url,
                        transaction_id=str(uuid.uuid4())[:8].upper(),
                        status='pending'  # Will be set to 'completed' when admin approves the school
                    )
                    db.session.add(enrollment)
                else:
                    # Update existing enrollment with payment info
                    existing_enrollment.payment_method = payment_method
                    existing_enrollment.payment_proof = payment_proof_url
                    existing_enrollment.amount = amount
        
        db.session.commit()
        
        # Log in the school admin
        if school.user_id:
            user = User.query.get(school.user_id)
            if user:
                login_user(user)
        
        flash('Payment information submitted! Your school is pending admin approval.', 'success')
        return redirect(url_for('schools.school_pending_approval'))
    
    return render_template('school_payment.html', 
                         school=school, 
                         school_system_id=school_system_id,
                         amount=amount)


@bp.route('/school/pending-approval')
@login_required
def school_pending_approval():
    """Waiting page shown to schools until admin approval"""
    # Get school for current user
    school = School.query.filter_by(user_id=current_user.id).first()
    
    if not school:
        flash('No school registration found for your account.', 'danger')
        return redirect(url_for('main.index'))
    
    if school.status == 'active':
        # Already approved, redirect to dashboard
        return redirect(url_for('schools.school_dashboard'))
    
    if school.status == 'rejected':
        flash('Your school registration has been rejected. Please contact support.', 'danger')
        return render_template('school_pending_approval.html', school=school, rejected=True)
    
    # Still pending
    return render_template('school_pending_approval.html', school=school, rejected=False)


@bp.route('/school/dashboard')
@login_required
def school_dashboard():
    """School Mentor Dashboard - For school mentors to manage students and attendance"""
    # Verify user is a school admin (mentor)
    if not current_user.is_school_admin:
        flash('Access denied. School mentor privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    # Get school for current user
    school = School.query.filter_by(user_id=current_user.id).first()
    if not school:
        flash('No school registration found for your account.', 'danger')
        return redirect(url_for('main.index'))
    
    if school.status != 'active':
        # School not approved yet
        return redirect(url_for('schools.school_pending_approval'))
    
    # Use the unified student dashboard logic which handles school classes
    # But we'll customize the profile section in the template to show mentor info
    from .admin import student_dashboard
    return student_dashboard()


@bp.route('/school/register-student', methods=['POST'])
@login_required
def register_student_in_school():
    """Register a student within the school"""
    school = School.query.filter_by(user_id=current_user.id).first()
    
    if not school or school.status != 'active':
        flash('You do not have permission to register students.', 'danger')
        return redirect(url_for('schools.school_dashboard'))
    
    student_name = request.form.get('student_name', '').strip()
    student_email = request.form.get('student_email', '').strip()
    student_phone = request.form.get('student_phone', '').strip()
    student_age = request.form.get('student_age', type=int)
    parent_name = request.form.get('parent_name', '').strip()
    parent_email = request.form.get('parent_email', '').strip()
    parent_phone = request.form.get('parent_phone', '').strip()
    additional_info = request.form.get('additional_info', '').strip()
    
    if not student_name:
        flash('Student name is required.', 'danger')
        return redirect(url_for('schools.school_dashboard'))
    
    try:
        # Generate Student System ID
        student_system_id, student_number = generate_student_id(school.id)
        
        # Handle image upload
        student_image_url = None
        if 'student_image' in request.files:
            image_file = request.files['student_image']
            if image_file and image_file.filename:
                from ..services.cloudinary_service import CloudinaryService
                try:
                    success, result = CloudinaryService.upload_file(
                        file=image_file, 
                        folder='student_photos',
                        resource_type='auto'
                    )
                    if success and isinstance(result, dict) and result.get('url'):
                        student_image_url = result['url']
                except Exception as e:
                    flash(f'Error uploading image: {str(e)}', 'warning')
        
        # Create student record
        student = RegisteredSchoolStudent(
            school_id=school.id,
            student_system_id=student_system_id,
            student_number=student_number,
            student_name=student_name,
            student_email=student_email,
            student_phone=student_phone,
            student_age=student_age,
            student_image_url=student_image_url,
            parent_name=parent_name,
            parent_email=parent_email,
            parent_phone=parent_phone,
            additional_info=additional_info,
            registered_by=current_user.id
        )
        db.session.add(student)
        db.session.commit()
        
        flash(f'Student "{student_name}" registered successfully! Student System ID: {student_system_id}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error registering student: {str(e)}', 'danger')
    
    return redirect(url_for('schools.school_dashboard'))


@bp.route('/individual/enter', methods=['GET', 'POST'])
def individual_enter():
    """Individual class entry using Student Name + Student System ID"""
    from flask_login import login_user
    from ..models.classes import ClassEnrollment
    
    if request.method == 'POST':
        student_name = request.form.get('student_name', '').strip()
        student_system_id = request.form.get('student_system_id', '').strip().upper()
        
        if not student_name or not student_system_id:
            flash('Please provide both Student Name and Student System ID.', 'danger')
            return render_template('individual_enter.html')
        
        # Find user by student_id
        user = User.query.filter_by(student_id=student_system_id).first()
        
        if not user:
            flash('Student System ID not found.', 'danger')
            return render_template('individual_enter.html')
        
        # Verify name matches
        full_name_lower = student_name.lower()
        user_full_name = f"{user.first_name} {user.last_name}".lower()
        
        # Check enrollment
        enrollment = ClassEnrollment.query.filter_by(
            user_id=user.id,
            class_type='individual',
            status='completed'
        ).first()
        
        name_matches = (
            user_full_name == full_name_lower or
            (enrollment and enrollment.customer_name and enrollment.customer_name.lower() == full_name_lower)
        )
        
        if not name_matches:
            flash('Student Name does not match the Student System ID.', 'danger')
            return render_template('individual_enter.html')
        
        if not enrollment:
            flash('You are not enrolled in any Individual class.', 'danger')
            return render_template('individual_enter.html')
        
        login_user(user)
        flash(f'Welcome, {user.first_name}!', 'success')
        return redirect(url_for('admin.student_dashboard'))
    
    return render_template('individual_enter.html')


@bp.route('/group/enter', methods=['GET', 'POST'])
def group_enter():
    """Group class entry using Group Class Name + Group System ID (GRO-XXXXXX)"""
    from flask_login import login_user
    from ..models.classes import ClassEnrollment, GroupClass
    
    if request.method == 'POST':
        group_name = request.form.get('group_name', '').strip()
        group_system_id = request.form.get('group_system_id', '').strip().upper()
        
        if not group_name or not group_system_id:
            flash('Please provide both Group Class Name and Group System ID.', 'danger')
            return render_template('group_enter.html')
        
        # Find enrollment by group_system_id
        try:
            enrollment = ClassEnrollment.query.filter_by(
                group_system_id=group_system_id,
                class_type='group',
                status='completed'
            ).first()
        except Exception as e:
            if 'group_system_id' in str(e).lower() or 'column' in str(e).lower():
                flash('Database migration required. Please contact administrator.', 'warning')
                return render_template('group_enter.html')
            raise
        
        if not enrollment:
            flash('Group System ID not found.', 'danger')
            return render_template('group_enter.html')
        
        # Find group class by name and verify it matches enrollment
        group_class = GroupClass.query.filter_by(
            name=group_name,
            class_type='group',
            id=enrollment.class_id
        ).first()
        
        if not group_class:
            flash('Group Class not found or does not match the Group System ID.', 'danger')
            return render_template('group_enter.html')
        
        # Get user from enrollment
        user = User.query.get(enrollment.user_id)
        if not user:
            flash('User account not found.', 'danger')
            return render_template('group_enter.html')
        
        login_user(user)
        flash(f'Welcome, {user.first_name}!', 'success')
        return redirect(url_for('main.group_class_dashboard'))
    
    return render_template('group_enter.html')


@bp.route('/family/enter', methods=['GET', 'POST'])
def family_enter():
    """Family class entry using Family Name + Family System ID"""
    from flask_login import login_user
    from ..models.classes import ClassEnrollment
    
    if request.method == 'POST':
        family_name = request.form.get('family_name', '').strip()
        family_system_id = request.form.get('family_system_id', '').strip().upper()
        
        if not family_name or not family_system_id:
            flash('Please provide both Family Name and Family System ID.', 'danger')
            return render_template('family_enter.html')
        
        # Find enrollment by family_system_id
        try:
            enrollment = ClassEnrollment.query.filter_by(
                family_system_id=family_system_id,
                class_type='family',
                status='completed'
            ).first()
        except Exception as e:
            if 'family_system_id' in str(e).lower() or 'column' in str(e).lower():
                flash('Database migration required. Please contact administrator.', 'warning')
                return render_template('family_enter.html')
            raise
        
        if not enrollment:
            flash('Family System ID not found.', 'danger')
            return render_template('family_enter.html')
        
        # Verify family name matches
        user = User.query.get(enrollment.user_id)
        if not user:
            flash('Family account not found.', 'danger')
            return render_template('family_enter.html')
        
        family_name_lower = family_name.lower()
        user_full_name = f"{user.first_name} {user.last_name}".lower()
        
        name_matches = (
            user_full_name == family_name_lower or
            (enrollment.customer_name and enrollment.customer_name.lower() == family_name_lower)
        )
        
        if not name_matches:
            flash('Family Name does not match the Family System ID.', 'danger')
            return render_template('family_enter.html')
        
        login_user(user)
        flash(f'Welcome, {user.first_name}!', 'success')
        return redirect(url_for('main.family_dashboard'))
    
    return render_template('family_enter.html')


@bp.route('/school-mentor/enter', methods=['GET', 'POST'])
def school_mentor_enter():
    """School mentor entry using School Name + School System ID"""
    from flask_login import login_user
    
    if request.method == 'POST':
        school_name = request.form.get('school_name', '').strip()
        school_system_id = request.form.get('school_system_id', '').strip().upper()
        
        if not school_name or not school_system_id:
            flash('Please provide both School Name and School System ID.', 'danger')
            return render_template('school_mentor_enter.html')
        
        # Find school by system ID
        school = School.query.filter_by(school_system_id=school_system_id).first()
        
        if not school:
            flash('School System ID not found.', 'danger')
            return render_template('school_mentor_enter.html')
        
        # Verify school name matches
        if school.school_name.lower() != school_name.lower():
            flash('School Name does not match the School System ID.', 'danger')
            return render_template('school_mentor_enter.html')
        
        # Get school admin user
        user = User.query.get(school.user_id)
        
        if not user:
            flash('School administrator account not found.', 'danger')
            return render_template('school_mentor_enter.html')
        
        if not user.is_school_admin:
            flash('This account is not authorized as a school mentor.', 'danger')
            return render_template('school_mentor_enter.html')
        
        # Check school status
        if school.status == 'active' and school.payment_status == 'completed':
            login_user(user)
            flash(f'Welcome, {user.first_name}!', 'success')
            return redirect(url_for('schools.school_dashboard'))
        elif school.status == 'active' and school.payment_status != 'completed':
            flash('Your school payment is still pending. Please complete payment to access the classroom.', 'warning')
            return redirect(url_for('schools.school_pending_approval'))
        else:
            login_user(user)
            return redirect(url_for('schools.school_pending_approval'))
    
    return render_template('school_mentor_enter.html')


@bp.route('/school-student/login', methods=['GET', 'POST'])
def school_student_login():
    """School student login using School Name + Student System ID"""
    from flask import session
    from ..models.classes import SchoolStudent, ClassEnrollment
    
    if request.method == 'POST':
        school_name = request.form.get('school_name', '').strip()
        student_system_id = request.form.get('student_system_id', '').strip().upper()
        
        if not school_name or not student_system_id:
            flash('Please provide both School Name and Student System ID.', 'danger')
            return render_template('school_student_login.html')
        
        # Find the student by school name and system ID
        student = SchoolStudent.query.filter_by(
            school_name=school_name,
            student_system_id=student_system_id
        ).first()
        
        if not student:
            flash('Invalid School Name or Student System ID.', 'danger')
            return render_template('school_student_login.html')
        
        # Verify the student is registered in at least one active class
        enrollment = ClassEnrollment.query.filter_by(
            id=student.enrollment_id,
            status='completed'
        ).first()
        
        if not enrollment:
            flash('Student is not enrolled in any active class.', 'danger')
            return render_template('school_student_login.html')
        
        # Store student info in session (not using User login, but session-based)
        session['school_student_id'] = student.id
        session['school_student_name'] = student.student_name
        session['school_student_system_id'] = student.student_system_id
        session['school_name'] = student.school_name
        session['school_student_class_id'] = student.class_id
        session['school_student_enrollment_id'] = student.enrollment_id
        
        flash(f'Welcome, {student.student_name}!', 'success')
        return redirect(url_for('schools.school_student_dashboard'))
    
    return render_template('school_student_login.html')


@bp.route('/school-student/dashboard')
def school_student_dashboard():
    """School student dashboard - shows only their classes and materials"""
    from flask import session
    from datetime import date
    from calendar import monthrange
    from ..models.classes import SchoolStudent, ClassEnrollment, GroupClass, Attendance
    from ..models.materials import LearningMaterial
    
    # Check if student is logged in via session
    if 'school_student_id' not in session:
        flash('Please log in to access your dashboard.', 'warning')
        return redirect(url_for('schools.school_student_login'))
    
    student_id = session['school_student_id']
    student = SchoolStudent.query.get(student_id)
    
    if not student:
        session.clear()
        flash('Student record not found.', 'danger')
        return redirect(url_for('schools.school_student_login'))
    
    # Get all classes this student is registered in
    student_classes = SchoolStudent.query.filter_by(
        student_system_id=student.student_system_id,
        school_name=student.school_name
    ).all()
    
    enrolled_classes = []
    for stu_class in student_classes:
        enrollment = ClassEnrollment.query.get(stu_class.enrollment_id)
        if enrollment and enrollment.status == 'completed':
            # Get class details
            class_obj = GroupClass.query.get(stu_class.class_id)
            if class_obj:
                enrolled_classes.append({
                    'id': class_obj.id,
                    'name': class_obj.name,
                    'description': class_obj.description,
                    'class_type': 'school',
                    'enrollment': enrollment,
                    'student_record': stu_class
                })
    
    # Get learning materials for student's classes
    materials = []
    for cls in enrolled_classes:
        class_materials = LearningMaterial.query.filter_by(
            actual_class_id=cls['id'],
            class_type='school'
        ).order_by(LearningMaterial.created_at.desc()).all()
        materials.extend(class_materials)
    
    # Get attendance records for current month
    today = date.today()
    month_start = date(today.year, today.month, 1)
    month_end = date(today.year, today.month, monthrange(today.year, today.month)[1])
    
    attendance_records = {}
    monthly_stats = {}
    
    for cls in enrolled_classes:
        # Get attendance for this student in this class
        # Note: Attendance uses school admin's user_id as proxy, but we check notes field
        from ..models.users import User
        school = User.query.get(student.registered_by)
        if school:
            attendance = Attendance.query.filter(
                Attendance.student_id == school.id,
                Attendance.class_id == cls['id'],
                Attendance.class_type == 'school',
                Attendance.attendance_date >= month_start,
                Attendance.attendance_date <= month_end,
                Attendance.notes.like(f'%school_student_{student.id}%')
            ).order_by(Attendance.attendance_date.desc()).all()
            
            attendance_records[cls['id']] = attendance
            
            # Calculate monthly stats
            total_days = monthrange(today.year, today.month)[1]
            present_days = len([a for a in attendance if a.status == 'present'])
            percentage = (present_days / total_days * 100) if total_days > 0 else 0
            monthly_stats[cls['id']] = {
                'present': present_days,
                'total': total_days,
                'percentage': round(percentage, 1)
            }
    
    # Get today's attendance
    today_attendance = {}
    for cls in enrolled_classes:
        from ..models.users import User
        school = User.query.get(student.registered_by)
        if school:
            att = Attendance.query.filter(
                Attendance.student_id == school.id,
                Attendance.class_id == cls['id'],
                Attendance.class_type == 'school',
                Attendance.attendance_date == today,
                Attendance.notes.like(f'%school_student_{student.id}%')
            ).first()
            today_attendance[cls['id']] = att
    
    # Get projects count (school students don't have User accounts, so count is 0 for now)
    # In the future, if projects are linked to school students, update this logic
    projects_count = 0
    
    return render_template('school_student_dashboard.html',
                         student=student,
                         enrolled_classes=enrolled_classes,
                         materials=materials,
                         attendance_records=attendance_records,
                         monthly_stats=monthly_stats,
                         today_attendance=today_attendance,
                         today=today,
                         projects_count=projects_count)


@bp.route('/school-student/logout')
def school_student_logout():
    """Logout school student"""
    from flask import session
    session.pop('school_student_id', None)
    session.pop('school_student_name', None)
    session.pop('school_student_system_id', None)
    session.pop('school_name', None)
    session.pop('school_student_class_id', None)
    session.pop('school_student_enrollment_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))


@bp.route('/enter-classroom', methods=['GET', 'POST'])
def enter_classroom():
    """
    Unified classroom entry point - shows all classroom type options
    For POST requests, handles legacy login flow for backward compatibility
    """
    if request.method == 'GET':
        return render_template('enter_classroom.html')
    
    # POST request - legacy login flow (backward compatibility)
    # Classroom entry system - validate Name and System ID for Individual, Group, and Family classes.
    # School classes must use /school-student/login (School Name + School Student System ID).
    from ..models.classes import ClassEnrollment, FamilyMember
    
    full_name = request.form.get('full_name', '').strip()
    system_id = request.form.get('student_id', '').strip().upper()
    
    if not full_name or not system_id:
        flash('Please provide both Name and System ID.', 'danger')
        return render_template('enter_classroom.html')
    
    # CRITICAL: Block School Student System IDs (STU-XXX-XXXXX format)
    # School students must use /school-student/login with School Name + System ID
    if system_id.startswith('STU-') and '-' in system_id[4:]:  # Format: STU-XXX-XXXXX
        flash('School students must use the School Student Login page with School Name and Student System ID.', 'warning')
        return redirect(url_for('schools.school_student_login'))
    
    # 1. INDIVIDUAL CLASS LOGIN: Student Name + Student System ID
    # 2. GROUP CLASS LOGIN: Student Name + Student System ID
    if system_id.startswith('STU-'):
        user = User.query.filter_by(student_id=system_id).first()
        
        if user:
            full_name_lower = full_name.lower()
            user_full_name = f"{user.first_name} {user.last_name}".lower()
            
            # Check enrollment for additional name verification
            enrollment = ClassEnrollment.query.filter_by(
                user_id=user.id,
                status='completed'
            ).first()
            
            name_matches = (
                user_full_name == full_name_lower or
                (enrollment and enrollment.customer_name and enrollment.customer_name.lower() == full_name_lower)
            )
            
            if name_matches:
                # Verify class type is Individual or Group (NOT school)
                if enrollment and enrollment.class_type == 'school':
                    flash('School students must use the School Student Login page.', 'warning')
                    return redirect(url_for('schools.school_student_login'))
                
                login_user(user)
                
                # Redirect based on class type
                if enrollment:
                    if enrollment.class_type == 'individual':
                        return redirect(url_for('admin.student_dashboard'))
                    elif enrollment.class_type == 'group':
                        return redirect(url_for('admin.student_dashboard'))
                    elif enrollment.class_type == 'family':
                        return redirect(url_for('admin.student_dashboard'))
                
                return redirect(url_for('admin.student_dashboard'))
            else:
                flash('Name does not match the Student System ID.', 'danger')
        else:
            flash('Student System ID not found.', 'danger')
    
    # 3. FAMILY CLASS LOGIN: Family Name + Family System ID (FAM-XXXXX format)
    elif system_id.startswith('FAM-'):
        try:
            enrollment = ClassEnrollment.query.filter_by(
                family_system_id=system_id,
                class_type='family',
                status='completed'
            ).first()
        except Exception as e:
                # Handle case where family_system_id column doesn't exist yet
                if 'family_system_id' in str(e).lower() or 'column' in str(e).lower():
                    flash('Database migration required. Please contact administrator to run migration at /admin/add-family-system-id-column', 'warning')
                    return render_template('enter_classroom.html')
                raise
        
        if enrollment:
            # Verify family name matches (check customer_name or user's name)
            full_name_lower = full_name.lower()
            user = User.query.get(enrollment.user_id)
            
            if user:
                user_full_name = f"{user.first_name} {user.last_name}".lower()
                name_matches = (
                    user_full_name == full_name_lower or
                    (enrollment.customer_name and enrollment.customer_name.lower() == full_name_lower)
                )
                
                if name_matches:
                    login_user(user)
                    return redirect(url_for('admin.student_dashboard'))
                else:
                    flash('Family Name does not match the Family System ID.', 'danger')
            else:
                flash('Family account not found.', 'danger')
        else:
            flash('Family System ID not found.', 'danger')
    
    # 4. SCHOOL ADMIN LOGIN: Admin Name + School System ID (SCH-XXXXXX format)
    elif system_id.startswith('SCH-'):
        school = School.query.filter_by(school_system_id=system_id).first()
        if school:
            full_name_lower = full_name.lower()
            user = User.query.get(school.user_id)
            user_full_name = f"{user.first_name} {user.last_name}".lower() if user else ""
            
            name_matches = (
                school.admin_name.lower() == full_name_lower or
                user_full_name == full_name_lower or
                (user and user.username.lower() == full_name_lower)
            )
            
            if name_matches:
                if user:
                    if school.status == 'active' and school.payment_status == 'completed':
                        login_user(user)
                        return redirect(url_for('schools.school_dashboard'))
                    elif school.status == 'active' and school.payment_status != 'completed':
                        flash('Your school payment is still pending. Please complete payment to access the classroom.', 'warning')
                        return redirect(url_for('schools.school_pending_approval'))
                    else:
                        login_user(user)
                        return redirect(url_for('schools.school_pending_approval'))
                else:
                    flash('School administrator account not found.', 'danger')
            else:
                flash(f'The name "{full_name}" does not match our records for this School ID.', 'danger')
        else:
            flash(f'School ID "{system_id}" not found.', 'danger')
    else:
        flash('Invalid System ID format. Use STU-XXXXX for Individual/Group, FAM-XXXXX for Family, or SCH-XXXXXX for School Admin.', 'danger')
    
    return render_template('enter_classroom.html')


@bp.route('/student/create-account', methods=['GET', 'POST'])
def student_create_account():
    """Create account for registered school student"""
    student_id = session.get('pending_student_id')
    
    if not student_id:
        flash('No pending student registration found.', 'danger')
        return redirect(url_for('schools.enter_classroom'))
    
    student = RegisteredSchoolStudent.query.get(student_id)
    if not student:
        flash('Student registration not found.', 'danger')
        return redirect(url_for('schools.enter_classroom'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not all([username, email, password]):
            flash('All fields are required.', 'danger')
            return render_template('student_create_account.html', student=student)
        
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('student_create_account.html', student=student)
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('student_create_account.html', student=student)
        
        # Check existing user
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
            return render_template('student_create_account.html', student=student)
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('student_create_account.html', student=student)
        
        try:
            # Create user account
            user = User(
                username=username,
                email=email,
                first_name=student.student_name.split()[0] if student.student_name.split() else student.student_name,
                last_name=' '.join(student.student_name.split()[1:]) if len(student.student_name.split()) > 1 else '',
                is_student=True,
                is_school_student=True,
                school_id=student.school_id,
                student_system_id=student.student_system_id
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            
            # Link student to user account
            student.user_id = user.id
            db.session.commit()
            
            # Log in the student
            login_user(user)
            session.pop('pending_student_id', None)
            
            flash(f'Account created successfully! Welcome, {student.student_name}!', 'success')
            return redirect(url_for('schools.school_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Account creation failed: {str(e)}', 'danger')
            return render_template('student_create_account.html', student=student)
    
    return render_template('student_create_account.html', student=student)
