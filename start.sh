#!/bin/bash
# start.sh

echo "🚀 Starting TechBuxin Flask App..."

# Set environment variables
export PYTHONPATH="/opt/render/project/src:$PYTHONPATH"
export FLASK_APP=app.py
export FLASK_ENV=production

# Database setup
echo "📊 Setting up database..."
python -c "
try:
    from app import app, db
    with app.app_context():
        db.create_all()
        print('✅ Database tables created/verified')
except Exception as e:
    print(f'❌ Database setup failed: {e}')
    exit(1)
"

# Start with optimized Gunicorn
echo "🌐 Starting Gunicorn server..."
exec gunicorn \
    --config gunicorn.conf.py \
    --workers 2 \
    --timeout 300 \
    --bind 0.0.0.0:$PORT \
    --worker-class sync \
    --worker-connections 1000 \
    --max-requests 500 \
    --max-requests-jitter 50 \
    --preload \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    app:application
