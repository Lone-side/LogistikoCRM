import sys
import os
import warnings
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

# Ανεξάρτητο κλειδί κρυπτογράφησης δεδομένων (Fernet) — δείτε mydata/encryption.py.
# Δημιουργία (standalone, χωρίς Django settings): python scripts/generate_fernet_key.py
# (ή manage.py rotate_encryption_key --generate σε ήδη λειτουργική εγκατάσταση)
DATA_ENCRYPTION_KEY_CURRENT = os.getenv('DATA_ENCRYPTION_KEY_CURRENT', '')
DATA_ENCRYPTION_KEY_PREVIOUS = os.getenv('DATA_ENCRYPTION_KEY_PREVIOUS', '')
DATA_ENCRYPTION_KEY_ID = os.getenv('DATA_ENCRYPTION_KEY_ID', '')

for _key_name in ('DATA_ENCRYPTION_KEY_CURRENT', 'DATA_ENCRYPTION_KEY_PREVIOUS'):
    _key_value = locals()[_key_name]
    if _key_value:
        try:
            from cryptography.fernet import Fernet as _Fernet
            _Fernet(_key_value.encode('utf-8'))
        except Exception as _exc:
            from django.core.exceptions import ImproperlyConfigured
            raise ImproperlyConfigured(
                f"Το {_key_name} δεν είναι έγκυρο Fernet key: {_exc}"
            )

# RBAC: όταν True, οι χρήστες βλέπουν μόνο πελάτες στους οποίους είναι
# ανατεθειμένοι (assigned_users), εκτός από superusers και όσους έχουν
# το permission accounting.view_all_clients.
ENFORCE_CLIENT_ASSIGNMENT = os.getenv('ENFORCE_CLIENT_ASSIGNMENT', 'False').lower() in ('true', '1', 'yes')

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
# Σε development (DEBUG=True) το default είναι console ώστε να μη γίνει
# ποτέ κατά λάθος πραγματική αποστολή SMTP
if os.getenv('EMAIL_BACKEND_CONSOLE', os.getenv('DEBUG', 'False')).lower() in ('true', '1', 'yes'):
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

# ALLOWED_HOSTS - Ρυθμίσεις για τοπικό δίκτυο
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '192.168.*.*',      # Όλα τα τοπικά δίκτυα 192.168.x.x
    '10.*.*.*',         # Εταιρικά δίκτυα 10.x.x.x
    '172.16.*.*',       # Private networks 172.16.x.x
]
# Επιπλέον hosts παραγωγής από env (comma-separated, π.χ. crm.example.gr)
ALLOWED_HOSTS += [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h.strip()]

# CSRF trusted origins για παραγωγή πίσω από HTTPS proxy
# (comma-separated, π.χ. https://crm.example.gr)
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()
]

# Πίσω από reverse proxy (nginx): εμπιστεύσου το X-Forwarded-Proto για HTTPS
if os.environ.get('USE_X_FORWARDED_PROTO', 'False').lower() in ('true', '1', 'yes'):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_X_FORWARDED_HOST = True

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

# Το admin ζει κάτω από το SECRET_ADMIN_PREFIX (μέσα σε i18n_patterns) -
# το reverse_lazy βρίσκει το σωστό URL αντί για το ανύπαρκτο /admin/login/
from django.urls import reverse_lazy
LOGIN_URL = reverse_lazy('admin:login')

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

