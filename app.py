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
        if self.class_type == 'individual':
            class_obj = IndividualClass.query.get(self.actual_class_id)
        else:
            class_obj = GroupClass.query.get(self.actual_class_id)
        return class_obj.name if class_obj else "Unknown Class"

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

@app.route('/admin/update_enrollment_status/<int:enrollment_id>', methods=['POST'])
@login_required
def update_enrollment_status(enrollment_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    enrollment = ClassEnrollment.query.get_or_404(enrollment_id)
    new_status = request.form.get('status')
    
    if new_status in ['pending', 'completed', 'failed']:
        enrollment.status = new_status
        db.session.commit()
        
        if new_status == 'completed':
            if enrollment.class_type == 'individual':
                class_obj = IndividualClass.query.get(enrollment.class_id)
            else:
                class_obj = GroupClass.query.get(enrollment.class_id)
            
            if current_user not in class_obj.students:
                class_obj.students.append(current_user)
                db.session.commit()
            
            flash('Enrollment approved! Student has been added to the class.', 'success')
        else:
            flash(f'Enrollment status updated to {new_status}.', 'success')
    else:
        flash('Invalid status!', 'danger')
    
    return redirect(url_for('view_enrollment', enrollment_id=enrollment_id))

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
            
            # Handle video uploads
            video_files = request.files.getlist('video_files')
            video_titles = request.form.getlist('video_titles')
            video_descriptions = request.form.getlist('video_descriptions')
            video_orders = request.form.getlist('video_orders')
            video_durations = request.form.getlist('video_durations')
            
            video_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
            os.makedirs(video_folder, exist_ok=True)
            
            for i, video_file in enumerate(video_files):
                if video_file and video_file.filename and allowed_file(video_file.filename, 'video'):
                    video_file.seek(0, 2)
                    file_size = video_file.tell()
                    video_file.seek(0)
                    
                    if file_size > 500 * 1024 * 1024:
                        flash(f'Video file {video_file.filename} is too large. Maximum size is 500MB.', 'warning')
                        continue
                    
                    filename = secure_filename(video_file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                    unique_filename = f"{timestamp}{course.id}_{i+1}_{filename}"
                    
                    video_path = os.path.join(video_folder, unique_filename)
                    video_file.save(video_path)
                    
                    course_video = CourseVideo(
                        course_id=course.id,
                        title=video_titles[i] if i < len(video_titles) else f"Lesson {i+1}",
                        description=video_descriptions[i] if i < len(video_descriptions) else "",
                        video_filename=unique_filename,
                        duration=video_durations[i] if i < len(video_durations) and video_durations[i] else None,
                        order_index=int(video_orders[i]) if i < len(video_orders) else i+1
                    )
                    
                    db.session.add(course_video)
            
            # Handle course materials
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
        course.title = request.form['title']
        course.description = request.form['description']
        course.short_description = request.form.get('short_description', '')
        course.price = float(request.form['price'])
        course.duration_weeks = int(request.form.get('duration_weeks', 4))
        course.level = request.form['level']
        course.category = request.form['category']
        course.image_url = request.form.get('image_url', '')
        course.is_active = 'is_active' in request.form
        
        db.session.commit()
        
        flash('Course updated successfully!', 'success')
        return redirect(url_for('admin_courses'))
    
    return render_template('edit_course.html', course=course)


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
                # Create SKU from product name
                base_sku = name.upper().replace(' ', '-').replace('&', 'AND')
                # Remove special characters and limit length
                base_sku = ''.join(c for c in base_sku if c.isalnum() or c == '-')[:10]
                
                # Check if SKU exists and make it unique
                counter = 1
                sku = f"{base_sku}-{counter:03d}"
                while Product.query.filter_by(sku=sku).first():
                    counter += 1
                    sku = f"{base_sku}-{counter:03d}"
            else:
                # Check if provided SKU already exists
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
            
            # Save to database
            db.session.add(product)
            db.session.commit()
            
            # Success message
            flash(f'Product "{product.name}" created successfully!', 'success')
            
            # Redirect to products list or stay on create page
            if request.form.get('action') == 'save_and_new':
                return redirect(url_for('create_product'))
            else:
                return redirect(url_for('admin_products'))
                
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating product: {str(e)}', 'danger')
            print(f"Error creating product: {e}")
            return render_template('create_product.html')
    
    # GET request - show the form
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

@app.route('/learn/course/<int:course_id>')
@login_required
def learn_course(course_id):
    course = Course.query.get_or_404(course_id)
    
    if not current_user.is_admin:
        purchase = Purchase.query.filter_by(
            user_id=current_user.id,
            course_id=course_id,
            status='completed'
        ).first()
        
        if not purchase:
            flash('You need to purchase this course to access the learning content.', 'warning')
            return redirect(url_for('course_detail', course_id=course_id))
    
    videos = CourseVideo.query.filter_by(course_id=course_id).order_by(CourseVideo.order_index).all()
    materials = CourseMaterial.query.filter_by(course_id=course_id).all()
    
    return render_template('learn_course.html', 
                         course=course, 
                         videos=videos,
                         materials=materials)

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
    
    payment_method = request.form.get('payment_method')
    full_name = request.form.get('full_name')
    phone = request.form.get('phone')
    email = request.form.get('email')
    address = request.form.get('address')
    
    payment_proof = request.files.get('payment_proof')
    proof_filename = None
    if payment_proof and allowed_file(payment_proof.filename):
        filename = secure_filename(payment_proof.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        payment_proof.save(filepath)
        proof_filename = filename
    
    valid_methods = ['bank_transfer', 'wave', 'western_union', 'moneygram', 'ria']
    if payment_method not in valid_methods:
        flash('Please select a valid payment method', 'danger')
        return redirect(url_for('checkout'))
    
    transaction_id = str(uuid.uuid4())[:8]
    
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
            payment_proof=proof_filename
        )
        db.session.add(purchase)
        db.session.delete(cart_item)
    
    db.session.commit()
    
    flash('Order submitted successfully! Our team will verify your payment and you will receive access to your courses once confirmed.', 'success')
    return redirect(url_for('my_course_orders'))

@app.route('/process_product_payment', methods=['POST'])
@login_required
def process_product_payment():
    cart_items = ProductCartItem.query.filter_by(user_id=current_user.id).all()
    
    if not cart_items:
        flash('Your cart is empty!', 'warning')
        return redirect(url_for('products'))

    payment_method = request.form.get('payment_method')
    full_name = request.form.get('full_name')
    phone = request.form.get('phone')
    email = request.form.get('email')
    address = request.form.get('address')
    
    payment_proof = request.files.get('payment_proof')
    proof_filename = None
    if payment_proof and allowed_file(payment_proof.filename):
        filename = secure_filename(payment_proof.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        payment_proof.save(filepath)
        proof_filename = filename
    
    valid_methods = ['bank_transfer', 'wave', 'western_union', 'moneygram', 'ria']
    if payment_method not in valid_methods:
        flash('Please select a valid payment method', 'danger')
        return redirect(url_for('product_checkout'))

    transaction_id = str(uuid.uuid4())[:8]
    
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
            payment_proof=proof_filename
        )
        db.session.add(order)
        db.session.delete(cart_item)
    
    db.session.commit()
    
    flash('Order placed successfully! Our team will verify your payment and contact you shortly.', 'success')
    return redirect(url_for('my_orders'))

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

@app.route('/payment_proof/<filename>')
@login_required
def payment_proof(filename):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    else:
        flash(f'Payment proof file "{filename}" not found. This is a demo order.', 'warning')
        return redirect(url_for('admin_product_orders'))

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
        
        # Handle payment proof upload
        payment_proof = request.files.get('payment_proof')
        proof_filename = None
        
        if payment_proof and payment_proof.filename:
            if allowed_file(payment_proof.filename):
                try:
                    # Check file size (max 5MB)
                    payment_proof.seek(0, 2)  # Seek to end
                    file_size = payment_proof.tell()
                    payment_proof.seek(0)  # Seek back to beginning
                    
                    if file_size > 5 * 1024 * 1024:  # 5MB limit
                        flash('Payment proof file is too large. Maximum size is 5MB.', 'danger')
                        return redirect(url_for('enroll_class', class_type=class_type, class_id=class_id))
                    
                    # Save the file
                    filename = secure_filename(payment_proof.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                    unique_filename = f"{timestamp}enrollment_{class_type}_{class_id}_{current_user.id}_{filename}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    payment_proof.save(filepath)
                    proof_filename = unique_filename
                    
                except Exception as e:
                    flash(f'Error uploading payment proof: {str(e)}', 'danger')
                    return redirect(url_for('enroll_class', class_type=class_type, class_id=class_id))
            else:
                flash('Invalid file type for payment proof. Please upload an image or PDF file.', 'danger')
                return redirect(url_for('enroll_class', class_type=class_type, class_id=class_id))
        else:
            flash('Payment proof is required!', 'danger')
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
                payment_proof=proof_filename
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

# ========================================
# SAMPLE DATA CREATION
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
            },
            {
                'title': 'Digital Marketing Fundamentals',
                'description': 'Learn SEO, social media marketing, content strategy, and analytics.',
                'short_description': 'Complete guide to digital marketing',
                'price': 79.99,
                'duration_weeks': 6,
                'level': 'Beginner',
                'category': 'Marketing',
                'image_url': 'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=400'
            },
            {
                'title': 'UI/UX Design Masterclass',
                'description': 'Design beautiful and user-friendly interfaces using modern design principles.',
                'short_description': 'Create stunning user interfaces and experiences',
                'price': 129.99,
                'duration_weeks': 10,
                'level': 'Intermediate',
                'category': 'Design',
                'image_url': 'https://images.unsplash.com/photo-1558655146-9f40138edfeb?w=400'
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
            },
            {
                'name': 'Wireless Bluetooth Headphones',
                'description': 'High-quality wireless headphones perfect for online learning and coding sessions.',
                'short_description': 'Premium wireless headphones for students',
                'price': 89.99,
                'product_type': 'Physical',
                'category': 'Electronics',
                'brand': 'AudioTech',
                'sku': 'HEADPHONE-BT-001',
                'stock_quantity': 50,
                'image_url': 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400'
            },
            {
                'name': 'Ergonomic Laptop Stand',
                'description': 'Adjustable aluminum laptop stand designed for comfortable studying and working.',
                'short_description': 'Improve your workspace ergonomics',
                'price': 49.99,
                'product_type': 'Physical',
                'category': 'Accessories',
                'brand': 'WorkSpace',
                'sku': 'STAND-LAP-001',
                'stock_quantity': 30,
                'image_url': 'https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=400'
            }
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
        
        db.session.commit()
        print("Sample data created successfully")
        
    except Exception as e:
        print(f"Error creating sample data: {e}")
        db.session.rollback()


@app.route('/api/notify-course/<int:course_id>', methods=['POST'])
def notify_course(course_id):
    # Save user interest in course
    # Send email when course becomes available
    pass

@app.route('/api/subscribe', methods=['POST'])
def subscribe_updates():
    # Save email for course updates
    pass



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
def upload_video_to_cloudinary(video_file, course_id, video_index):
    """Upload video to Cloudinary and return the URL"""
    try:
        # Create a unique public_id for the video
        public_id = f"course_{course_id}_video_{video_index}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        print(f"🚀 Uploading to Cloudinary: {public_id}")
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            video_file,
            resource_type="video",
            public_id=public_id,
            folder="course_videos",
            overwrite=True,
            format="mp4"  # Convert to MP4 automatically
        )
        
        print(f"✅ Cloudinary upload successful: {result['secure_url']}")
        
        return {
            'url': result['secure_url'],
            'public_id': result['public_id'],
            'duration': result.get('duration', 0),
            'size': result.get('bytes', 0)
        }
    except Exception as e:
        print(f"❌ Cloudinary upload error: {e}")
        return None

# 5. IMPORTANT: Update your CourseVideo model to support both old and new systems
# Find your CourseVideo class and make sure video_url is nullable:
# (Your model already looks correct, but double-check that video_url can be None)

# 6. REPLACE your course_video route 
# Find @app.route('/course_video/<filename>') and replace the ENTIRE function with:

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

# 7. UPDATE your create_course route to use Cloudinary for NEW videos
# Find the video upload section in your create_course route and replace it with:

# IN YOUR create_course ROUTE, REPLACE THIS SECTION:
# Handle video uploads
video_files = request.files.getlist('video_files')
video_titles = request.form.getlist('video_titles')
video_descriptions = request.form.getlist('video_descriptions')
video_orders = request.form.getlist('video_orders')
video_durations = request.form.getlist('video_durations')

video_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
os.makedirs(video_folder, exist_ok=True)

for i, video_file in enumerate(video_files):
    if video_file and video_file.filename and allowed_file(video_file.filename, 'video'):
        video_file.seek(0, 2)
        file_size = video_file.tell()
        video_file.seek(0)
        
        if file_size > 500 * 1024 * 1024:
            flash(f'Video file {video_file.filename} is too large. Maximum size is 500MB.', 'warning')
            continue
        
        filename = secure_filename(video_file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        unique_filename = f"{timestamp}{course.id}_{i+1}_{filename}"
        
        video_path = os.path.join(video_folder, unique_filename)
        video_file.save(video_path)
        
        course_video = CourseVideo(
            course_id=course.id,
            title=video_titles[i] if i < len(video_titles) else f"Lesson {i+1}",
            description=video_descriptions[i] if i < len(video_descriptions) else "",
            video_filename=unique_filename,
            duration=video_durations[i] if i < len(video_durations) and video_durations[i] else None,
            order_index=int(video_orders[i]) if i < len(video_orders) else i+1
        )
        
        db.session.add(course_video)

# WITH THIS CLOUDINARY VERSION:
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

# 8. ADD THESE TEST AND MIGRATION ROUTES (add at the end of your routes)
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

@app.route('/admin/cloudinary-test')
@login_required
def cloudinary_test():
    """Test Cloudinary connection"""
    if not current_user.is_admin:
        return "Admin only", 403
    
    try:
        # Test Cloudinary connection
        result = cloudinary.api.ping()
        
        html = '<h1>☁️ Cloudinary Connection Test</h1>'
        html += '<style>body { font-family: Arial; padding: 20px; }</style>'
        html += f'<p><strong>✅ Connection successful!</strong></p>'
        html += f'<p><strong>Cloud Name:</strong> {cloudinary.config().cloud_name}</p>'
        html += f'<p><strong>API Key:</strong> {cloudinary.config().api_key}</p>'
        html += f'<p><strong>Status:</strong> {result.get("status", "OK")}</p>'
        
        # Test upload quota
        try:
            usage = cloudinary.api.usage()
            html += f'<h3>📊 Usage Statistics:</h3>'
            html += f'<p><strong>Storage used:</strong> {usage.get("storage", {}).get("usage", 0) / 1024 / 1024:.1f} MB</p>'
            html += f'<p><strong>Bandwidth used this month:</strong> {usage.get("bandwidth", {}).get("usage", 0) / 1024 / 1024:.1f} MB</p>'
        except:
            html += '<p><em>Could not fetch usage statistics</em></p>'
        
        html += '<p><a href="/admin/migrate-existing-videos">🚀 Start Migration</a></p>'
        
        return html
        
    except Exception as e:
        return f'''
        <h1>❌ Cloudinary Connection Failed</h1>
        <style>body {{ font-family: Arial; padding: 20px; }}</style>
        <p><strong>Error:</strong> {str(e)}</p>
        <p><strong>Check:</strong></p>
        <ul>
            <li>Environment variables are set correctly</li>
            <li>Cloud name, API key, and API secret are correct</li>
            <li>Internet connection is working</li>
        </ul>
        <p><a href="/admin/courses">← Back to Courses</a></p>
        '''

# ========================================
# APPLICATION STARTUP
# ========================================

# Initialize database when the module loads (with proper context)
try:
    with app.app_context():
        db.create_all()
        create_sample_data()
        print("✅ Database initialized successfully")
except Exception as e:
    print(f"❌ Error initializing database: {e}")

# Application instance for production
application = app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    application.run(host='0.0.0.0', port=port, debug=False)
