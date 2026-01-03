from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user, logout_user, login_user

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
    ClassTime,
    StudentClassTimeSelection,
    IDCard,
    MonthlyPayment,
    SiteSettings,
)

bp = Blueprint('admin', __name__)


def require_admin():
    """Helper function to check admin authentication and redirect if not admin"""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        logout_user()
        return redirect(url_for('auth.login'))
    return None


def get_id_card_for_entity(entity_type, entity_id):
    """
    Helper function to get ID card for an entity
    Returns IDCard object or None if not found
    """
    try:
        # First try with is_active=True
        id_card = IDCard.query.filter_by(
            entity_type=entity_type,
            entity_id=entity_id,
            is_active=True
        ).first()
        
        # If not found, try without is_active filter (fallback)
        if not id_card:
            id_card = IDCard.query.filter_by(
                entity_type=entity_type,
                entity_id=entity_id
            ).first()
        
        return id_card
    except Exception as e:
        print(f"Error in get_id_card_for_entity: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def check_student_needs_id_card(user):
    """
    CRITICAL: Check if a student needs to see their ID card
    This is the SINGLE SOURCE OF TRUTH for ID card viewing requirement
    Returns (needs_card, id_card) tuple
    
    Rule: Approval is NOT COMPLETE until student views ID card
    """
    from flask import session
    if not user or user.is_admin:
        return False, None
    
    # Check if user has approved enrollment
    approved_enrollment = ClassEnrollment.query.filter_by(
        user_id=user.id,
        status='completed'
    ).first()
    
    if not approved_enrollment:
        # Also check for school students
        from ..models.schools import School, RegisteredSchoolStudent
        school = School.query.filter_by(user_id=user.id).first()
        if school and school.status == 'active' and school.payment_status == 'completed':
            # School admin - check for school ID card
            id_card = get_id_card_for_entity('school', school.id)
            if id_card:
                viewed_cards = session.get('id_card_viewed', [])
                if id_card.id not in viewed_cards:
                    return True, id_card
            return False, None
        
        # Check for registered school student
        registered_student = RegisteredSchoolStudent.query.filter_by(
            user_id=user.id
        ).first()
        if registered_student:
            id_card = get_id_card_for_entity('school_student', registered_student.id)
            if id_card:
                viewed_cards = session.get('id_card_viewed', [])
                if id_card.id not in viewed_cards:
                    return True, id_card
            return False, None
        
        return False, None
    
    # Determine entity type and ID
    entity_type = approved_enrollment.class_type
    entity_id = None
    
    if entity_type == 'individual':
        entity_id = user.id
    elif entity_type == 'group':
        entity_id = user.id
    elif entity_type == 'family':
        entity_id = approved_enrollment.id
    elif entity_type == 'school':
        # For school, check if user is school admin
        from ..models.schools import School
        school = School.query.filter_by(user_id=user.id).first()
        if school:
            entity_id = school.id
        else:
            return False, None
    
    # Get ID card - MUST exist if enrollment is approved
    id_card = get_id_card_for_entity(entity_type, entity_id)
    
    # DEBUG: Log if ID card not found
    if not id_card:
        print(f"WARNING: No ID card found for user {user.id}, entity_type={entity_type}, entity_id={entity_id}")
        # Try to find ANY ID card for this user (fallback)
        id_card = IDCard.query.filter_by(
            entity_type=entity_type,
            entity_id=entity_id
        ).first()  # Remove is_active filter as fallback
        if id_card:
            print(f"Found ID card without is_active filter: {id_card.id}")
    
    if id_card:
        # Check if ID card has been viewed in session
        viewed_cards = session.get('id_card_viewed', [])
        if id_card.id not in viewed_cards:
            # Student MUST see ID card - approval is incomplete
            print(f"Student {user.id} needs to view ID card {id_card.id}")
            return True, id_card
        else:
            print(f"Student {user.id} has already viewed ID card {id_card.id}")
    
    return False, None


def require_id_card_viewed(f):
    """
    CRITICAL Decorator to enforce ID card viewing on ALL student routes
    This MUST be the FIRST check - before any other logic
    Approval is NOT COMPLETE until student views ID card
    
    Made lazy to skip database access for health checks and status endpoints.
    """
    from functools import wraps
    from flask import redirect, url_for, session, request
    import traceback
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip database access for health checks, status endpoints, or API endpoints
        if request.endpoint in ['health.health_check', 'main.health'] or \
           request.path.startswith('/api/health') or \
           request.path in ['/health', '/status', '/ping']:
            return f(*args, **kwargs)
        
        # CRITICAL: Only check for authenticated non-admin users
        # If user is not authenticated, they can't have an ID card yet, so skip check
        if not current_user.is_authenticated:
            return f(*args, **kwargs)
        
        if not current_user.is_admin:
            try:
                # CRITICAL: Check if student needs to see ID card
                # This is the SINGLE SOURCE OF TRUTH
                needs_card, id_card = check_student_needs_id_card(current_user)
                
                if needs_card and id_card:
                    # FORCE redirect to ID card - override EVERYTHING
                    # This is the ONLY page student can access until ID card is viewed
                    print(f"REDIRECTING: User {current_user.id} to ID card {id_card.id}")
                    return redirect(url_for('admin.view_id_card', id_card_id=id_card.id))
                elif id_card is None:
                    # ID card doesn't exist - check if enrollment is approved
                    approved_enrollment = ClassEnrollment.query.filter_by(
                        user_id=current_user.id,
                        status='completed'
                    ).first()
                    if approved_enrollment:
                        # Enrollment is approved but no ID card found - this is an error
                        print(f"WARNING: User {current_user.id} has approved enrollment but no ID card found")
            except Exception as e:
                # If check fails, log the error but don't block
                print(f"ERROR in require_id_card_viewed decorator for user {current_user.id}: {str(e)}")
                traceback.print_exc()
        return f(*args, **kwargs)
    return decorated_function


# Removed /class-admin route - using existing /login page instead


@bp.route('/admin/add-family-system-id-column')
def add_family_system_id_column():
    """Add family_system_id column to class_enrollment table - ADMIN ONLY"""
    from sqlalchemy import text, inspect
    
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    try:
        # Check if column already exists
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('class_enrollment')]
        
        if 'family_system_id' in columns:
            return """
            <html>
            <head><title>Migration Complete</title>
            <style>body { font-family: Arial; padding: 20px; text-align: center; }</style></head>
            <body>
                <h1>✅ Column Already Exists</h1>
                <p><strong>family_system_id</strong> column already exists in class_enrollment table.</p>
                <p>No action needed.</p>
                <p><a href="/admin/dashboard" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">← Back to Admin</a></p>
            </body>
            </html>
            """
        
        # Add the column
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE class_enrollment ADD COLUMN family_system_id VARCHAR(20)'))
            conn.commit()
        
        return """
        <html>
        <head><title>Migration Complete</title>
        <style>body { font-family: Arial; padding: 20px; text-align: center; }</style></head>
        <body>
            <h1>✅ Migration Successful!</h1>
            <p><strong>family_system_id</strong> column added to class_enrollment table.</p>
            <p>Family class login system is now ready to use.</p>
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


@bp.route('/admin/add-group-system-id-column')
def add_group_system_id_column():
    """Add group_system_id column to class_enrollment table - ADMIN ONLY"""
    from sqlalchemy import text, inspect
    
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    try:
        # Check if column already exists
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('class_enrollment')]
        
        if 'group_system_id' in columns:
            return f"""
        <html>
        <head><title>Migration Complete</title>
        <style>body {{ font-family: Arial; padding: 20px; text-align: center; }}</style></head>
        <body>
            <h1>✅ Column Already Exists</h1>
            <p><strong>group_system_id</strong> column already exists in class_enrollment table.</p>
            <p>No migration needed.</p>
        </body>
        </html>
        """
        
        # Add the column
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE class_enrollment ADD COLUMN group_system_id VARCHAR(20)'))
            conn.commit()
        
        return f"""
        <html>
        <head><title>Migration Complete</title>
        <style>body {{ font-family: Arial; padding: 20px; text-align: center; }}</style></head>
        <body>
            <h1>✅ Migration Successful!</h1>
            <p><strong>group_system_id</strong> column added to class_enrollment table.</p>
            <p>Group System ID functionality is now ready to use.</p>
        </body>
        </html>
        """
        
    except Exception as e:
        return f"""
        <html>
        <head><title>Migration Error</title>
        <style>body {{ font-family: Arial; padding: 20px; text-align: center; }}</style></head>
        <body>
            <h1>❌ Migration Error</h1>
            <p>Error: {str(e)}</p>
        </body>
        </html>
        """, 500


@bp.route('/admin/add-profile-picture-column')
def add_profile_picture_column():
    """Add profile_picture column to user table - accessible without login for initial setup"""
    from sqlalchemy import inspect, text
    
    try:
        # Check if column already exists
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('user')]
        
        if 'profile_picture' in columns:
            return """
            <html>
            <head><title>Migration Complete</title>
            <style>body { font-family: Arial; padding: 20px; text-align: center; }</style></head>
            <body>
                <h1>✅ Column Already Exists</h1>
                <p><strong>profile_picture</strong> column already exists in user table.</p>
                <p>No action needed.</p>
            </body>
            </html>
            """
        
        # Add the column
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE "user" ADD COLUMN profile_picture VARCHAR(500)'))
            conn.commit()
        
        return """
        <html>
        <head><title>Migration Complete</title>
        <style>body { font-family: Arial; padding: 20px; text-align: center; }</style></head>
        <body>
            <h1>✅ Migration Successful!</h1>
            <p><strong>profile_picture</strong> column added to user table.</p>
            <p>Profile picture functionality is now ready to use.</p>
        </body>
        </html>
        """
        
    except Exception as e:
        return f"""
        <html>
        <head><title>Migration Error</title>
        <style>body {{ font-family: Arial; padding: 20px; text-align: center; }}</style></head>
        <body>
            <h1>❌ Migration Error</h1>
            <p>Error: {str(e)}</p>
        </body>
        </html>
        """, 500


@bp.route('/admin/add-timezone-columns')
def add_timezone_columns():
    """Add timezone columns to ClassTime and User tables - accessible without login for initial setup"""
    from sqlalchemy import text
    from flask import jsonify
    
    try:
        # Add timezone column to class_time table
        db.session.execute(text("""
            ALTER TABLE class_time 
            ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Kolkata'
        """))
        
        # Add timezone column to user table
        db.session.execute(text("""
            ALTER TABLE "user" 
            ADD COLUMN IF NOT EXISTS timezone VARCHAR(50)
        """))
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Timezone columns added successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/admin/add-school-student-system-id-column')
def add_school_student_system_id_column():
    """Add student_system_id column to school_student table - ADMIN ONLY"""
    from sqlalchemy import text, inspect
    
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    try:
        # Check if column already exists
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('school_student')]
        
        if 'student_system_id' in columns:
            return """
            <html>
            <head><title>Migration Complete</title>
            <style>body { font-family: Arial; padding: 20px; text-align: center; }</style></head>
            <body>
                <h1>✅ Column Already Exists</h1>
                <p><strong>student_system_id</strong> column already exists in school_student table.</p>
                <p>No action needed.</p>
                <p><a href="/admin/dashboard" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">← Back to Admin</a></p>
            </body>
            </html>
            """
        
        # Add the column
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE school_student ADD COLUMN student_system_id VARCHAR(20)'))
            conn.commit()
        
        return """
        <html>
        <head><title>Migration Complete</title>
        <style>body { font-family: Arial; padding: 20px; text-align: center; }</style></head>
        <body>
            <h1>✅ Migration Successful!</h1>
            <p><strong>student_system_id</strong> column added to school_student table.</p>
            <p>School student login system is now ready to use.</p>
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
                <p><a href="/admin/setup-group-class-columns">Update Group Class Columns</a></p>
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


@bp.route('/admin/setup-monthly-payment-table')
def setup_monthly_payment_table():
    """Create monthly_payment table if it doesn't exist - accessible without login for initial setup"""
    from sqlalchemy import text, inspect
    
    messages = []
    try:
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if 'monthly_payment' not in existing_tables:
            # Create the monthly_payment table
            create_table_sql = text("""
                CREATE TABLE monthly_payment (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES "user"(id),
                    enrollment_id INTEGER NOT NULL REFERENCES class_enrollment(id),
                    class_type VARCHAR(20) NOT NULL,
                    payment_month INTEGER NOT NULL,
                    payment_year INTEGER NOT NULL,
                    amount FLOAT NOT NULL,
                    receipt_url VARCHAR(500) NOT NULL,
                    receipt_filename VARCHAR(255),
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status VARCHAR(20) DEFAULT 'pending',
                    verified_by INTEGER REFERENCES "user"(id),
                    verified_at TIMESTAMP,
                    notes TEXT,
                    CONSTRAINT unique_monthly_payment UNIQUE (user_id, enrollment_id, payment_month, payment_year)
                )
            """)
            db.session.execute(create_table_sql)
            db.session.commit()
            messages.append("✅ Created monthly_payment table successfully!")
        else:
            messages.append("ℹ️ monthly_payment table already exists.")
    except Exception as e:
        db.session.rollback()
        messages.append(f"❌ Error: {str(e)}")
    
    messages_html = "".join([f"<li>{m}</li>" for m in messages])
    
    return f"""
    <html>
    <head><title>Monthly Payment Table Setup</title>
    <style>body {{ font-family: Arial; padding: 40px; text-align: center; background: #f0f0f0; }}
    .card {{ background: white; padding: 40px; border-radius: 15px; max-width: 600px; margin: 0 auto; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
    h1 {{ color: #28a745; }} a {{ color: #667eea; }} ul {{ text-align: left; }}</style></head>
    <body>
        <div class="card">
            <h1>Monthly Payment Table Setup</h1>
            <ul>{messages_html}</ul>
            <p><a href="/student/dashboard">Go to Student Dashboard</a></p>
            <p><a href="/">Go to Homepage</a></p>
        </div>
    </body>
    </html>
    """


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

        # Check and add title column
        try:
            result = db.session.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='learning_material' AND column_name='title'
            """))
            if not result.fetchone():
                db.session.execute(text("ALTER TABLE learning_material ADD COLUMN title VARCHAR(200)"))
                db.session.commit()
                messages.append("Added title column")
            else:
                messages.append("title column already exists")
        except Exception as e:
            db.session.rollback()
            messages.append(f"title error: {str(e)}")

        # Check and add actual_class_id column
        try:
            result = db.session.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='learning_material' AND column_name='actual_class_id'
            """))
            if not result.fetchone():
                db.session.execute(text("ALTER TABLE learning_material ADD COLUMN actual_class_id INTEGER"))
                db.session.commit()
                messages.append("Added actual_class_id column")
            else:
                messages.append("actual_class_id column already exists")
        except Exception as e:
            db.session.rollback()
            messages.append(f"actual_class_id error: {str(e)}")
        
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
    admin_check = require_admin()
    if admin_check:
        return admin_check
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


@bp.route('/admin/setup-group-class-columns')
def setup_group_class_columns():
    """Add new columns to group_class table - accessible without login for initial setup"""
    from sqlalchemy import text
    messages = []
    
    try:
        # Check and add class_type column
        try:
            result = db.session.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='group_class' AND column_name='class_type'
            """))
            if not result.fetchone():
                db.session.execute(text("ALTER TABLE group_class ADD COLUMN class_type VARCHAR(20) DEFAULT 'group'"))
                db.session.commit()
                messages.append("Added class_type column to group_class")
            else:
                messages.append("class_type column already exists in group_class")
        except Exception as e:
            db.session.rollback()
            messages.append(f"class_type column error: {str(e)}")
            
        # Check and add instructor_name column
        try:
            result = db.session.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='group_class' AND column_name='instructor_name'
            """))
            if not result.fetchone():
                db.session.execute(text("ALTER TABLE group_class ADD COLUMN instructor_name VARCHAR(100)"))
                db.session.commit()
                messages.append("Added instructor_name column to group_class")
            else:
                messages.append("instructor_name column already exists in group_class")
        except Exception as e:
            db.session.rollback()
            messages.append(f"instructor_name column error: {str(e)}")
            
        messages_html = "".join([f"<li>{m}</li>" for m in messages])
        
        return f"""
        <html>
        <head><title>Group Class Columns Updated</title>
        <style>body {{ font-family: Arial; padding: 40px; text-align: center; background: #f0f0f0; }}
        .card {{ background: white; padding: 40px; border-radius: 15px; max-width: 600px; margin: 0 auto; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
        h1 {{ color: #28a745; }} a {{ color: #667eea; }} ul {{ text-align: left; }}</style></head>
        <body>
            <div class="card">
                <h1>✅ Group Class Table Updated!</h1>
                <ul>{messages_html}</ul>
                <p><a href="/admin/dashboard">Go to Admin Dashboard</a></p>
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


@bp.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Admin dashboard - requires admin authentication"""
    from ..extensions import db
    db.session.rollback()  # Ensure clean transaction state at start
    
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        logout_user()
        return redirect(url_for('auth.login'))
    
    # Note: Share materials functionality has been moved to individual admin pages:
    # - /admin/schools (for schools)
    # - /admin/individual-classes (for individual classes)
    # - /admin/group-classes (for group classes)
    # - /admin/family-classes (for family classes)
    
    # Old POST handler removed - share materials now handled in individual admin pages
    # Get all data for the dashboard
    try:
        students = User.query.filter_by(is_student=True).all()
    except Exception:
        db.session.rollback()
        students = []
    individual_students = students
    
    # Get course orders
    try:
        course_orders = Purchase.query.order_by(Purchase.purchased_at.desc()).limit(50).all()
    except Exception:
        db.session.rollback()
        course_orders = []
    
    # Get enrollments
    try:
        enrollments = ClassEnrollment.query.order_by(ClassEnrollment.enrolled_at.desc()).limit(50).all()
    except Exception:
        db.session.rollback()
        enrollments = []
    
    # Get robotics count
    try:
        robotics_count = RoboticsProjectSubmission.query.count()
    except Exception:
        db.session.rollback()
        robotics_count = 0
    
    # Get all classes
    try:
        all_group_classes = GroupClass.query.all()
    except Exception:
        db.session.rollback()
        all_group_classes = []
    
    # Filter school-specific classes for the dashboard
    school_classes_latest = [c for c in all_group_classes if hasattr(c, 'class_type') and c.class_type == 'school']
    
    try:
        all_individual_classes_legacy = IndividualClass.query.all()
    except Exception:
        db.session.rollback()
        all_individual_classes_legacy = []
    
    # Get Schools (entities) for school type - NOT enrollments
    schools_data = []
    try:
        schools = School.query.filter_by(status='active').order_by(School.school_name).all()
        for school in schools:
            # Count registered students for this school
            student_count = RegisteredSchoolStudent.query.filter_by(school_id=school.id).count()
            
            # Get classes this school has joined
            school_classes = []
            if school.user_id:
                enrollments = ClassEnrollment.query.filter_by(
                    user_id=school.user_id,
                    class_type='school',
                    status='completed'
                ).all()
                school_classes = [e.class_id for e in enrollments]
            
            schools_data.append({
                'id': school.id,
                'school_name': school.school_name,
                'school_system_id': school.school_system_id,
                'student_count': student_count,
                'class_ids': school_classes
            })
    except Exception:
        db.session.rollback()
    
    # Get Families (entities) for family type - NOT enrollments
    families_data = []
    try:
        family_enrollments = ClassEnrollment.query.filter_by(
            class_type='family',
            status='completed'
        ).all()
        # Group by main user to create family entities
        families_dict = {}
        for enrollment in family_enrollments:
            main_user = User.query.get(enrollment.user_id)
            if main_user:
                # Use user_id as family identifier
                if enrollment.user_id not in families_dict:
                    member_count = FamilyMember.query.filter_by(enrollment_id=enrollment.id).count()
                    families_dict[enrollment.user_id] = {
                        'id': enrollment.user_id,  # Use user_id as family ID
                        'family_name': f"{main_user.first_name} {main_user.last_name}'s Family",
                        'member_count': member_count,
                        'class_ids': []
                    }
                families_dict[enrollment.user_id]['class_ids'].append(enrollment.class_id)
        
        families_data = list(families_dict.values())
    except Exception:
        db.session.rollback()
    
    # Get group classes with student counts
    group_classes_data = []
    try:
        # Only show classes with type 'group' or default 'group'
        for class_obj in all_group_classes:
            if hasattr(class_obj, 'class_type') and class_obj.class_type == 'group':
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
    except Exception:
        db.session.rollback()
    
    # Materials removed from dashboard - now shown in individual admin pages
    
    # Get all individual classes for the dashboard
    all_individual_classes = []
    try:
        # Check if class_type column exists
        individual_classes_new = GroupClass.query.filter_by(class_type='individual').all()
        all_individual_classes = individual_classes_new + all_individual_classes_legacy
    except Exception:
        db.session.rollback()
        all_individual_classes = all_individual_classes_legacy

    return render_template('admin_dashboard.html',
        students=students,
        individual_students=individual_students,
        all_group_classes=all_group_classes,
        all_individual_classes=all_individual_classes,
        school_classes_latest=school_classes_latest,
        schools_data=schools_data,  # Changed from school_enrollments_data
        families_data=families_data,  # Changed from family_enrollments_data
        group_classes_data=group_classes_data,
        course_orders=course_orders,
        enrollments=enrollments,
        robotics_count=robotics_count
    )


@bp.route('/admin/users')
@login_required
def admin_users():
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    db.session.rollback()  # Ensure clean transaction state
    from flask import request
    search = request.args.get('search', '')
    try:
        query = User.query
        if search:
            query = query.filter(
                User.email.contains(search) | 
                User.first_name.contains(search) | 
                User.last_name.contains(search)
            )
        users = query.order_by(User.id.desc()).all()
    except Exception:
        db.session.rollback()
        users = []
    return render_template('admin_users.html', users=users, search_term=search)


