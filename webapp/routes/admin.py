from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user, logout_user

from ..extensions import db
from ..models import (
    User,
    Purchase,
    ClassEnrollment,
    StudentProject,
    RoboticsProjectSubmission,
)

bp = Blueprint('admin', __name__)


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


@bp.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_user(user_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.health'))
    user = User.query.get_or_404(user_id)
    from flask import request, render_template
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
