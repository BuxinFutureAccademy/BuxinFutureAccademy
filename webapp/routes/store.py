import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory
from flask_login import login_required, current_user

from ..extensions import db
from ..models import (
    Course,
    CourseVideo,
    CourseMaterial,
    Purchase,
    CartItem,
    IndividualClass,
    GroupClass,
)

bp = Blueprint('store', __name__)


@bp.route('/store', endpoint='store')
def store():
    category = request.args.get('category', '')
    level = request.args.get('level', '')
    search = request.args.get('search', '')

    try:
        query = Course.query.filter_by(is_active=True)
        if category:
            query = query.filter_by(category=category)
        if level:
            query = query.filter_by(level=level)
        if search:
            query = query.filter(Course.title.contains(search) | Course.description.contains(search))

        try:
            courses = query.order_by(Course.created_at.desc()).all()
        except Exception:
            # Fallback if created_at column is missing in DB
            courses = query.order_by(Course.id.desc()).all()

        try:
            categories = [c[0] for c in db.session.query(Course.category).distinct().all()]
        except Exception:
            categories = []
    except Exception as e:
        current_app.logger.error(f"/store query failed: {e}")
        flash('Store is temporarily unavailable. Please try again later.', 'danger')
        courses = []
        categories = []

    cart_count = 0
    if current_user.is_authenticated:
        try:
            cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
        except Exception:
            cart_count = 0

    return render_template(
        'store.html',
        courses=courses,
        categories=categories,
        cart_count=cart_count,
        selected_category=category,
        selected_level=level,
        search_term=search,
    )


@bp.route('/available-classes', endpoint='available_classes')
def available_classes():
    """Browse and enroll in available classes"""
    from ..models import ClassPricing

    pricing_type = request.args.get('type', 'individual')

    try:
        pricing_data = ClassPricing.get_all_pricing()
        pricing_info = pricing_data.get(pricing_type, pricing_data.get('individual', {}))
    except Exception:
        pricing_data = {}
        pricing_info = {'name': pricing_type.title(), 'price': 100}

    classes = []
    try:
        classes = GroupClass.query.all()
    except Exception:
        classes = []

    # Include legacy individual classes if they exist
    try:
        legacy_individual = IndividualClass.query.all()
        classes = classes + legacy_individual
    except Exception:
        pass
    
    return render_template(
        'available_classes.html',
        classes=classes,
        pricing_type=pricing_type,
        pricing_info=pricing_info,
        pricing_data=pricing_data
    )