@bp.route('/admin/create-class', methods=['GET', 'POST'])
@login_required
def create_class():
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    from flask import request
    import json
    
    if request.method == 'POST':
        class_type = request.form.get('class_type', '').strip()
        existing_class_id = request.form.get('existing_class_id', '').strip()
        
        if not class_type:
            flash('Class Type is required.', 'danger')
            # Get all existing classes for dropdown
            all_classes = GroupClass.query.order_by(GroupClass.name).all()
            return render_template('create_class.html', all_classes=all_classes)
        
        # If existing class is selected, create a new class with same content but new class_type
        if existing_class_id and existing_class_id != 'none':
            try:
                existing_class = GroupClass.query.get(int(existing_class_id))
                if existing_class:
                    # Check if class with same name and new type already exists
                    existing_same_type = GroupClass.query.filter_by(
                        name=existing_class.name,
                        class_type=class_type
                    ).first()
                    
                    if existing_same_type:
                        flash(f'Class "{existing_class.name}" already exists for {class_type} type.', 'info')
                    else:
                        # Create new class with same content but new class_type
                        new_class = GroupClass(
                            name=existing_class.name,
                            description=existing_class.description,
                            teacher_id=current_user.id,
                            class_type=class_type,
                            instructor_name=existing_class.instructor_name,
                            curriculum=existing_class.curriculum,
                            max_students=existing_class.max_students if existing_class.max_students else 100
                        )
                        db.session.add(new_class)
                        db.session.commit()
                        flash(f'Class "{existing_class.name}" created for {class_type} type! It will now appear in {class_type} classes.', 'success')
                    
                    # Redirect to the correct management section
                    if class_type == 'school':
                        return redirect(url_for('admin.admin_schools'))
                    elif class_type == 'individual':
                        return redirect(url_for('admin.admin_individual_classes'))
                    elif class_type == 'group':
                        return redirect(url_for('admin.admin_group_classes'))
                    elif class_type == 'family':
                        return redirect(url_for('admin.admin_family_classes'))
                    return redirect(url_for('admin.admin_dashboard'))
            except (ValueError, AttributeError) as e:
                flash(f'Error using existing class: {str(e)}', 'danger')
        
        # Create new class
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        instructor_name = request.form.get('instructor_name', '').strip()
        
        # Get curriculum items
        curriculum_items = request.form.getlist('curriculum[]')
        curriculum_text = '\n'.join([item.strip() for item in curriculum_items if item.strip()])
        
        if not name or not description:
            flash('Name and Description are required when creating a new class.', 'danger')
            all_classes = GroupClass.query.order_by(GroupClass.name).all()
            return render_template('create_class.html', all_classes=all_classes)
        
        try:
            # Create the class using GroupClass as the unified model
            new_class = GroupClass(
                name=name,
                description=description,
                teacher_id=current_user.id,
                class_type=class_type,
                instructor_name=instructor_name,
                curriculum=curriculum_text if curriculum_text else None,
                max_students=100 # High default as limits are managed elsewhere
            )
            
            db.session.add(new_class)
            db.session.commit()
            flash(f'Class "{name}" created successfully!', 'success')
            
            # Redirect to the correct management section
            if class_type == 'school':
                return redirect(url_for('admin.admin_schools'))
            elif class_type == 'individual':
                return redirect(url_for('admin.admin_individual_classes'))
            elif class_type == 'group':
                return redirect(url_for('admin.admin_group_classes'))
            elif class_type == 'family':
                return redirect(url_for('admin.admin_family_classes'))
            
            return redirect(url_for('admin.admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            # If the error is about missing columns, try to fix it automatically
            if 'column "class_type" of relation "group_class" does not exist' in str(e) or 'column "curriculum" of relation "group_class" does not exist' in str(e):
                try:
                    from sqlalchemy import text
                    db.session.execute(text('ALTER TABLE group_class ADD COLUMN IF NOT EXISTS class_type VARCHAR(20) DEFAULT \'group\''))
                    db.session.execute(text('ALTER TABLE group_class ADD COLUMN IF NOT EXISTS instructor_name VARCHAR(100)'))
                    db.session.execute(text('ALTER TABLE group_class ADD COLUMN IF NOT EXISTS curriculum TEXT'))
                    db.session.commit()
                    flash('Database structure updated. Please try creating the class again.', 'info')
                except Exception as db_e:
                    flash(f'Database update failed: {str(db_e)}', 'danger')
            else:
                flash(f'Error creating class: {str(e)}', 'danger')
            all_classes = GroupClass.query.order_by(GroupClass.name).all()
            return render_template('create_class.html', all_classes=all_classes)
    
    # GET request - show form with existing classes
    all_classes = GroupClass.query.order_by(GroupClass.name).all()
    return render_template('create_class.html', all_classes=all_classes)


@bp.route('/admin/classes')
@login_required
def admin_classes():
    """View all classes"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    # Legacy individual classes are kept for display, but new classes use GroupClass
    try:
        individual_classes = IndividualClass.query.all()
    except Exception:
        db.session.rollback()
        individual_classes = []
        
    # Explicitly show only classes categorized by type
    try:
        group_classes = GroupClass.query.filter_by(class_type='group').all()
    except Exception:
        db.session.rollback()
        group_classes = []
        
    try:
        family_classes = GroupClass.query.filter_by(class_type='family').all()
    except Exception:
        db.session.rollback()
        family_classes = []
        
    try:
        school_classes = GroupClass.query.filter_by(class_type='school').all()
    except Exception:
        db.session.rollback()
        school_classes = []
        
    try:
        new_individual_classes = GroupClass.query.filter_by(class_type='individual').all()
    except Exception:
        db.session.rollback()
        new_individual_classes = []
    
    all_classes = group_classes + individual_classes + family_classes + school_classes + new_individual_classes
    
    return render_template('admin_classes.html',
        classes=all_classes,
        group_classes=group_classes,
        family_classes=family_classes,
        school_classes=school_classes,
        individual_classes=individual_classes + new_individual_classes
    )


@bp.route('/admin/edit-class/<int:class_id>', methods=['GET', 'POST'])
@bp.route('/admin/edit-class/<class_type>/<int:class_id>', methods=['GET', 'POST'])  # legacy URL
@login_required
def edit_class(class_id, class_type=None):
    """Edit a class"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    from flask import request
    
    # Prefer unified GroupClass; fall back to legacy IndividualClass for older records
    class_obj = GroupClass.query.get(class_id) or IndividualClass.query.get_or_404(class_id)
    
    if request.method == 'POST':
        class_obj.name = request.form.get('name', class_obj.name).strip()
        class_obj.description = request.form.get('description', class_obj.description).strip()
        
        if hasattr(class_obj, 'class_type'):
            class_obj.class_type = request.form.get('class_type', class_obj.class_type)
        
        if hasattr(class_obj, 'instructor_name'):
            class_obj.instructor_name = request.form.get('instructor_name', '')
        
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
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
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
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
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
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    enrollment = ClassEnrollment.query.get_or_404(enrollment_id)
    
    # Get class info
    class_obj = GroupClass.query.get(enrollment.class_id) or IndividualClass.query.get(enrollment.class_id)
    
    # Get user info
    user = User.query.get(enrollment.user_id)
    
    # Get ID card for this enrollment/user
    id_card = None
    if enrollment.class_type == 'individual' and user:
        id_card = get_id_card_for_entity('individual', user.id)
    elif enrollment.class_type == 'group' and user:
        id_card = get_id_card_for_entity('group', user.id)
    elif enrollment.class_type == 'family':
        id_card = get_id_card_for_entity('family', enrollment.id)
    
    return render_template('view_enrollment.html',
        enrollment=enrollment,
        class_obj=class_obj,
        user=user,
        id_card=id_card
    )


@bp.route('/admin/enrollment/<int:enrollment_id>/approve', methods=['POST'])
@login_required
def approve_enrollment(enrollment_id):
    """Approve an enrollment and generate Student ID"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    enrollment = ClassEnrollment.query.get_or_404(enrollment_id)
    user = User.query.get(enrollment.user_id)
    
    if not user:
        flash('User not found for this enrollment.', 'danger')
        return redirect(url_for('admin.admin_enrollments'))
    
    # Generate System IDs and Student IDs based on class type
    if enrollment.class_type == 'group':
        # Generate Group System ID if not exists
        try:
            if not enrollment.group_system_id:
                from ..models.classes import generate_group_system_id
                enrollment.group_system_id = generate_group_system_id()
        except Exception as e:
            # Handle case where group_system_id column doesn't exist yet
            if 'group_system_id' in str(e).lower() or 'column' in str(e).lower():
                flash('Database migration required. Please visit /admin/add-group-system-id-column first.', 'warning')
                return redirect(url_for('admin.admin_enrollments'))
            raise
        
        # CRITICAL: Group students should NOT have individual student IDs (STU-XXXXX)
        # They only use Group System ID (GRO-XXXXX)
        # Remove any existing student_id if this user is only in group classes
        user.class_type = 'group'
        
        # Check if user has any individual class enrollments
        individual_enrollment = ClassEnrollment.query.filter_by(
            user_id=user.id,
            class_type='individual',
            status='completed'
        ).first()
        
        # Only remove student_id if user has NO individual enrollments
        if not individual_enrollment and user.student_id:
            # User is only in group classes - remove individual student ID
            user.student_id = None
            db.session.flush()
        
        db.session.flush()  # Ensure changes are saved before ID card generation
        flash(f'Group System ID: {enrollment.group_system_id}', 'info')
    elif enrollment.class_type == 'family':
        # Generate Family System ID if not exists
        try:
            if not enrollment.family_system_id:
                from ..models.classes import generate_family_system_id
                enrollment.family_system_id = generate_family_system_id()
        except Exception as e:
            # Handle case where family_system_id column doesn't exist yet
            if 'family_system_id' in str(e).lower() or 'column' in str(e).lower():
                flash('Database migration required. Please visit /admin/add-family-system-id-column first.', 'warning')
                return redirect(url_for('admin.admin_enrollments'))
            raise
        
        # CRITICAL: Generate Student ID if not exists
        # Always check database uniqueness before assigning
        if not user.student_id:
            from ..models.classes import generate_student_id_for_class
            new_student_id = generate_student_id_for_class('family')
            
            # Double-check: Ensure this ID is truly unique
            existing_user = User.query.filter_by(student_id=new_student_id).first()
            if existing_user and existing_user.id != user.id:
                # ID collision - generate a new one
                new_student_id = generate_student_id_for_class('family')
            
            user.student_id = new_student_id
            user.class_type = 'family'
            db.session.flush()  # Ensure it's saved before ID card generation
            flash(f'Family System ID: {enrollment.family_system_id}, Student ID: {user.student_id}', 'info')
    elif enrollment.class_type == 'individual':
        # CRITICAL: Generate Student ID if not exists
        # Always check database uniqueness before assigning
        if not user.student_id:
            from ..models.classes import generate_student_id_for_class
            new_student_id = generate_student_id_for_class('individual')
            
            # Double-check: Ensure this ID is truly unique
            existing_user = User.query.filter_by(student_id=new_student_id).first()
            if existing_user and existing_user.id != user.id:
                # ID collision - generate a new one
                new_student_id = generate_student_id_for_class('individual')
            
            user.student_id = new_student_id
            user.class_type = 'individual'
            db.session.flush()  # Ensure it's saved before ID card generation
            flash(f'Student ID generated: {user.student_id}', 'info')
    
    # Add student to class based on class type
    if enrollment.class_type == 'individual':
        from ..models.classes import IndividualClass, individual_class_students
        class_obj = GroupClass.query.filter_by(id=enrollment.class_id, class_type='individual').first() or \
                    IndividualClass.query.get(enrollment.class_id)
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
    elif enrollment.class_type == 'school':
        # For school enrollments, just mark as completed - don't add to group_class.students
        # Schools manage their own students through SchoolStudent model
        pass
    elif enrollment.class_type == 'family':
        # Family classes also use enrollment-based approach
        pass
    
    enrollment.status = 'completed'
    
    # CRITICAL: Generate ID Card IMMEDIATELY after approval
    try:
        from ..models.id_cards import (
            generate_individual_student_id_card,
            generate_group_student_id_card,
            generate_family_id_card
        )
        
        # Get class object for ID card generation
        if enrollment.class_type == 'individual':
            class_obj = GroupClass.query.filter_by(id=enrollment.class_id, class_type='individual').first() or \
                        IndividualClass.query.get(enrollment.class_id)
            if class_obj:
                generate_individual_student_id_card(enrollment, user, class_obj, current_user.id)
        elif enrollment.class_type == 'group':
            class_obj = GroupClass.query.get(enrollment.class_id)
            if class_obj:
                generate_group_student_id_card(enrollment, user, class_obj, current_user.id)
        elif enrollment.class_type == 'family':
            class_obj = GroupClass.query.filter_by(id=enrollment.class_id, class_type='family').first()
            if class_obj:
                generate_family_id_card(enrollment, user, class_obj, current_user.id)
    except Exception as e:
        print(f"Error generating ID card: {e}")
        # Don't fail approval if ID card generation fails, but log it
    
    try:
        db.session.commit()
        # For group enrollments, only show group system ID, not individual student ID
        if enrollment.class_type == 'group':
            flash(f'Enrollment approved! Group System ID: {enrollment.group_system_id}. ID Card generated. Student will be redirected to view ID card immediately.', 'success')
        else:
            student_id_msg = f'Student ID: {user.student_id}' if user.student_id else ''
            flash(f'Enrollment approved! {student_id_msg}. ID Card generated. Student will be redirected to view ID card immediately.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_enrollments'))


@bp.route('/admin/enrollment/<int:enrollment_id>/reject', methods=['POST'])
@login_required
def reject_enrollment(enrollment_id):
    """Reject an enrollment"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
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
def student_dashboard():
    from datetime import datetime, date, timedelta
    from flask import flash, session
    from calendar import monthrange
    
    # NO LOGIN REQUIRED - Get user from session or current_user
    user = None
    user_id = None
    
    # Check if user is logged in (for admin or logged-in users)
    if current_user.is_authenticated:
        user = current_user
        user_id = current_user.id
    else:
        # Get user from session (set by entry forms or ID card)
        user_id = session.get('student_user_id') or session.get('user_id')
        if user_id:
            user = User.query.get(user_id)
    
    # If no user found, redirect to entry form
    if not user:
        flash('Please enter your Name and System ID to access your classroom.', 'info')
        return redirect(url_for('main.index'))
    
    # Check if user has any CONFIRMED enrollment (status = 'completed')
    has_confirmed_enrollment = ClassEnrollment.query.filter_by(
        user_id=user_id,
        status='completed'
    ).first() is not None
    
    # Set session variable for navbar (hide all links except BuXin Academy logo)
    if has_confirmed_enrollment:
        session['is_registered_student'] = True
    else:
        session['is_registered_student'] = False
    
    # Check if user is a school admin with active status and completed payment
    is_approved_school = False
    if getattr(user, 'is_school_admin', False) or getattr(user, 'is_school_student', False):
        school = School.query.filter_by(user_id=user_id).first()
        if school and school.status == 'active' and school.payment_status == 'completed':
            is_approved_school = True
    
    if not has_confirmed_enrollment and not getattr(user, 'is_admin', False) and not is_approved_school:
        # Check if they have pending enrollment
        has_pending = ClassEnrollment.query.filter_by(
            user_id=user_id,
            status='pending'
        ).first() is not None
        
        if has_pending:
            flash('Your class enrollment is pending approval. Please wait for admin confirmation.', 'warning')
        else:
            flash('You need to enroll in a class first. Please register for a class to access your dashboard.', 'info')
        return redirect(url_for('main.index'))
    
    purchases = Purchase.query.filter_by(user_id=user_id, status='completed').all()
    projects = StudentProject.query.filter_by(student_id=user_id).all()
    enrollments = ClassEnrollment.query.filter_by(user_id=user_id, status='completed').all()
    
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
            students = []
            attendance_students = []
            
            if cls['class_type'] == 'school':
                # CRITICAL FIX: For school classes, ONLY show registered SchoolStudent records
                # Do NOT include the school admin user in attendance - only registered students
                current_school_enrollment = cls['enrollment']
                
                # For class_students, we can include the admin user (for other purposes)
                # But for attendance, we ONLY want registered school students
                students = []
                if current_school_enrollment and current_school_enrollment.user_id == user_id:
                    student = User.query.get(current_school_enrollment.user_id)
                if student:
                    students.append({
                        'id': student.id,
                        'name': f"{student.first_name} {student.last_name}",
                        'username': student.username,
                            'type': 'user'  # School admin user (for class_students only, not attendance)
                        })
                
                # CRITICAL: Attendance should ONLY show registered SchoolStudent records
                # Filter by class_id, enrollment_id, and registered_by to ensure strict school isolation
                registered_school_students = SchoolStudent.query.filter_by(
                    class_id=cls['id'],  # THIS class only
                    enrollment_id=current_school_enrollment.id,  # THIS school's enrollment only
                    registered_by=user_id  # Only students registered by this school admin
                ).order_by(SchoolStudent.student_name).all()
                
                # Attendance list: ONLY registered school students (no admin user)
                attendance_students = []
                for reg_student in registered_school_students:
                    attendance_students.append({
                        'id': f"school_student_{reg_student.id}",  # Unique identifier
                        'name': reg_student.student_name,
                        'username': None,
                        'type': 'school_student',
                        'school_student_id': reg_student.id,
                        'school_name': reg_student.school_name
                    })
                
                class_students[cls['id']] = students
            else:
                # For group and family classes, get all enrollments (they're not school-specific)
                class_enrollments = ClassEnrollment.query.filter_by(
                    class_id=cls['id'],  # THIS class only
                    class_type=cls['class_type'],  # Same class type
                    status='completed'  # Only completed enrollments
                ).all()
                
                for enr in class_enrollments:
                    student = User.query.get(enr.user_id)
                    if student:
                        students.append({
                            'id': student.id,
                            'name': f"{student.first_name} {student.last_name}",
                            'username': student.username,
                            'type': 'user'  # Regular enrolled user
                        })
                
                attendance_students = list(students)  # Start with enrolled users
                
                if cls['class_type'] == 'family':
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
                
                class_students[cls['id']] = students
            
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
            Attendance.student_id == user_id,
            Attendance.class_id == cls['id'],
            Attendance.attendance_date >= month_start,
            Attendance.attendance_date <= month_end
        ).order_by(Attendance.attendance_date.desc()).all()
        
        attendance_records[cls['id']] = attendance
        
        # For group/family/school classes, get all students' attendance
        if cls['class_type'] in ['group', 'family', 'school']:
            if cls['class_type'] == 'school':
                # CRITICAL: For school classes, only get attendance for students from THIS school
                # Get list of valid student IDs (school admin + registered school students)
                valid_student_ids = [user_id]  # School admin
                
                # Add registered school students for this class
                registered_students = SchoolStudent.query.filter_by(
                    class_id=cls['id'],
                    enrollment_id=cls['enrollment'].id,
                    registered_by=user_id
                ).all()
                
                # For school students, we can't directly query by student_id since they're not Users
                # Instead, filter attendance by class_id and then filter results
                all_attendance = Attendance.query.filter(
                    Attendance.class_id == cls['id'],
                    Attendance.class_type == 'school',
                    Attendance.attendance_date >= month_start,
                    Attendance.attendance_date <= month_end
                ).order_by(Attendance.attendance_date.desc()).all()
                
                # Filter to only include attendance for valid students
                # For User-based attendance, check if student_id is in valid_student_ids
                # For SchoolStudent attendance, we'd need a different approach (they don't have user_id)
                # For now, only include attendance for the school admin user
                filtered_attendance = [
                    att for att in all_attendance 
                    if att.student_id in valid_student_ids
                ]
                all_class_attendance[cls['id']] = filtered_attendance
            else:
                # For group and family classes, get all attendance (not school-specific)
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
            Attendance.student_id == user_id,
            Attendance.class_id == cls['id'],
            Attendance.attendance_date == today
        ).first()
        today_attendance[cls['id']] = today_att
        
        # Get today's attendance for all students in this class
        # CRITICAL: Only get attendance for students registered in THIS specific class
        if cls['class_type'] in ['group', 'family', 'school']:
            class_today_attendance = {}
            
            if cls['class_type'] == 'school':
                # CRITICAL: For school classes, get attendance for registered school students
                # Get the school enrollment
                school_enrollment = cls['enrollment']
                if school_enrollment:
                    # Get all registered school students for this class
                    registered_students = SchoolStudent.query.filter_by(
                        class_id=cls['id'],
                        enrollment_id=school_enrollment.id,
                        registered_by=user_id
                    ).all()
                    
                    # Get attendance for each registered school student
                    for reg_student in registered_students:
                        # Find attendance record with school_student_id in notes
                        att = Attendance.query.filter(
                            Attendance.student_id == user_id,  # School admin as proxy
                            Attendance.class_id == cls['id'],
                            Attendance.class_type == 'school',
                            Attendance.attendance_date == today,
                            Attendance.notes.like(f'%school_student_{reg_student.id}%')
                        ).first()
                        
                        if att:
                            # Use special key format for school students
                            class_today_attendance[f'school_student_{reg_student.id}'] = att
                    # Note: SchoolStudent type students don't have user_id, so they can't have Attendance records
                    # They are view-only in the attendance list
            else:
                # For group and family classes, get attendance for all enrolled users
                for student in class_students.get(cls['id'], []):
                    if student['type'] == 'user':
                        att = Attendance.query.filter(
                            Attendance.student_id == student['id'],
                            Attendance.class_id == cls['id'],  # THIS class only
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
            # CRITICAL: Only get students registered for THIS specific class and THIS school
            # Strict filtering to prevent cross-class or cross-school contamination
            students = SchoolStudent.query.filter_by(
                class_id=cls['id'],  # THIS class only
                enrollment_id=cls['enrollment'].id,  # THIS enrollment only
                registered_by=user_id  # Only students registered by this school admin
            ).order_by(SchoolStudent.student_name).all()
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
                        LearningMaterial.class_id == f"student_{user_id}",
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
                # Materials shared to this school class
                # Format: "school_{class_id}" (as set in material sharing)
                class_materials = LearningMaterial.query.filter(
                    LearningMaterial.class_type == 'school',
                    LearningMaterial.actual_class_id == cls['id']
                ).all()
                materials.extend(class_materials)
            elif cls['class_type'] == 'family':
                # Materials shared to this family enrollment
                # Materials are saved with class_id=f"family_{enrollment.class_id}" and actual_class_id=enrollment.class_id
                class_materials = LearningMaterial.query.filter(
                    LearningMaterial.class_type == 'family',
                    LearningMaterial.actual_class_id == cls['id']
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
    
    # Get school information if user is a school mentor
    school = None
    if getattr(user, 'is_school_admin', False):
        school = School.query.filter_by(user_id=user_id).first()
    
    # Get student's timezone (default to browser timezone or India if not set)
    student_timezone = getattr(user, 'timezone', None) or 'Asia/Kolkata'
    
    # Get class times for each enrolled class type
    class_times_by_type = {}
    student_time_selections = {}
    active_live_class = None  # Will contain the enrollment and class time if live class is active
    
    # Get current time in student's timezone
    import pytz
    from datetime import datetime, time as dt_time
    student_tz = pytz.timezone(student_timezone)
    current_datetime = datetime.now(student_tz)
    current_time = current_datetime.time()
    current_day = current_datetime.strftime('%A')  # Monday, Tuesday, etc.
    
    for enrollment in enrollments:
        class_type = enrollment.class_type
        if class_type not in class_times_by_type:
            # Get active time slots for this class type
            times = ClassTime.query.filter_by(
                class_type=class_type,
                is_active=True
            ).order_by(ClassTime.day, ClassTime.start_time).all()
            class_times_by_type[class_type] = times
        
        # Get student's time selection for this enrollment
        selection = StudentClassTimeSelection.query.filter_by(
            enrollment_id=enrollment.id
        ).first()
        if selection:
            student_time_selections[enrollment.id] = selection
        
        # Check if Live Class should be active for this enrollment
        if class_type in ['individual', 'family']:
            # For Individual/Family: Check if student has selected a time and it matches current time
            if selection and selection.class_time:
                class_time = selection.class_time
                # IMPORTANT: Verify class_time matches this enrollment's class_id
                # If class_time.class_id is None, it applies to all classes of this type
                # If class_time.class_id is set, it must match the enrollment's class_id
                if class_time.class_id is None or class_time.class_id == enrollment.class_id:
                    # Convert class time to student's timezone
                    try:
                        admin_tz = pytz.timezone(class_time.timezone)
                        today = current_datetime.date()
                        start_dt = admin_tz.localize(datetime.combine(today, class_time.start_time))
                        end_dt = admin_tz.localize(datetime.combine(today, class_time.end_time))
                        
                        start_dt_student = start_dt.astimezone(student_tz)
                        end_dt_student = end_dt.astimezone(student_tz)
                        
                        student_start_time = start_dt_student.time()
                        student_end_time = end_dt_student.time()
                        student_day = start_dt_student.strftime('%A')
                        
                        # Check if current day and time match
                        if (current_day == student_day and 
                            student_start_time <= current_time <= student_end_time):
                            # Get the class object based on class_type
                            class_obj = None
                            if class_type == 'individual':
                                class_obj = IndividualClass.query.get(enrollment.class_id) or \
                                           GroupClass.query.filter_by(id=enrollment.class_id, class_type='individual').first()
                            elif class_type == 'family':
                                class_obj = GroupClass.query.filter_by(id=enrollment.class_id, class_type='family').first()
                            
                            if class_obj:
                                active_live_class = {
                                    'enrollment': enrollment,
                                    'class_time': class_time,
                                    'class': class_obj
                                }
                                break  # Only one live class at a time
                    except Exception as e:
                        from flask import current_app
                        import traceback
                        current_app.logger.error(f"Error checking live class for individual/family: {str(e)}\n{traceback.format_exc()}")
                        pass  # If conversion fails, skip
                    
        elif class_type in ['group', 'school']:
            # For Group/School: Check if there's a fixed time that matches current time AND class_id
            fixed_times = class_times_by_type.get(class_type, [])
            for class_time in fixed_times:
                # IMPORTANT: Verify class_time matches this enrollment's class_id
                # If class_id is None, it applies to all classes of this type
                # If class_id is set, it must match the enrollment's class_id
                if class_time.class_id is not None and class_time.class_id != enrollment.class_id:
                    continue  # Skip if time slot is for a different class
                
                try:
                    admin_tz = pytz.timezone(class_time.timezone)
                    today = current_datetime.date()
                    start_dt = admin_tz.localize(datetime.combine(today, class_time.start_time))
                    end_dt = admin_tz.localize(datetime.combine(today, class_time.end_time))
                    
                    start_dt_student = start_dt.astimezone(student_tz)
                    end_dt_student = end_dt.astimezone(student_tz)
                    
                    student_start_time = start_dt_student.time()
                    student_end_time = end_dt_student.time()
                    student_day = start_dt_student.strftime('%A')
                    
                    # Check if current day and time match
                    if (current_day == student_day and 
                        student_start_time <= current_time <= student_end_time):
                        # Get the class object based on class_type
                        class_obj = None
                        if class_type == 'group':
                            class_obj = GroupClass.query.filter_by(id=enrollment.class_id, class_type='group').first()
                        elif class_type == 'school':
                            class_obj = GroupClass.query.filter_by(id=enrollment.class_id, class_type='school').first()
                        
                        if class_obj:
                            active_live_class = {
                                'enrollment': enrollment,
                                'class_time': class_time,
                                'class': class_obj
                            }
                            break  # Only one live class at a time
                except Exception as e:
                    from flask import current_app
                    import traceback
                    current_app.logger.error(f"Error checking live class for group/school: {str(e)}\n{traceback.format_exc()}")
                    pass  # If conversion fails, skip
    
    # Get ID card for user (always get it if it exists, regardless of viewing status)
    user_id_card = None
    if not getattr(user, 'is_admin', False):
        approved_enrollment = ClassEnrollment.query.filter_by(
            user_id=user_id,
            status='completed'
        ).first()
        if approved_enrollment:
            entity_type = approved_enrollment.class_type
            entity_id = None
            if entity_type == 'individual':
                entity_id = user_id
            elif entity_type == 'group':
                entity_id = user_id
            elif entity_type == 'family':
                entity_id = approved_enrollment.id
            elif entity_type == 'school':
                school_obj = School.query.filter_by(user_id=user_id).first()
                if school_obj:
                    entity_id = school_obj.id
            if entity_id:
                user_id_card = get_id_card_for_entity(entity_type, entity_id)
    
    # Get monthly payments for all enrollments - dynamic based on enrollment date
    monthly_payments = {}
    enrollment_info = {}  # Store enrollment month/year for each enrollment
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    try:
        for enrollment in enrollments:
            # Get enrollment date (when student was enrolled/approved)
            enrollment_date = enrollment.enrolled_at if enrollment.enrolled_at else datetime.utcnow()
            enrollment_month = enrollment_date.month
            enrollment_year = enrollment_date.year
            
            # Store enrollment info
            enrollment_info[enrollment.id] = {
                'month': enrollment_month,
                'year': enrollment_year,
                'date': enrollment_date
            }
            
            # Get payments for this enrollment from enrollment year onwards
            payments = MonthlyPayment.query.filter(
                MonthlyPayment.enrollment_id == enrollment.id,
                MonthlyPayment.payment_year >= enrollment_year
            ).all()
            
            # Create a dict with month as key
            payment_dict = {}
            for payment in payments:
                payment_dict[payment.payment_month] = payment
            
            # Auto-mark enrollment month as verified (paid) if status is completed
            # This represents the initial payment that got them approved
            if enrollment.status == 'completed' and enrollment_month not in payment_dict:
                # Create a virtual payment record for the enrollment month
                # We'll handle this in the template by checking enrollment status
                pass
            
            monthly_payments[enrollment.id] = payment_dict
            
            # Calculate months to show (from enrollment to current + 1)
            months_to_show = []
            temp_year = enrollment_year
            temp_month = enrollment_month
            max_months = 15  # Show up to 15 months ahead
            count = 0
            
            while count < max_months and (temp_year < current_year or (temp_year == current_year and temp_month <= current_month + 1)):
                months_to_show.append((temp_year, temp_month))
                temp_month += 1
                if temp_month > 12:
                    temp_month = 1
                    temp_year += 1
                count += 1
            
            enrollment_info[enrollment.id]['months_to_show'] = months_to_show
    except Exception as e:
        # If table doesn't exist yet, just use empty dict
        error_str = str(e)
        if 'monthly_payment' in error_str.lower() or 'does not exist' in error_str.lower():
            monthly_payments = {}
            enrollment_info = {}
        else:
            raise
    
    return render_template('student_dashboard.html', 
                          enrollment_info=enrollment_info,
                          current_year=current_year,
                          current_month=current_month,
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
                          school=school,
                          class_times_by_type=class_times_by_type,
                          student_time_selections=student_time_selections,
                          student_timezone=student_timezone,
                          active_live_class=active_live_class,
                          now=now,
                          id_card=user_id_card,
                          today=today,
                          monthly_payments=monthly_payments,
                          Attendance=Attendance,
                          user=user)


@bp.route('/my-curriculum')
def my_curriculum():
    """Display curriculum for all enrolled classes"""
    from flask import session
    from ..models.classes import GroupClass, IndividualClass, ClassEnrollment
    
    # NO LOGIN REQUIRED - Get user from session or current_user
    user = None
    user_id = None
    
    # Check if user is logged in (for admin or logged-in users)
    if current_user.is_authenticated:
        user = current_user
        user_id = current_user.id
    else:
        # Get user from session (set by entry forms or ID card)
        user_id = session.get('student_user_id') or session.get('user_id')
        if user_id:
            user = User.query.get(user_id)
    
    # If no user found, redirect to entry form
    if not user:
        flash('Please enter your Name and System ID to access your curriculum.', 'info')
        return redirect(url_for('main.index'))
    
    # Get all completed enrollments
    enrollments = ClassEnrollment.query.filter_by(
        user_id=user_id,
        status='completed'
    ).all()
    
    # Also check for registered school students
    from ..models.schools import RegisteredSchoolStudent
    registered_school_students = RegisteredSchoolStudent.query.filter_by(user_id=user_id).all()
    for reg_student in registered_school_students:
        enrollment = ClassEnrollment.query.get(reg_student.enrollment_id)
        if enrollment and enrollment.status == 'completed':
            enrollments.append(enrollment)
    
    # Get classes with curriculum
    classes_with_curriculum = []
    seen_class_ids = set()  # Avoid duplicates
    
    for enrollment in enrollments:
        if enrollment.class_id in seen_class_ids:
            continue
        seen_class_ids.add(enrollment.class_id)
        
        # Try GroupClass first (unified), then IndividualClass (legacy)
        class_obj = GroupClass.query.get(enrollment.class_id) or IndividualClass.query.get(enrollment.class_id)
        if class_obj:
            # Get curriculum (only GroupClass has curriculum field)
            curriculum_text = ''
            if hasattr(class_obj, 'curriculum'):
                curriculum_text = class_obj.curriculum or ''
            
            curriculum_items = []
            
            if curriculum_text and curriculum_text.strip():
                # Split by newlines and filter empty lines
                all_items = curriculum_text.split('\n')
                for item in all_items:
                    if item.strip():
                        curriculum_items.append(item.strip())
            
            classes_with_curriculum.append({
                'id': class_obj.id,
                'name': class_obj.name,
                'description': getattr(class_obj, 'description', None) or '',
                'class_type': enrollment.class_type,
                'curriculum_items': curriculum_items,
                'has_curriculum': len(curriculum_items) > 0
            })
    
    return render_template('my_curriculum.html', 
                          classes_with_curriculum=classes_with_curriculum,
                          user=user)


@bp.route('/student/mark-attendance', methods=['POST'])
@login_required
def mark_attendance():
    """Student marks their own attendance or school admin marks student attendance"""
    from datetime import date
    
    class_id = request.form.get('class_id', type=int) or 0
    status = request.form.get('status', 'present')  # present, absent
    student_id = request.form.get('student_id', type=int)  # For group/family classes
    school_student_id = request.form.get('school_student_id', type=int)  # For school students
    class_type = request.form.get('class_type', '')
    
    # CRITICAL: Handle school student attendance (NEW - attendance in popup only)
    if school_student_id and class_type == 'school':
        # Validate that this is a registered school student for this school and class
        school_enrollment = ClassEnrollment.query.filter_by(
            user_id=current_user.id,  # School admin's enrollment
            class_id=class_id,
            class_type='school',
            status='completed'
        ).first()
        
        if not school_enrollment:
            flash('School is not enrolled in this class.', 'danger')
            return redirect(url_for('schools.school_dashboard'))
        
        # Verify the school student belongs to this school and class
        registered_student = SchoolStudent.query.filter_by(
            id=school_student_id,
            class_id=class_id,
            enrollment_id=school_enrollment.id,
            registered_by=current_user.id
        ).first()
        
        if not registered_student:
            flash('Student is not registered in this class.', 'danger')
            return redirect(url_for('schools.school_dashboard'))
        
        # For school students, we use the school admin's user_id as a proxy
        # but store the school_student_id in the notes field for tracking
        target_student_id = current_user.id  # Use school admin as proxy
        today = date.today()
        
        # Check if attendance already exists for this school student today
        # We'll use a special format in notes: "school_student_{id}"
        existing = Attendance.query.filter(
            Attendance.student_id == target_student_id,
            Attendance.class_id == class_id,
            Attendance.class_type == 'school',
            Attendance.attendance_date == today,
            Attendance.notes.like(f'%school_student_{school_student_id}%')
        ).first()
        
        if existing:
            existing.status = status
            existing.marked_by = current_user.id
            existing.notes = f'school_student_{school_student_id}'
            flash('Attendance updated successfully!', 'success')
        else:
            new_attendance = Attendance(
                student_id=target_student_id,
                class_id=class_id,
                class_type='school',
                attendance_date=today,
                status=status,
                marked_by=current_user.id,
                notes=f'school_student_{school_student_id}'  # Store school student ID in notes
            )
            db.session.add(new_attendance)
            flash('Attendance marked successfully!', 'success')
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Error marking attendance: {str(e)}', 'danger')
        
        return redirect(url_for('schools.school_dashboard'))
    
    # Original logic for regular students (group, family, individual)
    target_student_id = student_id if student_id else current_user.id
    enrollment = None
    is_valid = False
    
    if class_type == 'school':
        # For school classes (non-school-student case)
        enrollment = ClassEnrollment.query.filter_by(
            user_id=target_student_id,
            class_id=class_id,
            class_type='school',
            status='completed'
        ).first()
        
        if enrollment:
            is_valid = True
        else:
            school_enrollment = ClassEnrollment.query.filter_by(
                user_id=current_user.id,
                class_id=class_id,
                class_type='school',
                status='completed'
            ).first()
            
            if school_enrollment:
                registered_student = SchoolStudent.query.filter_by(
                    class_id=class_id,
                    enrollment_id=school_enrollment.id,
                    registered_by=current_user.id
                ).first()
                
                if registered_student:
                    is_valid = True
                    enrollment = type('obj', (object,), {'class_type': 'school'})()
        
        if not is_valid:
            flash('Student is not enrolled or registered in this class.', 'danger')
            if current_user.is_school_admin:
                return redirect(url_for('schools.school_dashboard'))
            return redirect(url_for('admin.student_dashboard'))
    else:
        # Regular class enrollment attendance (group, family, individual)
        enrollment = ClassEnrollment.query.filter_by(
            user_id=target_student_id,
            class_id=class_id,
            status='completed'
        ).first()
        
        if not enrollment:
            flash('You are not enrolled in this class.', 'danger')
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
        if current_user.is_school_admin:
            return redirect(url_for('schools.school_dashboard'))
        return redirect(url_for('admin.student_dashboard'))
    
    # Get school name from School model
    from ..models.schools import School
    school = School.query.filter_by(user_id=current_user.id).first()
    if not school:
        flash('School not found.', 'danger')
        if current_user.is_school_admin:
            return redirect(url_for('schools.school_dashboard'))
        return redirect(url_for('admin.student_dashboard'))
    
    school_name = school.school_name
    
    if not student_name:
        flash('Student name is required.', 'danger')
        if current_user.is_school_admin:
            return redirect(url_for('schools.school_dashboard'))
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
        # Generate unique Student System ID for this school
        from ..models.schools import School
        school = School.query.filter_by(user_id=current_user.id).first()
        if not school:
            flash('School not found.', 'danger')
            if current_user.is_school_admin:
                return redirect(url_for('schools.school_dashboard'))
            return redirect(url_for('admin.student_dashboard'))
        
        # Generate system_id based on school and existing students
        # Format: STU-{school_id}-{sequential_number}
        existing_students = SchoolStudent.query.filter_by(
            school_name=school_name
        ).order_by(SchoolStudent.id.desc()).all()
        
        if existing_students:
            # Extract highest number from existing system_ids
            max_num = 0
            for stu in existing_students:
                if stu.student_system_id and stu.student_system_id.startswith('STU-'):
                    try:
                        parts = stu.student_system_id.split('-')
                        if len(parts) >= 3:
                            num = int(parts[-1])
                            max_num = max(max_num, num)
                    except:
                        pass
            next_num = max_num + 1
        else:
            next_num = 1
        
        # Format: STU-{school_id:03d}-{student_number:05d}
        student_system_id = f"STU-{school.id:03d}-{next_num:05d}"
        
        # Ensure uniqueness
        while SchoolStudent.query.filter_by(student_system_id=student_system_id).first():
            next_num += 1
            student_system_id = f"STU-{school.id:03d}-{next_num:05d}"
        
        new_student = SchoolStudent(
            enrollment_id=enrollment_id,
            class_id=class_id,
            school_name=school_name,
            student_name=student_name,
            student_system_id=student_system_id,
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
        db.session.flush()  # Get ID without committing
        
        # Generate ID Card for the school student
        try:
            from ..models.id_cards import generate_school_student_id_card
            id_card = generate_school_student_id_card(new_student, school, current_user.id)
            db.session.commit()
            flash(f'Student "{student_name}" registered successfully! Student System ID: {student_system_id}. ID Card generated.', 'success')
        except Exception as e:
            db.session.commit()  # Commit student even if ID card generation fails
            flash(f'Student "{student_name}" registered successfully! Student System ID: {student_system_id}. Error generating ID card: {str(e)}', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error registering student: {str(e)}', 'danger')
    
    if current_user.is_school_admin:
        return redirect(url_for('schools.school_dashboard'))
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
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
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
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
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
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
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
            return redirect(url_for('admin.admin_edit_user', user_id=user.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to update user: {e}', 'danger')
    # Get user statistics
    purchases_count = Purchase.query.filter_by(user_id=user.id, status='completed').count()
    enrollments_count = ClassEnrollment.query.filter_by(user_id=user.id, status='completed').count()
    projects_count = len(user.student_projects) if hasattr(user, 'student_projects') else 0
    account_age_days = (datetime.utcnow() - user.created_at).days if user.created_at else 0
    
    return render_template('edit_user.html', 
                           user=user, 
                           Purchase=Purchase, 
                           ClassEnrollment=ClassEnrollment,
                           GroupClass=GroupClass,
                           IndividualClass=IndividualClass,
                           datetime=datetime,
                           purchases_count=purchases_count,
                           enrollments_count=enrollments_count,
                           projects_count=projects_count,
                           account_age_days=account_age_days)


# ========== GALLERY MANAGEMENT ==========
@bp.route('/admin/gallery')
@login_required
def admin_gallery():
    """Admin page to manage homepage gallery (images and videos)"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
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
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
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
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
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
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
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
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
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
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
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
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
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
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
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
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
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
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    # Get pricing data from database or use defaults
    pricing_data = ClassPricing.get_all_pricing()
    
    return render_template('admin_pricing.html', pricing_data=pricing_data)


@bp.route('/admin/pricing/<class_type>/update', methods=['POST'])
@login_required
def update_pricing(class_type):
    """Update pricing for a class type"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
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

@bp.route('/admin/reset-student-ids', methods=['POST'])
@login_required
def reset_student_ids():
    """Reset all student IDs to start from STU-00001 - ADMIN ONLY"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    try:
        from ..models.classes import reset_all_student_ids
        result = reset_all_student_ids()
        
        if result['success']:
            flash(result['message'], 'success')
        else:
            flash(result['message'], 'danger')
    except Exception as e:
        flash(f'Error resetting student IDs: {str(e)}', 'danger')
    
        return redirect(url_for('admin.admin_individual_classes'))


# ==================== RESET & BACKUP MANAGEMENT ====================

@bp.route('/admin/individual-classes/reset', methods=['POST'])
@login_required
def reset_individual_classes():
    """Reset all individual classes data - PIN: 1"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    pin = request.form.get('pin', '').strip()
    if pin != '1':
        flash('Invalid PIN. Reset cancelled.', 'danger')
        return redirect(url_for('admin.admin_individual_classes'))
    
    try:
        # Get all individual class enrollments first
        individual_enrollments = ClassEnrollment.query.filter_by(class_type='individual').all()
        enrollment_ids = [e.id for e in individual_enrollments]
        
        # Delete child records first: StudentClassTimeSelection
        if enrollment_ids:
            from ..models.classes import StudentClassTimeSelection
            time_selections = StudentClassTimeSelection.query.filter(
                StudentClassTimeSelection.enrollment_id.in_(enrollment_ids)
            ).all()
            for selection in time_selections:
                db.session.delete(selection)
        
        # Delete all individual class enrollments
        for enrollment in individual_enrollments:
            db.session.delete(enrollment)
        
        # Delete all individual classes
        individual_classes = IndividualClass.query.all()
        for class_obj in individual_classes:
            db.session.delete(class_obj)
        
        # Delete group classes with class_type='individual'
        group_individual_classes = GroupClass.query.filter_by(class_type='individual').all()
        for class_obj in group_individual_classes:
            db.session.delete(class_obj)
        
        # Remove individual student IDs from users (set to None)
        users_with_individual = User.query.filter(
            User.student_id.isnot(None),
            User.student_id.like('STU-%')
        ).all()
        for user in users_with_individual:
            # Check if user has other enrollments
            other_enrollments = ClassEnrollment.query.filter(
                ClassEnrollment.user_id == user.id,
                ClassEnrollment.class_type != 'individual',
                ClassEnrollment.status == 'completed'
            ).first()
            if not other_enrollments:
                user.student_id = None
                user.class_type = None
        
        # Delete individual ID cards
        individual_id_cards = IDCard.query.filter_by(entity_type='individual').all()
        for id_card in individual_id_cards:
            db.session.delete(id_card)
        
        db.session.commit()
        flash('✅ All individual classes data has been reset successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting individual classes: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_individual_classes'))


@bp.route('/admin/individual-classes/backup', methods=['GET'])
@login_required
def backup_individual_classes():
    """Backup all individual classes data"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    try:
        from flask import jsonify
        from datetime import datetime
        
        # Get all individual class data
        enrollments = ClassEnrollment.query.filter_by(class_type='individual').all()
        classes = IndividualClass.query.all()
        group_individual_classes = GroupClass.query.filter_by(class_type='individual').all()
        id_cards = IDCard.query.filter_by(entity_type='individual').all()
        
        backup_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'enrollments': [{
                'id': e.id,
                'user_id': e.user_id,
                'class_id': e.class_id,
                'amount': float(e.amount),
                'status': e.status,
                'payment_method': e.payment_method,
                'enrolled_at': e.enrolled_at.isoformat() if e.enrolled_at else None,
                'customer_name': e.customer_name,
                'customer_email': e.customer_email,
                'customer_phone': e.customer_phone
            } for e in enrollments],
            'individual_classes': [{
                'id': c.id,
                'name': c.name,
                'description': c.description,
                'teacher_id': c.teacher_id,
                'created_at': c.created_at.isoformat() if c.created_at else None
            } for c in classes],
            'group_individual_classes': [{
                'id': c.id,
                'name': c.name,
                'description': c.description,
                'teacher_id': c.teacher_id,
                'max_students': c.max_students,
                'created_at': c.created_at.isoformat() if c.created_at else None
            } for c in group_individual_classes],
            'id_cards': [{
                'id': card.id,
                'entity_id': card.entity_id,
                'system_id': card.system_id,
                'name': card.name,
                'email': card.email,
                'phone': card.phone,
                'created_at': card.created_at.isoformat() if card.created_at else None
            } for card in id_cards]
        }
        
        response = jsonify(backup_data)
        response.headers['Content-Disposition'] = f'attachment; filename=individual_classes_backup_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json'
        return response
    except Exception as e:
        flash(f'Error creating backup: {str(e)}', 'danger')
        return redirect(url_for('admin.admin_individual_classes'))


@bp.route('/admin/individual-classes/upload-backup', methods=['POST'])
@login_required
def upload_backup_individual_classes():
    """Upload and restore individual classes backup data"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    try:
        if 'backup_file' not in request.files:
            flash('No file uploaded', 'danger')
            return redirect(url_for('admin.admin_individual_classes'))
        
        file = request.files['backup_file']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(url_for('admin.admin_individual_classes'))
        
        if not file.filename.endswith('.json'):
            flash('Invalid file type. Please upload a JSON file.', 'danger')
            return redirect(url_for('admin.admin_individual_classes'))
        
        import json
        from datetime import datetime
        
        # Read and parse JSON
        backup_data = json.load(file)
        
        # Restore enrollments
        if 'enrollments' in backup_data:
            for e_data in backup_data['enrollments']:
                enrollment = ClassEnrollment(
                    user_id=e_data['user_id'],
                    class_id=e_data['class_id'],
                    class_type='individual',
                    amount=e_data['amount'],
                    status=e_data['status'],
                    payment_method=e_data.get('payment_method'),
                    enrolled_at=datetime.fromisoformat(e_data['enrolled_at']) if e_data.get('enrolled_at') else None,
                    customer_name=e_data.get('customer_name'),
                    customer_email=e_data.get('customer_email'),
                    customer_phone=e_data.get('customer_phone')
                )
                db.session.add(enrollment)
        
        # Restore individual classes
        if 'individual_classes' in backup_data:
            for c_data in backup_data['individual_classes']:
                class_obj = IndividualClass(
                    name=c_data['name'],
                    description=c_data.get('description'),
                    teacher_id=c_data.get('teacher_id')
                )
                db.session.add(class_obj)
        
        # Restore group individual classes
        if 'group_individual_classes' in backup_data:
            for c_data in backup_data['group_individual_classes']:
                class_obj = GroupClass(
                    name=c_data['name'],
                    description=c_data.get('description'),
                    teacher_id=c_data.get('teacher_id'),
                    max_students=c_data.get('max_students', 10),
                    class_type='individual'
                )
                db.session.add(class_obj)
        
        # Restore ID cards
        if 'id_cards' in backup_data:
            for card_data in backup_data['id_cards']:
                id_card = IDCard(
                    entity_id=card_data['entity_id'],
                    entity_type='individual',
                    system_id=card_data.get('system_id'),
                    name=card_data.get('name'),
                    email=card_data.get('email'),
                    phone=card_data.get('phone')
                )
                db.session.add(id_card)
        
        db.session.commit()
        flash('✅ Backup data restored successfully!', 'success')
    except json.JSONDecodeError:
        db.session.rollback()
        flash('Invalid JSON file format', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error restoring backup: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_individual_classes'))


@bp.route('/admin/group-classes/reset', methods=['POST'])
@login_required
def reset_group_classes():
    """Reset all group classes data - PIN: 2"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    pin = request.form.get('pin', '').strip()
    if pin != '2':
        flash('Invalid PIN. Reset cancelled.', 'danger')
        return redirect(url_for('admin.admin_group_classes'))
    
    try:
        # Delete all group class enrollments
        group_enrollments = ClassEnrollment.query.filter_by(class_type='group').all()
        for enrollment in group_enrollments:
            db.session.delete(enrollment)
        
        # Delete all group classes
        group_classes = GroupClass.query.filter_by(class_type='group').all()
        for class_obj in group_classes:
            db.session.delete(class_obj)
        
        # Remove individual student IDs from group-only users
        users_with_student_id = User.query.filter(
            User.student_id.isnot(None),
            User.student_id.like('STU-%')
        ).all()
        for user in users_with_student_id:
            # Check if user has individual enrollments
            individual_enrollment = ClassEnrollment.query.filter_by(
                user_id=user.id,
                class_type='individual',
                status='completed'
            ).first()
            if not individual_enrollment:
                user.student_id = None
                user.class_type = None
        
        # Delete group ID cards
        group_id_cards = IDCard.query.filter_by(entity_type='group').all()
        for id_card in group_id_cards:
            db.session.delete(id_card)
        
        db.session.commit()
        flash('✅ All group classes data has been reset successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting group classes: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_group_classes'))


@bp.route('/admin/group-classes/backup', methods=['GET'])
@login_required
def backup_group_classes():
    """Backup all group classes data"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    try:
        from flask import jsonify
        from datetime import datetime
        
        enrollments = ClassEnrollment.query.filter_by(class_type='group').all()
        classes = GroupClass.query.filter_by(class_type='group').all()
        id_cards = IDCard.query.filter_by(entity_type='group').all()
        
        backup_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'enrollments': [{
                'id': e.id,
                'user_id': e.user_id,
                'class_id': e.class_id,
                'group_system_id': e.group_system_id,
                'amount': float(e.amount),
                'status': e.status,
                'payment_method': e.payment_method,
                'enrolled_at': e.enrolled_at.isoformat() if e.enrolled_at else None,
                'customer_name': e.customer_name,
                'customer_email': e.customer_email,
                'customer_phone': e.customer_phone
            } for e in enrollments],
            'group_classes': [{
                'id': c.id,
                'name': c.name,
                'description': c.description,
                'teacher_id': c.teacher_id,
                'max_students': c.max_students,
                'created_at': c.created_at.isoformat() if c.created_at else None
            } for c in classes],
            'id_cards': [{
                'id': card.id,
                'entity_id': card.entity_id,
                'system_id': card.system_id,
                'group_system_id': card.group_system_id,
                'name': card.name,
                'email': card.email,
                'phone': card.phone,
                'created_at': card.created_at.isoformat() if card.created_at else None
            } for card in id_cards]
        }
        
        response = jsonify(backup_data)
        response.headers['Content-Disposition'] = f'attachment; filename=group_classes_backup_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json'
        return response
    except Exception as e:
        flash(f'Error creating backup: {str(e)}', 'danger')
        return redirect(url_for('admin.admin_group_classes'))


@bp.route('/admin/group-classes/upload-backup', methods=['POST'])
@login_required
def upload_backup_group_classes():
    """Upload and restore group classes backup data"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    try:
        if 'backup_file' not in request.files:
            flash('No file uploaded', 'danger')
            return redirect(url_for('admin.admin_group_classes'))
        
        file = request.files['backup_file']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(url_for('admin.admin_group_classes'))
        
        if not file.filename.endswith('.json'):
            flash('Invalid file type. Please upload a JSON file.', 'danger')
            return redirect(url_for('admin.admin_group_classes'))
        
        import json
        from datetime import datetime
        
        backup_data = json.load(file)
        
        # Restore enrollments
        if 'enrollments' in backup_data:
            for e_data in backup_data['enrollments']:
                enrollment = ClassEnrollment(
                    user_id=e_data['user_id'],
                    class_id=e_data['class_id'],
                    class_type='group',
                    amount=e_data['amount'],
                    status=e_data['status'],
                    payment_method=e_data.get('payment_method'),
                    group_system_id=e_data.get('group_system_id'),
                    enrolled_at=datetime.fromisoformat(e_data['enrolled_at']) if e_data.get('enrolled_at') else None,
                    customer_name=e_data.get('customer_name'),
                    customer_email=e_data.get('customer_email'),
                    customer_phone=e_data.get('customer_phone')
                )
                db.session.add(enrollment)
        
        # Restore group classes
        if 'group_classes' in backup_data:
            for c_data in backup_data['group_classes']:
                class_obj = GroupClass(
                    name=c_data['name'],
                    description=c_data.get('description'),
                    teacher_id=c_data.get('teacher_id'),
                    max_students=c_data.get('max_students', 10),
                    class_type='group'
                )
                db.session.add(class_obj)
        
        # Restore ID cards
        if 'id_cards' in backup_data:
            for card_data in backup_data['id_cards']:
                id_card = IDCard(
                    entity_id=card_data['entity_id'],
                    entity_type='group',
                    system_id=card_data.get('system_id'),
                    group_system_id=card_data.get('group_system_id'),
                    name=card_data.get('name'),
                    email=card_data.get('email'),
                    phone=card_data.get('phone')
                )
                db.session.add(id_card)
        
        db.session.commit()
        flash('✅ Backup data restored successfully!', 'success')
    except json.JSONDecodeError:
        db.session.rollback()
        flash('Invalid JSON file format', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error restoring backup: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_group_classes'))


@bp.route('/admin/family-classes/reset', methods=['POST'])
@login_required
def reset_family_classes():
    """Reset all family classes data - PIN: 3"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    pin = request.form.get('pin', '').strip()
    if pin != '3':
        flash('Invalid PIN. Reset cancelled.', 'danger')
        return redirect(url_for('admin.admin_family_classes'))
    
    try:
        # Get all family class enrollments first
        family_enrollments = ClassEnrollment.query.filter_by(class_type='family').all()
        enrollment_ids = [e.id for e in family_enrollments]
        
        # Delete child records first: FamilyMember (has FK to enrollment_id)
        if enrollment_ids:
            from ..models.classes import FamilyMember
            family_members = FamilyMember.query.filter(
                FamilyMember.enrollment_id.in_(enrollment_ids)
            ).all()
            for member in family_members:
                db.session.delete(member)
            
            # Delete child records: StudentClassTimeSelection (for family classes)
            from ..models.classes import StudentClassTimeSelection
            time_selections = StudentClassTimeSelection.query.filter(
                StudentClassTimeSelection.enrollment_id.in_(enrollment_ids)
            ).all()
            for selection in time_selections:
                db.session.delete(selection)
        
        # Delete all family class enrollments
        for enrollment in family_enrollments:
            db.session.delete(enrollment)
        
        # Delete all family classes
        family_classes = GroupClass.query.filter_by(class_type='family').all()
        for class_obj in family_classes:
            db.session.delete(class_obj)
        
        # Remove family system IDs and student IDs from users
        users_with_family = User.query.filter(
            User.student_id.isnot(None),
            User.student_id.like('STU-%')
        ).all()
        for user in users_with_family:
            # Check if user has other enrollments
            other_enrollments = ClassEnrollment.query.filter(
                ClassEnrollment.user_id == user.id,
                ClassEnrollment.class_type != 'family',
                ClassEnrollment.status == 'completed'
            ).first()
            if not other_enrollments:
                user.student_id = None
                user.class_type = None
        
        # Delete family ID cards
        family_id_cards = IDCard.query.filter_by(entity_type='family').all()
        for id_card in family_id_cards:
            db.session.delete(id_card)
        
        db.session.commit()
        flash('✅ All family classes data has been reset successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting family classes: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_family_classes'))


@bp.route('/admin/family-classes/backup', methods=['GET'])
@login_required
def backup_family_classes():
    """Backup all family classes data"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    try:
        from flask import jsonify
        from datetime import datetime
        from ..models.classes import FamilyMember
        
        enrollments = ClassEnrollment.query.filter_by(class_type='family').all()
        classes = GroupClass.query.filter_by(class_type='family').all()
        family_members = FamilyMember.query.all()
        id_cards = IDCard.query.filter_by(entity_type='family').all()
        
        backup_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'enrollments': [{
                'id': e.id,
                'user_id': e.user_id,
                'class_id': e.class_id,
                'family_system_id': e.family_system_id,
                'amount': float(e.amount),
                'status': e.status,
                'payment_method': e.payment_method,
                'enrolled_at': e.enrolled_at.isoformat() if e.enrolled_at else None,
                'customer_name': e.customer_name,
                'customer_email': e.customer_email,
                'customer_phone': e.customer_phone
            } for e in enrollments],
            'family_classes': [{
                'id': c.id,
                'name': c.name,
                'description': c.description,
                'teacher_id': c.teacher_id,
                'max_students': c.max_students,
                'created_at': c.created_at.isoformat() if c.created_at else None
            } for c in classes],
            'family_members': [{
                'id': m.id,
                'enrollment_id': m.enrollment_id,
                'member_name': m.member_name,
                'member_age': m.member_age,
                'relationship': m.relationship,
                'member_email': m.member_email,
                'member_phone': m.member_phone
            } for m in family_members],
            'id_cards': [{
                'id': card.id,
                'entity_id': card.entity_id,
                'system_id': card.system_id,
                'family_system_id': card.family_system_id,
                'name': card.name,
                'email': card.email,
                'phone': card.phone,
                'created_at': card.created_at.isoformat() if card.created_at else None
            } for card in id_cards]
        }
        
        response = jsonify(backup_data)
        response.headers['Content-Disposition'] = f'attachment; filename=family_classes_backup_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json'
        return response
    except Exception as e:
        flash(f'Error creating backup: {str(e)}', 'danger')
        return redirect(url_for('admin.admin_family_classes'))


@bp.route('/admin/family-classes/upload-backup', methods=['POST'])
@login_required
def upload_backup_family_classes():
    """Upload and restore family classes backup data"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    try:
        if 'backup_file' not in request.files:
            flash('No file uploaded', 'danger')
            return redirect(url_for('admin.admin_family_classes'))
        
        file = request.files['backup_file']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(url_for('admin.admin_family_classes'))
        
        if not file.filename.endswith('.json'):
            flash('Invalid file type. Please upload a JSON file.', 'danger')
            return redirect(url_for('admin.admin_family_classes'))
        
        import json
        from datetime import datetime
        from ..models.classes import FamilyMember
        
        backup_data = json.load(file)
        
        # Restore enrollments first (needed for foreign keys)
        enrollment_map = {}  # old_id -> new_enrollment
        if 'enrollments' in backup_data:
            for e_data in backup_data['enrollments']:
                enrollment = ClassEnrollment(
                    user_id=e_data['user_id'],
                    class_id=e_data['class_id'],
                    class_type='family',
                    amount=e_data['amount'],
                    status=e_data['status'],
                    payment_method=e_data.get('payment_method'),
                    family_system_id=e_data.get('family_system_id'),
                    enrolled_at=datetime.fromisoformat(e_data['enrolled_at']) if e_data.get('enrolled_at') else None,
                    customer_name=e_data.get('customer_name'),
                    customer_email=e_data.get('customer_email'),
                    customer_phone=e_data.get('customer_phone')
                )
                db.session.add(enrollment)
                db.session.flush()  # Get the new ID
                enrollment_map[e_data['id']] = enrollment
        
        # Restore family classes
        if 'family_classes' in backup_data:
            for c_data in backup_data['family_classes']:
                class_obj = GroupClass(
                    name=c_data['name'],
                    description=c_data.get('description'),
                    teacher_id=c_data.get('teacher_id'),
                    max_students=c_data.get('max_students', 10),
                    class_type='family'
                )
                db.session.add(class_obj)
        
        # Restore family members (after enrollments)
        if 'family_members' in backup_data:
            for m_data in backup_data['family_members']:
                old_enrollment_id = m_data['enrollment_id']
                new_enrollment = enrollment_map.get(old_enrollment_id)
                if new_enrollment:
                    member = FamilyMember(
                        enrollment_id=new_enrollment.id,
                        class_id=m_data.get('class_id', new_enrollment.class_id),
                        member_name=m_data['member_name'],
                        member_age=m_data.get('member_age'),
                        relationship=m_data.get('relationship'),
                        member_email=m_data.get('member_email'),
                        member_phone=m_data.get('member_phone'),
                        registered_by=m_data.get('registered_by', new_enrollment.user_id)
                    )
                    db.session.add(member)
        
        # Restore ID cards
        if 'id_cards' in backup_data:
            for card_data in backup_data['id_cards']:
                id_card = IDCard(
                    entity_id=card_data['entity_id'],
                    entity_type='family',
                    system_id=card_data.get('system_id'),
                    family_system_id=card_data.get('family_system_id'),
                    name=card_data.get('name'),
                    email=card_data.get('email'),
                    phone=card_data.get('phone')
                )
                db.session.add(id_card)
        
        db.session.commit()
        flash('✅ Backup data restored successfully!', 'success')
    except json.JSONDecodeError:
        db.session.rollback()
        flash('Invalid JSON file format', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error restoring backup: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_family_classes'))


@bp.route('/admin/schools/reset', methods=['POST'])
@login_required
def reset_school_classes():
    """Reset all school classes data - PIN: 4"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    pin = request.form.get('pin', '').strip()
    if pin != '4':
        flash('Invalid PIN. Reset cancelled.', 'danger')
        return redirect(url_for('admin.admin_schools'))
    
    try:
        # Get all school class enrollments first
        school_enrollments = ClassEnrollment.query.filter_by(class_type='school').all()
        enrollment_ids = [e.id for e in school_enrollments]
        
        # Delete child records first: SchoolStudent (has FK to enrollment_id)
        if enrollment_ids:
            from ..models.classes import SchoolStudent
            school_students = SchoolStudent.query.filter(
                SchoolStudent.enrollment_id.in_(enrollment_ids)
            ).all()
            for student in school_students:
                db.session.delete(student)
        
        # Delete all school class enrollments
        for enrollment in school_enrollments:
            db.session.delete(enrollment)
        
        # Delete all school classes
        school_classes = GroupClass.query.filter_by(class_type='school').all()
        for class_obj in school_classes:
            db.session.delete(class_obj)
        
        # Delete all registered school students (RegisteredSchoolStudent - different table)
        registered_students = RegisteredSchoolStudent.query.all()
        for student in registered_students:
            db.session.delete(student)
        
        # Delete all schools
        schools = School.query.all()
        for school in schools:
            db.session.delete(school)
        
        # Delete school ID cards
        school_id_cards = IDCard.query.filter_by(entity_type='school').all()
        for id_card in school_id_cards:
            db.session.delete(id_card)
        
        # Delete school student ID cards
        school_student_id_cards = IDCard.query.filter_by(entity_type='school_student').all()
        for id_card in school_student_id_cards:
            db.session.delete(id_card)
        
        db.session.commit()
        flash('✅ All school classes data has been reset successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting school classes: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_schools'))


@bp.route('/admin/schools/backup', methods=['GET'])
@login_required
def backup_school_classes():
    """Backup all school classes data"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    try:
        from flask import jsonify
        from datetime import datetime
        
        enrollments = ClassEnrollment.query.filter_by(class_type='school').all()
        classes = GroupClass.query.filter_by(class_type='school').all()
        schools = School.query.all()
        registered_students = RegisteredSchoolStudent.query.all()
        school_id_cards = IDCard.query.filter_by(entity_type='school').all()
        school_student_id_cards = IDCard.query.filter_by(entity_type='school_student').all()
        
        backup_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'enrollments': [{
                'id': e.id,
                'user_id': e.user_id,
                'class_id': e.class_id,
                'amount': float(e.amount),
                'status': e.status,
                'payment_method': e.payment_method,
                'enrolled_at': e.enrolled_at.isoformat() if e.enrolled_at else None,
                'customer_name': e.customer_name,
                'customer_email': e.customer_email,
                'customer_phone': e.customer_phone
            } for e in enrollments],
            'school_classes': [{
                'id': c.id,
                'name': c.name,
                'description': c.description,
                'teacher_id': c.teacher_id,
                'max_students': c.max_students,
                'created_at': c.created_at.isoformat() if c.created_at else None
            } for c in classes],
            'schools': [{
                'id': s.id,
                'school_name': s.school_name,
                'school_system_id': s.school_system_id,
                'admin_name': s.admin_name,
                'admin_email': s.admin_email,
                'status': s.status,
                'payment_status': s.payment_status,
                'created_at': s.created_at.isoformat() if s.created_at else None
            } for s in schools],
            'registered_students': [{
                'id': rs.id,
                'enrollment_id': rs.enrollment_id,
                'student_name': rs.student_name,
                'student_system_id': rs.student_system_id,
                'school_name': rs.school_name,
                'student_email': rs.student_email,
                'student_phone': rs.student_phone
            } for rs in registered_students],
            'school_id_cards': [{
                'id': card.id,
                'entity_id': card.entity_id,
                'system_id': card.system_id,
                'school_system_id': card.school_system_id,
                'name': card.name,
                'email': card.email,
                'phone': card.phone
            } for card in school_id_cards],
            'school_student_id_cards': [{
                'id': card.id,
                'entity_id': card.entity_id,
                'system_id': card.system_id,
                'school_system_id': card.school_system_id,
                'name': card.name,
                'email': card.email,
                'phone': card.phone
            } for card in school_student_id_cards]
        }
        
        response = jsonify(backup_data)
        response.headers['Content-Disposition'] = f'attachment; filename=school_classes_backup_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json'
        return response
    except Exception as e:
        flash(f'Error creating backup: {str(e)}', 'danger')
        return redirect(url_for('admin.admin_schools'))


@bp.route('/admin/schools/upload-backup', methods=['POST'])
@login_required
def upload_backup_school_classes():
    """Upload and restore school classes backup data"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    try:
        if 'backup_file' not in request.files:
            flash('No file uploaded', 'danger')
            return redirect(url_for('admin.admin_schools'))
        
        file = request.files['backup_file']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(url_for('admin.admin_schools'))
        
        if not file.filename.endswith('.json'):
            flash('Invalid file type. Please upload a JSON file.', 'danger')
            return redirect(url_for('admin.admin_schools'))
        
        import json
        from datetime import datetime
        from ..models.classes import SchoolStudent
        
        backup_data = json.load(file)
        
        # Restore enrollments first (needed for foreign keys)
        enrollment_map = {}  # old_id -> new_enrollment
        if 'enrollments' in backup_data:
            for e_data in backup_data['enrollments']:
                enrollment = ClassEnrollment(
                    user_id=e_data['user_id'],
                    class_id=e_data['class_id'],
                    class_type='school',
                    amount=e_data['amount'],
                    status=e_data['status'],
                    payment_method=e_data.get('payment_method'),
                    enrolled_at=datetime.fromisoformat(e_data['enrolled_at']) if e_data.get('enrolled_at') else None,
                    customer_name=e_data.get('customer_name'),
                    customer_email=e_data.get('customer_email'),
                    customer_phone=e_data.get('customer_phone')
                )
                db.session.add(enrollment)
                db.session.flush()  # Get the new ID
                enrollment_map[e_data['id']] = enrollment
        
        # Restore school classes
        if 'school_classes' in backup_data:
            for c_data in backup_data['school_classes']:
                class_obj = GroupClass(
                    name=c_data['name'],
                    description=c_data.get('description'),
                    teacher_id=c_data.get('teacher_id'),
                    max_students=c_data.get('max_students', 10),
                    class_type='school'
                )
                db.session.add(class_obj)
        
        # Restore schools
        if 'schools' in backup_data:
            for s_data in backup_data['schools']:
                school = School(
                    school_name=s_data['school_name'],
                    school_system_id=s_data.get('school_system_id'),
                    admin_name=s_data.get('admin_name'),
                    admin_email=s_data.get('admin_email'),
                    status=s_data.get('status', 'pending'),
                    payment_status=s_data.get('payment_status', 'pending')
                )
                db.session.add(school)
        
        # Restore registered school students (after enrollments)
        if 'registered_students' in backup_data:
            for rs_data in backup_data['registered_students']:
                old_enrollment_id = rs_data.get('enrollment_id')
                new_enrollment = enrollment_map.get(old_enrollment_id) if old_enrollment_id else None
                if new_enrollment:
                    student = RegisteredSchoolStudent(
                        enrollment_id=new_enrollment.id,
                        student_name=rs_data['student_name'],
                        student_system_id=rs_data.get('student_system_id'),
                        school_name=rs_data.get('school_name'),
                        student_email=rs_data.get('student_email'),
                        student_phone=rs_data.get('student_phone')
                    )
                    db.session.add(student)
        
        # Restore school ID cards
        if 'school_id_cards' in backup_data:
            for card_data in backup_data['school_id_cards']:
                id_card = IDCard(
                    entity_id=card_data['entity_id'],
                    entity_type='school',
                    system_id=card_data.get('system_id'),
                    school_system_id=card_data.get('school_system_id'),
                    name=card_data.get('name'),
                    email=card_data.get('email'),
                    phone=card_data.get('phone')
                )
                db.session.add(id_card)
        
        # Restore school student ID cards
        if 'school_student_id_cards' in backup_data:
            for card_data in backup_data['school_student_id_cards']:
                id_card = IDCard(
                    entity_id=card_data['entity_id'],
                    entity_type='school_student',
                    system_id=card_data.get('system_id'),
                    school_system_id=card_data.get('school_system_id'),
                    name=card_data.get('name'),
                    email=card_data.get('email'),
                    phone=card_data.get('phone')
                )
                db.session.add(id_card)
        
        db.session.commit()
        flash('✅ Backup data restored successfully!', 'success')
    except json.JSONDecodeError:
        db.session.rollback()
        flash('Invalid JSON file format', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error restoring backup: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_schools'))


@bp.route('/admin/individual-classes', methods=['GET', 'POST'])
@login_required
def admin_individual_classes():
    """View and manage all individual (one-on-one) students and classes"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    # Handle POST for sharing materials to individual students (not classes)
    if request.method == 'POST' and 'share_material' in request.form:
        student_ids = request.form.getlist('student_ids')  # Changed from class_ids to student_ids
        title = request.form.get('title', '').strip()
        content = request.form.get('message', '').strip()
        
        if not student_ids:
            flash('Please select at least one student.', 'danger')
        elif not content and not request.files.get('material_file'):
            flash('Please provide content or upload a file.', 'danger')
        else:
            from ..services.cloudinary_service import CloudinaryService
            from werkzeug.utils import secure_filename
            import re
            
            material_type = 'text'
            file_url = None
            file_type = None
            file_name = None
            youtube_url = None
            
            youtube_pattern = r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})'
            youtube_match = re.search(youtube_pattern, content)
            if youtube_match:
                youtube_url = f"https://www.youtube.com/watch?v={youtube_match.group(1)}"
                material_type = 'youtube'
            
            uploaded_file = request.files.get('material_file')
            if uploaded_file and uploaded_file.filename:
                file_name = secure_filename(uploaded_file.filename)
                file_ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
                
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
                
                success, result = CloudinaryService.upload_file(
                    file=uploaded_file,
                    folder='learning_materials',
                    resource_type=resource_type
                )
                
                if success:
                    file_url = result.get('url')
                    file_type = result.get('format', file_ext)
                else:
                    flash(f'File upload failed: {result}', 'warning')
            
            try:
                shared_count = 0
                for student_id_str in student_ids:
                    student_id = int(student_id_str)
                    student = User.query.get(student_id)
                    if student:
                        # Share material directly to this student
                        material = LearningMaterial(
                            class_id=f"student_{student.id}",
                            class_type='individual',
                            actual_class_id=student.id,
                            title=title,
                            content=content,
                            created_by=current_user.id,
                            material_type=material_type,
                            file_url=file_url,
                            file_type=file_type,
                            file_name=file_name,
                            youtube_url=youtube_url
                        )
                        db.session.add(material)
                        shared_count += 1
                
                db.session.commit()
                flash(f'Material shared with {shared_count} student(s)!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error sharing material: {str(e)}', 'danger')
            return redirect(url_for('admin.admin_individual_classes'))
    
    # Handle POST actions (approve, reject, deactivate)
    if request.method == 'POST':
        enrollment_id = request.form.get('enrollment_id', type=int)
        action = request.form.get('action')
        
        if enrollment_id:
            enrollment = ClassEnrollment.query.get(enrollment_id)
            if enrollment and enrollment.class_type == 'individual':
                if action == 'approve':
                    # EXACT SAME PATTERN AS WORKING GROUP CLASS APPROVAL
                    user = User.query.get(enrollment.user_id)
                    if user:
                        # Generate Student ID if not exists (same as group_system_id for groups)
                        try:
                            if not user.student_id:
                                from ..models.classes import generate_student_id_for_class
                                user.student_id = generate_student_id_for_class('individual')
                        except Exception as e:
                            # Handle any errors in student ID generation
                            flash(f'Error generating Student ID: {str(e)}', 'danger')
                            return redirect(url_for('admin.admin_individual_classes'))
                        
                        # Set user class type
                            user.class_type = 'individual'
                        
                        # Get the individual class
                        individual_class = GroupClass.query.filter_by(id=enrollment.class_id, class_type='individual').first() or \
                                          IndividualClass.query.get(enrollment.class_id)
                        
                        # Check if user not already in class (same pattern as group)
                        if individual_class and user not in individual_class.students:
                            individual_class.students.append(user)
                            enrollment.status = 'completed'
                            
                            # Generate ID Card (same pattern as group)
                            try:
                                from ..models.id_cards import generate_individual_student_id_card
                                id_card = generate_individual_student_id_card(enrollment, user, individual_class, current_user.id)
                                db.session.commit()
                                flash(f'Enrollment approved! Student ID: {user.student_id}. ID Card generated. Student will be redirected to view ID card immediately.', 'success')
                            except Exception as e:
                                db.session.rollback()
                                db.session.commit()
                                flash(f'Enrollment approved! Student ID: {user.student_id}. Error generating ID card: {str(e)}', 'warning')
                        else:
                            enrollment.status = 'completed'
                            db.session.commit()
                            flash(f'Enrollment approved! Student ID: {user.student_id}', 'success')
                elif action == 'reject':
                    enrollment.status = 'rejected'
                    db.session.commit()
                    flash('Enrollment rejected.', 'warning')
                elif action == 'deactivate':
                    enrollment.status = 'rejected'  # Mark as rejected to deactivate
                    db.session.commit()
                    flash('Individual class has been deactivated.', 'success')
            return redirect(url_for('admin.admin_individual_classes'))
    
    # Get search and filter parameters
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    
    # Get all individual class enrollments (including pending for approval)
    # Show both completed and pending enrollments
    query = ClassEnrollment.query.filter_by(class_type='individual')
    
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
    
    # Build list of individual class students (separate pending and completed)
    pending_enrollments = []
    individual_students = []
    
    for enrollment in enrollments:
        user = User.query.get(enrollment.user_id)
        if user:
            # Get the individual class
            try:
                individual_class = GroupClass.query.filter_by(id=enrollment.class_id, class_type='individual').first() or \
                                   IndividualClass.query.get(enrollment.class_id)
            except Exception:
                db.session.rollback()
                individual_class = None
            
            # Get student's class time selection
            from ..models.classes import StudentClassTimeSelection, ClassTime
            from datetime import datetime
            
            time_selection = StudentClassTimeSelection.query.filter_by(
                enrollment_id=enrollment.id
            ).first()
            
            class_time_info = None
            time_priority = 9999  # Higher priority = appears first (lower number = higher priority)
            if time_selection and time_selection.class_time:
                ct = time_selection.class_time
                # Calculate priority: current/upcoming times get priority 0-100, past times get 100+
                now = datetime.now()
                # Get next occurrence of this time
                days_ahead = (ct.day - now.weekday()) % 7
                if days_ahead == 0 and ct.start_time > now.time():
                    # Today, upcoming
                    time_priority = 0
                elif days_ahead == 0:
                    # Today, past
                    time_priority = 50
                elif days_ahead == 1:
                    # Tomorrow
                    time_priority = 10
                elif days_ahead <= 7:
                    # This week
                    time_priority = 20 + days_ahead
                else:
                    # Next week or later
                    time_priority = 100 + days_ahead
                
                class_time_info = {
                    'time': ct,
                    'display': ct.get_full_display(user.timezone or 'Asia/Kolkata'),
                    'priority': time_priority
                }
            
            student_data = {
                'enrollment': enrollment,
                'user': user,
                'class': individual_class,
                'student_name': enrollment.customer_name or f"{user.first_name} {user.last_name}",
                'student_id': user.student_id or '',
                'class_name': individual_class.name if individual_class else 'Unknown',
                'payment_status': enrollment.status,
                'payment_amount': enrollment.amount,
                'payment_method': enrollment.payment_method or 'N/A',
                'payment_proof': enrollment.payment_proof,
                'registration_date': enrollment.enrolled_at,
                'class_status': 'Active' if enrollment.status == 'completed' else 'Inactive',
                'class_time': class_time_info,
                'time_priority': time_priority
            }
            
            if enrollment.status == 'pending':
                pending_enrollments.append(student_data)
            else:
                individual_students.append(student_data)
    
    # Sort individual students by class time priority (current/upcoming first)
    individual_students.sort(key=lambda x: (x['time_priority'], x['student_name']))
    
    # Apply status filter
    if status_filter:
        if status_filter == 'active':
            individual_students = [s for s in individual_students if s['class_status'] == 'Active']
        elif status_filter == 'inactive':
            individual_students = [s for s in individual_students if s['class_status'] == 'Inactive']
    
    # Get all individual classes for the dropdown/list
    classes = GroupClass.query.filter_by(class_type='individual').all()
    legacy_classes = IndividualClass.query.all()
    all_individual_classes = classes + legacy_classes

    # Get recent materials for individual classes (limit 20)
    try:
        individual_materials = LearningMaterial.query.filter_by(class_type='individual').order_by(LearningMaterial.created_at.desc()).limit(20).all()
    except Exception:
        db.session.rollback()
        individual_materials = []

    # Get monthly payments data (for admin view)
    monthly_payments_data = {}
    selected_month = request.args.get('payment_month', type=int)
    selected_year = request.args.get('payment_year', type=int, default=datetime.now().year)
    
    if selected_month:
        payments = MonthlyPayment.query.filter_by(
            class_type='individual',
            payment_month=selected_month,
            payment_year=selected_year
        ).all()
        
        for payment in payments:
            student_name = payment.user.first_name + ' ' + payment.user.last_name if payment.user else 'Unknown'
            monthly_payments_data[payment.id] = {
                'student_name': student_name,
                'student_id': payment.user.student_id if payment.user else 'N/A',
                'receipt_url': payment.receipt_url,
                'amount': payment.amount,
                'uploaded_at': payment.uploaded_at,
                'status': payment.status
            }

    return render_template('admin_individual_classes.html',
        individual_students=individual_students,
        pending_enrollments=pending_enrollments,
        all_individual_classes=all_individual_classes,
        search=search,
        status_filter=status_filter,
        materials=individual_materials,
        monthly_payments_data=monthly_payments_data,
        selected_month=selected_month,
        selected_year=selected_year
    )


@bp.route('/admin/group-classes', methods=['GET', 'POST'])
@login_required
def admin_group_classes():
    """View and manage group classes with multiple students"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    # Handle POST for sharing materials to multiple group classes
    if request.method == 'POST' and 'share_material' in request.form:
        class_ids = request.form.getlist('class_ids')
        title = request.form.get('title', '').strip()
        content = request.form.get('message', '').strip()
        
        if not class_ids:
            flash('Please select at least one group class.', 'danger')
        elif not content and not request.files.get('material_file'):
            flash('Please provide content or upload a file.', 'danger')
        else:
            from ..services.cloudinary_service import CloudinaryService
            from werkzeug.utils import secure_filename
            import re
            
            material_type = 'text'
            file_url = None
            file_type = None
            file_name = None
            youtube_url = None
            
            youtube_pattern = r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})'
            youtube_match = re.search(youtube_pattern, content)
            if youtube_match:
                youtube_url = f"https://www.youtube.com/watch?v={youtube_match.group(1)}"
                material_type = 'youtube'
            
            uploaded_file = request.files.get('material_file')
            if uploaded_file and uploaded_file.filename:
                file_name = secure_filename(uploaded_file.filename)
                file_ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
                
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
                
                success, result = CloudinaryService.upload_file(
                    file=uploaded_file,
                    folder='learning_materials',
                    resource_type=resource_type
                )
                
                if success:
                    file_url = result.get('url')
                    file_type = result.get('format', file_ext)
                else:
                    flash(f'File upload failed: {result}', 'warning')
            
            try:
                shared_count = 0
                for class_id_str in class_ids:
                    class_id = int(class_id_str)
                    class_obj = GroupClass.query.get(class_id)
                    if class_obj and class_obj.class_type == 'group':
                        material = LearningMaterial(
                            class_id=f"group_{class_id}",
                            class_type='group',
                            actual_class_id=class_id,
                            title=title,
                            content=content,
                            created_by=current_user.id,
                            material_type=material_type,
                            file_url=file_url,
                            file_type=file_type,
                            file_name=file_name,
                            youtube_url=youtube_url
                        )
                        db.session.add(material)
                        shared_count += 1
                
                db.session.commit()
                flash(f'Material shared with {len(class_ids)} group class(es)!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error sharing material: {str(e)}', 'danger')
            return redirect(url_for('admin.admin_group_classes'))
    
    # Get search parameter
    search = request.args.get('search', '').strip()
    
    # Get all group classes
    query = GroupClass.query.filter_by(class_type='group')
    
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
    
    # Get recent materials for group classes (limit 20)
    try:
        group_materials = LearningMaterial.query.filter_by(class_type='group').order_by(LearningMaterial.created_at.desc()).limit(20).all()
    except Exception:
        db.session.rollback()
        group_materials = []
    
    # Get monthly payments data (for admin view)
    monthly_payments_data = {}
    selected_month = request.args.get('payment_month', type=int)
    selected_year = request.args.get('payment_year', type=int, default=datetime.now().year)
    
    if selected_month:
        payments = MonthlyPayment.query.filter_by(
            class_type='group',
            payment_month=selected_month,
            payment_year=selected_year
        ).all()
        
        for payment in payments:
            student_name = payment.user.first_name + ' ' + payment.user.last_name if payment.user else 'Unknown'
            monthly_payments_data[payment.id] = {
                'student_name': student_name,
                'student_id': payment.user.student_id if payment.user else 'N/A',
                'receipt_url': payment.receipt_url,
                'amount': payment.amount,
                'uploaded_at': payment.uploaded_at,
                'status': payment.status
            }
    
    return render_template('admin_group_classes.html',
        group_classes=group_classes,
        search=search,
        materials=group_materials,
        monthly_payments_data=monthly_payments_data,
        selected_month=selected_month,
        selected_year=selected_year
    )


@bp.route('/admin/group-classes/<int:class_id>', methods=['GET', 'POST'])
@login_required
def admin_group_class_detail(class_id):
    """View detailed information about a specific group class"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    # Handle POST actions (approve, reject, remove student, close class)
    if request.method == 'POST':
        action = request.form.get('action')
        user_id = request.form.get('user_id', type=int)
        enrollment_id = request.form.get('enrollment_id', type=int)
        
        group_class = GroupClass.query.get_or_404(class_id)
        
        # Handle enrollment approval/rejection
        if enrollment_id and action in ['approve', 'reject']:
            enrollment = ClassEnrollment.query.get(enrollment_id)
            if enrollment and enrollment.class_type == 'group' and enrollment.class_id == class_id:
                if action == 'approve':
                    user = User.query.get(enrollment.user_id)
                    if user:
                        # Generate Group System ID if not exists
                        try:
                            if not enrollment.group_system_id:
                                from ..models.classes import generate_group_system_id
                                enrollment.group_system_id = generate_group_system_id()
                        except Exception as e:
                            # Handle case where group_system_id column doesn't exist yet
                            if 'group_system_id' in str(e).lower() or 'column' in str(e).lower():
                                flash('Database migration required. Please visit /admin/add-group-system-id-column first.', 'warning')
                                return redirect(url_for('admin.admin_group_class_detail', class_id=class_id))
                            raise
                        
                        # CRITICAL: Group students should NOT have individual student IDs (STU-XXXXX)
                        # They only use Group System ID (GRO-XXXXX)
                            user.class_type = 'group'
                        
                        # Check if user has any individual class enrollments
                        individual_enrollment = ClassEnrollment.query.filter_by(
                            user_id=user.id,
                            class_type='individual',
                            status='completed'
                        ).first()
                        
                        # Only remove student_id if user has NO individual enrollments
                        if not individual_enrollment and user.student_id:
                            # User is only in group classes - remove individual student ID
                            user.student_id = None
                            db.session.flush()
                        
                        # Check if class is full
                        if len(group_class.students) >= group_class.max_students:
                            flash(f'Cannot approve: Group class is full ({len(group_class.students)}/{group_class.max_students} students).', 'warning')
                        elif user not in group_class.students:
                            group_class.students.append(user)
                            enrollment.status = 'completed'
                            
                            # Generate ID Card
                            try:
                                from ..models.id_cards import generate_group_student_id_card
                                id_card = generate_group_student_id_card(enrollment, user, group_class, current_user.id)
                                db.session.commit()
                                flash(f'Enrollment approved! Group System ID: {enrollment.group_system_id}. ID Card generated. Student will be redirected to view ID card immediately.', 'success')
                            except Exception as e:
                                db.session.rollback()
                                db.session.commit()
                                flash(f'Enrollment approved! Group System ID: {enrollment.group_system_id}. Error generating ID card: {str(e)}', 'warning')
                        else:
                            enrollment.status = 'completed'
                            db.session.commit()
                            flash(f'Enrollment approved! Group System ID: {enrollment.group_system_id}', 'success')
                elif action == 'reject':
                    enrollment.status = 'rejected'
                    db.session.commit()
                    flash('Enrollment rejected.', 'warning')
            return redirect(url_for('admin.admin_group_class_detail', class_id=class_id))
        
        if action == 'remove_student' and user_id:
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
    
    # Get all students in this group class (approved)
    students = []
    for student in group_class.students:
        enrollment = ClassEnrollment.query.filter_by(
            user_id=student.id,
            class_id=class_id,
            class_type='group',
            status='completed'
        ).first()
        
        # Get ID card for this student
        id_card = get_id_card_for_entity('group', student.id) if student else None
        
        students.append({
            'user': student,
            'student_name': f"{student.first_name} {student.last_name}",
            'student_id': student.student_id or 'N/A',
            'payment_status': enrollment.status if enrollment else 'N/A',
            'registration_date': enrollment.enrolled_at if enrollment else None,
            'enrollment': enrollment,  # Include enrollment to access group_system_id
            'id_card': id_card  # Include ID card
        })
    
    # Get pending enrollments for this group class
    pending_enrollments = []
    pending_enrollments_query = ClassEnrollment.query.filter_by(
        class_id=class_id,
        class_type='group',
        status='pending'
    ).all()
    
    for enrollment in pending_enrollments_query:
        user = User.query.get(enrollment.user_id)
        if user:
            pending_enrollments.append({
                'enrollment': enrollment,
                'user': user,
                'student_name': enrollment.customer_name or f"{user.first_name} {user.last_name}",
                'payment_amount': enrollment.amount,
                'payment_method': enrollment.payment_method or 'N/A',
                'payment_proof': enrollment.payment_proof,
                'registration_date': enrollment.enrolled_at
            })
    
    return render_template('admin_group_class_detail.html',
        group_class=group_class,
        students=students,
        pending_enrollments=pending_enrollments
    )


@bp.route('/admin/family-classes', methods=['GET', 'POST'])
@login_required
def admin_family_classes():
    """View and manage family-based registrations"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    # Handle POST for sharing materials to multiple family classes
    if request.method == 'POST' and 'share_material' in request.form:
        enrollment_ids = request.form.getlist('enrollment_ids')  # Family enrollments
        title = request.form.get('title', '').strip()
        content = request.form.get('message', '').strip()
        
        if not enrollment_ids:
            flash('Please select at least one family class.', 'danger')
        elif not content and not request.files.get('material_file'):
            flash('Please provide content or upload a file.', 'danger')
        else:
            from ..services.cloudinary_service import CloudinaryService
            from werkzeug.utils import secure_filename
            import re
            
            material_type = 'text'
            file_url = None
            file_type = None
            file_name = None
            youtube_url = None
            
            youtube_pattern = r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})'
            youtube_match = re.search(youtube_pattern, content)
            if youtube_match:
                youtube_url = f"https://www.youtube.com/watch?v={youtube_match.group(1)}"
                material_type = 'youtube'
            
            uploaded_file = request.files.get('material_file')
            if uploaded_file and uploaded_file.filename:
                file_name = secure_filename(uploaded_file.filename)
                file_ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
                
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
                
                success, result = CloudinaryService.upload_file(
                    file=uploaded_file,
                    folder='learning_materials',
                    resource_type=resource_type
                )
                
                if success:
                    file_url = result.get('url')
                    file_type = result.get('format', file_ext)
                else:
                    flash(f'File upload failed: {result}', 'warning')
            
            try:
                shared_count = 0
                for enrollment_id_str in enrollment_ids:
                    enrollment_id = int(enrollment_id_str)
                    enrollment = ClassEnrollment.query.get(enrollment_id)
                    if enrollment and enrollment.class_type == 'family' and enrollment.status == 'completed':
                        material = LearningMaterial(
                            class_id=f"family_{enrollment.class_id}",
                            class_type='family',
                            actual_class_id=enrollment.class_id,
                            title=title,
                            content=content,
                            created_by=current_user.id,
                            material_type=material_type,
                            file_url=file_url,
                            file_type=file_type,
                            file_name=file_name,
                            youtube_url=youtube_url
                        )
                        db.session.add(material)
                        shared_count += 1
                
                db.session.commit()
                flash(f'Material shared with {len(enrollment_ids)} family class(es)!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error sharing material: {str(e)}', 'danger')
            return redirect(url_for('admin.admin_family_classes'))
    
    # Get search parameter
    search = request.args.get('search', '').strip()
    
    # Get all family class enrollments (including pending for approval)
    query = ClassEnrollment.query.filter_by(class_type='family')
    
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
    
    # Build family list (separate pending and completed)
    pending_families = []
    families = []
    
    for enrollment in enrollments:
        user = User.query.get(enrollment.user_id)
        family_members = FamilyMember.query.filter_by(enrollment_id=enrollment.id).all()
        
        family_data = {
            'enrollment': enrollment,
            'parent_user': user,
            'family_name': enrollment.customer_name or f"{user.first_name} {user.last_name}" if user else 'Unknown',
            'total_students': len(family_members) + 1,  # +1 for the parent/registrant
            'payment_status': enrollment.status,
            'payment_amount': enrollment.amount,
            'payment_method': enrollment.payment_method or 'N/A',
            'payment_proof': enrollment.payment_proof,
            'registration_date': enrollment.enrolled_at,
            'family_members': family_members
        }
        
        if enrollment.status == 'pending':
            pending_families.append(family_data)
        else:
            families.append(family_data)
    
    # Get recent materials for family classes (limit 20)
    try:
        family_materials = LearningMaterial.query.filter_by(class_type='family').order_by(LearningMaterial.created_at.desc()).limit(20).all()
    except Exception:
        db.session.rollback()
        family_materials = []
    
    # Get monthly payments data (for admin view)
    monthly_payments_data = {}
    selected_month = request.args.get('payment_month', type=int)
    selected_year = request.args.get('payment_year', type=int, default=datetime.now().year)
    
    if selected_month:
        payments = MonthlyPayment.query.filter_by(
            class_type='family',
            payment_month=selected_month,
            payment_year=selected_year
        ).all()
        
        for payment in payments:
            student_name = payment.user.first_name + ' ' + payment.user.last_name if payment.user else 'Unknown'
            monthly_payments_data[payment.id] = {
                'student_name': student_name,
                'student_id': payment.user.student_id if payment.user else 'N/A',
                'receipt_url': payment.receipt_url,
                'amount': payment.amount,
                'uploaded_at': payment.uploaded_at,
                'status': payment.status
            }
    
    return render_template('admin_family_classes.html',
        families=families,
        pending_families=pending_families,
        search=search,
        materials=family_materials,
        monthly_payments_data=monthly_payments_data,
        selected_month=selected_month,
        selected_year=selected_year
    )


@bp.route('/admin/family-classes/<int:enrollment_id>', methods=['GET', 'POST'])
@login_required
def admin_family_class_detail(enrollment_id):
    """View detailed information about a specific family class"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    # Handle POST actions (approve, reject, suspend family, add/remove family member)
    if request.method == 'POST':
        action = request.form.get('action')
        form_enrollment_id = request.form.get('enrollment_id', type=int)
        
        # Use form_enrollment_id if provided, otherwise use route parameter
        target_enrollment_id = form_enrollment_id if form_enrollment_id else enrollment_id
        enrollment = ClassEnrollment.query.get_or_404(target_enrollment_id)
        
        if enrollment.class_type != 'family':
            flash('This is not a family class enrollment.', 'danger')
            return redirect(url_for('admin.admin_family_classes'))
        
        # Handle enrollment approval/rejection
        if action in ['approve', 'reject']:
            if action == 'approve':
                user = User.query.get(enrollment.user_id)
                if user:
                    # Generate Family System ID for the enrollment if not exists
                    try:
                        if not enrollment.family_system_id:
                            from ..models.classes import generate_family_system_id
                            enrollment.family_system_id = generate_family_system_id()
                    except Exception as e:
                        # Handle case where family_system_id column doesn't exist yet
                        if 'family_system_id' in str(e).lower() or 'column' in str(e).lower():
                            flash('Database migration required. Please visit /admin/add-family-system-id-column first.', 'warning')
                            return redirect(url_for('admin.admin_family_class_detail', enrollment_id=enrollment_id))
                        raise
                    
                    # Generate Student ID if not exists
                    if not user.student_id:
                        from ..models.classes import generate_student_id_for_class
                        new_student_id = generate_student_id_for_class('family')
                        existing_user = User.query.filter_by(student_id=new_student_id).first()
                        if existing_user and existing_user.id != user.id:
                            new_student_id = generate_student_id_for_class('family')
                        user.student_id = new_student_id
                        user.class_type = 'family'
                        db.session.flush()
                    
                    # Generate Student IDs for all family members
                    family_members = FamilyMember.query.filter_by(enrollment_id=enrollment.id).all()
                    for member in family_members:
                        if member.user_id:
                            member_user = User.query.get(member.user_id)
                            if member_user and not member_user.student_id:
                                member_user.student_id = generate_student_id_for_class('family')
                                member_user.class_type = 'family'
                    
                    enrollment.status = 'completed'
                    
                    # Get class object
                    class_obj = GroupClass.query.get(enrollment.class_id) or IndividualClass.query.get(enrollment.class_id)
                    
                    # Generate ID Card
                    try:
                        from ..models.id_cards import generate_family_id_card
                        id_card = generate_family_id_card(enrollment, user, class_obj, current_user.id)
                        db.session.commit()
                        flash(f'Family enrollment approved! Family System ID: {enrollment.family_system_id}. ID Card generated. Family will be redirected to view ID card immediately.', 'success')
                    except Exception as e:
                        db.session.rollback()
                        db.session.commit()
                        flash(f'Family enrollment approved! Family System ID: {enrollment.family_system_id}. Error generating ID card: {str(e)}', 'warning')
            elif action == 'reject':
                enrollment.status = 'rejected'
                db.session.commit()
                flash('Family enrollment rejected.', 'warning')
            return redirect(url_for('admin.admin_family_classes'))
        
        if action == 'suspend_family':
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
    
    # Get ID card for this family
    id_card = get_id_card_for_entity('family', enrollment_id)
    
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
        family_members=family_members,
        id_card=id_card
    )


@bp.route('/student/upload-payment', methods=['POST'])
@login_required
def upload_monthly_payment():
    """Route for students to upload monthly payment receipts"""
    from ..services.cloudinary_service import CloudinaryService
    from werkzeug.utils import secure_filename
    from datetime import datetime
    
    enrollment_id = request.form.get('enrollment_id', type=int)
    payment_month = request.form.get('payment_month', type=int)
    payment_year = request.form.get('payment_year', type=int)
    amount = request.form.get('amount', type=float)
    
    if not enrollment_id or not payment_month or not payment_year or not amount:
        flash('Please fill in all required fields.', 'danger')
        return redirect(url_for('admin.student_dashboard'))
    
    # Verify enrollment belongs to current user
    enrollment = ClassEnrollment.query.get(enrollment_id)
    if not enrollment or enrollment.user_id != current_user.id:
        flash('Invalid enrollment.', 'danger')
        return redirect(url_for('admin.student_dashboard'))
    
    # Check if payment already exists
    existing_payment = MonthlyPayment.query.filter_by(
        enrollment_id=enrollment_id,
        payment_month=payment_month,
        payment_year=payment_year
    ).first()
    
    if existing_payment:
        flash(f'Payment receipt for {existing_payment.get_month_name()} {payment_year} already uploaded.', 'warning')
        return redirect(url_for('admin.student_dashboard'))
    
    # Handle file upload
    uploaded_file = request.files.get('receipt_file')
    if not uploaded_file or not uploaded_file.filename:
        flash('Please upload a payment receipt.', 'danger')
        return redirect(url_for('admin.student_dashboard'))
    
    try:
        file_name = secure_filename(uploaded_file.filename)
        success, result = CloudinaryService.upload_file(
            file=uploaded_file,
            folder='monthly_payments',
            resource_type='auto'
        )
        
        if success and isinstance(result, dict) and result.get('url'):
            # Create payment record
            payment = MonthlyPayment(
                user_id=current_user.id,
                enrollment_id=enrollment_id,
                class_type=enrollment.class_type,
                payment_month=payment_month,
                payment_year=payment_year,
                amount=amount,
                receipt_url=result.get('url'),
                receipt_filename=file_name,
                status='pending'
            )
            db.session.add(payment)
            db.session.commit()
            flash(f'Payment receipt for {payment.get_month_name()} {payment_year} uploaded successfully!', 'success')
        else:
            flash('Error uploading receipt. Please try again.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error uploading payment: {str(e)}', 'danger')
    
    return redirect(url_for('admin.student_dashboard'))


@bp.route('/admin/monthly-payment/<int:payment_id>/approve', methods=['POST'])
@login_required
def approve_monthly_payment(payment_id):
    """Approve a monthly payment"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    payment = MonthlyPayment.query.get_or_404(payment_id)
    
    try:
        payment.status = 'verified'
        payment.verified_by = current_user.id
        payment.verified_at = datetime.utcnow()
        db.session.commit()
        month_name = payment.get_month_name()
        flash(f'Payment for {month_name} {payment.payment_year} approved successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error approving payment: {str(e)}', 'danger')
    
    # Redirect back to the admin page that shows payments
    referer = request.headers.get('Referer', url_for('admin.admin_dashboard'))
    return redirect(referer)


@bp.route('/admin/monthly-payment/<int:payment_id>/reject', methods=['POST'])
@login_required
def reject_monthly_payment(payment_id):
    """Reject a monthly payment"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    payment = MonthlyPayment.query.get_or_404(payment_id)
    notes = request.form.get('notes', '')
    
    try:
        payment.status = 'rejected'
        payment.verified_by = current_user.id
        payment.verified_at = datetime.utcnow()
        if notes:
            payment.notes = notes
        db.session.commit()
        month_name = payment.get_month_name()
        flash(f'Payment for {month_name} {payment.payment_year} rejected.', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error rejecting payment: {str(e)}', 'danger')
    
    # Redirect back to the admin page that shows payments
    referer = request.headers.get('Referer', url_for('admin.admin_dashboard'))
    return redirect(referer)


@bp.route('/admin/schools', methods=['GET', 'POST'])
@login_required
def admin_schools():
    """View all registered schools and school classes"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    # Handle POST for sharing materials to multiple schools
    if request.method == 'POST':
        school_ids = request.form.getlist('school_ids')  # Get multiple school IDs
        title = request.form.get('title', '').strip()
        content = request.form.get('message', '').strip()
        
        if not school_ids:
            flash('Please select at least one school.', 'danger')
        elif not content and not request.files.get('material_file'):
            flash('Please provide content or upload a file.', 'danger')
        else:
            # Process file upload and material creation (reuse logic from admin_dashboard)
            from ..services.cloudinary_service import CloudinaryService
            from werkzeug.utils import secure_filename
            import re
            
            material_type = 'text'
            file_url = None
            file_type = None
            file_name = None
            youtube_url = None
            
            # Detect YouTube URL
            youtube_pattern = r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})'
            youtube_match = re.search(youtube_pattern, content)
            if youtube_match:
                youtube_url = f"https://www.youtube.com/watch?v={youtube_match.group(1)}"
                material_type = 'youtube'
            
            # Handle file upload
            uploaded_file = request.files.get('material_file')
            if uploaded_file and uploaded_file.filename:
                file_name = secure_filename(uploaded_file.filename)
                file_ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
                
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
                
                success, result = CloudinaryService.upload_file(
                    file=uploaded_file,
                    folder='learning_materials',
                    resource_type=resource_type
                )
                
                if success:
                    file_url = result.get('url')
                    file_type = result.get('format', file_ext)
                else:
                    flash(f'File upload failed: {result}', 'warning')
            
            # Share material to each selected school
            try:
                shared_count = 0
                for school_id_str in school_ids:
                    school_id = int(school_id_str)
                    school = School.query.get(school_id)
                    if school and school.status == 'active':
                        # Get all classes this school has joined
                        # Check if school has user_id, otherwise find enrollments by school_id or school_name
                        if school.user_id:
                            enrollments = ClassEnrollment.query.filter_by(
                                user_id=school.user_id,
                                class_type='school',
                                status='completed'
                            ).all()
                        else:
                            # Fallback: find enrollments by matching school name or system ID
                            from sqlalchemy import or_
                            from ..models.classes import SchoolStudent, ClassEnrollment as CE
                            # Get enrollments through SchoolStudent records
                            school_students = SchoolStudent.query.filter_by(school_name=school.school_name).all()
                            enrollment_ids = list(set([s.enrollment_id for s in school_students]))
                            if enrollment_ids:
                                enrollments = CE.query.filter(
                                    CE.id.in_(enrollment_ids),
                                    CE.class_type == 'school',
                                    CE.status == 'completed'
                                ).all()
                            else:
                                enrollments = []
                        
                        # Share material to each class this school has joined
                        for enrollment in enrollments:
                            material = LearningMaterial(
                                class_id=f"school_{enrollment.class_id}",
                                class_type='school',
                                actual_class_id=enrollment.class_id,
                                title=title,
                                content=content,
                                created_by=current_user.id,
                                material_type=material_type,
                                file_url=file_url,
                                file_type=file_type,
                                file_name=file_name,
                                youtube_url=youtube_url
                            )
                            db.session.add(material)
                            shared_count += 1
                
                db.session.commit()
                flash(f'Material shared with {len(school_ids)} school(s)! Total {shared_count} class(es) received the material.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error sharing material: {str(e)}', 'danger')
    
    schools = School.query.order_by(School.created_at.desc()).all()
    
    # Get counts and enrollment info for each school
    from ..models.classes import ClassEnrollment
    for school in schools:
        school.student_count = RegisteredSchoolStudent.query.filter_by(school_id=school.id).count()
        # Get enrollment count (classes this school has joined)
        if school.user_id:
            school.enrollment_count = ClassEnrollment.query.filter_by(
                user_id=school.user_id,
                class_type='school',
                status='completed'
            ).count()
            school.pending_enrollment_count = ClassEnrollment.query.filter_by(
                user_id=school.user_id,
                class_type='school',
                status='pending'
            ).count()
        else:
            school.enrollment_count = 0
            school.pending_enrollment_count = 0
    
    # Get all school-type classes
    try:
        school_classes = GroupClass.query.filter_by(class_type='school').all()
    except Exception:
        db.session.rollback()
        school_classes = []
        
    # Get recent materials for school classes (limit 20)
    try:
        school_materials = LearningMaterial.query.filter_by(class_type='school').order_by(LearningMaterial.created_at.desc()).limit(20).all()
    except Exception:
        db.session.rollback()
        school_materials = []
        
    # Get monthly payments data (for admin view)
    monthly_payments_data = {}
    selected_month = request.args.get('payment_month', type=int)
    selected_year = request.args.get('payment_year', type=int, default=datetime.now().year)
    
    if selected_month:
        payments = MonthlyPayment.query.filter_by(
            class_type='school',
            payment_month=selected_month,
            payment_year=selected_year
        ).all()
        
        for payment in payments:
            student_name = payment.user.first_name + ' ' + payment.user.last_name if payment.user else 'Unknown'
            monthly_payments_data[payment.id] = {
                'student_name': student_name,
                'student_id': payment.user.student_id if payment.user else 'N/A',
                'receipt_url': payment.receipt_url,
                'amount': payment.amount,
                'uploaded_at': payment.uploaded_at,
                'status': payment.status
            }
    
    return render_template('admin_schools.html', 
        schools=schools, 
        school_classes=school_classes, 
        materials=school_materials,
        monthly_payments_data=monthly_payments_data,
        selected_month=selected_month,
        selected_year=selected_year
    )


@bp.route('/admin/schools/<int:school_id>')
@login_required
def admin_school_detail(school_id):
    """View school details, students, and classes"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    school = School.query.get_or_404(school_id)
    
    # Get ID card for this school
    id_card = get_id_card_for_entity('school', school_id)
    
    students = RegisteredSchoolStudent.query.filter_by(school_id=school_id).order_by(RegisteredSchoolStudent.created_at.desc()).all()
    
    # Get ID cards for school students
    student_id_cards = {}
    for student in students:
        student_id_card = get_id_card_for_entity('school_student', student.id)
        if student_id_card:
            student_id_cards[student.id] = student_id_card
    
    # Get classes this school has enrolled in with students per class
    school_classes = []
    students_by_class = {}  # {class_id: [list of SchoolStudent]}
    enrolled_class_ids = set()
    if school.user_id:
        enrollments = ClassEnrollment.query.filter_by(
            user_id=school.user_id,
            class_type='school',
            status='completed'
        ).all()
        
        for enrollment in enrollments:
            class_obj = GroupClass.query.get(enrollment.class_id)
            if class_obj:
                enrolled_class_ids.add(enrollment.class_id)
                # CRITICAL: Get students registered for THIS specific class and THIS school only
                # Filter by enrollment_id (unique to school) and class_id to ensure strict isolation
                from ..models.classes import SchoolStudent
                class_students = SchoolStudent.query.filter_by(
                    class_id=enrollment.class_id,  # THIS class only
                    enrollment_id=enrollment.id  # THIS school's enrollment only
                ).order_by(SchoolStudent.student_name).all()
                students_by_class[enrollment.class_id] = class_students
                
                school_classes.append({
                    'id': class_obj.id,
                    'name': class_obj.name,
                    'description': class_obj.description,
                    'enrolled_at': enrollment.enrolled_at,
                    'enrollment_id': enrollment.id,
                    'student_count': len(class_students)
                })
    
    # Get all available school classes (for enrollment dropdown)
    available_school_classes = GroupClass.query.filter_by(class_type='school').all()
    # Filter out already enrolled classes
    available_school_classes = [c for c in available_school_classes if c.id not in enrolled_class_ids]
    
    # Calculate attendance summary for each student
    attendance_summary = {}  # {student_id: {'present': count, 'total': count}}
    attendance_history = {}  # {student_id: [{'date': date, 'status': 'present'/'absent', 'class_name': name}]}
    
    from datetime import date, timedelta
    from ..models.classes import Attendance
    
    # Get attendance for last 30 days
    thirty_days_ago = date.today() - timedelta(days=30)
    
    for cls in school_classes:
        class_students = students_by_class.get(cls['id'], [])
        for student in class_students:
            if student.id not in attendance_summary:
                attendance_summary[student.id] = {'present': 0, 'total': 0}
                attendance_history[student.id] = []
            
            # Get attendance records for this student in this class
            # Note: Attendance uses school admin's user_id, but we check notes field
            school_admin = User.query.get(student.registered_by)
            if school_admin:
                attendance_records = Attendance.query.filter(
                    Attendance.student_id == school_admin.id,
                    Attendance.class_id == cls['id'],
                    Attendance.class_type == 'school',
                    Attendance.attendance_date >= thirty_days_ago,
                    Attendance.notes.like(f'%school_student_{student.id}%')
                ).order_by(Attendance.attendance_date.desc()).all()
                
                for att in attendance_records:
                    attendance_summary[student.id]['total'] += 1
                    if att.status == 'present':
                        attendance_summary[student.id]['present'] += 1
                    
                    attendance_history[student.id].append({
                        'date': att.attendance_date,
                        'status': att.status,
                        'class_name': cls['name']
                    })
    
    # Get daily attendance if filters are provided
    daily_attendance = {}  # {student_id: {'status': 'present'/'absent'}}
    attendance_class_id = request.args.get('attendance_class_id', type=int)
    attendance_date_str = request.args.get('attendance_date', '')
    
    if attendance_class_id and attendance_date_str:
        try:
            from datetime import datetime
            attendance_date = datetime.strptime(attendance_date_str, '%Y-%m-%d').date()
            
            class_students = students_by_class.get(attendance_class_id, [])
            for student in class_students:
                school_admin = User.query.get(student.registered_by)
                if school_admin:
                    att = Attendance.query.filter(
                        Attendance.student_id == school_admin.id,
                        Attendance.class_id == attendance_class_id,
                        Attendance.class_type == 'school',
                        Attendance.attendance_date == attendance_date,
                        Attendance.notes.like(f'%school_student_{student.id}%')
                    ).first()
                    
                    if att:
                        daily_attendance[student.id] = {'status': att.status}
        except:
            pass  # Ignore date parsing errors
                
    return render_template('admin_school_detail.html', 
                         school=school, 
                         students=students,
                         school_classes=school_classes,
                         students_by_class=students_by_class,
                         available_school_classes=available_school_classes,
                         attendance_summary=attendance_summary,
                         attendance_history=attendance_history,
                         daily_attendance=daily_attendance,
                         id_card=id_card,
                         student_id_cards=student_id_cards)


@bp.route('/admin/schools/<int:school_id>/approve', methods=['POST'])
@login_required
def approve_school(school_id):
    """Approve a school registration"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    school = School.query.get_or_404(school_id)
    
    try:
        is_reapproval = school.status == 'active'
        school.status = 'active'
        if not school.approved_at:
            school.approved_at = datetime.utcnow()
            school.approved_by = current_user.id
        
        # CRITICAL FIX: Update all school enrollments to 'completed' status
        # This is required for admin material sharing to work correctly
        # Also handles schools that were approved before this fix was applied
        from ..models.classes import ClassEnrollment
        enrollments = ClassEnrollment.query.filter_by(
            user_id=school.user_id,
            class_type='school'
        ).filter(
            ClassEnrollment.status.in_(['pending', 'completed'])
        ).all()
        
        enrollment_count = 0
        for enrollment in enrollments:
            if enrollment.status != 'completed':
                enrollment.status = 'completed'
                enrollment_count += 1
        
        db.session.commit()
        
        # Generate ID Card (only for new approvals)
        if not is_reapproval:
            try:
                from ..models.id_cards import generate_school_id_card
                id_card = generate_school_id_card(school, current_user.id)
                db.session.commit()
                if enrollment_count > 0:
                    flash(f'School "{school.school_name}" has been approved! {enrollment_count} class enrollment(s) activated. ID Card generated. School will be redirected to view ID card immediately.', 'success')
                else:
                    flash(f'School "{school.school_name}" has been approved! ID Card generated. School will be redirected to view ID card immediately.', 'success')
            except Exception as e:
                if enrollment_count > 0:
                    flash(f'School "{school.school_name}" has been approved! {enrollment_count} class enrollment(s) activated. Error generating ID card: {str(e)}', 'warning')
                else:
                    flash(f'School "{school.school_name}" has been approved! Error generating ID card: {str(e)}', 'warning')
        else:
            if enrollment_count > 0:
                flash(f'School "{school.school_name}" re-approved! {enrollment_count} class enrollment(s) activated.', 'success')
            else:
                flash(f'School "{school.school_name}" is already approved with active enrollments.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error approving school: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_school_detail', school_id=school_id))


@bp.route('/admin/schools/repair-enrollments', methods=['POST'])
@login_required
def repair_school_enrollments():
    """Repair enrollments for all schools - activate pending and create missing enrollments"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    from ..models.classes import ClassEnrollment, GroupClass
    from ..models.gallery import ClassPricing
    import uuid
    
    try:
        # Get all schools (active and pending)
        all_schools = School.query.all()
        repaired_count = 0
        activated_count = 0
        created_count = 0
        
        # Get pricing
        pricing_data = ClassPricing.get_all_pricing()
        school_pricing = pricing_data.get('school', {'price': 500, 'name': 'School Plan'})
        amount = school_pricing.get('price', 500)
        
        # Get all school classes
        school_classes = GroupClass.query.filter_by(class_type='school').all()
        
        for school in all_schools:
            if not school.user_id:
                continue
            
            school_repaired = False
            
            # Step 1: Activate any pending enrollments
            pending_enrollments = ClassEnrollment.query.filter_by(
                user_id=school.user_id,
                class_type='school',
                status='pending'
            ).all()
            
            for enrollment in pending_enrollments:
                enrollment.status = 'completed'
                activated_count += 1
                school_repaired = True
            
            # Step 2: If school has NO enrollments at all, create one for the first available school class
            existing_enrollments = ClassEnrollment.query.filter_by(
                user_id=school.user_id,
                class_type='school'
            ).all()
            
            if not existing_enrollments and school_classes:
                # Create enrollment for the first school class (admin can change this later)
                first_class = school_classes[0]
                enrollment = ClassEnrollment(
                    user_id=school.user_id,
                    class_type='school',
                    class_id=first_class.id,
                    amount=amount,
                    customer_name=school.school_name,
                    customer_email=school.school_email,
                    customer_phone=school.contact_phone,
                    customer_address=school.contact_address,
                    payment_method='admin_repair',
                    transaction_id=f"REPAIR-{str(uuid.uuid4())[:8].upper()}",
                    status='completed' if school.status == 'active' else 'pending'
                )
                db.session.add(enrollment)
                created_count += 1
                school_repaired = True
            
            if school_repaired:
                repaired_count += 1
        
        db.session.commit()
        
        message_parts = []
        if activated_count > 0:
            message_parts.append(f"activated {activated_count} pending enrollment(s)")
        if created_count > 0:
            message_parts.append(f"created {created_count} new enrollment(s)")
        
        if repaired_count > 0:
            flash(f'Repaired {repaired_count} school(s)! {", ".join(message_parts)}.', 'success')
        else:
            flash('All schools already have proper enrollments.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error repairing enrollments: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_schools'))


@bp.route('/admin/schools/<int:school_id>/enroll-class', methods=['POST'])
@login_required
def enroll_school_in_class(school_id):
    """Manually enroll a school in a class"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    school = School.query.get_or_404(school_id)
    class_id = request.form.get('class_id', type=int)
    
    if not class_id:
        flash('Please select a class.', 'danger')
        return redirect(url_for('admin.admin_school_detail', school_id=school_id))
    
    if not school.user_id:
        flash('School does not have a user account. Cannot create enrollment.', 'danger')
        return redirect(url_for('admin.admin_school_detail', school_id=school_id))
    
    from ..models.classes import ClassEnrollment, GroupClass
    from ..models.gallery import ClassPricing
    import uuid
    
    # Check if class exists and is a school class
    class_obj = GroupClass.query.get(class_id)
    if not class_obj:
        flash('Class not found.', 'danger')
        return redirect(url_for('admin.admin_school_detail', school_id=school_id))
    
    if getattr(class_obj, 'class_type', None) != 'school':
        flash('Selected class is not a school class.', 'danger')
        return redirect(url_for('admin.admin_school_detail', school_id=school_id))
    
    # Check if enrollment already exists
    existing = ClassEnrollment.query.filter_by(
        user_id=school.user_id,
        class_type='school',
        class_id=class_id
    ).first()
    
    if existing:
        if existing.status == 'completed':
            flash(f'School is already enrolled in "{class_obj.name}".', 'info')
        else:
            # Activate pending enrollment
            existing.status = 'completed'
            db.session.commit()
            flash(f'School enrollment in "{class_obj.name}" has been activated!', 'success')
        return redirect(url_for('admin.admin_school_detail', school_id=school_id))
    
    # Get pricing
    pricing_data = ClassPricing.get_all_pricing()
    school_pricing = pricing_data.get('school', {'price': 500, 'name': 'School Plan'})
    amount = school_pricing.get('price', 500)
    
    try:
        # Create new enrollment
        enrollment = ClassEnrollment(
            user_id=school.user_id,
            class_type='school',
            class_id=class_id,
            amount=amount,
            customer_name=school.school_name,
            customer_email=school.school_email,
            customer_phone=school.contact_phone,
            customer_address=school.contact_address,
            payment_method='admin_manual',
            transaction_id=f"ADMIN-{str(uuid.uuid4())[:8].upper()}",
            status='completed'  # Auto-complete since admin is enrolling manually
        )
        db.session.add(enrollment)
        db.session.commit()
        flash(f'School "{school.school_name}" has been enrolled in "{class_obj.name}"!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error enrolling school: {str(e)}', 'danger')
    
    return redirect(url_for('admin.admin_school_detail', school_id=school_id))


@bp.route('/admin/schools/<int:school_id>/reject', methods=['POST'])
@login_required
def reject_school(school_id):
    """Reject a school registration"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
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


@bp.route('/profile/upload', methods=['POST'])
@login_required
def upload_profile_picture():
    """Upload profile picture for current user"""
    if 'profile_picture' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(request.referrer or url_for('admin.student_dashboard'))
    
    file = request.files['profile_picture']
    if file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(request.referrer or url_for('admin.student_dashboard'))
    
    try:
        from ..services.cloudinary_service import CloudinaryService
        from datetime import datetime
        
        # Upload to Cloudinary
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        public_id = f"profile_{current_user.id}_{timestamp}"
        
        success, result = CloudinaryService.upload_file(
            file=file,
            folder='profile_pictures',
            resource_type='image',
            public_id=public_id
        )
        
        if success:
            # Delete old profile picture if exists
            if current_user.profile_picture:
                try:
                    old_url = current_user.profile_picture
                    if 'cloudinary.com' in old_url:
                        parts = old_url.split('/')
                        if len(parts) > 0:
                            old_public_id = parts[-1].split('.')[0]
                            CloudinaryService.delete_file(old_public_id, resource_type='image')
                except:
                    pass
            
            current_user.profile_picture = result['url']
            db.session.commit()
            flash('Profile picture uploaded successfully!', 'success')
        else:
            flash(f'Failed to upload profile picture: {result}', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error uploading profile picture: {str(e)}', 'danger')
    
    return redirect(request.referrer or url_for('admin.student_dashboard'))


@bp.route('/profile/delete', methods=['POST'])
@login_required
def delete_profile_picture():
    """Delete profile picture for current user"""
    try:
        from ..services.cloudinary_service import CloudinaryService
        
        if current_user.profile_picture:
            try:
                old_url = current_user.profile_picture
                if 'cloudinary.com' in old_url:
                    parts = old_url.split('/')
                    if len(parts) > 0:
                        public_id = parts[-1].split('.')[0]
                        CloudinaryService.delete_file(public_id, resource_type='image')
            except:
                pass
            
            current_user.profile_picture = None
            db.session.commit()
            flash('Profile picture deleted successfully!', 'success')
        else:
            flash('No profile picture to delete.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting profile picture: {str(e)}', 'danger')
    
    return redirect(request.referrer or url_for('admin.student_dashboard'))


@bp.route('/school-student/profile/upload', methods=['POST'])
def upload_school_student_profile_picture():
    """Upload profile picture for school student"""
    from flask import session
    from ..models.classes import SchoolStudent
    
    if 'school_student_id' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('schools.school_student_login'))
    
    student_id = session['school_student_id']
    student = SchoolStudent.query.get(student_id)
    
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('schools.school_student_login'))
    
    if 'profile_picture' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(request.referrer or url_for('schools.school_student_dashboard'))
    
    file = request.files['profile_picture']
    if file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(request.referrer or url_for('schools.school_student_dashboard'))
    
    try:
        from ..services.cloudinary_service import CloudinaryService
        from datetime import datetime
        
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        public_id = f"school_student_{student.id}_{timestamp}"
        
        success, result = CloudinaryService.upload_file(
            file=file,
            folder='profile_pictures',
            resource_type='image',
            public_id=public_id
        )
        
        if success:
            if student.student_image_url:
                try:
                    old_url = student.student_image_url
                    if 'cloudinary.com' in old_url:
                        parts = old_url.split('/')
                        if len(parts) > 0:
                            old_public_id = parts[-1].split('.')[0]
                            CloudinaryService.delete_file(old_public_id, resource_type='image')
                except:
                    pass
            
            student.student_image_url = result['url']
            db.session.commit()
            flash('Profile picture uploaded successfully!', 'success')
        else:
            flash(f'Failed to upload profile picture: {result}', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error uploading profile picture: {str(e)}', 'danger')
    
    return redirect(request.referrer or url_for('schools.school_student_dashboard'))


@bp.route('/school-student/profile/delete', methods=['POST'])
def delete_school_student_profile_picture():
    """Delete profile picture for school student"""
    from flask import session
    from ..models.classes import SchoolStudent
    
    if 'school_student_id' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('schools.school_student_login'))
    
    student_id = session['school_student_id']
    student = SchoolStudent.query.get(student_id)
    
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('schools.school_student_login'))
    
    try:
        from ..services.cloudinary_service import CloudinaryService
        
        if student.student_image_url:
            try:
                old_url = student.student_image_url
                if 'cloudinary.com' in old_url:
                    parts = old_url.split('/')
                    if len(parts) > 0:
                        public_id = parts[-1].split('.')[0]
                        CloudinaryService.delete_file(public_id, resource_type='image')
            except:
                pass
            
            student.student_image_url = None
            db.session.commit()
            flash('Profile picture deleted successfully!', 'success')
        else:
            flash('No profile picture to delete.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting profile picture: {str(e)}', 'danger')
    
    return redirect(request.referrer or url_for('schools.school_student_dashboard'))


