import os
from flask import Blueprint, current_app, render_template, redirect, url_for, send_from_directory, jsonify, request, flash, session
from flask_login import login_required, current_user
from ..services.mailer import send_bulk_email
from ..models import HomeGallery, StudentVictory, StudentProject, ClassPricing, ClassTime, StudentClassTimeSelection, ClassEnrollment
from ..routes.admin import require_id_card_viewed

bp = Blueprint('main', __name__)

@bp.route('/')
@require_id_card_viewed
def index():
    from datetime import datetime
    from ..extensions import db
    from flask_login import current_user
    
    # Decorator @require_id_card_viewed handles ID card check FIRST
    # If student needs ID card, decorator redirects them - this code never runs
    # If student has viewed ID card, check if they should be redirected to dashboard
    
    if current_user.is_authenticated and not current_user.is_admin:
        from ..models import ClassEnrollment, School, RegisteredSchoolStudent
        
        # Check for approved enrollments (Individual, Group, Family, School)
        approved_enrollments = ClassEnrollment.query.filter_by(
            user_id=current_user.id,
            status='completed'
        ).all()
        
        if approved_enrollments:
            # Priority order: Individual > Group > Family > School
            individual_enrollment = next((e for e in approved_enrollments if e.class_type == 'individual'), None)
            if individual_enrollment:
                return redirect(url_for('admin.student_dashboard'))
            
            group_enrollment = next((e for e in approved_enrollments if e.class_type == 'group'), None)
            if group_enrollment:
                return redirect(url_for('main.group_class_dashboard'))
            
            family_enrollment = next((e for e in approved_enrollments if e.class_type == 'family'), None)
            if family_enrollment:
                return redirect(url_for('main.family_dashboard'))
            
            school_enrollment = next((e for e in approved_enrollments if e.class_type == 'school'), None)
            if school_enrollment:
                return redirect(url_for('schools.school_dashboard'))
            
            return redirect(url_for('admin.student_dashboard'))
        
        # Check if user is a school admin with active school
        school = School.query.filter_by(user_id=current_user.id).first()
        if school and school.status == 'active' and school.payment_status == 'completed':
            return redirect(url_for('schools.school_dashboard'))
        
        # Check if user is a registered school student
        from flask import session
        if session.get('school_student_id'):
            return redirect(url_for('schools.school_student_dashboard'))
        
        registered_school_student = RegisteredSchoolStudent.query.filter_by(
            user_id=current_user.id
        ).first()
        if registered_school_student:
            return redirect(url_for('schools.school_student_dashboard'))
    
    # Initialize empty lists for graceful degradation if tables don't exist
    gallery_images = []
    gallery_videos = []
    featured_images = []
    featured_videos = []
    victories = []
    featured_victories = []
    projects_with_images = []
    projects_with_videos = []
    
    try:
        db.session.rollback()  # Ensure clean transaction state
        # Get gallery images (from admin + student projects)
        gallery_images = HomeGallery.query.filter_by(
            is_active=True, 
            media_type='image'
        ).order_by(HomeGallery.display_order.asc(), HomeGallery.created_at.desc()).limit(12).all()
        
        # Get gallery videos
        gallery_videos = HomeGallery.query.filter_by(
            is_active=True, 
            media_type='video'
        ).order_by(HomeGallery.display_order.asc(), HomeGallery.created_at.desc()).limit(8).all()
        
        # Get featured items
        featured_images = HomeGallery.query.filter_by(
            is_active=True, 
            media_type='image',
            is_featured=True
        ).limit(6).all()
        
        featured_videos = HomeGallery.query.filter_by(
            is_active=True, 
            media_type='video',
            is_featured=True
        ).limit(4).all()
    except Exception as e:
        # Table doesn't exist yet, rollback and continue with empty lists
        db.session.rollback()
        current_app.logger.warning(f"HomeGallery table may not exist: {e}")
    
    victories = []
    featured_victories = []
    try:
        # Get student victories - handle missing profile_picture column gracefully
        from sqlalchemy.exc import ProgrammingError
        try:
            victories = StudentVictory.query.filter_by(is_active=True).order_by(
                StudentVictory.display_order.asc(),
                StudentVictory.achievement_date.desc()
            ).limit(6).all()
            
            featured_victories = StudentVictory.query.filter_by(
                is_active=True,
                is_featured=True
            ).limit(3).all()
            
            # Pre-load student relationships to catch errors early, but handle gracefully
            for victory in victories + featured_victories:
                try:
                    # Try to access student to trigger lazy load and catch error early
                    if hasattr(victory, 'student_id') and victory.student_id:
                        _ = victory.student  # Trigger lazy load
                except ProgrammingError as pe:
                    if 'profile_picture' in str(pe):
                        # Mark that student can't be loaded due to missing column
                        victory._student_load_error = True
                        current_app.logger.warning(f"profile_picture column missing for victory {victory.id}. Please run migration: /admin/add-profile-picture-column")
        except ProgrammingError as pe:
            # Check if it's the profile_picture column error
            if 'profile_picture' in str(pe):
                current_app.logger.warning("profile_picture column missing. Please run migration: /admin/add-profile-picture-column")
                victories = []
                featured_victories = []
            else:
                raise  # Re-raise if it's a different error
    except Exception as e:
        # Table doesn't exist yet, or other error, rollback and continue with empty lists
        db.session.rollback()
        current_app.logger.warning(f"StudentVictory query error: {e}")
        victories = []
        featured_victories = []
    
    try:
        # Also get projects with images/videos that aren't in gallery yet (fallback)
        projects_with_images = StudentProject.query.filter(
            StudentProject.is_active == True,
            StudentProject.image_url.isnot(None),
            StudentProject.image_url != ''
        ).order_by(StudentProject.created_at.desc()).limit(12).all()
        
        projects_with_videos = StudentProject.query.filter(
            StudentProject.is_active == True,
            StudentProject.youtube_url.isnot(None),
            StudentProject.youtube_url != ''
        ).order_by(StudentProject.created_at.desc()).limit(8).all()
    except Exception as e:
        # Rollback and continue with empty lists
        db.session.rollback()
        current_app.logger.warning(f"Error fetching student projects: {e}")
    
    # Get class pricing - with rollback to clear any failed transactions
    try:
        db.session.rollback()  # Clear any failed transaction state
        pricing_data = ClassPricing.get_all_pricing()
    except Exception:
        db.session.rollback()
        pricing_data = ClassPricing.get_default_pricing()
    
    return render_template('index.html',
        gallery_images=gallery_images,
        gallery_videos=gallery_videos,
        featured_images=featured_images,
        featured_videos=featured_videos,
        victories=victories,
        featured_victories=featured_victories,
        projects_with_images=projects_with_images,
        projects_with_videos=projects_with_videos,
        pricing_data=pricing_data,
        now=datetime.now
    )


