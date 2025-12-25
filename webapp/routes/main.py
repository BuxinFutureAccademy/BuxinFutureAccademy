import os
from flask import Blueprint, current_app, render_template, redirect, url_for, send_from_directory, jsonify, request, flash
from flask_login import login_required, current_user
from ..services.mailer import send_bulk_email
from ..models import HomeGallery, StudentVictory, StudentProject, ClassPricing

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    from datetime import datetime
    from ..extensions import db
    
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
@login_required
def group_class_dashboard():
    """Group Class Dashboard - Unified with student dashboard design"""
    from .admin import student_dashboard
    return student_dashboard()


@bp.route('/family/dashboard')
@login_required
def family_dashboard():
    """Family Dashboard - Unified with student dashboard design"""
    from .admin import student_dashboard
    return student_dashboard()