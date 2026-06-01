import sys
import os
from pathlib import Path
from datetime import datetime as dt
from django.utils.translation import gettext_lazy as _
from pathlib import Path
from datetime import datetime as dt
from django.utils.translation import gettext_lazy as _
# Near top of settings.py
from celery.schedules import crontab
# ΝΕΟ: Load environment variables

from dotenv import load_dotenv
load_dotenv()

# Προειδοποίηση (όχι σφάλμα) αν τρέχει σε μη υποστηριζόμενη Python. Το Django 5.0
# υποστηρίζει 3.10–3.12· σε 3.13/3.14 ο Django test client σπάει και η
# συμπεριφορά αποκλίνει από production (Docker/CI = 3.11).
if sys.version_info[:2] not in {(3, 10), (3, 11), (3, 12)}:
    import warnings as _warnings
    _warnings.warn(
        f"Μη υποστηριζόμενη έκδοση Python {sys.version_info.major}."
        f"{sys.version_info.minor} για Django 5.0 (συνιστάται 3.11 — βλ. "
        f".python-version). Σε 3.13+ τα tests/test-client ενδέχεται να σπάσουν.",
        RuntimeWarning,
    )


from crm.settings import *          # NOQA
from common.settings import *       # NOQA
from tasks.settings import *        # NOQA
from voip.settings import *         # NOQA
from .datetime_settings import *    # NOQA
# Μετά συνέχισε με τα imports σου
from crm.settings import *          # NOQA
from common.settings import *       # NOQA

# ---- Django settings ---- #

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
# To get new value of key use code:
# from django.core.management.utils import get_random_secret_key
# print(get_random_secret_key())
SECRET_KEY = os.getenv('SECRET_KEY', 'default-key-for-development')

# Add your hosts to the list (configured below)

# Database - SECURITY FIX: Use environment variables
DATABASES = {
    'default': {
        # SQLite for development
        'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.sqlite3'),
        'NAME': os.getenv('DB_NAME', str(BASE_DIR / 'db.sqlite3')),

        # For PostgreSQL/MySQL production
        'USER': os.getenv('DB_USER', ''),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', ''),
    }
}

# Email Configuration
# For testing without real SMTP, set EMAIL_BACKEND_CONSOLE=true in .env
if os.getenv('EMAIL_BACKEND_CONSOLE', 'false').lower() in ('true', '1', 'yes'):
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_SUBJECT_PREFIX = 'CRM: '
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'true').lower() in ('true', '1', 'yes')

SERVER_EMAIL = os.getenv('SERVER_EMAIL', os.getenv('EMAIL_HOST_USER', ''))
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', os.getenv('EMAIL_HOST_USER', ''))

# Email Rate Limiting and Connection Pooling
# These settings prevent SMTP throttling and improve bulk email performance
EMAIL_RATE_LIMIT = float(os.getenv('EMAIL_RATE_LIMIT', '2.0'))  # emails per second
EMAIL_BURST_LIMIT = int(os.getenv('EMAIL_BURST_LIMIT', '5'))    # max burst size
EMAIL_POOL_MAX_CONNECTIONS = int(os.getenv('EMAIL_POOL_MAX_CONNECTIONS', '3'))
EMAIL_POOL_CONNECTION_TTL = float(os.getenv('EMAIL_POOL_CONNECTION_TTL', '300.0'))  # seconds

# Email Retry Settings
EMAIL_MAX_RETRIES = int(os.getenv('EMAIL_MAX_RETRIES', '3'))
EMAIL_RETRY_BASE_DELAY = float(os.getenv('EMAIL_RETRY_BASE_DELAY', '2.0'))  # seconds
EMAIL_RETRY_MAX_DELAY = float(os.getenv('EMAIL_RETRY_MAX_DELAY', '30.0'))   # seconds

# Admin email for error notifications - configure via environment
ADMIN_NAME = os.getenv('ADMIN_NAME', 'Admin')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', os.getenv('EMAIL_HOST_USER', ''))
ADMINS = [(ADMIN_NAME, ADMIN_EMAIL)] if ADMIN_EMAIL else []

# SECURITY WARNING: don't run with debug turned on in production!
# SECURITY FIX: Default to False, only enable in dev with explicit env var
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')

# ALLOWED_HOSTS - ρυθμίζεται μέσω env (comma-separated λίστα).
# ΠΡΟΣΟΧΗ: Το Django ΔΕΝ υποστηρίζει μερικά wildcards όπως '192.168.*.*'.
# Για πρόσβαση από τοπικό δίκτυο: είτε DEBUG=True (επιτρέπει τα πάντα),
# είτε όρισε ρητά τα hosts/IPs στο env ALLOWED_HOSTS.
_allowed_hosts_env = os.getenv('ALLOWED_HOSTS', '')
if _allowed_hosts_env:
    ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_env.split(',') if h.strip()]