# ==================== PROTECTED MEDIA ====================
# Σε production (DEBUG=False) τα /media/ σερβίρονται από authenticated view
# με signed tokens (common/views/protected_media.py).
# Διάρκεια ζωής των signed media tokens (?mt=...) σε δευτερόλεπτα
MEDIA_TOKEN_MAX_AGE = int(os.environ.get('MEDIA_TOKEN_MAX_AGE', 4 * 3600))
# Με nginx μπροστά: X-Accel-Redirect στο internal location (μηδενικό φορτίο Django)
MEDIA_ACCEL_REDIRECT = os.environ.get('MEDIA_ACCEL_REDIRECT', 'False').lower() in ('true', '1', 'yes')
MEDIA_ACCEL_PREFIX = os.environ.get('MEDIA_ACCEL_PREFIX', '/protected-media/')

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
# Τα anonymous health endpoints πρέπει να απαντούν και σε plain HTTP όταν
# το SSL redirect είναι ενεργό: το docker healthcheck μιλά απευθείας στο
# gunicorn (http://localhost:8000) πίσω από το nginx, οπότε ένα 301 σε
# https καταλήγει σε TLS handshake πάνω σε plaintext socket και ο
# container μένει μόνιμα unhealthy. Το SecurityMiddleware ταιριάζει τα
# regexes στο request.path χωρίς το αρχικό '/'. Το /api/health/detailed/
# μένει ΕΚΤΟΣ λίστας σκόπιμα (admin-only, περνά πάντα από HTTPS).
HEALTH_CHECK_EXEMPT_URLS = [
    r'^api/health/$',
    r'^api/health/ready/$',
    r'^api/health/live/$',
]
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_PRELOAD = False

# ΜΗΝ το γυρίσεις σε "DENY". Το DENY μπλοκάρει ΚΑΙ same-origin framing, και η
# εφαρμογή προβάλλει PDF μέσα σε <iframe> σε δύο σημεία:
#   frontend/src/components/FilePreviewModal.tsx  (προεπισκόπηση εγγράφου)
#   frontend/src/pages/SharedLinkPortal.tsx       (portal πελάτη)
# Με DENY ο browser αρνείται να αποδώσει και τα δύο — η προεπισκόπηση σπάει
# σιωπηλά. Το SAMEORIGIN είναι η σωστή τιμή εδώ· η σύγχρονη εκδοχή του ίδιου
# ελέγχου είναι το CSP frame-ancestors 'self' (εκκρεμεί, βλ. backlog).
X_FRAME_OPTIONS = "SAMEORIGIN"

# Το Lax είναι ήδη το default του Django· δηλώνεται ρητά ώστε μια μελλοντική
# αλλαγή σε "None" (που απαιτεί Secure και ανοίγει CSRF επιφάνεια) να είναι
# συνειδητή απόφαση και όχι σιωπηλή παράλειψη.
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

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

# Credentials for Google reCAPTCHA (environment-backed, όχι hardcoded).
GOOGLE_RECAPTCHA_SITE_KEY = os.getenv('GOOGLE_RECAPTCHA_SITE_KEY', '')
GOOGLE_RECAPTCHA_SECRET_KEY = os.getenv('GOOGLE_RECAPTCHA_SECRET_KEY', '')

# Τα δύο keys πρέπει να ορίζονται μαζί ή καθόλου — μερική configuration
# σημαίνει είτε ότι το widget δεν θα εμφανίζεται είτε ότι το verification
# δεν θα μπορεί να τρέξει, οπότε αποτυγχάνουμε κλειστά στο startup.
if bool(GOOGLE_RECAPTCHA_SITE_KEY) != bool(GOOGLE_RECAPTCHA_SECRET_KEY):
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured(
        "Μερική reCAPTCHA configuration: τα GOOGLE_RECAPTCHA_SITE_KEY και "
        "GOOGLE_RECAPTCHA_SECRET_KEY πρέπει να είναι είτε και τα δύο "
        "ορισμένα είτε και τα δύο κενά."
    )

# Timeout (seconds) για το verification request προς την Google.
GOOGLE_RECAPTCHA_VERIFY_TIMEOUT = int(
    os.getenv('GOOGLE_RECAPTCHA_VERIFY_TIMEOUT', '5')
)

