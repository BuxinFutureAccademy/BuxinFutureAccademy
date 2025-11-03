from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from ..services.cloudinary_service import cloudinary_service

bp = Blueprint('file_uploads', __name__)

def allowed_file(filename, allowed_extensions=None):
    """Check if the file extension is allowed."""
    if allowed_extensions is None:
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'mp4', 'mov'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

@bp.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    """
    Handle file uploads to Cloudinary.
    Expected form data:
    - file: The file to upload
    - folder: (optional) The folder in Cloudinary
    - resource_type: (optional) Type of resource ('image', 'video', 'raw', 'auto')
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400

    # Get upload parameters
    folder = request.form.get('folder', 'misc')
    resource_type = request.form.get('resource_type', 'auto')
    
    # Upload to Cloudinary
    success, result = cloudinary_service.upload_file(
        file=file,
        folder=folder,
        resource_type=resource_type
    )
    
    if success:
        return jsonify({
            'message': 'File uploaded successfully',
            'data': result
        }), 200
    else:
        return jsonify({'error': result}), 500

@bp.route('/api/delete-file', methods=['POST'])
@login_required
def delete_file():
    """
    Delete a file from Cloudinary.
    Expected JSON data:
    {
        "public_id": "folder/filename",
        "resource_type": "image"  # or 'video', 'raw'
    }
    """
    data = request.get_json()
    if not data or 'public_id' not in data:
        return jsonify({'error': 'Missing public_id'}), 400
    
    public_id = data['public_id']
    resource_type = data.get('resource_type', 'image')
    
    success, message = cloudinary_service.delete_file(public_id, resource_type)
    
    if success:
        return jsonify({'message': message}), 200
    else:
        return jsonify({'error': message}), 500
