# -*- coding: utf-8 -*-
"""
Office/LAN operational preflight — read-only έλεγχοι ετοιμότητας.

Τρέχει μέσα στο web container (docker compose ... exec web python
manage.py office_preflight) ή μέσω του wrapper scripts/office_preflight.sh
που προσθέτει και τους host-level ελέγχους (container health, TLS).

Read-only by design: ΚΑΝΕΝΑ write πουθενά (ούτε tempfiles) — μόνο
os.access, ORM reads, in-process health checks και ένα loopback HTTP GET.
Στο output εμφανίζονται ΜΟΝΟ ονόματα ελέγχων/μετρήσεις — ποτέ τιμές
secrets, ΑΦΜ ή ονόματα πελατών.

ΠΡΟΣΟΧΗ (settings split): το manage.py φορτώνει webcrm.settings_local,
ενώ gunicorn/celery το webcrm.settings. Για ALLOWED_HOSTS και
CSRF_TRUSTED_ORIGINS ο έλεγχος διαβάζει το os.environ — αυτό βλέπει το
served app — όχι το (ξαναγραμμένο από το settings_local) setting.

Χρήση σε gates: --fail-on-findings → exit code != 0 (CommandError),
ίδιο συμβόλαιο με τα audit_* commands.
"""
import os
import time
import urllib.error
import urllib.request

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.migrations.executor import MigrationExecutor

from accounting.management.commands.backup_database import (
    BACKUP_PREFIX,
    default_backup_dir,
)
from common.api_health import (
    UNHEALTHY_COMPONENT_STATUSES,
    check_cache,
    check_celery,
    check_database,
    check_disk_space,
)

REQUIRED_ROLE_GROUPS = ('Διαχειριστής', 'Λογιστής', 'Βοηθός')

LOCAL_HEALTH_URL = 'http://localhost:8000/api/health/'


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def probe_local_health(url=LOCAL_HEALTH_URL, timeout=5):
    """
    GET στο gunicorn ΧΩΡΙΣ redirect follow.
    Επιστρέφει ('ok', status) / ('redirect', status) / ('error', status)
    / ('unreachable', λόγος).
    """
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(url, timeout=timeout) as response:
            return ('ok', response.status)
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 307, 308):
            return ('redirect', e.code)
        return ('error', e.code)
    except (urllib.error.URLError, OSError) as e:
        return ('unreachable', str(getattr(e, 'reason', e)))


def _env_truthy(name):
    return os.environ.get(name, '').strip().lower() in ('true', '1', 'yes')