# Rate limit για τα public intake endpoints (contact_form, add_request)
# ανά client IP και endpoint. Μορφή DRF: "<αριθμός>/<περίοδος>".
PUBLIC_FORM_THROTTLE_RATE = os.getenv('PUBLIC_FORM_THROTTLE_RATE', '30/hour')

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
# Legacy upstream components start daemon threads from AppConfig.ready(), so
# they run in web, Celery, migrations and management commands. Production is
# fail-safe: Celery is the only scheduler unless explicitly overridden.
#
# Resolution (fail-safe + backward compatible):
#   * An explicit LEGACY_APP_THREADS_ENABLED env value always wins.
#   * Otherwise the *final* environment decides: development => threads ON
#     (backward compatible with existing development behaviour), production
#     => threads OFF (single Celery scheduler). The final environment is
#     chosen by webcrm.settings_local._resolve_environment(), which calls
#     _resolve_legacy_threads_enabled() below after import so the flag never
#     lags behind DEBUG.
_LEGACY_ENV_RAW = os.environ.get('LEGACY_APP_THREADS_ENABLED')
if _LEGACY_ENV_RAW is not None:
    LEGACY_APP_THREADS_ENABLED = _LEGACY_ENV_RAW.strip().lower() in ('true', '1', 'yes')
else:
    LEGACY_APP_THREADS_ENABLED = None  # resolved by settings_local

    def _resolve_legacy_threads_enabled():
        from webcrm.settings_local import ENVIRONMENT
        return ENVIRONMENT == 'development'
if TESTING:
    SECURE_SSL_REDIRECT = False
    LANGUAGE_CODE = 'en'
    LANGUAGES = [('en', ''), ('uk', '')]
    # Τα tests ελέγχουν ειδοποιήσεις μέσω mail_admins - χρειάζεται μη κενό ADMINS
    ADMINS = [('Admin', 'admin@example.com')]


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
    # Τα export endpoints διαβάζουν μόνα τους το ?format= (xlsx/pdf/json).
    # Χωρίς αυτό το DRF ερμήνευε το ?format=xlsx ως renderer negotiation
    # και γύριζε 404 πριν καν τρέξει το view (σπασμένα Excel downloads).
    'URL_FORMAT_OVERRIDE': None,
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
        'shared_link_upload': '30/hour',  # Public uploads πελατών μέσω portal (ανά IP)
        'shared_link_auth': '10/hour',    # Δοκιμές κωδικού σε προστατευμένα links (ανά IP)
        # Το login είναι ο κλασικός στόχος credential stuffing. Χωρίς δικό του
        # scope έπεφτε στο γενικό anon (100/hour) — πολύ χαλαρό για endpoint
        # που δοκιμάζει κωδικούς. Το refresh θέλει πιο γενναιόδωρο όριο: είναι
        # αυτόματο και θα γίνει συχνότερο αν κοντύνει το ACCESS_TOKEN_LIFETIME.
        'login': '10/min',                # Προσπάθειες σύνδεσης (ανά IP)
        'token_refresh': '60/min',        # Ανανέωση JWT (ανά IP)
        'credential_reveal': '10/hour',   # Αποκαλύψεις κωδικών πελατών (ανά χρήστη)
        'afm_lookup': '60/hour',          # GSIS ΑΦΜ lookups (ανά χρήστη)
    },
    # Exception handling
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',
}

# Πίσω από reverse proxy: πόσα proxies μεσολαβούν, ώστε το throttling ανά IP
# να χρησιμοποιεί την πραγματική IP από το X-Forwarded-For (π.χ. NUM_PROXIES=1)
if os.environ.get('NUM_PROXIES'):
    REST_FRAMEWORK['NUM_PROXIES'] = int(os.environ['NUM_PROXIES'])

