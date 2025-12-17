from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
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


@bp.route('/register-school', methods=['GET', 'POST'])
def register_school():
    """School registration form"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        # Check database setup first
        db_error = check_database_setup()
        if db_error:
            flash(db_error, 'danger')
            return render_template('register_school.html')
        
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
            return render_template('register_school.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('register_school.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register_school.html')
        
        try:
            # Check existing user
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash('Username already taken.', 'danger')
                return render_template('register_school.html')
            
            existing_email = User.query.filter_by(email=admin_email).first()
            if existing_email:
                flash('Email already registered.', 'danger')
                return render_template('register_school.html')
            
            # Check if school email already exists
            existing_school = School.query.filter_by(school_email=school_email).first()
            if existing_school:
                flash('School email already registered.', 'danger')
                return render_template('register_school.html')
            
            # Create user account for school admin
            user = User(
                username=username,
                email=admin_email,
                first_name=admin_name.split()[0] if admin_name.split() else admin_name,
                last_name=' '.join(admin_name.split()[1:]) if len(admin_name.split()) > 1 else '',
                is_student=False,
                is_admin=False,
                is_school_admin=True
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
            
            # Store school_id in session for payment flow
            session['pending_school_id'] = school.id
            session['school_system_id'] = school_system_id
            
            flash(f'School registration submitted! Your School System ID is: {school_system_id}', 'success')
            return redirect(url_for('schools.school_payment'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Registration failed: {str(e)}', 'danger')
            return render_template('register_school.html')
    
    return render_template('register_school.html')


@bp.route('/school/payment', methods=['GET', 'POST'])
def school_payment():
    """School payment page"""
    school_id = session.get('pending_school_id')
    school_system_id = session.get('school_system_id')
    
    if not school_id:
        flash('No pending school registration found.', 'danger')
        return redirect(url_for('schools.register_school'))
    
    school = School.query.get(school_id)
    if not school:
        flash('School registration not found.', 'danger')
        return redirect(url_for('schools.register_school'))
    
    if request.method == 'POST':
        # Handle payment proof upload
        payment_method = request.form.get('payment_method', '')
        payment_proof = None
        
        if 'payment_proof' in request.files:
            file = request.files['payment_proof']
            if file and file.filename:
                try:
                    upload_result = cloudinary.uploader.upload(file)
                    payment_proof = upload_result.get('secure_url')
                except Exception as e:
                    flash(f'Error uploading payment proof: {str(e)}', 'warning')
        
        # Update school payment status
        school.payment_status = 'completed' if payment_proof else 'pending'
        school.payment_proof = payment_proof
        
        db.session.commit()
        
        # Log in the school admin
        if school.user_id:
            user = User.query.get(school.user_id)
            if user:
                login_user(user)
        
        flash('Payment information submitted! Your school is pending admin approval.', 'success')
        return redirect(url_for('schools.school_pending_approval'))
    
    return render_template('school_payment.html', school=school, school_system_id=school_system_id)


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
    """School classroom dashboard"""
    # Get school for current user
    school = School.query.filter_by(user_id=current_user.id).first()
    
    if not school:
        flash('No school registration found for your account.', 'danger')
        return redirect(url_for('main.index'))
    
    if school.status != 'active':
        return redirect(url_for('schools.school_pending_approval'))
    
    # Get all registered students
    students = RegisteredSchoolStudent.query.filter_by(school_id=school.id).order_by(RegisteredSchoolStudent.created_at.desc()).all()
    
    # Get attendance data for today
    from datetime import date
    from ..models import Attendance
    
    today = date.today()
    today_attendance = {}
    monthly_attendance = {}  # For monthly stats
    
    for student in students:
        if student.user_id:
            # Today's attendance
            att = Attendance.query.filter_by(
                student_id=student.user_id,
                attendance_date=today
            ).first()
            if att:
                today_attendance[student.id] = att
            
            # Monthly attendance stats
            from calendar import monthrange
            month_start = date(today.year, today.month, 1)
            month_end = date(today.year, today.month, monthrange(today.year, today.month)[1])
            
            monthly_att = Attendance.query.filter(
                Attendance.student_id == student.user_id,
                Attendance.attendance_date >= month_start,
                Attendance.attendance_date <= month_end,
                Attendance.status == 'present'
            ).count()
            
            total_days = monthrange(today.year, today.month)[1]
            monthly_attendance[student.id] = {
                'present': monthly_att,
                'total': total_days,
                'percentage': round((monthly_att / total_days * 100) if total_days > 0 else 0, 1)
            }
    
    return render_template('school_dashboard.html', 
                         school=school, 
                         students=students,
                         today_attendance=today_attendance,
                         monthly_attendance=monthly_attendance,
                         today=today,
                         Attendance=Attendance)


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
                try:
                    upload_result = cloudinary.uploader.upload(image_file)
                    student_image_url = upload_result.get('secure_url')
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


@bp.route('/enter-classroom', methods=['GET', 'POST'])
def enter_classroom():
    """Classroom entry system - validate Full Name and Student ID (ID-based access)"""
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        student_id = request.form.get('student_id', '').strip().upper()
        
        if not full_name or not student_id:
            flash('Please provide both Full Name and Student ID.', 'danger')
            return render_template('enter_classroom.html')
        
        # Check if it's a Student ID (STU-XXXXX format)
        if student_id.startswith('STU-'):
            # First check for general student IDs (Group, Family, Individual classes)
            user = User.query.filter_by(student_id=student_id).first()
            
            if user:
                # Verify full name matches (case-insensitive, check both first+last name and customer_name from enrollment)
                full_name_lower = full_name.lower()
                user_full_name = f"{user.first_name} {user.last_name}".lower()
                
                # Also check enrollment customer_name
                from ..models.classes import ClassEnrollment
                enrollment = ClassEnrollment.query.filter_by(
                    user_id=user.id,
                    status='completed'
                ).first()
                
                name_matches = (
                    user_full_name == full_name_lower or
                    (enrollment and enrollment.customer_name and enrollment.customer_name.lower() == full_name_lower)
                )
                
                if name_matches:
                    login_user(user)
                    # Redirect based on class type
                    if user.class_type == 'group':
                        return redirect(url_for('main.group_class_dashboard'))
                    elif user.class_type == 'family':
                        return redirect(url_for('main.family_dashboard'))
                    elif user.class_type == 'individual':
                        return redirect(url_for('admin.student_dashboard'))
                    elif user.is_school_student:
                        return redirect(url_for('schools.school_dashboard'))
                    else:
                        return redirect(url_for('admin.student_dashboard'))
                else:
                    flash('Full name does not match the Student ID.', 'danger')
            else:
                # Check for school student IDs (legacy support)
                student = RegisteredSchoolStudent.query.filter_by(
                    student_system_id=student_id
                ).first()
                
                if student and student.school:
                    # Verify name matches
                    if student.student_name.lower() == full_name_lower and student.school.status == 'active':
                        if student.user_id:
                            user = User.query.get(student.user_id)
                            if user:
                                login_user(user)
                                return redirect(url_for('schools.school_dashboard'))
                        else:
                            session['pending_student_id'] = student.id
                            flash(f'Welcome {student.student_name}! Please create an account to access the classroom.', 'info')
                            return redirect(url_for('schools.student_create_account'))
                    else:
                        flash('Full name does not match the Student ID.', 'danger')
                else:
                    flash('Student ID not found.', 'danger')
        else:
            flash('Invalid Student ID format. Must start with STU-.', 'danger')
    
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

