from flask import Blueprint, jsonify

bp = Blueprint('health', __name__)

@bp.route('/api/health')
@bp.route('/health')
@bp.route('/status')
@bp.route('/ping')
def health_check():
    """
    Database-free health check endpoint.
    This endpoint confirms the application process is running without accessing Neon.
    Used by monitoring services, uptime checks, and wake-up requests.
    """
    # NO DATABASE ACCESS - NO MODEL IMPORTS - NO SESSION CHECKS
    return jsonify({
        "status": "healthy",
        "service": "running",
        "message": "Application is running"
    }), 200
