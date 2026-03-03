import multiprocessing

# Server socket
bind = "0.0.0.0:10000"

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000

# Timeout — set high because AI pipeline can take a while
timeout = 300
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