# ========================================
# CLASS TIME MANAGEMENT ROUTES
# ========================================

@bp.route('/admin/class-time-settings', methods=['GET', 'POST'])
@login_required
def admin_class_time_settings():
    """Admin page for managing class time slots"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            # Add new time slot
            class_type = request.form.get('class_type', '').strip()
            class_id = request.form.get('class_id', type=int) or None
            day = request.form.get('day', '').strip()
            start_time_str = request.form.get('start_time', '').strip()
            end_time_str = request.form.get('end_time', '').strip()
            timezone = request.form.get('timezone', 'Asia/Kolkata').strip()  # Default to India timezone
            max_capacity = request.form.get('max_capacity', type=int) or None
            
            if not all([class_type, day, start_time_str, end_time_str, timezone]):
                flash('Please fill in all required fields.', 'danger')
                return redirect(url_for('admin.admin_class_time_settings'))
            
            # Determine if selectable based on class type
            is_selectable = class_type in ['individual', 'family']
            
            try:
                # Parse time strings
                from datetime import time as dt_time
                start_time = dt_time.fromisoformat(start_time_str)
                end_time = dt_time.fromisoformat(end_time_str)
                
                class_time = ClassTime(
                    class_type=class_type,
                    class_id=class_id,
                    day=day,
                    start_time=start_time,
                    end_time=end_time,
                    timezone=timezone,
                    is_selectable=is_selectable,
                    max_capacity=max_capacity,
                    created_by=current_user.id
                )
                db.session.add(class_time)
                db.session.commit()
                flash(f'Time slot added successfully: {day} {class_time.get_display_time()} ({class_time.get_timezone_name()})', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding time slot: {str(e)}', 'danger')
        
        elif action == 'delete':
            time_id = request.form.get('time_id', type=int)
            if time_id:
                class_time = ClassTime.query.get(time_id)
                if class_time:
                    try:
                        # Check if there are any student selections using this time
                        selections = StudentClassTimeSelection.query.filter_by(class_time_id=time_id).all()
                        selection_count = len(selections)
                        
                        # Delete all selections first (if any)
                        for selection in selections:
                            db.session.delete(selection)
                        
                        # Now delete the time slot
                        db.session.delete(class_time)
                        db.session.commit()
                        
                        if selection_count > 0:
                            flash(f'Time slot deleted successfully. {selection_count} student selection(s) were also removed.', 'success')
                        else:
                            flash('Time slot deleted successfully.', 'success')
                    except Exception as e:
                        db.session.rollback()
                        flash(f'Error deleting time slot: {str(e)}', 'danger')
                else:
                    flash('Time slot not found.', 'danger')
        
        elif action == 'toggle':
            time_id = request.form.get('time_id', type=int)
            if time_id:
                class_time = ClassTime.query.get(time_id)
                if class_time:
                    class_time.is_active = not class_time.is_active
                    db.session.commit()
                    status = 'activated' if class_time.is_active else 'deactivated'
                    flash(f'Time slot {status} successfully.', 'success')
        
        return redirect(url_for('admin.admin_class_time_settings'))
    
    # Get all class times grouped by class type
    all_times = ClassTime.query.order_by(ClassTime.class_type, ClassTime.day, ClassTime.start_time).all()
    
    # Group by class type
    times_by_type = {
        'individual': [],
        'family': [],
        'group': [],
        'school': []
    }
    
    for time_slot in all_times:
        if time_slot.class_type in times_by_type:
            times_by_type[time_slot.class_type].append(time_slot)
    
    # Get all classes for dropdowns
    individual_classes = IndividualClass.query.all()
    group_classes = GroupClass.query.all()
    
    return render_template('admin_class_time_settings.html',
        times_by_type=times_by_type,
        individual_classes=individual_classes,
        group_classes=group_classes
    )


@bp.route('/admin/class-time-selections')
@login_required
def admin_class_time_selections():
    """Admin view of student time selections"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    # Get all time selections
    selections = StudentClassTimeSelection.query.order_by(
        StudentClassTimeSelection.selected_at.desc()
    ).all()
    
    # Get class times for display with timezone info
    for selection in selections:
        if selection.class_time:
            # Original admin time
            selection.original_time = selection.class_time.get_full_display()
            selection.admin_timezone = selection.class_time.get_timezone_name()
            
            # Converted time (if student has timezone set)
            student_timezone = selection.user.timezone if selection.user and selection.user.timezone else None
            if student_timezone:
                selection.converted_time = selection.class_time.get_full_display(student_timezone)
                selection.student_timezone = selection.user.timezone
            else:
                selection.converted_time = None
                selection.student_timezone = None
        else:
            selection.original_time = 'N/A'
            selection.admin_timezone = 'N/A'
            selection.converted_time = None
            selection.student_timezone = None
        
        selection.student_name = f"{selection.user.first_name} {selection.user.last_name}" if selection.user else 'Unknown'
        selection.student_id = selection.user.student_id if selection.user else 'N/A'
        selection.student_country = selection.user.timezone if selection.user and selection.user.timezone else 'Not set'
    
    return render_template('admin_class_time_selections.html', selections=selections)


