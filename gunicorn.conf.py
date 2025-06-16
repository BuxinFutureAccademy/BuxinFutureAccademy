# gunicorn.conf.py
import os

# Worker configuration optimized for Render
bind = f"0.0.0.0:{os.environ.get('PORT', 10000)}"
workers = 2  # Reduced for memory efficiency on Render
worker_class = "sync"
worker_connections = 1000

# Critical: Extended timeouts for video uploads
timeout = 300  # 5 minutes for video uploads (was 30s default)
keepalive = 30
max_requests = 500
max_requests_jitter = 50

# Memory management to prevent crashes
worker_memory_limit = 400 * 1024 * 1024  # 400MB per worker
max_worker_memory_usage = 300 * 1024 * 1024  # 300MB restart threshold

# Logging configuration
loglevel = "info"
accesslog = "-"
errorlog = "-"
capture_output = True
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming for easier monitoring
proc_name = "techbuxin_flask_app"

# Performance optimizations
preload_app = True
enable_stdio_inheritance = True
reuse_port = True

# Security and limits
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Graceful handling of worker issues
def worker_abort(worker):
    """Handle worker timeout gracefully"""
    worker.log.warning(f"Worker {worker.pid} timed out - likely during file upload")

def when_ready(server):
    """Called when server is ready"""
    server.log.info("TechBuxin server ready - workers spawning")

def worker_int(worker):
    """Handle worker interrupt signals"""
    worker.log.info(f"Worker {worker.pid} received interrupt signal")

def pre_fork(server, worker):
    """Called before worker fork"""
    server.log.info(f"Pre-fork worker {worker.pid}")

def post_fork(server, worker):
    """Called after worker fork"""
    server.log.info(f"Post-fork worker {worker.pid}")
    
def worker_exit(server, worker):
    """Called when worker exits"""
    server.log.info(f"Worker {worker.pid} exited")
