import os
import warnings
from pathlib import Path

from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
from kombu import Exchange, Queue

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def env_str(name, default=''):
    return os.getenv(name, default)


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def env_int(name, default):
    value = os.getenv(name)
    return int(value) if value not in (None, '') else default


def env_list(name, default=''):
    return [item.strip() for item in os.getenv(name, default).split(',') if item.strip()]


DEBUG = env_bool('DEBUG', False)

SECRET_KEY = env_str('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-dev-only-key-do-not-use-in-production'
    else:
        raise ImproperlyConfigured(
            'SECRET_KEY environment variable must be set when DEBUG is False.'
        )
elif not DEBUG and (SECRET_KEY.startswith('django-insecure') or SECRET_KEY.startswith('change-me') or len(SECRET_KEY) < 32):
    raise ImproperlyConfigured(
        'SECRET_KEY is weak or a placeholder. Use a random value of at least 32 characters.'
    )

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1')

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
    'whitenoise.middleware.WhiteNoiseMiddleware',
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

ADMIN_URL = env_str('ADMIN_URL', 'admin/').strip('/') + '/'
ENABLE_API_DOCS = env_bool('ENABLE_API_DOCS', DEBUG)
METRICS_TOKEN = env_str('METRICS_TOKEN')

DATABASES = {
    'default': {
        'ENGINE': 'django_prometheus.db.backends.postgresql',
        'NAME': env_str('DB_NAME', 'fleet_db'),
        'USER': env_str('DB_USER', 'fleet_user'),
        'PASSWORD': env_str('DB_PASSWORD', 'fleet_password'),
        'HOST': env_str('DB_HOST', 'localhost'),
        'PORT': env_str('DB_PORT', '5432'),
        'CONN_MAX_AGE': env_int('DB_CONN_MAX_AGE', 60),
        'CONN_HEALTH_CHECKS': True,
        'DISABLE_SERVER_SIDE_CURSORS': True,
        'OPTIONS': {'connect_timeout': env_int('DB_CONNECT_TIMEOUT', 5)},
    }
}

if not DEBUG and DATABASES['default']['PASSWORD'] == 'fleet_password':
    raise ImproperlyConfigured('DB_PASSWORD must be set to a non-default value when DEBUG is False.')

AUTH_USER_MODEL = 'auth_module.User'

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

JWT_SIGNING_KEY = env_str('JWT_SIGNING_KEY') or SECRET_KEY
JWT_ACCESS_LIFETIME_MINUTES = env_int('JWT_ACCESS_LIFETIME_MINUTES', 30)
JWT_REFRESH_LIFETIME_DAYS = env_int('JWT_REFRESH_LIFETIME_DAYS', 7)

AUTH_MAX_FAILED_LOGINS = env_int('AUTH_MAX_FAILED_LOGINS', 5)
AUTH_LOCKOUT_SECONDS = env_int('AUTH_LOCKOUT_SECONDS', 900)
ALLOW_SELF_REGISTRATION = env_bool('ALLOW_SELF_REGISTRATION', True)

if not DEBUG and JWT_SIGNING_KEY == SECRET_KEY:
    warnings.warn('JWT_SIGNING_KEY is not set: JWTs are signed with SECRET_KEY. Use a separate key in production.')
if len(JWT_SIGNING_KEY) < 32 and not DEBUG:
    raise ImproperlyConfigured('JWT_SIGNING_KEY must be at least 32 characters when DEBUG is False.')

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024

CORS_ALLOWED_ORIGINS = env_list(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173',
)

ENABLE_HTTPS_ENFORCEMENT = env_bool('ENABLE_HTTPS_ENFORCEMENT', False)

if not DEBUG and not ENABLE_HTTPS_ENFORCEMENT:
    warnings.warn('DEBUG is False but ENABLE_HTTPS_ENFORCEMENT is off: NFR-SEC10 requires HTTPS in production.')

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_HTTPONLY = True

if ENABLE_HTTPS_ENFORCEMENT:
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r'^health/$']
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

