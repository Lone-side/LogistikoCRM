"""
Local/Production Settings Override
"""
from .settings import *
import os
import sys

from django.core.exceptions import ImproperlyConfigured

_VALID_ENVIRONMENTS = ('production', 'development')


def _resolve_environment():
    """
    Επιλέγει development/production **fail closed**.

    Ιστορικό: παλιότερα ήταν `os.getenv('DJANGO_ENV', 'development')`, οπότε
    απών ή λάθος γραμμένο DJANGO_ENV σήμαινε σιωπηλά development — δηλαδή
    DEBUG=True, ALLOWED_HOSTS=['*'] και **δημόσια /media/** (το urls.py
    διαλέγει `static()` αντί για το authenticated `serve_protected_media`
    με βάση το DEBUG). Το `DEBUG=False` δεν βοηθούσε: το development
    branch το έγραφε από πάνω.

    Κανόνες:

    - Ρητό `production` / `development` (case-insensitive, με trim): ισχύει
      — ΕΚΤΟΣ αν το ρητό DEBUG το αντιφάσκει (βλ. παρακάτω).
    - `production` με ρητά truthy DEBUG: ImproperlyConfigured. Το
      settings.py έχει ήδη παραλείψει το production security block.
    - `development` με ρητά falsey DEBUG: ImproperlyConfigured. Το
      settings.py έτρεξε production guards για ένα dev περιβάλλον.
    - Ρητό αλλά άγνωστο (`prod`, `prodction`, κενό): ImproperlyConfigured.
      Ένα typo ΔΕΝ επιτρέπεται να μεταφράζεται σε «development».
    - Απόν, αλλά τρέχει ο test runner: development. Τα tests πρέπει να
      δουλεύουν χωρίς env setup. Η εξαίρεση αφορά ΜΟΝΟ πραγματικό test
      invocation και ΜΟΝΟ την απουσία DJANGO_ENV — ρητή αντίφαση σκάει
      και στα tests. Το security-smoke CI job ορίζει ρητά production,
      οπότε η production διαδρομή παραμένει καλυμμένη.
    - Απόν, με ρητό `DEBUG=True`: development. Σαφής δήλωση πρόθεσης για
      τοπικό `runserver` χωρίς πλήρες .env.
    - Οτιδήποτε άλλο (συμπεριλαμβανομένου του `DEBUG=False` σκέτο):
      ImproperlyConfigured. Ποτέ σιωπηλή μετάπτωση σε development.
    """
    raw = os.environ.get('DJANGO_ENV')
    # Το DEBUG διαβάζεται ΜΕΤΑ το load_dotenv() του settings.py (τρέχει στο
    # `from .settings import *` παραπάνω), δηλαδή είναι η ΙΔΙΑ τιμή που
    # κατανάλωσε το settings.py — ό,τι ήρθε από .env μετράει ως ρητό.
    debug_raw = os.environ.get('DEBUG')

    if raw is not None:
        value = raw.strip().lower()
        if value not in _VALID_ENVIRONMENTS:
            raise ImproperlyConfigured(
                f'Άγνωστο DJANGO_ENV={raw!r}. Επιτρέπονται μόνο '
                f'DJANGO_ENV=production ή DJANGO_ENV=development. '
                f'Ένα typo δεν γίνεται σιωπηλά development — βλ. DEPLOYMENT.md.'
            )

        # Αντιφατικοί συνδυασμοί DJANGO_ENV/DEBUG: fail closed.
        #
        # Το settings.py εισάγεται ΠΡΩΤΟ και παίρνει τις αποφάσεις
        # ασφαλείας από το DEBUG env var τη στιγμή του import. Εδώ μπορεί
        # να αλλάξει μόνο το τελικό flag — ο κώδικας που το settings.py
        # παρέλειψε ή εκτέλεσε ΔΕΝ ξανατρέχει. Άρα:
        #
        # - production + truthy DEBUG: το settings.py παρέλειψε ολόκληρο
        #   το production security block (HSTS, SSL redirect, secure
        #   cookies, fail-closed guards). Αν απλώς γυρίζαμε το DEBUG σε
        #   False, θα προέκυπτε μερικώς φορτωμένη production διαμόρφωση
        #   που μοιάζει ασφαλής. Μετρημένο: DEBUG=False με SSL_REDIRECT=
        #   False, SESSION_SECURE=False, HSTS=0.
        # - development + falsey DEBUG: το settings.py έτρεξε guards και
        #   security για παραγωγή, ενώ το development branch θα επέβαλλε
        #   DEBUG=True από πάνω — ασυνεπές μείγμα χωρίς νόημα.
        if debug_raw is not None:
            debug_truthy = debug_raw.strip().lower() in ('true', '1', 'yes')
            if value == 'production' and debug_truthy:
                raise ImproperlyConfigured(
                    f'Αντίφαση: DJANGO_ENV=production με DEBUG={debug_raw!r}. '
                    f'Το settings.py διάβασε ήδη το DEBUG κατά το import και '
                    f'παρέλειψε το production security block (HSTS, SSL '
                    f'redirect, secure cookies, fail-closed guards) — αυτός ο '
                    f'κώδικας δεν ξανατρέχει. Σε production το DEBUG πρέπει '
                    f'να είναι απόν ή False (έλεγξε και το .env — το '
                    f'load_dotenv μετράει ως ρητή τιμή).'
                )
            if value == 'development' and not debug_truthy:
                raise ImproperlyConfigured(
                    f'Αντίφαση: DJANGO_ENV=development με DEBUG={debug_raw!r}. '
                    f'Με falsey DEBUG το settings.py έτρεξε production guards '
                    f'και security κατά το import, ενώ το development branch '
                    f'θα επέβαλλε DEBUG=True από πάνω. Σε development το '
                    f'DEBUG πρέπει να είναι απόν ή True.'
                )
        return value

    # Test runner: `manage.py test` ή pytest.
    if sys.argv[1:2] == ['test'] or 'pytest' in os.path.basename(sys.argv[0]):
        return 'development'

    if os.environ.get('DEBUG', '').strip().lower() in ('true', '1', 'yes'):
        return 'development'

    raise ImproperlyConfigured(
        'Λείπει το DJANGO_ENV. Όρισε DJANGO_ENV=production σε παραγωγή ή '
        'DJANGO_ENV=development τοπικά.\n'
        'Το DEBUG=False ΔΕΝ αρκεί: το settings_local διαλέγει περιβάλλον '
        'μόνο από το DJANGO_ENV, και παλιότερα η απουσία του κατέληγε '
        'σιωπηλά σε DEBUG=True με δημόσια /media/. Γι΄ αυτό πλέον '
        'αποτυγχάνει κλειστά αντί να μαντεύει. Βλ. DEPLOYMENT.md.'
    )


