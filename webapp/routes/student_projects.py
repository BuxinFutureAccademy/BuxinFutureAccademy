from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ..extensions import db
from ..models import StudentProject, ProjectLike, ProjectComment, User

bp = Blueprint('student_projects', __name__)


@bp.route('/student-projects', endpoint='student_projects')
def student_projects():
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
        recent_comments = (
            ProjectComment.query.filter_by(project_id=project.id)
            .order_by(ProjectComment.created_at.desc())
            .limit(3)
            .all()
        )
        project.recent_comments = list(reversed(recent_comments))

    total_projects = StudentProject.query.filter_by(is_active=True).count()
    featured_projects = StudentProject.query.filter_by(is_active=True, featured=True).count()

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
    )


@bp.route('/student-projects/<int:project_id>', endpoint='view_project')
def view_project(project_id):
    project = StudentProject.query.get_or_404(project_id)
    if not project.is_active:
        flash('This project is not available.', 'warning')
        return redirect(url_for('student_projects.student_projects'))
    page = request.args.get('page', 1, type=int)
    comments = project.comments.order_by(ProjectComment.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
    user_reaction = None
    if current_user.is_authenticated:
        user_reaction = project.user_reaction(current_user.id)
    return render_template('view_project.html', project=project, comments=comments, user_reaction=user_reaction)


@bp.route('/my-projects', endpoint='my_projects')
@login_required
def my_projects():
    projects = (
        StudentProject.query.filter_by(student_id=current_user.id).order_by(StudentProject.created_at.desc()).all()
    )
    total_likes = sum(project.get_like_count() for project in projects)
    total_comments = sum(project.get_comment_count() for project in projects)
    return render_template('my_projects.html', projects=projects, total_likes=total_likes, total_comments=total_comments)


@bp.route('/create-project', methods=['GET', 'POST'], endpoint='create_project')
@login_required
def create_project():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        project_url = request.form.get('project_url', '').strip()
        github_url = request.form.get('github_url', '').strip()
        image_url = request.form.get('image_url', '').strip()
        tags = request.form.get('tags', '').strip()
        
        if not title or not description:
            flash('Title and description are required.', 'danger')
            return render_template('create_project.html')
        
        try:
            project = StudentProject(
                title=title,
                description=description,
                project_url=project_url or None,
                github_url=github_url or None,
                image_url=image_url or None,
                tags=tags or None,
                student_id=current_user.id,
                is_active=True,
                featured=False
            )
            db.session.add(project)
            db.session.commit()
            flash('Project created successfully!', 'success')
            return redirect(url_for('student_projects.my_projects'))
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to create project: {str(e)}', 'danger')
            return render_template('create_project.html')
    
    return render_template('create_project.html')


@bp.route('/admin/projects', endpoint='admin_projects')
@login_required
def admin_projects():
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
        query = query.join(User).order_by(User.first_name.asc(), User.last_name.asc())
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