class Command(BaseCommand):
    help = ('Read-only preflight έλεγχοι για office/LAN λειτουργία '
            '(--fail-on-findings για gates)')

    def add_arguments(self, parser):
        parser.add_argument(
            '--fail-on-findings', action='store_true',
            help='Exit με σφάλμα αν υπάρχει οποιοδήποτε FAIL',
        )
        parser.add_argument(
            '--max-backup-age-hours', type=int, default=26,
            help='Μέγιστη αποδεκτή ηλικία τελευταίου backup (default 26 — '
                 'το beat τρέχει καθημερινά 02:00)',
        )

    def handle(self, *args, **options):
        self.results = []

        self._check_production_mode()
        self._check_allowed_hosts_env()
        self._check_csrf_origins_env()
        self._check_forwarded_proto_env()
        self._check_secrets()
        self._check_component('database', check_database)
        self._check_component('cache', check_cache)
        self._check_celery()
        self._check_disk()
        self._check_migrations()
        self._check_writable_paths()
        self._check_rbac()
        self._check_backup_age(options['max_backup_age_hours'])
        self._check_mydata_sandbox()
        self._check_mydata_client_credentials()
        self._check_local_health_endpoint()

        fails = [r for r in self.results if r[0] == 'FAIL']
        warns = [r for r in self.results if r[0] == 'WARN']
        self.stdout.write('')
        self.stdout.write(
            f'Σύνολο: {len(self.results)} έλεγχοι — '
            f'{len(fails)} FAIL, {len(warns)} WARN'
        )
        if fails and options['fail_on_findings']:
            raise CommandError(
                f'{len(fails)} preflight έλεγχοι απέτυχαν — δείτε παραπάνω.'
            )

    # ---- helpers ----

    def _report(self, level, check, message):
        self.results.append((level, check, message))
        style = {'OK': self.style.SUCCESS,
                 'WARN': self.style.WARNING,
                 'FAIL': self.style.ERROR}[level]
        self.stdout.write(f'{style(f"[{level}]"):<18} {check}: {message}')

    # ---- checks ----

    def _check_production_mode(self):
        env = os.environ.get('DJANGO_ENV', '').strip().lower()
        if settings.DEBUG:
            self._report('FAIL', 'production-mode', 'DEBUG είναι True')
        elif env != 'production':
            self._report('FAIL', 'production-mode',
                         f'DJANGO_ENV={env or "(κενό)"} — απαιτείται '
                         '"production" (το gunicorn/celery αποφασίζει '
                         'security από αυτό)')
        else:
            self._report('OK', 'production-mode',
                         'DEBUG=False, DJANGO_ENV=production')

    def _check_allowed_hosts_env(self):
        raw = os.environ.get('ALLOWED_HOSTS', '')
        hosts = [h.strip() for h in raw.split(',') if h.strip()]
        if not hosts:
            self._report('FAIL', 'allowed-hosts',
                         'κενό ALLOWED_HOSTS env — το settings_local '
                         'θα δεχτεί μόνο localhost')
        elif any(h == '*' for h in hosts):
            self._report('FAIL', 'allowed-hosts', "περιέχει '*'")
        else:
            self._report('OK', 'allowed-hosts', f'{len(hosts)} entries')

    def _check_csrf_origins_env(self):
        raw = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
        origins = [o.strip() for o in raw.split(',') if o.strip()]
        if not origins:
            self._report('FAIL', 'csrf-origins',
                         'κενό CSRF_TRUSTED_ORIGINS env (τα HTTPS POST '
                         'θα απορρίπτονται)')
        elif any(not o.startswith('https://') for o in origins):
            self._report('FAIL', 'csrf-origins',
                         'υπάρχουν μη-https origins')
        else:
            self._report('OK', 'csrf-origins', f'{len(origins)} origins')

    def _check_forwarded_proto_env(self):
        if _env_truthy('USE_X_FORWARDED_PROTO'):
            self._report('OK', 'x-forwarded-proto', 'ενεργό')
        else:
            self._report('FAIL', 'x-forwarded-proto',
                         'ανενεργό — πίσω από το TLS nginx προκαλεί '
                         'redirect loop')

    def _check_secrets(self):
        if settings.SECRET_KEY == 'default-key-for-development':
            self._report('FAIL', 'secret-key', 'default τιμή')
        elif len(settings.SECRET_KEY) < 50:
            self._report('FAIL', 'secret-key', 'μικρότερο από 50 χαρακτήρες')
        else:
            self._report('OK', 'secret-key', 'ορισμένο')

        if getattr(settings, 'FRITZ_API_TOKEN', '') in (
                '', 'change-this-token-in-production'):
            self._report('FAIL', 'fritz-token', 'default/κενή τιμή')
        else:
            self._report('OK', 'fritz-token', 'ορισμένο')

        key = getattr(settings, 'DATA_ENCRYPTION_KEY_CURRENT', '')
        if not key:
            self._report('FAIL', 'encryption-key',
                         'DATA_ENCRYPTION_KEY_CURRENT απόν')
        else:
            try:
                Fernet(key.encode() if isinstance(key, str) else key)
                self._report('OK', 'encryption-key', 'έγκυρο Fernet key')
            except Exception:
                self._report('FAIL', 'encryption-key', 'μη έγκυρο Fernet key')

    def _check_component(self, name, func):
        try:
            status = func().get('status')
        except Exception as e:
            self._report('FAIL', name, f'έλεγχος απέτυχε: {e.__class__.__name__}')
            return
        if status in UNHEALTHY_COMPONENT_STATUSES:
            self._report('FAIL', name, f'status={status}')
        elif status != 'healthy':
            self._report('WARN', name, f'status={status}')
        else:
            self._report('OK', name, 'healthy')

    def _check_celery(self):
        try:
            result = check_celery()
        except Exception as e:
            self._report('FAIL', 'celery', f'έλεγχος απέτυχε: {e.__class__.__name__}')
            return
        status = result.get('status')
        if status in UNHEALTHY_COMPONENT_STATUSES:
            self._report('FAIL', 'celery', f'status={status}')
        elif status != 'healthy':
            self._report('WARN', 'celery',
                         f'status={status} (workers={result.get("workers")})')
        else:
            self._report('OK', 'celery', f'workers={result.get("workers")}')

    def _check_disk(self):
        try:
            result = check_disk_space()
        except Exception as e:
            self._report('FAIL', 'disk', f'έλεγχος απέτυχε: {e.__class__.__name__}')
            return
        status = result.get('status')
        used = result.get('used_percent')
        if status == 'critical':
            self._report('FAIL', 'disk', f'{used}% σε χρήση (critical)')
        elif status != 'healthy':
            self._report('WARN', 'disk', f'{used}% σε χρήση ({status})')
        else:
            self._report('OK', 'disk', f'{used}% σε χρήση')

    def _check_migrations(self):
        try:
            executor = MigrationExecutor(connections['default'])
            plan = executor.migration_plan(
                executor.loader.graph.leaf_nodes())
        except Exception as e:
            self._report('FAIL', 'migrations',
                         f'έλεγχος απέτυχε: {e.__class__.__name__}')
            return
        if plan:
            self._report('FAIL', 'migrations',
                         f'{len(plan)} pending migrations')
        else:
            self._report('OK', 'migrations', 'καμία εκκρεμής')

    def _check_writable_paths(self):
        paths = {
            'media': settings.MEDIA_ROOT,
            'backups': default_backup_dir(),
            'logs': os.path.join(settings.BASE_DIR, 'logs'),
        }
        for name, path in paths.items():
            if not os.path.isdir(path):
                self._report('FAIL', f'writable-{name}',
                             'ο φάκελος δεν υπάρχει')
            elif not os.access(path, os.W_OK):
                self._report('FAIL', f'writable-{name}', 'όχι εγγράψιμος')
            else:
                self._report('OK', f'writable-{name}', 'εγγράψιμος')

    def _check_rbac(self):
        existing = set(
            Group.objects.filter(
                name__in=REQUIRED_ROLE_GROUPS).values_list('name', flat=True)
        )
        missing = [g for g in REQUIRED_ROLE_GROUPS if g not in existing]
        if missing:
            self._report('FAIL', 'rbac-groups',
                         f'λείπουν: {", ".join(missing)} '
                         '(τρέξτε: manage.py setup_roles)')
        else:
            self._report('OK', 'rbac-groups', 'και τα 3 role groups υπάρχουν')

        if get_user_model().objects.filter(is_superuser=True).exists():
            self._report('OK', 'superuser', 'υπάρχει')
        else:
            self._report('WARN', 'superuser',
                         'κανένας superuser (τρέξτε: manage.py setupdata)')

    def _check_backup_age(self, max_age_hours):
        backup_dir = default_backup_dir()
        try:
            backups = sorted(
                backup_dir.glob(f'{BACKUP_PREFIX}*'),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            backups = []
        if not backups:
            self._report('WARN', 'backup-age',
                         'κανένα backup ακόμη (το beat τρέχει 02:00 — ή '
                         'χειροκίνητα: manage.py backup_database)')
            return
        age_hours = (time.time() - backups[0].stat().st_mtime) / 3600
        if age_hours > max_age_hours:
            self._report('FAIL', 'backup-age',
                         f'τελευταίο backup πριν {age_hours:.1f} ώρες '
                         f'(όριο {max_age_hours})')
        else:
            self._report('OK', 'backup-age',
                         f'τελευταίο πριν {age_hours:.1f} ώρες')

    def _check_mydata_sandbox(self):
        if getattr(settings, 'MYDATA_IS_SANDBOX', True):
            self._report('OK', 'mydata-sandbox', 'sandbox ενεργό')
        else:
            self._report('FAIL', 'mydata-sandbox',
                         'MYDATA_IS_SANDBOX=False — η office εγκατάσταση '
                         'επιτρέπεται ΜΟΝΟ σε sandbox')

    def _check_mydata_client_credentials(self):
        try:
            from mydata.models import MyDataCredentials
        except Exception:
            self._report('OK', 'mydata-client-creds', 'μη διαθέσιμο app')
            return
        production = MyDataCredentials.objects.filter(is_sandbox=False)
        active = production.filter(is_active=True).count()
        inactive = production.filter(is_active=False).count()
        if active:
            # Fail-closed: ενεργά production credentials σημαίνουν ότι το
            # sync μπορεί να μιλήσει στο πραγματικό myDATA — απαγορευμένο
            # στην office εγκατάσταση (sandbox-only gate).
            self._report('FAIL', 'mydata-client-creds',
                         f'{active} ΕΝΕΡΓΑ πελατ. credentials σε ΠΑΡΑΓΩΓΗ '
                         '(is_sandbox=False, is_active=True) — '
                         'απενεργοποιήστε τα ή γυρίστε τα σε sandbox')
        elif inactive:
            self._report('WARN', 'mydata-client-creds',
                         f'{inactive} ανενεργά πελατ. credentials σε '
                         'παραγωγή (is_sandbox=False — το default του '
                         'πεδίου είναι παραγωγή, ελέγξτε τα πριν την '
                         'ενεργοποίηση)')
        else:
            self._report('OK', 'mydata-client-creds',
                         'κανένα production credential')

    def _check_local_health_endpoint(self):
        state, detail = probe_local_health()
        if state == 'ok' and detail == 200:
            self._report('OK', 'local-health', 'HTTP 200 χωρίς redirect')
        elif state == 'redirect':
            self._report('FAIL', 'local-health',
                         f'HTTP {detail} redirect — regression του '
                         'SECURE_REDIRECT_EXEMPT (το container healthcheck '
                         'θα αποτυγχάνει)')
        elif state == 'unreachable':
            self._report('WARN', 'local-health',
                         'gunicorn μη προσβάσιμο στο localhost:8000 — '
                         'τρέχετε εκτός web container;')
        else:
            self._report('FAIL', 'local-health', f'HTTP {detail}')
