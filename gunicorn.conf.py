# gunicorn.conf.py
import os

# Worker configuration for Render
bind = f"0.0.0.0:{os.environ.get('PORT', 10000)}"
workers = 2  # Reduced for memory efficiency
worker_class = "sync"
worker_connections = 1000

# Timeout settings for video uploads
timeout = 300  # 5 minutes for video uploads
keepalive = 30
max_requests = 500
max_requests_jitter = 50

# Memory management
worker_memory_limit = 400 * 1024 * 1024  # 400MB per worker
max_worker_memory_usage = 300 * 1024 * 1024  # 300MB limit

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"
capture_output = True

# Process naming
proc_name = "techbuxin_flask_app"

# Graceful worker restarts
preload_app = True
enable_stdio_inheritance = True

# Security
limit_request_line = 4094
limit_request_fields = 100

def worker_abort(worker):
    """Handle worker timeout gracefully"""
    worker.log.info("Worker timed out - likely during file upload")

def when_ready(server):
    """Called just after the server is started"""
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    """Handle worker interrupt"""
    worker.log.info("Worker received INT or QUIT signal")
