from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required

from ..extensions import db
from ..models import User, PasswordResetToken
from ..services.mailer import send_bulk_email

bp = Blueprint('auth', __name__)


# In-memory rate limiting storage
password_reset_attempts = {}


def is_rate_limited(email: str) -> bool:
    now = datetime.utcnow()
    if email in password_reset_attempts:
        attempts = [t for t in password_reset_attempts[email] if (now - t).total_seconds() < 3600]
        password_reset_attempts[email] = attempts
        if len(attempts) >= 3:
            return True
    return False


def record_password_reset_attempt(email: str):
    now = datetime.utcnow()
    password_reset_attempts.setdefault(email, []).append(now)


# Token helpers

def generate_reset_token(user: User) -> str | None:
    try:
        PasswordResetToken.query.filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.expires_at < datetime.utcnow(),
        ).delete()
        reset_token = PasswordResetToken(user_id=user.id)
        db.session.add(reset_token)
        db.session.commit()
        return reset_token.token
    except Exception as e:
        db.session.rollback()
        print(f"Error generating reset token: {e}")
        return None


def verify_reset_token(token: str) -> User | None:
    try:
        reset_token = PasswordResetToken.query.filter_by(token=token).first()
        if not reset_token or not reset_token.is_valid():
            return None
        # Access relationship to return user
        return db.session.get(User, reset_token.user_id)
    except Exception as e:
        print(f"Error verifying reset token: {e}")
        return None


def send_password_reset_email(user: User, reset_token: str) -> bool:
    try:
        reset_url = url_for('auth.reset_password', token=reset_token, _external=True)
        subject = "Reset Your Account Password"
        message = f"""
Hello {user.first_name},

We received a request to reset your password.

Click the link below to reset your password:
{reset_url}

This link will expire in 1 hour.
If you didn't request this, ignore this email.
"""
        class TempUser:
            def __init__(self, email, first_name):
                self.email = email
                self.first_name = first_name
        temp_user = TempUser(user.email, user.first_name)
        sent_count = send_bulk_email([temp_user], subject, message)
        return sent_count > 0
    except Exception as e:
        print(f"Failed to send password reset email: {e}")
        return False


# Routes

