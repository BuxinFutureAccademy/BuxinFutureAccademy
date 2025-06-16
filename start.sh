#!/bin/bash
# start.sh - Optimized startup script for Render

set -e  # Exit on any error

echo "🚀 Starting TechBuxin Flask Application..."
echo "📅 $(date)"

# Environment setup
export PYTHONPATH="/opt/render/project/src:$PYTHONPATH"
export FLASK_APP=app.py
export FLASK_ENV=production
export PYTHONUNBUFFERED=1

# Memory optimization
export MALLOC_ARENA_MAX=2
export PYTHONMALLOC=malloc

echo "🔧 Environment configured"

# Database initialization with retry logic
echo "📊 Initializing database..."
python -c "
import sys
import time
from app import app, db

max_retries = 3
for attempt in range(max_retries):
    try:
        with app.app_context():
            db.create_all()
            print(f'✅ Database initialized (attempt {attempt + 1})')
            break
    except Exception as e:
        print(f'❌ Database init failed (attempt {attempt + 1}): {e}')
        if attempt == max_retries - 1:
            print('💥 Database initialization failed after all retries')
            sys.exit(1)
        time.sleep(5)
"

echo "🌐 Starting Gunicorn server..."

# Use the configuration file
exec gunicorn \
    --config gunicorn.conf.py \
    --bind 0.0.0.0:$PORT \
    --timeout 300 \
    --workers 2 \
    --worker-class sync \
    --worker-connections 1000 \
    --max-requests 500 \
    --max-requests-jitter 50 \
    --preload \
    --worker-tmp-dir /dev/shm \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    app:application
