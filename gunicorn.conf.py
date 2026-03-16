# Gunicorn production config — capped at 2 workers for Render free/starter tier
bind = "0.0.0.0:10000"
workers = 2           # FIX: was cpu_count*2+1 — caused OOM on Render
worker_class = "sync"
timeout = 600         # 10 min — pipeline can take 3-5 min
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"
