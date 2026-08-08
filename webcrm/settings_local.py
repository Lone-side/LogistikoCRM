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

    - Ρητό `production` / `development` (case-insensitive, με trim): ισχύει.
    - Ρητό αλλά άγνωστο (`prod`, `prodction`, κενό): ImproperlyConfigured.
      Ένα typo ΔΕΝ επιτρέπεται να μεταφράζεται σε «development».
    - Απόν, αλλά τρέχει ο test runner: development. Τα tests πρέπει να
      δουλεύουν χωρίς env setup, και ήδη τρέχουν έτσι (το CI test job
      ορίζει DEBUG=False χωρίς DJANGO_ENV). Το security-smoke job ορίζει
      ρητά production, οπότε η production διαδρομή παραμένει καλυμμένη.
    - Απόν, με ρητό `DEBUG=True`: development. Σαφής δήλωση πρόθεσης για
      τοπικό `runserver` χωρίς πλήρες .env.
    - Οτιδήποτε άλλο (συμπεριλαμβανομένου του `DEBUG=False` σκέτο):
      ImproperlyConfigured. Ποτέ σιωπηλή μετάπτωση σε development.
    """
    raw = os.environ.get('DJANGO_ENV')

    if raw is not None:
        value = raw.strip().lower()
        if value in _VALID_ENVIRONMENTS:
            return value
        raise ImproperlyConfigured(
            f'Άγνωστο DJANGO_ENV={raw!r}. Επιτρέπονται μόνο '
            f'DJANGO_ENV=production ή DJANGO_ENV=development. '
            f'Ένα typo δεν γίνεται σιωπηλά development — βλ. DEPLOYMENT.md.'
        )

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