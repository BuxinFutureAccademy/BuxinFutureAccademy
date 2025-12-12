import os
from flask import Blueprint, current_app, render_template, redirect, url_for, send_from_directory, jsonify, request
from ..services.mailer import send_bulk_email
from ..models import HomeGallery, StudentVictory, StudentProject

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
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
    
    # Get student victories
    victories = StudentVictory.query.filter_by(is_active=True).order_by(
        StudentVictory.display_order.asc(),
        StudentVictory.achievement_date.desc()
    ).limit(6).all()
    
    featured_victories = StudentVictory.query.filter_by(
        is_active=True,
        is_featured=True
    ).limit(3).all()
    
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
    
    from datetime import datetime
    return render_template('index.html',
        gallery_images=gallery_images,
        gallery_videos=gallery_videos,
        featured_images=featured_images,
        featured_videos=featured_videos,
        victories=victories,
        featured_victories=featured_victories,
        projects_with_images=projects_with_images,
        projects_with_videos=projects_with_videos,
        now=datetime.now
    )

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
