# app.py - Complete Flask Application (Production Ready)
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid
import requests
import json
import smtplib
import urllib.parse
from email.message import EmailMessage

# ========================================
# APPLICATION CONFIGURATION
# ========================================

app = Flask(__name__)

# Production configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')

# Database configuration for production
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    # Handle PostgreSQL URL for Render
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    # Fallback to SQLite for local development
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///learning_management.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File upload configuration
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

# AI Assistant Configuration
app.config['DEEPINFRA_API_KEY'] = os.environ.get('DEEPINFRA_API_KEY', "JJT2oAUiJNKaEzkGAcP0PpzZ1hBoExqz")
app.config['DEEPINFRA_API_URL'] = "https://api.deepinfra.com/v1/openai/chat/completions"

# Flask app email configurations
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'worldvlog13@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'mfrp osrt pwki lmmx')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'worldvlog13@gmail.com')

# WhatsApp Web fixed number URL base
app.config['WHATSAPP_WEB_URL'] = 'https://web.whatsapp.com/send?phone=+919319038312'

# Create upload directories if they don't exist
try:
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'static/uploads'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'videos'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'materials'), exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create upload directories: {e}")

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ========================================
# DATABASE MODELS (Copy all your models here)
# ========================================

# Association tables for many-to-many relationships
individual_class_students = db.Table('individual_class_students',
    db.Column('class_id', db.Integer, db.ForeignKey('individual_class.id'), primary_key=True),
    db.Column('student_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

group_class_students = db.Table('group_class_students',
    db.Column('class_id', db.Integer, db.ForeignKey('group_class.id'), primary_key=True),
    db.Column('student_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

class ClassEnrollment(db.Model):
    """Model for tracking class enrollments and payments"""
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
    user = db.relationship('User', foreign_keys=[user_id], lazy='select')

class User(UserMixin, db.Model):
    """User model for authentication and user management"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_student = db.Column(db.Boolean, default=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    whatsapp_number = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class IndividualClass(db.Model):
    """Model for individual classes"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    teacher = db.relationship('User', foreign_keys=[teacher_id], lazy='select')
    students = db.relationship('User', secondary=individual_class_students, 
                             lazy='select', back_populates='individual_classes')

class GroupClass(db.Model):
    """Model for group classes"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    max_students = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    teacher = db.relationship('User', foreign_keys=[teacher_id], lazy='select')
    students = db.relationship('User', secondary=group_class_students, 
                             lazy='select', back_populates='group_classes')  # ✅ FIXED

class Course(db.Model):
    """Model for courses in the store"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    short_description = db.Column(db.String(500))
    price = db.Column(db.Float, nullable=False, default=0.0)
    duration_weeks = db.Column(db.Integer, default=4)
    level = db.Column(db.String(20), default='Beginner')
    category = db.Column(db.String(100), nullable=False)
    image_url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    featured = db.Column(db.Boolean, default=False)  # ADD THIS LINE
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    creator = db.relationship('User', foreign_keys=[created_by], lazy='select')

    
    def get_enrolled_count(self):
        return Purchase.query.filter_by(course_id=self.id, status='completed').count()
    
    def get_video_count(self):
        return CourseVideo.query.filter_by(course_id=self.id).count()
    
    def get_total_duration(self):
        videos = CourseVideo.query.filter_by(course_id=self.id).all()
        total_minutes = 0
        for video in videos:
            if video.duration:
                try:
                    time_parts = video.duration.split(':')
                    minutes = int(time_parts[0])
                    seconds = int(time_parts[1]) if len(time_parts) > 1 else 0
                    total_minutes += minutes + (seconds / 60)
                except:
                    pass
        if total_minutes == 0:
            return ""
        elif total_minutes >= 60:
            hours = int(total_minutes // 60)
            minutes = int(total_minutes % 60)
            return f"{hours}h {minutes}m"
        else:
            return f"{int(total_minutes)}m"

class CourseVideo(db.Model):
    """Model for course videos/lessons"""
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    video_filename = db.Column(db.String(255), nullable=False)
    video_url = db.Column(db.String(500))
    duration = db.Column(db.String(10))
    order_index = db.Column(db.Integer, default=1)
    is_preview = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    course = db.relationship('Course', backref=db.backref('videos', lazy=True, order_by='CourseVideo.order_index'))

class CourseMaterial(db.Model):
    """Model for course materials (PDFs, docs, etc.)"""
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    course = db.relationship('Course', backref=db.backref('materials', lazy=True))
    
    def get_file_size_mb(self):
        return round(self.file_size / (1024 * 1024), 2) if self.file_size else 0

class Purchase(db.Model):
    """Model for course purchases/payments"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    payment_method = db.Column(db.String(50), default='bank_transfer')
    transaction_id = db.Column(db.String(100))
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)
    customer_name = db.Column(db.String(100))
    customer_phone = db.Column(db.String(20))
    customer_email = db.Column(db.String(120))
    customer_address = db.Column(db.Text)
    payment_proof = db.Column(db.String(255))
    user = db.relationship('User', foreign_keys=[user_id], lazy='select')
    course = db.relationship('Course', foreign_keys=[course_id], lazy='select')

class Product(db.Model):
    """Model for products in the store"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    short_description = db.Column(db.String(500))
    price = db.Column(db.Float, nullable=False, default=0.0)
    product_type = db.Column(db.String(20), default='Physical')
    category = db.Column(db.String(100), nullable=False)
    brand = db.Column(db.String(100))
    sku = db.Column(db.String(50), unique=True)
    stock_quantity = db.Column(db.Integer, default=0)
    image_url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    featured = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    creator = db.relationship('User', foreign_keys=[created_by], lazy='select')
    
    def get_sales_count(self):
        return ProductOrder.query.filter_by(product_id=self.id, status='completed').count()
    
    def is_in_stock(self):
        return self.product_type == 'Digital' or self.stock_quantity > 0

class ProductOrder(db.Model):
    """Model for product orders"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    payment_method = db.Column(db.String(50), default='bank_transfer')
    transaction_id = db.Column(db.String(100))
    shipping_address = db.Column(db.Text)
    tracking_number = db.Column(db.String(100))
    ordered_at = db.Column(db.DateTime, default=datetime.utcnow)
    shipped_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    customer_name = db.Column(db.String(100))
    customer_phone = db.Column(db.String(20))
    customer_email = db.Column(db.String(120))
    customer_address = db.Column(db.Text)
    payment_proof = db.Column(db.String(255))
    user = db.relationship('User', foreign_keys=[user_id], lazy='select')
    product = db.relationship('Product', foreign_keys=[product_id], lazy='select')

class CartItem(db.Model):
    """Model for course cart items"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', foreign_keys=[user_id], lazy='select')
    course = db.relationship('Course', foreign_keys=[course_id], lazy='select')

class ProductCartItem(db.Model):
    """Model for product cart items"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', foreign_keys=[user_id], lazy='select')
    product = db.relationship('Product', foreign_keys=[product_id], lazy='select')
    
    def get_total_price(self):
        return self.product.price * self.quantity


#////////////////////////////////////////////////////////////////////////////

class DigitalProductFile(db.Model):
    """Model for digital product files"""
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer)
    download_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    product = db.relationship('Product', backref=db.backref('digital_files', lazy=True))
    
    def get_file_size_mb(self):
        return round(self.file_size / (1024 * 1024), 2) if self.file_size else 0



class LearningMaterial(db.Model):
    """Model for learning materials shared in classes"""
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    class_id = db.Column(db.String(50), nullable=False)
    class_type = db.Column(db.String(20), nullable=False)
    actual_class_id = db.Column(db.Integer, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    creator = db.relationship('User', foreign_keys=[created_by], lazy='select')
    
@property
def class_name(self):
    if self.class_id.startswith('student_'):
        # Individual student sharing
        student_id = int(self.class_id.replace('student_', ''))
        student = User.query.get(student_id)
        return f"👤 {student.first_name} {student.last_name}" if student else "Unknown Student"
    
    elif self.class_type == 'individual':
        class_obj = IndividualClass.query.get(self.actual_class_id)
        return f"📖 {class_obj.name}" if class_obj else "Unknown Individual Class"
    
    elif self.class_type == 'group':
        class_obj = GroupClass.query.get(self.actual_class_id)
        return f"🎓 {class_obj.name}" if class_obj else "Unknown Group Class"
    
    return "Unknown Class"

# Add back_populates to User model relationships
User.individual_classes = db.relationship('IndividualClass', 
                                         secondary=individual_class_students,
                                         back_populates='students', lazy='select')
User.group_classes = db.relationship('GroupClass', 
                                    secondary=group_class_students,
                                    back_populates='students', lazy='select')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


                              
@app.route('/admin/fix-password-hash-length')
@login_required
def fix_password_hash_length():
    """Fix password_hash field length - ADMIN ONLY"""
    if not current_user.is_admin:
        return "Access denied: Admin privileges required", 403
    
    try:
        # Increase password_hash field length from 120 to 255 characters
        with db.engine.connect() as conn:
            # PostgreSQL syntax for Render
            conn.execute(db.text('ALTER TABLE "user" ALTER COLUMN password_hash TYPE VARCHAR(255)'))
            conn.commit()
        
        return """
        <html>
        <head><title>Database Fixed</title>
        <style>body { font-family: Arial; padding: 20px; text-align: center; }</style></head>
        <body>
            <h1>✅ Database Fixed Successfully!</h1>
            <p><strong>password_hash</strong> field expanded from 120 to 255 characters</p>
            <p>Registration should now work properly.</p>
            <br>
            <p><a href="/register" style="background: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🧪 Test Registration</a></p>
            <p><a href="/admin/dashboard" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">← Back to Admin</a></p>
        </body>
        </html>
        """
        
    except Exception as e:
        return f"""
        <html>
        <head><title>Migration Error</title>
        <style>body {{ font-family: Arial; padding: 20px; text-align: center; }}</style></head>
        <body>
            <h1>❌ Migration Failed</h1>
            <p><strong>Error:</strong> {str(e)}</p>
            <p>Contact support if this persists.</p>
            <p><a href="/admin/dashboard">← Back to Admin</a></p>
        </body>
        </html>
        """, 500

        
# ========================================
# HELPER FUNCTIONS
# ========================================

def allowed_file(filename, file_type='general'):
    """Check if file extension is allowed for upload"""
    if file_type == 'video':
        allowed_extensions = {'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv'}
    elif file_type == 'material':
        allowed_extensions = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'zip', 'rar'}
    else:
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'mp4', 'avi', 'mov'}
    
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def send_bulk_email(recipients, subject, message):
    """Send bulk emails to recipients using EmailMessage and SMTP."""
    sent_count = 0
    try:
        server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
        server.starttls()
        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])

        for user in recipients:
            try:
                msg = EmailMessage()
                msg['From'] = app.config['MAIL_DEFAULT_SENDER']
                msg['To'] = user.email
                msg['Subject'] = subject or "Message from Learning Management System"

                body = f"""Dear {user.first_name} {user.last_name},

{message}

Best regards,
Learning Management System Team
"""
                msg.set_content(body)
                server.send_message(msg)
                sent_count += 1
            except Exception as e:
                print(f"Failed to send email to {user.email}: {e}")
                continue
        server.quit()
    except Exception as e:
        print(f"Failed to connect to email server: {e}")
        return 0
    return sent_count

def generate_whatsapp_links(recipients, message):
    whatsapp_links = []
    for user in recipients:
        if not user.whatsapp_number:
            continue

        phone = ''.join(filter(str.isdigit, user.whatsapp_number))
        formatted_message = f"Hello {user.first_name},\n\n{message}\n\nBest regards,\nLearning Management System"
        encoded_message = urllib.parse.quote(formatted_message)

        whatsapp_link = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_message}"
        whatsapp_links.append({
            'user': user,
            'link': whatsapp_link,
            'message': formatted_message
        })
    return whatsapp_links


# ========================================
# ADD ALL OTHER ROUTES HERE
# ========================================

# ========================================
# AUTHENTICATION ROUTES
# ========================================

@app.route('/admin/enrollment/<int:enrollment_id>')
@login_required
def view_enrollment(enrollment_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    enrollment = ClassEnrollment.query.get_or_404(enrollment_id)
    return render_template('view_enrollment.html', enrollment=enrollment, IndividualClass=IndividualClass, GroupClass=GroupClass)

# Replace your existing update_enrollment_status route in app.py with this fixed version:

@app.route('/admin/update_enrollment_status/<int:enrollment_id>', methods=['POST'])
@login_required
def update_enrollment_status(enrollment_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    enrollment = ClassEnrollment.query.get_or_404(enrollment_id)
    new_status = request.form.get('status')
    
    if new_status in ['pending', 'completed', 'failed']:
        old_status = enrollment.status
        enrollment.status = new_status
        
        if new_status == 'completed' and old_status != 'completed':
            # Get the student
            student = User.query.get(enrollment.user_id)
            
            if student:
                # Get the class based on type
                if enrollment.class_type == 'individual':
                    class_obj = IndividualClass.query.get(enrollment.class_id)
                    class_name = class_obj.name if class_obj else "Unknown Class"
                    
                    # Add student to individual class if not already enrolled
                    if class_obj and student not in class_obj.students:
                        class_obj.students.append(student)
                        flash(f'✅ Enrollment approved! {student.first_name} {student.last_name} has been added to "{class_name}" individual class.', 'success')
                        print(f"✅ Added {student.username} to individual class {class_name}")
                    elif class_obj and student in class_obj.students:
                        flash(f'✅ Enrollment approved! {student.first_name} {student.last_name} was already in "{class_name}" individual class.', 'info')
                    else:
                        flash(f'❌ Error: Individual class not found (ID: {enrollment.class_id})', 'danger')
                        
                elif enrollment.class_type == 'group':
                    class_obj = GroupClass.query.get(enrollment.class_id)
                    class_name = class_obj.name if class_obj else "Unknown Class"
                    
                    # Check if group class is full
                    if class_obj:
                        if len(class_obj.students) >= class_obj.max_students:
                            flash(f'❌ Cannot approve enrollment: Group class "{class_name}" is full ({len(class_obj.students)}/{class_obj.max_students} students).', 'warning')
                            enrollment.status = 'pending'  # Revert status
                        elif student not in class_obj.students:
                            class_obj.students.append(student)
                            flash(f'✅ Enrollment approved! {student.first_name} {student.last_name} has been added to "{class_name}" group class. ({len(class_obj.students)}/{class_obj.max_students} students)', 'success')
                            print(f"✅ Added {student.username} to group class {class_name}")
                        else:
                            flash(f'✅ Enrollment approved! {student.first_name} {student.last_name} was already in "{class_name}" group class.', 'info')
                    else:
                        flash(f'❌ Error: Group class not found (ID: {enrollment.class_id})', 'danger')
                        
                # Commit the changes
                db.session.commit()
                
                # Send confirmation email to student (optional)
                try:
                    if class_obj:
                        subject = f"Class Enrollment Approved - {class_name}"
                        message = f"""
Dear {student.first_name},

Great news! Your enrollment in "{class_name}" has been approved.

You can now:
- Access learning materials shared by your instructor
- Participate in class activities  
- View class content in your student dashboard

Login to your dashboard: https://www.techbuxin.com/student/dashboard

Best regards,
BuXin Future Academy Team
"""
                        send_bulk_email([student], subject, message)
                        print(f"📧 Sent confirmation email to {student.email}")
                except Exception as e:
                    print(f"❌ Failed to send confirmation email: {e}")
            else:
                flash(f'❌ Error: Student not found (ID: {enrollment.user_id})', 'danger')
                
        elif new_status == 'failed':
            flash(f'❌ Enrollment marked as failed.', 'warning')
        else:
            flash(f'📝 Enrollment status updated to {new_status}.', 'info')
            
        db.session.commit()
    else:
        flash('❌ Invalid status!', 'danger')
    
    return redirect(url_for('view_enrollment', enrollment_id=enrollment_id))

# Add this utility route to your app.py to fix existing approved enrollments:

@app.route('/admin/fix-existing-enrollments')
@login_required
def fix_existing_enrollments():
    """Fix existing approved enrollments by adding students to classes - ADMIN ONLY"""
    if not current_user.is_admin:
        return "Access denied: Admin privileges required", 403
    
    try:
        # Get all completed enrollments
        completed_enrollments = ClassEnrollment.query.filter_by(status='completed').all()
        
        fixed_individual = 0
        fixed_group = 0
        errors = []
        
        for enrollment in completed_enrollments:
            try:
                student = User.query.get(enrollment.user_id)
                if not student:
                    errors.append(f"Enrollment #{enrollment.id}: Student not found (ID: {enrollment.user_id})")
                    continue
                
                if enrollment.class_type == 'individual':
                    class_obj = IndividualClass.query.get(enrollment.class_id)
                    if class_obj:
                        if student not in class_obj.students:
                            class_obj.students.append(student)
                            fixed_individual += 1
                            print(f"✅ Fixed: Added {student.username} to individual class {class_obj.name}")
                    else:
                        errors.append(f"Enrollment #{enrollment.id}: Individual class not found (ID: {enrollment.class_id})")
                        
                elif enrollment.class_type == 'group':
                    class_obj = GroupClass.query.get(enrollment.class_id)
                    if class_obj:
                        if student not in class_obj.students:
                            if len(class_obj.students) < class_obj.max_students:
                                class_obj.students.append(student)
                                fixed_group += 1
                                print(f"✅ Fixed: Added {student.username} to group class {class_obj.name}")
                            else:
                                errors.append(f"Enrollment #{enrollment.id}: Group class '{class_obj.name}' is full")
                    else:
                        errors.append(f"Enrollment #{enrollment.id}: Group class not found (ID: {enrollment.class_id})")
                        
            except Exception as e:
                errors.append(f"Enrollment #{enrollment.id}: {str(e)}")
        
        # Commit all fixes
        db.session.commit()
        
        # Generate report
        html = f"""
        <html>
        <head><title>Enrollment Fix Results</title>
        <style>
            body {{ font-family: Arial; padding: 20px; background: #f8f9fa; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 2rem; border-radius: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }}
            .success {{ color: #28a745; background: #d4edda; padding: 1rem; border-radius: 5px; margin: 1rem 0; }}
            .warning {{ color: #856404; background: #fff3cd; padding: 1rem; border-radius: 5px; margin: 1rem 0; }}
            .error {{ color: #721c24; background: #f8d7da; padding: 1rem; border-radius: 5px; margin: 1rem 0; }}
            ul {{ margin: 1rem 0; }}
            .stats {{ display: flex; justify-content: space-around; margin: 2rem 0; }}
            .stat {{ text-align: center; padding: 1rem; background: #f8f9fa; border-radius: 10px; }}
            .stat-number {{ font-size: 2rem; font-weight: bold; color: #007bff; }}
        </style>
        </head>
        <body>
            <div class="container">
                <h1>🔧 Enrollment Fix Results</h1>
                
                <div class="stats">
                    <div class="stat">
                        <div class="stat-number">{completed_enrollments.count()}</div>
                        <div>Total Enrollments</div>
                    </div>
                    <div class="stat">
                        <div class="stat-number">{fixed_individual}</div>
                        <div>Individual Fixed</div>
                    </div>
                    <div class="stat">
                        <div class="stat-number">{fixed_group}</div>
                        <div>Group Fixed</div>
                    </div>
                    <div class="stat">
                        <div class="stat-number">{len(errors)}</div>
                        <div>Errors</div>
                    </div>
                </div>
                
                <div class="success">
                    <h3>✅ Successfully Fixed</h3>
                    <p><strong>Individual Classes:</strong> {fixed_individual} students added</p>
                    <p><strong>Group Classes:</strong> {fixed_group} students added</p>
                    <p><strong>Total Fixed:</strong> {fixed_individual + fixed_group} enrollments</p>
                </div>
        """
        
        if errors:
            html += f"""
                <div class="warning">
                    <h3>⚠️ Errors Encountered ({len(errors)})</h3>
                    <ul>
            """
            for error in errors:
                html += f"<li>{error}</li>"
            html += "</ul></div>"
        
        html += f"""
                <div class="success">
                    <h3>🎯 What Happened</h3>
                    <p>This fix process reviewed all approved class enrollments and ensured students were properly added to their classes. Now:</p>
                    <ul>
                        <li>✅ Students can see their classes in the student dashboard</li>
                        <li>✅ Admins can share materials with enrolled students</li>
                        <li>✅ Learning materials will appear for enrolled students</li>
                        <li>✅ Class rosters are accurate</li>
                    </ul>
                </div>
                
                <div style="text-align: center; margin-top: 2rem;">
                    <a href="/admin/dashboard" style="background: #007bff; color: white; padding: 1rem 2rem; text-decoration: none; border-radius: 5px; margin: 0 1rem;">← Admin Dashboard</a>
                    <a href="/admin/enrollments" style="background: #28a745; color: white; padding: 1rem 2rem; text-decoration: none; border-radius: 5px; margin: 0 1rem;">View Enrollments</a>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
        
    except Exception as e:
        return f"""
        <html>
        <head><title>Fix Failed</title>
        <style>body {{ font-family: Arial; padding: 20px; text-align: center; }}</style></head>
        <body>
            <h1>❌ Fix Failed</h1>
            <p><strong>Error:</strong> {str(e)}</p>
            <p><a href="/admin/dashboard">← Back to Admin Dashboard</a></p>
        </body>
        </html>
        """, 500

# Add this debug route to see what's happening with enrollments:

@app.route('/debug/enrollments')
@login_required
def debug_enrollments():
    """Debug route to check enrollment status and class memberships"""
    if not current_user.is_admin:
        return "Admin only", 403
    
    # Get all enrollments
    all_enrollments = ClassEnrollment.query.all()
    individual_classes = IndividualClass.query.all()
    group_classes = GroupClass.query.all()
    
    html = f"""
    <html>
    <head><title>Enrollment Debug</title>
    <style>
        body {{ font-family: Arial; padding: 20px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .completed {{ background-color: #d4edda; }}
        .pending {{ background-color: #fff3cd; }}
        .failed {{ background-color: #f8d7da; }}
        .enrolled {{ color: #28a745; font-weight: bold; }}
        .not-enrolled {{ color: #dc3545; font-weight: bold; }}
    </style>
    </head>
    <body>
        <h1>🔍 Enrollment Debug Report</h1>
        
        <h2>📊 Summary</h2>
        <p><strong>Total Enrollments:</strong> {len(all_enrollments)}</p>
        <p><strong>Individual Classes:</strong> {len(individual_classes)}</p>
        <p><strong>Group Classes:</strong> {len(group_classes)}</p>
        
        <h2>📋 All Enrollments</h2>
        <table>
            <tr>
                <th>ID</th>
                <th>Student</th>
                <th>Class Type</th>
                <th>Class Name</th>
                <th>Status</th>
                <th>Actually Enrolled?</th>
                <th>Issue</th>
            </tr>
    """
    
    for enrollment in all_enrollments:
        student = User.query.get(enrollment.user_id)
        student_name = f"{student.first_name} {student.last_name}" if student else "Unknown"
        
        # Check if student is actually in the class
        actually_enrolled = False
        class_name = "Unknown"
        issue = ""
        
        if enrollment.class_type == 'individual':
            class_obj = IndividualClass.query.get(enrollment.class_id)
            if class_obj:
                class_name = class_obj.name
                actually_enrolled = student in class_obj.students if student else False
                if enrollment.status == 'completed' and not actually_enrolled:
                    issue = "❌ Approved but not in class roster"
            else:
                issue = "❌ Class not found"
                
        elif enrollment.class_type == 'group':
            class_obj = GroupClass.query.get(enrollment.class_id)
            if class_obj:
                class_name = class_obj.name
                actually_enrolled = student in class_obj.students if student else False
                if enrollment.status == 'completed' and not actually_enrolled:
                    issue = "❌ Approved but not in class roster"
            else:
                issue = "❌ Class not found"
        
        status_class = enrollment.status
        enrolled_class = "enrolled" if actually_enrolled else "not-enrolled"
        enrolled_text = "✅ YES" if actually_enrolled else "❌ NO"
        
        html += f"""
            <tr class="{status_class}">
                <td>{enrollment.id}</td>
                <td>{student_name}</td>
                <td>{enrollment.class_type.title()}</td>
                <td>{class_name}</td>
                <td>{enrollment.status.title()}</td>
                <td class="{enrolled_class}">{enrolled_text}</td>
                <td>{issue}</td>
            </tr>
        """
    
    html += """
        </table>
        
        <h2>🏫 Individual Classes</h2>
        <table>
            <tr>
                <th>Class ID</th>
                <th>Class Name</th>
                <th>Students Enrolled</th>
                <th>Student Names</th>
            </tr>
    """
    
    for iclass in individual_classes:
        student_names = [f"{s.first_name} {s.last_name}" for s in iclass.students]
        html += f"""
            <tr>
                <td>{iclass.id}</td>
                <td>{iclass.name}</td>
                <td>{len(iclass.students)}</td>
                <td>{', '.join(student_names) if student_names else 'No students'}</td>
            </tr>
        """
    
    html += """
        </table>
        
        <h2>👥 Group Classes</h2>
        <table>
            <tr>
                <th>Class ID</th>
                <th>Class Name</th>
                <th>Students Enrolled</th>
                <th>Max Students</th>
                <th>Student Names</th>
            </tr>
    """
    
    for gclass in group_classes:
        student_names = [f"{s.first_name} {s.last_name}" for s in gclass.students]
        html += f"""
            <tr>
                <td>{gclass.id}</td>
                <td>{gclass.name}</td>
                <td>{len(gclass.students)}</td>
                <td>{gclass.max_students}</td>
                <td>{', '.join(student_names) if student_names else 'No students'}</td>
            </tr>
        """
    
    html += f"""
        </table>
        
        <h2>🔧 Actions</h2>
        <p><a href="/admin/fix-existing-enrollments" style="background: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">🔧 Fix All Enrollment Issues</a></p>
        <p><a href="/admin/dashboard">← Back to Admin Dashboard</a></p>
        <p><a href="/admin/enrollments">View Enrollments</a></p>
    </body>
    </html>
    """
    
    return html

# ========================================
# ADDITIONAL ROUTES
# ========================================

@app.route('/about')
def about_us():
    context = {
        'page_title': 'About BuXin Future Academy',
        'meta_description': 'Learn about BuXin Future Academy - pioneering robotics, AI, and electric vehicle technology in Africa.'
    }
    return render_template('about_us.html', **context)
                           
@app.route('/')                           
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('Login successful!', 'success')
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        whatsapp_number = request.form.get('whatsapp_number')

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return render_template('register.html')
        
        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            whatsapp_number=whatsapp_number,
            is_student=True,
            is_admin=False
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# ========================================
# ADMIN DASHBOARD ROUTES
# ========================================

@app.route('/admin/dashboard', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        class_id = request.form.get('class_id')
        content = request.form.get('message', '').strip()

        if not class_id or not content:
            flash("Both recipient and content are required.", "danger")
        else:
            # Handle different recipient types
            if class_id.startswith('individual_student_'):
                # Single student
                student_id = int(class_id.replace('individual_student_', ''))
                student = User.query.get(student_id)
                if student:
                    material = LearningMaterial(
                        class_id=f"student_{student_id}",
                        class_type='individual',
                        actual_class_id=student_id,
                        content=content,
                        created_by=current_user.id
                    )
                    db.session.add(material)
                    db.session.commit()
                    flash(f"Material shared with {student.first_name} {student.last_name}!", "success")
                else:
                    flash("Student not found.", "danger")
            
            elif class_id.startswith('individual_') or class_id.startswith('group_'):
                # Class-based sharing (existing functionality)
                class_type, actual_class_id = class_id.split('_', 1)
                
                material = LearningMaterial(
                    class_id=class_id,
                    class_type=class_type,
                    actual_class_id=int(actual_class_id),
                    content=content,
                    created_by=current_user.id
                )
                db.session.add(material)
                db.session.commit()
                flash("Learning material shared with class!", "success")
            
            return redirect(url_for('admin_dashboard'))

    # Get all data for the dashboard
    students = User.query.filter_by(is_student=True).all()
    materials = LearningMaterial.query.order_by(LearningMaterial.id.desc()).limit(20).all()
    individual_classes = IndividualClass.query.all()
    group_classes = GroupClass.query.all()
    
    # Get orders and enrollments
    course_orders = Purchase.query.order_by(Purchase.purchased_at.desc()).limit(50).all()
    product_orders = ProductOrder.query.order_by(ProductOrder.ordered_at.desc()).limit(50).all()
    enrollments = ClassEnrollment.query.order_by(ClassEnrollment.enrolled_at.desc()).limit(50).all()

    # Get individual students who are enrolled in individual classes
    individual_students = []
    for iclass in individual_classes:
        for student in iclass.students:
            if student not in individual_students:
                individual_students.append(student)

    # Build class options for backward compatibility
    class_options = []
    for iclass in individual_classes:
        class_options.append({
            'id': f'individual_{iclass.id}',
            'name': f'{iclass.name} (Individual)',
            'student_count': len(iclass.students)
        })
    
    for gclass in group_classes:
        class_options.append({
            'id': f'group_{gclass.id}',
            'name': f'{gclass.name} (Group)',
            'student_count': len(gclass.students)
        })

    return render_template(
        "admin_dashboard.html",
        students=students,
        individual_students=individual_students,  # Individual students list
        materials=materials,
        individual_classes=individual_classes,
        group_classes=group_classes,
        course_orders=course_orders,              # Course orders
        product_orders=product_orders,            # Product orders  
        enrollments=enrollments,                  # Class enrollments
        class_options=class_options,
        # Add these imports for the template
        IndividualClass=IndividualClass,
        GroupClass=GroupClass
    )
@app.route('/admin/create_class', methods=['GET', 'POST'])
@login_required
def create_class():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        class_type = request.form['class_type']
        name = request.form['name']
        description = request.form.get('description', '')
        student_ids = request.form.getlist('students')
        
        if class_type == 'individual':
            new_class = IndividualClass(
                name=name,
                description=description,
                teacher_id=current_user.id
            )
        else:
            max_students = int(request.form.get('max_students', 10))
            new_class = GroupClass(
                name=name,
                description=description,
                teacher_id=current_user.id,
                max_students=max_students
            )
        
        db.session.add(new_class)
        db.session.commit()
        
        students = User.query.filter(User.id.in_(student_ids)).all()
        new_class.students.extend(students)
        db.session.commit()
        
        flash(f'{class_type.title()} class created successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    students = User.query.filter_by(is_student=True).all()
    return render_template('create_class.html', students=students)

# ========================================
# COURSE MANAGEMENT ROUTES
# ========================================

@app.route('/admin/courses')
@login_required
def admin_courses():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    courses = Course.query.order_by(Course.created_at.desc()).all()
    return render_template('admin_courses.html', courses=courses)

@app.route('/admin/create_course', methods=['GET', 'POST'])
@login_required
def create_course():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            # Basic course information
            title = request.form['title']
            description = request.form['description']
            short_description = request.form.get('short_description', '')
            price = float(request.form['price'])
            duration_weeks = int(request.form.get('duration_weeks', 4))
            level = request.form['level']
            category = request.form['category']
            image_url = request.form.get('image_url', '')
            
            # Create the course
            course = Course(
                title=title,
                description=description,
                short_description=short_description,
                price=price,
                duration_weeks=duration_weeks,
                level=level,
                category=category,
                image_url=image_url,
                created_by=current_user.id
            )
            
            db.session.add(course)
            db.session.flush()
            
            # Handle video uploads - CLOUDINARY VERSION
            video_files = request.files.getlist('video_files')
            video_titles = request.form.getlist('video_titles')
            video_descriptions = request.form.getlist('video_descriptions')
            video_orders = request.form.getlist('video_orders')
            video_durations = request.form.getlist('video_durations')
            
            for i, video_file in enumerate(video_files):
                if video_file and video_file.filename and allowed_file(video_file.filename, 'video'):
                    video_file.seek(0, 2)
                    file_size = video_file.tell()
                    video_file.seek(0)
                    
                    if file_size > 500 * 1024 * 1024:  # 500MB
                        flash(f'Video file {video_file.filename} is too large. Maximum size is 500MB.', 'warning')
                        continue
                    
                    print(f"📤 Uploading {video_file.filename} to Cloudinary...")
                    
                    # Upload to Cloudinary instead of local storage
                    upload_result = upload_video_to_cloudinary(video_file, course.id, i+1)
                    
                    if upload_result:
                        # Create a fallback filename for compatibility
                        fallback_filename = f"cloudinary_{upload_result['public_id']}.mp4"
                        
                        course_video = CourseVideo(
                            course_id=course.id,
                            title=video_titles[i] if i < len(video_titles) else f"Lesson {i+1}",
                            description=video_descriptions[i] if i < len(video_descriptions) else "",
                            video_filename=fallback_filename,  # Fallback filename
                            video_url=upload_result['url'],  # Cloudinary URL
                            duration=video_durations[i] if i < len(video_durations) and video_durations[i] else None,
                            order_index=int(video_orders[i]) if i < len(video_orders) else i+1
                        )
                        db.session.add(course_video)
                        print(f"✅ Video saved to database: {course_video.title}")
                    else:
                        flash(f'Failed to upload video: {video_file.filename}', 'danger')
                        print(f"❌ Failed to upload: {video_file.filename}")
            
            # Handle course materials (keep local storage for materials)
            material_files = request.files.getlist('course_materials')
            materials_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'materials')
            os.makedirs(materials_folder, exist_ok=True)
            
            for material_file in material_files:
                if material_file and material_file.filename and allowed_file(material_file.filename, 'material'):
                    material_file.seek(0, 2)
                    file_size = material_file.tell()
                    material_file.seek(0)
                    
                    if file_size > 10 * 1024 * 1024:
                        flash(f'Material file {material_file.filename} is too large. Maximum size is 10MB.', 'warning')
                        continue
                    
                    filename = secure_filename(material_file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                    unique_filename = f"{timestamp}{course.id}_{filename}"
                    
                    material_path = os.path.join(materials_folder, unique_filename)
                    material_file.save(material_path)
                    
                    course_material = CourseMaterial(
                        course_id=course.id,
                        title=filename.rsplit('.', 1)[0],
                        filename=unique_filename,
                        file_type=filename.rsplit('.', 1)[1].lower(),
                        file_size=file_size
                    )
                    
                    db.session.add(course_material)
            
            db.session.commit()
            
            flash('Course created successfully with videos and materials!', 'success')
            return redirect(url_for('admin_courses'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating course: {str(e)}', 'danger')
            return render_template('create_course.html')
    
    return render_template('create_course.html')

@app.route('/admin/edit_course/<int:course_id>', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    course = Course.query.get_or_404(course_id)
    
    if request.method == 'POST':
        try:
            # Get and validate form data
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            short_description = request.form.get('short_description', '').strip()
            category = request.form.get('category', '').strip()
            level = request.form.get('level', '').strip()
            image_url = request.form.get('image_url', '').strip()
            
            # Validate required fields
            if not all([title, description, category, level]):
                flash('Please fill in all required fields.', 'danger')
                return render_template('edit_course.html', course=course)
            
            # Handle price
            try:
                price = float(request.form.get('price', 0))
                if price < 0:
                    flash('Price must be positive.', 'danger')
                    return render_template('edit_course.html', course=course)
            except ValueError:
                flash('Invalid price format.', 'danger')
                return render_template('edit_course.html', course=course)
            
            # Handle duration
            try:
                duration_weeks = int(request.form.get('duration_weeks', 4))
                if duration_weeks < 1: duration_weeks = 1
                if duration_weeks > 52: duration_weeks = 52
            except ValueError:
                duration_weeks = 4
            
            # Update course (ONLY fields that exist in your model)
            course.title = title
            course.description = description
            course.short_description = short_description
            course.price = price
            course.duration_weeks = duration_weeks
            course.level = level
            course.category = category
            course.image_url = image_url if image_url else None
            course.is_active = 'is_active' in request.form
            
            # Only try to set featured if it exists in the model
            if hasattr(course, 'featured'):
                course.featured = 'featured' in request.form
            
            db.session.commit()
            flash(f'Course "{course.title}" updated successfully!', 'success')
            return redirect(url_for('admin_courses'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Update failed: {str(e)}', 'danger')
            return render_template('edit_course.html', course=course)
    
    return render_template('edit_course.html', course=course)


# =====================================================
# STEP 2: ADD ONLY THIS ONE SAFE MIGRATION ROUTE
# (Add this anywhere in your admin routes section)
# =====================================================

@app.route('/admin/safe-migrate')
@login_required  
def safe_migrate():
    """Safely add featured column only if it doesn't exist - NO DUPLICATES"""
    if not current_user.is_admin:
        return "Access denied", 403
    
    try:
        # Check if column already exists using SQLAlchemy inspector
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('course')]
        
        if 'featured' in columns:
            return "✅ Featured column already exists. No action needed."
        
        # Add column only if it doesn't exist
        with db.engine.connect() as conn:
            if 'sqlite' in str(db.engine.url):
                # SQLite syntax
                conn.execute(db.text('ALTER TABLE course ADD COLUMN featured BOOLEAN DEFAULT 0'))
            else:
                # PostgreSQL/MySQL syntax  
                conn.execute(db.text('ALTER TABLE course ADD COLUMN featured BOOLEAN DEFAULT FALSE'))
            conn.commit()
        
        return "✅ Featured column added successfully!"
        
    except Exception as e:
        return f"❌ Migration failed: {str(e)}"


# Add this route to your Flask application (app.py)
# Place it in the COURSE MANAGEMENT ROUTES section

@app.route('/admin/delete_course/<int:course_id>', methods=['POST'])
@login_required
def delete_course(course_id):
    """Delete a course and its associated content"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    try:
        course = Course.query.get_or_404(course_id)
        course_title = course.title
        
        # Check if there are any purchases for this course
        purchases_count = Purchase.query.filter_by(course_id=course_id).count()
        
        if purchases_count > 0:
            # Check if there are completed purchases
            completed_purchases = Purchase.query.filter_by(course_id=course_id, status='completed').count()
            if completed_purchases > 0:
                flash(f'Cannot delete "{course_title}" because {completed_purchases} students have purchased this course. Deactivate it instead.', 'warning')
                return redirect(url_for('admin_courses'))
            else:
                # Delete pending/failed purchases
                Purchase.query.filter_by(course_id=course_id).delete()
        
        # Check if there are any cart items for this course
        cart_items_count = CartItem.query.filter_by(course_id=course_id).count()
        if cart_items_count > 0:
            # Remove from all carts
            CartItem.query.filter_by(course_id=course_id).delete()
        
        # Delete associated course videos
        videos = CourseVideo.query.filter_by(course_id=course_id).all()
        video_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
        
        for video in videos:
            # Delete video file from filesystem
            video_path = os.path.join(video_folder, video.video_filename)
            try:
                if os.path.exists(video_path):
                    os.remove(video_path)
            except Exception as e:
                print(f"Warning: Could not delete video file {video.video_filename}: {e}")
            
            # Delete video record from database
            db.session.delete(video)
        
        # Delete associated course materials
        materials = CourseMaterial.query.filter_by(course_id=course_id).all()
        materials_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'materials')
        
        for material in materials:
            # Delete material file from filesystem
            material_path = os.path.join(materials_folder, material.filename)
            try:
                if os.path.exists(material_path):
                    os.remove(material_path)
            except Exception as e:
                print(f"Warning: Could not delete material file {material.filename}: {e}")
            
            # Delete material record from database
            db.session.delete(material)
        
        # Finally, delete the course itself
        db.session.delete(course)
        db.session.commit()
        
        flash(f'Course "{course_title}" and all its content have been deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting course: {str(e)}', 'danger')
        print(f"Error deleting course {course_id}: {e}")
    
    return redirect(url_for('admin_courses'))


@app.route('/course_video/<filename>')
@login_required
def course_video(filename):
    """Serve video files from Cloudinary or local storage"""
    
    # Check if video exists in database
    video = CourseVideo.query.filter_by(video_filename=filename).first()
    if not video:
        flash('Video not found in database', 'error')
        return f"Video '{filename}' not found in database", 404
    
    # Check permissions (only if not admin)
    if not current_user.is_admin:
        purchase = Purchase.query.filter_by(
            user_id=current_user.id,
            course_id=video.course_id,
            status='completed'
        ).first()
        
        if not purchase and not video.is_preview:
            flash('You need to purchase this course to access the videos.', 'warning')
            return "Access denied - course not purchased", 403
    
    # If video has a Cloudinary URL, redirect to it
    if video.video_url:
        print(f"📹 Serving from Cloudinary: {video.video_url}")
        return redirect(video.video_url)
    
    # Fallback to local file system (for videos not yet migrated)
    video_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
    video_file_path = os.path.join(video_folder, filename)
    
    if os.path.exists(video_file_path):
        print(f"📁 Serving from local storage: {filename}")
        return send_from_directory(
            video_folder, 
            filename, 
            mimetype='video/mp4',
            as_attachment=False
        )
    else:
        # Video not found anywhere
        error_msg = f"Video file missing: {filename}"
        print(f"❌ ERROR: {error_msg}")
        
        return f"""
        <div style="padding: 20px; font-family: Arial;">
            <h1>Video Not Available</h1>
            <p><strong>Video:</strong> {video.title}</p>
            <p><strong>Status:</strong> Not found in Cloudinary or local storage</p>
            <p><strong>Solutions:</strong></p>
            <ul>
                <li><a href="/admin/migrate-existing-videos">🔄 Check Migration Status</a></li>
                <li><a href="/admin/reupload-videos">📤 Re-upload Missing Videos</a></li>
            </ul>
            <p><a href="/admin/courses">← Back to Courses</a></p>
        </div>
        """, 404


# ========================================
# COMPLETE VIDEO MANAGEMENT ROUTES - CONFLICT-FREE VERSION
# ========================================

@app.route('/admin/add_video_to_course', methods=['POST'])
@login_required
def add_video_to_course():
    """Add a new video to an existing course - FIXED VERSION"""
    if not current_user.is_admin:
        return {'success': False, 'error': 'Access denied'}, 403
    
    try:
        print("🎬 add_video_to_course route called")
        
        # Get course ID from form data
        course_id = request.form.get('course_id')
        if not course_id:
            print("❌ No course_id provided")
            return {'success': False, 'error': 'Course ID is required'}, 400
        
        print(f"📚 Course ID: {course_id}")
        
        # Verify course exists
        course = Course.query.get_or_404(course_id)
        print(f"✅ Course found: {course.title}")
        
        # Get form data
        video_title = request.form.get('video_title', '').strip()
        video_description = request.form.get('video_description', '').strip()
        video_duration = request.form.get('video_duration', '').strip()
        video_order = request.form.get('video_order', '1')
        
        print(f"📝 Video details: {video_title}, Order: {video_order}")
        
        if not video_title:
            return {'success': False, 'error': 'Video title is required'}, 400
        
        # Handle video file upload
        video_file = request.files.get('video_file')
        if not video_file or video_file.filename == '':
            return {'success': False, 'error': 'Video file is required'}, 400
        
        if not allowed_file(video_file.filename, 'video'):
            return {'success': False, 'error': 'Invalid video file format'}, 400
        
        # Check file size (500MB limit)
        video_file.seek(0, 2)
        file_size = video_file.tell()
        video_file.seek(0)
        
        print(f"📁 File size: {file_size / (1024*1024):.1f}MB")
        
        if file_size > 500 * 1024 * 1024:  # 500MB
            return {'success': False, 'error': 'Video file is too large. Maximum size is 500MB.'}, 400
        
        print(f"📤 Starting Cloudinary upload for: {video_title}")
        
        # Upload to Cloudinary
        upload_result = upload_video_to_cloudinary(video_file, course.id, int(video_order))
        
        if not upload_result:
            print("❌ Cloudinary upload failed")
            return {'success': False, 'error': 'Failed to upload video to Cloudinary'}, 500
        
        print(f"✅ Cloudinary upload successful: {upload_result['url']}")
        
        # Create video record in database
        fallback_filename = f"cloudinary_{upload_result['public_id']}.mp4"
        
        course_video = CourseVideo(
            course_id=course.id,
            title=video_title,
            description=video_description,
            video_filename=fallback_filename,
            video_url=upload_result['url'],
            duration=video_duration if video_duration else None,
            order_index=int(video_order)
        )
        
        db.session.add(course_video)
        db.session.commit()
        
        print(f"✅ Video saved to database: {course_video.id}")
        
        # Return success response
        response_data = {
            'success': True,
            'message': f'Video "{video_title}" uploaded successfully',
            'video': {
                'id': course_video.id,
                'title': course_video.title,
                'description': course_video.description,
                'duration': course_video.duration,
                'order_index': course_video.order_index,
                'video_url': course_video.video_url,
                'video_filename': course_video.video_filename
            }
        }
        
        print(f"📤 Sending response: {response_data}")
        return response_data
        
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        print(f"❌ Error in add_video_to_course: {error_msg}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': error_msg}, 500


@app.route('/admin/delete_video/<int:video_id>', methods=['POST'])
@login_required
def delete_course_video_by_id(video_id):  # ✅ CONFLICT-FREE FUNCTION NAME
    """Delete a single video from a course"""
    if not current_user.is_admin:
        return {'success': False, 'error': 'Access denied'}, 403
    
    try:
        video = CourseVideo.query.get_or_404(video_id)
        video_title = video.title
        
        # Delete from Cloudinary if it's a Cloudinary video
        if video.video_url and 'cloudinary.com' in video.video_url:
            try:
                import re
                match = re.search(r'/course_videos/([^.]+)', video.video_url)
                if match:
                    public_id = f"course_videos/{match.group(1)}"
                    cloudinary.uploader.destroy(public_id, resource_type="video")
                    print(f"🗑️ Deleted from Cloudinary: {public_id}")
            except Exception as e:
                print(f"⚠️ Warning: Could not delete from Cloudinary: {e}")
        
        # Delete local file if it exists (fallback)
        elif video.video_filename and not video.video_url:
            try:
                video_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
                video_path = os.path.join(video_folder, video.video_filename)
                if os.path.exists(video_path):
                    os.remove(video_path)
                    print(f"🗑️ Deleted local file: {video.video_filename}")
            except Exception as e:
                print(f"⚠️ Warning: Could not delete local file: {e}")
        
        # Delete video record from database
        db.session.delete(video)
        db.session.commit()
        
        print(f"✅ Video deleted successfully: {video_title}")
        
        return {'success': True, 'message': f'Video "{video_title}" deleted successfully'}
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error deleting video: {str(e)}")
        return {'success': False, 'error': str(e)}, 500


@app.route('/admin/edit_video/<int:video_id>', methods=['GET', 'POST'])
@login_required
def edit_course_video_by_id(video_id):  # ✅ CONFLICT-FREE FUNCTION NAME
    """Edit video details (title, description, order, etc.)"""
    if not current_user.is_admin:
        return {'success': False, 'error': 'Access denied'}, 403
    
    video = CourseVideo.query.get_or_404(video_id)
    
    if request.method == 'POST':
        try:
            # Handle both JSON and form data
            if request.is_json:
                data = request.get_json()
            else:
                data = request.form
            
            # Update video details
            new_title = data.get('title', '').strip()
            new_description = data.get('description', '').strip()
            new_duration = data.get('duration', '').strip()
            new_order = data.get('order_index', video.order_index)
            
            if not new_title:
                return {'success': False, 'error': 'Video title is required'}, 400
            
            # Update video fields
            video.title = new_title
            video.description = new_description
            video.duration = new_duration if new_duration else None
            video.order_index = int(new_order)
            
            db.session.commit()
            
            print(f"✅ Video updated successfully: {video.title}")
            
            return {
                'success': True,
                'message': f'Video "{video.title}" updated successfully',
                'video': {
                    'id': video.id,
                    'title': video.title,
                    'description': video.description,
                    'duration': video.duration,
                    'order_index': video.order_index
                }
            }
            
        except ValueError as e:
            return {'success': False, 'error': 'Invalid order index'}, 400
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error updating video: {str(e)}")
            return {'success': False, 'error': str(e)}, 500
    
    # GET request - return video data for editing
    return {
        'success': True,
        'video': {
            'id': video.id,
            'title': video.title,
            'description': video.description,
            'duration': video.duration,
            'order_index': video.order_index,
            'course_id': video.course_id,
            'video_url': video.video_url,
            'video_filename': video.video_filename
        }
    }


@app.route('/admin/delete_material/<int:material_id>', methods=['POST'])
@login_required
def delete_course_material_by_id(material_id):  # ✅ CONFLICT-FREE FUNCTION NAME
    """Delete a single course material"""
    if not current_user.is_admin:
        return {'success': False, 'error': 'Access denied'}, 403
    
    try:
        material = CourseMaterial.query.get_or_404(material_id)
        material_title = material.title
        material_filename = material.filename
        
        # Delete file from filesystem
        try:
            materials_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'materials')
            material_path = os.path.join(materials_folder, material_filename)
            if os.path.exists(material_path):
                os.remove(material_path)
                print(f"🗑️ Deleted material file: {material_filename}")
        except Exception as e:
            print(f"⚠️ Warning: Could not delete material file: {e}")
        
        # Delete record from database
        db.session.delete(material)
        db.session.commit()
        
        print(f"✅ Material deleted successfully: {material_title}")
        
        return {
            'success': True, 
            'message': f'Material "{material_title}" deleted successfully'
        }
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error deleting material: {str(e)}")
        return {'success': False, 'error': str(e)}, 500


# ========================================
# ADDITIONAL HELPER ROUTE - BONUS
# ========================================

@app.route('/admin/add_material_to_course', methods=['POST'])
@login_required
def add_material_to_course():
    """Add a new material to an existing course - BONUS ROUTE"""
    if not current_user.is_admin:
        return {'success': False, 'error': 'Access denied'}, 403
    
    try:
        course_id = request.form.get('course_id')
        if not course_id:
            return {'success': False, 'error': 'Course ID is required'}, 400
        
        course = Course.query.get_or_404(course_id)
        
        # Get material title
        material_title = request.form.get('material_title', '').strip()
        
        # Handle file upload
        material_file = request.files.get('material_file')
        if not material_file or material_file.filename == '':
            return {'success': False, 'error': 'Material file is required'}, 400
        
        if not allowed_file(material_file.filename, 'material'):
            return {'success': False, 'error': 'Invalid file format. Allowed: PDF, DOC, DOCX, PPT, PPTX, TXT, ZIP'}, 400
        
        # Check file size (10MB limit for materials)
        material_file.seek(0, 2)
        file_size = material_file.tell()
        material_file.seek(0)
        
        if file_size > 10 * 1024 * 1024:  # 10MB
            return {'success': False, 'error': 'File is too large. Maximum size is 10MB.'}, 400
        
        # Save file
        filename = secure_filename(material_file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        unique_filename = f"{timestamp}{course.id}_{filename}"
        
        materials_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'materials')
        os.makedirs(materials_folder, exist_ok=True)
        material_path = os.path.join(materials_folder, unique_filename)
        material_file.save(material_path)
        
        # Create material record
        course_material = CourseMaterial(
            course_id=course.id,
            title=material_title if material_title else filename.rsplit('.', 1)[0],
            filename=unique_filename,
            file_type=filename.rsplit('.', 1)[1].lower(),
            file_size=file_size
        )
        
        db.session.add(course_material)
        db.session.commit()
        
        print(f"✅ Material added successfully: {course_material.title}")
        
        return {
            'success': True,
            'message': f'Material "{course_material.title}" added successfully',
            'material': {
                'id': course_material.id,
                'title': course_material.title,
                'filename': course_material.filename,
                'file_type': course_material.file_type,
                'file_size_mb': course_material.get_file_size_mb()
            }
        }
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error adding material: {str(e)}")
        return {'success': False, 'error': str(e)}, 500


# ========================================
# BULK OPERATIONS - BONUS ROUTES
# ========================================

@app.route('/admin/reorder_videos', methods=['POST'])
@login_required
def reorder_course_videos():
    """Reorder videos in a course - BONUS FEATURE"""
    if not current_user.is_admin:
        return {'success': False, 'error': 'Access denied'}, 403
    
    try:
        data = request.get_json()
        video_orders = data.get('video_orders', [])  # List of {id: video_id, order: new_order}
        
        if not video_orders:
            return {'success': False, 'error': 'No video orders provided'}, 400
        
        updated_count = 0
        for item in video_orders:
            video_id = item.get('id')
            new_order = item.get('order')
            
            if video_id and new_order is not None:
                video = CourseVideo.query.get(video_id)
                if video:
                    video.order_index = new_order
                    updated_count += 1
        
        if updated_count > 0:
            db.session.commit()
            print(f"✅ Reordered {updated_count} videos")
            return {'success': True, 'message': f'Reordered {updated_count} videos successfully'}
        else:
            return {'success': False, 'error': 'No valid videos found to reorder'}, 400
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error reordering videos: {str(e)}")
        return {'success': False, 'error': str(e)}, 500


@app.route('/admin/course/<int:course_id>/video_count')
@login_required
def get_course_video_count(course_id):
    """Get current video count for a course - UTILITY ROUTE"""
    if not current_user.is_admin:
        return {'success': False, 'error': 'Access denied'}, 403
    
    try:
        course = Course.query.get_or_404(course_id)
        video_count = CourseVideo.query.filter_by(course_id=course_id).count()
        
        return {
            'success': True,
            'course_id': course_id,
            'video_count': video_count,
            'course_title': course.title
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}, 500

# ========================================
# PRODUCT MANAGEMENT ROUTES (Keep these together)
# ========================================

@app.route('/admin/products')
@login_required
def admin_products():
    """Display all products with filtering and search"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    # Get filter parameters
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    status = request.args.get('status', '').strip()
    sort_by = request.args.get('sort', 'newest')
    
    # Start with base query
    query = Product.query
    
    # Apply filters
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            db.or_(
                Product.name.like(search_filter),
                Product.description.like(search_filter),
                Product.brand.like(search_filter),
                Product.sku.like(search_filter)
            )
        )
    
    if category:
        query = query.filter_by(category=category)
    
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    
    # Apply sorting
    if sort_by == 'name':
        query = query.order_by(Product.name.asc())
    elif sort_by == 'price_low':
        query = query.order_by(Product.price.asc())
    elif sort_by == 'price_high':
        query = query.order_by(Product.price.desc())
    elif sort_by == 'stock':
        query = query.order_by(Product.stock_quantity.desc())
    else:  # newest
        query = query.order_by(Product.created_at.desc())
    
    products = query.all()
    
    return render_template('admin_products.html', products=products)

# Replace your existing create_product route with this updated version

#///////////////////////////////////////////////////////////////////////////////////////////////////

@app.route('/admin/create_product', methods=['GET', 'POST'])
@login_required
def create_product():
    """Create a new product"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            short_description = request.form.get('short_description', '').strip()
            price = request.form.get('price', '0')
            product_type = request.form.get('product_type', '').strip()
            category = request.form.get('category', '').strip()
            brand = request.form.get('brand', '').strip()
            sku = request.form.get('sku', '').strip()
            stock_quantity = request.form.get('stock_quantity', '0')
            image_url = request.form.get('image_url', '').strip()
            is_active = 'is_active' in request.form
            featured = 'featured' in request.form
            
            # Validate required fields
            if not all([name, description, price, product_type, category]):
                flash('Please fill in all required fields (Name, Description, Price, Type, Category).', 'danger')
                return render_template('create_product.html')
            
            # Validate and convert price
            try:
                price = float(price)
                if price < 0:
                    flash('Price must be a positive number.', 'danger')
                    return render_template('create_product.html')
            except ValueError:
                flash('Please enter a valid price.', 'danger')
                return render_template('create_product.html')
            
            # Validate and convert stock quantity
            try:
                stock_quantity = int(stock_quantity)
                if stock_quantity < 0:
                    flash('Stock quantity must be a positive number.', 'danger')
                    return render_template('create_product.html')
            except ValueError:
                flash('Please enter a valid stock quantity.', 'danger')
                return render_template('create_product.html')
            
            # Auto-generate SKU if not provided
            if not sku:
                base_sku = name.upper().replace(' ', '-').replace('&', 'AND')
                base_sku = ''.join(c for c in base_sku if c.isalnum() or c == '-')[:10]
                
                counter = 1
                sku = f"{base_sku}-{counter:03d}"
                while Product.query.filter_by(sku=sku).first():
                    counter += 1
                    sku = f"{base_sku}-{counter:03d}"
            else:
                existing_product = Product.query.filter_by(sku=sku).first()
                if existing_product:
                    flash(f'SKU "{sku}" already exists. Please choose a different SKU.', 'danger')
                    return render_template('create_product.html')
            
            # For digital products, set stock to 0
            if product_type == 'Digital':
                stock_quantity = 0
            
            # Validate image URL if provided
            if image_url:
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(image_url)
                    if not all([parsed.scheme, parsed.netloc]):
                        flash('Please enter a valid image URL.', 'warning')
                        image_url = ''
                except:
                    flash('Please enter a valid image URL.', 'warning')
                    image_url = ''
            
            # Create the product
            product = Product(
                name=name,
                description=description,
                short_description=short_description,
                price=price,
                product_type=product_type,
                category=category,
                brand=brand,
                sku=sku,
                stock_quantity=stock_quantity,
                image_url=image_url,
                is_active=is_active,
                featured=featured,
                created_by=current_user.id
            )
            
            # Save to database first
            db.session.add(product)
            db.session.flush()  # Get the product ID
            
            # Handle digital product file uploads
            if product_type == 'Digital':
                digital_files = request.files.getlist('digital_files')
                digital_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'digital_products')
                os.makedirs(digital_folder, exist_ok=True)
                
                for digital_file in digital_files:
                    if digital_file and digital_file.filename:
                        # Check file size (max 100MB)
                        digital_file.seek(0, 2)
                        file_size = digital_file.tell()
                        digital_file.seek(0)
                        
                        if file_size > 100 * 1024 * 1024:  # 100MB
                            flash(f'File {digital_file.filename} is too large. Maximum size is 100MB.', 'warning')
                            continue
                        
                        # Save file with unique name
                        original_filename = secure_filename(digital_file.filename)
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                        unique_filename = f"{timestamp}{product.id}_{original_filename}"
                        
                        file_path = os.path.join(digital_folder, unique_filename)
                        digital_file.save(file_path)
                        
                        # Save file info to database
                        digital_product_file = DigitalProductFile(
                            product_id=product.id,
                            filename=unique_filename,
                            original_filename=original_filename,
                            file_type=original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else '',
                            file_size=file_size
                        )
                        db.session.add(digital_product_file)
            
            db.session.commit()
            
            flash('Product created successfully with digital files!', 'success')
            return redirect(url_for('admin_products'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating product: {str(e)}', 'danger')
            return render_template('create_product.html')
    
    return render_template('create_product.html')


@app.route('/admin/edit_product/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    """Edit an existing product"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    product = Product.query.get_or_404(product_id)
    
    if request.method == 'POST':
        try:
            # Get form data
            product.name = request.form.get('name', '').strip()
            product.description = request.form.get('description', '').strip()
            product.short_description = request.form.get('short_description', '').strip()
            price = request.form.get('price', '0')
            product.product_type = request.form.get('product_type', '').strip()
            product.category = request.form.get('category', '').strip()
            product.brand = request.form.get('brand', '').strip()
            sku = request.form.get('sku', '').strip()
            stock_quantity = request.form.get('stock_quantity', '0')
            product.image_url = request.form.get('image_url', '').strip()
            product.is_active = 'is_active' in request.form
            product.featured = 'featured' in request.form
            
            # Validate required fields
            if not all([product.name, product.description, price, product.product_type, product.category]):
                flash('Please fill in all required fields (Name, Description, Price, Type, Category).', 'danger')
                return render_template('edit_product.html', product=product)
            
            # Validate and convert price
            try:
                product.price = float(price)
                if product.price < 0:
                    flash('Price must be a positive number.', 'danger')
                    return render_template('edit_product.html', product=product)
            except ValueError:
                flash('Please enter a valid price.', 'danger')
                return render_template('edit_product.html', product=product)
            
            # Validate and convert stock quantity
            try:
                product.stock_quantity = int(stock_quantity)
                if product.stock_quantity < 0:
                    flash('Stock quantity must be a positive number.', 'danger')
                    return render_template('edit_product.html', product=product)
            except ValueError:
                flash('Please enter a valid stock quantity.', 'danger')
                return render_template('edit_product.html', product=product)
            
            # Check SKU uniqueness if changed
            if sku != product.sku:
                existing_product = Product.query.filter_by(sku=sku).filter(Product.id != product_id).first()
                if existing_product:
                    flash(f'SKU "{sku}" already exists. Please choose a different SKU.', 'danger')
                    return render_template('edit_product.html', product=product)
                product.sku = sku
            
            # For digital products, set stock to 0
            if product.product_type == 'Digital':
                product.stock_quantity = 0
            
            # Validate image URL if provided
            if product.image_url:
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(product.image_url)
                    if not all([parsed.scheme, parsed.netloc]):
                        flash('Please enter a valid image URL.', 'warning')
                        product.image_url = ''
                except:
                    flash('Please enter a valid image URL.', 'warning')
                    product.image_url = ''
            
            # Save changes
            db.session.commit()
            
            flash(f'Product "{product.name}" updated successfully!', 'success')
            return redirect(url_for('admin_products'))
                
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating product: {str(e)}', 'danger')
            print(f"Error updating product {product_id}: {e}")
            return render_template('edit_product.html', product=product)
    
    # GET request - show the form with current data
    return render_template('edit_product.html', product=product)

@app.route('/admin/delete_product/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    """Delete a product"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))

    try:
        product = Product.query.get_or_404(product_id)
        product_name = product.name
        
        # Check if there are any orders for this product
        orders_count = 0
        try:
            orders_count = ProductOrder.query.filter_by(product_id=product_id).count()
        except:
            pass  # Table might not exist or have different structure
        
        if orders_count > 0:
            flash(f'Cannot delete "{product_name}" because it has {orders_count} associated orders. Deactivate it instead.', 'warning')
            return redirect(url_for('admin_products'))
        
        # Check if there are any cart items for this product
        cart_items_count = 0
        try:
            cart_items_count = ProductCartItem.query.filter_by(product_id=product_id).count()
            if cart_items_count > 0:
                # Remove from carts first
                ProductCartItem.query.filter_by(product_id=product_id).delete()
        except:
            pass  # Table might not exist or have different structure
        
        # Delete the product
        db.session.delete(product)
        db.session.commit()
        
        flash(f'Product "{product_name}" deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting product: {str(e)}', 'danger')
        print(f"Error deleting product {product_id}: {e}")
    
    return redirect(url_for('admin_products'))



@app.route('/admin/products/bulk-action', methods=['POST'])
@login_required
def bulk_product_action():
    """Handle bulk actions on multiple products"""
    if not current_user.is_admin:
        return {'success': False, 'error': 'Access denied'}, 403
    
    try:
        data = request.get_json()
        action = data.get('action')
        product_ids = data.get('product_ids', [])
        
        if not action or not product_ids:
            return {'success': False, 'error': 'Missing action or product IDs'}, 400
        
        products = Product.query.filter(Product.id.in_(product_ids)).all()
        
        if action == 'activate':
            for product in products:
                product.is_active = True
            message = f'Activated {len(products)} products'
            
        elif action == 'deactivate':
            for product in products:
                product.is_active = False
            message = f'Deactivated {len(products)} products'
            
        elif action == 'feature':
            for product in products:
                product.featured = True
            message = f'Featured {len(products)} products'
            
        elif action == 'unfeature':
            for product in products:
                product.featured = False
            message = f'Unfeatured {len(products)} products'
            
        elif action == 'delete':
            # Check for orders first
            products_with_orders = []
            for product in products:
                try:
                    orders_count = ProductOrder.query.filter_by(product_id=product.id).count()
                    if orders_count > 0:
                        products_with_orders.append(product.name)
                except:
                    pass  # Table might not exist
            
            if products_with_orders:
                return {
                    'success': False, 
                    'error': f'Cannot delete products with orders: {", ".join(products_with_orders)}'
                }, 400
            
            # Delete products
            for product in products:
                try:
                    # Remove from carts first
                    ProductCartItem.query.filter_by(product_id=product.id).delete()
                except:
                    pass  # Table might not exist
                db.session.delete(product)
            
            message = f'Deleted {len(products)} products'
            
        else:
            return {'success': False, 'error': 'Invalid action'}, 400
        
        db.session.commit()
        return {'success': True, 'message': message}
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in bulk action: {e}")
        return {'success': False, 'error': str(e)}, 500

@app.route('/admin/products/stats')
@login_required
def product_stats():
    """Get product statistics for dashboard"""
    if not current_user.is_admin:
        return {'error': 'Access denied'}, 403
    
    try:
        total_products = Product.query.count()
        active_products = Product.query.filter_by(is_active=True).count()
        inactive_products = Product.query.filter_by(is_active=False).count()
        featured_products = Product.query.filter_by(featured=True).count()
        digital_products = Product.query.filter_by(product_type='Digital').count()
        physical_products = Product.query.filter_by(product_type='Physical').count()
        
        # Low stock products (physical products with stock < 10)
        low_stock_products = Product.query.filter(
            Product.product_type == 'Physical',
            Product.stock_quantity < 10,
            Product.stock_quantity > 0
        ).count()
        
        # Out of stock products
        out_of_stock_products = Product.query.filter(
            Product.product_type == 'Physical',
            Product.stock_quantity == 0
        ).count()
        
        # Categories
        categories = db.session.query(Product.category, db.func.count(Product.id)).group_by(Product.category).all()
        category_stats = [{'name': cat[0], 'count': cat[1]} for cat in categories if cat[0]]
        
        return {
            'total_products': total_products,
            'active_products': active_products,
            'inactive_products': inactive_products,
            'featured_products': featured_products,
            'digital_products': digital_products,
            'physical_products': physical_products,
            'low_stock_products': low_stock_products,
            'out_of_stock_products': out_of_stock_products,
            'category_stats': category_stats
        }
        
    except Exception as e:
        print(f"Error getting product stats: {e}")
        return {'error': str(e)}, 500

@app.route('/admin/products/export')
@login_required
def export_products():
    """Export products to CSV"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    try:
        import csv
        from io import StringIO
        from flask import Response
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'ID', 'Name', 'Description', 'Short Description', 'Price', 
            'Product Type', 'Category', 'Brand', 'SKU', 'Stock Quantity',
            'Image URL', 'Is Active', 'Featured', 'Created At'
        ])
        
        # Write product data
        products = Product.query.order_by(Product.created_at.desc()).all()
        for product in products:
            writer.writerow([
                product.id,
                product.name,
                product.description,
                product.short_description,
                product.price,
                product.product_type,
                product.category,
                product.brand,
                product.sku,
                product.stock_quantity,
                product.image_url,
                'Yes' if product.is_active else 'No',
                'Yes' if product.featured else 'No',
                product.created_at.strftime('%Y-%m-%d %H:%M:%S') if product.created_at else ''
            ])
        
        output.seek(0)
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=products_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            }
        )
        
    except Exception as e:
        flash(f'Error exporting products: {str(e)}', 'danger')
        return redirect(url_for('admin_products'))

@app.route('/admin/products/import', methods=['GET', 'POST'])
@login_required
def import_products():
    """Import products from CSV"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            import csv
            from io import StringIO
            
            # Check if file was uploaded
            if 'csv_file' not in request.files:
                flash('No file selected!', 'danger')
                return redirect(url_for('import_products'))
            
            file = request.files['csv_file']
            if file.filename == '':
                flash('No file selected!', 'danger')
                return redirect(url_for('import_products'))
            
            if not file.filename.endswith('.csv'):
                flash('Please upload a CSV file!', 'danger')
                return redirect(url_for('import_products'))
            
            # Read CSV content
            stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.DictReader(stream)
            
            created_count = 0
            error_count = 0
            errors = []
            
            for row_num, row in enumerate(csv_input, start=2):  # Start at 2 to account for header
                try:
                    # Validate required fields
                    if not all([row.get('Name'), row.get('Description'), row.get('Price'), 
                              row.get('Product Type'), row.get('Category')]):
                        errors.append(f"Row {row_num}: Missing required fields")
                        error_count += 1
                        continue
                    
                    # Check if product with same name or SKU exists
                    existing_product = Product.query.filter(
                        db.or_(
                            Product.name == row['Name'],
                            Product.sku == row.get('SKU')
                        )
                    ).first()
                    
                    if existing_product:
                        errors.append(f"Row {row_num}: Product '{row['Name']}' or SKU '{row.get('SKU')}' already exists")
                        error_count += 1
                        continue
                    
                    # Create product
                    product = Product(
                        name=row['Name'],
                        description=row['Description'],
                        short_description=row.get('Short Description', ''),
                        price=float(row['Price']),
                        product_type=row['Product Type'],
                        category=row['Category'],
                        brand=row.get('Brand', ''),
                        sku=row.get('SKU', ''),
                        stock_quantity=int(row.get('Stock Quantity', 0)),
                        image_url=row.get('Image URL', ''),
                        is_active=row.get('Is Active', 'Yes').lower() in ['yes', 'true', '1'],
                        featured=row.get('Featured', 'No').lower() in ['yes', 'true', '1'],
                        created_by=current_user.id
                    )
                    
                    db.session.add(product)
                    created_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    error_count += 1
                    continue
            
            db.session.commit()
            
            # Show results
            if created_count > 0:
                flash(f'Successfully imported {created_count} products!', 'success')
            
            if error_count > 0:
                flash(f'{error_count} errors occurred during import. Check the error details below.', 'warning')
                for error in errors[:10]:  # Show first 10 errors
                    flash(error, 'danger')
                if len(errors) > 10:
                    flash(f'... and {len(errors) - 10} more errors', 'danger')
            
            return redirect(url_for('admin_products'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error importing products: {str(e)}', 'danger')
            return redirect(url_for('import_products'))
    
    # GET request - show import form
    return render_template('import_products.html')

#//////////////////////////////////////////////////////////////////
# Add this route to your app.py file

@app.route('/my_digital_products')
@login_required
def my_digital_products():
    """Show user's purchased digital products"""
    # Get completed orders for digital products
    digital_orders = ProductOrder.query.filter_by(
        user_id=current_user.id,
        status='completed'
    ).join(Product).filter(
        Product.product_type == 'Digital'
    ).order_by(ProductOrder.ordered_at.desc()).all()
    
    return render_template('my_digital_products.html', orders=digital_orders)


# Add this route to your app.py file

@app.route('/view_digital_product/<int:order_id>')
@login_required
def view_digital_product(order_id):
    """View a specific digital product"""
    # Verify user owns this digital product
    order = ProductOrder.query.filter_by(
        id=order_id,
        user_id=current_user.id,
        status='completed'
    ).join(Product).filter(
        Product.product_type == 'Digital'
    ).first_or_404()
    
    return render_template('view_digital_product.html', order=order)

# Add this route to serve digital product files
@app.route('/download_digital_product/<int:file_id>')
@login_required
def download_digital_product(file_id):
    """Download digital product file (only for purchased products)"""
    digital_file = DigitalProductFile.query.get_or_404(file_id)
    
    # Check if user has purchased this product (unless admin)
    if not current_user.is_admin:
        purchase = ProductOrder.query.filter_by(
            user_id=current_user.id,
            product_id=digital_file.product_id,
            status='completed'
        ).first()
        
        if not purchase:
            flash('You need to purchase this product to download the files.', 'warning')
            return redirect(url_for('product_detail', product_id=digital_file.product_id))
    
    # Increment download count
    digital_file.download_count += 1
    db.session.commit()
    
    # Serve the file
    digital_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'digital_products')
    return send_from_directory(
        digital_folder, 
        digital_file.filename,
        as_attachment=True,
        download_name=digital_file.original_filename
    )

@app.route('/admin/migrate-digital-files')
@login_required
def migrate_digital_files():
    """Create the digital product files table - ADMIN ONLY"""
    if not current_user.is_admin:
        return "Access denied", 403
    
    try:
        # Create the digital_product_file table
        db.create_all()
        
        # Create upload directory if it doesn't exist
        digital_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'digital_products')
        os.makedirs(digital_folder, exist_ok=True)
        
        return "✅ Digital files table created successfully! Upload folder ready."
        
    except Exception as e:
        return f"❌ Migration failed: {str(e)}"
        



# ========================================
# ORDER MANAGEMENT ROUTES
# ========================================

@app.route('/admin/product_orders')
@login_required
def admin_product_orders():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))

    orders = ProductOrder.query.order_by(ProductOrder.ordered_at.desc()).all()
    total_revenue = db.session.query(db.func.sum(ProductOrder.total_amount)).filter_by(status='completed').scalar() or 0

    return render_template('admin_product_orders.html', 
                         orders=orders, 
                         total_revenue=total_revenue)

@app.route('/admin/course_orders')
@login_required
def admin_course_orders():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))

    orders = Purchase.query.order_by(Purchase.purchased_at.desc()).all()
    total_revenue = db.session.query(db.func.sum(Purchase.amount)).filter_by(status='completed').scalar() or 0
    pending_orders = Purchase.query.filter_by(status='pending').count()

    return render_template('admin_course_orders.html', 
                         orders=orders, 
                         total_revenue=total_revenue,
                         pending_orders=pending_orders)

@app.route('/admin/view_order/<int:order_id>')
@login_required
def view_order(order_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    order = ProductOrder.query.get_or_404(order_id)
    return render_template('view_order.html', order=order)

@app.route('/admin/view_course_order/<int:order_id>')
@login_required
def view_course_order(order_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    order = Purchase.query.get_or_404(order_id)
    return render_template('view_course_order.html', order=order)

@app.route('/admin/update_order_status/<int:order_id>', methods=['POST'])
@login_required
def update_order_status(order_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    order = ProductOrder.query.get_or_404(order_id)
    new_status = request.form.get('status')
    
    if new_status in ['pending', 'completed', 'shipped', 'delivered', 'cancelled']:
        order.status = new_status
        if new_status == 'shipped':
            order.shipped_at = datetime.utcnow()
            order.tracking_number = request.form.get('tracking_number', '')
        elif new_status == 'delivered':
            order.delivered_at = datetime.utcnow()
        
        db.session.commit()
        flash(f'Order status updated to {new_status}!', 'success')
    else:
        flash('Invalid status!', 'danger')
    
    return redirect(url_for('view_order', order_id=order_id))

@app.route('/admin/update_course_order_status/<int:order_id>', methods=['POST'])
@login_required
def update_course_order_status(order_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    order = Purchase.query.get_or_404(order_id)
    new_status = request.form.get('status')
    
    if new_status in ['pending', 'completed', 'failed', 'refunded']:
        old_status = order.status
        order.status = new_status
        db.session.commit()
        
        if old_status != new_status:
            if new_status == 'completed':
                flash(f'Order #{order.id} approved! Customer now has access to the course.', 'success')
            elif new_status == 'failed':
                flash(f'Order #{order.id} marked as failed.', 'warning')
            elif new_status == 'refunded':
                flash(f'Order #{order.id} refunded.', 'info')
            else:
                flash(f'Order #{order.id} status updated to {new_status}.', 'success')
    else:
        flash('Invalid status!', 'danger')
    
    return redirect(url_for('view_course_order', order_id=order_id))

# ========================================
# STUDENT DASHBOARD ROUTES
# ========================================

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    # Get student's enrolled classes
    individual_classes = current_user.individual_classes
    group_classes = current_user.group_classes
    
    # Build list of class_ids that should show materials for this student
    relevant_class_ids = []
    
    # Add individual class materials (format: "individual_X")
    for iclass in individual_classes:
        relevant_class_ids.append(f'individual_{iclass.id}')
    
    # Add group class materials (format: "group_X")  
    for gclass in group_classes:
        relevant_class_ids.append(f'group_{gclass.id}')
    
    # Add individual student materials (format: "student_X")
    relevant_class_ids.append(f'student_{current_user.id}')
    
    # Get materials for all relevant classes/student
    materials = LearningMaterial.query.filter(
        LearningMaterial.class_id.in_(relevant_class_ids)
    ).order_by(LearningMaterial.created_at.desc()).all()
    
    print(f"🔍 Debug Student Dashboard:")
    print(f"   Student ID: {current_user.id}")
    print(f"   Individual Classes: {[f'individual_{c.id}' for c in individual_classes]}")
    print(f"   Group Classes: {[f'group_{c.id}' for c in group_classes]}")
    print(f"   Relevant Class IDs: {relevant_class_ids}")
    print(f"   Materials Found: {len(materials)}")
    for material in materials:
        print(f"     - {material.class_id}: {material.content[:50]}...")
    
    return render_template(
        'student_dashboard.html',
        materials=materials,
        individual_classes=individual_classes,
        group_classes=group_classes
    )



@app.route('/debug/materials')
@login_required
def debug_materials():
    """Debug route to see what materials exist and student enrollments"""
    
    # Get all materials
    all_materials = LearningMaterial.query.all()
    
    # Get current user's classes
    individual_classes = current_user.individual_classes
    group_classes = current_user.group_classes
    
    debug_info = {
        'current_user_id': current_user.id,
        'current_user_name': f"{current_user.first_name} {current_user.last_name}",
        'is_admin': current_user.is_admin,
        'individual_classes': [
            {
                'id': c.id, 
                'name': c.name, 
                'expected_class_id': f'individual_{c.id}'
            } for c in individual_classes
        ],
        'group_classes': [
            {
                'id': c.id, 
                'name': c.name, 
                'expected_class_id': f'group_{c.id}'
            } for c in group_classes
        ],
        'all_materials': [
            {
                'id': m.id,
                'class_id': m.class_id,
                'class_type': m.class_type,
                'actual_class_id': m.actual_class_id,
                'content_preview': m.content[:100] + '...' if len(m.content) > 100 else m.content,
                'created_at': m.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'class_name': m.class_name
            } for m in all_materials
        ]
    }
    
    # Build expected class IDs for this student
    expected_class_ids = []
    expected_class_ids.extend([f'individual_{c.id}' for c in individual_classes])
    expected_class_ids.extend([f'group_{c.id}' for c in group_classes])
    expected_class_ids.append(f'student_{current_user.id}')
    
    debug_info['expected_class_ids'] = expected_class_ids
    
    # Check which materials should be visible
    visible_materials = [
        m for m in all_materials 
        if m.class_id in expected_class_ids
    ]
    
    debug_info['visible_materials_count'] = len(visible_materials)
    debug_info['visible_materials'] = [
        {
            'id': m.id,
            'class_id': m.class_id,
            'content_preview': m.content[:50] + '...',
            'class_name': m.class_name
        } for m in visible_materials
    ]
    
    # Return as HTML for easy viewing
    html = f"""
    <html>
    <head><title>Materials Debug</title>
    <style>body {{ font-family: Arial; padding: 20px; }}</style></head>
    <body>
        <h1>🔍 Materials Debug Information</h1>
        
        <h2>👤 Current User</h2>
        <p><strong>ID:</strong> {debug_info['current_user_id']}</p>
        <p><strong>Name:</strong> {debug_info['current_user_name']}</p>
        <p><strong>Is Admin:</strong> {debug_info['is_admin']}</p>
        
        <h2>📚 Individual Classes Enrolled</h2>
        <ul>
    """
    
    for iclass in debug_info['individual_classes']:
        html += f"<li><strong>{iclass['name']}</strong> (ID: {iclass['id']}, Expected class_id: {iclass['expected_class_id']})</li>"
    
    html += "</ul><h2>👥 Group Classes Enrolled</h2><ul>"
    
    for gclass in debug_info['group_classes']:
        html += f"<li><strong>{gclass['name']}</strong> (ID: {gclass['id']}, Expected class_id: {gclass['expected_class_id']})</li>"
    
    html += f"""
        </ul>
        
        <h2>🎯 Expected Class IDs for This Student</h2>
        <ul>
    """
    
    for class_id in debug_info['expected_class_ids']:
        html += f"<li><code>{class_id}</code></li>"
    
    html += f"""
        </ul>
        
        <h2>📋 All Materials in Database ({len(debug_info['all_materials'])})</h2>
        <table border="1" style="border-collapse: collapse; width: 100%;">
            <tr>
                <th>ID</th>
                <th>Class ID</th>
                <th>Class Type</th>
                <th>Class Name</th>
                <th>Content Preview</th>
                <th>Created</th>
                <th>Visible to Student?</th>
            </tr>
    """
    
    for material in debug_info['all_materials']:
        is_visible = material['class_id'] in debug_info['expected_class_ids']
        visibility_color = "green" if is_visible else "red"
        visibility_text = "✅ YES" if is_visible else "❌ NO"
        
        html += f"""
            <tr>
                <td>{material['id']}</td>
                <td><code>{material['class_id']}</code></td>
                <td>{material['class_type']}</td>
                <td>{material['class_name']}</td>
                <td>{material['content_preview']}</td>
                <td>{material['created_at']}</td>
                <td style="color: {visibility_color}; font-weight: bold;">{visibility_text}</td>
            </tr>
        """
    
    html += f"""
        </table>
        
        <h2>✅ Materials Visible to This Student ({debug_info['visible_materials_count']})</h2>
        <ul>
    """
    
    for material in debug_info['visible_materials']:
        html += f"<li><strong>{material['class_name']}</strong>: {material['content_preview']} (class_id: <code>{material['class_id']}</code>)</li>"
    
    html += f"""
        </ul>
        
        <h3>🔄 Actions</h3>
        <p><a href="/student/dashboard">← Back to Student Dashboard</a></p>
        <p><a href="/admin/dashboard">← Back to Admin Dashboard</a></p>
    </body>
    </html>
    """
    
    return html

# ========================================
# AI ASSISTANT ROUTES
# ========================================

@app.route('/ai_assistant', methods=['GET', 'POST'])
@login_required
def ai_assistant():
    if request.method == 'POST':
        question = request.form.get('question')
        if not question:
            flash('Please enter a question', 'danger')
            return redirect(url_for('ai_assistant'))
        
        try:
            headers = {
                "Authorization": f"Bearer {app.config['DEEPINFRA_API_KEY']}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "meta-llama/Meta-Llama-3-70B-Instruct",
                "messages": [{"role": "user", "content": f"You are an expert tutor helping a student. Answer this question in detail but in simple terms: {question}"}],
                "temperature": 0.7
            }
            
            response = requests.post(app.config['DEEPINFRA_API_URL'], headers=headers, data=json.dumps(data))
            response.raise_for_status()
            
            answer = response.json()['choices'][0]['message']['content']
            return render_template('ai_assistant.html', answer=answer, question=question)
            
        except Exception as e:
            flash(f'Error getting AI response: {str(e)}', 'danger')
            return redirect(url_for('ai_assistant'))
    
    return render_template('ai_assistant.html')

# ========================================
# STORE ROUTES
# ========================================

@app.route('/store')
def store():
    category = request.args.get('category', '')
    level = request.args.get('level', '')
    search = request.args.get('search', '')
    
    query = Course.query.filter_by(is_active=True)
    
    if category:
        query = query.filter_by(category=category)
    if level:
        query = query.filter_by(level=level)
    if search:
        query = query.filter(Course.title.contains(search) | Course.description.contains(search))
    
    courses = query.order_by(Course.created_at.desc()).all()
    categories = db.session.query(Course.category).distinct().all()
    categories = [cat[0] for cat in categories]
    
    cart_count = 0
    if current_user.is_authenticated:
        cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
    
    return render_template('store.html', 
                         courses=courses, 
                         categories=categories,
                         cart_count=cart_count,
                         selected_category=category,
                         selected_level=level,
                         search_term=search)

@app.route('/course/<int:course_id>')
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    is_purchased = False
    in_cart = False
    
    if current_user.is_authenticated:
        is_purchased = Purchase.query.filter_by(
            user_id=current_user.id, 
            course_id=course_id, 
            status='completed'
        ).first() is not None
        
        in_cart = CartItem.query.filter_by(
            user_id=current_user.id, 
            course_id=course_id
        ).first() is not None
    
    return render_template('course_detail.html', 
                         course=course, 
                         is_purchased=is_purchased,
                         in_cart=in_cart)

@app.route('/add_to_cart/<int:course_id>', methods=['POST'])
@login_required
def add_to_cart(course_id):
    course = Course.query.get_or_404(course_id)
    
    existing_purchase = Purchase.query.filter_by(
        user_id=current_user.id, 
        course_id=course_id, 
        status='completed'
    ).first()
    
    if existing_purchase:
        flash('You have already purchased this course!', 'info')
        return redirect(url_for('course_detail', course_id=course_id))
    
    existing_cart_item = CartItem.query.filter_by(
        user_id=current_user.id, 
        course_id=course_id
    ).first()
    
    if existing_cart_item:
        flash('Course is already in your cart!', 'info')
        return redirect(url_for('course_detail', course_id=course_id))
    
    cart_item = CartItem(user_id=current_user.id, course_id=course_id)
    db.session.add(cart_item)
    db.session.commit()
    
    flash('Course added to cart!', 'success')
    return redirect(url_for('course_detail', course_id=course_id))

@app.route('/cart')
@login_required
def cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.course.price for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/remove_from_cart/<int:cart_item_id>', methods=['POST'])
@login_required
def remove_from_cart(cart_item_id):
    cart_item = CartItem.query.get_or_404(cart_item_id)
    
    if cart_item.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('cart'))
    
    db.session.delete(cart_item)
    db.session.commit()
    
    flash('Course removed from cart!', 'success')
    return redirect(url_for('cart'))

@app.route('/checkout')
@login_required
def checkout():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    
    if not cart_items:
        flash('Your cart is empty!', 'warning')
        return redirect(url_for('store'))
    
    total = sum(item.course.price for item in cart_items)
    return render_template('checkout.html', cart_items=cart_items, total=total)

@app.route('/my_courses')
@login_required
def my_courses():
    purchases = Purchase.query.filter_by(
        user_id=current_user.id, 
        status='completed'
    ).order_by(Purchase.purchased_at.desc()).all()
    
    return render_template('my_courses.html', purchases=purchases)

@app.route('/my_course_orders')
@login_required
def my_course_orders():
    orders = Purchase.query.filter_by(
        user_id=current_user.id
    ).order_by(Purchase.purchased_at.desc()).all()
    
    return render_template('my_course_orders.html', orders=orders)

# ========================================
# ENHANCED LEARN COURSE ROUTE - ADD THIS TO YOUR app.py
# ========================================
# Replace your existing learn_course route with this enhanced version

@app.route('/learn/course/<int:course_id>')
@login_required
def learn_course(course_id):
    # Enhanced learn course route with proper data preparation
    course = Course.query.get_or_404(course_id)
    
    print(f"🎓 Learn course accessed: {course.title} (ID: {course_id})")
    print(f"👤 User: {current_user.username} (Admin: {current_user.is_admin})")
    
    # Check if user has access to this course
    has_access = False
    access_reason = ""
    
    if current_user.is_admin:
        has_access = True
        access_reason = "Admin access"
        print("✅ Access granted: Admin user")
    else:
        # Check if user has purchased this course
        purchase = Purchase.query.filter_by(
            user_id=current_user.id,
            course_id=course_id,
            status='completed'
        ).first()
        
        if purchase:
            has_access = True
            access_reason = f"Purchased on {purchase.purchased_at.strftime('%Y-%m-%d')}"
            print(f"✅ Access granted: Course purchased on {purchase.purchased_at}")
        else:
            # Check for pending purchases
            pending_purchase = Purchase.query.filter_by(
                user_id=current_user.id,
                course_id=course_id,
                status='pending'
            ).first()
            
            if pending_purchase:
                print(f"⏳ Pending purchase found, created on {pending_purchase.purchased_at}")
                flash('Your payment is being verified. You will have access once confirmed.', 'info')
            else:
                print("❌ No purchase found for this course")
            
            flash('You need to purchase this course to access the learning content.', 'warning')
            return redirect(url_for('course_detail', course_id=course_id))
    
    # Get course videos (ordered by order_index)
    videos = CourseVideo.query.filter_by(course_id=course_id).order_by(CourseVideo.order_index).all()
    print(f"📹 Found {len(videos)} videos for course")
    
    # Get course materials
    materials = CourseMaterial.query.filter_by(course_id=course_id).all()
    print(f"📁 Found {len(materials)} materials for course")
    
    # Prepare enhanced video data with proper playback URLs and availability
    enhanced_videos = []
    debug_info = {
        'total_videos': len(videos),
        'cloudinary_videos': 0,
        'local_videos': 0,
        'missing_videos': 0,
        'videos_with_missing_files': 0
    }
    
    video_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
    
    for i, video in enumerate(videos):
        # Determine video source and availability
        playback_url = None
        source_type = 'unknown'
        available = False
        file_exists = False
        
        if video.video_url:
            # Cloudinary video
            playback_url = video.video_url
            source_type = 'cloudinary'
            available = True
            debug_info['cloudinary_videos'] += 1
            print(f"  Video {i+1}: {video.title} (Cloudinary) - ✅ Available")
            print(f"    Cloudinary URL: {video.video_url}")
        elif video.video_filename:
            # Local video - check if file exists
            video_path = os.path.join(video_folder, video.video_filename)
            file_exists = os.path.exists(video_path)
            
            if file_exists:
                playback_url = url_for('course_video', filename=video.video_filename)
                source_type = 'local'
                available = True
                debug_info['local_videos'] += 1
                print(f"  Video {i+1}: {video.title} (Local) - ✅ Available")
                print(f"    Local file: {video.video_filename}")
            else:
                source_type = 'local'
                available = False
                debug_info['local_videos'] += 1
                debug_info['videos_with_missing_files'] += 1
                print(f"  Video {i+1}: {video.title} (Local) - ❌ File missing")
                print(f"    Missing file: {video.video_filename}")
        else:
            # No video source at all
            source_type = 'none'
            available = False
            debug_info['missing_videos'] += 1
            print(f"  Video {i+1}: {video.title} - ❌ No source")
        
        # Create enhanced video object
        enhanced_video = {
            'id': video.id,
            'title': video.title,
            'description': video.description or '',
            'duration': video.duration or '',
            'order_index': video.order_index,
            'video_filename': video.video_filename or '',
            'video_url': video.video_url or '',
            'playback_url': playback_url,
            'source_type': source_type,
            'available': available,
            'file_exists': file_exists,
            'is_preview': getattr(video, 'is_preview', False),
            'course_id': video.course_id
        }
        enhanced_videos.append(enhanced_video)
    
    # Convert materials to enhanced format
    enhanced_materials = []
    for material in materials:
        print(f"  Material: {material.title} ({material.file_type})")
        material_data = {
            'id': material.id,
            'title': material.title,
            'filename': material.filename,
            'file_type': material.file_type,
            'file_size_mb': material.get_file_size_mb(),
            'course_id': material.course_id
        }
        enhanced_materials.append(material_data)
    
    # Add debug route if not exists
    try:
        url_for('debug_course_videos', course_id=course_id)
        debug_route_exists = True
    except:
        debug_route_exists = False
    
    # Prepare context for template
    context = {
        'course': course,
        'videos': enhanced_videos,  # Use enhanced videos with all needed properties
        'materials': materials,  # Keep original for template compatibility
        'enhanced_materials': enhanced_materials,  # Enhanced materials for JavaScript
        'has_access': has_access,
        'access_reason': access_reason,
        'debug_info': debug_info if current_user.is_admin else None,
        'debug_route_exists': debug_route_exists
    }
    
    print(f"🎯 Rendering template with {len(enhanced_videos)} enhanced videos and {len(materials)} materials")
    print(f"📊 Debug info: {debug_info}")
    
    return render_template('learn_course.html', **context)

#////////////////////////////////////////////////////////

@app.route('/admin/fix-course-images')
@login_required
def fix_course_images():
    """Simple fix for course images"""
    if not current_user.is_admin:
        return "Admin only", 403
    
    # Get all courses without images
    courses = Course.query.all()
    fixed = 0
    
    for course in courses:
        # If no image or empty image, add a simple one
        if not course.image_url or course.image_url.strip() == '':
            course.image_url = 'https://via.placeholder.com/400x200/007bff/ffffff?text=' + course.category.replace(' ', '+')
            fixed += 1
    
    db.session.commit()
    
    return f"Fixed {fixed} course images! <a href='/store'>Check Store</a>"



# ========================================
# NEW COURSE STATUS TOGGLE ROUTES - ADD THESE TO YOUR app.py
# ========================================
# Add these routes in the COURSE MANAGEMENT ROUTES section

@app.route('/admin/toggle-course-status/<int:course_id>', methods=['POST'])
@login_required
def toggle_course_status(course_id):
    """Toggle course active/inactive status via AJAX"""
    if not current_user.is_admin:
        return {'success': False, 'error': 'Access denied. Admin privileges required.'}, 403
    
    try:
        # Get the course
        course = Course.query.get_or_404(course_id)
        
        # Get the new status from request
        data = request.get_json()
        new_status = data.get('is_active', False)
        
        # Validate the status value
        if not isinstance(new_status, bool):
            return {'success': False, 'error': 'Invalid status value. Must be true or false.'}, 400
        
        # Update the course status
        old_status = course.is_active
        course.is_active = new_status
        
        # Commit the change
        db.session.commit()
        
        # Log the change
        action = "activated" if new_status else "deactivated"
        print(f"✅ Course '{course.title}' (ID: {course_id}) {action} by admin {current_user.username}")
        
        # Return success response
        response_data = {
            'success': True,
            'message': f'Course "{course.title}" {action} successfully!',
            'course_id': course_id,
            'new_status': new_status,
            'old_status': old_status
        }
        
        return response_data, 200
        
    except Exception as e:
        # Rollback in case of error
        db.session.rollback()
        
        error_message = str(e)
        print(f"❌ Error toggling course status for course {course_id}: {error_message}")
        
        return {
            'success': False, 
            'error': f'Failed to update course status: {error_message}'
        }, 500


@app.route('/admin/bulk-toggle-courses', methods=['POST'])
@login_required
def bulk_toggle_courses():
    """Bulk toggle multiple courses status"""
    if not current_user.is_admin:
        return {'success': False, 'error': 'Access denied. Admin privileges required.'}, 403
    
    try:
        # Get request data
        data = request.get_json()
        course_ids = data.get('course_ids', [])
        new_status = data.get('is_active', False)
        
        # Validate input
        if not course_ids:
            return {'success': False, 'error': 'No course IDs provided.'}, 400
        
        if not isinstance(new_status, bool):
            return {'success': False, 'error': 'Invalid status value. Must be true or false.'}, 400
        
        # Update courses
        updated_courses = []
        failed_courses = []
        
        for course_id in course_ids:
            try:
                course = Course.query.get(course_id)
                if course:
                    course.is_active = new_status
                    updated_courses.append({
                        'id': course.id,
                        'title': course.title,
                        'new_status': new_status
                    })
                else:
                    failed_courses.append({'id': course_id, 'error': 'Course not found'})
            except Exception as e:
                failed_courses.append({'id': course_id, 'error': str(e)})
        
        # Commit all changes
        if updated_courses:
            db.session.commit()
        
        action = "activated" if new_status else "deactivated"
        success_count = len(updated_courses)
        
        print(f"✅ Bulk operation: {success_count} courses {action} by admin {current_user.username}")
        
        response_data = {
            'success': True,
            'message': f'{success_count} course(s) {action} successfully!',
            'updated_count': success_count,
            'failed_count': len(failed_courses),
            'updated_courses': updated_courses,
            'failed_courses': failed_courses if failed_courses else None
        }
        
        return response_data, 200
        
    except Exception as e:
        # Rollback in case of error
        db.session.rollback()
        
        error_message = str(e)
        print(f"❌ Error in bulk course toggle: {error_message}")
        
        return {
            'success': False, 
            'error': f'Bulk operation failed: {error_message}'
        }, 500


@app.route('/admin/course-status-stats')
@login_required
def course_status_stats():
    """Get course status statistics"""
    if not current_user.is_admin:
        return {'error': 'Access denied'}, 403
    
    try:
        total_courses = Course.query.count()
        active_courses = Course.query.filter_by(is_active=True).count()
        inactive_courses = Course.query.filter_by(is_active=False).count()
        
        # Get courses by category status
        category_stats = db.session.query(
            Course.category,
            db.func.count(Course.id).label('total'),
            db.func.sum(db.case([(Course.is_active == True, 1)], else_=0)).label('active'),
            db.func.sum(db.case([(Course.is_active == False, 1)], else_=0)).label('inactive')
        ).group_by(Course.category).all()
        
        category_data = []
        for stat in category_stats:
            category_data.append({
                'category': stat.category,
                'total': stat.total,
                'active': stat.active,
                'inactive': stat.inactive
            })
        
        return {
            'total_courses': total_courses,
            'active_courses': active_courses,
            'inactive_courses': inactive_courses,
            'active_percentage': round((active_courses / total_courses) * 100, 1) if total_courses > 0 else 0,
            'category_breakdown': category_data
        }
        
    except Exception as e:
        return {'error': str(e)}, 500


# ========================================
# PRODUCT STORE ROUTES
# ========================================

@app.route('/products')
def products():
    category = request.args.get('category', '')
    product_type = request.args.get('type', '')
    search = request.args.get('search', '')
    sort_by = request.args.get('sort', 'newest')
    
    query = Product.query.filter_by(is_active=True)
    
    if category:
        query = query.filter_by(category=category)
    if product_type:
        query = query.filter_by(product_type=product_type)
    if search:
        query = query.filter(Product.name.contains(search) | Product.description.contains(search))
    
    if sort_by == 'price_low':
        query = query.order_by(Product.price.asc())
    elif sort_by == 'price_high':
        query = query.order_by(Product.price.desc())
    elif sort_by == 'name':
        query = query.order_by(Product.name.asc())
    else:
        query = query.order_by(Product.created_at.desc())
    
    products = query.all()
    categories = db.session.query(Product.category).distinct().all()
    categories = [cat[0] for cat in categories]
    
    product_cart_count = 0
    if current_user.is_authenticated:
        product_cart_count = ProductCartItem.query.filter_by(user_id=current_user.id).count()
    
    return render_template('products.html', 
                         products=products, 
                         categories=categories,
                         product_cart_count=product_cart_count,
                         selected_category=category,
                         selected_type=product_type,
                         search_term=search,
                         sort_by=sort_by)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    in_cart = False
    cart_quantity = 0
    
    if current_user.is_authenticated:
        cart_item = ProductCartItem.query.filter_by(
            user_id=current_user.id, 
            product_id=product_id
        ).first()
        if cart_item:
            in_cart = True
            cart_quantity = cart_item.quantity
    
    return render_template('product_detail.html', 
                         product=product, 
                         in_cart=in_cart,
                         cart_quantity=cart_quantity)

@app.route('/add_product_to_cart/<int:product_id>', methods=['POST'])
@login_required
def add_product_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    quantity = int(request.form.get('quantity', 1))
    
    if not product.is_in_stock():
        flash('Product is out of stock!', 'warning')
        return redirect(url_for('product_detail', product_id=product_id))
    
    if product.product_type == 'Physical' and quantity > product.stock_quantity:
        flash(f'Only {product.stock_quantity} items available in stock!', 'warning')
        return redirect(url_for('product_detail', product_id=product_id))
    
    existing_cart_item = ProductCartItem.query.filter_by(
        user_id=current_user.id, 
        product_id=product_id
    ).first()
    
    if existing_cart_item:
        existing_cart_item.quantity += quantity
        if product.product_type == 'Physical' and existing_cart_item.quantity > product.stock_quantity:
            existing_cart_item.quantity = product.stock_quantity
            flash(f'Updated quantity to maximum available ({product.stock_quantity})', 'info')
        else:
            flash('Product quantity updated in cart!', 'success')
    else:
        cart_item = ProductCartItem(
            user_id=current_user.id, 
            product_id=product_id,
            quantity=quantity
        )
        db.session.add(cart_item)
        flash('Product added to cart!', 'success')
    
    db.session.commit()
    return redirect(url_for('product_detail', product_id=product_id))

@app.route('/product_cart')
@login_required
def product_cart():
    cart_items = ProductCartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.get_total_price() for item in cart_items)
    return render_template('product_cart.html', cart_items=cart_items, total=total)

@app.route('/update_product_cart/<int:cart_item_id>', methods=['POST'])
@login_required
def update_product_cart(cart_item_id):
    cart_item = ProductCartItem.query.get_or_404(cart_item_id)
    
    if cart_item.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('product_cart'))
    
    new_quantity = int(request.form.get('quantity', 1))
    
    if new_quantity <= 0:
        db.session.delete(cart_item)
        flash('Product removed from cart!', 'success')
    else:
        if cart_item.product.product_type == 'Physical' and new_quantity > cart_item.product.stock_quantity:
            new_quantity = cart_item.product.stock_quantity
            flash(f'Quantity adjusted to maximum available ({cart_item.product.stock_quantity})', 'warning')
        
        cart_item.quantity = new_quantity
        flash('Cart updated!', 'success')
    
    db.session.commit()
    return redirect(url_for('product_cart'))

@app.route('/remove_product_from_cart/<int:cart_item_id>', methods=['POST'])
@login_required
def remove_product_from_cart(cart_item_id):
    cart_item = ProductCartItem.query.get_or_404(cart_item_id)
    
    if cart_item.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('product_cart'))
    
    db.session.delete(cart_item)
    db.session.commit()
    
    flash('Product removed from cart!', 'success')
    return redirect(url_for('product_cart'))

@app.route('/product_checkout')
@login_required
def product_checkout():
    cart_items = ProductCartItem.query.filter_by(user_id=current_user.id).all()
    
    if not cart_items:
        flash('Your cart is empty!', 'warning')
        return redirect(url_for('products'))
    
    total = sum(item.get_total_price() for item in cart_items)
    return render_template('product_checkout.html', cart_items=cart_items, total=total)

@app.route('/my_orders')
@login_required
def my_orders():
    orders = ProductOrder.query.filter_by(
        user_id=current_user.id
    ).order_by(ProductOrder.ordered_at.desc()).all()
    
    return render_template('my_orders.html', orders=orders)

# ========================================
# PAYMENT ROUTES
# ========================================

@app.route('/process_payment', methods=['POST'])
@login_required
def process_payment():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    
    if not cart_items:
        flash('Your cart is empty!', 'warning')
        return redirect(url_for('store'))
    
    # Get form data
    payment_method = request.form.get('payment_method')
    full_name = request.form.get('full_name')
    phone = request.form.get('phone')
    email = request.form.get('email')
    address = request.form.get('address')
    
    # Validate payment method
    valid_methods = ['bank_transfer', 'wave', 'western_union', 'moneygram', 'ria']
    if payment_method not in valid_methods:
        flash('Please select a valid payment method', 'danger')
        return redirect(url_for('checkout'))
    
    # Handle payment proof upload
    payment_proof = request.files.get('payment_proof')
    proof_url, error = handle_payment_proof_upload(
        payment_proof, 'course_purchase', 'batch', current_user.id
    )
    
    if error:
        flash(error, 'danger')
        return redirect(url_for('checkout'))
    
    transaction_id = str(uuid.uuid4())[:8]
    
    # Create purchases
    for cart_item in cart_items:
        purchase = Purchase(
            user_id=current_user.id,
            course_id=cart_item.course_id,
            amount=cart_item.course.price,
            status='pending',
            payment_method=payment_method,
            transaction_id=f"{transaction_id}-{cart_item.id}",
            customer_name=full_name,
            customer_phone=phone,
            customer_email=email,
            customer_address=address,
            payment_proof=proof_url
        )
        db.session.add(purchase)
        db.session.delete(cart_item)
    
    db.session.commit()
    flash('Order submitted successfully!', 'success')
    return redirect(url_for('my_course_orders'))

@app.route('/process_product_payment', methods=['POST'])
@login_required
def process_product_payment():
    cart_items = ProductCartItem.query.filter_by(user_id=current_user.id).all()
    
    if not cart_items:
        flash('Your cart is empty!', 'warning')
        return redirect(url_for('products'))

    # Get form data
    payment_method = request.form.get('payment_method')
    full_name = request.form.get('full_name')
    phone = request.form.get('phone')
    email = request.form.get('email')
    address = request.form.get('address')
    
    # Validate payment method
    valid_methods = ['bank_transfer', 'wave', 'western_union', 'moneygram', 'ria']
    if payment_method not in valid_methods:
        flash('Please select a valid payment method', 'danger')
        return redirect(url_for('product_checkout'))
    
    # Handle payment proof upload
    payment_proof = request.files.get('payment_proof')
    proof_url, error = handle_payment_proof_upload(
        payment_proof, 'product_purchase', 'batch', current_user.id
    )
    
    if error:
        flash(error, 'danger')
        return redirect(url_for('product_checkout'))

    transaction_id = str(uuid.uuid4())[:8]
    
    # Create orders
    for cart_item in cart_items:
        if cart_item.product.product_type == 'Physical':
            if cart_item.quantity > cart_item.product.stock_quantity:
                flash(f'Insufficient stock for {cart_item.product.name}', 'danger')
                return redirect(url_for('product_cart'))
            cart_item.product.stock_quantity -= cart_item.quantity
        
        order = ProductOrder(
            user_id=current_user.id,
            product_id=cart_item.product_id,
            quantity=cart_item.quantity,
            unit_price=cart_item.product.price,
            total_amount=cart_item.get_total_price(),
            status='pending',
            payment_method=payment_method,
            transaction_id=f"{transaction_id}-{cart_item.id}",
            shipping_address=address if cart_item.product.product_type == 'Physical' else None,
            customer_name=full_name,
            customer_phone=phone,
            customer_email=email,
            customer_address=address,
            payment_proof=proof_url
        )
        db.session.add(order)
        db.session.delete(cart_item)
    
    db.session.commit()
    flash('Order placed successfully!', 'success')
    return redirect(url_for('my_orders'))


def upload_payment_proof_to_cloudinary(file, order_type, order_id, user_id):
    """Upload payment proof to Cloudinary permanently"""
    try:
        file.seek(0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        public_id = f"payment_proof_{order_type}_{order_id}_{user_id}_{timestamp}"
        
        result = cloudinary.uploader.upload(
            file,
            resource_type="image",
            public_id=public_id,
            folder="payment_proofs",
            overwrite=True,
            format="jpg",
            quality="auto",
            transformation=[{"width": 800, "height": 600, "crop": "limit"}]
        )
        
        print(f"✅ Payment proof uploaded: {result['secure_url']}")
        return result['secure_url']
        
    except Exception as e:
        print(f"❌ Cloudinary upload error: {e}")
        return None

def handle_payment_proof_upload(payment_proof_file, order_type, order_id, user_id):
    """Handle payment proof upload with validation - REUSABLE FUNCTION"""
    if not payment_proof_file or not payment_proof_file.filename:
        return None, "Payment proof is required!"
    
    if not allowed_file(payment_proof_file.filename):
        return None, "Invalid file type. Please upload an image file."
    
    # Check file size (5MB limit)
    payment_proof_file.seek(0, 2)
    file_size = payment_proof_file.tell()
    payment_proof_file.seek(0)
    
    if file_size > 5 * 1024 * 1024:
        return None, "File too large. Maximum size is 5MB."
    
    # Upload to Cloudinary
    cloudinary_url = upload_payment_proof_to_cloudinary(
        payment_proof_file, order_type, order_id, user_id
    )
    
    if not cloudinary_url:
        return None, "Failed to upload payment proof. Please try again."
    
    return cloudinary_url, None

# Simple migration route
@app.route('/admin/migrate-payment-proofs')
@login_required
def migrate_payment_proofs():
    """Simple migration of existing payment proofs to Cloudinary"""
    if not current_user.is_admin:
        return "Admin only", 403
    
    try:
        migrated = 0
        errors = 0
        
        # Get all records with local files
        all_records = []
        all_records.extend(Purchase.query.filter(
            Purchase.payment_proof.isnot(None),
            ~Purchase.payment_proof.like('https://%')
        ).all())
        all_records.extend(ProductOrder.query.filter(
            ProductOrder.payment_proof.isnot(None),
            ~ProductOrder.payment_proof.like('https://%')
        ).all())
        all_records.extend(ClassEnrollment.query.filter(
            ClassEnrollment.payment_proof.isnot(None),
            ~ClassEnrollment.payment_proof.like('https://%')
        ).all())
        
        for record in all_records:
            try:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], record.payment_proof)
                
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as file:
                        record_type = 'course' if hasattr(record, 'course_id') else 'product' if hasattr(record, 'product_id') else 'class'
                        cloudinary_url = upload_payment_proof_to_cloudinary(
                            file, record_type, record.id, record.user_id
                        )
                    
                    if cloudinary_url:
                        record.payment_proof = cloudinary_url
                        migrated += 1
                    else:
                        errors += 1
                else:
                    errors += 1
                    
            except Exception as e:
                errors += 1
        
        if migrated > 0:
            db.session.commit()
        
        return f'''
        <html>
        <head><title>Migration Complete</title>
        <style>body {{ font-family: Arial; padding: 20px; text-align: center; }}</style></head>
        <body>
            <h1>📤 Payment Proof Migration Complete</h1>
            <p><strong>✅ Migrated:</strong> {migrated} files</p>
            <p><strong>❌ Errors:</strong> {errors} files</p>
            <p><strong>📁 Total processed:</strong> {len(all_records)} records</p>
            <p><a href="/admin/courses" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">← Back to Admin</a></p>
        </body>
        </html>
        '''
        
    except Exception as e:
        return f"Migration failed: {str(e)}"



@app.route('/payments')
@login_required
def payments():
    if current_user.is_admin:
        all_payments = Purchase.query.order_by(Purchase.purchased_at.desc()).all()
        total_revenue = db.session.query(db.func.sum(Purchase.amount)).filter_by(status='completed').scalar() or 0
        return render_template('admin_payments.html', 
                             payments=all_payments, 
                             total_revenue=total_revenue)
    else:
        user_payments = Purchase.query.filter_by(
            user_id=current_user.id
        ).order_by(Purchase.purchased_at.desc()).all()
        return render_template('user_payments.html', payments=user_payments)

# ========================================
# USER MANAGEMENT ROUTES
# ========================================

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))

    user_type = request.args.get('type', 'all')
    search = request.args.get('search', '')
    sort_by = request.args.get('sort', 'created_at')

    query = User.query
    if user_type == 'admin':
        query = query.filter_by(is_admin=True)
    elif user_type == 'student':
        query = query.filter_by(is_student=True)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            db.or_(
                User.username.like(search_filter),
                User.email.like(search_filter),
                User.first_name.like(search_filter),
                User.last_name.like(search_filter)
            )
        )

    if sort_by == 'username':
        query = query.order_by(User.username.asc())
    elif sort_by == 'email':
        query = query.order_by(User.email.asc())
    elif sort_by == 'name':
        query = query.order_by(User.first_name.asc(), User.last_name.asc())
    else:
        query = query.order_by(User.created_at.desc())

    users = query.all()
    total_users = User.query.count()
    total_admins = User.query.filter_by(is_admin=True).count()
    total_students = User.query.filter_by(is_student=True).count()

    return render_template('admin_users.html',
                           users=users,
                           total_users=total_users,
                           total_admins=total_admins,
                           total_students=total_students,
                           selected_type=user_type,
                           search_term=search,
                           sort_by=sort_by)

@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))

    user = User.query.get_or_404(user_id)

    if user.id == current_user.id and request.method == 'POST':
        if not request.form.get('is_admin'):
            flash('You cannot remove your own admin privileges!', 'danger')
            return redirect(url_for('edit_user', user_id=user_id))

    if request.method == 'POST':
        user.username = request.form['username']
        user.email = request.form['email']
        user.first_name = request.form['first_name']
        user.last_name = request.form['last_name']
        user.is_admin = 'is_admin' in request.form
        user.is_student = 'is_student' in request.form

        new_password = request.form.get('password')
        if new_password:
            user.set_password(new_password)

        try:
            db.session.commit()
            flash(f'User {user.username} updated successfully!', 'success')
            return redirect(url_for('admin_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {e}', 'danger')

    return render_template('edit_user.html', user=user, Purchase=Purchase)

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))

    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash('You cannot delete your own account!', 'danger')
        return redirect(url_for('admin_users'))

    try:
        username = user.username
        db.session.delete(user)
        db.session.commit()
        flash(f'User {username} deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {e}', 'danger')

    return redirect(url_for('admin_users'))

@app.route('/admin/users/create', methods=['GET', 'POST'])
@login_required
def create_user():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        is_admin = 'is_admin' in request.form
        is_student = 'is_student' in request.form

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return render_template('create_user.html')
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return render_template('create_user.html')

        try:
            user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_admin=is_admin,
                is_student=is_student
            )
            user.set_password(password)

            db.session.add(user)
            db.session.commit()

            flash(f'User {username} created successfully!', 'success')
            return redirect(url_for('admin_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating user: {e}', 'danger')

    return render_template('create_user.html')

@app.route('/admin/users/<int:user_id>/profile')
@login_required
def user_profile(user_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))

    user = User.query.get_or_404(user_id)

    purchases = Purchase.query.filter_by(user_id=user_id).order_by(Purchase.purchased_at.desc()).all()
    orders = ProductOrder.query.filter_by(user_id=user_id).order_by(ProductOrder.ordered_at.desc()).all()
    enrollments = ClassEnrollment.query.filter_by(user_id=user_id).order_by(ClassEnrollment.enrolled_at.desc()).all()

    total_spent = sum(p.amount for p in purchases if p.status == 'completed')
    total_spent += sum(o.total_amount for o in orders if o.status == 'completed')
    total_spent += sum(e.amount for e in enrollments if e.status == 'completed')

    return render_template('user_profile.html',
                           user=user,
                           purchases=purchases,
                           orders=orders,
                           enrollments=enrollments,
                           total_spent=total_spent,
                           IndividualClass=IndividualClass,
                           GroupClass=GroupClass)

@app.route('/admin/bulk-message', methods=['GET', 'POST'])
@login_required
def bulk_message():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        recipient_type = request.form.get('recipient_type')
        message_subject = request.form.get('subject', '')
        message_content = request.form.get('message', '')
        send_email = 'send_email' in request.form
        send_whatsapp = 'send_whatsapp' in request.form
        selected_users = request.form.getlist('selected_users')

        if not message_content:
            flash('Message content is required!', 'danger')
            return redirect(url_for('bulk_message'))

        if recipient_type == 'all':
            recipients = User.query.all()
        elif recipient_type == 'admins':
            recipients = User.query.filter_by(is_admin=True).all()
        elif recipient_type == 'students':
            recipients = User.query.filter_by(is_student=True).all()
        elif recipient_type == 'selected' and selected_users:
            recipients = User.query.filter(User.id.in_(selected_users)).all()
        else:
            flash('Please select recipients!', 'danger')
            return redirect(url_for('bulk_message'))

        if not recipients:
            flash('No recipients found!', 'warning')
            return redirect(url_for('bulk_message'))

        email_count = 0
        whatsapp_count = 0

        if send_email:
            email_count = send_bulk_email(recipients, message_subject, message_content)

        if send_whatsapp:
            whatsapp_count = len(recipients)
            whatsapp_links = generate_whatsapp_links(recipients, message_content)
            flash(f'WhatsApp links generated for {whatsapp_count} users. Check the results below.', 'info')
            return render_template('bulk_message_result.html',
                                   whatsapp_links=whatsapp_links,
                                   email_count=email_count,
                                   message=message_content)

        if email_count > 0:
            flash(f'Successfully sent {email_count} emails!', 'success')

        return redirect(url_for('bulk_message'))

    users = User.query.order_by(User.first_name, User.last_name).all()
    return render_template('bulk_message.html', users=users)

# ========================================
# FILE SERVING ROUTES
# ========================================

# Add this test route to verify upload process

# Add this temporary route to test video playback with existing videos
@app.route('/course_video_bypass/<filename>')
@login_required
def course_video_bypass(filename):
    """Bypass route for testing - serves videos without database check"""
    
    # Find the video file directly
    video_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
    video_file_path = os.path.join(video_folder, filename)
    
    # Check if file actually exists
    if not os.path.exists(video_file_path):
        return f"""
        <div style="padding: 20px; font-family: Arial;">
            <h1>File Not Found</h1>
            <p><strong>Looking for:</strong> {filename}</p>
            <p><strong>Path:</strong> {video_file_path}</p>
            <p><strong>Available files:</strong></p>
            <ul>
        """ + ''.join([f'<li>{f}</li>' for f in os.listdir(video_folder)]) + """
            </ul>
            <p><a href="/video-debug">← Back to Debug</a></p>
        </div>
        """, 404
    
    try:
        # Serve the video file directly
        return send_from_directory(
            video_folder, 
            filename, 
            mimetype='video/mp4',
            as_attachment=False
        )
    except Exception as e:
        return f"Error serving video: {e}", 500

# Add a test player page
@app.route('/test-player')
@login_required
def test_player():
    if not current_user.is_admin:
        return "Admin only", 403
    
    # Get available video files
    video_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
    available_files = []
    
    if os.path.exists(video_folder):
        available_files = [f for f in os.listdir(video_folder) if f.endswith(('.mp4', '.avi', '.mov'))]
    
    if not available_files:
        return """
        <h1>No Video Files Available</h1>
        <p>Upload a test video first at <a href="/test-upload">/test-upload</a></p>
        """
    
    # Create a simple video player page
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Video Player Test</title>
        <style>
            body { font-family: Arial; padding: 20px; }
            video { max-width: 800px; width: 100%; }
            .video-item { margin: 20px 0; padding: 15px; border: 1px solid #ddd; }
        </style>
    </head>
    <body>
        <h1>Video Player Test</h1>
        <p>Available video files:</p>
    """
    
    for video_file in available_files:
        html += f"""
        <div class="video-item">
            <h3>{video_file}</h3>
            <video controls>
                <source src="/course_video_bypass/{video_file}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
            <p><a href="/course_video_bypass/{video_file}" target="_blank">Direct link</a></p>
        </div>
        """
    
    html += """
        <p><a href="/test-upload">Upload another test video</a></p>
        <p><a href="/video-debug">Back to debug</a></p>
    </body>
    </html>
    """
    
    return html

@app.route('/test-upload', methods=['GET', 'POST'])
@login_required
def test_upload():
    if not current_user.is_admin:
        return "Only admin can test uploads", 403
    
    if request.method == 'POST':
        if 'test_video' not in request.files:
            return "No file uploaded", 400
        
        file = request.files['test_video']
        if file.filename == '':
            return "No file selected", 400
        
        if file:
            filename = secure_filename(file.filename)
            test_filename = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            
            video_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
            file_path = os.path.join(video_folder, test_filename)
            
            try:
                # Save the file
                file.save(file_path)
                
                # Check if it was saved
                file_exists = os.path.exists(file_path)
                file_size = os.path.getsize(file_path) if file_exists else 0
                
                # List all files in video folder
                all_files = os.listdir(video_folder) if os.path.exists(video_folder) else []
                
                result = f"""
                <h1>Test Upload Result</h1>
                <p><strong>File uploaded:</strong> {test_filename}</p>
                <p><strong>File saved to:</strong> {file_path}</p>
                <p><strong>File exists:</strong> {'✅ YES' if file_exists else '❌ NO'}</p>
                <p><strong>File size:</strong> {file_size / (1024*1024):.1f} MB</p>
                
                <h2>All files in video folder:</h2>
                <ul>
                """
                
                for f in all_files:
                    result += f"<li>{f}</li>"
                
                result += f"""
                </ul>
                
                <h2>Test Video Link:</h2>
                <p><a href="/course_video/{test_filename}" target="_blank">Try to play: {test_filename}</a></p>
                
                <p><a href="/test-upload">Upload another test video</a></p>
                <p><a href="/video-debug">Check debug info</a></p>
                """
                
                return result
                
            except Exception as e:
                return f"Upload failed: {e}"
    
    # GET request - show upload form
    return '''
    <h1>Test Video Upload</h1>
    <form method="POST" enctype="multipart/form-data">
        <p>Select a small video file (MP4, under 50MB):</p>
        <input type="file" name="test_video" accept=".mp4,.avi,.mov" required>
        <br><br>
        <button type="submit">Upload Test Video</button>
    </form>
    <p><a href="/video-debug">← Back to Debug</a></p>
    '''


#..................................................................................................................................................
@app.route('/course_material/<filename>')
@login_required
def course_material(filename):
    material = CourseMaterial.query.filter_by(filename=filename).first_or_404()
    
    if not current_user.is_admin:
        purchase = Purchase.query.filter_by(
            user_id=current_user.id,
            course_id=material.course_id,
            status='completed'
        ).first()
        
        if not purchase:
            flash('You need to purchase this course to access the materials.', 'warning')
            return redirect(url_for('course_detail', course_id=material.course_id))
    
    materials_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'materials')
    return send_from_directory(materials_folder, filename)

@app.route('/payment_proof/<path:filename>')
@login_required
def payment_proof(filename):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    # If it's a Cloudinary URL, redirect to it
    if filename.startswith('https://'):
        return redirect(filename)
    
    # Otherwise, try local file (for backward compatibility)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    else:
        return f"<div style='padding:20px;border:1px solid #ccc;'>Payment proof file not found: {filename}</div>", 404


def upload_payment_proof_to_cloudinary(file, enrollment_type, enrollment_id, user_id):
    """Upload payment proof to Cloudinary"""
    try:
        file.seek(0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        public_id = f"payment_proof_{enrollment_type}_{enrollment_id}_{user_id}_{timestamp}"
        
        result = cloudinary.uploader.upload(
            file,
            resource_type="image",
            public_id=public_id,
            folder="payment_proofs",
            overwrite=True,
            format="jpg",  # Convert to JPG for smaller size
            quality="auto"
        )
        
        return result['secure_url']
    except Exception as e:
        print(f"❌ Cloudinary payment proof upload error: {e}")
        return None



        
# ========================================
# CLASS ENROLLMENT ROUTES
# ========================================

@app.route('/classes')
@login_required
def available_classes():
    individual_classes = IndividualClass.query.all()
    group_classes = GroupClass.query.all()
    return render_template('available_classes.html',
                         individual_classes=individual_classes,
                         group_classes=group_classes)

@app.route('/enroll/<class_type>/<int:class_id>', methods=['GET', 'POST'])
@login_required
def enroll_class(class_type, class_id):
    # Validate class type
    if class_type not in ['individual', 'group']:
        flash('Invalid class type!', 'danger')
        return redirect(url_for('available_classes'))
    
    # Get the class object based on type
    if class_type == 'individual':
        class_obj = IndividualClass.query.get_or_404(class_id)
    else:
        class_obj = GroupClass.query.get_or_404(class_id)
    
    # Check if user is already enrolled
    existing_enrollment = ClassEnrollment.query.filter_by(
        user_id=current_user.id,
        class_id=class_id,
        class_type=class_type,
        status='completed'
    ).first()
    
    if existing_enrollment:
        flash('You are already enrolled in this class!', 'info')
        return redirect(url_for('student_dashboard'))
    
    # Check if there's a pending enrollment
    pending_enrollment = ClassEnrollment.query.filter_by(
        user_id=current_user.id,
        class_id=class_id,
        class_type=class_type,
        status='pending'
    ).first()
    
    if pending_enrollment:
        flash('You already have a pending enrollment for this class. Please wait for admin approval.', 'info')
        return redirect(url_for('student_dashboard'))
    
    # Set dynamic pricing based on class type
    if class_type == 'individual':
        class_fee = 100.00  # $100 for individual classes
        currency = '$'
        fee_display = f'${class_fee:.0f}'
    else:
        class_fee = 1000.00  # D1000 for group classes
        currency = 'D'
        fee_display = f'D{class_fee:.0f}'
    
    if request.method == 'POST':
        # Get form data
        payment_method = request.form.get('payment_method')
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        
        # Validate required fields
        if not all([payment_method, full_name, phone, email, address]):
            flash('All fields are required!', 'danger')
            return redirect(url_for('enroll_class', class_type=class_type, class_id=class_id))
        
        # Validate payment method
        valid_methods = ['bank_transfer', 'wave', 'western_union', 'moneygram', 'ria']
        if payment_method not in valid_methods:
            flash('Please select a valid payment method', 'danger')
            return redirect(url_for('enroll_class', class_type=class_type, class_id=class_id))
        
        # Handle payment proof upload to Cloudinary - CLEAN VERSION
        payment_proof = request.files.get('payment_proof')
        proof_url, error = handle_payment_proof_upload(
            payment_proof, 'class_enrollment', class_id, current_user.id
        )
        
        if error:
            flash(error, 'danger')
            return redirect(url_for('enroll_class', class_type=class_type, class_id=class_id))
        
        # Check group class capacity before enrollment
        if class_type == 'group':
            if len(class_obj.students) >= class_obj.max_students:
                flash('This group class is already full!', 'danger')
                return redirect(url_for('available_classes'))
        
        try:
            # Create enrollment record
            enrollment = ClassEnrollment(
                user_id=current_user.id,
                class_id=class_id,
                class_type=class_type,
                amount=class_fee,  # Dynamic amount based on class type
                status='pending',
                payment_method=payment_method,
                transaction_id=str(uuid.uuid4())[:8].upper(),
                customer_name=full_name,
                customer_phone=phone,
                customer_email=email,
                customer_address=address,
                payment_proof=proof_url  # Store Cloudinary URL
            )
            
            db.session.add(enrollment)
            db.session.commit()
            
            # Send notification email to admin (optional)
            try:
                admin_users = User.query.filter_by(is_admin=True).all()
                if admin_users:
                    subject = f"New Class Enrollment - {class_obj.name}"
                    message = f"""
A new enrollment has been submitted:

Class: {class_obj.name} ({class_type.title()})
Student: {full_name} ({current_user.username})
Email: {email}
Phone: {phone}
Amount: {fee_display}
Payment Method: {payment_method.replace('_', ' ').title()}
Transaction ID: {enrollment.transaction_id}

Please review and approve the enrollment in the admin dashboard.
"""
                    send_bulk_email(admin_users, subject, message)
            except Exception as e:
                print(f"Failed to send admin notification: {e}")
            
            flash(f'Enrollment submitted successfully! You will receive access to the class once our team verifies your payment of {fee_display}.', 'success')
            return redirect(url_for('student_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing enrollment: {str(e)}', 'danger')
            return redirect(url_for('enroll_class', class_type=class_type, class_id=class_id))
    
    # Payment methods configuration
    payment_methods = [
        {
            'id': 'bank_transfer',
            'name': 'Direct Bank Transfer',
            'details': 'Bank: Ecobank Gambia<br>Name: Abdoukadir Jabbie<br>Account #: 6261010783<br>SWIFT Code: ECOCGMGMXXX'
        },
        {
            'id': 'wave',
            'name': 'WAVE',
            'details': 'Phone: +2205427090<br>Name: Foday Muhammed Jabbi'
        },
        {
            'id': 'western_union',
            'name': 'Western Union',
            'details': 'Receiver Name: Foday Muhammed Jabbi<br>Country: The Gambia<br>Phone: +2205427090'
        },
        {
            'id': 'moneygram',
            'name': 'MoneyGram',
            'details': 'Receiver Name: Foday Muhammed Jabbi<br>Country: The Gambia<br>Phone: +2205427090'
        },
        {
            'id': 'ria',
            'name': 'Ria Money Transfer',
            'details': 'Receiver Name: Foday Muhammed Jabbi<br>Country: The Gambia<br>Phone: +2205427090'
        }
    ]
    
    return render_template('enroll_class.html',
                         class_obj=class_obj,
                         class_type=class_type,
                         payment_methods=payment_methods,
                         class_fee=class_fee,
                         currency=currency,
                         fee_display=fee_display)
    

@app.route('/admin/enrollments')
@login_required
def admin_enrollments():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))

    enrollments = ClassEnrollment.query.order_by(ClassEnrollment.enrolled_at.desc()).all()
    return render_template('admin_enrollments.html', enrollments=enrollments, IndividualClass=IndividualClass, GroupClass=GroupClass)



@app.route('/admin/edit_class/<class_type>/<int:class_id>', methods=['GET', 'POST'])
@login_required
def edit_class(class_type, class_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    # Get the class based on type
    if class_type == 'individual':
        class_obj = IndividualClass.query.get_or_404(class_id)
    elif class_type == 'group':
        class_obj = GroupClass.query.get_or_404(class_id)
    else:
        flash('Invalid class type!', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        # Update class details
        class_obj.name = request.form['name']
        class_obj.description = request.form.get('description', '')
        
        # Update max_students for group classes
        if class_type == 'group':
            new_max_students = int(request.form.get('max_students', 10))
            if new_max_students < len(class_obj.students):
                flash(f'Cannot set max students to {new_max_students}. Current enrollment: {len(class_obj.students)}', 'danger')
                return render_template('edit_class.html', class_obj=class_obj, class_type=class_type, students=User.query.filter_by(is_student=True).all())
            class_obj.max_students = new_max_students
        
        # Update student enrollment
        student_ids = request.form.getlist('students')
        selected_students = User.query.filter(User.id.in_(student_ids)).all() if student_ids else []
        
        # For group classes, check enrollment limit
        if class_type == 'group' and len(selected_students) > class_obj.max_students:
            flash(f'Cannot enroll {len(selected_students)} students. Maximum allowed: {class_obj.max_students}', 'danger')
            return render_template('edit_class.html', class_obj=class_obj, class_type=class_type, students=User.query.filter_by(is_student=True).all())
        
        # Update students list
        class_obj.students.clear()
        class_obj.students.extend(selected_students)
        
        try:
            db.session.commit()
            flash(f'{class_type.title()} class updated successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating class: {str(e)}', 'danger')
    
    # Get all students for the form
    students = User.query.filter_by(is_student=True).all()
    return render_template('edit_class.html', class_obj=class_obj, class_type=class_type, students=students)


@app.route('/admin/delete_class/<class_type>/<int:class_id>', methods=['POST'])
@login_required
def delete_class(class_type, class_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    # Get the class based on type
    if class_type == 'individual':
        class_obj = IndividualClass.query.get_or_404(class_id)
    elif class_type == 'group':
        class_obj = GroupClass.query.get_or_404(class_id)
    else:
        flash('Invalid class type!', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    class_name = class_obj.name
    
    try:
        # Check if there are any learning materials associated with this class
        materials_count = LearningMaterial.query.filter_by(
            class_type=class_type,
            actual_class_id=class_id
        ).count()
        
        if materials_count > 0:
            # You can choose to delete materials or prevent deletion
            # Option 1: Delete associated materials
            LearningMaterial.query.filter_by(
                class_type=class_type,
                actual_class_id=class_id
            ).delete()
            
            # Option 2: Prevent deletion (uncomment below and comment above)
            # flash(f'Cannot delete class "{class_name}". It has {materials_count} associated learning materials.', 'danger')
            # return redirect(url_for('admin_dashboard'))
        
        # Check for any enrollments
        enrollments_count = ClassEnrollment.query.filter_by(
            class_id=class_id,
            class_type=class_type
        ).count()
        
        if enrollments_count > 0:
            # Delete associated enrollments or prevent deletion
            # Option 1: Delete enrollments
            ClassEnrollment.query.filter_by(
                class_id=class_id,
                class_type=class_type
            ).delete()
            
            # Option 2: Prevent deletion (uncomment below and comment above)
            # flash(f'Cannot delete class "{class_name}". It has {enrollments_count} student enrollments.', 'danger')
            # return redirect(url_for('admin_dashboard'))
        
        # Clear student relationships before deleting
        class_obj.students.clear()
        
        # Delete the class
        db.session.delete(class_obj)
        db.session.commit()
        
        flash(f'{class_type.title()} class "{class_name}" deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting class: {str(e)}', 'danger')
    
    return redirect(url_for('admin_dashboard'))


# Add these routes to handle the new features:

@app.route('/admin/toggle-product-status/<int:product_id>', methods=['POST'])
@login_required
def toggle_product_status(product_id):
    if not current_user.is_admin:
        return {'success': False, 'error': 'Access denied'}
    
    product = Product.query.get_or_404(product_id)
    data = request.get_json()
    product.is_active = data.get('is_active', False)
    
    try:
        db.session.commit()
        return {'success': True}
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}

@app.route('/admin/product/<int:product_id>/details')
@login_required
def product_details(product_id):
    if not current_user.is_admin:
        return {'error': 'Access denied'}, 403
    
    product = Product.query.get_or_404(product_id)
    return {
        'id': product.id,
        'name': product.name,
        'description': product.description,
        'price': product.price,
        'category': product.category,
        'product_type': product.product_type,
        'stock_quantity': product.stock_quantity,
        'brand': product.brand,
        'sku': product.sku,
        'image_url': product.image_url,
        'is_active': product.is_active,
        'featured': product.featured
    }


#...................................................................................
# Add this route to your app.py file - just copy and paste it anywhere with your other routes

@app.route('/video-debug')
@login_required
def video_debug():
    if not current_user.is_admin:
        return "Only admin can see this", 403
    
    # Check what's in the database
    videos_in_db = CourseVideo.query.all()
    
    # Check upload folder
    upload_folder = app.config.get('UPLOAD_FOLDER', 'Not configured')
    video_folder = os.path.join(upload_folder, 'videos') if upload_folder != 'Not configured' else 'Not configured'
    
    html = '<h1>Video Debug Information</h1>'
    html += '<style>body { font-family: Arial; margin: 20px; }'
    html += '.section { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }'
    html += '.good { color: green; } .bad { color: red; }</style>'
    
    html += '<div class="section">'
    html += '<h2>📊 Database Information</h2>'
    html += f'<p>Videos in database: <strong>{len(videos_in_db)}</strong></p>'
    
    if videos_in_db:
        html += "<ul>"
        for video in videos_in_db:
            html += f"<li><strong>{video.title}</strong> - File: {video.video_filename}</li>"
        html += "</ul>"
    else:
        html += "<p class='bad'>❌ No videos found in database</p>"
    
    html += '</div>'
    
    # Folder info
    html += '<div class="section">'
    html += '<h2>📁 Folder Information</h2>'
    html += f'<p>Upload folder setting: <code>{upload_folder}</code></p>'
    html += f'<p>Video folder path: <code>{video_folder}</code></p>'
    
    folder_exists = os.path.exists(upload_folder) if upload_folder != 'Not configured' else False
    video_folder_exists = os.path.exists(video_folder) if video_folder != 'Not configured' else False
    
    html += f'<p>Upload folder exists: <span class="{"good" if folder_exists else "bad"}">'
    html += f'{"✅ YES" if folder_exists else "❌ NO"}</span></p>'
    html += f'<p>Video folder exists: <span class="{"good" if video_folder_exists else "bad"}">'
    html += f'{"✅ YES" if video_folder_exists else "❌ NO"}</span></p>'
    html += '</div>'
    
    # File listing
    if video_folder != 'Not configured' and os.path.exists(video_folder):
        try:
            files = os.listdir(video_folder)
            html += '<div class="section">'
            html += '<h2>📄 Files in Video Folder</h2>'
            html += f'<p>Found {len(files)} files:</p>'
            
            if files:
                html += '<ul>'
                for file in files:
                    file_path = os.path.join(video_folder, file)
                    file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
                    html += f'<li><strong>{file}</strong> ({file_size:.1f} MB)</li>'
                html += '</ul>'
            else:
                html += '<p class="bad">❌ No files found</p>'
            html += '</div>'
        except Exception as e:
            html += f'<div class="section"><p class="bad">Error reading folder: {e}</p></div>'
    
    html += '<div class="section"><a href="/admin/courses">← Back to Courses</a></div>'
    return html


# Add these routes to your app.py file (after your existing routes)

@app.route('/admin/reupload-videos')
@login_required
def reupload_videos():
    """Show missing videos and allow re-upload"""
    if not current_user.is_admin:
        return "Admin only", 403
    
    # Get all videos from database
    all_videos = CourseVideo.query.all()
    video_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
    
    missing_videos = []
    existing_videos = []
    
    for video in all_videos:
        video_path = os.path.join(video_folder, video.video_filename)
        if os.path.exists(video_path):
            existing_videos.append(video)
        else:
            missing_videos.append(video)
    
    html = '<html><head><title>Re-upload Missing Videos</title>'
    html += '<style>'
    html += 'body { font-family: Arial; padding: 20px; }'
    html += '.video-item { margin: 15px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }'
    html += '.missing { border-color: #dc3545; background: #f8d7da; }'
    html += '.existing { border-color: #28a745; background: #d4edda; }'
    html += '.upload-form { margin: 10px 0; }'
    html += 'input[type="file"] { margin: 5px 0; }'
    html += 'button { background: #007bff; color: white; padding: 8px 15px; border: none; border-radius: 3px; cursor: pointer; }'
    html += 'button:hover { background: #0056b3; }'
    html += '.success { color: #28a745; }'
    html += '.error { color: #dc3545; }'
    html += '</style></head><body>'
    
    html += '<h1>Video Re-upload System</h1>'
    
    html += '<div style="background: #e3f2fd; padding: 15px; margin: 20px 0; border-radius: 5px;">'
    html += '<h3>📊 Summary:</h3>'
    html += f'<p><strong>Total videos in database:</strong> {len(all_videos)}</p>'
    html += f'<p><strong>Missing video files:</strong> <span class="error">{len(missing_videos)}</span></p>'
    html += f'<p><strong>Existing video files:</strong> <span class="success">{len(existing_videos)}</span></p>'
    html += '</div>'
    
    if missing_videos:
        html += '<h2>❌ Missing Videos (Need Re-upload)</h2>'
        for video in missing_videos:
            course = Course.query.get(video.course_id)
            course_name = course.title if course else "Unknown Course"
            
            html += f'<div class="video-item missing">'
            html += f'<h4>{video.title}</h4>'
            html += f'<p><strong>Course:</strong> {course_name}</p>'
            html += f'<p><strong>Expected filename:</strong> {video.video_filename}</p>'
            html += f'<form method="POST" action="/admin/reupload-video/{video.id}" enctype="multipart/form-data" class="upload-form">'
            html += f'<input type="file" name="video_file" accept=".mp4,.avi,.mov" required>'
            html += f'<button type="submit">Re-upload Video</button>'
            html += f'</form>'
            html += f'</div>'
    
    if existing_videos:
        html += '<h2>✅ Videos with Files Present</h2>'
        for video in existing_videos:
            course = Course.query.get(video.course_id)
            course_name = course.title if course else "Unknown Course"
            file_path = os.path.join(video_folder, video.video_filename)
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
            
            html += f'<div class="video-item existing">'
            html += f'<h4>{video.title}</h4>'
            html += f'<p><strong>Course:</strong> {course_name}</p>'
            html += f'<p><strong>Filename:</strong> {video.video_filename}</p>'
            html += f'<p><strong>File size:</strong> {file_size:.1f} MB</p>'
            html += f'<p><a href="/course_video_bypass/{video.video_filename}" target="_blank">🎬 Test Play</a></p>'
            html += f'</div>'
    
    html += '<div style="margin: 30px 0; padding: 15px; background: #fff3cd; border-radius: 5px;">'
    html += '<h3>💡 Instructions:</h3>'
    html += '<ol>'
    html += '<li>For each missing video, click "Choose File" and select the correct video file</li>'
    html += '<li>Click "Re-upload Video" to upload the file</li>'
    html += '<li>The file will be saved with the same filename as expected by the database</li>'
    html += '<li>Test the video using the "Test Play" link after upload</li>'
    html += '</ol>'
    html += '</div>'
    
    html += '<p><a href="/admin/courses">← Back to Admin Courses</a></p>'
    html += '<p><a href="/video-debug">🔍 Check Debug Info</a></p>'
    html += '</body></html>'
    
    return html

@app.route('/admin/reupload-video/<int:video_id>', methods=['POST'])
@login_required
def reupload_video(video_id):
    """Handle individual video re-upload"""
    if not current_user.is_admin:
        return "Admin only", 403
    
    video = CourseVideo.query.get_or_404(video_id)
    
    if 'video_file' not in request.files:
        return "No file provided", 400
    
    file = request.files['video_file']
    if file.filename == '':
        return "No file selected", 400
    
    try:
        video_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
        
        # Save with the exact filename expected by the database
        file_path = os.path.join(video_folder, video.video_filename)
        file.save(file_path)
        
        # Verify the file was saved
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
            course = Course.query.get(video.course_id)
            course_name = course.title if course else "Unknown Course"
            
            html = '<html><head><title>Video Re-uploaded</title>'
            html += '<style>body { font-family: Arial; padding: 20px; }</style>'
            html += '</head><body>'
            html += '<h1>✅ Video Re-uploaded Successfully!</h1>'
            html += f'<p><strong>Video:</strong> {video.title}</p>'
            html += f'<p><strong>Course:</strong> {course_name}</p>'
            html += f'<p><strong>Filename:</strong> {video.video_filename}</p>'
            html += f'<p><strong>File size:</strong> {file_size:.1f} MB</p>'
            
            html += '<h3>Test the video:</h3>'
            html += f'<video controls style="max-width: 500px; width: 100%;">'
            html += f'<source src="/course_video_bypass/{video.video_filename}" type="video/mp4">'
            html += 'Your browser does not support the video tag.'
            html += '</video>'
            
            html += '<p><a href="/admin/reupload-videos">← Back to Re-upload Page</a></p>'
            html += '<p><a href="/admin/courses">← Back to Admin Courses</a></p>'
            html += '</body></html>'
            
            return html
        else:
            return "Error: File was not saved properly", 500
            
    except Exception as e:
        return f"Upload failed: {str(e)}", 500

@app.route('/admin/bulk-reupload', methods=['GET', 'POST'])
@login_required
def bulk_reupload():
    """Allow bulk re-upload of multiple videos at once"""
    if not current_user.is_admin:
        return "Admin only", 403
    
    if request.method == 'POST':
        uploaded_count = 0
        errors = []
        
        try:
            # Get all uploaded files
            for key in request.files:
                if key.startswith('video_'):
                    video_id = int(key.replace('video_', ''))
                    file = request.files[key]
                    
                    if file and file.filename:
                        video = CourseVideo.query.get(video_id)
                        if video:
                            try:
                                video_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
                                file_path = os.path.join(video_folder, video.video_filename)
                                file.save(file_path)
                                
                                if os.path.exists(file_path):
                                    uploaded_count += 1
                                else:
                                    errors.append(f"Failed to save {video.title}")
                            except Exception as e:
                                errors.append(f"Error uploading {video.title}: {str(e)}")
            
            result_html = '<html><head><title>Bulk Upload Results</title>'
            result_html += '<style>body { font-family: Arial; padding: 20px; }</style>'
            result_html += '</head><body>'
            result_html += '<h1>📊 Bulk Upload Results</h1>'
            result_html += f'<p><strong>✅ Successfully uploaded:</strong> {uploaded_count} videos</p>'
            
            if errors:
                result_html += f'<p><strong>❌ Errors:</strong> {len(errors)}</p>'
                result_html += '<ul>'
                for error in errors:
                    result_html += f'<li>{error}</li>'
                result_html += '</ul>'
            
            result_html += '<p><a href="/admin/reupload-videos">← Back to Re-upload Page</a></p>'
            result_html += '<p><a href="/test-player">🎬 Test Videos</a></p>'
            result_html += '</body></html>'
            
            return result_html
            
        except Exception as e:
            return f"Bulk upload failed: {str(e)}", 500
    
    # GET request - show bulk upload form
    missing_videos = []
    all_videos = CourseVideo.query.all()
    video_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
    
    for video in all_videos:
        video_path = os.path.join(video_folder, video.video_filename)
        if not os.path.exists(video_path):
            missing_videos.append(video)
    
    if not missing_videos:
        return '<h1>✅ No Missing Videos</h1><p>All videos are present!</p><p><a href="/admin/courses">← Back to Courses</a></p>'
    
    html = '<html><head><title>Bulk Video Re-upload</title>'
    html += '<style>body { font-family: Arial; padding: 20px; }'
    html += '.video-row { margin: 10px 0; padding: 10px; border: 1px solid #ddd; }'
    html += 'input[type="file"] { width: 300px; }'
    html += '</style></head><body>'
    
    html += '<h1>📦 Bulk Video Re-upload</h1>'
    html += f'<p>Upload multiple videos at once. Found <strong>{len(missing_videos)}</strong> missing videos.</p>'
    
    html += '<form method="POST" enctype="multipart/form-data">'
    for video in missing_videos:
        course = Course.query.get(video.course_id)
        course_name = course.title if course else "Unknown Course"
        
        html += '<div class="video-row">'
        html += f'<strong>{video.title}</strong> ({course_name})<br>'
        html += f'<input type="file" name="video_{video.id}" accept=".mp4,.avi,.mov">'
        html += '</div>'
    
    html += '<br><button type="submit" style="background: #28a745; color: white; padding: 10px 20px; border: none; border-radius: 5px;">📤 Upload All Videos</button>'
    html += '</form>'
    
    html += '<p><a href="/admin/reupload-videos">← Back to Individual Upload</a></p>'
    html += '</body></html>'
    
    return html


#...............................................................................................................................

# 2. ADD THESE IMPORTS at the top of your app.py (after your existing imports)
import cloudinary
import cloudinary.uploader
import cloudinary.api

# 3. ADD CLOUDINARY CONFIGURATION after your existing app.config settings
# Add this after your WhatsApp config line:

# Cloudinary Configuration
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', 'dfizb64hx'),
    api_key=os.environ.get('CLOUDINARY_API_KEY', '959475453929561'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET', 'bLYgaJv1YnTToGNN-xamKKC-9Ac')
)

# 4. ADD THIS HELPER FUNCTION (add anywhere in your app.py, I suggest after your other helper functions)
# Enhanced upload_video_to_cloudinary function
# Replace your existing function in app.py with this improved version:

def upload_video_to_cloudinary(video_file, course_id, video_index):
    """Upload video to Cloudinary and return the URL - ENHANCED VERSION"""
    try:
        print(f"🚀 Starting Cloudinary upload...")
        print(f"   Course ID: {course_id}")
        print(f"   Video Index: {video_index}")
        
        # Reset file pointer to beginning
        video_file.seek(0)
        
        # Create a unique public_id for the video
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        public_id = f"course_{course_id}_video_{video_index}_{timestamp}"
        
        print(f"📝 Public ID: {public_id}")
        
        # Get file size for logging
        video_file.seek(0, 2)
        file_size = video_file.tell()
        video_file.seek(0)
        print(f"📁 File size: {file_size / (1024*1024):.1f}MB")
        
        # Upload to Cloudinary with optimized settings
        upload_params = {
            'resource_type': "video",
            'public_id': public_id,
            'folder': "course_videos",
            'overwrite': True,
            'format': "mp4",  # Convert to MP4 automatically
            'quality': "auto",  # Optimize quality automatically
            'fetch_format': "auto",  # Use best format for delivery
            'flags': "progressive",  # Enable progressive streaming
        }
        
        print(f"📤 Uploading to Cloudinary with params: {upload_params}")
        
        # Perform the upload
        result = cloudinary.uploader.upload(
            video_file,
            **upload_params
        )
        
        print(f"✅ Cloudinary upload successful!")
        print(f"   URL: {result.get('secure_url', 'No URL')}")
        print(f"   Public ID: {result.get('public_id', 'No ID')}")
        print(f"   Duration: {result.get('duration', 'Unknown')} seconds")
        print(f"   Size: {result.get('bytes', 0) / (1024*1024):.1f}MB")
        
        # Return structured result
        upload_data = {
            'url': result['secure_url'],
            'public_id': result['public_id'],
            'duration': result.get('duration', 0),
            'size': result.get('bytes', 0),
            'format': result.get('format', 'mp4'),
            'width': result.get('width', 0),
            'height': result.get('height', 0)
        }
        
        return upload_data
        
    except Exception as e:
        print(f"❌ Cloudinary upload error: {str(e)}")
        import traceback
        print("Full traceback:")
        traceback.print_exc()
        return None

# Also add this helper function to check Cloudinary configuration:
def check_cloudinary_config():
    """Check if Cloudinary is properly configured"""
    try:
        config = cloudinary.config()
        print(f"☁️ Cloudinary Configuration:")
        print(f"   Cloud Name: {config.cloud_name}")
        print(f"   API Key: {config.api_key}")
        print(f"   API Secret: {'***' + config.api_secret[-4:] if config.api_secret else 'Not set'}")
        
        # Test connection
        result = cloudinary.api.ping()
        print(f"✅ Cloudinary connection test: {result}")
        return True
    except Exception as e:
        print(f"❌ Cloudinary configuration error: {e}")
        return False

#//////////////////////////////////////////////////////////////////////////

def upload_digital_file_to_cloudinary(file, product_id, original_filename):
    """Upload digital product file (PDF, etc.) to Cloudinary permanently"""
    try:
        print(f"📤 Uploading digital file to Cloudinary: {original_filename}")
        
        # Reset file pointer to beginning
        file.seek(0)
        
        # Create a unique public_id for the file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = secure_filename(original_filename).replace('.', '_')
        public_id = f"product_{product_id}_{safe_filename}_{timestamp}"
        
        # Get file size for logging
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        print(f"📁 File size: {file_size / (1024*1024):.1f}MB")
        
        # Determine resource type based on file extension
        file_extension = original_filename.lower().split('.')[-1] if '.' in original_filename else ''
        
        if file_extension in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']:
            resource_type = "image"
        elif file_extension in ['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm']:
            resource_type = "video"
        else:
            resource_type = "raw"  # For PDFs, documents, etc.
        
        # Upload to Cloudinary with optimized settings for digital products
        upload_params = {
            'resource_type': resource_type,
            'public_id': public_id,
            'folder': "digital_products",
            'overwrite': True,
            'use_filename': True,
            'unique_filename': False,
        }
        
        # Add format for PDFs and documents
        if file_extension == 'pdf':
            upload_params['format'] = 'pdf'
        
        print(f"📤 Uploading to Cloudinary with params: {upload_params}")
        
        # Perform the upload
        result = cloudinary.uploader.upload(file, **upload_params)
        
        print(f"✅ Cloudinary upload successful!")
        print(f"   URL: {result.get('secure_url', 'No URL')}")
        print(f"   Public ID: {result.get('public_id', 'No ID')}")
        print(f"   Size: {result.get('bytes', 0) / (1024*1024):.1f}MB")
        print(f"   Format: {result.get('format', 'Unknown')}")
        
        # Return structured result
        upload_data = {
            'url': result['secure_url'],
            'public_id': result['public_id'],
            'size': result.get('bytes', 0),
            'format': result.get('format', file_extension),
            'resource_type': result.get('resource_type', resource_type)
        }
        
        return upload_data
        
    except Exception as e:
        print(f"❌ Cloudinary upload error: {str(e)}")
        import traceback
        print("Full traceback:")
        traceback.print_exc()
        return None

def delete_digital_file_from_cloudinary(public_id, resource_type="raw"):
    """Delete digital file from Cloudinary"""
    try:
        result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        print(f"🗑️ Deleted from Cloudinary: {public_id}")
        return result.get('result') == 'ok'
    except Exception as e:
        print(f"❌ Error deleting from Cloudinary: {e}")
        return False

# Add this migration route to your app.py to add Cloudinary fields to existing table

@app.route('/admin/migrate-digital-files-table')
@login_required
def migrate_digital_files_table():
    """Add Cloudinary fields to existing digital_product_file table - ADMIN ONLY"""
    if not current_user.is_admin:
        return "Access denied: Admin privileges required", 403
    
    try:
        # Check if table exists and what columns it has
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        
        # Check if table exists
        if 'digital_product_file' not in inspector.get_table_names():
            # Create table if it doesn't exist
            db.create_all()
            return """
            <html>
            <head><title>Table Created</title>
            <style>body { font-family: Arial; padding: 20px; text-align: center; }</style></head>
            <body>
                <h1>✅ Digital Product Files Table Created!</h1>
                <p>The table has been created with all Cloudinary fields.</p>
                <p><a href="/admin/products">← Back to Products</a></p>
            </body>
            </html>
            """
        
        # Get existing columns
        columns = [col['name'] for col in inspector.get_columns('digital_product_file')]
        
        # Add missing Cloudinary columns
        new_columns = []
        
        with db.engine.connect() as conn:
            if 'cloudinary_url' not in columns:
                if 'sqlite' in str(db.engine.url):
                    conn.execute(db.text('ALTER TABLE digital_product_file ADD COLUMN cloudinary_url VARCHAR(500)'))
                else:
                    conn.execute(db.text('ALTER TABLE digital_product_file ADD COLUMN cloudinary_url VARCHAR(500)'))
                new_columns.append('cloudinary_url')
            
            if 'cloudinary_public_id' not in columns:
                if 'sqlite' in str(db.engine.url):
                    conn.execute(db.text('ALTER TABLE digital_product_file ADD COLUMN cloudinary_public_id VARCHAR(255)'))
                else:
                    conn.execute(db.text('ALTER TABLE digital_product_file ADD COLUMN cloudinary_public_id VARCHAR(255)'))
                new_columns.append('cloudinary_public_id')
            
            if 'cloudinary_resource_type' not in columns:
                if 'sqlite' in str(db.engine.url):
                    conn.execute(db.text("ALTER TABLE digital_product_file ADD COLUMN cloudinary_resource_type VARCHAR(20) DEFAULT 'raw'"))
                else:
                    conn.execute(db.text("ALTER TABLE digital_product_file ADD COLUMN cloudinary_resource_type VARCHAR(20) DEFAULT 'raw'"))
                new_columns.append('cloudinary_resource_type')
            
            if 'storage_type' not in columns:
                if 'sqlite' in str(db.engine.url):
                    conn.execute(db.text("ALTER TABLE digital_product_file ADD COLUMN storage_type VARCHAR(20) DEFAULT 'local'"))
                else:
                    conn.execute(db.text("ALTER TABLE digital_product_file ADD COLUMN storage_type VARCHAR(20) DEFAULT 'local'"))
                new_columns.append('storage_type')
                
            conn.commit()
        
        return f"""
        <html>
        <head><title>Migration Complete</title>
        <style>body {{ font-family: Arial; padding: 20px; text-align: center; }}</style></head>
        <body>
            <h1>✅ Database Migration Complete!</h1>
            <p><strong>Added columns:</strong> {', '.join(new_columns) if new_columns else 'No new columns needed'}</p>
            <p><strong>Existing columns:</strong> {', '.join(columns)}</p>
            
            <h3>🎯 Next Steps:</h3>
            <ol style="text-align: left; max-width: 600px; margin: 0 auto;">
                <li><strong>Upload new digital products</strong> - They'll automatically go to Cloudinary</li>
                <li><strong>Migrate existing files</strong> - <a href="/admin/migrate-digital-files-to-cloudinary">Click here to migrate</a></li>
                <li><strong>Test downloads</strong> - Verify files work correctly</li>
            </ol>
            
            <p style="margin-top: 2rem;">
                <a href="/admin/products" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">← Back to Products</a>
            </p>
        </body>
        </html>
        """
        
    except Exception as e:
        return f"""
        <html>
        <head><title>Migration Error</title>
        <style>body {{ font-family: Arial; padding: 20px; text-align: center; }}</style></head>
        <body>
            <h1>❌ Migration Failed</h1>
            <p><strong>Error:</strong> {str(e)}</p>
            <p><a href="/admin/products">← Back to Products</a></p>
        </body>
        </html>
        """, 500

@app.route('/admin/migrate-digital-files-to-cloudinary')
@login_required
def migrate_digital_files_to_cloudinary():
    """Migrate existing local digital files to Cloudinary - ADMIN ONLY"""
    if not current_user.is_admin:
        return "Access denied", 403
    
    try:
        # Get all digital files stored locally
        local_files = DigitalProductFile.query.filter_by(storage_type='local').all()
        digital_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'digital_products')
        
        migrated_count = 0
        errors = []
        
        for digital_file in local_files:
            try:
                file_path = os.path.join(digital_folder, digital_file.filename)
                
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as file:
                        upload_result = upload_digital_file_to_cloudinary(
                            file, digital_file.product_id, digital_file.original_filename
                        )
                    
                    if upload_result:
                        # Update database record
                        digital_file.cloudinary_url = upload_result['url']
                        digital_file.cloudinary_public_id = upload_result['public_id']
                        digital_file.cloudinary_resource_type = upload_result['resource_type']
                        digital_file.storage_type = 'cloudinary'
                        migrated_count += 1
                        print(f"✅ Migrated: {digital_file.original_filename}")
                    else:
                        errors.append(f"Failed to upload {digital_file.original_filename}")
                else:
                    errors.append(f"File not found: {digital_file.filename}")
                    
            except Exception as e:
                errors.append(f"Error with {digital_file.original_filename}: {str(e)}")
        
        if migrated_count > 0:
            db.session.commit()
        
        return f'''
        <html>
        <head><title>Digital Files Migration Complete</title>
        <style>body {{ font-family: Arial; padding: 20px; text-align: center; }}</style></head>
        <body>
            <h1>📤 Digital Files Migration Complete</h1>
            <p><strong>✅ Migrated:</strong> {migrated_count} files</p>
            <p><strong>❌ Errors:</strong> {len(errors)} files</p>
            <p><strong>📁 Total processed:</strong> {len(local_files)} files</p>
            {"<ul>" + "".join([f"<li>{error}</li>" for error in errors]) + "</ul>" if errors else ""}
            <p><a href="/admin/products" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">← Back to Products</a></p>
        </body>
        </html>
        '''
        
    except Exception as e:
        return f"Migration failed: {str(e)}"

#////////////////////////////////////////////////////////////////////////////////////////////////////

# Add this route for debugging Cloudinary
@app.route('/admin/test-cloudinary')
@login_required
def test_cloudinary():
    """Test Cloudinary connection - ADMIN ONLY"""
    if not current_user.is_admin:
        return "Access denied", 403
    
    try:
        config_ok = check_cloudinary_config()
        
        if config_ok:
            return {
                'status': 'success',
                'message': 'Cloudinary is properly configured and accessible',
                'cloud_name': cloudinary.config().cloud_name
            }
        else:
            return {
                'status': 'error', 
                'message': 'Cloudinary configuration failed'
            }, 500
            
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }, 500


@app.route('/admin/cloudinary-test')
@login_required
def cloudinary_test():
    """Test Cloudinary connection"""
    if not current_user.is_admin:
        return "Admin only", 403
    
    try:
        # Test Cloudinary connection
        result = cloudinary.api.ping()
        
        html = '<html><head><title>Cloudinary Test</title>'
        html += '<style>body { font-family: Arial; padding: 20px; }</style></head><body>'
        html += '<h1>☁️ Cloudinary Connection Test</h1>'
        html += '<p><strong>✅ Connection successful!</strong></p>'
        html += f'<p><strong>Cloud Name:</strong> {cloudinary.config().cloud_name}</p>'
        html += f'<p><strong>API Key:</strong> {cloudinary.config().api_key}</p>'
        html += f'<p><strong>Status:</strong> {result.get("status", "OK")}</p>'
        
        # Test upload quota
        try:
            usage = cloudinary.api.usage()
            storage_mb = usage.get("storage", {}).get("usage", 0) / 1024 / 1024
            bandwidth_mb = usage.get("bandwidth", {}).get("usage", 0) / 1024 / 1024
            
            html += '<h3>📊 Usage Statistics:</h3>'
            html += f'<p><strong>Storage used:</strong> {storage_mb:.1f} MB / 25,000 MB</p>'
            html += f'<p><strong>Bandwidth used this month:</strong> {bandwidth_mb:.1f} MB / 25,000 MB</p>'
            html += f'<p><strong>Storage remaining:</strong> {25000 - storage_mb:.1f} MB</p>'
        except Exception as e:
            html += f'<p><em>Could not fetch usage: {e}</em></p>'
        
        html += '<p><a href="/admin/migrate-existing-videos">🚀 Migrate Existing Videos</a></p>'
        html += '<p><a href="/admin/courses">← Back to Courses</a></p>'
        html += '</body></html>'
        
        return html
        
    except Exception as e:
        return f'''
        <html><head><title>Cloudinary Error</title>
        <style>body {{ font-family: Arial; padding: 20px; }}</style></head><body>
        <h1>❌ Cloudinary Connection Failed</h1>
        <p><strong>Error:</strong> {str(e)}</p>
        <h3>💡 How to Fix:</h3>
        <ol>
            <li>Check environment variables on Render:
                <ul>
                    <li>CLOUDINARY_CLOUD_NAME=dfizb64hx</li>
                    <li>CLOUDINARY_API_KEY=959475453929561</li>
                    <li>CLOUDINARY_API_SECRET=bLYgaJv1YnTToGNN-xamKKC-9Ac</li>
                </ul>
            </li>
            <li>Redeploy your app after adding variables</li>
            <li>Check if cloudinary is in requirements.txt</li>
        </ol>
        <p><a href="/admin/courses">← Back to Courses</a></p>
        </body></html>
        '''


# 7. ADD MIGRATION ROUTES for your existing videos

@app.route('/admin/migrate-existing-videos')
@login_required
def migrate_existing_videos():
    """Show existing videos and migrate them to Cloudinary"""
    if not current_user.is_admin:
        return "Admin only", 403
    
    # Get all videos that have local files but no Cloudinary URL
    all_videos = CourseVideo.query.all()
    video_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
    
    local_videos = []
    cloudinary_videos = []
    missing_videos = []
    
    for video in all_videos:
        if video.video_url:  # Has Cloudinary URL
            cloudinary_videos.append(video)
        else:
            video_path = os.path.join(video_folder, video.video_filename)
            if os.path.exists(video_path):
                local_videos.append(video)
            else:
                missing_videos.append(video)
    
    html = '<html><head><title>Migrate Videos to Cloudinary</title>'
    html += '<style>'
    html += 'body { font-family: Arial; padding: 20px; }'
    html += '.video-item { margin: 15px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }'
    html += '.local { border-color: #ffc107; background: #fff3cd; }'
    html += '.cloudinary { border-color: #28a745; background: #d4edda; }'
    html += '.missing { border-color: #dc3545; background: #f8d7da; }'
    html += 'button { background: #007bff; color: white; padding: 8px 15px; border: none; border-radius: 3px; cursor: pointer; }'
    html += '.migrate-btn { background: #28a745; }'
    html += '</style></head><body>'
    
    html += '<h1>🚀 Migrate Videos to Cloudinary</h1>'
    
    html += '<div style="background: #e3f2fd; padding: 15px; margin: 20px 0; border-radius: 5px;">'
    html += '<h3>📊 Video Status:</h3>'
    html += f'<p><strong>✅ Already on Cloudinary:</strong> {len(cloudinary_videos)}</p>'
    html += f'<p><strong>📁 Local files (need migration):</strong> {len(local_videos)}</p>'
    html += f'<p><strong>❌ Missing files:</strong> {len(missing_videos)}</p>'
    html += '</div>'
    
    if local_videos:
        html += '<h2>📁 Local Videos (Ready to Migrate)</h2>'
        html += '<form method="POST" action="/admin/start-migration">'
        
        for video in local_videos:
            course = Course.query.get(video.course_id)
            course_name = course.title if course else "Unknown Course"
            video_path = os.path.join(video_folder, video.video_filename)
            file_size = os.path.getsize(video_path) / (1024 * 1024)  # MB
            
            html += f'<div class="video-item local">'
            html += f'<input type="checkbox" name="video_ids" value="{video.id}" checked> '
            html += f'<strong>{video.title}</strong><br>'
            html += f'Course: {course_name}<br>'
            html += f'File: {video.video_filename} ({file_size:.1f} MB)<br>'
            html += f'<a href="/course_video_bypass/{video.video_filename}" target="_blank">🎬 Test Play</a>'
            html += f'</div>'
        
        html += '<br><button type="submit" class="migrate-btn">🚀 Migrate Selected Videos to Cloudinary</button>'
        html += '</form>'
    
    if cloudinary_videos:
        html += '<h2>☁️ Videos Already on Cloudinary</h2>'
        for video in cloudinary_videos:
            course = Course.query.get(video.course_id)
            course_name = course.title if course else "Unknown Course"
            
            html += f'<div class="video-item cloudinary">'
            html += f'<strong>{video.title}</strong><br>'
            html += f'Course: {course_name}<br>'
            html += f'Cloudinary ID: {video.video_filename}<br>'
            html += f'<a href="{video.video_url}" target="_blank">🎬 Play from Cloudinary</a>'
            html += f'</div>'
    
    if missing_videos:
        html += '<h2>❌ Missing Videos</h2>'
        for video in missing_videos:
            course = Course.query.get(video.course_id)
            course_name = course.title if course else "Unknown Course"
            
            html += f'<div class="video-item missing">'
            html += f'<strong>{video.title}</strong><br>'
            html += f'Course: {course_name}<br>'
            html += f'Status: File not found<br>'
            html += f'<a href="/admin/reupload-videos">📤 Re-upload Missing Videos</a>'
            html += f'</div>'
    
    html += '<p><a href="/admin/courses">← Back to Admin Courses</a></p>'
    html += '</body></html>'
    
    return html

@app.route('/admin/start-migration', methods=['POST'])
@login_required
def start_migration():
    """Migrate selected videos to Cloudinary"""
    if not current_user.is_admin:
        return "Admin only", 403
    
    video_ids = request.form.getlist('video_ids')
    if not video_ids:
        return "No videos selected", 400
    
    html = '<html><head><title>Migration Progress</title>'
    html += '<style>body { font-family: Arial; padding: 20px; }</style>'
    html += '</head><body>'
    html += '<h1>🚀 Migration Progress</h1>'
    
    migrated_count = 0
    errors = []
    
    for video_id in video_ids:
        try:
            video = CourseVideo.query.get(int(video_id))
            if not video:
                continue
            
            video_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
            video_path = os.path.join(video_folder, video.video_filename)
            
            if not os.path.exists(video_path):
                errors.append(f"File not found: {video.title}")
                continue
            
            html += f'<p>🔄 Migrating: {video.title}...</p>'
            
            # Upload to Cloudinary
            with open(video_path, 'rb') as file:
                upload_result = upload_video_to_cloudinary(file, video.course_id, video.id)
            
            if upload_result:
                # Update database record
                video.video_url = upload_result['url']
                # Keep the original filename for backward compatibility
                # video.video_filename = upload_result['public_id']
                
                db.session.commit()
                migrated_count += 1
                html += f'<p>✅ Success: {video.title} migrated to Cloudinary</p>'
            else:
                errors.append(f"Upload failed: {video.title}")
                html += f'<p>❌ Failed: {video.title}</p>'
                
        except Exception as e:
            errors.append(f"Error with {video.title}: {str(e)}")
            html += f'<p>❌ Error: {video.title} - {str(e)}</p>'
    
    html += f'<h2>📊 Migration Summary</h2>'
    html += f'<p><strong>✅ Successfully migrated:</strong> {migrated_count} videos</p>'
    html += f'<p><strong>❌ Errors:</strong> {len(errors)}</p>'
    
    if errors:
        html += '<h3>Error Details:</h3><ul>'
        for error in errors:
            html += f'<li>{error}</li>'
        html += '</ul>'
    
    html += '<p><a href="/admin/migrate-existing-videos">← Back to Migration Page</a></p>'
    html += '<p><a href="/test-player">🎬 Test Migrated Videos</a></p>'
    html += '</body></html>'
    
    return html


# ========================================
# SAMPLE DATA CREATION - CLEANED VERSION
# ========================================

def create_sample_data():
    """Create sample admin user and data if they don't exist"""
    try:
        # Create admin user
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@example.com',
                first_name='Admin',
                last_name='User',
                is_admin=True,
                is_student=False
            )
            admin.set_password('admin123')
            db.session.add(admin)
            print("Created admin user")
        
        # Create sample students
        for i in range(1, 6):
            student = User.query.filter_by(username=f'student{i}').first()
            if not student:
                student = User(
                    username=f'student{i}',
                    email=f'student{i}@example.com',
                    first_name='Student',
                    last_name=str(i),
                    is_admin=False,
                    is_student=True
                )
                student.set_password('password123')
                db.session.add(student)

        # Get admin user for creating related data (avoid duplicate query)
        if not admin:
            admin = User.query.filter_by(username='admin').first()
        
        # Create sample data only if admin exists
        if admin:
            # Create sample classes
            individual_class = IndividualClass.query.first()
            if not individual_class:
                individual_class = IndividualClass(
                    name='Python Basics',
                    description='Individual Python programming class',
                    teacher_id=admin.id
                )
                db.session.add(individual_class)
            
            group_class = GroupClass.query.first()
            if not group_class:
                group_class = GroupClass(
                    name='Web Development Group',
                    description='Group class for web development',
                    teacher_id=admin.id,
                    max_students=5
                )
                db.session.add(group_class)
            
            # Create sample courses with realistic data
            sample_courses = [
                {
                    'title': 'Introduction to Python',
                    'description': 'Learn Python programming fundamentals',
                    'short_description': 'Beginner-friendly Python course',
                    'price': 49.99,
                    'duration_weeks': 4,
                    'level': 'Beginner',
                    'category': 'Programming',
                    'image_url': 'https://example.com/python-course.jpg'
                },
                {
                    'title': 'Web Development with Flask',
                    'description': 'Build web applications using Python Flask',
                    'short_description': 'Hands-on Flask web development',
                    'price': 79.99,
                    'duration_weeks': 6,
                    'level': 'Intermediate',
                    'category': 'Web Development',
                    'image_url': 'https://example.com/flask-course.jpg'
                }
            ]
            
            for course_data in sample_courses:
                existing_course = Course.query.filter_by(title=course_data['title']).first()
                if not existing_course:
                    course = Course(
                        title=course_data['title'],
                        description=course_data['description'],
                        short_description=course_data['short_description'],
                        price=course_data['price'],
                        duration_weeks=course_data['duration_weeks'],
                        level=course_data['level'],
                        category=course_data['category'],
                        image_url=course_data['image_url'],
                        created_by=admin.id
                    )
                    db.session.add(course)
            
            # Create sample products
            sample_products = [
                
            ]
            
            for product_data in sample_products:
                existing_product = Product.query.filter_by(name=product_data['name']).first()
                if not existing_product:
                    product = Product(
                        name=product_data['name'],
                        description=product_data['description'],
                        short_description=product_data['short_description'],
                        price=product_data['price'],
                        product_type=product_data['product_type'],
                        category=product_data['category'],
                        brand=product_data['brand'],
                        sku=product_data['sku'],
                        stock_quantity=product_data['stock_quantity'],
                        image_url=product_data['image_url'],
                        created_by=admin.id
                    )
                    db.session.add(product)
        
        # Single commit at the end
        db.session.commit()
        print("Sample data created successfully")
        
    except Exception as e:
        print(f"Error creating sample data: {e}")
        db.session.rollback()


# Add these routes to your app.py file (copy and paste at the end of your routes)................................................................

@app.route('/admin/migrate-batch')
@login_required
def migrate_batch():
    """Migrate videos in small batches to avoid timeouts"""
    if not current_user.is_admin:
        return "Admin only", 403
    
    # Get all videos that need migration
    all_videos = CourseVideo.query.all()
    video_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
    
    local_videos = []
    for video in all_videos:
        if not video.video_url:  # No Cloudinary URL
            video_path = os.path.join(video_folder, video.video_filename)
            if os.path.exists(video_path):
                file_size = os.path.getsize(video_path) / (1024 * 1024)  # MB
                course = Course.query.get(video.course_id)
                local_videos.append({
                    'video': video,
                    'size': file_size,
                    'course_name': course.title if course else "Unknown Course"
                })
    
    if not local_videos:
        return '''
        <html><head><title>Migration Complete</title>
        <style>body { font-family: Arial; padding: 20px; text-align: center; }</style></head>
        <body>
            <h1>🎉 All Videos Already Migrated!</h1>
            <p>All your videos are safely stored on Cloudinary.</p>
            <p><a href="/test-player">🎬 Test Videos</a> | <a href="/admin/courses">← Back to Courses</a></p>
        </body></html>
        '''
    
    # Sort by size (smallest first for faster initial success)
    local_videos.sort(key=lambda x: x['size'])
    
    # Group into batches of 2-3 videos, keeping total under 60MB per batch
    batches = []
    current_batch = []
    current_size = 0
    
    for video_data in local_videos:
        if len(current_batch) >= 3 or (current_size + video_data['size']) > 60:
            if current_batch:
                batches.append(current_batch)
            current_batch = [video_data]
            current_size = video_data['size']
        else:
            current_batch.append(video_data)
            current_size += video_data['size']
    
    if current_batch:
        batches.append(current_batch)
    
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Batch Video Migration</title>
        <style>
            body { font-family: Arial; padding: 20px; background: #f8f9fa; }
            .container { max-width: 1000px; margin: 0 auto; }
            .header { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .batch { margin: 15px 0; padding: 15px; border: 1px solid #007bff; border-radius: 8px; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .video-item { margin: 5px 0; padding: 8px 12px; background: #f8f9fa; border-radius: 4px; border-left: 3px solid #007bff; }
            .migrate-btn { background: #28a745; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; font-weight: bold; }
            .migrate-btn:hover { background: #218838; }
            .migrate-btn:disabled { background: #6c757d; cursor: not-allowed; }
            .progress-container { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .progress-bar { width: 100%; background: #e9ecef; border-radius: 10px; padding: 3px; }
            .progress-fill { width: 0%; background: linear-gradient(90deg, #28a745, #20c997); height: 24px; border-radius: 8px; transition: width 0.5s ease; text-align: center; line-height: 24px; color: white; font-weight: bold; }
            .status-success { color: #28a745; font-weight: bold; }
            .status-error { color: #dc3545; font-weight: bold; }
            .status-progress { color: #007bff; font-weight: bold; }
            .controls { text-align: center; margin: 20px 0; }
            .start-btn { background: #007bff; color: white; padding: 15px 30px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; }
            .start-btn:hover { background: #0056b3; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 Smart Batch Video Migration</h1>
                <p>Migrating <strong>''' + str(len(local_videos)) + '''</strong> videos to Cloudinary in <strong>''' + str(len(batches)) + '''</strong> optimized batches.</p>
                <p><strong>Strategy:</strong> Upload 2-3 videos at a time (max 60MB per batch) to prevent timeouts.</p>
            </div>
            
            <div class="progress-container">
                <h3>📊 Migration Progress</h3>
                <div class="progress-bar">
                    <div class="progress-fill" id="progress-fill">0%</div>
                </div>
                <p id="progress-text" style="margin-top: 10px; text-align: center;">Ready to start migration</p>
            </div>
            
            <div class="controls">
                <button class="start-btn" onclick="startMigration()" id="start-btn">
                    🚀 Start Automatic Migration
                </button>
                <p><small>Migration will start automatically and process each batch sequentially</small></p>
            </div>
    '''
    
    for i, batch in enumerate(batches):
        batch_size = sum(v['size'] for v in batch)
        html += f'''
            <div class="batch" id="batch-{i}">
                <h3>📦 Batch {i+1} ({len(batch)} videos, {batch_size:.1f} MB)</h3>
        '''
        
        for video_data in batch:
            html += f'''
                <div class="video-item">
                    <strong>{video_data["video"].title}</strong><br>
                    <small>Course: {video_data["course_name"]} • Size: {video_data["size"]:.1f} MB</small>
                </div>
            '''
        
        html += f'''
                <div style="margin-top: 10px;">
                    <button class="migrate-btn" onclick="migrateBatch({i})" id="btn-{i}" disabled>
                        ⏳ Waiting...
                    </button>
                    <span id="status-{i}" style="margin-left: 15px;"></span>
                </div>
            </div>
        '''
    
    html += '''
        </div>
        
        <script>
        let completedBatches = 0;
        const totalBatches = ''' + str(len(batches)) + ''';
        let migrationStarted = false;
        
        function startMigration() {
            if (migrationStarted) return;
            migrationStarted = true;
            
            document.getElementById('start-btn').disabled = true;
            document.getElementById('start-btn').textContent = '🔄 Migration in Progress...';
            document.getElementById('progress-text').textContent = 'Starting migration...';
            
            // Enable first batch button
            document.getElementById('btn-0').disabled = false;
            document.getElementById('btn-0').textContent = '🚀 Migrate Batch 1';
            
            // Start with first batch
            setTimeout(() => migrateBatch(0), 500);
        }
        
        async function migrateBatch(batchIndex) {
            const btn = document.getElementById(`btn-${batchIndex}`);
            const status = document.getElementById(`status-${batchIndex}`);
            
            btn.disabled = true;
            btn.textContent = '⏳ Uploading...';
            btn.style.background = '#ffc107';
            status.innerHTML = '<span class="status-progress">📤 Uploading to Cloudinary...</span>';
            
            try {
                const response = await fetch(`/admin/process-batch/${batchIndex}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                });
                
                if (response.ok) {
                    const result = await response.text();
                    status.innerHTML = '<span class="status-success">✅ ' + result + '</span>';
                    btn.textContent = '✅ Completed';
                    btn.style.background = '#28a745';
                    
                    completedBatches++;
                    updateProgress();
                    
                    // Enable and auto-start next batch after 3 seconds
                    if (batchIndex + 1 < totalBatches) {
                        const nextBtn = document.getElementById(`btn-${batchIndex + 1}`);
                        nextBtn.disabled = false;
                        nextBtn.textContent = `🚀 Migrate Batch ${batchIndex + 2}`;
                        
                        setTimeout(() => {
                            migrateBatch(batchIndex + 1);
                        }, 3000);
                    }
                    
                } else {
                    throw new Error(`HTTP ${response.status}`);
                }
            } catch (error) {
                console.error('Migration error:', error);
                status.innerHTML = '<span class="status-error">❌ Failed - <a href="#" onclick="migrateBatch(' + batchIndex + ')">Retry</a></span>';
                btn.disabled = false;
                btn.textContent = '🔄 Retry Batch ' + (batchIndex + 1);
                btn.style.background = '#dc3545';
            }
        }
        
        function updateProgress() {
            const percentage = Math.round((completedBatches / totalBatches) * 100);
            const progressFill = document.getElementById('progress-fill');
            progressFill.style.width = percentage + '%';
            progressFill.textContent = percentage + '%';
            
            document.getElementById('progress-text').innerHTML = 
                `<strong>${completedBatches} of ${totalBatches} batches completed</strong>`;
            
            if (completedBatches === totalBatches) {
                document.getElementById('progress-text').innerHTML = 
                    '<strong style="color: #28a745;">🎉 All videos migrated successfully!</strong><br>' +
                    '<a href="/test-player" style="margin: 0 10px;">🎬 Test Videos</a> | ' +
                    '<a href="/admin/courses">← Back to Courses</a>';
                    
                // Confetti effect (optional)
                document.body.style.background = 'linear-gradient(45deg, #e8f5e8, #f0f8ff)';
            }
        }
        </script>
        
        <div style="text-align: center; margin-top: 30px; padding: 20px;">
            <p><a href="/admin/migrate-existing-videos">← Back to Migration Options</a></p>
        </div>
        
    </body>
    </html>
    '''
    
    return html

@app.route('/admin/process-batch/<int:batch_index>', methods=['POST'])
@login_required
def process_batch(batch_index):
    """Process a single batch of videos"""
    if not current_user.is_admin:
        return "Admin only", 403
    
    try:
        # Get videos for this batch (same logic as migrate_batch)
        all_videos = CourseVideo.query.all()
        video_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
        
        local_videos = []
        for video in all_videos:
            if not video.video_url:
                video_path = os.path.join(video_folder, video.video_filename)
                if os.path.exists(video_path):
                    file_size = os.path.getsize(video_path) / (1024 * 1024)
                    local_videos.append({
                        'video': video,
                        'size': file_size
                    })
        
        local_videos.sort(key=lambda x: x['size'])
        
        # Group into batches (same logic)
        batches = []
        current_batch = []
        current_size = 0
        
        for video_data in local_videos:
            if len(current_batch) >= 3 or (current_size + video_data['size']) > 60:
                if current_batch:
                    batches.append(current_batch)
                current_batch = [video_data]
                current_size = video_data['size']
            else:
                current_batch.append(video_data)
                current_size += video_data['size']
        
        if current_batch:
            batches.append(current_batch)
        
        if batch_index >= len(batches):
            return "Invalid batch index", 400
        
        batch = batches[batch_index]
        migrated_count = 0
        errors = []
        
        for video_data in batch:
            try:
                video = video_data['video']
                video_path = os.path.join(video_folder, video.video_filename)
                
                print(f"🚀 Migrating batch {batch_index + 1}: {video.title}")
                
                # Upload to Cloudinary
                with open(video_path, 'rb') as file:
                    upload_result = upload_video_to_cloudinary(file, video.course_id, video.id)
                
                if upload_result:
                    # Update database
                    video.video_url = upload_result['url']
                    migrated_count += 1
                    print(f"✅ Success: {video.title}")
                else:
                    errors.append(video.title)
                    print(f"❌ Failed: {video.title}")
                    
            except Exception as e:
                errors.append(f"{video.title}: {str(e)}")
                print(f"❌ Error: {video.title} - {str(e)}")
        
        # Commit all successful migrations
        if migrated_count > 0:
            db.session.commit()
        
        if errors:
            return f"{migrated_count} migrated, {len(errors)} failed"
        else:
            return f"{migrated_count} videos migrated successfully"
            
    except Exception as e:
        print(f"❌ Batch processing error: {e}")
        return f"Batch processing failed: {str(e)}", 500

@app.route('/admin/migration-status')
@login_required
def migration_status():
    """Get current migration status as JSON"""
    if not current_user.is_admin:
        return {'error': 'Access denied'}, 403
    
    try:
        all_videos = CourseVideo.query.all()
        cloudinary_count = sum(1 for v in all_videos if v.video_url)
        local_count = len(all_videos) - cloudinary_count
        
        return {
            'total': len(all_videos),
            'cloudinary': cloudinary_count,
            'local': local_count,
            'percentage': round((cloudinary_count / len(all_videos)) * 100) if all_videos else 0
        }
    except Exception as e:
        return {'error': str(e)}, 500

# ========================================
# DATABASE INITIALIZATION FUNCTION
# ========================================

def init_database():
    """Initialize database tables and sample data"""
    try:
        print("Creating database tables...")
        db.create_all()
        print("Database tables created successfully")
        
        print("Creating sample data...")
        create_sample_data()
        print("Sample data created successfully")
        
        return True
    except Exception as e:
        print(f"Error initializing database: {e}")
        return False

# ========================================
# LAZY DATABASE INITIALIZATION
# ========================================

_db_initialized = False

def ensure_db_initialized():
    """Ensure database is initialized only once"""
    global _db_initialized
    if not _db_initialized:
        try:
            with app.app_context():
                init_database()
                _db_initialized = True
                print("✅ Database initialized successfully")
        except Exception as e:
            print(f"❌ Database initialization failed: {e}")

# ========================================
# ROUTES FOR DATABASE MANAGEMENT
# ========================================

@app.route('/init-db')
@login_required
def manual_init_db():
    """Manual database initialization endpoint - ADMIN ONLY"""
    if not current_user.is_admin:
        return "❌ Access denied: Admin privileges required", 403
    
    try:
        ensure_db_initialized()
        return "✅ Database initialized successfully!", 200
    except Exception as e:
        return f"❌ Error: {str(e)}", 500

@app.cli.command("init-db")
def init_db_command():
    """Initialize the database (CLI command)"""
    ensure_db_initialized()
    print("Database initialized")

@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        # Ensure database is initialized
        ensure_db_initialized()
        
        # Test database connection
        with app.app_context():
            db.session.execute(db.text('SELECT 1'))
            user_count = User.query.count()
            courses_count = Course.query.count()
            products_count = Product.query.count()
        
        return {
            "status": "healthy", 
            "database": "connected",
            "users": user_count,
            "courses": courses_count,
            "products": products_count,
            "timestamp": datetime.utcnow().isoformat()
        }, 200
    except Exception as e:
        return {
            "status": "error", 
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }, 500

# ========================================
# INITIALIZE DATABASE AT STARTUP
# ========================================

# Initialize database when app starts (for production)
with app.app_context():
    ensure_db_initialized()

# ========================================
# CREATE WSGI APPLICATION
# ========================================

# This is the WSGI application that Gunicorn will use
application = app

# ========================================
# LOCAL DEVELOPMENT ONLY
# ========================================

if __name__ == '__main__':
    # Only for local development
    with app.app_context():
        init_database()
    
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
