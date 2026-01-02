from flask import Blueprint, redirect, url_for, flash
from flask_login import login_required

from ..extensions import db
from ..models import LearningMaterial

bp = Blueprint('materials', __name__)


@bp.route('/admin/material/delete/<int:material_id>', methods=['POST'])
@login_required
def delete_material(material_id):
    from flask import request
    material = LearningMaterial.query.get_or_404(material_id)
    class_type = material.class_type
    
    db.session.delete(material)
    db.session.commit()
    flash('Material deleted successfully.', 'success')
    
    # Redirect to the appropriate admin page based on class type
    if class_type == 'school':
        return redirect(url_for('admin.admin_schools'))
    elif class_type == 'individual':
        return redirect(url_for('admin.admin_individual_classes'))
    elif class_type == 'group':
        return redirect(url_for('admin.admin_group_classes'))
    elif class_type == 'family':
        return redirect(url_for('admin.admin_family_classes'))
    else:
        return redirect(url_for('admin.admin_dashboard'))
