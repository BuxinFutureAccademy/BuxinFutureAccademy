from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, current_app
from flask_login import login_required, current_user
from ..extensions import db
from ..models import StudentProject, ProjectLike, ProjectComment, User, ClassEnrollment

bp = Blueprint('student_projects', __name__)


def get_student_user():
    """Helper function to get student user from session or current_user"""
    user = None
    user_id = None
    
    if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
        user = current_user
        user_id = current_user.id
    else:
        user_id = session.get('student_user_id') or session.get('user_id')
        if user_id:
            user = User.query.get(user_id)
    
    return user, user_id


def get_or_create_guest_user(name):
    """Create or get a guest user for anonymous likes/comments"""
    if not name or not name.strip():
        name = 'Guest'
    
    name = name.strip()
    
    # Check if a guest user with this name already exists (within last 24 hours)
    from datetime import timedelta
    recent_guest = User.query.filter(
        User.username.like(f'guest_{name.lower().replace(" ", "_")}%'),
        User.email.like('guest@temp%'),
        User.created_at >= datetime.utcnow() - timedelta(hours=24)
    ).first()
    
    if recent_guest:
        return recent_guest
    
    # Create new guest user
    import secrets
    timestamp = int(datetime.utcnow().timestamp())
    random_suffix = secrets.token_hex(4)
    username_base = f"guest_{name.lower().replace(' ', '_')}_{timestamp}"
    username = username_base[:80]  # Ensure it fits in username field
    
    # Ensure unique username
    counter = 1
    while User.query.filter_by(username=username).first():
        username = f"{username_base[:75]}_{counter}"
        counter += 1
    
    # Ensure unique email
    email = f"guest_{timestamp}_{random_suffix}@temp.buxin.com"
    counter = 1
    while User.query.filter_by(email=email).first():
        email = f"guest_{timestamp}_{random_suffix}_{counter}@temp.buxin.com"
        counter += 1
    
    guest_user = User(
        username=username,
        email=email,
        first_name=name.split()[0] if name.split() else name,
        last_name=' '.join(name.split()[1:]) if len(name.split()) > 1 else 'Guest',
        is_student=True,
        is_admin=False
    )
    # Set a random password (won't be used)
    guest_user.set_password(secrets.token_urlsafe(32))
    db.session.add(guest_user)
    db.session.flush()
    
    return guest_user


def check_student_enrollment(user_id):
    """Check if student has a completed enrollment in any class type (individual, group, family, school)"""
    if not user_id:
        return False
    
    # Check for completed enrollment in any class type
    enrollment = ClassEnrollment.query.filter_by(
        user_id=user_id,
        status='completed'
    ).first()
    
    if enrollment:
        return True
    
    # Also check for school students (RegisteredSchoolStudent)
    from ..models.schools import RegisteredSchoolStudent
    school_student = RegisteredSchoolStudent.query.filter_by(user_id=user_id).first()
    if school_student:
        # Check if the school enrollment is completed
        school_enrollment = ClassEnrollment.query.filter_by(
            id=school_student.enrollment_id,
            status='completed'
        ).first()
        if school_enrollment:
            return True
    
    return False


