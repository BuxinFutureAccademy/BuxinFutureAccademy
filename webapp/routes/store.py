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
    """Browse and enroll in available classes - Filtered by class type"""
    from ..models import ClassPricing, ClassEnrollment, User
    from flask import session
    import traceback
    
    try:
        # Check if student is registered - if yes, redirect to dashboard
        user = None
        user_id = None
        
        try:
            if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
                user = current_user
                user_id = current_user.id
            else:
                user_id = session.get('student_user_id') or session.get('user_id')
                if user_id:
                    try:
                        user = User.query.get(user_id)
                    except Exception as e:
                        current_app.logger.error(f"Error querying user: {e}")
                        user = None
        except Exception as e:
            current_app.logger.error(f"Error checking user authentication: {e}")
            # Continue without user - allow page to load
        
        # If student is registered, redirect to dashboard
        if user:
            try:
                enrollment = ClassEnrollment.query.filter_by(
                    user_id=user_id,
                    status='completed'
                ).first()
                if enrollment:
                    # Student is registered - redirect to dashboard
                    if enrollment.class_type == 'individual':
                        return redirect(url_for('admin.student_dashboard'))
                    elif enrollment.class_type == 'group':
                        return redirect(url_for('main.group_class_dashboard'))
                    elif enrollment.class_type == 'family':
                        return redirect(url_for('main.family_dashboard'))
                    elif enrollment.class_type == 'school':
                        return redirect(url_for('schools.school_dashboard'))
                    return redirect(url_for('admin.student_dashboard'))
            except Exception as e:
                current_app.logger.error(f"Error checking enrollment: {e}")
                # Continue - don't block page load
        
        pricing_type = request.args.get('type')
        
        # Don't override type parameter if explicitly provided in URL
        # Only use user's class_type if no type parameter is provided
        if not pricing_type:
            try:
                if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated and hasattr(current_user, 'class_type') and current_user.class_type:
                    pricing_type = current_user.class_type
            except Exception as e:
                current_app.logger.error(f"Error checking user class_type: {e}")

        # Default to individual if not specified
        if not pricing_type:
            pricing_type = 'individual'

        try:
            pricing_data = ClassPricing.get_all_pricing()
            pricing_info = pricing_data.get(pricing_type, pricing_data.get('individual', {}))
        except Exception as e:
            current_app.logger.error(f"Error getting pricing data: {e}")
            current_app.logger.error(traceback.format_exc())
            try:
                db.session.rollback()
            except:
                pass
            pricing_data = {}
            pricing_info = {'name': pricing_type.title(), 'price': 100}

        classes = []
        enrolled_class_ids = set()
        
        # Get enrolled class IDs for this user
        if user_id:
            try:
                enrollments = ClassEnrollment.query.filter_by(
                    user_id=user_id,
                    status='completed'
                ).all()
                enrolled_class_ids = {e.class_id for e in enrollments}
            except Exception as e:
                current_app.logger.error(f"Error getting enrollments: {e}")
                enrolled_class_ids = set()
        
        # Filter classes by type - each type has its own list
        if pricing_type == 'individual':
            try:
                # Show legacy individual classes AND new unified classes with type 'individual'
                legacy_classes = IndividualClass.query.all()
                new_classes = GroupClass.query.filter_by(class_type='individual').all()
                classes = legacy_classes + new_classes
            except Exception as e:
                current_app.logger.error(f"Error querying individual classes: {e}")
                current_app.logger.error(traceback.format_exc())
                try:
                    db.session.rollback()
                except:
                    pass
                classes = []
        elif pricing_type == 'group':
            try:
                classes = GroupClass.query.filter_by(class_type='group').all()
            except Exception as e:
                current_app.logger.error(f"Error querying group classes: {e}")
                try:
                    db.session.rollback()
                except:
                    pass
                classes = []
        elif pricing_type == 'family':
            try:
                classes = GroupClass.query.filter_by(class_type='family').all()
            except Exception as e:
                current_app.logger.error(f"Error querying family classes: {e}")
                try:
                    db.session.rollback()
                except:
                    pass
                classes = []
        elif pricing_type == 'school':
            try:
                classes = GroupClass.query.filter_by(class_type='school').all()
            except Exception as e:
                current_app.logger.error(f"Error querying school classes: {e}")
                try:
                    db.session.rollback()
                except:
                    pass
                classes = []
        
        return render_template(
            'available_classes.html',
            classes=classes,
            pricing_type=pricing_type,
            pricing_info=pricing_info,
            pricing_data=pricing_data,
            enrolled_class_ids=enrolled_class_ids,
            user=user
        )
    except Exception as e:
        current_app.logger.error(f"Critical error in available_classes route: {e}")
        current_app.logger.error(traceback.format_exc())
        # Return a basic error page or redirect
        flash('An error occurred while loading classes. Please try again later.', 'danger')
        return redirect(url_for('main.index'))


