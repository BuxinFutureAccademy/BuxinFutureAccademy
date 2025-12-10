import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, Response
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import User, RoboticsProjectSubmission
from ..services.mailer import send_bulk_email

bp = Blueprint('projects', __name__)


@bp.route('/robotics-projects')
def robotics_projects():
    return render_template('robotics_projects.html')


@bp.route('/robotics-projects', methods=['POST'])
def submit_robotics_project():
    try:
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        location = request.form.get('location', '').strip()
        education_level = request.form.get('education_level', '').strip()

        project_title = request.form.get('project_title', '').strip()
        project_description = request.form.get('project_description', '').strip()
        problem_solved = request.form.get('problem_solved', '').strip()
        components = request.form.get('components', '').strip()
        progress = request.form.get('progress', '').strip()
        project_goal = request.form.get('project_goal', '').strip()
        additional_comments = request.form.get('additional_comments', '').strip()

        help_needed_list = request.form.getlist('help_needed')
        help_needed = ','.join(help_needed_list) if help_needed_list else ''

        if not all([name, email, education_level, project_title, project_description]):
            flash('Please fill in all required fields!', 'danger')
            return redirect(url_for('projects.robotics_projects'))

        # Handle file uploads to Cloudinary if available
        uploaded_files = []
        project_files = request.files.getlist('project_files')

        for file in project_files:
            if not (file and file.filename):
                continue
            file.seek(0, 2)
            file_size = file.tell()
            file.seek(0)
            if file_size > 10 * 1024 * 1024:
                flash(f'File {file.filename} is too large. Maximum size is 10MB per file.', 'warning')
                continue
            allowed_extensions = {'jpg', 'jpeg', 'png', 'pdf', 'doc', 'docx', 'txt'}
            file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            if file_extension not in allowed_extensions:
                flash(f'File {file.filename} has an unsupported format. Allowed: {", ".join(allowed_extensions)}', 'warning')
                continue
            try:
                # Attempt Cloudinary upload if library is available
                try:
                    import cloudinary.uploader as uploader
                except Exception:
                    uploader = None
                if uploader:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    safe_filename = secure_filename(file.filename).replace('.', '_')
                    public_id = f"robotics_project_{timestamp}_{safe_filename}"
                    resource_type = 'image' if file_extension in ['jpg', 'jpeg', 'png'] else 'raw'
                    result = uploader.upload(
                        file,
                        resource_type=resource_type,
                        public_id=public_id,
                        folder='robotics_projects',
                        overwrite=True,
                    )
                    uploaded_files.append({
                        'filename': file.filename,
                        'url': result.get('secure_url'),
                        'public_id': result.get('public_id'),
                        'size': file_size,
                        'type': file_extension,
                    })
                else:
                    # Fallback: no upload, only record name/size
                    uploaded_files.append({
                        'filename': file.filename,
                        'url': None,
                        'public_id': None,
                        'size': file_size,
                        'type': file_extension,
                    })
            except Exception as e:
                print(f"Failed to upload {file.filename}: {e}")
                flash(f'Failed to upload {file.filename}. Please try again.', 'warning')

        submission = RoboticsProjectSubmission(
            name=name,
            email=email,
            phone=phone,
            location=location,
            education_level=education_level,
            project_title=project_title,
            project_description=project_description,
            problem_solved=problem_solved,
            components=components,
            progress=progress,
            project_goal=project_goal,
            help_needed=help_needed,
            additional_comments=additional_comments,
            uploaded_files=json.dumps(uploaded_files) if uploaded_files else None,
        )
        db.session.add(submission)
        db.session.commit()

        # Confirmation email to submitter (best-effort)
        try:
            subject = f"Your Robotics Project Submission Received - {project_title}"
            message = f"""
Dear {name},

Thank you for submitting your robotics project idea: "{project_title}"

We have received your submission and will review it.\n\nSubmission ID: #{submission.id}\nSubmitted on: {submission.submitted_at.strftime('%Y-%m-%d %H:%M:%S')}
"""
            class TempUser:
                def __init__(self, email, first_name):
                    self.email = email
                    self.first_name = first_name
            temp_user = TempUser(email, name.split()[0])
            send_bulk_email([temp_user], subject, message)
        except Exception as e:
            print(f"Failed to send confirmation email: {e}")

        # Notify admins (best-effort)
        try:
            admin_users = User.query.filter_by(is_admin=True).all()
            if admin_users:
                admin_subject = f"New Robotics Project Submission - {project_title}"
                admin_message = f"New robotics project submission received: {name} ({email})\nProject: {project_title}\n"
                send_bulk_email(admin_users, admin_subject, admin_message)
        except Exception as e:
            print(f"Failed to send admin notification: {e}")

        flash('Your robotics project submission has been received!', 'success')
        return redirect(url_for('projects.robotics_projects'))

    except Exception as e:
        db.session.rollback()
        print(f"Error submitting robotics project: {e}")
        flash('An error occurred while submitting your project. Please try again.', 'danger')
        return redirect(url_for('projects.robotics_projects'))


