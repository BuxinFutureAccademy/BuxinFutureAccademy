import os
from flask import Blueprint, current_app, render_template, redirect, url_for, send_from_directory, jsonify, request
from ..services.mailer import send_bulk_email

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('index.html')

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