ENVIRONMENT = _resolve_environment()

# Resolve the legacy AppConfig daemon-thread flag from the *final* environment
# so it never lags behind the DEBUG value that webcrm.settings read at import
# time. An explicit LEGACY_APP_THREADS_ENABLED env value already won and is
# left untouched. When unset: development => threads ON (backward compatible),
# production => OFF (Celery is the sole scheduler).
import webcrm.settings as _base_settings
if _base_settings.LEGACY_APP_THREADS_ENABLED is None:
    _base_settings.LEGACY_APP_THREADS_ENABLED = \
        _base_settings._resolve_legacy_threads_enabled()

if ENVIRONMENT == 'production':
    DEBUG = False
    # Πρόσθεσε τις IPs που χρειάζεσαι
    ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

    # Security για production
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'SAMEORIGIN'

    # Session security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_AGE = 86400  # 24 hours

else:  # development
    DEBUG = True
    # Δέχεται όλες τις IPs για εύκολο local development
    ALLOWED_HOSTS = ['*']

    # Χωρίς .env το settings.py υπολογίζει DEBUG=False κατά το import και
    # ενεργοποιεί το production security block (SSL redirect, secure cookies,
    # HSTS) - απενεργοποίηση εδώ ώστε ο runserver να είναι πλοηγήσιμος
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

# Αυτόματη ανίχνευση τοπικής IP για CSRF
def get_local_ip():
    """Βρίσκει την τοπική IP του server"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

LOCAL_IP = get_local_ip()

# CSRF για local network - αυτόματη ρύθμιση
CSRF_TRUSTED_ORIGINS = [
    f'http://{LOCAL_IP}:8000',
    f'http://{LOCAL_IP}:3000',
    'http://localhost:8000',
    'http://localhost:3000',
    'http://127.0.0.1:8000',
    'http://127.0.0.1:3000',
]

# Improved Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs/django.log',
            'maxBytes': 1024 * 1024 * 5,  # 5MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'] if DEBUG else ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'accounting': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# Create logs directory if not exists
import os
os.makedirs(BASE_DIR / 'logs', exist_ok=True)