@bp.route('/enroll/<int:class_id>', methods=['GET', 'POST'])
@bp.route('/enroll/<class_type>/<int:class_id>', methods=['GET', 'POST'])  # legacy URL with class_type
@login_required
def enroll_class(class_id, class_type=None):
    """Enroll in a class"""
    from ..models import ClassPricing
    
    # Get pricing type from URL parameter (individual, group, family, school)
    pricing_type = request.args.get('pricing', 'individual')
    
    # Get the class object (unified class model uses GroupClass; keep legacy individual support)
    class_obj = GroupClass.query.get(class_id) or IndividualClass.query.get_or_404(class_id)
    
    # Get pricing from database
    pricing_data = ClassPricing.get_all_pricing()
    selected_pricing = pricing_data.get(pricing_type, pricing_data.get('individual', {}))
    
    # Get price and display info
    amount = selected_pricing.get('price', 100)
    pricing_name = selected_pricing.get('name', pricing_type.title())
    pricing_color = selected_pricing.get('color', '#00d4ff')
    pricing_icon = selected_pricing.get('icon', 'fa-user')
    max_students = selected_pricing.get('max_students', 1)
    features = selected_pricing.get('features', [])
    fee_display = f"${int(amount)} USD"
    
    # Payment methods
    payment_methods = [
        {
            'id': 'wave',
            'name': 'Wave Money',
            'icon': 'fa-mobile-alt',
            'color': '#00a8ff',
            'details': 'Send payment via Wave and upload screenshot'
        },
        {
            'id': 'bank',
            'name': 'Bank Transfer',
            'icon': 'fa-university',
            'color': '#28a745',
            'details': 'Transfer to our bank account'
        },
        {
            'id': 'cash',
            'name': 'Cash Payment',
            'icon': 'fa-money-bill-wave',
            'color': '#ffc107',
            'details': 'Pay in cash at our office'
        }
    ]
    
    if request.method == 'POST':
        # Handle enrollment submission
        full_name = request.form.get('full_name', '')
        phone = request.form.get('phone', '')
        email = request.form.get('email', '')
        address = request.form.get('address', '')
        payment_method = request.form.get('payment_method', '')
        
        try:
            # Create enrollment record
            from ..models import ClassEnrollment
            enrollment = ClassEnrollment(
                user_id=current_user.id,
                class_type=pricing_type,  # store selected pricing plan
                class_id=class_id,
                amount=amount,
                customer_name=full_name,
                customer_email=email,
                customer_phone=phone,
                customer_address=address,
                payment_method=payment_method,
                status='pending'
            )
            db.session.add(enrollment)
            db.session.commit()
            flash(f'Enrollment submitted! We will verify your payment and grant access soon.', 'success')
            return redirect(url_for('main.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Enrollment failed: {str(e)}', 'danger')
    
    return render_template(
        'enroll_class.html',
        class_obj=class_obj,
        class_type=class_type,
        pricing_type=pricing_type,
        pricing_name=pricing_name,
        pricing_color=pricing_color,
        pricing_icon=pricing_icon,
        max_students=max_students,
        features=features,
        fee_display=fee_display,
        amount=amount,
        payment_methods=payment_methods
    )


@bp.route('/course/<int:course_id>', endpoint='course_detail')
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    is_purchased = False
    in_cart = False

    if current_user.is_authenticated:
        is_purchased = (
            Purchase.query.filter_by(user_id=current_user.id, course_id=course_id, status='completed').first()
            is not None
        )
        in_cart = (
            CartItem.query.filter_by(user_id=current_user.id, course_id=course_id).first()
            is not None
        )

    return render_template('course_detail.html', course=course, is_purchased=is_purchased, in_cart=in_cart)


@bp.route('/add_to_cart/<int:course_id>', methods=['POST'])
@login_required
def add_to_cart(course_id):
    course = Course.query.get_or_404(course_id)

    existing_purchase = Purchase.query.filter_by(
        user_id=current_user.id, course_id=course_id, status='completed'
    ).first()
    if existing_purchase:
        flash('You have already purchased this course!', 'info')
        return redirect(url_for('store.course_detail', course_id=course_id))

    existing_cart_item = CartItem.query.filter_by(user_id=current_user.id, course_id=course_id).first()
    if existing_cart_item:
        flash('Course is already in your cart!', 'info')
        return redirect(url_for('store.course_detail', course_id=course_id))

    db.session.add(CartItem(user_id=current_user.id, course_id=course_id))
    db.session.commit()
    flash('Course added to cart!', 'success')
    return redirect(url_for('store.course_detail', course_id=course_id))


@bp.route('/cart')
@login_required
def cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.course.price for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)


@bp.route('/remove_from_cart/<int:cart_item_id>', methods=['POST'])
@login_required
def remove_from_cart(cart_item_id):
    cart_item = CartItem.query.get_or_404(cart_item_id)
    if cart_item.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('store.cart'))
    db.session.delete(cart_item)
    db.session.commit()
    flash('Course removed from cart!', 'success')
    return redirect(url_for('store.cart'))


@bp.route('/checkout')
@login_required
def checkout():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash('Your cart is empty!', 'warning')
        return redirect(url_for('store.store'))
    total = sum(item.course.price for item in cart_items)
    return render_template('checkout.html', cart_items=cart_items, total=total)


@bp.route('/my_courses')
@login_required
def my_courses():
    purchases = (
        Purchase.query.filter_by(user_id=current_user.id, status='completed')
        .order_by(Purchase.purchased_at.desc())
        .all()
    )
    return render_template('my_courses.html', purchases=purchases)


@bp.route('/my_course_orders')
@login_required
def my_course_orders():
    orders = (
        Purchase.query.filter_by(user_id=current_user.id)
        .order_by(Purchase.purchased_at.desc())
        .all()
    )
    return render_template('my_course_orders.html', orders=orders)


