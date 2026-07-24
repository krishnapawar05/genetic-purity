import os

# Server socket binding
bind = "0.0.0.0:" + os.environ.get("PORT", "5000")

# Worker processes: 1 worker process keeps RAM usage under Railway's 1 GB limit
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))

# Worker threads: gthread worker class enables non-blocking concurrent request processing
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
worker_class = "gthread"

# Worker timeouts: 180s (3 minutes) prevents SIGKILL during large 20 MB image uploads and inference
timeout = 180
graceful_timeout = 30
keepalive = 5

# Recycle worker processes periodically to avoid memory fragmentation over long runtime
max_requests = 100
max_requests_jitter = 10