# Admin routes
@bp.route('/admin/robotics-submissions')
@login_required
def admin_robotics_submissions():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))

    status_filter = request.args.get('status', '')
    education_filter = request.args.get('education', '')
    search = request.args.get('search', '')
    sort_by = request.args.get('sort', 'newest')

    query = RoboticsProjectSubmission.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    if education_filter:
        query = query.filter_by(education_level=education_filter)
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(
                RoboticsProjectSubmission.name.like(like),
                RoboticsProjectSubmission.email.like(like),
                RoboticsProjectSubmission.project_title.like(like),
                RoboticsProjectSubmission.project_description.like(like),
            )
        )

    if sort_by == 'name':
        query = query.order_by(RoboticsProjectSubmission.name.asc())
    elif sort_by == 'title':
        query = query.order_by(RoboticsProjectSubmission.project_title.asc())
    elif sort_by == 'status':
        query = query.order_by(RoboticsProjectSubmission.status.asc())
    elif sort_by == 'oldest':
        query = query.order_by(RoboticsProjectSubmission.submitted_at.asc())
    else:
        query = query.order_by(RoboticsProjectSubmission.submitted_at.desc())

    submissions = query.all()

    total_submissions = RoboticsProjectSubmission.query.count()
    pending_submissions = RoboticsProjectSubmission.query.filter_by(status='pending').count()
    selected_submissions = RoboticsProjectSubmission.query.filter_by(status='selected').count()
    reviewed_submissions = RoboticsProjectSubmission.query.filter_by(status='reviewed').count()

    return render_template(
        'admin_robotics_submissions.html',
        submissions=submissions,
        total_submissions=total_submissions,
        pending_submissions=pending_submissions,
        selected_submissions=selected_submissions,
        reviewed_submissions=reviewed_submissions,
        status_filter=status_filter,
        education_filter=education_filter,
        search_term=search,
        sort_by=sort_by,
    )