_renderers = ['rest_framework.renderers.JSONRenderer']
if DEBUG:
    _renderers.append('rest_framework.renderers.BrowsableAPIRenderer')

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'auth_module.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'EXCEPTION_HANDLER': 'fleet_monitoring.exceptions.api_exception_handler',
    'DEFAULT_RENDERER_CLASSES': _renderers,
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'user': '1000/min',
        'login': '30/min',
        'register': '10/min',
        'refresh': '60/min',
        'ingestion': '100/min',
    },
    'NUM_PROXIES': env_int('NUM_PROXIES', 0) or None,
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Fleet Monitoring API',
    'DESCRIPTION': 'Backend API for fleet monitoring system',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

LOG_LEVEL = env_str('LOG_LEVEL', 'INFO').upper()

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
        'level': LOG_LEVEL,
    },
    'loggers': {
        'audit': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
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
        'LOCATION': env_str('REDIS_URL', 'redis://localhost:6379/1'),
        'KEY_PREFIX': 'fleet',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'IGNORE_EXCEPTIONS': True,
            'SOCKET_CONNECT_TIMEOUT': 2,
            'SOCKET_TIMEOUT': 2,
            'CONNECTION_POOL_KWARGS': {'max_connections': env_int('REDIS_MAX_CONNECTIONS', 100)},
        },
    }
}

DJANGO_REDIS_IGNORE_EXCEPTIONS = True
DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True
DJANGO_REDIS_LOGGER = 'fleet_monitoring.cache_degradation'

CELERY_BROKER_URL = env_str('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672//')
CELERY_RESULT_BACKEND = env_str('CELERY_RESULT_BACKEND_URL', 'redis://localhost:6379/2')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_RESULT_EXPIRES = 3600
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = env_int('CELERY_TASK_TIME_LIMIT', 300)
CELERY_TASK_SOFT_TIME_LIMIT = env_int('CELERY_TASK_SOFT_TIME_LIMIT', 240)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_TRANSPORT_OPTIONS = {'confirm_publish': True}
CELERY_WORKER_HIJACK_ROOT_LOGGER = False

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

CELERY_TASK_ALWAYS_EAGER = env_bool('CELERY_TASK_ALWAYS_EAGER', False)
CELERY_TASK_EAGER_PROPAGATES = True

CELERY_BEAT_SCHEDULE = {
    'telemetry-retention-cleanup': {
        'task': 'telemetry_module.tasks.cleanup_old_telemetry',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'telemetry.raw.process'},
    },
    'telemetry-ensure-future-partitions': {
        'task': 'telemetry_module.tasks.ensure_future_telemetry_partitions',
        'schedule': crontab(hour=1, minute=0),
        'options': {'queue': 'telemetry.raw.process'},
    },
    'daily-fleet-summary-report': {
        'task': 'reports_module.tasks.generate_scheduled_fleet_report',
        'schedule': crontab(hour=6, minute=0),
        'options': {'queue': 'reports.generate'},
    },
    'auth-cleanup-expired-refresh-tokens': {
        'task': 'auth_module.tasks.cleanup_expired_refresh_tokens',
        'schedule': crontab(hour=3, minute=30),
        'options': {'queue': 'telemetry.raw.process'},
    },
    'system-health-heartbeat': {
        'task': 'telemetry_module.tasks.system_health_check',
        'schedule': 300.0,
        'options': {'queue': 'telemetry.raw.process'},
    },
}

TELEMETRY_RETENTION_DAYS = env_int('TELEMETRY_RETENTION_DAYS', 365)
ALERT_COOLDOWN_SECONDS = env_int('ALERT_COOLDOWN_SECONDS', 300)
TELEMETRY_MAX_FUTURE_SECONDS = env_int('TELEMETRY_MAX_FUTURE_SECONDS', 300)
TELEMETRY_CACHE_TTL_SECONDS = env_int('TELEMETRY_CACHE_TTL_SECONDS', 86400)

EMAIL_BACKEND = env_str('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = env_str('EMAIL_HOST', 'localhost')
EMAIL_PORT = env_int('EMAIL_PORT', 25)
EMAIL_HOST_USER = env_str('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = env_str('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', False)
DEFAULT_FROM_EMAIL = env_str('DEFAULT_FROM_EMAIL', 'alerts@fleet-monitoring.local')