@bp.route('/learn/course/<int:course_id>')
@login_required
def learn_course(course_id):
    course = Course.query.get_or_404(course_id)

    has_access = False
    access_reason = ''
    if getattr(current_user, 'is_admin', False):
        has_access = True
        access_reason = 'Admin access'
    else:
        purchase = Purchase.query.filter_by(
            user_id=current_user.id, course_id=course_id, status='completed'
        ).first()
        if purchase:
            has_access = True
            access_reason = f"Purchased on {purchase.purchased_at.strftime('%Y-%m-%d')}"
        else:
            pending = Purchase.query.filter_by(
                user_id=current_user.id, course_id=course_id, status='pending'
            ).first()
            if pending:
                flash('Your payment is being verified. You will have access once confirmed.', 'info')
            flash('You need to purchase this course to access the learning content.', 'warning')
            return redirect(url_for('store.course_detail', course_id=course_id))

    videos = CourseVideo.query.filter_by(course_id=course_id).order_by(CourseVideo.order_index).all()
    materials = CourseMaterial.query.filter_by(course_id=course_id).all()

    enhanced_videos = []
    debug_info = {
        'total_videos': len(videos),
        'cloudinary_videos': 0,
        'local_videos': 0,
        'missing_videos': 0,
        'videos_with_missing_files': 0,
    }

    video_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'videos')

    for video in videos:
        playback_url = None
        source_type = 'unknown'
        available = False
        file_exists = False

        if getattr(video, 'video_url', None):
            playback_url = video.video_url
            source_type = 'cloudinary'
            available = True
            debug_info['cloudinary_videos'] += 1
        elif getattr(video, 'video_filename', None):
            video_path = os.path.join(video_folder, video.video_filename)
            file_exists = os.path.exists(video_path)
            if file_exists:
                playback_url = url_for('store.course_video', filename=video.video_filename)
                source_type = 'local'
                available = True
                debug_info['local_videos'] += 1
            else:
                source_type = 'local'
                available = False
                debug_info['local_videos'] += 1
                debug_info['videos_with_missing_files'] += 1
        else:
            source_type = 'none'
            available = False
            debug_info['missing_videos'] += 1

        enhanced_videos.append(
            {
                'id': video.id,
                'title': video.title,
                'description': video.description or '',
                'duration': video.duration or '',
                'order_index': video.order_index,
                'video_filename': video.video_filename or '',
                'video_url': video.video_url or '',
                'playback_url': playback_url,
                'source_type': source_type,
                'available': available,
                'file_exists': file_exists,
                'is_preview': getattr(video, 'is_preview', False),
                'course_id': video.course_id,
            }
        )

    enhanced_materials = []
    for material in materials:
        enhanced_materials.append(
            {
                'id': material.id,
                'title': material.title,
                'filename': material.filename,
                'file_type': material.file_type,
                'file_size_mb': material.get_file_size_mb(),
                'course_id': material.course_id,
            }
        )

    context = {
        'course': course,
        'videos': enhanced_videos,
        'materials': materials,
        'enhanced_materials': enhanced_materials,
        'has_access': has_access,
        'access_reason': access_reason,
        'debug_info': debug_info if getattr(current_user, 'is_admin', False) else None,
        'debug_route_exists': False,
    }

    return render_template('learn_course.html', **context)


@bp.route('/course_video/<filename>')
@login_required
def course_video(filename):
    video_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'videos')
    return send_from_directory(video_dir, filename)


@bp.route('/course_video_bypass/<filename>')
@login_required
def course_video_bypass(filename):
    video_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'videos')
    return send_from_directory(video_dir, filename)


@bp.route('/course_material/<filename>')
@login_required
def course_material(filename):
    material_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'materials')
    return send_from_directory(material_dir, filename)


@bp.route('/admin/fix-course-images')
@login_required
def fix_course_images():
    if not getattr(current_user, 'is_admin', False):
        return 'Admin only', 403
    courses = Course.query.all()
    fixed = 0
    for course in courses:
        if not course.image_url or not course.image_url.strip():
            course.image_url = 'https://via.placeholder.com/400x200/007bff/ffffff?text=' + course.category.replace(' ', '+')
            fixed += 1
    db.session.commit()
    return f"Fixed {fixed} course images! <a href='/store'>Check Store</a>"


@bp.route('/admin/toggle-course-status/<int:course_id>', methods=['POST'])
@login_required
def toggle_course_status(course_id):
    if not getattr(current_user, 'is_admin', False):
        return {'success': False, 'error': 'Access denied. Admin privileges required.'}, 403
    try:
        course = Course.query.get_or_404(course_id)
        data = request.get_json()
        new_status = data.get('is_active', False)
        if not isinstance(new_status, bool):
            return {'success': False, 'error': 'Invalid status value. Must be true or false.'}, 400
        old_status = course.is_active
        course.is_active = new_status
        db.session.commit()
        action = 'activated' if new_status else 'deactivated'
        return {
            'success': True,
            'message': f'Course "{course.title}" {action} successfully!',
            'course_id': course_id,
            'new_status': new_status,
            'old_status': old_status,
        }, 200
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': f'Failed to update course status: {str(e)}'}, 500


