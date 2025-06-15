# app.py - Fixed Learning Management System
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, Response
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
import cloudinary
import cloudinary.uploader
import cloudinary.api
from io import StringIO

# ========================================
# APPLICATION CONFIGURATION
# ========================================

app = Flask(__name__)

# Configuration settings
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///learning_management.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File upload configuration
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

# AI Assistant Configuration
app.config['DEEPINFRA_API_KEY'] = os.environ.get('DEEPINFRA_API_KEY', "JJT2oAUiJNKaEzkGAcP0PpzZ1hBoExqz")
app.config['DEEPINFRA_API_URL'] = "https://api.deepinfra.com/v1/openai/chat/completions"

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'worldvlog13@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'mfrp osrt pwki lmmx')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'worldvlog13@gmail.com')

# WhatsApp configuration
app.config['WHATSAPP_WEB_URL'] = 'https://web.whatsapp.com/send?phone=+919319038312'

# Cloudinary Configuration
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', 'dfizb64hx'),
    api_key=os.environ.get('CLOUDINARY_API_KEY', '959475453929561'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET', 'bLYgaJv1YnTToGNN-xamKKC-9Ac')
)

# Create upload directories
def create_upload_directories():
    """Create necessary upload directories"""
    try:
        os.makedirs(app.config.get('UPLOAD_FOLDER', 'static/uploads'), exist_ok=True)
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'videos'), exist_ok=True)
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'materials'), exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create upload directories: {e}")

create_upload_directories()

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ========================================
# DATABASE MODELS
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
        """Hash and set user password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if provided password matches user's password"""
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
                             lazy='select', back_populates='group_classes')

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
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    creator = db.relationship('User', foreign_keys=[created_by], lazy='select')
    
    def get_enrolled_count(self):
        """Get number of students enrolled in this course"""
        return Purchase.query.filter_by(course_id=self.id, status='completed').count()
    
    def get_video_count(self):
        """Get number of videos in this course"""
        return CourseVideo.query.filter_by(course_id=self.id).count()
    
    def get_total_duration(self):
        """Calculate total course duration from videos"""
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
    video_url = db.Column(db.String(500))  # Cloudinary URL
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
        """Get file size in MB"""
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
        """Get number of completed sales for this product"""
        return ProductOrder.query.filter_by(product_id=self.id, status='completed').count()
    
    def is_in_stock(self):
        """Check if product is in stock"""
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
        """Calculate total price for this cart item"""
        return self.product.price * self.quantity

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
        """Get the name of the associated class"""
        if self.class_type == 'individual':
            class_obj = IndividualClass.query.get(self.actual_class_id)
        else:
            class_obj = GroupClass.query.get(self.actual_class_id)
        return class_obj.name if class_obj else "Unknown Class"

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

# Add back_populates relationships to User model
User.individual_classes = db.relationship('IndividualClass', 
                                         secondary=individual_class_students,
                                         back_populates='students', lazy='select')
User.group_classes = db.relationship('GroupClass', 
                                    secondary=group_class_students,
                                    back_populates='students', lazy='select')

@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login"""
    return User.query.get(int(user_id))

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

def upload_video_to_cloudinary(video_file, course_id, video_index):
    """Upload video to Cloudinary and return the URL"""
    try:
        public_id = f"course_{course_id}_video_{video_index}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        result = cloudinary.uploader.upload(
            video_file,
            resource_type="video",
            public_id=public_id,
            folder="course_videos",
            overwrite=True,
            format="mp4"
        )
        
        return {
            'url': result['secure_url'],
            'public_id': result['public_id'],
            'duration': result.get('duration', 0),
            'size': result.get('bytes', 0)
        }
    except Exception as e:
        print(f"❌ Cloudinary upload error: {e}")
        return None

def send_bulk_email(recipients, subject, message):
    """Send bulk emails to recipients"""
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
    """Generate WhatsApp links for bulk messaging"""
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
# AUTHENTICATION ROUTES
# ========================================

@app.route('/')
def index():
    """Main landing page"""
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
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
    """User registration"""
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
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/about')
def about_us():
    """About us page"""
    context = {
        'page_title': 'About BuXin Future Academy',
        'meta_description': 'Learn about BuXin Future Academy - pioneering robotics, AI, and electric vehicle technology in Africa.'
    }
    return render_template('about_us.html', **context)

# ========================================
# ADMIN DASHBOARD ROUTES
# ========================================

@app.route('/admin/dashboard', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    """Admin dashboard with learning material sharing"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        class_id = request.form.get('class_id')
        content = request.form.get('message', '').strip()

        if not class_id or not content:
            flash("Both class and content are required.", "danger")
        else:
            class_type, actual_class_id = class_id.split('_')
            
            material = LearningMaterial(
                class_id=class_id,
                class_type=class_type,
                actual_class_id=int(actual_class_id),
                content=content,
                created_by=current_user.id
            )
            db.session.add(material)
            db.session.commit()
            flash("Learning material shared!", "success")
            return redirect(url_for('admin_dashboard'))

    students = User.query.filter_by(is_student=True).all()
    materials = LearningMaterial.query.order_by(LearningMaterial.id.desc()).limit(20).all()
    individual_classes = IndividualClass.query.all()
    group_classes = GroupClass.query.all()

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
        materials=materials,
        individual_classes=individual_classes,
        group_classes=group_classes,
        class_options=class_options
    )

