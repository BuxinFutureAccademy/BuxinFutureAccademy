import os
from flask import Blueprint, current_app
from flask_login import login_required, current_user

from ..extensions import db

bp = Blueprint('uploads', __name__)


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
