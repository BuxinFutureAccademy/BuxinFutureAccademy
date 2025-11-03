import os
from datetime import datetime
from flask import Blueprint, current_app, redirect, url_for, flash, send_from_directory
from flask_login import login_required, current_user

from ..extensions import db
from ..models import DigitalProductFile, ProductOrder

bp = Blueprint('uploads', __name__)


@bp.route('/download_digital_product/<int:file_id>', endpoint='download_digital_product')
@login_required
def download_digital_product(file_id: int):
    digital_file = DigitalProductFile.query.get_or_404(file_id)

    if not getattr(current_user, 'is_admin', False):
        purchase = ProductOrder.query.filter_by(
            user_id=current_user.id,
            product_id=digital_file.product_id,
            status='completed',
        ).first()
        if not purchase:
            flash('You need to purchase this product to download the files.', 'warning')
            return redirect(url_for('store.product_detail', product_id=digital_file.product_id)) if False else redirect('/')

    digital_file.download_count = (digital_file.download_count or 0) + 1
    db.session.commit()

    if getattr(digital_file, 'storage_type', 'cloudinary') == 'cloudinary' and getattr(digital_file, 'cloudinary_url', None):
        return redirect(digital_file.cloudinary_url)

    digital_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'digital_products')
    file_path = os.path.join(digital_folder, digital_file.filename)
    if os.path.exists(file_path):
        return send_from_directory(
            digital_folder,
            digital_file.filename,
            as_attachment=True,
            download_name=digital_file.original_filename,
        )
    flash('File not found. Please contact support.', 'error')
    return redirect('/')


@bp.route('/admin/migrate-digital-files')
@login_required
def migrate_digital_files():
    if not getattr(current_user, 'is_admin', False):
        return 'Access denied', 403
    try:
        db.create_all()
        digital_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'digital_products')
        os.makedirs(digital_folder, exist_ok=True)
        return 'Digital files table ensured and upload folder ready.'
    except Exception as e:
        return f'Migration failed: {e}', 500