@bp.route('/admin/live-class', methods=['GET', 'POST'])
@login_required
def admin_live_class():
    """Admin page for hosting live classes - shows students for selected class and time"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    try:
        from datetime import datetime, date, time as dt_time
        import pytz
        
        # Get data for dropdowns based on class type
        # Individual: Get all students (users) with individual enrollments
        individual_students = []
        try:
            from ..models.users import User
            individual_enrollments = ClassEnrollment.query.filter_by(
                class_type='individual',
                status='completed'
            ).all()
            for enrollment in individual_enrollments:
                user = User.query.get(enrollment.user_id)
                if user:
                    # Get the class name for this enrollment
                    class_obj = IndividualClass.query.get(enrollment.class_id) or \
                               GroupClass.query.filter_by(id=enrollment.class_id, class_type='individual').first()
                    class_name = class_obj.name if class_obj else 'Unknown Class'
                    individual_students.append({
                        'id': user.id,  # Use user_id as the identifier
                        'name': f"{user.first_name} {user.last_name}",
                        'student_id': user.student_id or 'N/A',
                        'enrollment_id': enrollment.id,
                        'class_id': enrollment.class_id,
                        'class_name': class_name
                    })
        except Exception as e:
            import traceback
            traceback.print_exc()
            individual_students = []
        
        # Family: Get all families (enrollments with family_system_id)
        families = []
        try:
            family_enrollments = ClassEnrollment.query.filter_by(
                class_type='family',
                status='completed'
            ).filter(ClassEnrollment.family_system_id.isnot(None)).all()
            for enrollment in family_enrollments:
                user = User.query.get(enrollment.user_id)
                if user:
                    # Get the class name for this enrollment
                    class_obj = GroupClass.query.filter_by(id=enrollment.class_id, class_type='family').first()
                    class_name = class_obj.name if class_obj else 'Unknown Class'
                    families.append({
                        'id': enrollment.id,  # Use enrollment_id as the identifier
                        'name': f"Family {enrollment.family_system_id}",
                        'family_system_id': enrollment.family_system_id,
                        'user_name': f"{user.first_name} {user.last_name}",
                        'class_id': enrollment.class_id,
                        'class_name': class_name
                    })
        except Exception as e:
            import traceback
            traceback.print_exc()
            families = []
        
        # Group: Get all group classes (keep as is)
        try:
            group_classes = GroupClass.query.filter_by(class_type='group').all() or []
        except Exception:
            group_classes = []
        
        # School: Get all schools (not classes)
        schools = []
        try:
            from ..models.schools import School
            schools_list = School.query.filter_by(status='active').all() or []
            for school in schools_list:
                schools.append({
                    'id': school.id,
                    'name': school.school_name,
                    'school_system_id': school.school_system_id
                })
        except Exception as e:
            import traceback
            traceback.print_exc()
            schools = []
        
        # Get all active class times (with error handling)
        try:
            all_class_times = ClassTime.query.filter_by(is_active=True).order_by(
                ClassTime.class_type, ClassTime.day, ClassTime.start_time
            ).all() or []
        except Exception:
            all_class_times = []
        
        # Get selected filters from form or default to today
        selected_class_type = request.form.get('class_type', request.args.get('class_type', ''))
        selected_class_id = request.form.get('class_id', request.args.get('class_id', type=int))
        selected_date = request.form.get('date', request.args.get('date', date.today().isoformat()))
        # Ensure time_id is converted to integer
        time_id_raw = request.form.get('time_id', request.args.get('time_id'))
        selected_time_id = int(time_id_raw) if time_id_raw and str(time_id_raw).isdigit() else None
        
        eligible_students = []
        selected_class_time = None
        selected_class_obj = None
        
        if selected_class_type and selected_time_id:
            # Get the selected class time (ensure selected_time_id is integer)
            try:
                selected_time_id = int(selected_time_id)
            except (ValueError, TypeError):
                selected_time_id = None
            
            if selected_time_id:
                selected_class_time = ClassTime.query.get(selected_time_id)
            else:
                selected_class_time = None
            
            if selected_class_time:
                # Parse selected date
                try:
                    target_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
                    target_day = target_date.strftime('%A')  # Monday, Tuesday, etc.
                except:
                    target_date = date.today()
                    target_day = target_date.strftime('%A')
                
                # Verify day matches
                if selected_class_time.day == target_day:
                    # Get eligible students based on class type
                    if selected_class_type == 'individual':
                        # selected_class_id is user_id
                        if selected_class_id:
                            user = User.query.get(selected_class_id)
                            if user:
                                # Find the enrollment for this user
                                enrollment = ClassEnrollment.query.filter_by(
                                    user_id=user.id,
                                    class_type='individual',
                                    status='completed'
                                ).first()
                                
                                if enrollment:
                                    # Get the class object
                                    selected_class_obj = IndividualClass.query.get(enrollment.class_id) or \
                                                       GroupClass.query.filter_by(id=enrollment.class_id, class_type='individual').first()
                                    
                                    # Check if this student selected this time
                                    time_id_int = int(selected_time_id) if selected_time_id else None
                                    if time_id_int:
                                        selection = StudentClassTimeSelection.query.filter_by(
                                            enrollment_id=enrollment.id,
                                            class_time_id=time_id_int
                                        ).first()
                                    else:
                                        selection = None
                                    
                                    if selection:
                                        eligible_students.append({
                                            'id': user.id,
                                            'name': f"{user.first_name} {user.last_name}",
                                            'system_id': user.student_id or 'N/A',
                                            'class_type': 'Individual',
                                            'enrollment': enrollment,
                                            'user': user
                                        })
                        
                    elif selected_class_type == 'family':
                        # selected_class_id is enrollment_id
                        if selected_class_id:
                            enrollment = ClassEnrollment.query.get(selected_class_id)
                            if enrollment and enrollment.class_type == 'family':
                                # Get the class object
                                selected_class_obj = GroupClass.query.filter_by(id=enrollment.class_id, class_type='family').first()
                                
                                # Check if this family selected this time
                                time_id_int = int(selected_time_id) if selected_time_id else None
                                if time_id_int:
                                    selection = StudentClassTimeSelection.query.filter_by(
                                        enrollment_id=enrollment.id,
                                        class_time_id=time_id_int
                                    ).first()
                                else:
                                    selection = None
                                
                                if selection:
                                    user = User.query.get(enrollment.user_id)
                                    # Get family members
                                    family_members = FamilyMember.query.filter_by(
                                        enrollment_id=enrollment.id,
                                        class_id=enrollment.class_id
                                    ).all()
                                    
                                    if family_members:
                                        for member in family_members:
                                            eligible_students.append({
                                                'id': f"family_{member.id}",
                                                'name': member.member_name,
                                                'system_id': enrollment.family_system_id or 'N/A',
                                                'class_type': 'Family',
                                                'enrollment': enrollment,
                                                'member': member
                                            })
                                    elif user:  # If no family members, add the main user
                                        eligible_students.append({
                                            'id': user.id,
                                            'name': f"{user.first_name} {user.last_name}",
                                            'system_id': enrollment.family_system_id or 'N/A',
                                            'class_type': 'Family',
                                            'enrollment': enrollment,
                                            'user': user
                                        })
                        
                    elif selected_class_type == 'group':
                        # selected_class_id is class_id (unchanged)
                        if selected_class_id:
                            selected_class_obj = GroupClass.query.filter_by(id=selected_class_id, class_type='group').first()
                            
                            if selected_class_obj:
                                # Get all students in this group class (fixed time applies to all)
                                enrollments = ClassEnrollment.query.filter_by(
                                    class_id=selected_class_obj.id,
                                    class_type='group',
                                    status='completed'
                                ).all()
                                
                                for enrollment in enrollments:
                                    user = User.query.get(enrollment.user_id)
                                    if user:  # Check if user exists
                                        # Group students use group_system_id, NOT individual student_id
                                        eligible_students.append({
                                            'id': user.id,
                                            'name': f"{user.first_name} {user.last_name}",
                                            'system_id': enrollment.group_system_id or 'N/A',  # Use group_system_id only
                                            'class_type': 'Group',
                                            'enrollment': enrollment,
                                            'user': user
                                        })
                        
                    elif selected_class_type == 'school':
                        # selected_class_id is school_id
                        if selected_class_id:
                            from ..models.schools import School
                            school = School.query.get(selected_class_id)
                            if school:
                                # Get all enrollments for this school
                                # Find enrollments where the school's students are registered
                                from ..models.classes import SchoolStudent
                                school_students = SchoolStudent.query.filter_by(
                                    school_name=school.school_name
                                ).all()
                                
                                # Get unique class_ids from these school students
                                class_ids = set()
                                for ss in school_students:
                                    if ss.class_id:
                                        class_ids.add(ss.class_id)
                                
                                # For each class, get all school students
                                for class_id in class_ids:
                                    class_obj = GroupClass.query.filter_by(id=class_id, class_type='school').first()
                                    if class_obj:
                                        selected_class_obj = class_obj  # Use the first class found
                                        
                                        # Get enrollments for this class
                                        enrollments = ClassEnrollment.query.filter_by(
                                            class_id=class_id,
                                            class_type='school',
                                            status='completed'
                                        ).all()
                                        
                                        for enrollment in enrollments:
                                            # Get registered school students for this enrollment
                                            class_school_students = SchoolStudent.query.filter_by(
                                                enrollment_id=enrollment.id,
                                                class_id=class_id,
                                                school_name=school.school_name
                                            ).all()
                                            
                                            for school_student in class_school_students:
                                                eligible_students.append({
                                                    'id': f"school_{school_student.id}",
                                                    'name': school_student.student_name,
                                                    'system_id': school_student.student_system_id or 'N/A',
                                                    'class_type': 'School',
                                                    'enrollment': enrollment,
                                                    'school_student': school_student,
                                                    'school_name': school_student.school_name
                                                })
                                        break  # Only process first class
        
        # Group class times by class type for dropdown
        class_times_by_type = {
            'individual': [t for t in all_class_times if t and t.class_type == 'individual'],
            'family': [t for t in all_class_times if t and t.class_type == 'family'],
            'group': [t for t in all_class_times if t and t.class_type == 'group'],
            'school': [t for t in all_class_times if t and t.class_type == 'school']
        }
        
        # Ensure all lists exist (defensive)
        if 'individual' not in class_times_by_type:
            class_times_by_type['individual'] = []
        if 'family' not in class_times_by_type:
            class_times_by_type['family'] = []
        if 'group' not in class_times_by_type:
            class_times_by_type['group'] = []
        if 'school' not in class_times_by_type:
            class_times_by_type['school'] = []
        
        return render_template('admin_live_class.html',
                             individual_students=individual_students,
                             group_classes=group_classes,
                             families=families,
                             schools=schools,
                             class_times_by_type=class_times_by_type,
                             eligible_students=eligible_students,
                             selected_class_type=selected_class_type,
                             selected_class_id=selected_class_id,
                             selected_date=selected_date,
                             selected_time_id=selected_time_id,
                             selected_class_time=selected_class_time,
                             selected_class_obj=selected_class_obj)
    except Exception as e:
        from datetime import date
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        flash(f'Error loading live class page: {error_msg}', 'danger')
        return render_template('admin_live_class.html',
                             individual_students=[],
                             group_classes=[],
                             families=[],
                             schools=[],
                             class_times_by_type={'individual': [], 'family': [], 'group': [], 'school': []},
                             eligible_students=[],
                             selected_class_type='',
                             selected_class_id=None,
                             selected_date=date.today().isoformat(),
                             selected_time_id=None,
                             selected_class_time=None,
                             selected_class_obj=None)


@bp.route('/id-card/<int:id_card_id>', methods=['GET', 'POST'])
def view_id_card(id_card_id):
    """
    View ID card - NO LOGIN REQUIRED
    Students can see their ID card immediately after approval without logging in
    """
    from flask import session
    from ..models.classes import SchoolStudent
    id_card = IDCard.query.get_or_404(id_card_id)
    
    # NO LOGIN CHECK - Allow access to ID card without login
    # Students can view their ID card directly after approval
    has_access = True  # Always allow access - no login needed
    is_owner = True  # Treat as owner since they're viewing their own card
    
    # If user is logged in and is admin, mark as admin
    is_admin = current_user.is_authenticated and current_user.is_admin if current_user.is_authenticated else False
    
    # Mark ID card as viewed in session (for tracking) - NO LOGIN REQUIRED
    session['id_card_viewed'] = session.get('id_card_viewed', [])
    if id_card_id not in session['id_card_viewed']:
        session['id_card_viewed'].append(id_card_id)
        session.permanent = True
    
    # CRITICAL: Set session data for student access (NO LOGIN REQUIRED)
    # This allows students to access dashboard using Name + System ID
    if id_card.entity_type == 'individual':
        # Get user from entity_id
        user = User.query.get(id_card.entity_id)
        if user:
            session['student_user_id'] = user.id
            session['student_name'] = f"{user.first_name} {user.last_name}"
            session['student_system_id'] = user.student_id  # Individual students use student_id
    elif id_card.entity_type == 'group':
        # Get user from entity_id
        user = User.query.get(id_card.entity_id)
        if user:
            session['student_user_id'] = user.id
            session['student_name'] = f"{user.first_name} {user.last_name}"
            # Group students use group_system_id (stored in id_card.system_id), NOT individual student_id
            session['group_system_id'] = id_card.system_id or id_card.group_system_id
    elif id_card.entity_type == 'family':
        # Get enrollment and user
        enrollment = ClassEnrollment.query.get(id_card.entity_id)
        if enrollment:
            user = User.query.get(enrollment.user_id)
            if user:
                session['student_user_id'] = user.id
                session['student_name'] = f"{user.first_name} {user.last_name}"
                session['family_system_id'] = enrollment.family_system_id
    elif id_card.entity_type == 'school':
        # Get school and user
        school_obj = School.query.get(id_card.entity_id)
        if school_obj:
            user = User.query.get(school_obj.user_id)
            if user:
                session['student_user_id'] = user.id
                session['school_name'] = school_obj.school_name
                session['school_system_id'] = school_obj.school_system_id
    elif id_card.entity_type == 'school_student':
        # Get registered school student - handle both SchoolStudent and RegisteredSchoolStudent
        school_student = SchoolStudent.query.get(id_card.entity_id)
        registered_student = RegisteredSchoolStudent.query.get(id_card.entity_id)
        
        if school_student:
            # This is a SchoolStudent (registered in a specific class)
            session['school_student_id'] = school_student.id
            session['school_student_name'] = school_student.student_name
            session['school_student_system_id'] = school_student.student_system_id
            session['school_name'] = school_student.school_name
        elif registered_student:
            # This is a RegisteredSchoolStudent (general school registration)
            session['school_student_id'] = registered_student.id
            session['school_student_name'] = registered_student.student_name
            session['school_student_system_id'] = registered_student.student_system_id
            # Get school name from school_id
            school = School.query.get(registered_student.school_id)
            if school:
                session['school_name'] = school.school_name
    
    # Handle photo/logo upload
    if request.method == 'POST' and request.form.get('action') == 'upload_photo':
        photo_file = request.files.get('photo')
        if photo_file and photo_file.filename:
            try:
                from ..services.cloudinary_service import CloudinaryService
                success, result = CloudinaryService.upload_file(photo_file, folder='id_cards', resource_type='image')
                if success:
                    photo_url = result.get('url')
                    id_card.photo_url = photo_url
                
                # Update user profile picture if applicable
                if id_card.entity_type in ['individual', 'group']:
                    user = User.query.get(id_card.entity_id)
                    if user:
                        user.profile_picture = photo_url
                elif id_card.entity_type == 'school':
                    school = School.query.get(id_card.entity_id)
                    # TODO: Add school logo field to School model if needed
                
                db.session.commit()
                flash('Photo updated successfully!', 'success')
                return redirect(url_for('admin.view_id_card', id_card_id=id_card.id))
            except Exception as e:
                db.session.rollback()
                flash(f'Error uploading photo: {str(e)}', 'danger')
    
    # Determine redirect URL based on entity type
    redirect_url = None
    if id_card.entity_type == 'individual':
        redirect_url = url_for('admin.student_dashboard')
    elif id_card.entity_type == 'group':
        redirect_url = url_for('main.group_class_dashboard')
    elif id_card.entity_type == 'family':
        redirect_url = url_for('main.family_dashboard')
    elif id_card.entity_type == 'school':
        redirect_url = url_for('schools.school_dashboard')
    elif id_card.entity_type == 'school_student':
        redirect_url = url_for('schools.school_student_dashboard')
    
    return render_template('view_id_card.html', id_card=id_card, redirect_url=redirect_url)


@bp.route('/id-card/<int:id_card_id>/download')
@login_required
def download_id_card(id_card_id):
    """Redirect to view ID card page - Print functionality is now used instead of PDF download"""
    id_card = IDCard.query.get_or_404(id_card_id)
    
    # Check access (same as view_id_card)
    has_access = False
    if current_user.is_admin:
        has_access = True
    elif id_card.entity_type in ['individual', 'group'] and id_card.entity_id == current_user.id:
        has_access = True
    elif id_card.entity_type == 'family':
        enrollment = ClassEnrollment.query.get(id_card.entity_id)
        if enrollment and enrollment.user_id == current_user.id:
            has_access = True
    elif id_card.entity_type == 'school':
        school = School.query.get(id_card.entity_id)
        if school and school.user_id == current_user.id:
            has_access = True
    elif id_card.entity_type == 'school_student':
        # Check both SchoolStudent and RegisteredSchoolStudent
        from ..models.classes import SchoolStudent
        school_student = SchoolStudent.query.get(id_card.entity_id)
        registered_student = RegisteredSchoolStudent.query.get(id_card.entity_id)
        
        if school_student and school_student.registered_by == current_user.id:
            has_access = True
        elif registered_student and registered_student.user_id == current_user.id:
            has_access = True
    
    if not has_access:
        flash('Access denied.', 'danger')
        return redirect(url_for('main.index'))
    
    # Redirect to view page where user can print
    flash('Please use the "Print ID Card" button to print your ID card.', 'info')
    return redirect(url_for('admin.view_id_card', id_card_id=id_card.id))


@bp.route('/admin/contact-settings', methods=['GET', 'POST'])
@login_required
def admin_contact_settings():
    """Admin page for managing contact settings (WhatsApp and Email)"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    if request.method == 'POST':
        whatsapp_number = request.form.get('whatsapp_number', '').strip()
        contact_email = request.form.get('contact_email', '').strip()
        
        try:
            # Save settings using SiteSettings model
            if whatsapp_number:
                SiteSettings.set_setting('whatsapp_number', whatsapp_number, current_user.id)
            else:
                SiteSettings.set_setting('whatsapp_number', '', current_user.id)
            
            if contact_email:
                SiteSettings.set_setting('contact_email', contact_email, current_user.id)
            else:
                SiteSettings.set_setting('contact_email', '', current_user.id)
            
            flash('Contact settings saved successfully!', 'success')
            return redirect(url_for('admin.admin_contact_settings'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving contact settings: {str(e)}', 'danger')
    
    # Get current settings
    whatsapp_number = SiteSettings.get_setting('whatsapp_number', '')
    contact_email = SiteSettings.get_setting('contact_email', '')
    
    return render_template('admin_contact_settings.html', 
                         whatsapp_number=whatsapp_number, 
                         contact_email=contact_email)


@bp.route('/admin/payment-settings', methods=['GET', 'POST'])
@login_required
def admin_payment_settings():
    """Admin page for managing payment method details"""
    admin_check = require_admin()
    if admin_check:
        return admin_check
    
    if request.method == 'POST':
        # Wave settings
        wave_name = request.form.get('wave_name', '').strip()
        wave_number = request.form.get('wave_number', '').strip()
        
        # Bank settings
        bank_account_holder = request.form.get('bank_account_holder', '').strip()
        bank_name = request.form.get('bank_name', '').strip()
        bank_branch = request.form.get('bank_branch', '').strip()
        bank_account_number = request.form.get('bank_account_number', '').strip()
        bank_ifsc = request.form.get('bank_ifsc', '').strip()
        
        # Money transfer settings (for Western Union, MoneyGram, Ria)
        money_transfer_receiver = request.form.get('money_transfer_receiver', '').strip()
        money_transfer_country = request.form.get('money_transfer_country', '').strip()
        money_transfer_phone = request.form.get('money_transfer_phone', '').strip()
        
        try:
            # Save settings using SiteSettings model
            SiteSettings.set_setting('payment_wave_name', wave_name, current_user.id)
            SiteSettings.set_setting('payment_wave_number', wave_number, current_user.id)
            SiteSettings.set_setting('payment_bank_account_holder', bank_account_holder, current_user.id)
            SiteSettings.set_setting('payment_bank_name', bank_name, current_user.id)
            SiteSettings.set_setting('payment_bank_branch', bank_branch, current_user.id)
            SiteSettings.set_setting('payment_bank_account_number', bank_account_number, current_user.id)
            SiteSettings.set_setting('payment_bank_ifsc', bank_ifsc, current_user.id)
            SiteSettings.set_setting('payment_money_transfer_receiver', money_transfer_receiver, current_user.id)
            SiteSettings.set_setting('payment_money_transfer_country', money_transfer_country, current_user.id)
            SiteSettings.set_setting('payment_money_transfer_phone', money_transfer_phone, current_user.id)
            
            flash('Payment settings saved successfully!', 'success')
            return redirect(url_for('admin.admin_payment_settings'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving payment settings: {str(e)}', 'danger')
    
    # Get current settings with defaults
    wave_name = SiteSettings.get_setting('payment_wave_name', 'Foday M J')
    wave_number = SiteSettings.get_setting('payment_wave_number', '5427090')
    bank_account_holder = SiteSettings.get_setting('payment_bank_account_holder', 'ABDOUKADIR JABBI')
    bank_name = SiteSettings.get_setting('payment_bank_name', 'State Bank of India (SBI)')
    bank_branch = SiteSettings.get_setting('payment_bank_branch', 'Surajpur Greater Noida')
    bank_account_number = SiteSettings.get_setting('payment_bank_account_number', '60541424234')
    bank_ifsc = SiteSettings.get_setting('payment_bank_ifsc', 'SBIN0014022')
    money_transfer_receiver = SiteSettings.get_setting('payment_money_transfer_receiver', 'Abdoukadir Jabbi')
    money_transfer_country = SiteSettings.get_setting('payment_money_transfer_country', 'India')
    money_transfer_phone = SiteSettings.get_setting('payment_money_transfer_phone', '+91 93190 38312')
    
    return render_template('admin_payment_settings.html',
                         wave_name=wave_name,
                         wave_number=wave_number,
                         bank_account_holder=bank_account_holder,
                         bank_name=bank_name,
                         bank_branch=bank_branch,
                         bank_account_number=bank_account_number,
                         bank_ifsc=bank_ifsc,
                         money_transfer_receiver=money_transfer_receiver,
                         money_transfer_country=money_transfer_country,
                         money_transfer_phone=money_transfer_phone)
