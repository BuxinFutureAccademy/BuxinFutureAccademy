from flask import Blueprint, redirect, url_for, flash
from flask_login import login_required

from ..extensions import db
from ..models import LearningMaterial

bp = Blueprint('materials', __name__)


@bp.route('/admin/material/delete/<int:material_id>', methods=['POST'])
@login_required
def delete_material(material_id):
    material = LearningMaterial.query.get_or_404(material_id)
    db.session.delete(material)
    db.session.commit()
    flash('Material deleted successfully.', 'success')
    return redirect(url_for('admin_dashboard', _anchor='materials'))
