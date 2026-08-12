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
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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
        'ENGINE': 'django.db.backends.postgresql',
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
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
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

CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')

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
    'formatters': {
        'audit': {
            'format': '%(asctime)s | actor=%(actor)s | action=%(action)s | %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
        'audit_console': {
            'class': 'logging.StreamHandler',
            'formatter': 'audit',
        },
    },
    'loggers': {
        'audit': {
            'handlers': ['audit_console'],
            'level': 'INFO',
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
        }
    }
}

from kombu import Exchange, Queue

CELERY_BROKER_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672//')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND_URL', 'redis://localhost:6379/2')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

telemetry_exchange = Exchange('fleet.telemetry', type='direct', durable=True)

CELERY_TASK_QUEUES = (
    Queue('telemetry.raw.process', telemetry_exchange, routing_key='telemetry.raw.process', durable=True),
)
CELERY_TASK_DEFAULT_QUEUE = 'telemetry.raw.process'
CELERY_TASK_DEFAULT_EXCHANGE = 'fleet.telemetry'
CELERY_TASK_DEFAULT_ROUTING_KEY = 'telemetry.raw.process'

CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', 'False').lower() == 'true'
CELERY_TASK_EAGER_PROPAGATES = True