@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('student_dashboard' if current_user.is_student else 'admin_dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email:
            flash('Please enter your email address.', 'danger')
            return render_template('forgot_password.html')
        # Basic email format check
        import re
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            flash('Please enter a valid email address.', 'danger')
            return render_template('forgot_password.html')

        if is_rate_limited(email):
            flash('Too many attempts. Please try again later.', 'warning')
            return render_template('forgot_password.html')

        user = User.query.filter_by(email=email).first()
        if user:
            recent_token = PasswordResetToken.query.filter(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.created_at > datetime.utcnow() - timedelta(minutes=5),
                PasswordResetToken.used == False,
            ).first()
            if recent_token:
                flash('A password reset email was already sent recently. Please check your email.', 'warning')
                return render_template('forgot_password.html')

            reset_token = generate_reset_token(user)
            if reset_token and send_password_reset_email(user, reset_token):
                flash('Password reset instructions have been sent to your email address.', 'success')
                record_password_reset_attempt(email)
                return redirect(url_for('auth.login')) if False else redirect(url_for('login'))
            flash('Failed to process password reset. Please try again later.', 'danger')
        else:
            flash('If an account with that email exists, password reset instructions have been sent.', 'success')
            record_password_reset_attempt(email)
            return redirect(url_for('login'))

    return render_template('forgot_password.html')


@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('student_dashboard' if current_user.is_student else 'admin_dashboard'))

    user = verify_reset_token(token)
    if not user:
        flash('Invalid or expired password reset link. Please request a new password reset.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        if not password:
            flash('Password is required.', 'danger')
            return render_template('reset_password.html', token=token, user=user)
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('reset_password.html', token=token, user=user)
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html', token=token, user=user)

        try:
            user.set_password(password)
            reset_token = PasswordResetToken.query.filter_by(token=token).first()
            if reset_token:
                reset_token.used = True
            PasswordResetToken.query.filter(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.id != (reset_token.id if reset_token else 0),
            ).delete()
            db.session.commit()
            try:
                subject = "Your password has been reset"
                message = f"Hello {user.first_name}, your password was reset successfully."
                class TempUser:
                    def __init__(self, email, first_name):
                        self.email = email
                        self.first_name = first_name
                temp_user = TempUser(user.email, user.first_name)
                send_bulk_email([temp_user], subject, message)
            except Exception as e:
                print(f"Failed to send confirmation email: {e}")
            flash('Your password has been successfully reset! You can now log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            print(f"Error resetting password: {e}")
            flash('An error occurred while resetting your password. Please try again.', 'danger')

    return render_template('reset_password.html', token=token, user=user)


@bp.route('/admin/password-reset-tokens')
@login_required
def admin_password_reset_tokens():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    tokens = PasswordResetToken.query.filter(
        PasswordResetToken.created_at >= seven_days_ago
    ).order_by(PasswordResetToken.created_at.desc()).all()
    total_tokens = len(tokens)
    used_tokens = sum(1 for t in tokens if t.used)
    expired_tokens = sum(1 for t in tokens if t.is_expired() and not t.used)
    active_tokens = sum(1 for t in tokens if t.is_valid())
    return render_template('admin_password_reset_tokens.html',
                           tokens=tokens,
                           total_tokens=total_tokens,
                           used_tokens=used_tokens,
                           expired_tokens=expired_tokens,
                           active_tokens=active_tokens)


@bp.route('/admin/create-password-reset-table')
@login_required
def create_password_reset_table():
    if not current_user.is_admin:
        return "Access denied: Admin privileges required", 403
    try:
        db.create_all()
        return "Password reset table ensured.", 200
    except Exception as e:
        return f"Error creating table: {e}", 500


@bp.route('/admin/password-reset-token/<int:token_id>')
@login_required
def get_password_reset_token_details(token_id):
    if not current_user.is_admin:
        return {'error': 'Access denied'}, 403
    try:
        token = PasswordResetToken.query.get_or_404(token_id)
        user = db.session.get(User, token.user_id)
        time_remaining = (token.expires_at - datetime.utcnow()).total_seconds() / 60
        return {
            'token_id': token.id,
            'user': {
                'id': user.id,
                'email': user.email,
            },
            'used': token.used,
            'expires_at': token.expires_at.isoformat(),
            'time_remaining_min': max(0, int(time_remaining)),
        }
    except Exception as e:
        return {'error': str(e)}, 500


@bp.route('/admin/revoke-reset-token/<int:token_id>', methods=['POST'])
@login_required
def revoke_password_reset_token(token_id):
    if not current_user.is_admin:
        return {'success': False, 'error': 'Access denied'}, 403
    try:
        token = PasswordResetToken.query.get_or_404(token_id)
        if token.used:
            return {'success': False, 'error': 'Token has already been used'}, 400
        token.used = True
        db.session.commit()
        return {'success': True}
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}, 500


@bp.route('/admin/cleanup-expired-tokens', methods=['POST'])
@login_required
def cleanup_expired_password_reset_tokens():
    if not current_user.is_admin:
        return {'success': False, 'error': 'Access denied'}, 403
    try:
        deleted_count = PasswordResetToken.query.filter(
            PasswordResetToken.expires_at < datetime.utcnow()
        ).delete()
        db.session.commit()
        return {'success': True, 'deleted_count': deleted_count}
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}, 500


@bp.route('/admin/password-reset-stats')
@login_required
def get_password_reset_stats():
    if not current_user.is_admin:
        return {'error': 'Access denied'}, 403
    try:
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        tokens = PasswordResetToken.query.filter(
            PasswordResetToken.created_at >= seven_days_ago
        ).all()
        total_tokens = len(tokens)
        used_tokens = sum(1 for t in tokens if t.used)
        expired_tokens = sum(1 for t in tokens if t.is_expired() and not t.used)
        active_tokens = sum(1 for t in tokens if t.is_valid())
        return {
            'total_tokens': total_tokens,
            'used_tokens': used_tokens,
            'expired_tokens': expired_tokens,
            'active_tokens': active_tokens,
        }
    except Exception as e:
        return {'error': str(e)}, 500


@bp.route('/admin/auto-cleanup-expired-tokens')
@login_required
def auto_cleanup_expired_tokens():
    if not current_user.is_admin:
        return {'success': False, 'error': 'Access denied'}, 403
    try:
        cleanup_time = datetime.utcnow() - timedelta(hours=24)
        deleted_count = PasswordResetToken.query.filter(
            PasswordResetToken.expires_at < cleanup_time
        ).delete()
        db.session.commit()
        return {'success': True, 'deleted_count': deleted_count}
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}, 500