@bp.route('/admin/robotics-submission/<int:submission_id>')
@login_required
def view_robotics_submission(submission_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    submission = RoboticsProjectSubmission.query.get_or_404(submission_id)
    return render_template('view_robotics_submission.html', submission=submission)


@bp.route('/admin/update-robotics-submission/<int:submission_id>', methods=['POST'])
@login_required
def update_robotics_submission(submission_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))

    submission = RoboticsProjectSubmission.query.get_or_404(submission_id)
    try:
        new_status = request.form.get('status')
        admin_notes = request.form.get('admin_notes', '').strip()
        if new_status in ['pending', 'reviewed', 'selected', 'declined']:
            old_status = submission.status
            submission.status = new_status
            submission.admin_notes = admin_notes
            submission.reviewed_by = current_user.id
            submission.reviewed_at = datetime.utcnow()
            db.session.commit()
            try:
                if new_status != old_status:
                    subject = f"Project Update: {submission.project_title}"
                    if new_status == 'selected':
                        message = f"Hello {submission.name}, your project '{submission.project_title}' has been SELECTED for mentorship!\n\n{('Note: ' + admin_notes) if admin_notes else ''}"
                    else:
                        message = f"Hello {submission.name}, your project status has been updated.\nStatus: {new_status}.\n\n{('Feedback: ' + admin_notes) if admin_notes else ''}"
                    class TempUser:
                        def __init__(self, email, first_name):
                            self.email = email
                            self.first_name = first_name
                    temp_user = TempUser(submission.email, submission.name.split()[0])
                    send_bulk_email([temp_user], subject, message)
            except Exception as e:
                print(f"Failed to send status update email: {e}")
            flash(f'Submission status updated to "{new_status}" successfully!', 'success')
        else:
            flash('Invalid status selected!', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating submission: {str(e)}', 'danger')
    return redirect(url_for('projects.view_robotics_submission', submission_id=submission_id))


@bp.route('/admin/robotics-submissions/export')
@login_required
def export_robotics_submissions():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    try:
        import csv
        from io import StringIO
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'ID', 'Name', 'Email', 'Phone', 'Location', 'Education Level',
            'Project Title', 'Project Description', 'Problem Solved', 'Components',
            'Progress', 'Project Goal', 'Help Needed', 'Additional Comments',
            'Status', 'Admin Notes', 'Submitted At', 'Reviewed At', 'Files Count',
        ])
        submissions = RoboticsProjectSubmission.query.order_by(RoboticsProjectSubmission.submitted_at.desc()).all()
        for submission in submissions:
            files_count = len(submission.get_uploaded_files_list()) if hasattr(submission, 'get_uploaded_files_list') else 0
            writer.writerow([
                submission.id,
                submission.name,
                submission.email,
                submission.phone or '',
                submission.location or '',
                submission.education_level,
                submission.project_title,
                submission.project_description,
                submission.problem_solved or '',
                submission.components or '',
                submission.progress or '',
                submission.project_goal or '',
                submission.help_needed or '',
                submission.additional_comments or '',
                submission.status,
                submission.admin_notes or '',
                submission.submitted_at.strftime('%Y-%m-%d %H:%M:%S'),
                submission.reviewed_at.strftime('%Y-%m-%d %H:%M:%S') if submission.reviewed_at else '',
                files_count,
            ])
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=robotics_submissions_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'},
        )
    except Exception as e:
        flash(f'Error exporting submissions: {str(e)}', 'danger')
        return redirect(url_for('projects.admin_robotics_submissions'))


@bp.route('/admin/robotics-submissions/stats')
@login_required
def robotics_submissions_stats():
    if not current_user.is_admin:
        return {'error': 'Access denied'}, 403
    try:
        total = RoboticsProjectSubmission.query.count()
        pending = RoboticsProjectSubmission.query.filter_by(status='pending').count()
        reviewed = RoboticsProjectSubmission.query.filter_by(status='reviewed').count()
        selected = RoboticsProjectSubmission.query.filter_by(status='selected').count()
        declined = RoboticsProjectSubmission.query.filter_by(status='declined').count()

        education_stats = db.session.query(
            RoboticsProjectSubmission.education_level,
            db.func.count(RoboticsProjectSubmission.id),
        ).group_by(RoboticsProjectSubmission.education_level).all()
        education_data = [{'level': level, 'count': count} for (level, count) in education_stats]

        help_stats = {}
        for submission in RoboticsProjectSubmission.query.all():
            help_list = submission.get_help_needed_list() if hasattr(submission, 'get_help_needed_list') else []
            for help_type in help_list:
                help_stats[help_type] = help_stats.get(help_type, 0) + 1
        help_data = [{'type': k, 'count': v} for k, v in help_stats.items()]

        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_count = RoboticsProjectSubmission.query.filter(
            RoboticsProjectSubmission.submitted_at >= thirty_days_ago
        ).count()

        return {
            'total': total,
            'pending': pending,
            'reviewed': reviewed,
            'selected': selected,
            'declined': declined,
            'education': education_data,
            'help_needed': help_data,
            'recent_30d': recent_count,
        }
    except Exception as e:
        return {'error': str(e)}, 500