@bp.route('/admin/create-gallery-tables')
def create_gallery_tables():
    """Admin endpoint to create the new gallery tables"""
    from flask_login import current_user
    from ..extensions import db
    
    # Check if user is admin (allow if not logged in for initial setup)
    try:
        if current_user.is_authenticated and not current_user.is_admin:
            return jsonify({"error": "Admin access required"}), 403
    except:
        pass
    
    try:
        db.create_all()
        return jsonify({
            "success": True,
            "message": "All database tables created successfully including home_gallery and student_victory"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@bp.route('/about')
def about():
    return render_template('about_us.html')

@bp.get('/health')
def health():
    return {'status': 'ok'}

@bp.route('/portfolio')
def portfolio():
    try:
        return render_template('portfolio.html')
    except Exception as e:
        return f"""
        <h1>Portfolio Page</h1>
        <p>Template Error: {str(e)}</p>
        <p>Make sure 'portfolio.html' exists in your 'templates' folder.</p>
        <p><a href="/">← Back to Home</a></p>
        """

@bp.route('/profolio')
def profolio_redirect():
    return redirect(url_for('main.portfolio'), code=301)

@bp.route('/favicon.ico')
def favicon():
    favicon_path = os.path.join(current_app.static_folder, 'favicon.ico')
    if os.path.exists(favicon_path):
        return send_from_directory(current_app.static_folder, 'favicon.ico', mimetype='image/vnd.microsoft.icon')
    return ("", 204)

@bp.route('/portfolio-test')
def portfolio_test():
    return """
    <html>
    <head><title>Portfolio Test</title></head>
    <body style="font-family: Arial; padding: 20px; text-align: center;">
        <h1>✅ Portfolio Route is Working!</h1>
        <p>The route is accessible. Now you need to:</p>
        <ol style="text-align: left; max-width: 500px; margin: 0 auto;">
            <li>Create the 'templates' folder (if it doesn't exist)</li>
            <li>Save the portfolio HTML as 'templates/portfolio.html'</li>
            <li>Restart your Flask application</li>
            <li>Visit <a href="/portfolio">/portfolio</a> again</li>
        </ol>
        <p><a href="/">← Back to Home</a></p>
    </body>
    </html>
    """

@bp.route('/choose-class-type')
def choose_class_type():
    """Choose Class Type page - First step in registration flow"""
    return render_template('choose_class_type.html')


@bp.route('/contact-support', methods=['POST'])
def contact_support():
    data = request.get_json()
    email = (data.get('email') or '').strip()
    whatsapp = (data.get('whatsapp') or '').strip()
    message = (data.get('message') or '').strip()

    if not email or not whatsapp or not message:
        return jsonify(success=False, error="All fields are required."), 400

    subject = "New Support Message from Website"
    body = f"""You have received a new support message from the website:

Email: {email}
WhatsApp: {whatsapp}

Message:
{message}
"""

    class TempUser:
        def __init__(self, email, first_name):
            self.email = email
            self.first_name = first_name
            self.last_name = ""

    admin_email = current_app.config.get('MAIL_DEFAULT_SENDER') or 'worldvlog13@gmail.com'
    temp_admin = TempUser(admin_email, "Admin")
    try:
        sent_count = send_bulk_email([temp_admin], subject, body)
        if sent_count > 0:
            return jsonify(success=True)
        return jsonify(success=False, error="Failed to send email."), 500
    except Exception as e:
        print(f"Error sending support email: {e}")
        return jsonify(success=False, error="Internal error."), 500


@bp.route('/profile/<int:user_id>')
@login_required
def user_profile(user_id):
    """User Profile page - View student enrollments and progress"""
    from ..models import User, ClassEnrollment, GroupClass, IndividualClass, Purchase
    
    user = User.query.get_or_404(user_id)
    
    # Security: only admins or the user themselves can view the profile
    if not current_user.is_admin and current_user.id != user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('main.index'))
        
    enrollments = ClassEnrollment.query.filter_by(user_id=user.id).order_by(ClassEnrollment.enrolled_at.desc()).all()
    purchases = Purchase.query.filter_by(user_id=user.id).order_by(Purchase.purchased_at.desc()).all()
    
    return render_template('user_profile.html', 
                           user=user, 
                           enrollments=enrollments, 
                           purchases=purchases,
                           GroupClass=GroupClass,
                           IndividualClass=IndividualClass)

@bp.route('/group-class/dashboard')
def group_class_dashboard():
    """Group Class Dashboard - Unified with student dashboard design"""
    from .admin import student_dashboard
    return student_dashboard()


@bp.route('/family/dashboard')
def family_dashboard():
    """Family Dashboard - Unified with student dashboard design"""
    from .admin import student_dashboard
    return student_dashboard()


@bp.route('/qr/<int:id_card_id>')
def qr_code_redirect(id_card_id):
    """
    QR Code Route - NO LOGIN REQUIRED
    When student scans QR code, sets session data and redirects to their dashboard
    """
    from ..models import IDCard, User, School, RegisteredSchoolStudent
    
    id_card = IDCard.query.get_or_404(id_card_id)
    
    if not id_card.is_active:
        flash('This ID card is not active.', 'danger')
        return redirect(url_for('main.index'))
    
    # Set session data based on entity type (same logic as view_id_card)
    if id_card.entity_type == 'individual' or id_card.entity_type == 'group':
        # Get user from entity_id
        user = User.query.get(id_card.entity_id)
        if user:
            session['student_user_id'] = user.id
            session['student_name'] = f"{user.first_name} {user.last_name}"
            session['student_system_id'] = user.student_id
            # Redirect to appropriate dashboard
            if id_card.entity_type == 'individual':
                return redirect(url_for('admin.student_dashboard'))
            else:
                return redirect(url_for('main.group_class_dashboard'))
    elif id_card.entity_type == 'family':
        # Get enrollment and user
        enrollment = ClassEnrollment.query.get(id_card.entity_id)
        if enrollment:
            user = User.query.get(enrollment.user_id)
            if user:
                session['student_user_id'] = user.id
                session['student_name'] = f"{user.first_name} {user.last_name}"
                session['family_system_id'] = enrollment.family_system_id
                return redirect(url_for('main.family_dashboard'))
    elif id_card.entity_type == 'school':
        # Get school and user
        school_obj = School.query.get(id_card.entity_id)
        if school_obj:
            user = User.query.get(school_obj.user_id)
            if user:
                session['student_user_id'] = user.id
                session['school_name'] = school_obj.school_name
                session['school_system_id'] = school_obj.school_system_id
                return redirect(url_for('schools.school_dashboard'))
    elif id_card.entity_type == 'school_student':
        # Get registered school student
        registered_student = RegisteredSchoolStudent.query.get(id_card.entity_id)
        if registered_student:
            session['school_student_id'] = registered_student.id
            session['school_student_name'] = registered_student.student_name
            session['school_student_system_id'] = registered_student.student_system_id
            session['school_name'] = registered_student.school_name
            return redirect(url_for('schools.school_student_dashboard'))
    
    # If we get here, something went wrong
    flash('Unable to redirect. Please contact support.', 'danger')
    return redirect(url_for('main.index'))


@bp.route('/select-class-time', methods=['POST'])
@login_required
def select_class_time():
    """Student route for selecting class time (Individual and Family only)"""
    from datetime import datetime
    from ..extensions import db
    
    time_id = request.form.get('time_id', type=int)
    
    if not time_id:
        flash('Please select a time slot.', 'danger')
        return redirect(request.referrer or url_for('admin.student_dashboard'))
    
    # Get the class time
    class_time = ClassTime.query.get(time_id)
    if not class_time:
        flash('Time slot not found.', 'danger')
        return redirect(request.referrer or url_for('admin.student_dashboard'))
    
    # Verify it's selectable
    if not class_time.is_selectable:
        flash('This time slot is not selectable.', 'danger')
        return redirect(request.referrer or url_for('admin.student_dashboard'))
    
    # Verify class type matches
    if class_time.class_type not in ['individual', 'family']:
        flash('Time selection is only available for Individual and Family classes.', 'danger')
        return redirect(request.referrer or url_for('admin.student_dashboard'))
    
    # Find the student's enrollment for this class type
    enrollment = ClassEnrollment.query.filter_by(
        user_id=current_user.id,
        class_type=class_time.class_type,
        status='completed'
    ).first()
    
    if not enrollment:
        flash('You must be enrolled and approved in a class before selecting a time.', 'danger')
        return redirect(request.referrer or url_for('admin.student_dashboard'))
    
    # Get student's timezone for display
    student_timezone = current_user.timezone or 'Asia/Kolkata'
    
    # Check if student already has a selection for this enrollment
    existing_selection = StudentClassTimeSelection.query.filter_by(
        enrollment_id=enrollment.id
    ).first()
    
    if existing_selection:
        # Update existing selection
        existing_selection.class_time_id = time_id
        existing_selection.selected_at = datetime.utcnow()
        db.session.commit()
        flash(f'Time updated to: {class_time.get_full_display(student_timezone)}', 'success')
    else:
        # Create new selection
        selection = StudentClassTimeSelection(
            user_id=current_user.id,
            enrollment_id=enrollment.id,
            class_time_id=time_id,
            class_type=class_time.class_type
        )
        db.session.add(selection)
        db.session.commit()
        flash(f'Time selected: {class_time.get_full_display(student_timezone)}', 'success')
    
    return redirect(request.referrer or url_for('admin.student_dashboard'))


@bp.route('/update-timezone', methods=['POST'])
@login_required
def update_timezone():
    """Student route for updating their timezone preference"""
    from ..extensions import db
    
    timezone = request.form.get('timezone', '').strip()
    
    if not timezone:
        flash('Please select a timezone.', 'danger')
        return redirect(request.referrer or url_for('admin.student_dashboard'))
    
    # Validate timezone
    try:
        import pytz
        pytz.timezone(timezone)  # Will raise exception if invalid
    except Exception:
        flash('Invalid timezone selected.', 'danger')
        return redirect(request.referrer or url_for('admin.student_dashboard'))
    
    # Update user's timezone
    current_user.timezone = timezone
    db.session.commit()
    
    flash('Timezone updated successfully. Class times are now shown in your local time.', 'success')
    return redirect(request.referrer or url_for('admin.student_dashboard'))