@bp.route('/register-class/<class_type>/<int:class_id>', methods=['GET', 'POST'])
def register_class(class_type, class_id):
    """Register for a class - No login required"""
    from ..models import ClassPricing, ClassEnrollment, User
    import secrets
    import string
    
    # Get the class object
    if class_type == 'individual':
        class_obj = GroupClass.query.filter_by(id=class_id, class_type='individual').first() or IndividualClass.query.get_or_404(class_id)
    elif class_type in ['group', 'family', 'school']:
        class_obj = GroupClass.query.filter_by(id=class_id, class_type=class_type).first_or_404()
    else:
        flash('Invalid class type.', 'danger')
        return redirect(url_for('store.available_classes', type=class_type))
    
    # Get pricing from database
    pricing_data = ClassPricing.get_all_pricing()
    selected_pricing = pricing_data.get(class_type, pricing_data.get('individual', {}))
    
    # Get price and display info
    amount = selected_pricing.get('price', 100)
    pricing_name = selected_pricing.get('name', class_type.title())
    pricing_color = selected_pricing.get('color', '#00d4ff')
    pricing_icon = selected_pricing.get('icon', 'fa-user')
    max_students = selected_pricing.get('max_students', 1)
    features = selected_pricing.get('features', [])
    fee_display = f"${int(amount)} USD"
    
    # Get payment methods with details from settings
    def get_payment_methods():
        """Get payment methods with details from SiteSettings"""
        from ..models.site_settings import SiteSettings
        import json
        
        # Get payment details from settings
        wave_name = SiteSettings.get_setting('payment_wave_name', 'Foday M J')
        wave_number = SiteSettings.get_setting('payment_wave_number', '5427090')
        
        bank_account_holder = SiteSettings.get_setting('payment_bank_account_holder', 'ABDOUKADIR JABBI')
        bank_name = SiteSettings.get_setting('payment_bank_name', 'State Bank of India (SBI)')
        bank_branch = SiteSettings.get_setting('payment_bank_branch', 'Surajpur Greater Noida')
        bank_account_number = SiteSettings.get_setting('payment_bank_account_number', '60541424234')
        bank_ifsc = SiteSettings.get_setting('payment_bank_ifsc', 'SBIN0014022')
        
        return [
            {
                'id': 'wave',
                'name': 'Wave',
                'icon': 'fa-mobile-alt',
                'color': '#00a8ff',
                'details': f'{wave_name} - {wave_number}',
                'full_details': {
                    'name': wave_name,
                    'number': wave_number
                }
            },
            {
                'id': 'bank',
                'name': 'Bank Transfer',
                'icon': 'fa-university',
                'color': '#28a745',
                'details': f'{bank_name} - {bank_account_number}',
                'full_details': {
                    'account_holder': bank_account_holder,
                    'bank_name': bank_name,
                    'branch': bank_branch,
                    'account_number': bank_account_number,
                    'ifsc': bank_ifsc
                }
            },
            {
                'id': 'cash',
                'name': 'Cash',
                'icon': 'fa-money-bill-wave',
                'color': '#ffc107',
                'details': 'Pay in cash at our office',
                'full_details': {}
            }
        ]
    
    payment_methods = get_payment_methods()
    
    if request.method == 'POST':
        # Handle registration submission - different fields for different class types
        if class_type == 'school':
            # School registration fields
            school_name = request.form.get('school_name', '').strip()
            school_email = request.form.get('school_email', '').strip()
            school_phone = request.form.get('school_phone', '').strip()
            school_address = request.form.get('school_address', '').strip()
            admin_name = request.form.get('admin_name', '').strip()
            admin_email = request.form.get('admin_email', '').strip()
            admin_phone = request.form.get('admin_phone', '').strip()
            
            # Use school info for user creation, admin info for contact
            full_name = school_name
            email = school_email
            phone = school_phone
            address = school_address
            # Store admin info in address field
            admin_contact = f"Admin: {admin_name} | Email: {admin_email} | Phone: {admin_phone}"
            address = f"{school_address}\n\n{admin_contact}"
        else:
            # Individual, Group, Family registration fields
            full_name = request.form.get('full_name', '').strip()
            phone = request.form.get('phone', '').strip()
            email = request.form.get('email', '').strip()
            address = request.form.get('address', '').strip()
        
        payment_method = request.form.get('payment_method', '')
        payment_proof = request.files.get('payment_proof')
        
        # Validate required fields
        if class_type == 'school':
            if not school_name or not school_email or not school_phone or not school_address or not admin_name or not admin_email or not admin_phone:
                flash('Please fill in all required fields.', 'danger')
        else:
            if not full_name or not email or not phone:
                flash('Please fill in all required fields.', 'danger')
            return render_template('register_class.html',
                class_obj=class_obj,
                class_type=class_type,
                pricing_type=class_type,
                pricing_name=pricing_name,
                pricing_color=pricing_color,
                pricing_icon=pricing_icon,
                max_students=max_students,
                features=features,
                fee_display=fee_display,
                amount=amount,
                payment_methods=payment_methods
            )
        
        try:
            # Create or get user account (temporary account for enrollment)
            # Generate a temporary username from email
            username_base = email.split('@')[0] if email else f"user_{secrets.token_hex(4)}"
            username = username_base
            counter = 1
            while User.query.filter_by(username=username).first():
                username = f"{username_base}_{counter}"
                counter += 1
            
            # Check if user already exists by email
            user = User.query.filter_by(email=email).first()
            if not user:
                # Create new user account (no password - ID-based access only)
                user = User(
                    username=username,
                    email=email,
                    first_name=full_name.split()[0] if full_name else '',
                    last_name=' '.join(full_name.split()[1:]) if len(full_name.split()) > 1 else '',
                    whatsapp_number=phone,
                    is_student=True,
                    is_admin=False,
                    class_type=class_type
                )
                # Set a random password (won't be used for login)
                user.set_password(secrets.token_urlsafe(16))
                db.session.add(user)
                db.session.flush()  # Get user.id
            else:
                # Update existing user info
                user.first_name = full_name.split()[0] if full_name else user.first_name
                user.last_name = ' '.join(full_name.split()[1:]) if len(full_name.split()) > 1 else user.last_name
                user.whatsapp_number = phone or user.whatsapp_number
                if not user.class_type:
                    user.class_type = class_type
            
            # Handle payment proof upload (REQUIRED - uploads to Cloudinary)
            if not payment_proof or not payment_proof.filename:
                flash('Payment receipt upload is required. Please upload your payment proof.', 'danger')
                return render_template('register_class.html',
                    class_obj=class_obj,
                    class_type=class_type,
                    pricing_type=class_type,
                    pricing_name=pricing_name,
                    pricing_color=pricing_color,
                    pricing_icon=pricing_icon,
                    max_students=max_students,
                    features=features,
                    fee_display=fee_display,
                    amount=amount,
                    payment_methods=payment_methods
                )
            
            # Upload payment proof to Cloudinary (REQUIRED)
            payment_proof_url = None
            from ..services.cloudinary_service import CloudinaryService
            try:
                success, result = CloudinaryService.upload_file(
                    file=payment_proof, 
                    folder='payment_proofs',
                    resource_type='auto'
                )
                if success and isinstance(result, dict) and result.get('url'):
                    payment_proof_url = result['url']
                else:
                    error_msg = result if isinstance(result, str) else "Cloudinary upload returned no URL"
                    raise Exception(error_msg)
            except Exception as e:
                current_app.logger.error(f"Payment proof upload failed: {e}")
                flash('Failed to upload payment receipt. Please try again.', 'danger')
                return render_template('register_class.html',
                    class_obj=class_obj,
                    class_type=class_type,
                    pricing_type=class_type,
                    pricing_name=pricing_name,
                    pricing_color=pricing_color,
                    pricing_icon=pricing_icon,
                    max_students=max_students,
                    features=features,
                    fee_display=fee_display,
                    amount=amount,
                    payment_methods=payment_methods
                )
            
            # Generate System ID based on class type
            family_system_id = None
            group_system_id = None
            
            if class_type == 'family':
                from ..models.classes import generate_family_system_id
                try:
                    family_system_id = generate_family_system_id()
                except Exception as e:
                    # Handle case where family_system_id column doesn't exist yet
                    if 'family_system_id' in str(e).lower() or 'column' in str(e).lower():
                        flash('Database migration required. Please contact administrator.', 'warning')
                        return render_template('register_class.html',
                            class_obj=class_obj,
                            class_type=class_type,
                            pricing_type=class_type,
                            pricing_name=pricing_name,
                            pricing_color=pricing_color,
                            pricing_icon=pricing_icon,
                            max_students=max_students,
                            features=features,
                            fee_display=fee_display,
                            amount=amount,
                            payment_methods=payment_methods
                        )
                    raise
            elif class_type == 'group':
                from ..models.classes import generate_group_system_id
                try:
                    group_system_id = generate_group_system_id()
                except Exception as e:
                    # Handle case where group_system_id column doesn't exist yet
                    if 'group_system_id' in str(e).lower() or 'column' in str(e).lower():
                        flash('Database migration required. Please contact administrator.', 'warning')
                        return render_template('register_class.html',
                            class_obj=class_obj,
                            class_type=class_type,
                            pricing_type=class_type,
                            pricing_name=pricing_name,
                            pricing_color=pricing_color,
                            pricing_icon=pricing_icon,
                            max_students=max_students,
                            features=features,
                            fee_display=fee_display,
                            amount=amount,
                            payment_methods=payment_methods
                        )
                    raise
            
            # Create enrollment record
            enrollment = ClassEnrollment(
                user_id=user.id,
                class_type=class_type,
                class_id=class_id,
                amount=amount,
                customer_name=full_name,
                customer_email=email,
                customer_phone=phone,
                customer_address=address,
                payment_method=payment_method,
                payment_proof=payment_proof_url,
                status='pending',  # Pending until admin approval
                family_system_id=family_system_id,
                group_system_id=group_system_id
            )
            db.session.add(enrollment)
            db.session.commit()
            
            # Redirect to waiting for approval page (existing page)
            return redirect(url_for('store.enrollment_pending_approval', enrollment_id=enrollment.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Enrollment failed: {e}")
            flash(f'Registration failed: {str(e)}', 'danger')
    
    return render_template('register_class.html',
        class_obj=class_obj,
        class_type=class_type,
        pricing_type=class_type,
        pricing_name=pricing_name,
        pricing_color=pricing_color,
        pricing_icon=pricing_icon,
        max_students=max_students,
        features=features,
        fee_display=fee_display,
        amount=amount,
        payment_methods=payment_methods
    )


@bp.route('/enrollment-pending/<int:enrollment_id>', endpoint='enrollment_pending_approval')
def enrollment_pending_approval(enrollment_id):
    """Waiting for approval page - NO LOGIN REQUIRED - Student sees ID card immediately after approval"""
    from ..models import ClassEnrollment, IDCard, User
    
    enrollment = ClassEnrollment.query.get_or_404(enrollment_id)
    
    # CRITICAL: Check enrollment status FIRST
    if enrollment.status == 'completed':
        # Enrollment is approved - GET ID CARD DIRECTLY (NO LOGIN NEEDED)
        user = User.query.get(enrollment.user_id)
        if user:
            # Get ID card directly from enrollment/user
            entity_type = enrollment.class_type
            entity_id = user.id if entity_type in ['individual', 'group'] else enrollment.id
            
            id_card = IDCard.query.filter_by(
                entity_type=entity_type,
                entity_id=entity_id,
                is_active=True
            ).first()
            
            # If not found, try without is_active filter
            if not id_card:
                id_card = IDCard.query.filter_by(
                    entity_type=entity_type,
                    entity_id=entity_id
                ).first()
            
            if id_card:
                # SHOW ID CARD IMMEDIATELY - NO LOGIN REQUIRED
                return redirect(url_for('admin.view_id_card', id_card_id=id_card.id))
            else:
                # ID card not found yet - might be generating, show message
                flash('Your enrollment has been approved! Your ID card is being generated. Please refresh in a moment.', 'info')
                return render_template('enrollment_pending_approval.html', enrollment=enrollment)
        else:
            flash('User not found for this enrollment.', 'danger')
            return render_template('enrollment_pending_approval.html', enrollment=enrollment)
    
    # Still pending - show waiting page
    return render_template('enrollment_pending_approval.html', enrollment=enrollment)


@bp.route('/enroll/<int:class_id>', methods=['GET', 'POST'])
@bp.route('/enroll/<class_type>/<int:class_id>', methods=['GET', 'POST'])  # legacy URL with class_type
@login_required
def enroll_class(class_id, class_type=None):
    """Legacy enrollment route - requires login (kept for backward compatibility)"""
    # Redirect to new registration flow
    pricing_type = request.args.get('pricing', class_type or 'individual')
    return redirect(url_for('store.register_class', class_type=pricing_type, class_id=class_id))


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
def my_courses():
    from flask import session
    from ..models import User
    
    # Get user from session or current_user
    user = None
    user_id = None
    
    if current_user.is_authenticated:
        user = current_user
        user_id = current_user.id
    else:
        user_id = session.get('student_user_id') or session.get('user_id')
        if user_id:
            user = User.query.get(user_id)
    
    if not user:
        flash('Please enter your Name and System ID to access your courses.', 'info')
        return redirect(url_for('main.index'))
    
    purchases = (
        Purchase.query.filter_by(user_id=user_id, status='completed')
        .order_by(Purchase.purchased_at.desc())
        .all()
    )
    return render_template('my_courses.html', purchases=purchases, user=user)


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


