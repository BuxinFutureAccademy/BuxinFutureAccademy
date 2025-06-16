#!/bin/bash
set -e

echo "🚀 Starting TechBuxin Application..."

# Environment setup
export PYTHONPATH="/opt/render/project/src:$PYTHONPATH"
export FLASK_APP=app.py
export FLASK_ENV=production
export PYTHONUNBUFFERED=1

# Memory optimization for Render
export MALLOC_ARENA_MAX=2

echo "📊 Initializing database..."
python -c "
try:
    from app import app, db
    with app.app_context():
        db.create_all()
        print('✅ Database initialized')
except Exception as e:
    print(f'❌ Database init error: {e}')
    import sys
    sys.exit(1)
"

echo "🌐 Starting production server..."
exec gunicorn --config gunicorn.conf.py app:application