elif DEBUG:
    # Development / τοπικό δίκτυο: επιτρέπει όλα τα hosts (τα μερικά wildcards
    # δεν υποστηρίζονται, οπότε αυτός είναι ο μόνος τρόπος για 192.168.x.x clients).
    ALLOWED_HOSTS = ['*']
else:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1']

FORMS_URLFIELD_ASSUME_HTTPS = True

# Internationalization
LANGUAGE_CODE = 'el'
LANGUAGES = [
    ('ar', 'Arabic'),
    ('cs', 'Czech'),
    ('de', 'German'),
    ('el', 'Greek'),
    ('en', 'English'),
    ('es', 'Spanish'),
    ('fr', 'French'),
    ('he', 'Hebrew'),
    ('hi', 'Hindi'),
    ('id', 'Indonesian'),
    ('it', 'Italian'),
    ('ja', 'Japanese'),
    ('ko', 'Korean'),
    ('nl', 'Nederlands'),
    ('pl', 'Polish'),
    ('pt-br', 'Portuguese'),
    ('ro', 'Romanian'),
    ('ru', 'Russian'),
    ('tr', 'Turkish'),
    ('uk', 'Ukrainian'),
    ('vi', 'Vietnamese'),
    ('zh-hans', 'Chinese'),
]

TIME_ZONE = 'Europe/Athens'   # specify your time zone

USE_I18N = True

USE_TZ = True

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

LOGIN_URL = '/admin/login/'

# Application definition
# Application definition
INSTALLED_APPS = [
    'accounting',
    'django.contrib.sites',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'crm.apps.CrmConfig',
    'massmail.apps.MassmailConfig',
    'analytics.apps.AnalyticsConfig',
    'help',
    'tasks.apps.TasksConfig',
    'chat.apps.ChatConfig',
    'voip',
    'common.apps.CommonConfig',
    'settings',
    'rest_framework',
    'corsheaders',
    'rest_framework_simplejwt',
    'inventory',
    'mydata',
    'rest_framework.authtoken',
    'rest_framework_simplejwt.token_blacklist',  # JWT token blacklist for logout
    'drf_spectacular',  # OpenAPI/Swagger documentation
    'django_q',
    # 'tinymce',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # ← ΝΕΟ
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'common.utils.usermiddleware.UserMiddleware'
]

ROOT_URLCONF = 'webcrm.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # ✅ Accounting Dashboard Statistics
                'accounting.context_processors.dashboard_stats',
            ],
        },
    },
]

WSGI_APPLICATION = 'webcrm.wsgi.application'

# Password validation
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

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'static'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Archive root for client files - can be configured to network path
# Examples:
#   - Local: BASE_DIR / 'media' / 'archive'
#   - Network (Linux): '/mnt/nas/logistiko/'
#   - Network (Windows): 'Z:\\Logistiko\\'
ARCHIVE_ROOT = os.environ.get('ARCHIVE_ROOT', str(BASE_DIR / 'media'))

FIXTURE_DIRS = ['tests/fixtures']

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

SITE_ID = 1

SECURE_HSTS_SECONDS = 0  # set to 31536000 for the production server
# Set all the following to True for the production server
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_PRELOAD = False
X_FRAME_OPTIONS = "SAMEORIGIN"

# ---- CRM settings ---- #

# For more security, replace the url prefixes
# with your own unique value.
SECRET_CRM_PREFIX = '123/'
SECRET_ADMIN_PREFIX = '456-admin/'
SECRET_LOGIN_PREFIX = '789-login/'

# Specify ip of host to avoid importing emails sent by CRM
CRM_IP = "127.0.0.1"

CRM_REPLY_TO = ["'Do not reply' <crm@example.com>"]

# List of addresses to which users are not allowed to send mail.
NOT_ALLOWED_EMAILS = []

# List of applications on the main page and in the left sidebar.
APP_ON_INDEX_PAGE = [
    'tasks', 'crm', 'analytics',
    'massmail', 'common', 'settings'
]
MODEL_ON_INDEX_PAGE = {
    'tasks': {
        'app_model_list': ['Task', 'Memo']
    },
    'crm': {
        'app_model_list': [
            'Request', 'Deal', 'Lead', 'Company',
            'CrmEmail', 'Payment', 'Shipment'
        ]
    },
    'analytics': {
        'app_model_list': [
            'IncomeStat', 'RequestStat'
        ]
    },
    'massmail': {
        'app_model_list': [
            'MailingOut', 'EmlMessage'
        ]
    },
    'common': {
        'app_model_list': [
            'UserProfile', 'Reminder'
        ]
    },
    'settings': {
        'app_model_list': [
            'PublicEmailDomain', 'StopPhrase'
        ]
    }
}

