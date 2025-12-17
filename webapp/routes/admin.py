from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user, logout_user

from ..extensions import db
from ..models import (
    User,
    Purchase,
    ClassEnrollment,
    StudentProject,
    RoboticsProjectSubmission,
    IndividualClass,
    GroupClass,
    HomeGallery,
    StudentVictory,
    ClassPricing,
    Attendance,
    SchoolStudent,
    FamilyMember,
    LearningMaterial,
    School,
    RegisteredSchoolStudent,
)

bp = Blueprint('admin', __name__)


@bp.route('/admin/setup-school-tables')
def setup_school_tables():
    """Create school and registered_school_student tables - accessible without login for initial setup"""
    from sqlalchemy import text
    messages = []
    
    try:
        # First create all tables
        db.create_all()
        messages.append("Tables created")
        
        # Check if school table exists
        try:
            result = db.session.execute(text("""
                SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='school')
            """))
            if result.fetchone()[0]:
                messages.append("school table exists")
            else:
                messages.append("school table will be created on next db.create_all()")
        except Exception as e:
            messages.append(f"school table check error: {str(e)}")
        
        # Check if school_student_registered table exists
        try:
            result = db.session.execute(text("""
                SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='school_student_registered')
            """))
            if result.fetchone()[0]:
                messages.append("school_student_registered table exists")
            else:
                messages.append("school_student_registered table will be created on next db.create_all()")
        except Exception as e:
            messages.append(f"school_student_registered table check error: {str(e)}")
        
        # Check if user table has new columns
        try:
            result = db.session.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='user' AND column_name='school_id'
            """))
            if not result.fetchone():
                db.session.execute(text("ALTER TABLE \"user\" ADD COLUMN school_id INTEGER"))
                db.session.execute(text("ALTER TABLE \"user\" ADD COLUMN student_system_id VARCHAR(20)"))
                db.session.execute(text("ALTER TABLE \"user\" ADD COLUMN is_school_admin BOOLEAN DEFAULT FALSE"))
                db.session.execute(text("ALTER TABLE \"user\" ADD COLUMN is_school_student BOOLEAN DEFAULT FALSE"))
                db.session.commit()
                messages.append("Added school-related columns to user table")
            else:
                messages.append("user table columns already exist")
        except Exception as e:
            db.session.rollback()
            messages.append(f"user table columns error: {str(e)}")
        
        messages_html = "".join([f"<li>{m}</li>" for m in messages])
        
        return f"""
        <html>
        <head><title>School Tables Updated</title>
        <style>body {{ font-family: Arial; padding: 40px; text-align: center; background: #f0f0f0; }}
        .card {{ background: white; padding: 40px; border-radius: 15px; max-width: 600px; margin: 0 auto; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
        h1 {{ color: #28a745; }} a {{ color: #667eea; }} ul {{ text-align: left; }}</style></head>
        <body>
            <div class="card">
                <h1>✅ Database Updated!</h1>
                <p>School system tables:</p>
                <ul>{messages_html}</ul>
                <p><a href="/admin/setup-learning-material-columns">Update Learning Material Columns</a></p>
                <p><a href="/">Go to Homepage</a></p>
            </div>
        </body>
        </html>
        """
    except Exception as e:
        return f"""
        <html>
        <head><title>Error</title>
        <style>body {{ font-family: Arial; padding: 40px; text-align: center; }}
        .error {{ color: #dc3545; }}</style></head>
        <body>
            <h1 class="error">❌ Error</h1>
            <p>{str(e)}</p>
            <p><a href="/">Go to Homepage</a></p>
        </body>
        </html>
        """, 500


@bp.route('/admin/setup-learning-material-columns')
def setup_learning_material_columns():
    """Add new columns to learning_material table for enhanced materials support - accessible without login for initial setup"""
    from sqlalchemy import text
    messages = []
    
    try:
        # Check and add material_type column
        try:
            result = db.session.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='learning_material' AND column_name='material_type'
            """))
            if not result.fetchone():
                db.session.execute(text("ALTER TABLE learning_material ADD COLUMN material_type VARCHAR(20) DEFAULT 'text'"))
                db.session.commit()
                messages.append("Added material_type column")
            else:
                messages.append("material_type column already exists")
        except Exception as e:
            db.session.rollback()
            messages.append(f"material_type error: {str(e)}")
        
        # Check and add file_url column
        try:
            result = db.session.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='learning_material' AND column_name='file_url'
            """))
            if not result.fetchone():
                db.session.execute(text("ALTER TABLE learning_material ADD COLUMN file_url VARCHAR(500)"))
                db.session.commit()
                messages.append("Added file_url column")
            else:
                messages.append("file_url column already exists")
        except Exception as e:
            db.session.rollback()
            messages.append(f"file_url error: {str(e)}")
        
        # Check and add file_type column
        try:
            result = db.session.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='learning_material' AND column_name='file_type'
            """))
            if not result.fetchone():
                db.session.execute(text("ALTER TABLE learning_material ADD COLUMN file_type VARCHAR(50)"))
                db.session.commit()
                messages.append("Added file_type column")
            else:
                messages.append("file_type column already exists")
        except Exception as e:
            db.session.rollback()
            messages.append(f"file_type error: {str(e)}")
        
        # Check and add youtube_url column
        try:
            result = db.session.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='learning_material' AND column_name='youtube_url'
            """))
            if not result.fetchone():
                db.session.execute(text("ALTER TABLE learning_material ADD COLUMN youtube_url VARCHAR(500)"))
                db.session.commit()
                messages.append("Added youtube_url column")
            else:
                messages.append("youtube_url column already exists")
        except Exception as e:
            db.session.rollback()
            messages.append(f"youtube_url error: {str(e)}")
        
        # Check and add file_name column
        try:
            result = db.session.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='learning_material' AND column_name='file_name'
            """))
            if not result.fetchone():
                db.session.execute(text("ALTER TABLE learning_material ADD COLUMN file_name VARCHAR(255)"))
                db.session.commit()
                messages.append("Added file_name column")
            else:
                messages.append("file_name column already exists")
        except Exception as e:
            db.session.rollback()
            messages.append(f"file_name error: {str(e)}")
        
        messages_html = "".join([f"<li>{m}</li>" for m in messages])
        
        return f"""
        <html>
        <head><title>Learning Material Columns Updated</title>
        <style>body {{ font-family: Arial; padding: 40px; text-align: center; background: #f0f0f0; }}
        .card {{ background: white; padding: 40px; border-radius: 15px; max-width: 600px; margin: 0 auto; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
        h1 {{ color: #28a745; }} a {{ color: #667eea; }} ul {{ text-align: left; }}</style></head>
        <body>
            <div class="card">
                <h1>✅ Database Updated!</h1>
                <p>Learning Material table columns:</p>
                <ul>{messages_html}</ul>
                <p><a href="/student/dashboard">Go to Student Dashboard</a></p>
                <p><a href="/">Go to Homepage</a></p>
            </div>
        </body>
        </html>
        """
    except Exception as e:
        return f"""
        <html>
        <head><title>Error</title>
        <style>body {{ font-family: Arial; padding: 40px; text-align: center; }}
        .error {{ color: #dc3545; }}</style></head>
        <body>
            <h1 class="error">❌ Error</h1>
            <p>{str(e)}</p>
            <p><a href="/">Go to Homepage</a></p>
        </body>
        </html>
        """, 500


@bp.route('/admin/setup-gallery-tables')
def setup_gallery_tables():
    """Create gallery and victory tables - accessible without login for initial setup"""
    from sqlalchemy import text
    messages = []
    
    try:
        # First create all tables
        db.create_all()
        messages.append("Tables created")
        
        # Check if video_format column exists
        try:
            result = db.session.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='home_gallery' AND column_name='video_format'
            """))
            if not result.fetchone():
                db.session.execute(text("ALTER TABLE home_gallery ADD COLUMN video_format VARCHAR(20) DEFAULT 'long'"))
                db.session.commit()
                messages.append("Added video_format column")
            else:
                messages.append("video_format column already exists")
        except Exception as e:
            db.session.rollback()
            messages.append(f"video_format error: {str(e)}")
        
        # Check if video_platform column exists
        try:
            result = db.session.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='home_gallery' AND column_name='video_platform'
            """))
            if not result.fetchone():
                db.session.execute(text("ALTER TABLE home_gallery ADD COLUMN video_platform VARCHAR(50) DEFAULT 'youtube'"))
                db.session.commit()
                messages.append("Added video_platform column")
            else:
                messages.append("video_platform column already exists")
        except Exception as e:
            db.session.rollback()
            messages.append(f"video_platform error: {str(e)}")
        
        # Check if class_pricing table exists and create if needed
        try:
            result = db.session.execute(text("""
                SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='class_pricing')
            """))
            if not result.fetchone()[0]:
                db.session.execute(text("""
                    CREATE TABLE class_pricing (
                        id SERIAL PRIMARY KEY,
                        class_type VARCHAR(50) UNIQUE NOT NULL,
                        name VARCHAR(100) NOT NULL,
                        price FLOAT NOT NULL,
                        description TEXT,
                        max_students INTEGER DEFAULT 1,
                        icon VARCHAR(50) DEFAULT 'fa-user',
                        color VARCHAR(20) DEFAULT '#00d4ff',
                        features TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        is_popular BOOLEAN DEFAULT FALSE,
                        display_order INTEGER DEFAULT 0,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                db.session.commit()
                messages.append("Created class_pricing table")
            else:
                messages.append("class_pricing table already exists")
        except Exception as e:
            db.session.rollback()
            messages.append(f"class_pricing: {str(e)}")
        
        messages_html = "".join([f"<li>{m}</li>" for m in messages])
        
        return f"""
        <html>
        <head><title>Tables Updated</title>
        <style>body {{ font-family: Arial; padding: 40px; text-align: center; background: #f0f0f0; }}
        .card {{ background: white; padding: 40px; border-radius: 15px; max-width: 600px; margin: 0 auto; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
        h1 {{ color: #28a745; }} a {{ color: #667eea; }} ul {{ text-align: left; }}</style></head>
        <body>
            <div class="card">
                <h1>✅ Database Updated!</h1>
                <p>Results:</p>
                <ul>{messages_html}</ul>
                <p><a href="/admin/gallery">Go to Gallery Management</a></p>
                <p><a href="/admin/victories">Go to Victories Management</a></p>
                <p><a href="/admin/pricing">Go to Pricing Management</a></p>
                <p><a href="/">Go to Homepage</a></p>
            </div>
        </body>
        </html>
        """
    except Exception as e:
        return f"""
        <html>
        <head><title>Error</title>
        <style>body {{ font-family: Arial; padding: 40px; text-align: center; }}
        .error {{ color: #dc3545; }}</style></head>
        <body>
            <h1 class="error">❌ Error</h1>
            <p>{str(e)}</p>
            <p><a href="/">Go to Homepage</a></p>
        </body>
        </html>
        """, 500


# Utilities

def anonymize_user_data(user_id: int) -> bool:
    try:
        user = User.query.get(user_id)
        if not user:
            return False
        user.username = f"deleted_user_{user_id}"
        user.email = f"deleted_{user_id}@techbuxin.com"
        user.first_name = "Deleted"
        user.last_name = "User"
        user.whatsapp_number = None
        user.is_student = False
        user.is_admin = False
        for purchase in Purchase.query.filter_by(user_id=user_id).all():
            purchase.customer_name = "Deleted User"
            purchase.customer_email = f"deleted_{user_id}@techbuxin.com"
            purchase.customer_phone = None
            purchase.customer_address = None
        for enrollment in ClassEnrollment.query.filter_by(user_id=user_id).all():
            enrollment.customer_name = "Deleted User"
            enrollment.customer_email = f"deleted_{user_id}@techbuxin.com"
            enrollment.customer_phone = None
            enrollment.customer_address = None
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Error anonymizing user data: {e}")
        return False


# Account deletion page
@bp.route('/delete-account', methods=['GET', 'POST'])
@login_required
def delete_account():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    from flask import request
    if request.method == 'POST':
        try:
            user_name = f"{current_user.first_name} {current_user.last_name}".strip()
            email = current_user.email

            # Anonymize instead of hard-deleting related data; customize as needed
            anonymize_user_data(current_user.id)

            # Log the user out
            logout_user()

            return render_template('deletion_success.html', user_name=user_name, email=email)
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting account: {e}")
            flash('An error occurred while deleting your account. Please try again.', 'danger')
            return render_template('delete_account.html')

    user_data = {
        'courses_purchased': Purchase.query.filter_by(user_id=current_user.id, status='completed').count(),
        'class_enrollments': ClassEnrollment.query.filter_by(user_id=current_user.id, status='completed').count(),
        'projects_posted': StudentProject.query.filter_by(student_id=current_user.id).count(),
        'robotics_submissions': RoboticsProjectSubmission.query.filter_by(user_id=current_user.id).count() if hasattr(RoboticsProjectSubmission, 'user_id') else 0,
        'account_created': current_user.created_at.strftime('%Y-%m-%d') if getattr(current_user, 'created_at', None) else 'Unknown',
    }
    return render_template('delete_account.html', user_data=user_data)


# Admin view placeholder for deletion requests
@bp.route('/admin/account-deletion-requests')
@login_required
def admin_account_deletion_requests():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    return render_template('admin_deletion_requests.html')


# DB maintenance: Fix password hash column length
@bp.route('/admin/fix-password-hash-length')
@login_required
def fix_password_hash_length():
    if not current_user.is_admin:
        return "Access denied: Admin privileges required", 403
    try:
        with db.engine.connect() as conn:
            conn.execute(db.text('ALTER TABLE "user" ALTER COLUMN password_hash TYPE VARCHAR(255)'))
            conn.commit()
        return (
            """
        <html>
        <head><title>Database Fixed</title>
        <style>body { font-family: Arial; padding: 20px; text-align: center; }</style></head>
        <body>
            <h1>Database Fixed Successfully</h1>
            <p>password_hash field expanded to 255 characters.</p>
        </body>
        </html>
        """
        )
    except Exception as e:
        return f"Error: {e}", 500


@bp.route('/admin/initialize-db')
@login_required
def initialize_db():
    if not current_user.is_admin:
        return "Access denied: Admin privileges required", 403
    try:
        db.create_all()
        return "Database initialized (db.create_all executed)."
    except Exception as e:
        return f"Initialization failed: {e}", 500


@bp.route('/admin/dashboard', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    from flask import request
    
    # Handle POST for sharing materials
    if request.method == 'POST':
        recipient_type = request.form.get('recipient_type', '')  # 'individual', 'school', 'family', 'group'
        recipient_id = request.form.get('recipient_id', '')
        content = request.form.get('message', '').strip()
        
        # Helper function to detect YouTube URLs
        def extract_youtube_id(url):
            """Extract YouTube video ID from various URL formats"""
            import re
            patterns = [
                r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
                r'youtube\.com\/watch\?.*v=([^&\n?#]+)'
            ]
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
            return None
        
        def detect_youtube_url(text):
            """Detect if text contains YouTube URL"""
            import re
            youtube_pattern = r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})'
            match = re.search(youtube_pattern, text)
            if match:
                return f"https://www.youtube.com/watch?v={match.group(1)}"
            return None
        
        # Determine material type and handle file uploads
        material_type = 'text'
        file_url = None
        file_type = None
        file_name = None
        youtube_url = None
        
        # Check for YouTube URL in content
        youtube_url = detect_youtube_url(content)
        if youtube_url:
            material_type = 'youtube'
        
        # Check for file upload
        uploaded_file = request.files.get('material_file')
        if uploaded_file and uploaded_file.filename:
            from ..services.cloudinary_service import CloudinaryService
            from werkzeug.utils import secure_filename
            
            file_name = secure_filename(uploaded_file.filename)
            file_ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
            
            # Determine resource type and material type
            if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg']:
                resource_type = 'image'
                material_type = 'image'
            elif file_ext in ['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv']:
                resource_type = 'video'
                material_type = 'video'
            elif file_ext in ['pdf']:
                resource_type = 'raw'
                material_type = 'pdf'
            else:
                resource_type = 'raw'
                material_type = 'text'
            
            # Upload to Cloudinary
            folder = 'learning_materials'
            success, result = CloudinaryService.upload_file(
                file=uploaded_file,
                folder=folder,
                resource_type=resource_type
            )
            
            if success:
                file_url = result.get('url')
                file_type = result.get('format', file_ext)
            else:
                flash(f'File upload failed: {result}', 'warning')
        
        # If no file and no YouTube, check if content is just a link (for backward compatibility)
        if material_type == 'text' and content.startswith('http'):
            # Keep as text with link
            pass
        
        if not recipient_type or not recipient_id:
            flash('Please select a recipient type and recipient.', 'danger')
        elif not content and not file_url and not youtube_url:
            flash('Please provide content, upload a file, or include a YouTube link.', 'danger')
        else:
            try:
                if recipient_type == 'individual':
                    # Share to individual student
                    student_id = int(recipient_id)
                    student = User.query.get(student_id)
                    if student:
                        material = LearningMaterial(
                            class_id=f"student_{student_id}",
                            class_type='individual',
                            actual_class_id=student_id,
                            content=content,
                            created_by=current_user.id,
                            material_type=material_type,
                            file_url=file_url,
                            file_type=file_type,
                            file_name=file_name,
                            youtube_url=youtube_url
                        )
                        db.session.add(material)
                        db.session.commit()
                        flash(f'Material shared with {student.first_name} {student.last_name}!', 'success')
                    else:
                        flash('Student not found.', 'danger')
                
                elif recipient_type == 'school':
                    # Share to all students in a school class
                    enrollment_id = int(recipient_id)
                    enrollment = ClassEnrollment.query.get(enrollment_id)
                    if enrollment and enrollment.class_type == 'school':
                        # Get all registered students for this school
                        school_students = SchoolStudent.query.filter_by(
                            enrollment_id=enrollment_id,
                            class_id=enrollment.class_id
                        ).all()
                        
                        # Also get the main enrolled user
                        main_user = User.query.get(enrollment.user_id)
                        
                        shared_count = 0
                        # Share to main enrolled user
                        if main_user:
                            material = LearningMaterial(
                                class_id=f"school_{enrollment.class_id}_enrollment_{enrollment_id}",
                                class_type='school',
                                actual_class_id=enrollment.class_id,
                                content=content,
                                created_by=current_user.id
                            )
                            db.session.add(material)
                            shared_count += 1
                        
                        # Share to all registered students (they see it through their enrollment)
                        # We create one material record for the school class, and all students see it
                        material = LearningMaterial(
                            class_id=f"school_{enrollment.class_id}_enrollment_{enrollment_id}",
                            class_type='school',
                            actual_class_id=enrollment.class_id,
                            content=content,
                            created_by=current_user.id,
                            material_type=material_type,
                            file_url=file_url,
                            file_type=file_type,
                            file_name=file_name,
                            youtube_url=youtube_url
                        )
                        db.session.add(material)
                        db.session.commit()
                        flash(f'Material shared with school class! All {len(school_students) + 1} members will see it.', 'success')
                    else:
                        flash('Invalid school enrollment.', 'danger')
                
                elif recipient_type == 'family':
                    # Share to all family members
                    enrollment_id = int(recipient_id)
                    enrollment = ClassEnrollment.query.get(enrollment_id)
                    if enrollment and enrollment.class_type == 'family':
                        # Get all registered family members
                        family_members = FamilyMember.query.filter_by(
                            enrollment_id=enrollment_id,
                            class_id=enrollment.class_id
                        ).all()
                        
                        # Get main enrolled user
                        main_user = User.query.get(enrollment.user_id)
                        
                        # Create material for the family class - all members see it
                        material = LearningMaterial(
                            class_id=f"family_{enrollment.class_id}_enrollment_{enrollment_id}",
                            class_type='family',
                            actual_class_id=enrollment.class_id,
                            content=content,
                            created_by=current_user.id,
                            material_type=material_type,
                            file_url=file_url,
                            file_type=file_type,
                            file_name=file_name,
                            youtube_url=youtube_url
                        )
                        db.session.add(material)
                        db.session.commit()
                        flash(f'Material shared with family class! All {len(family_members) + 1} members will see it.', 'success')
                    else:
                        flash('Invalid family enrollment.', 'danger')
                
                elif recipient_type == 'group':
                    # Share to all students in a group class
                    class_id = int(recipient_id)
                    class_obj = GroupClass.query.get(class_id)
                    if class_obj:
                        # Get all enrollments for this group class
                        group_enrollments = ClassEnrollment.query.filter_by(
                            class_id=class_id,
                            class_type='group',
                            status='completed'
                        ).all()
                        
                        # Create material for the group class - all enrolled students see it
                        material = LearningMaterial(
                            class_id=f"group_{class_id}",
                            class_type='group',
                            actual_class_id=class_id,
                            content=content,
                            created_by=current_user.id,
                            material_type=material_type,
                            file_url=file_url,
                            file_type=file_type,
                            file_name=file_name,
                            youtube_url=youtube_url
                        )
                        db.session.add(material)
                        db.session.commit()
                        flash(f'Material shared with group class "{class_obj.name}"! All {len(group_enrollments)} enrolled students will see it.', 'success')
                    else:
                        flash('Group class not found.', 'danger')
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error sharing material: {str(e)}', 'danger')
    
    # Get all data for the dashboard
    students = User.query.filter_by(is_student=True).all()
    individual_students = students
    
    # Get course orders
    course_orders = Purchase.query.order_by(Purchase.purchased_at.desc()).limit(50).all()
    
    # Get enrollments
    enrollments = ClassEnrollment.query.order_by(ClassEnrollment.enrolled_at.desc()).limit(50).all()
    
    # Get robotics count
    robotics_count = RoboticsProjectSubmission.query.count()
    
    # Get all classes
    try:
        all_group_classes = GroupClass.query.all()
    except Exception:
        all_group_classes = []
    
    try:
        all_individual_classes = IndividualClass.query.all()
    except Exception:
        all_individual_classes = []
    
    # Get school enrollments (for school type) with school names
    school_enrollments_data = []
    school_enrollments = ClassEnrollment.query.filter_by(
        class_type='school',
        status='completed'
    ).all()
    for enrollment in school_enrollments:
        # Get school name from first registered student
        first_student = SchoolStudent.query.filter_by(enrollment_id=enrollment.id).first()
        school_name = first_student.school_name if first_student else 'School'
        student_count = SchoolStudent.query.filter_by(enrollment_id=enrollment.id).count()
        school_enrollments_data.append({
            'id': enrollment.id,
            'class_id': enrollment.class_id,
            'school_name': school_name,
            'student_count': student_count
        })
    
    # Get family enrollments (for family type) with member counts
    family_enrollments_data = []
    family_enrollments = ClassEnrollment.query.filter_by(
        class_type='family',
        status='completed'
    ).all()
    for enrollment in family_enrollments:
        member_count = FamilyMember.query.filter_by(enrollment_id=enrollment.id).count()
        # Get main user name
        main_user = User.query.get(enrollment.user_id)
        family_name = f"{main_user.first_name} {main_user.last_name}'s Family" if main_user else 'Family'
        family_enrollments_data.append({
            'id': enrollment.id,
            'class_id': enrollment.class_id,
            'member_count': member_count,
            'family_name': family_name
        })
    
    # Get group classes with student counts
    group_classes_data = []
    for class_obj in all_group_classes:
        student_count = ClassEnrollment.query.filter_by(
            class_id=class_obj.id,
            class_type='group',
            status='completed'
        ).count()
        group_classes_data.append({
            'id': class_obj.id,
            'name': class_obj.name,
            'student_count': student_count
        })
    
    # Get materials
    try:
        materials = LearningMaterial.query.order_by(LearningMaterial.created_at.desc()).limit(50).all()
    except Exception:
        materials = []
    
    return render_template('admin_dashboard.html',
        students=students,
        individual_students=individual_students,
        all_group_classes=all_group_classes,
        all_individual_classes=all_individual_classes,
        school_enrollments_data=school_enrollments_data,
        family_enrollments_data=family_enrollments_data,
        group_classes_data=group_classes_data,
        materials=materials,
        course_orders=course_orders,
        enrollments=enrollments,
        robotics_count=robotics_count
    )


@bp.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    from flask import request
    search = request.args.get('search', '')
    query = User.query
    if search:
        query = query.filter(
            User.email.contains(search) | 
            User.first_name.contains(search) | 
            User.last_name.contains(search)
        )
    users = query.order_by(User.id.desc()).all()
    return render_template('admin_users.html', users=users, search_term=search)


@bp.route('/admin/create-class', methods=['GET', 'POST'])
@login_required
def create_class():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    from flask import request
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        max_students = request.form.get('max_students', 10)
        
        if not name:
            flash('Class name is required.', 'danger')
            return render_template('create_class.html')
        
        try:
            try:
                max_students = int(max_students)
            except Exception:
                max_students = 10

            # All classes are now a single type; we use GroupClass as the unified model
            new_class = GroupClass(
                name=name,
                description=description,
                teacher_id=current_user.id,
                max_students=max_students
            )
            
            db.session.add(new_class)
            db.session.commit()
            flash(f'Class "{name}" created successfully!', 'success')
            return redirect(url_for('admin.admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating class: {str(e)}', 'danger')
            return render_template('create_class.html')
    
    return render_template('create_class.html')


@bp.route('/admin/classes')
@login_required
def admin_classes():
    """View all classes"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    # Legacy individual classes are kept for display, but new classes use GroupClass
    individual_classes = IndividualClass.query.all()
    group_classes = GroupClass.query.all()
    all_classes = group_classes + individual_classes
    
    return render_template('admin_classes.html',
        classes=all_classes
    )


@bp.route('/admin/edit-class/<int:class_id>', methods=['GET', 'POST'])
@bp.route('/admin/edit-class/<class_type>/<int:class_id>', methods=['GET', 'POST'])  # legacy URL
@login_required
def edit_class(class_id, class_type=None):
    """Edit a class"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    from flask import request
    
    # Prefer unified GroupClass; fall back to legacy IndividualClass for older records
    class_obj = GroupClass.query.get(class_id) or IndividualClass.query.get_or_404(class_id)
    
    if request.method == 'POST':
        class_obj.name = request.form.get('name', class_obj.name).strip()
        class_obj.description = request.form.get('description', class_obj.description).strip()
        
        if hasattr(class_obj, 'max_students'):
            try:
                class_obj.max_students = int(request.form.get('max_students', 10))
            except Exception:
                class_obj.max_students = 10
        
        try:
            db.session.commit()
            flash(f'Class "{class_obj.name}" updated successfully!', 'success')
            return redirect(url_for('admin.admin_classes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating class: {str(e)}', 'danger')
    
    return render_template('edit_class.html', class_obj=class_obj)


@bp.route('/admin/delete-class/<int:class_id>', methods=['POST'])
@bp.route('/admin/delete-class/<class_type>/<int:class_id>', methods=['POST'])  # legacy URL
@login_required
def delete_class(class_id, class_type=None):
    """Delete a class"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    class_obj = GroupClass.query.get(class_id) or IndividualClass.query.get_or_404(class_id)
    
    class_name = class_obj.name
    
    try:
        db.session.delete(class_obj)
        db.session.commit()
        flash(f'Class "{class_name}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting class: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_classes'))


@bp.route('/admin/enrollments')
@login_required
def admin_enrollments():
    """View all class enrollments"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    from flask import request
    status_filter = request.args.get('status', '')
    
    query = ClassEnrollment.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    enrollments = query.order_by(ClassEnrollment.enrolled_at.desc()).all()
    
    # Get class names for each enrollment
    for enrollment in enrollments:
        # Unified classes now live in GroupClass; keep legacy lookup for old data
        class_obj = GroupClass.query.get(enrollment.class_id) or IndividualClass.query.get(enrollment.class_id)
        enrollment.class_name = class_obj.name if class_obj else 'Unknown'
        
        # Get user info
        user = User.query.get(enrollment.user_id)
        enrollment.user = user
    
    return render_template('admin_enrollments.html', 
        enrollments=enrollments,
        status_filter=status_filter
    )


@bp.route('/admin/enrollment/<int:enrollment_id>')
@login_required
def view_enrollment(enrollment_id):
    """View enrollment details"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    enrollment = ClassEnrollment.query.get_or_404(enrollment_id)
    
    # Get class info
    class_obj = GroupClass.query.get(enrollment.class_id) or IndividualClass.query.get(enrollment.class_id)
    
    # Get user info
    user = User.query.get(enrollment.user_id)
    
    return render_template('view_enrollment.html',
        enrollment=enrollment,
        class_obj=class_obj,
        user=user
    )


@bp.route('/admin/enrollment/<int:enrollment_id>/approve', methods=['POST'])
@login_required
def approve_enrollment(enrollment_id):
    """Approve an enrollment and generate Student ID"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    enrollment = ClassEnrollment.query.get_or_404(enrollment_id)
    user = User.query.get(enrollment.user_id)
    
    if not user:
        flash('User not found for this enrollment.', 'danger')
        return redirect(url_for('admin.admin_enrollments'))
    
    # Generate Student ID if not already generated (for Group, Family, Individual classes)
    if enrollment.class_type in ['group', 'family', 'individual']:
        if not user.student_id:
            from ..models.classes import generate_student_id_for_class
            user.student_id = generate_student_id_for_class(enrollment.class_type)
            user.class_type = enrollment.class_type
            flash(f'Student ID generated: {user.student_id}', 'info')
    
    # Add student to class based on class type
    if enrollment.class_type == 'individual':
        from ..models.classes import IndividualClass, individual_class_students
        class_obj = IndividualClass.query.get(enrollment.class_id)
        if class_obj and user not in class_obj.students:
            class_obj.students.append(user)
    elif enrollment.class_type == 'group':
        from ..models.classes import GroupClass, group_class_students
        class_obj = GroupClass.query.get(enrollment.class_id)
        if class_obj:
            if len(class_obj.students) >= class_obj.max_students:
                flash(f'Cannot approve: Group class is full ({len(class_obj.students)}/{class_obj.max_students} students).', 'warning')
                return redirect(url_for('admin.admin_enrollments'))
            if user not in class_obj.students:
                class_obj.students.append(user)
    
    enrollment.status = 'completed'
    
    try:
        db.session.commit()
        student_id_msg = f' (Student ID: {user.student_id})' if user.student_id else ''
        flash(f'Enrollment approved for {enrollment.customer_name}!{student_id_msg}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_enrollments'))


@bp.route('/admin/enrollment/<int:enrollment_id>/reject', methods=['POST'])
@login_required
def reject_enrollment(enrollment_id):
    """Reject an enrollment"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    enrollment = ClassEnrollment.query.get_or_404(enrollment_id)
    enrollment.status = 'rejected'
    
    try:
        db.session.commit()
        flash(f'Enrollment rejected for {enrollment.customer_name}.', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_enrollments'))


@bp.route('/student/dashboard')
@login_required
def student_dashboard():
    from datetime import datetime, date, timedelta
    from flask import flash
    from calendar import monthrange
    
    # Check if user has any CONFIRMED enrollment (status = 'completed')
    # Only confirmed students can access the dashboard
    has_confirmed_enrollment = ClassEnrollment.query.filter_by(
        user_id=current_user.id,
        status='completed'
    ).first() is not None
    
    if not has_confirmed_enrollment and not current_user.is_admin:
        # Check if they have pending enrollment
        has_pending = ClassEnrollment.query.filter_by(
            user_id=current_user.id,
            status='pending'
        ).first() is not None
        
        if has_pending:
            flash('Your class enrollment is pending approval. Please wait for admin confirmation.', 'warning')
        else:
            flash('You need to enroll in a class first. Please register for a class to access your dashboard.', 'info')
        return redirect(url_for('main.index'))
    
    purchases = Purchase.query.filter_by(user_id=current_user.id, status='completed').all()
    projects = StudentProject.query.filter_by(student_id=current_user.id).all()
    enrollments = ClassEnrollment.query.filter_by(user_id=current_user.id, status='completed').all()
    
    # Get classes the student is enrolled in
    enrolled_classes = []
    for enrollment in enrollments:
        # Try GroupClass first (unified), then IndividualClass (legacy)
        class_obj = GroupClass.query.get(enrollment.class_id) or IndividualClass.query.get(enrollment.class_id)
        if class_obj:
            enrolled_classes.append({
                'id': class_obj.id,
                'name': class_obj.name,
                'description': class_obj.description,
                'class_type': enrollment.class_type,  # individual, group, family, school
                'enrollment': enrollment
            })
    
    # Get all students in same classes (for group/family classes)
    class_students = {}  # {class_id: [list of students]}
    # Also get all students for attendance (includes registered students for schools)
    all_students_for_attendance = {}  # {class_id: [list of all students for attendance]}
    
    for cls in enrolled_classes:
        if cls['class_type'] in ['group', 'family', 'school']:
            # Get all enrollments for this class
            class_enrollments = ClassEnrollment.query.filter_by(
                class_id=cls['id'],
                status='completed'
            ).all()
            students = []
            for enr in class_enrollments:
                student = User.query.get(enr.user_id)
                if student:
                    students.append({
                        'id': student.id,
                        'name': f"{student.first_name} {student.last_name}",
                        'username': student.username,
                        'type': 'user'  # Regular enrolled user
                    })
            class_students[cls['id']] = students
            
            # For attendance, also include registered students (for schools) or family members (for families)
            attendance_students = list(students)  # Start with enrolled users
            
            if cls['class_type'] == 'school':
                # Add registered school students
                registered_school_students = SchoolStudent.query.filter_by(
                    class_id=cls['id'],
                    enrollment_id=cls['enrollment'].id
                ).all()
                for reg_student in registered_school_students:
                    attendance_students.append({
                        'id': f"school_student_{reg_student.id}",  # Unique identifier
                        'name': reg_student.student_name,
                        'username': None,
                        'type': 'school_student',
                        'school_student_id': reg_student.id,
                        'school_name': reg_student.school_name
                    })
            elif cls['class_type'] == 'family':
                # Add registered family members
                registered_family_members = FamilyMember.query.filter_by(
                    class_id=cls['id'],
                    enrollment_id=cls['enrollment'].id
                ).all()
                for member in registered_family_members:
                    attendance_students.append({
                        'id': f"family_member_{member.id}",  # Unique identifier
                        'name': member.member_name,
                        'username': None,
                        'type': 'family_member',
                        'family_member_id': member.id,
                        'relationship': member.relationship
                    })
            
            all_students_for_attendance[cls['id']] = attendance_students
    
    # Get attendance data for current month
    today = date.today()
    month_start = date(today.year, today.month, 1)
    month_end = date(today.year, today.month, monthrange(today.year, today.month)[1])
    
    attendance_records = {}
    monthly_stats = {}
    all_class_attendance = {}  # For group classes - all students' attendance
    
    for cls in enrolled_classes:
        # Get attendance for current user in this class this month
        attendance = Attendance.query.filter(
            Attendance.student_id == current_user.id,
            Attendance.class_id == cls['id'],
            Attendance.attendance_date >= month_start,
            Attendance.attendance_date <= month_end
        ).order_by(Attendance.attendance_date.desc()).all()
        
        attendance_records[cls['id']] = attendance
        
        # For group classes, get all students' attendance
        if cls['class_type'] in ['group', 'family', 'school']:
            all_students_attendance = Attendance.query.filter(
                Attendance.class_id == cls['id'],
                Attendance.attendance_date >= month_start,
                Attendance.attendance_date <= month_end
            ).order_by(Attendance.attendance_date.desc()).all()
            all_class_attendance[cls['id']] = all_students_attendance
        
        # Calculate monthly percentage
        total_days = monthrange(today.year, today.month)[1]
        present_days = len([a for a in attendance if a.status == 'present'])
        percentage = (present_days / total_days * 100) if total_days > 0 else 0
        monthly_stats[cls['id']] = {
            'present': present_days,
            'total': total_days,
            'percentage': round(percentage, 1)
        }
    
    # Check today's attendance
    today_attendance = {}
    all_students_today_attendance = {}  # {class_id: {student_id: attendance_record}}
    
    for cls in enrolled_classes:
        today_att = Attendance.query.filter(
            Attendance.student_id == current_user.id,
            Attendance.class_id == cls['id'],
            Attendance.attendance_date == today
        ).first()
        today_attendance[cls['id']] = today_att
        
        # Get today's attendance for all students in this class
        if cls['class_type'] in ['group', 'family', 'school']:
            class_today_attendance = {}
            # Get attendance for all enrolled users
            for student in class_students.get(cls['id'], []):
                if student['type'] == 'user':
                    att = Attendance.query.filter(
                        Attendance.student_id == student['id'],
                        Attendance.class_id == cls['id'],
                        Attendance.attendance_date == today
                    ).first()
                    if att:
                        class_today_attendance[student['id']] = att
            all_students_today_attendance[cls['id']] = class_today_attendance
    
    # Get registered students/family members for school/family classes
    registered_students = {}  # {class_id: [list of SchoolStudent]}
    registered_family = {}    # {class_id: [list of FamilyMember]}
    
    for cls in enrolled_classes:
        if cls['class_type'] == 'school':
            # Get all registered students for this school class
            students = SchoolStudent.query.filter_by(
                class_id=cls['id'],
                enrollment_id=cls['enrollment'].id
            ).all()
            registered_students[cls['id']] = students
        elif cls['class_type'] == 'family':
            # Get all registered family members
            members = FamilyMember.query.filter_by(
                class_id=cls['id'],
                enrollment_id=cls['enrollment'].id
            ).all()
            registered_family[cls['id']] = members
    
    # Get materials shared to student's classes
    materials = []
    try:
        for cls in enrolled_classes:
            # Get materials for this class based on class type
            if cls['class_type'] == 'individual':
                # Materials shared directly to student or to individual class
                from sqlalchemy import or_
                class_materials = LearningMaterial.query.filter(
                    or_(
                        LearningMaterial.class_id == f"student_{current_user.id}",
                        (LearningMaterial.class_type == 'individual') & (LearningMaterial.actual_class_id == cls['id'])
                    )
                ).all()
                materials.extend(class_materials)
            elif cls['class_type'] == 'group':
                # Materials shared to this group class
                class_materials = LearningMaterial.query.filter_by(
                    class_type='group',
                    actual_class_id=cls['id']
                ).all()
                materials.extend(class_materials)
            elif cls['class_type'] == 'school':
                # Materials shared to this school enrollment
                enrollment_id = cls['enrollment'].id
                class_materials = LearningMaterial.query.filter(
                    LearningMaterial.class_id.like(f"%school_{cls['id']}_enrollment_{enrollment_id}%")
                ).all()
                materials.extend(class_materials)
            elif cls['class_type'] == 'family':
                # Materials shared to this family enrollment
                enrollment_id = cls['enrollment'].id
                class_materials = LearningMaterial.query.filter(
                    LearningMaterial.class_id.like(f"%family_{cls['id']}_enrollment_{enrollment_id}%")
                ).all()
                materials.extend(class_materials)
        
        # Remove duplicates and sort by date
        seen_ids = set()
        unique_materials = []
        for material in materials:
            if material.id not in seen_ids:
                seen_ids.add(material.id)
                unique_materials.append(material)
        materials = sorted(unique_materials, key=lambda x: x.created_at, reverse=True)
    except Exception as e:
        # If columns don't exist yet, check if it's a column error
        error_str = str(e)
        if 'material_type' in error_str or 'file_url' in error_str or 'youtube_url' in error_str or 'UndefinedColumn' in error_str:
            # Redirect to migration route
            flash('Database needs to be updated. Please visit the migration route first.', 'warning')
            return redirect(url_for('admin.setup_learning_material_columns'))
        # Re-raise if it's a different error
        raise
    
    # Helper function for time-based greeting
    def now():
        return datetime.now()
    
    return render_template('student_dashboard.html', 
                          purchases=purchases, 
                          projects=projects,
                          enrollments=enrollments,
                          enrolled_classes=enrolled_classes,
                          class_students=class_students,
                          all_students_for_attendance=all_students_for_attendance,
                          all_students_today_attendance=all_students_today_attendance,
                          attendance_records=attendance_records,
                          all_class_attendance=all_class_attendance,
                          monthly_stats=monthly_stats,
                          today_attendance=today_attendance,
                          registered_students=registered_students,
                          registered_family=registered_family,
                          materials=materials,
                          now=now,
                          today=today,
                          Attendance=Attendance)


@bp.route('/student/mark-attendance', methods=['POST'])
@login_required
def mark_attendance():
    """Student marks their own attendance or school admin marks student attendance"""
    from datetime import date
    
    class_id = request.form.get('class_id', type=int) or 0  # Can be 0 for school students
    status = request.form.get('status', 'present')  # present, absent
    student_id = request.form.get('student_id', type=int)  # For group/family classes or school students
    
    # If student_id is provided, it's for marking another student (in group/family/school)
    # Otherwise, mark self
    target_student_id = student_id if student_id else current_user.id
    
    # Check if this is a school student (school admin marking attendance)
    target_user = User.query.get(target_student_id)
    is_school_context = False
    
    if target_user and (target_user.is_school_student or current_user.is_school_admin):
        # School student attendance - no enrollment needed
        is_school_context = True
        class_type = 'school'
    else:
        # Regular class enrollment attendance
        enrollment = ClassEnrollment.query.filter_by(
            user_id=target_student_id,
            class_id=class_id,
            status='completed'
        ).first()
        
        if not enrollment:
            flash('You are not enrolled in this class.', 'danger')
            # Redirect based on user type
            if current_user.is_school_admin:
                return redirect(url_for('schools.school_dashboard'))
            return redirect(url_for('admin.student_dashboard'))
        
        class_type = enrollment.class_type
    
    # Check if already marked today
    today = date.today()
    existing = Attendance.query.filter_by(
        student_id=target_student_id,
        class_id=class_id,
        attendance_date=today
    ).first()
    
    if existing:
        existing.status = status
        existing.marked_by = current_user.id
        flash('Attendance updated successfully!', 'success')
    else:
        new_attendance = Attendance(
            student_id=target_student_id,
            class_id=class_id,
            class_type=class_type,
            attendance_date=today,
            status=status,
            marked_by=current_user.id
        )
        db.session.add(new_attendance)
        flash('Attendance marked successfully!', 'success')
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'Error marking attendance: {str(e)}', 'danger')
    
    # Redirect based on user type
    if current_user.is_school_admin:
        return redirect(url_for('schools.school_dashboard'))
    return redirect(url_for('admin.student_dashboard'))


@bp.route('/student/register-student', methods=['POST'])
@login_required
def register_student():
    """Register a student for a school class"""
    from werkzeug.utils import secure_filename
    import cloudinary
    import cloudinary.uploader
    
    enrollment_id = request.form.get('enrollment_id', type=int)
    class_id = request.form.get('class_id', type=int)
    school_name = request.form.get('school_name', '').strip()
    student_name = request.form.get('student_name', '').strip()
    student_age = request.form.get('student_age', type=int)
    student_email = request.form.get('student_email', '').strip()
    student_phone = request.form.get('student_phone', '').strip()
    parent_name = request.form.get('parent_name', '').strip()
    parent_phone = request.form.get('parent_phone', '').strip()
    parent_email = request.form.get('parent_email', '').strip()
    additional_info = request.form.get('additional_info', '').strip()
    
    # Verify enrollment
    enrollment = ClassEnrollment.query.filter_by(
        id=enrollment_id,
        user_id=current_user.id,
        class_id=class_id,
        class_type='school',
        status='completed'
    ).first()
    
    if not enrollment:
        flash('Invalid enrollment or you do not have permission.', 'danger')
        return redirect(url_for('admin.student_dashboard'))
    
    if not school_name or not student_name:
        flash('School name and student name are required.', 'danger')
        return redirect(url_for('admin.student_dashboard'))
    
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
    
    try:
        new_student = SchoolStudent(
            enrollment_id=enrollment_id,
            class_id=class_id,
            school_name=school_name,
            student_name=student_name,
            student_age=student_age,
            student_image_url=student_image_url,
            student_email=student_email,
            student_phone=student_phone,
            parent_name=parent_name,
            parent_phone=parent_phone,
            parent_email=parent_email,
            additional_info=additional_info,
            registered_by=current_user.id
        )
        db.session.add(new_student)
        db.session.commit()
        flash(f'Student "{student_name}" registered successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error registering student: {str(e)}', 'danger')
    
    return redirect(url_for('admin.student_dashboard'))


@bp.route('/student/register-family-member', methods=['POST'])
@login_required
def register_family_member():
    """Register a family member for a family class"""
    from werkzeug.utils import secure_filename
    import cloudinary
    import cloudinary.uploader
    
    enrollment_id = request.form.get('enrollment_id', type=int)
    class_id = request.form.get('class_id', type=int)
    member_name = request.form.get('member_name', '').strip()
    member_age = request.form.get('member_age', type=int)
    member_email = request.form.get('member_email', '').strip()
    member_phone = request.form.get('member_phone', '').strip()
    relationship = request.form.get('relationship', '').strip()
    additional_info = request.form.get('additional_info', '').strip()
    
    # Verify enrollment
    enrollment = ClassEnrollment.query.filter_by(
        id=enrollment_id,
        user_id=current_user.id,
        class_id=class_id,
        class_type='family',
        status='completed'
    ).first()
    
    if not enrollment:
        flash('Invalid enrollment or you do not have permission.', 'danger')
        return redirect(url_for('admin.student_dashboard'))
    
    # Check if already at max (4 family members)
    existing_count = FamilyMember.query.filter_by(enrollment_id=enrollment_id).count()
    if existing_count >= 4:
        flash('Maximum 4 family members allowed per family class.', 'danger')
        return redirect(url_for('admin.student_dashboard'))
    
    if not member_name:
        flash('Family member name is required.', 'danger')
        return redirect(url_for('admin.student_dashboard'))
    
    # Handle image upload
    member_image_url = None
    if 'member_image' in request.files:
        image_file = request.files['member_image']
        if image_file and image_file.filename:
            try:
                upload_result = cloudinary.uploader.upload(image_file)
                member_image_url = upload_result.get('secure_url')
            except Exception as e:
                flash(f'Error uploading image: {str(e)}', 'warning')
    
    try:
        new_member = FamilyMember(
            enrollment_id=enrollment_id,
            class_id=class_id,
            member_name=member_name,
            member_age=member_age,
            member_image_url=member_image_url,
            member_email=member_email,
            member_phone=member_phone,
            relationship=relationship,
            additional_info=additional_info,
            registered_by=current_user.id
        )
        db.session.add(new_member)
        db.session.commit()
        flash(f'Family member "{member_name}" registered successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error registering family member: {str(e)}', 'danger')
    
    return redirect(url_for('admin.student_dashboard'))


@bp.route('/admin/attendance')
@login_required
def admin_attendance():
    """Admin view and manage attendance"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    from datetime import date, timedelta
    from calendar import monthrange
    
    # Get filter parameters
    selected_date = request.args.get('date', date.today().isoformat())
    selected_class_id = request.args.get('class_id', type=int)
    selected_student_id = request.args.get('student_id', type=int)
    
    try:
        filter_date = date.fromisoformat(selected_date)
    except:
        filter_date = date.today()
    
    # Get all classes
    all_classes = GroupClass.query.all() + IndividualClass.query.all()
    
    # Get attendance for selected date
    attendance_query = Attendance.query.filter_by(attendance_date=filter_date)
    
    if selected_class_id:
        attendance_query = attendance_query.filter_by(class_id=selected_class_id)
    if selected_student_id:
        attendance_query = attendance_query.filter_by(student_id=selected_student_id)
    
    attendance_records = attendance_query.order_by(Attendance.created_at.desc()).all()
    
    # Get class names, student names, and marker names
    for att in attendance_records:
        class_obj = GroupClass.query.get(att.class_id) or IndividualClass.query.get(att.class_id)
        att.class_name = class_obj.name if class_obj else 'Unknown'
        student = User.query.get(att.student_id)
        att.student_name = f"{student.first_name} {student.last_name}" if student else 'Unknown'
        # Get marker (who marked the attendance)
        if att.marked_by:
            marker = User.query.get(att.marked_by)
            att.marker_name = f"{marker.first_name} {marker.last_name}" if marker else 'Unknown'
        else:
            att.marker_name = 'System'
    
    # Get all students enrolled in classes
    all_enrollments = ClassEnrollment.query.filter_by(status='completed').all()
    enrolled_students = {}
    for enr in all_enrollments:
        if enr.class_id not in enrolled_students:
            enrolled_students[enr.class_id] = []
        student = User.query.get(enr.user_id)
        if student:
            enrolled_students[enr.class_id].append({
                'id': student.id,
                'name': f"{student.first_name} {student.last_name}",
                'username': student.username
            })
    
    # Get monthly stats for each student
    today = date.today()
    month_start = date(today.year, today.month, 1)
    month_end = date(today.year, today.month, monthrange(today.year, today.month)[1])
    
    monthly_stats = {}
    all_students = User.query.filter_by(is_student=True).all()
    for student in all_students:
        student_attendance = Attendance.query.filter(
            Attendance.student_id == student.id,
            Attendance.attendance_date >= month_start,
            Attendance.attendance_date <= month_end
        ).all()
        
        total_days = monthrange(today.year, today.month)[1]
        present_days = len([a for a in student_attendance if a.status == 'present'])
        percentage = (present_days / total_days * 100) if total_days > 0 else 0
        
        monthly_stats[student.id] = {
            'present': present_days,
            'total': total_days,
            'percentage': round(percentage, 1)
        }
    
    return render_template('admin_attendance.html',
                         attendance_records=attendance_records,
                         all_classes=all_classes,
                         enrolled_students=enrolled_students,
                         filter_date=filter_date,
                         selected_class_id=selected_class_id,
                         selected_student_id=selected_student_id,
                         monthly_stats=monthly_stats)


@bp.route('/admin/mark-attendance', methods=['POST'])
@login_required
def admin_mark_attendance():
    """Admin marks attendance for students"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    from datetime import date
    
    student_id = request.form.get('student_id', type=int)
    class_id = request.form.get('class_id', type=int)
    attendance_date_str = request.form.get('attendance_date', date.today().isoformat())
    status = request.form.get('status', 'present')
    
    try:
        attendance_date = date.fromisoformat(attendance_date_str)
    except:
        attendance_date = date.today()
    
    # Verify enrollment
    enrollment = ClassEnrollment.query.filter_by(
        user_id=student_id,
        class_id=class_id,
        status='completed'
    ).first()
    
    if not enrollment:
        flash('Student is not enrolled in this class.', 'danger')
        return redirect(url_for('admin.admin_attendance'))
    
    # Check if already marked
    existing = Attendance.query.filter_by(
        student_id=student_id,
        class_id=class_id,
        attendance_date=attendance_date
    ).first()
    
    if existing:
        existing.status = status
        existing.marked_by = current_user.id
        flash('Attendance updated successfully!', 'success')
    else:
        new_attendance = Attendance(
            student_id=student_id,
            class_id=class_id,
            class_type=enrollment.class_type,
            attendance_date=attendance_date,
            status=status,
            marked_by=current_user.id
        )
        db.session.add(new_attendance)
        flash('Attendance marked successfully!', 'success')
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'Error marking attendance: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_attendance', date=attendance_date_str, class_id=class_id))


@bp.route('/admin/registered-students')
@login_required
def admin_registered_students():
    """Admin view all registered students and family members"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    filter_type = request.args.get('type', '')  # 'school', 'family', 'individual', 'group', or 'all'
    
    # Get all school students
    school_students = SchoolStudent.query.order_by(SchoolStudent.created_at.desc()).all()
    
    # Get all family members
    family_members = FamilyMember.query.order_by(FamilyMember.created_at.desc()).all()
    
    # Get individual students (enrollments with class_type='individual')
    individual_enrollments = ClassEnrollment.query.filter_by(
        class_type='individual',
        status='completed'
    ).order_by(ClassEnrollment.enrolled_at.desc()).all()
    
    individual_students = []
    for enrollment in individual_enrollments:
        student = User.query.get(enrollment.user_id)
        if student:
            class_obj = IndividualClass.query.get(enrollment.class_id) or GroupClass.query.get(enrollment.class_id)
            individual_students.append({
                'user': student,
                'enrollment': enrollment,
                'class': class_obj
            })
    
    # Get group students (enrollments with class_type='group')
    group_enrollments = ClassEnrollment.query.filter_by(
        class_type='group',
        status='completed'
    ).order_by(ClassEnrollment.enrolled_at.desc()).all()
    
    # Group by class
    group_students_by_class = {}
    for enrollment in group_enrollments:
        class_obj = GroupClass.query.get(enrollment.class_id)
        if class_obj:
            if class_obj.id not in group_students_by_class:
                group_students_by_class[class_obj.id] = {
                    'class': class_obj,
                    'students': []
                }
            student = User.query.get(enrollment.user_id)
            if student:
                group_students_by_class[class_obj.id]['students'].append({
                    'user': student,
                    'enrollment': enrollment
                })
    
    # Group school students by school name
    schools_grouped = {}
    for student in school_students:
        school_name = student.school_name
        if school_name not in schools_grouped:
            schools_grouped[school_name] = []
        schools_grouped[school_name].append(student)
    
    # Group family members by enrollment_id
    families_grouped = {}
    for member in family_members:
        enrollment_id = member.enrollment_id
        if enrollment_id not in families_grouped:
            families_grouped[enrollment_id] = []
        families_grouped[enrollment_id].append(member)
    
    # Get unique counts
    unique_schools = list(schools_grouped.keys())
    unique_families = list(families_grouped.keys())
    
    # Calculate total group students count
    total_group_students = sum(len(class_data['students']) for class_data in group_students_by_class.values())
    
    return render_template('admin_registered_students.html',
                         school_students=school_students,
                         family_members=family_members,
                         individual_students=individual_students,
                         group_students_by_class=group_students_by_class,
                         total_group_students=total_group_students,
                         schools_grouped=schools_grouped,
                         families_grouped=families_grouped,
                         unique_schools=unique_schools,
                         unique_families=unique_families,
                         filter_type=filter_type)


@bp.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_user(user_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.health'))
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        try:
            user.first_name = request.form.get('first_name', user.first_name)
            user.last_name = request.form.get('last_name', user.last_name)
            user.email = request.form.get('email', user.email)
            user.username = request.form.get('username', user.username)
            user.is_admin = request.form.get('is_admin') == 'on'
            user.is_student = request.form.get('is_student') != 'off' if request.form.get('is_student') else user.is_student
            db.session.commit()
            flash('User updated successfully.', 'success')
            return redirect(url_for('admin_edit_user', user_id=user.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to update user: {e}', 'danger')
    return render_template('admin_user_edit.html', user=user)


# ========== GALLERY MANAGEMENT ==========
@bp.route('/admin/gallery')
@login_required
def admin_gallery():
    """Admin page to manage homepage gallery (images and videos)"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    media_type = request.args.get('type', '')
    source = request.args.get('source', '')
    
    # Initialize with empty values in case tables don't exist
    gallery_items = []
    student_projects_with_images = []
    student_projects_with_videos = []
    total_images = 0
    total_videos = 0
    from_projects = 0
    
    try:
        query = HomeGallery.query
        if media_type:
            query = query.filter_by(media_type=media_type)
        if source:
            query = query.filter_by(source_type=source)
        
        gallery_items = query.order_by(HomeGallery.display_order.asc(), HomeGallery.created_at.desc()).all()
        
        # Stats
        total_images = HomeGallery.query.filter_by(media_type='image').count()
        total_videos = HomeGallery.query.filter_by(media_type='video').count()
        from_projects = HomeGallery.query.filter_by(source_type='student_project').count()
    except Exception as e:
        db.session.rollback()
        flash(f'Gallery tables not found. Please create them first by visiting /admin/create-gallery-tables', 'warning')
    
    try:
        # Get student projects with images or videos for quick import
        student_projects_with_images = StudentProject.query.filter(
            StudentProject.is_active == True,
            StudentProject.image_url.isnot(None),
            StudentProject.image_url != ''
        ).all()
        
        student_projects_with_videos = StudentProject.query.filter(
            StudentProject.is_active == True,
            StudentProject.youtube_url.isnot(None),
            StudentProject.youtube_url != ''
        ).all()
    except Exception:
        db.session.rollback()
    
    return render_template('admin_gallery.html',
        gallery_items=gallery_items,
        student_projects_with_images=student_projects_with_images,
        student_projects_with_videos=student_projects_with_videos,
        total_images=total_images,
        total_videos=total_videos,
        from_projects=from_projects,
        media_type_filter=media_type,
        source_filter=source
    )


@bp.route('/admin/gallery/add', methods=['GET', 'POST'])
@login_required
def admin_gallery_add():
    """Add new gallery item - supports both URL and file upload"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        media_type = request.form.get('media_type', 'image')
        media_url = request.form.get('media_url', '').strip()
        thumbnail_url = request.form.get('thumbnail_url', '').strip()
        is_featured = request.form.get('is_featured') == 'on'
        display_order = request.form.get('display_order', 0, type=int)
        input_method = request.form.get('input_method', 'url')
        
        # Handle file upload if chosen
        if input_method == 'upload':
            media_file = request.files.get('media_file')
            if media_file and media_file.filename:
                from ..services.cloudinary_service import cloudinary_service
                
                # Determine resource type
                resource_type = 'video' if media_type == 'video' else 'image'
                folder = f'gallery/{media_type}s'
                
                success, result = cloudinary_service.upload_file(
                    media_file,
                    folder=folder,
                    resource_type=resource_type
                )
                
                if success:
                    media_url = result['url']
                    flash(f'File uploaded successfully!', 'info')
                else:
                    flash(f'Upload failed: {result}', 'danger')
                    return render_template('admin_gallery_form.html', action='add')
        
        # Handle thumbnail upload
        thumbnail_file = request.files.get('thumbnail_file')
        if thumbnail_file and thumbnail_file.filename:
            from ..services.cloudinary_service import cloudinary_service
            success, result = cloudinary_service.upload_file(
                thumbnail_file,
                folder='gallery/thumbnails',
                resource_type='image'
            )
            if success:
                thumbnail_url = result['url']
        
        if not title:
            flash('Title is required.', 'danger')
            return render_template('admin_gallery_form.html', action='add')
        
        if not media_url:
            flash('Please provide a media URL or upload a file.', 'danger')
            return render_template('admin_gallery_form.html', action='add')
        
        try:
            gallery_item = HomeGallery(
                title=title,
                description=description,
                media_type=media_type,
                media_url=media_url,
                thumbnail_url=thumbnail_url or None,
                source_type='admin',
                is_active=True,
                is_featured=is_featured,
                display_order=display_order,
                created_by=current_user.id
            )
            db.session.add(gallery_item)
            db.session.commit()
            flash(f'{media_type.title()} added to gallery successfully!', 'success')
            return redirect(url_for('admin.admin_gallery'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding gallery item: {str(e)}', 'danger')
    
    return render_template('admin_gallery_form.html', action='add')


@bp.route('/admin/gallery/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_gallery_edit(item_id):
    """Edit gallery item - supports both URL and file upload"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    item = HomeGallery.query.get_or_404(item_id)
    
    if request.method == 'POST':
        item.title = request.form.get('title', item.title).strip()
        item.description = request.form.get('description', '').strip()
        item.is_active = request.form.get('is_active') == 'on'
        item.is_featured = request.form.get('is_featured') == 'on'
        item.display_order = request.form.get('display_order', 0, type=int)
        
        input_method = request.form.get('input_method', 'url')
        
        # Handle file upload if chosen
        if input_method == 'upload':
            media_file = request.files.get('media_file')
            if media_file and media_file.filename:
                from ..services.cloudinary_service import cloudinary_service
                
                resource_type = 'video' if item.media_type == 'video' else 'image'
                folder = f'gallery/{item.media_type}s'
                
                success, result = cloudinary_service.upload_file(
                    media_file,
                    folder=folder,
                    resource_type=resource_type
                )
                
                if success:
                    item.media_url = result['url']
                    flash(f'File uploaded successfully!', 'info')
                else:
                    flash(f'Upload failed: {result}', 'danger')
        else:
            # Use URL from form
            new_url = request.form.get('media_url', '').strip()
            if new_url:
                item.media_url = new_url
        
        # Handle thumbnail
        thumbnail_file = request.files.get('thumbnail_file')
        if thumbnail_file and thumbnail_file.filename:
            from ..services.cloudinary_service import cloudinary_service
            success, result = cloudinary_service.upload_file(
                thumbnail_file,
                folder='gallery/thumbnails',
                resource_type='image'
            )
            if success:
                item.thumbnail_url = result['url']
        else:
            new_thumb = request.form.get('thumbnail_url', '').strip()
            item.thumbnail_url = new_thumb or None
        
        try:
            db.session.commit()
            flash('Gallery item updated successfully!', 'success')
            return redirect(url_for('admin.admin_gallery'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating gallery item: {str(e)}', 'danger')
    
    return render_template('admin_gallery_form.html', action='edit', item=item)


@bp.route('/admin/gallery/<int:item_id>/delete', methods=['POST'])
@login_required
def admin_gallery_delete(item_id):
    """Delete gallery item"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    item = HomeGallery.query.get_or_404(item_id)
    try:
        db.session.delete(item)
        db.session.commit()
        flash('Gallery item deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting gallery item: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_gallery'))


@bp.route('/admin/gallery/import-project', methods=['POST'])
@login_required
def admin_gallery_import_project():
    """Import media from student project to gallery"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    project_id = request.form.get('project_id', type=int)
    import_type = request.form.get('import_type', 'image')  # 'image' or 'video'
    
    project = StudentProject.query.get_or_404(project_id)
    
    try:
        if import_type == 'image' and project.image_url:
            # Check if already imported
            existing = HomeGallery.query.filter_by(
                source_type='student_project',
                source_project_id=project_id,
                media_type='image'
            ).first()
            if existing:
                flash('This image is already in the gallery.', 'warning')
                return redirect(url_for('admin.admin_gallery'))
            
            gallery_item = HomeGallery(
                title=f"{project.title} - Image",
                description=project.description[:200] if project.description else None,
                media_type='image',
                media_url=project.image_url,
                source_type='student_project',
                source_project_id=project_id,
                is_active=True,
                created_by=current_user.id
            )
            db.session.add(gallery_item)
            db.session.commit()
            flash(f'Image from "{project.title}" added to gallery!', 'success')
            
        elif import_type == 'video' and project.youtube_url:
            # Check if already imported
            existing = HomeGallery.query.filter_by(
                source_type='student_project',
                source_project_id=project_id,
                media_type='video'
            ).first()
            if existing:
                flash('This video is already in the gallery.', 'warning')
                return redirect(url_for('admin.admin_gallery'))
            
            gallery_item = HomeGallery(
                title=f"{project.title} - Video",
                description=project.description[:200] if project.description else None,
                media_type='video',
                media_url=project.youtube_url,
                thumbnail_url=project.image_url,
                source_type='student_project',
                source_project_id=project_id,
                is_active=True,
                created_by=current_user.id
            )
            db.session.add(gallery_item)
            db.session.commit()
            flash(f'Video from "{project.title}" added to gallery!', 'success')
        else:
            flash('No valid media found in this project.', 'warning')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error importing media: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_gallery'))


# ========== STUDENT VICTORIES ==========
@bp.route('/admin/victories')
@login_required
def admin_victories():
    """Admin page to manage student victories"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    victories = []
    try:
        victories = StudentVictory.query.order_by(
            StudentVictory.display_order.asc(),
            StudentVictory.achievement_date.desc()
        ).all()
    except Exception as e:
        db.session.rollback()
        flash(f'Victories table not found. Please create it first by visiting /admin/create-gallery-tables', 'warning')
    
    return render_template('admin_victories.html', victories=victories)


@bp.route('/admin/victories/add', methods=['GET', 'POST'])
@login_required
def admin_victory_add():
    """Add new student victory"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    students = User.query.filter_by(is_student=True).order_by(User.first_name.asc()).all()
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        achievement_type = request.form.get('achievement_type', '').strip()
        image_url = request.form.get('image_url', '').strip()
        achievement_date_str = request.form.get('achievement_date', '')
        student_id = request.form.get('student_id', type=int)
        student_name = request.form.get('student_name', '').strip()
        is_featured = request.form.get('is_featured') == 'on'
        display_order = request.form.get('display_order', 0, type=int)
        input_method = request.form.get('input_method', 'url')
        
        if not title or not description:
            flash('Title and description are required.', 'danger')
            return render_template('admin_victory_form.html', action='add', students=students)
        
        # Handle file upload
        if input_method == 'upload' and 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename:
                try:
                    from ..services.cloudinary_service import cloudinary_service
                    upload_result = cloudinary_service.upload_file(file, folder='victories')
                    if upload_result and 'secure_url' in upload_result:
                        image_url = upload_result['secure_url']
                except Exception as upload_error:
                    flash(f'File upload failed: {str(upload_error)}', 'warning')
        
        achievement_date = None
        if achievement_date_str:
            try:
                from datetime import datetime as dt
                achievement_date = dt.strptime(achievement_date_str, '%Y-%m-%d').date()
            except:
                pass
        
        try:
            victory = StudentVictory(
                title=title,
                description=description,
                achievement_type=achievement_type or None,
                image_url=image_url or None,
                achievement_date=achievement_date,
                student_id=student_id if student_id else None,
                student_name=student_name or None,
                is_active=True,
                is_featured=is_featured,
                display_order=display_order,
                created_by=current_user.id
            )
            db.session.add(victory)
            db.session.commit()
            flash('Student victory added successfully!', 'success')
            return redirect(url_for('admin.admin_victories'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding victory: {str(e)}', 'danger')
    
    return render_template('admin_victory_form.html', action='add', students=students)


@bp.route('/admin/victories/<int:victory_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_victory_edit(victory_id):
    """Edit student victory"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    victory = StudentVictory.query.get_or_404(victory_id)
    students = User.query.filter_by(is_student=True).order_by(User.first_name.asc()).all()
    
    if request.method == 'POST':
        victory.title = request.form.get('title', victory.title).strip()
        victory.description = request.form.get('description', victory.description).strip()
        victory.achievement_type = request.form.get('achievement_type', '').strip() or None
        victory.student_id = request.form.get('student_id', type=int) or None
        victory.student_name = request.form.get('student_name', '').strip() or None
        victory.is_active = request.form.get('is_active') == 'on'
        victory.is_featured = request.form.get('is_featured') == 'on'
        victory.display_order = request.form.get('display_order', 0, type=int)
        
        # Handle image - URL or upload
        input_method = request.form.get('input_method', 'url')
        if input_method == 'upload' and 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename:
                try:
                    from ..services.cloudinary_service import cloudinary_service
                    upload_result = cloudinary_service.upload_file(file, folder='victories')
                    if upload_result and 'secure_url' in upload_result:
                        victory.image_url = upload_result['secure_url']
                except Exception as upload_error:
                    flash(f'File upload failed: {str(upload_error)}', 'warning')
        else:
            victory.image_url = request.form.get('image_url', '').strip() or None
        
        achievement_date_str = request.form.get('achievement_date', '')
        if achievement_date_str:
            try:
                from datetime import datetime as dt
                victory.achievement_date = dt.strptime(achievement_date_str, '%Y-%m-%d').date()
            except:
                pass
        else:
            victory.achievement_date = None
        
        try:
            db.session.commit()
            flash('Student victory updated successfully!', 'success')
            return redirect(url_for('admin.admin_victories'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating victory: {str(e)}', 'danger')
    
    return render_template('admin_victory_form.html', action='edit', victory=victory, students=students)


@bp.route('/admin/victories/<int:victory_id>/delete', methods=['POST'])
@login_required
def admin_victory_delete(victory_id):
    """Delete student victory"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    victory = StudentVictory.query.get_or_404(victory_id)
    try:
        db.session.delete(victory)
        db.session.commit()
        flash('Student victory deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting victory: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_victories'))


# ==================== PRICING MANAGEMENT ====================

@bp.route('/admin/pricing')
@login_required
def admin_pricing():
    """Manage class pricing"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    # Get pricing data from database or use defaults
    pricing_data = ClassPricing.get_all_pricing()
    
    return render_template('admin_pricing.html', pricing_data=pricing_data)


@bp.route('/admin/pricing/<class_type>/update', methods=['POST'])
@login_required
def update_pricing(class_type):
    """Update pricing for a class type"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    price = request.form.get('price', type=float)
    name = request.form.get('name', '').strip()
    max_students = request.form.get('max_students', 1, type=int)
    features = request.form.get('features', '').strip()
    color = request.form.get('color', '#00d4ff').strip()
    is_popular = request.form.get('is_popular') == 'on'
    
    # Get default icon based on class type
    default_icons = {
        'individual': 'fa-user',
        'group': 'fa-users',
        'family': 'fa-home',
        'school': 'fa-school'
    }
    
    try:
        # Try to find existing pricing record
        pricing = ClassPricing.query.filter_by(class_type=class_type).first()
        
        if pricing:
            # Update existing
            pricing.price = price
            pricing.name = name
            pricing.max_students = max_students
            pricing.features = features
            pricing.color = color
            pricing.is_popular = is_popular
        else:
            # Create new
            pricing = ClassPricing(
                class_type=class_type,
                name=name,
                price=price,
                max_students=max_students,
                features=features,
                color=color,
                icon=default_icons.get(class_type, 'fa-user'),
                is_popular=is_popular,
                is_active=True,
                display_order={'individual': 1, 'group': 2, 'family': 3, 'school': 4}.get(class_type, 5)
            )
            db.session.add(pricing)
        
        db.session.commit()
        flash(f'{name} pricing updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating pricing: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_pricing'))


# ==================== SCHOOL MANAGEMENT ====================

@bp.route('/admin/individual-classes', methods=['GET', 'POST'])
@login_required
def admin_individual_classes():
    """View and manage all individual (one-on-one) students and classes"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    # Handle POST actions (deactivate class)
    if request.method == 'POST':
        enrollment_id = request.form.get('enrollment_id', type=int)
        action = request.form.get('action')
        
        if action == 'deactivate' and enrollment_id:
            enrollment = ClassEnrollment.query.get(enrollment_id)
            if enrollment:
                enrollment.status = 'rejected'  # Mark as rejected to deactivate
                db.session.commit()
                flash('Individual class has been deactivated.', 'success')
            return redirect(url_for('admin.admin_individual_classes'))
    
    # Get search and filter parameters
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    
    # Get all individual class enrollments
    query = ClassEnrollment.query.filter_by(class_type='individual', status='completed')
    
    # Apply search filter
    if search:
        from sqlalchemy import or_
        query = query.join(User).filter(
            or_(
                User.first_name.ilike(f'%{search}%'),
                User.last_name.ilike(f'%{search}%'),
                User.student_id.ilike(f'%{search}%'),
                ClassEnrollment.customer_name.ilike(f'%{search}%')
            )
        )
    
    enrollments = query.order_by(ClassEnrollment.enrolled_at.desc()).all()
    
    # Build list of individual class students
    individual_students = []
    for enrollment in enrollments:
        user = User.query.get(enrollment.user_id)
        if user:
            # Get the individual class
            individual_class = IndividualClass.query.get(enrollment.class_id)
            
            individual_students.append({
                'enrollment': enrollment,
                'user': user,
                'class': individual_class,
                'student_name': f"{user.first_name} {user.last_name}",
                'student_id': user.student_id or 'N/A',
                'class_name': individual_class.name if individual_class else 'Unknown',
                'payment_status': enrollment.status,
                'registration_date': enrollment.enrolled_at,
                'class_status': 'Active' if enrollment.status == 'completed' else 'Inactive'
            })
    
    # Apply status filter
    if status_filter:
        if status_filter == 'active':
            individual_students = [s for s in individual_students if s['class_status'] == 'Active']
        elif status_filter == 'inactive':
            individual_students = [s for s in individual_students if s['class_status'] == 'Inactive']
    
    return render_template('admin_individual_classes.html',
        individual_students=individual_students,
        search=search,
        status_filter=status_filter
    )


@bp.route('/admin/group-classes')
@login_required
def admin_group_classes():
    """View and manage group classes with multiple students"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    # Get search parameter
    search = request.args.get('search', '').strip()
    
    # Get all group classes
    query = GroupClass.query
    
    if search:
        from sqlalchemy import or_
        query = query.filter(
            or_(
                GroupClass.name.ilike(f'%{search}%'),
                GroupClass.description.ilike(f'%{search}%')
            )
        )
    
    group_classes = query.order_by(GroupClass.created_at.desc()).all()
    
    # Get enrollment info for each group class
    for group_class in group_classes:
        # Get all enrollments for this group class
        enrollments = ClassEnrollment.query.filter_by(
            class_id=group_class.id,
            class_type='group',
            status='completed'
        ).all()
        
        group_class.total_students = len(group_class.students) if group_class.students else 0
        group_class.class_status = 'Active' if group_class.total_students > 0 else 'Closed'
        group_class.enrollments = enrollments
    
    return render_template('admin_group_classes.html',
        group_classes=group_classes,
        search=search
    )


@bp.route('/admin/group-classes/<int:class_id>', methods=['GET', 'POST'])
@login_required
def admin_group_class_detail(class_id):
    """View detailed information about a specific group class"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    # Handle POST actions
    if request.method == 'POST':
        action = request.form.get('action')
        user_id = request.form.get('user_id', type=int)
        
        if action == 'remove_student' and user_id:
            group_class = GroupClass.query.get_or_404(class_id)
            user = User.query.get(user_id)
            if user and user in group_class.students:
                group_class.students.remove(user)
                db.session.commit()
                flash(f'Student {user.first_name} {user.last_name} has been removed from the group class.', 'success')
            return redirect(url_for('admin.admin_group_class_detail', class_id=class_id))
        
        if action == 'close_class':
            # Mark all enrollments as rejected to close the class
            enrollments = ClassEnrollment.query.filter_by(
                class_id=class_id,
                class_type='group',
                status='completed'
            ).all()
            for enrollment in enrollments:
                enrollment.status = 'rejected'
            db.session.commit()
            flash('Group class has been closed/paused.', 'success')
            return redirect(url_for('admin.admin_group_class_detail', class_id=class_id))
    
    group_class = GroupClass.query.get_or_404(class_id)
    
    # Get all students in this group class
    students = []
    for student in group_class.students:
        enrollment = ClassEnrollment.query.filter_by(
            user_id=student.id,
            class_id=class_id,
            class_type='group',
            status='completed'
        ).first()
        
        students.append({
            'user': student,
            'student_name': f"{student.first_name} {student.last_name}",
            'student_id': student.student_id or 'N/A',
            'payment_status': enrollment.status if enrollment else 'N/A',
            'registration_date': enrollment.enrolled_at if enrollment else None
        })
    
    return render_template('admin_group_class_detail.html',
        group_class=group_class,
        students=students
    )


@bp.route('/admin/family-classes')
@login_required
def admin_family_classes():
    """View and manage family-based registrations"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    # Get search parameter
    search = request.args.get('search', '').strip()
    
    # Get all family class enrollments
    query = ClassEnrollment.query.filter_by(class_type='family', status='completed')
    
    if search:
        from sqlalchemy import or_
        query = query.join(User).filter(
            or_(
                User.first_name.ilike(f'%{search}%'),
                User.last_name.ilike(f'%{search}%'),
                User.student_id.ilike(f'%{search}%'),
                ClassEnrollment.customer_name.ilike(f'%{search}%')
            )
        )
    
    enrollments = query.order_by(ClassEnrollment.enrolled_at.desc()).all()
    
    # Build family list
    families = []
    for enrollment in enrollments:
        user = User.query.get(enrollment.user_id)
        family_members = FamilyMember.query.filter_by(enrollment_id=enrollment.id).all()
        
        families.append({
            'enrollment': enrollment,
            'parent_user': user,
            'family_name': enrollment.customer_name or f"{user.first_name} {user.last_name}" if user else 'Unknown',
            'total_students': len(family_members) + 1,  # +1 for the parent/registrant
            'payment_status': enrollment.status,
            'registration_date': enrollment.enrolled_at,
            'family_members': family_members
        })
    
    return render_template('admin_family_classes.html',
        families=families,
        search=search
    )


@bp.route('/admin/family-classes/<int:enrollment_id>', methods=['GET', 'POST'])
@login_required
def admin_family_class_detail(enrollment_id):
    """View detailed information about a specific family class"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    # Handle POST actions
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'suspend_family':
            enrollment = ClassEnrollment.query.get_or_404(enrollment_id)
            enrollment.status = 'rejected'  # Mark as rejected to suspend
            db.session.commit()
            flash('Family access has been suspended.', 'success')
            return redirect(url_for('admin.admin_family_class_detail', enrollment_id=enrollment_id))
    
    enrollment = ClassEnrollment.query.get_or_404(enrollment_id)
    
    if enrollment.class_type != 'family':
        flash('This is not a family class enrollment.', 'danger')
        return redirect(url_for('admin.admin_family_classes'))
    
    # Get parent/registrant user
    parent_user = User.query.get(enrollment.user_id)
    
    # Get all family members
    family_members = FamilyMember.query.filter_by(enrollment_id=enrollment_id).all()
    
    # Build complete list of all family students
    all_family_students = []
    
    # Add parent/registrant
    if parent_user:
        all_family_students.append({
            'user': parent_user,
            'member': None,
            'student_name': f"{parent_user.first_name} {parent_user.last_name}",
            'student_id': parent_user.student_id or 'N/A',
            'assigned_class': 'Family Class',
            'class_status': 'Active' if enrollment.status == 'completed' else 'Inactive',
            'is_parent': True
        })
    
    # Add family members (they may or may not have user accounts)
    for member in family_members:
        # Try to find user account for this member
        member_user = None
        if member.member_email:
            member_user = User.query.filter_by(email=member.member_email).first()
        
        all_family_students.append({
            'user': member_user,
            'member': member,
            'student_name': member.member_name,
            'student_id': member_user.student_id if member_user else 'N/A',
            'assigned_class': 'Family Class',
            'class_status': 'Active' if enrollment.status == 'completed' else 'Inactive',
            'is_parent': False,
            'relationship': member.relationship
        })
    
    return render_template('admin_family_class_detail.html',
        enrollment=enrollment,
        parent_user=parent_user,
        all_family_students=all_family_students,
        family_members=family_members
    )


@bp.route('/admin/schools')
@login_required
def admin_schools():
    """View all registered schools"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    schools = School.query.order_by(School.created_at.desc()).all()
    
    # Get counts for each school
    for school in schools:
        school.student_count = RegisteredSchoolStudent.query.filter_by(school_id=school.id).count()
    
    return render_template('admin_schools.html', schools=schools)


@bp.route('/admin/schools/<int:school_id>')
@login_required
def admin_school_detail(school_id):
    """View school details and students"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    school = School.query.get_or_404(school_id)
    students = RegisteredSchoolStudent.query.filter_by(school_id=school_id).order_by(RegisteredSchoolStudent.created_at.desc()).all()
    
    return render_template('admin_school_detail.html', school=school, students=students)


@bp.route('/admin/schools/<int:school_id>/approve', methods=['POST'])
@login_required
def approve_school(school_id):
    """Approve a school registration"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    school = School.query.get_or_404(school_id)
    
    try:
        school.status = 'active'
        school.approved_at = datetime.utcnow()
        school.approved_by = current_user.id
        db.session.commit()
        flash(f'School "{school.school_name}" has been approved!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error approving school: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_school_detail', school_id=school_id))


@bp.route('/admin/schools/<int:school_id>/reject', methods=['POST'])
@login_required
def reject_school(school_id):
    """Reject a school registration"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    school = School.query.get_or_404(school_id)
    reason = request.form.get('reason', '').strip()
    
    try:
        school.status = 'rejected'
        db.session.commit()
        flash(f'School "{school.school_name}" has been rejected.', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error rejecting school: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_school_detail', school_id=school_id))