@bp.route('/student-projects', endpoint='student_projects')
def student_projects():
    """View all student projects - public page, no enrollment required"""
    try:
        # Get user for like/comment functionality (supports both login and System ID)
        user, user_id = get_student_user()
        
        search = request.args.get('search', '').strip()
        sort_by = request.args.get('sort', 'newest')
        featured_only = request.args.get('featured') == 'true'
        page = request.args.get('page', 1, type=int)
        per_page = 10

        query = StudentProject.query.filter_by(is_active=True)
        if search:
            like = f"%{search}%"
            query = query.filter(db.or_(StudentProject.title.like(like), StudentProject.description.like(like)))
        if featured_only:
            query = query.filter_by(featured=True)

        if sort_by == 'popular':
            like_counts = db.session.query(
                ProjectLike.project_id,
                db.func.count(ProjectLike.id).label('like_count'),
            ).filter_by(is_like=True).group_by(ProjectLike.project_id).subquery()
            query = query.outerjoin(like_counts, StudentProject.id == like_counts.c.project_id).order_by(
                db.desc(db.func.coalesce(like_counts.c.like_count, 0))
            )
        elif sort_by == 'title':
            query = query.order_by(StudentProject.title.asc())
        else:
            query = query.order_by(StudentProject.created_at.desc())

        projects_pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        projects = projects_pagination.items

        for project in projects:
            try:
                recent_comments = (
                    ProjectComment.query.filter_by(project_id=project.id)
                    .order_by(ProjectComment.created_at.desc())
                    .limit(3)
                    .all()
                )
                project.recent_comments = list(reversed(recent_comments))
            except Exception as e:
                current_app.logger.error(f"Error loading comments for project {project.id}: {e}")
                project.recent_comments = []

        try:
            total_projects = StudentProject.query.filter_by(is_active=True).count()
            featured_projects = StudentProject.query.filter_by(is_active=True, featured=True).count()
        except Exception as e:
            current_app.logger.error(f"Error counting projects: {e}")
            total_projects = len(projects)
            featured_projects = 0

        return render_template(
            'student_projects.html',
            projects=projects,
            projects_pagination=projects_pagination,
            total_projects=total_projects,
            featured_projects=featured_projects,
            search_term=search,
            sort_by=sort_by,
            featured_only=featured_only,
            current_page=page,
            user=user,  # Pass user for template authentication checks
        )
    except Exception as e:
        current_app.logger.error(f"Error in student_projects route: {e}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        flash('An error occurred while loading projects. Please try again later.', 'danger')
        return redirect(url_for('main.index'))


@bp.route('/student-projects/<int:project_id>', endpoint='view_project')
def view_project(project_id):
    project = StudentProject.query.get_or_404(project_id)
    if not project.is_active:
        flash('This project is not available.', 'warning')
        return redirect(url_for('student_projects.student_projects'))
    page = request.args.get('page', 1, type=int)
    comments = project.comments.order_by(ProjectComment.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
    
    # Get user for reaction (supports both login and System ID authentication)
    user, user_id = get_student_user()
    user_reaction = None
    if user_id:
        user_reaction = project.user_reaction(user_id)
    
    return render_template('view_project.html', project=project, comments=comments, user_reaction=user_reaction, user=user)


@bp.route('/my-projects', endpoint='my_projects')
def my_projects():
    """View student's own projects - requires completed enrollment"""
    try:
        user, user_id = get_student_user()
        
        if not user:
            flash('Please enter your Name and System ID to access your projects.', 'info')
            return redirect(url_for('main.index'))
        
        # Check if student has completed enrollment
        if not check_student_enrollment(user_id):
            flash('You need to be registered in a class to view your projects. Please register for a class first.', 'warning')
            return redirect(url_for('store.available_classes'))
        
        try:
            projects = (
                StudentProject.query.filter_by(student_id=user_id).order_by(StudentProject.created_at.desc()).all()
            )
            total_likes = sum(project.get_like_count() for project in projects)
            total_comments = sum(project.get_comment_count() for project in projects)
        except Exception as e:
            current_app.logger.error(f"Error loading projects for user {user_id}: {e}")
            projects = []
            total_likes = 0
            total_comments = 0
        
        return render_template('my_projects.html', projects=projects, total_likes=total_likes, total_comments=total_comments, user=user)
    except Exception as e:
        current_app.logger.error(f"Error in my_projects route: {e}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        flash('An error occurred while loading your projects. Please try again later.', 'danger')
        return redirect(url_for('main.index'))


@bp.route('/create-project', methods=['GET', 'POST'], endpoint='create_project')
def create_project():
    """Create a new project - requires completed enrollment in any class type"""
    user, user_id = get_student_user()
    
    if not user:
        flash('Please enter your Name and System ID to create a project.', 'info')
        return redirect(url_for('main.index'))
    
    # CRITICAL: Check if student has completed enrollment (individual, group, family, or school)
    if not check_student_enrollment(user_id):
        flash('You need to be registered in a class to create projects. Please register for a class first.', 'warning')
        return redirect(url_for('store.available_classes'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        project_link = request.form.get('project_link', '').strip() or request.form.get('project_url', '').strip()
        youtube_url = request.form.get('youtube_url', '').strip() or request.form.get('github_url', '').strip()
        image_url = request.form.get('image_url', '').strip()
        
        if not title or not description:
            flash('Title and description are required.', 'danger')
            return render_template('create_project.html', user=user)
        
        try:
            project = StudentProject(
                title=title,
                description=description,
                project_link=project_link or None,
                youtube_url=youtube_url or None,
                image_url=image_url or None,
                student_id=user_id,
                is_active=True,
                featured=False
            )
            db.session.add(project)
            db.session.commit()
            flash('Project created successfully!', 'success')
            return redirect(url_for('student_projects.my_projects'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating project: {e}")
            flash(f'Failed to create project: {str(e)}', 'danger')
            return render_template('create_project.html', user=user)
    
    return render_template('create_project.html', user=user)


@bp.route('/admin/projects', endpoint='admin_projects')
@login_required
def admin_projects():
    try:
        if not getattr(current_user, 'is_admin', False):
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('main.health'))
        search = request.args.get('search', '').strip()
        status = request.args.get('status', '')
        featured = request.args.get('featured', '')
        sort_by = request.args.get('sort', 'newest')

        query = StudentProject.query
        if search:
            like = f"%{search}%"
            query = query.filter(db.or_(StudentProject.title.like(like), StudentProject.description.like(like)))
        if status == 'active':
            query = query.filter_by(is_active=True)
        elif status == 'inactive':
            query = query.filter_by(is_active=False)
        if featured == 'true':
            query = query.filter_by(featured=True)
        elif featured == 'false':
            query = query.filter_by(featured=False)

        if sort_by == 'title':
            query = query.order_by(StudentProject.title.asc())
        elif sort_by == 'student':
            # Use outerjoin to handle cases where student might be deleted
            # Join User table explicitly through the foreign key relationship
            query = query.outerjoin(User, StudentProject.student_id == User.id).order_by(
                User.first_name.asc(), 
                User.last_name.asc()
            )
        elif sort_by == 'popular':
            like_counts = db.session.query(
                ProjectLike.project_id,
                db.func.count(ProjectLike.id).label('like_count'),
            ).filter_by(is_like=True).group_by(ProjectLike.project_id).subquery()
            query = query.outerjoin(like_counts, StudentProject.id == like_counts.c.project_id).order_by(
                db.desc(db.func.coalesce(like_counts.c.like_count, 0))
            )
        else:
            query = query.order_by(StudentProject.created_at.desc())

        projects = query.all()
        total_projects = StudentProject.query.count()
        active_projects = StudentProject.query.filter_by(is_active=True).count()
        featured_projects = StudentProject.query.filter_by(featured=True).count()

        return render_template(
            'admin_projects.html',
            projects=projects,
            total_projects=total_projects,
            active_projects=active_projects,
            featured_projects=featured_projects,
            search_term=search,
            status_filter=status,
            featured_filter=featured,
            sort_by=sort_by,
        )
    except Exception as e:
        current_app.logger.error(f"Error in admin_projects route: {e}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        flash('An error occurred while loading projects. Please try again later.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))


@bp.route('/project/<int:project_id>/like', methods=['POST'])
def toggle_project_like(project_id):
    """Toggle like/dislike for a project - NO AUTHENTICATION REQUIRED - Anyone can like"""
    project = StudentProject.query.get_or_404(project_id)
    
    # Try to get user (supports both login and System ID authentication)
    user, user_id = get_student_user()
    
    # If no user, allow anonymous - use session ID or IP as identifier
    if not user_id:
        # For anonymous users, use session ID to track likes
        session_id = session.get('anonymous_session_id')
        if not session_id:
            import secrets
            session_id = f"anon_{secrets.token_hex(16)}"
            session['anonymous_session_id'] = session_id
        
        # For anonymous users, we'll use a special guest user
        # Create a temporary guest user for this session
        guest_name = session.get('anonymous_name', 'Guest')
        user = get_or_create_guest_user(guest_name)
        if not user:
            # If we can't create guest user, use a default
            user = get_or_create_guest_user('Guest')
        user_id = user.id if user else None
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Unable to process like. Please try again.'}), 500
    
    try:
        data = request.get_json() or {}
        is_like = data.get('is_like', True)  # True for like, False for dislike
        
        # Check if user already has a reaction
        existing_reaction = ProjectLike.query.filter_by(
            project_id=project_id,
            user_id=user_id
        ).first()
        
        if existing_reaction:
            if existing_reaction.is_like == is_like:
                # Same reaction - remove it
                db.session.delete(existing_reaction)
                action = 'removed'
            else:
                # Different reaction - update it
                existing_reaction.is_like = is_like
                action = 'liked' if is_like else 'disliked'
        else:
            # New reaction - create it
            new_reaction = ProjectLike(
                project_id=project_id,
                user_id=user_id,
                is_like=is_like
            )
            db.session.add(new_reaction)
            action = 'liked' if is_like else 'disliked'
        
        db.session.commit()
        
        # Return updated counts
        like_count = project.get_like_count()
        dislike_count = project.get_dislike_count()
        user_reaction = project.user_reaction(user_id)
        
        return jsonify({
            'success': True,
            'action': action,
            'like_count': like_count,
            'dislike_count': dislike_count,
            'user_reaction': user_reaction
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling project like: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/project/<int:project_id>/comment', methods=['POST'])
def add_project_comment(project_id):
    """Add a comment to a project - NO AUTHENTICATION REQUIRED - Anyone can comment"""
    project = StudentProject.query.get_or_404(project_id)
    
    try:
        data = request.get_json() or {}
        comment_text = data.get('comment', '').strip()
        commenter_name = data.get('name', '').strip()  # Optional name for anonymous users
        
        if not comment_text:
            return jsonify({'success': False, 'error': 'Comment cannot be empty.'}), 400
        
        if len(comment_text) > 500:
            return jsonify({'success': False, 'error': 'Comment is too long. Maximum 500 characters.'}), 400
        
        # Try to get user (supports both login and System ID authentication)
        user, user_id = get_student_user()
        
        # If no user, create/get guest user for anonymous commenter
        if not user_id:
            if commenter_name:
                user = get_or_create_guest_user(commenter_name)
                session['anonymous_name'] = commenter_name
            else:
                # Use default guest name
                user = get_or_create_guest_user('Guest')
            
            if not user:
                return jsonify({'success': False, 'error': 'Please provide a name to comment.'}), 400
            
            user_id = user.id
            db.session.flush()  # Ensure user is saved
        
        # Create new comment
        comment = ProjectComment(
            project_id=project_id,
            user_id=user_id,
            comment=comment_text
        )
        db.session.add(comment)
        db.session.commit()
        
        # Return the new comment data
        user_name = f"{user.first_name} {user.last_name}".strip() or user.username
        return jsonify({
            'success': True,
            'comment': {
                'id': comment.id,
                'comment': comment.comment,
                'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'user': {
                    'id': user.id,
                    'name': user_name
                }
            },
            'comment_count': project.get_comment_count()
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding project comment: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/delete-project/<int:project_id>', methods=['POST'], endpoint='delete_project')
@login_required
def delete_project(project_id):
    """Delete a project - Admin only or project owner"""
    try:
        project = StudentProject.query.get_or_404(project_id)
        
        # Check permissions - admin or project owner
        if not getattr(current_user, 'is_admin', False) and project.student_id != current_user.id:
            flash('You can only delete your own projects.', 'danger')
            if getattr(current_user, 'is_admin', False):
                return redirect(url_for('student_projects.admin_projects'))
            else:
                return redirect(url_for('student_projects.my_projects'))
        
        project_title = project.title
        
        # Delete the project (cascade will handle likes and comments)
        db.session.delete(project)
        db.session.commit()
        
        flash(f'Project "{project_title}" deleted successfully.', 'success')
        
        if getattr(current_user, 'is_admin', False):
            return redirect(url_for('student_projects.admin_projects'))
        else:
            return redirect(url_for('student_projects.my_projects'))
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting project: {e}")
        flash('An error occurred while deleting the project. Please try again.', 'danger')
        if getattr(current_user, 'is_admin', False):
            return redirect(url_for('student_projects.admin_projects'))
        else:
            return redirect(url_for('student_projects.view_project', project_id=project_id))


@bp.route('/admin/project/<int:project_id>/toggle-status', methods=['POST'], endpoint='toggle_project_status')
@login_required
def toggle_project_status(project_id):
    """Toggle project active status - Admin only"""
    if not getattr(current_user, 'is_admin', False):
        return jsonify({'success': False, 'error': 'Admin privileges required.'}), 403
    
    try:
        project = StudentProject.query.get_or_404(project_id)
        data = request.get_json() or {}
        new_status = data.get('is_active')
        
        if new_status is None:
            # Toggle current status
            project.is_active = not project.is_active
        else:
            project.is_active = bool(new_status)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'is_active': project.is_active,
            'message': f'Project {"activated" if project.is_active else "deactivated"} successfully.'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling project status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/admin/project/<int:project_id>/toggle-featured', methods=['POST'], endpoint='toggle_project_featured')
@login_required
def toggle_project_featured(project_id):
    """Toggle project featured status - Admin only"""
    if not getattr(current_user, 'is_admin', False):
        return jsonify({'success': False, 'error': 'Admin privileges required.'}), 403
    
    try:
        project = StudentProject.query.get_or_404(project_id)
        data = request.get_json() or {}
        new_featured = data.get('featured')
        
        if new_featured is None:
            # Toggle current status
            project.featured = not project.featured
        else:
            project.featured = bool(new_featured)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'featured': project.featured,
            'message': f'Project {"featured" if project.featured else "unfeatured"} successfully.'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling project featured status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