# Country VAT value
VAT = 24    # %

# 2-Step Verification Credentials for Google Accounts.
#  OAuth 2.0
CLIENT_ID = ''
CLIENT_SECRET = ''
OAUTH2_DATA = {
    'smtp.gmail.com': {
        'scope': "https://mail.google.com/",
        'accounts_base_url': 'https://accounts.google.com',
        'auth_command': 'o/oauth2/auth',
        'token_command': 'o/oauth2/token',
    }
}
# Hardcoded dummy redirect URI for non-web apps.
REDIRECT_URI = ''

# Credentials for Google reCAPTCHA.
GOOGLE_RECAPTCHA_SITE_KEY = ''
GOOGLE_RECAPTCHA_SECRET_KEY = ''

GEOIP = False
GEOIP_PATH = MEDIA_ROOT / 'geodb'

# For user profile list
SHOW_USER_CURRENT_TIME_ZONE = False

NO_NAME_STR = _('Untitled')

# For automated getting currency exchange rate
LOAD_EXCHANGE_RATE = False
LOADING_EXCHANGE_RATE_TIME = "6:30"
LOAD_RATE_BACKEND = ""  # "crm.backends.<specify_backend>.<specify_class>"

# Ability to mark payments through a representation
MARK_PAYMENTS_THROUGH_REP = False

# Site headers
SITE_TITLE = 'CRM'
ADMIN_HEADER = "ADMIN"
ADMIN_TITLE = "CRM Admin"
INDEX_TITLE = _('Main Menu')

# Allow mailing
MAILING = True
ENABLE_EMAIL_IMPORT = False
#ENABLE_IMAP_IMPORT = False
#EMAIL_IMPORT_ENABLED = False


# This is copyright information. Please don't change it!
COPYRIGHT_STRING = f"Django-CRM. Copyright (c) {dt.now().year}"
PROJECT_NAME = "dpeconsolutions_crm "
PROJECT_SITE = "www.dpeconsolutions.com"


TESTING = sys.argv[1:2] == ['test']
if TESTING:
    SECURE_SSL_REDIRECT = False
    LANGUAGE_CODE = 'en'
    LANGUAGES = [('en', ''), ('uk', '')]


    # CORS Settings - Επιτρέπει πρόσβαση από τοπικό δίκτυο
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://192.168.178.22:5173",  # Network IP για React
    "http://192.168.178.22:3000",  # Alternative React port
]

# Για development - επιτρέπει όλες τις origins (wildcard)
# ΣΗΜΕΙΩΣΗ: Αυτό λειτουργεί ΜΟΝΟ αν DEBUG=True
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOW_CREDENTIALS = True

# Additional CORS settings για καλύτερη συμβατότητα
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    # OpenAPI/Swagger schema generation
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # Rate limiting - protects against abuse/DDoS
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',       # Anonymous users: 100 requests/hour
        'user': '1000/hour',      # Authenticated users: 1000 requests/hour
        'set_password': '3/hour',   # Client portal password-set: brute-force guard (tight)
        'vat_read': '120/hour',     # Client portal VAT read: anti-scraping guard
    },
    # Exception handling
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',
}

# JWT Settings
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=5),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# drf-spectacular (OpenAPI/Swagger) Configuration
SPECTACULAR_SETTINGS = {
    'TITLE': 'LogistikoCRM API',
    'DESCRIPTION': 'API για Λογιστικό CRM - Django backend για React frontend integration',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': False,
    },
    'SWAGGER_UI_DIST': 'SIDECAR',
    'SWAGGER_UI_FAVICON_HREF': 'SIDECAR',
    'REDOC_DIST': 'SIDECAR',
    # Security scheme for JWT
    'SECURITY': [{'Bearer': []}],
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'Bearer': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
        }
    },
}

# myDATA Configuration (DUMMY για testing)
MYDATA_USER_ID = "ddiplas"
MYDATA_SUBSCRIPTION_KEY = os.getenv('MYDATA_SUBSCRIPTION_KEY', '')

MYDATA_IS_SANDBOX = True  


