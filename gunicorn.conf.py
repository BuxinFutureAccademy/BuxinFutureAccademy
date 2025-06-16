# gunicorn.conf.py
import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', 10000)}"
backlog = 2048

# Worker processes
workers = 2
worker_class = "sync"
worker_connections = 1000

# CRITICAL: Extended timeout for video uploads
timeout = 300  # 5 minutes instead of 30 seconds
keepalive = 30

# Worker lifecycle
max_requests = 500
max_requests_jitter = 50
preload_app = True

# Memory management
worker_memory_limit = 400 * 1024 * 1024  # 400MB per worker

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"
capture_output = True

# Process naming
proc_name = "techbuxin_app"

# Graceful worker management
def worker_abort(worker):
    worker.log.warning(f"Worker {worker.pid} timeout - likely video upload in progress")

def when_ready(server):
    server.log.info("TechBuxin server ready for connections")

def post_fork(server, worker):
    server.log.info(f"Worker {worker.pid} spawned")