@app.route('/admin/create_class', methods=['GET', 'POST'])
@login_required
def create_class():
    """Create new class (individual or group)"""
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

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    """Student dashboard with learning materials"""
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    individual_class_ids = [f'individual_{c.id}' for c in current_user.individual_classes]
    group_class_ids = [f'group_{c.id}' for c in current_user.group_classes]
    all_class_ids = individual_class_ids + group_class_ids
    
    materials = LearningMaterial.query.filter(
        LearningMaterial.class_id.in_(all_class_ids)
    ).order_by(LearningMaterial.created_at.desc()).all()
    
    return render_template(
        'student_dashboard.html',
        materials=materials,
        individual_classes=current_user.individual_classes,
        group_classes=current_user.group_classes
    )

@app.route('/ai_assistant', methods=['GET', 'POST'])
@login_required
def ai_assistant():
    """AI-powered learning assistant"""
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

@app.route('/store')
def store():
    """Course store with filtering and search"""
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
    """Detailed course view"""
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

@app.route('/admin/courses')
@login_required
def admin_courses():
    """Display all courses for admin"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    courses = Course.query.order_by(Course.created_at.desc()).all()
    return render_template('admin_courses.html', courses=courses)

@app.route('/admin/create_course', methods=['GET', 'POST'])
@login_required
def create_course():
    """Create new course with videos and materials"""
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
            
            # Handle video uploads to Cloudinary
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
                    
                    # Upload to Cloudinary
                    upload_result = upload_video_to_cloudinary(video_file, course.id, i+1)
                    
                    if upload_result:
                        # Create fallback filename for compatibility
                        fallback_filename = f"cloudinary_{upload_result['public_id']}.mp4"
                        
                        course_video = CourseVideo(
                            course_id=course.id,
                            title=video_titles[i] if i < len(video_titles) else f"Lesson {i+1}",
                            description=video_descriptions[i] if i < len(video_descriptions) else "",
                            video_filename=fallback_filename,
                            video_url=upload_result['url'],
                            duration=video_durations[i] if i < len(video_durations) and video_durations[i] else None,
                            order_index=int(video_orders[i]) if i < len(video_orders) else i+1
                        )
                        db.session.add(course_video)
                    else:
                        flash(f'Failed to upload video: {video_file.filename}', 'danger')
            
            # Handle course materials (local storage)
            material_files = request.files.getlist('course_materials')
            materials_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'materials')
            os.makedirs(materials_folder, exist_ok=True)
            
            for material_file in material_files:
                if material_file and material_file.filename and allowed_file(material_file.filename, 'material'):
                    material_file.seek(0, 2)
                    file_size = material_file.tell()
                    material_file.seek(0)
                    
                    if file_size > 10 * 1024 * 1024:  # 10MB limit
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

# ========================================
# DATABASE INITIALIZATION
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
            db.session.commit()
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

        db.session.commit()

        # Create sample classes
        admin = User.query.filter_by(username='admin').first()
        if admin:
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
        
        # Create sample courses
        sample_courses = [
            {
                'title': 'Complete Python Bootcamp',
                'description': 'Learn Python programming from scratch with hands-on projects and real-world applications.',
                'short_description': 'Master Python programming with practical projects',
                'price': 99.99,
                'duration_weeks': 8,
                'level': 'Beginner',
                'category': 'Programming',
                'image_url': 'https://images.unsplash.com/photo-1526379095098-d400fd0bf935?w=400'
            },
            {
                'title': 'Advanced JavaScript & React',
                'description': 'Build modern web applications with JavaScript ES6+ and React framework.',
                'short_description': 'Create dynamic web apps with JavaScript and React',
                'price': 149.99,
                'duration_weeks': 12,
                'level': 'Intermediate',
                'category': 'Web Development',
                'image_url': 'https://images.unsplash.com/photo-1633356122544-f134324a6cee?w=400'
            },
            {
                'title': 'Data Science with Python',
                'description': 'Analyze data, create visualizations, and build machine learning models using Python.',
                'short_description': 'Master data analysis and machine learning',
                'price': 199.99,
                'duration_weeks': 16,
                'level': 'Advanced',
                'category': 'Data Science',
                'image_url': 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=400'
            }
        ]
        
        # Create sample products
        sample_products = [
            {
                'name': 'Programming Fundamentals eBook',
                'description': 'Comprehensive digital guide covering programming basics across multiple languages.',
                'short_description': 'Essential programming guide for beginners',
                'price': 29.99,
                'product_type': 'Digital',
                'category': 'Books',
                'brand': 'TechBooks',
                'sku': 'EBOOK-PROG-001',
                'stock_quantity': 0,
                'image_url': 'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=400'
            }
        ]
        
        # Only create sample data if admin exists
        if admin:
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
        
        db.session.commit()
        print("Sample data created successfully")
        
    except Exception as e:
        print(f"Error creating sample data: {e}")
        db.session.rollback()

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

# Global flag to ensure database is initialized only once
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

@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        ensure_db_initialized()
        
        with app.app_context():
            db.session.execute(db.text('SELECT 1'))
            user_count = User.query.count()
        
        return {
            "status": "healthy", 
            "database": "connected",
            "users": user_count,
            "timestamp": datetime.utcnow().isoformat()
        }, 200
    except Exception as e:
        return {
            "status": "error", 
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }, 500

# ========================================
# ERROR HANDLERS
# ========================================

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return "Page not found", 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    db.session.rollback()
    return "Internal server error", 500

# ========================================
# APPLICATION STARTUP
# ========================================

# Initialize database on startup
ensure_db_initialized()

# Create WSGI application for deployment
application = app

# ========================================
# MAIN EXECUTION
# ========================================

if __name__ == '__main__':
    # Only for local development
    with app.app_context():
        init_database()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