Q_CLUSTER = {
    'name': 'LogistikoCRM',
    'workers': 2,
    'timeout': 90,
    'retry': 120,
    'queue_limit': 50,
    'bulk': 10,
    'orm': 'default',  # Use Django ORM instead of Redis!
    'sync': False,  # Run async
    'save_limit': 100,
    'label': 'Λογιστικό CRM',
}


# ==============================================================================
# 🏢 PERSONALIZATION - LogistikoCRM Configuration
# ==============================================================================

# Company Information - Configure via environment variables
COMPANY_NAME = os.getenv('COMPANY_NAME', 'Λογιστικό Γραφείο')
COMPANY_SHORT_NAME = os.getenv('COMPANY_SHORT_NAME', 'Λογιστήριο')
COMPANY_WEBSITE = os.getenv('COMPANY_WEBSITE', '')
COMPANY_PHONE = os.getenv('COMPANY_PHONE', '')
COMPANY_ADDRESS = os.getenv('COMPANY_ADDRESS', '')

# Accountant Information - Configure via environment variables
ACCOUNTANT_NAME = os.getenv('ACCOUNTANT_NAME', '')
ACCOUNTANT_TITLE = os.getenv('ACCOUNTANT_TITLE', 'Λογιστής')
ACCOUNTANT_EMAIL = os.getenv('ACCOUNTANT_EMAIL', EMAIL_HOST_USER)
ACCOUNTANT_PHONE = os.getenv('ACCOUNTANT_PHONE', COMPANY_PHONE)

# Email Template Defaults
EMAIL_SIGNATURE = f"""
Με εκτίμηση,

{ACCOUNTANT_NAME}
{ACCOUNTANT_TITLE}
{COMPANY_NAME}

📧 {ACCOUNTANT_EMAIL}
📞 {COMPANY_PHONE}
🌐 {COMPANY_WEBSITE}
"""

# Email Subject Prefixes
EMAIL_SUBJECT_PREFIX_COMPLETION = "✅ Ολοκλήρωση Υποχρέωσης"
EMAIL_SUBJECT_PREFIX_REMINDER = "⏰ Υπενθύμιση Προθεσμίας"
EMAIL_SUBJECT_PREFIX_OVERDUE = "⚠️ Καθυστερημένη Υποχρέωση"

# Branding
SITE_TITLE = 'LogistikoCRM - Λογιστικό Σύστημα'
ADMIN_HEADER = "ΔΙΑΧΕΙΡΙΣΗ ΛΟΓΙΣΤΙΚΟΥ"
ADMIN_TITLE = "LogistikoCRM Admin"
INDEX_TITLE = 'Κεντρικό Μενού'

# Copyright
COPYRIGHT_STRING = f"{COMPANY_NAME}. Copyright © {dt.now().year}"
PROJECT_NAME = "LogistikoCRM"

# Business Hours (for scheduling)
BUSINESS_HOURS_START = "09:00"
BUSINESS_HOURS_END = "17:00"

# Default Email Templates Context
DEFAULT_EMAIL_CONTEXT = {
    'company_name': COMPANY_NAME,
    'company_short_name': COMPANY_SHORT_NAME,
    'accountant_name': ACCOUNTANT_NAME,
    'accountant_title': ACCOUNTANT_TITLE,
    'email_signature': EMAIL_SIGNATURE,
    'website': COMPANY_WEBSITE,
    'phone': COMPANY_PHONE,
}


# ==============================================================================
# 📋 OBLIGATION SETTINGS - Ρυθμίσεις Υποχρεώσεων
# ==============================================================================

# Αυτόματη δημιουργία ClientObligation για νέους πελάτες
# True: Κάθε νέος πελάτης θα έχει αυτόματα ClientObligation
# False: Χειροκίνητη δημιουργία μέσω admin
AUTO_CREATE_CLIENT_OBLIGATION = True

# Default profile που θα αναθέτεται αυτόματα σε νέους πελάτες
# None: Δεν θα αναθέτεται κανένα profile (μόνο θα δημιουργηθεί ClientObligation)
# Όνομα profile: π.χ. "Βασικό" ή "Απλογραφικά"
AUTO_CLIENT_OBLIGATION_PROFILE = None  # Βάλε το όνομα του default profile αν θες


# ==================== CELERY CONFIG ====================
CELERY_BROKER_URL = 'redis://localhost:6379'
CELERY_RESULT_BACKEND = 'redis://localhost:6379'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Europe/Athens'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 min
# ==================== CELERY BEAT - SCHEDULED TASKS ====================

