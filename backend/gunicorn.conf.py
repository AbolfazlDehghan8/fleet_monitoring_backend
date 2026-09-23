import multiprocessing
import os

bind = '0.0.0.0:8000'
workers = int(os.getenv('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
threads = int(os.getenv('GUNICORN_THREADS', 1))
timeout = int(os.getenv('GUNICORN_TIMEOUT', 30))
graceful_timeout = 30
keepalive = 5
max_requests = 5000
max_requests_jitter = 500
worker_tmp_dir = '/dev/shm'
accesslog = '-'
errorlog = '-'
loglevel = os.getenv('LOG_LEVEL', 'info').lower()
forwarded_allow_ips = os.getenv('FORWARDED_ALLOW_IPS', '127.0.0.1')