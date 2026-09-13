from pathlib import Path
import os
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

_INSECURE_DEFAULT_SECRET_KEY = 'django-insecure-i1c79ca#r*+y4kt_*%$u@g9pop&!tgw(4bzt*=t2%0zd&@bccn'
SECRET_KEY = os.getenv('SECRET_KEY', _INSECURE_DEFAULT_SECRET_KEY)

DEBUG = os.getenv('DEBUG', 'True') == 'True'

if not DEBUG and SECRET_KEY == _INSECURE_DEFAULT_SECRET_KEY:
    raise ImproperlyConfigured(
        'SECRET_KEY environment variable must be set to a strong, unique value when DEBUG=False.'
    )

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django_prometheus',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'corsheaders',
    'drf_spectacular',

    'auth_module',
    'vehicles_module',
    'telemetry_module',
    'rules_module',
    'alerts_module',
    'reports_module',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'fleet_monitoring.middleware.CorrelationIdMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'fleet_monitoring.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'fleet_monitoring.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django_prometheus.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'fleet_db'),
        'USER': os.getenv('DB_USER', 'fleet_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'fleet_password'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

AUTH_USER_MODEL = 'auth_module.User'

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOWED_ORIGINS = os.getenv(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173'
).split(',')

ENABLE_HTTPS_ENFORCEMENT = os.getenv('ENABLE_HTTPS_ENFORCEMENT', 'False') == 'True'

if ENABLE_HTTPS_ENFORCEMENT:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'auth_module.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'user': '1000/min',
        'login': '30/min',
        'register': '10/min',
        'ingestion': '100/min',
    },
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Fleet Monitoring API',
    'DESCRIPTION': 'Backend API for fleet monitoring system',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'correlation_id': {
            '()': 'fleet_monitoring.logging_utils.CorrelationIdFilter',
        },
    },
    'formatters': {
        'json': {
            '()': 'fleet_monitoring.logging_utils.JsonFormatter',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
            'filters': ['correlation_id'],
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'audit': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'fleet_monitoring.cache_degradation': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'IGNORE_EXCEPTIONS': True,
            'SOCKET_CONNECT_TIMEOUT': 2,
            'SOCKET_TIMEOUT': 2,
        }
    }
}

DJANGO_REDIS_IGNORE_EXCEPTIONS = True
DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True
DJANGO_REDIS_LOGGER = 'fleet_monitoring.cache_degradation'

from kombu import Exchange, Queue

CELERY_BROKER_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672//')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND_URL', 'redis://localhost:6379/2')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

CELERY_WORKER_SEND_TASK_EVENTS = True
CELERY_TASK_SEND_SENT_EVENT = True

telemetry_exchange = Exchange('fleet.telemetry', type='direct', durable=True)
dlx_exchange = Exchange('fleet.dlx', type='direct', durable=True)

DEAD_LETTER_QUEUE_ARGUMENTS = {
    'x-dead-letter-exchange': 'fleet.dlx',
    'x-dead-letter-routing-key': 'tasks.dead_letter',
    'x-queue-type': 'classic',
}

DLQ_QUEUE_ARGUMENTS = {
    'x-queue-type': 'classic',
}

CELERY_TASK_QUEUES = (
    Queue(
        'telemetry.raw.process', telemetry_exchange, routing_key='telemetry.raw.process',
        durable=True, queue_arguments=DEAD_LETTER_QUEUE_ARGUMENTS,
    ),
    Queue(
        'alerts.trigger.notify', telemetry_exchange, routing_key='alerts.trigger.notify',
        durable=True, queue_arguments=DEAD_LETTER_QUEUE_ARGUMENTS,
    ),
    Queue(
        'reports.generate', telemetry_exchange, routing_key='reports.generate',
        durable=True, queue_arguments=DEAD_LETTER_QUEUE_ARGUMENTS,
    ),
    Queue(
        'tasks.dead_letter', dlx_exchange, routing_key='tasks.dead_letter',
        durable=True, queue_arguments=DLQ_QUEUE_ARGUMENTS,
    ),
)
CELERY_TASK_DEFAULT_QUEUE = 'telemetry.raw.process'
CELERY_TASK_DEFAULT_EXCHANGE = 'fleet.telemetry'
CELERY_TASK_DEFAULT_ROUTING_KEY = 'telemetry.raw.process'

CELERY_TASK_ROUTES = {
    'telemetry_module.tasks.*': {'queue': 'telemetry.raw.process'},
    'alerts_module.tasks.*': {'queue': 'alerts.trigger.notify'},
    'reports_module.tasks.*': {'queue': 'reports.generate'},
}

CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', 'False').lower() == 'true'
CELERY_TASK_EAGER_PROPAGATES = True

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'telemetry-retention-cleanup': {
        'task': 'telemetry_module.tasks.cleanup_old_telemetry',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'telemetry.raw.process'},
    },
    'telemetry-ensure-future-partitions': {
        'task': 'telemetry_module.tasks.ensure_future_telemetry_partitions',
        'schedule': crontab(hour=1, minute=0, day_of_month=1),
        'options': {'queue': 'telemetry.raw.process'},
    },
    'daily-fleet-summary-report': {
        'task': 'reports_module.tasks.generate_scheduled_fleet_report',
        'schedule': crontab(hour=6, minute=0),
        'options': {'queue': 'reports.generate'},
    },
    'system-health-heartbeat': {
        'task': 'telemetry_module.tasks.system_health_check',
        'schedule': 300.0,
        'options': {'queue': 'telemetry.raw.process'},
    },
}

TELEMETRY_RETENTION_DAYS = int(os.getenv('TELEMETRY_RETENTION_DAYS', '365'))

EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '25'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'False') == 'True'
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'alerts@fleet-monitoring.local')