@bp.route('/admin/bulk-toggle-courses', methods=['POST'])
@login_required
def bulk_toggle_courses():
    if not getattr(current_user, 'is_admin', False):
        return {'success': False, 'error': 'Access denied. Admin privileges required.'}, 403
    try:
        data = request.get_json()
        course_ids = data.get('course_ids', [])
        new_status = data.get('is_active', False)
        if not course_ids:
            return {'success': False, 'error': 'No course IDs provided.'}, 400
        if not isinstance(new_status, bool):
            return {'success': False, 'error': 'Invalid status value. Must be true or false.'}, 400

        updated_courses = []
        failed_courses = []
        for cid in course_ids:
            try:
                course = Course.query.get(cid)
                if course:
                    course.is_active = new_status
                    updated_courses.append({'id': course.id, 'title': course.title, 'new_status': new_status})
                else:
                    failed_courses.append({'id': cid, 'error': 'Course not found'})
            except Exception as e:
                failed_courses.append({'id': cid, 'error': str(e)})

        if updated_courses:
            db.session.commit()
        action = 'activated' if new_status else 'deactivated'
        return {
            'success': True,
            'message': f'{len(updated_courses)} course(s) {action} successfully!',
            'updated_count': len(updated_courses),
            'failed_count': len(failed_courses),
            'updated_courses': updated_courses,
            'failed_courses': failed_courses or None,
        }, 200
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': f'Bulk operation failed: {str(e)}'}, 500


@bp.route('/admin/course-status-stats')
@login_required
def course_status_stats():
    if not getattr(current_user, 'is_admin', False):
        return {'error': 'Access denied'}, 403
    try:
        total_courses = Course.query.count()
        active_courses = Course.query.filter_by(is_active=True).count()
        inactive_courses = Course.query.filter_by(is_active=False).count()
        category_stats = db.session.query(
            Course.category,
            db.func.count(Course.id).label('total'),
            db.func.sum(db.case([(Course.is_active == True, 1)], else_=0)).label('active'),
            db.func.sum(db.case([(Course.is_active == False, 1)], else_=0)).label('inactive'),
        ).group_by(Course.category).all()
        categories = [
            {
                'category': cat,
                'total': total,
                'active': active,
                'inactive': inactive,
            }
            for (cat, total, active, inactive) in category_stats
        ]
        return {
            'total_courses': total_courses,
            'active_courses': active_courses,
            'inactive_courses': inactive_courses,
            'categories': categories,
        }
    except Exception as e:
        return {'error': str(e)}, 500


@bp.route('/admin/courses')
@login_required
def admin_courses():
    if not getattr(current_user, 'is_admin', False):
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.health'))

    category = request.args.get('category', '')
    level = request.args.get('level', '')
    search = request.args.get('search', '')

    query = Course.query
    if category:
        query = query.filter_by(category=category)
    if level:
        query = query.filter_by(level=level)
    if search:
        query = query.filter(Course.title.contains(search) | Course.description.contains(search))

    courses = query.order_by(Course.created_at.desc()).all()
    categories = [c[0] for c in db.session.query(Course.category).distinct().all()]

    return render_template(
        'admin_courses.html',
        courses=courses,
        categories=categories,
        selected_category=category,
        selected_level=level,
        search_term=search,
    )




@bp.route('/admin/course_orders')
@login_required
def admin_course_orders():
    if not getattr(current_user, 'is_admin', False):
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.health'))
    orders = Purchase.query.order_by(Purchase.purchased_at.desc()).all()
    total_revenue = (
        db.session.query(db.func.sum(Purchase.amount)).filter_by(status='completed').scalar() or 0
    )
    pending_orders = Purchase.query.filter_by(status='pending').count()
    return render_template(
        'admin_course_orders.html', orders=orders, total_revenue=total_revenue, pending_orders=pending_orders
    )




@bp.route('/admin/view_course_order/<int:order_id>')
@login_required
def view_course_order(order_id):
    if not getattr(current_user, 'is_admin', False):
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.health'))
    order = Purchase.query.get_or_404(order_id)
    return render_template('view_course_order.html', order=order)