# JWT Settings
from datetime import timedelta
SIMPLE_JWT = {
    # Ήταν 5 ώρες: κλεμμένο access token έμενε χρήσιμο για μισή εργάσιμη.
    # Τα 30 λεπτά μικραίνουν το παράθυρο 10x. Δεν πήγαμε κατευθείαν στα 15'
    # (η συνήθης σύσταση) γιατί κάθε ανανέωση κάνει rotation+blacklist, και
    # θέλουμε μία εβδομάδα παρακολούθησης πριν εικοσαπλασιάσουμε τη συχνότητα.
    # Προϋποθέσεις που μπήκαν μαζί, ΜΗΝ το κοντύνεις χωρίς αυτές:
    #   - ο interceptor κρατά πλέον το rotated refresh token και σειριοποιεί
    #     τα παράλληλα refreshes (frontend/src/api/client.ts)
    #   - beat task 'flush-expired-jwt-tokens' καθαρίζει τους πίνακες
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    # Ξεχωριστό κλειδί υπογραφής, με fallback στο SECRET_KEY ώστε να μη
    # χρειάζεται αλλαγή σε υπάρχουσες εγκαταστάσεις.
    #
    # ΓΙΑΤΙ ΧΩΡΙΣΤΑ: χωρίς αυτό, τα δύο είναι δεμένα και δεν μπορείς να
    # αλλάξεις το ένα χωρίς να χτυπήσεις το άλλο — rotation του SECRET_KEY
    # (π.χ. μετά από διαρροή) πετάει έξω ΟΛΟΥΣ τους συνδεδεμένους, και το
    # SECRET_KEY χρησιμοποιείται επιπλέον σε sessions/CSRF/signing.
    #
    # ΠΡΟΣΟΧΗ όταν το ορίσεις: όλα τα υπάρχοντα tokens ακυρώνονται μία φορά
    # και οι χρήστες ξανασυνδέονται. Κάν' το εκτός ωραρίου.
    'SIGNING_KEY': os.environ.get('JWT_SIGNING_KEY') or SECRET_KEY,
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

# myDATA Configuration (credentials του γραφείου για αποστολή/λήψη παραστατικών)
MYDATA_USER_ID = os.getenv('MYDATA_USER_ID', '')
MYDATA_SUBSCRIPTION_KEY = os.getenv('MYDATA_SUBSCRIPTION_KEY', '')
# ΑΦΜ εκδότη για την αποστολή τιμολογίων (το ΑΦΜ του γραφείου —
# ΔΕΝ είναι το ίδιο με το MYDATA_USER_ID που είναι username της ΑΑΔΕ)
MYDATA_ISSUER_VAT = os.getenv('MYDATA_ISSUER_VAT', '')
# Fail-closed: sandbox (mydataapidev) εκτός αν οριστεί ΡΗΤΑ 'False'/'0'/'no'.
# Κενό, λάθος ή τυπογραφικό στη μεταβλητή = sandbox, ΠΟΤΕ κατά λάθος production.
MYDATA_IS_SANDBOX = os.getenv('MYDATA_IS_SANDBOX', 'true').strip().lower() not in ('false', '0', 'no')


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
# Ο broker/backend διαβάζεται από το περιβάλλον ώστε σε Docker/production
# να δείχνει στο redis service. Προτεραιότητα:
#   CELERY_BROKER_URL -> REDIS_URL -> localhost (development default)
# ΠΡΟΣΟΧΗ: hardcoded 'redis://localhost:6379' σημαίνει ότι σε container ο
# worker δεν βρίσκει ποτέ τον broker (timeouts, tasks δεν εκτελούνται).
_REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', _REDIS_URL)
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', _REDIS_URL)
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
    'ensure-yearly-folders': {
        'task': 'accounting.tasks.ensure_yearly_folders',
        'schedule': crontab(hour=6, minute=0, day_of_month=1, month_of_year=1),  # 1η Ιανουαρίου 06:00
    },
    'backup-database': {
        'task': 'accounting.tasks.backup_database_task',
        # Ήταν ΜΟΝΟ 02:00, δηλαδή RPO έως 24 ώρες: βλάβη δίσκου στις 16:00
        # έχανε ΟΛΗ τη δουλειά της ημέρας — καταχωρήσεις πελατών, ανεβασμένα
        # έγγραφα, υποχρεώσεις. Το restore rehearsal (16/08) έδειξε RTO 3'33",
        # άρα το αδύναμο σημείο ήταν καθαρά το RPO, όχι ο χρόνος επαναφοράς.
        #
        # Τέσσερις φορές την ημέρα, τοποθετημένες γύρω από το ωράριο του
        # γραφείου: μέγιστη απώλεια ~7 ώρες μέσα στην εργάσιμη.
        'schedule': crontab(hour='2,11,15,19', minute=0),
        # Ρητό ιστορικό σε ΜΕΡΕΣ. Χωρίς αυτό η εντολή κρατά τα τελευταία 30
        # ΑΡΧΕΙΑ, οπότε η τετραπλάσια συχνότητα θα κόντυνε το ιστορικό από
        # 30 μέρες σε 7,5 — ακριβώς το αντίθετο από ό,τι θέλουμε.
        'kwargs': {'keep_days': 21},
    },
    'cleanup-stale-sync-logs': {
        'task': 'accounting.tasks.cleanup_stale_sync_logs',
        'schedule': crontab(minute='*/30'),  # Κολλημένα PENDING sync logs
    },
    'update-overdue-obligations': {
        'task': 'accounting.tasks.update_overdue_obligations',
        'schedule': crontab(hour=0, minute=15),  # Καθημερινά 00:15
    },
    'send-document-request-reminders': {
        'task': 'accounting.tasks.send_document_request_reminders',
        'schedule': crontab(hour=10, minute=0, day_of_week='1-5'),  # 10:00 Δευ-Παρ
    },
    'flush-expired-jwt-tokens': {
        'task': 'accounting.tasks.flush_expired_jwt_tokens',
        # Με rotation+blacklist κάθε ανανέωση token αφήνει δύο σειρές που δεν
        # σβήνονται μόνες τους. Χωρίς αυτό οι πίνακες μεγαλώνουν για πάντα.
        'schedule': crontab(hour=3, minute=30),  # Καθημερινά 03:30
    },
}

