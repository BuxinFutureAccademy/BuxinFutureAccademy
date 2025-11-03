from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import User, PasswordResetToken
from ..services.mailer import send_bulk_email

bp = Blueprint('auth', __name__)

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


def verify_reset_token(token: str):
    try:
        reset_token = PasswordResetToken.query.filter_by(token=token).first()
        if not reset_token or not reset_token.is_valid():
            return None
        return db.session.get(User, reset_token.user_id)
    except Exception as e:
        print(f"Error verifying reset token: {e}")
        return None


def send_password_reset_email(user: User, reset_token: str) -> bool:
    try:
        reset_url = url_for('auth.reset_password', token=reset_token, _external=True)
        subject = "Reset Your Account Password"
        message = f"Hello {user.first_name}, click to reset: {reset_url}"
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


@bp.route('/forgot-password', methods=['GET', 'POST'], endpoint='forgot_password')
def forgot_password():
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('main.health'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email:
            flash('Please enter your email address.', 'danger')
            return render_template('forgot_password.html')
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
                return redirect(url_for('auth.login'))
            flash('Failed to process password reset. Please try again later.', 'danger')
        else:
            flash('If an account with that email exists, password reset instructions have been sent.', 'success')
            record_password_reset_attempt(email)
            return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')


@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('main.health'))

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
            except Exception:
                pass
            flash('Your password has been successfully reset! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception:
            db.session.rollback()
            flash('An error occurred while resetting your password. Please try again.', 'danger')

    return render_template('reset_password.html', token=token, user=user)


@bp.route('/login', methods=['GET', 'POST'], endpoint='login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.health'))
    if request.method == 'POST':
        identifier = request.form.get('email', '').strip().lower() or request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter((User.email == identifier) | (User.username == identifier)).first() if identifier else None
        if user and user.check_password(password):
            login_user(user)
            next_url = request.args.get('next') or url_for('main.health')
            return redirect(next_url)
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('auth.login'))


 


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
    return {
        'total_tokens': total_tokens,
        'used_tokens': used_tokens,
        'expired_tokens': expired_tokens,
        'active_tokens': active_tokens,
    }