CELERY_BEAT_SCHEDULE = {
    'send-obligation-reminders': {
        'task': 'accounting.tasks.send_obligation_reminders',
        'schedule': crontab(hour=9, minute=0, day_of_week='1-5'),  # 09:00 Mon-Fri
    },
    'send-daily-summary': {
        'task': 'accounting.tasks.send_daily_summary',
        'schedule': crontab(hour=17, minute=0, day_of_week='1-5'),  # 17:00 Mon-Fri
    },
    'process-scheduled-emails': {
        'task': 'accounting.tasks.process_scheduled_emails',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'retry-failed-emails': {
        'task': 'accounting.tasks.retry_failed_emails',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
}

# ==================== SITE CONFIGURATION ====================

# Used for emails and external links
SITE_URL = 'http://127.0.0.1:8000'  # Change for production!

# ==================== IoT DEVICE CONFIGURATION ====================
# SECURITY: IP addresses moved from hardcoded values to environment variables
TASMOTA_IP = os.environ.get('TASMOTA_IP', '192.168.178.27')
TASMOTA_PORT = int(os.environ.get('TASMOTA_PORT', '80'))
TASMOTA_DEVICE_NAME = os.environ.get('TASMOTA_DEVICE_NAME', 'Πόρτα Γραφείου')
# Pulse duration for electric door locks (in seconds)
TASMOTA_DOOR_PULSE_DURATION = float(os.environ.get('TASMOTA_DOOR_PULSE_DURATION', '0.5'))

# ==================== Fritz!Box VoIP Monitor Authentication ====================
# SECURITY: Token for Fritz!Box monitor webhook authentication
FRITZ_API_TOKEN = os.environ.get('FRITZ_API_TOKEN', 'change-this-token-in-production')

# ==============================================================================
# 📦 CACHING CONFIGURATION
# ==============================================================================
# Redis cache for improved performance (uses same Redis as Celery)
REDIS_CACHE_URL = os.environ.get('REDIS_CACHE_URL', 'redis://localhost:6379/1')

# Try to use Redis, fallback to database cache
try:
    import django_redis  # noqa: F401
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_CACHE_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
                'RETRY_ON_TIMEOUT': True,
            },
            'KEY_PREFIX': 'logistikocrm',
        }
    }
    # Use Redis for sessions too (faster)
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
except ImportError:
    # Fallback to database cache if django-redis not installed
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'django_cache_table',
        }
    }

# Cache timeouts (seconds)
CACHE_TTL_SHORT = 60 * 5       # 5 minutes - for frequently changing data
CACHE_TTL_MEDIUM = 60 * 60     # 1 hour - for moderately changing data
CACHE_TTL_LONG = 60 * 60 * 24  # 24 hours - for rarely changing data

# ==============================================================================
# 🔒 PRODUCTION SECURITY SETTINGS
# ==============================================================================
# These settings are automatically applied when DEBUG=False
if not DEBUG:
    from django.core.exceptions import ImproperlyConfigured

    # Require proper SECRET_KEY in production - fail fast instead of running insecure
    if SECRET_KEY == 'default-key-for-development':
        raise ImproperlyConfigured(
            'SECRET_KEY environment variable must be set in production '
            '(DEBUG=False). Refusing to start with the default development key.'
        )

    # Require the Fritz!Box webhook token to be changed from its placeholder
    if FRITZ_API_TOKEN == 'change-this-token-in-production':
        raise ImproperlyConfigured(
            'FRITZ_API_TOKEN environment variable must be set in production '
            '(DEBUG=False). Refusing to start with the placeholder token.'
        )

    # HSTS (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # HTTPS redirect
    SECURE_SSL_REDIRECT = True

    # Secure cookies
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True

    # Security headers
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True

    # CORS - strict origins only in production
    CORS_ALLOW_ALL_ORIGINS = False

# Always enable HttpOnly for session cookies (good practice)
SESSION_COOKIE_HTTPONLY = True

# ==============================================================================
# 📤 FILE UPLOAD SETTINGS
# ==============================================================================
MAX_UPLOAD_SIZE = int(os.environ.get('MAX_UPLOAD_SIZE', 10 * 1024 * 1024))  # 10MB default

# Allowed file extensions for upload
ALLOWED_UPLOAD_EXTENSIONS = [
    '.pdf', '.doc', '.docx', '.xls', '.xlsx',
    '.jpg', '.jpeg', '.png', '.gif',
    '.txt', '.csv', '.zip', '.rar',
]

# Blocked extensions (security)
BLOCKED_UPLOAD_EXTENSIONS = [
    '.exe', '.sh', '.bat', '.cmd', '.com', '.msi',
    '.vbs', '.js', '.jar', '.py', '.php', '.asp',
]