# ==================== SITE CONFIGURATION ====================

# Used for emails and external links
SITE_URL = os.environ.get('SITE_URL', 'http://127.0.0.1:8000')

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
# Localhost fallback για το VoIP service API (χωρίς X-API-Key). Πίσω από
# reverse proxy το REMOTE_ADDR μπορεί να φαίνεται loopback για εξωτερικά
# requests, οπότε σε production μένει κλειστό (default: DEBUG).
VOIP_ALLOW_LOCALHOST = os.environ.get(
    'VOIP_ALLOW_LOCALHOST', 'true' if DEBUG else 'false'
).lower() in ('true', '1', 'yes')

# ==============================================================================
# 📦 CACHING CONFIGURATION
# ==============================================================================
# Redis cache for improved performance (uses same Redis as Celery)
#
# Η επιλογή backend γίνεται από το ΠΕΡΙΒΑΛΛΟΝ, ΟΧΙ από την παρουσία του
# πακέτου: παλιότερα ένα σκέτο `import django_redis` αρκούσε για να στραφεί
# το cache (και τα sessions) σε Redis — ακόμη και σε μηχάνημα χωρίς Redis,
# όπου κάθε cache/session λειτουργία απλώς αποτύγχανε.
# Τώρα: Redis μόνο όταν έχει οριστεί ρητά REDIS_CACHE_URL (Docker/production).
# Αλλιώς database cache, που δουλεύει παντού (dev, CI, χωρίς Redis).
REDIS_CACHE_URL = os.environ.get('REDIS_CACHE_URL', '')

# Στα tests ΠΟΤΕ Redis: ο TestCase κάνει rollback τη βάση αλλά ΟΧΙ το Redis,
# οπότε cache/session/throttle counters θα διέρρεαν μεταξύ tests και θα
# έκαναν order-dependent flaky ό,τι βασίζεται σε cache (π.χ. DRF throttling).
_use_redis_cache = bool(REDIS_CACHE_URL) and not TESTING
if _use_redis_cache:
    try:
        import django_redis  # noqa: F401
    except ImportError:
        _use_redis_cache = False
        warnings.warn(
            'REDIS_CACHE_URL έχει οριστεί αλλά το django-redis δεν είναι '
            'εγκατεστημένο — fallback σε database cache. Εγκατέστησε το '
            'django-redis (βλ. requirements.txt).',
            RuntimeWarning,
        )

