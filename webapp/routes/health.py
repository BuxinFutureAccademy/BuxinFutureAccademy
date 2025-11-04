from flask import Blueprint, jsonify
import logging
import traceback

bp = Blueprint('health', __name__)

@bp.route('/api/health')
def health_check():
    """Health check endpoint to verify the application is running correctly."""
    try:
        from ..extensions import db
        from ..services import cloudinary_service
        
        # Test database connection
        db.session.execute('SELECT 1')
        
        # Test Cloudinary connection if configured
        cloudinary_status = "not configured"
        try:
            cloudinary_status = "available" if cloudinary_service.is_available() else "unavailable"
        except Exception as e:
            cloudinary_status = f"error: {str(e)}"
        
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "cloudinary": cloudinary_status,
            "environment": "production"
        })
        
    except Exception as e:
        logging.error(f"Health check failed: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({
            "status": "error",
            "error": str(e),
            "type": type(e).__name__
        }), 500