if _use_redis_cache:
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
else:
    # Database cache: δουλεύει χωρίς Redis. Απαιτεί `manage.py
    # createcachetable` — εκτελείται στο startup του production compose.
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
    # Σε πραγματική παραγωγή (όχι test runs) τα default secrets είναι fatal:
    # το SECRET_KEY προστατεύει sessions/CSRF ΚΑΙ την κρυπτογράφηση των
    # myDATA credentials (Fernet key από SHA-256(SECRET_KEY)), και το
    # FRITZ_API_TOKEN είναι το μοναδικό credential του Fritz webhook.
    import sys
    _RUNNING_TESTS = 'test' in sys.argv or 'pytest' in sys.modules
    if not _RUNNING_TESTS:
        from django.core.exceptions import ImproperlyConfigured
        if SECRET_KEY == 'default-key-for-development':
            raise ImproperlyConfigured(
                'Refusing to start with the default SECRET_KEY and DEBUG=False. '
                'Set the SECRET_KEY environment variable.'
            )
        if FRITZ_API_TOKEN == 'change-this-token-in-production':
            raise ImproperlyConfigured(
                'Refusing to start with the default FRITZ_API_TOKEN and DEBUG=False. '
                'Set the FRITZ_API_TOKEN environment variable to a long random value '
                '(e.g. `openssl rand -hex 32`), even if the Fritz monitor is unused.'
            )
        if not DATA_ENCRYPTION_KEY_CURRENT:
            raise ImproperlyConfigured(
                'DATA_ENCRYPTION_KEY_CURRENT is required in production — '
                'χωρίς αυτό τα credentials κρυπτογραφούνται με το legacy '
                'κλειδί από το SECRET_KEY. Δημιουργία (χωρίς να χρειάζεται '
                'να εκκινεί το Django): `python scripts/generate_fernet_key.py`.'
            )
        if not ENFORCE_CLIENT_ASSIGNMENT and os.getenv(
            'ALLOW_UNSCOPED_CLIENT_ACCESS', 'False'
        ).lower() not in ('true', '1', 'yes'):
            raise ImproperlyConfigured(
                'ENFORCE_CLIENT_ASSIGNMENT must be enabled in production. '
                'Αν το CRM χρησιμοποιείται μόνο από superuser και θέλετε '
                'συνειδητά RBAC off, ορίστε ALLOW_UNSCOPED_CLIENT_ACCESS=True.'
            )

    # HSTS (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # HTTPS redirect — πάντα ενεργό σε production. Στο CI security-smoke
    # (DJANGO_ENV=production) μένει ενεργό ΚΑΙ στο test runner: τα RBAC smoke
    # tests στέλνουν secure=True requests ώστε να ελέγχουν τα πραγματικά
    # status codes χωρίς να απενεργοποιείται το redirect. Στο απλό CI test
    # job (DEBUG=False χωρίς DJANGO_ENV=production) η υπόλοιπη σουίτα μιλάει
    # http, οπότε εκεί μόνο ισχύει η εξαίρεση του TESTING.
    if os.getenv('DJANGO_ENV', '').lower() == 'production':
        SECURE_SSL_REDIRECT = True
    else:
        SECURE_SSL_REDIRECT = not TESTING

    # Εξαίρεση από το SSL redirect ΜΟΝΟ για τα anonymous health endpoints
    # (βλ. HEALTH_CHECK_EXEMPT_URLS παραπάνω): αλλιώς το container
    # healthcheck του docker-compose.prod.yml αποτυγχάνει μόνιμα σε
    # DJANGO_ENV=production.
    SECURE_REDIRECT_EXEMPT = HEALTH_CHECK_EXEMPT_URLS

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