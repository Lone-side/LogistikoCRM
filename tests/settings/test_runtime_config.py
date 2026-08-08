# -*- coding: utf-8 -*-
"""
Regression tests για τη runtime configuration παραγωγής.

Καλύπτει τρία επιβεβαιωμένα ευρήματα:

1. Το Celery είχε hardcoded `redis://localhost:6379` και αγνοούσε το
   `REDIS_URL` του Docker → ο worker δεν έβρισκε ποτέ τον broker μέσα σε
   container (timeouts· reminders, scheduled emails, OCR και το ημερήσιο
   backup δεν εκτελούνταν).

2. Το cache επέλεγε Redis με βάση την ΠΑΡΟΥΣΙΑ του πακέτου
   (`import django_redis`), όχι το περιβάλλον — άρα σε μηχάνημα με
   εγκατεστημένο django-redis αλλά χωρίς Redis, cache και sessions
   αποτύγχαναν σιωπηλά.

3. Το production compose δεν όριζε `DJANGO_ENV`, ενώ το manage.py φορτώνει
   `webcrm.settings_local` → τα management commands (και το `migrate` του
   startup) έτρεχαν σε development mode.

Τα tests διαβάζουν το ΠΡΑΓΜΑΤΙΚΟ settings module σε απομονωμένο
περιβάλλον, χωρίς να αγγίζουν τα ενεργά settings της διεργασίας.
"""
import importlib
import os
import sys
from pathlib import Path
from unittest import mock

import yaml
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _load_settings(env, as_test_run=True):
    """
    Φορτώνει καθαρά το webcrm.settings με το δοσμένο environment.
    Επιστρέφει το module. Δεν επηρεάζει τα settings της τρέχουσας
    διεργασίας (γίνεται restore του sys.modules entry).

    as_test_run=False προσομοιώνει εκτέλεση εκτός `manage.py test`
    (δηλαδή production), ώστε να ελέγχεται το Redis branch — στα tests
    το Redis cache απενεργοποιείται σκόπιμα (βλ. settings).
    """
    saved = sys.modules.pop('webcrm.settings', None)
    argv_patch = mock.patch.object(
        sys, 'argv', sys.argv if as_test_run else ['gunicorn'])
    argv_patch.start()
    full_env = {
        # ελάχιστο valid περιβάλλον ώστε να μη σκάσουν τα prod guards
        'SECRET_KEY': 'x' * 60,
        'DEBUG': 'True',
        **env,
    }
    try:
        with mock.patch.dict(os.environ, full_env, clear=False):
            # τα κλειδιά που θέλουμε ρητά απόντα
            for key in ('REDIS_URL', 'REDIS_CACHE_URL',
                        'CELERY_BROKER_URL', 'CELERY_RESULT_BACKEND'):
                if key not in full_env:
                    os.environ.pop(key, None)
            return importlib.import_module('webcrm.settings')
    finally:
        argv_patch.stop()
        sys.modules.pop('webcrm.settings', None)
        if saved is not None:
            sys.modules['webcrm.settings'] = saved


class CeleryBrokerFromEnvTest(SimpleTestCase):
    """Εύρημα 1: ο broker πρέπει να διαβάζεται από το περιβάλλον."""

    def test_celery_broker_is_not_hardcoded(self):
        """Το REDIS_URL του Docker πρέπει να γίνεται σεβαστό."""
        s = _load_settings({'REDIS_URL': 'redis://redis:6379/0'})
        self.assertEqual(s.CELERY_BROKER_URL, 'redis://redis:6379/0')
        self.assertEqual(s.CELERY_RESULT_BACKEND, 'redis://redis:6379/0')

    def test_explicit_celery_broker_url_wins(self):
        """Ρητό CELERY_BROKER_URL υπερισχύει του REDIS_URL."""
        s = _load_settings({
            'REDIS_URL': 'redis://redis:6379/0',
            'CELERY_BROKER_URL': 'redis://other:6380/3',
        })
        self.assertEqual(s.CELERY_BROKER_URL, 'redis://other:6380/3')

    def test_development_default_is_localhost(self):
        """Χωρίς env, το development default παραμένει localhost."""
        s = _load_settings({})
        self.assertIn('localhost', s.CELERY_BROKER_URL)


class CacheBackendSelectionTest(SimpleTestCase):
    """Εύρημα 2: η επιλογή backend εξαρτάται από το ΠΕΡΙΒΑΛΛΟΝ."""

    def test_no_redis_url_uses_database_cache(self):
        """
        Χωρίς REDIS_CACHE_URL → database cache, ΑΚΟΜΗ ΚΑΙ αν το
        django-redis είναι εγκατεστημένο (dev/CI χωρίς Redis).
        """
        s = _load_settings({})
        self.assertEqual(
            s.CACHES['default']['BACKEND'],
            'django.core.cache.backends.db.DatabaseCache',
        )
        # δεν πρέπει να μεταφέρει τα sessions σε cache που δεν υπάρχει
        self.assertNotEqual(
            getattr(s, 'SESSION_ENGINE', ''),
            'django.contrib.sessions.backends.cache',
        )

    def test_redis_url_selects_redis_cache_in_production(self):
        """Με REDIS_CACHE_URL (εκτός test run) → Redis backend."""
        try:
            import django_redis  # noqa: F401
        except ImportError:
            self.skipTest('django-redis δεν είναι εγκατεστημένο')
        s = _load_settings({'REDIS_CACHE_URL': 'redis://redis:6379/1'},
                           as_test_run=False)
        self.assertEqual(
            s.CACHES['default']['BACKEND'], 'django_redis.cache.RedisCache')
        self.assertEqual(
            s.CACHES['default']['LOCATION'], 'redis://redis:6379/1')

    def test_redis_cache_disabled_during_test_runs(self):
        """
        Ακόμη και με REDIS_CACHE_URL, μέσα σε `manage.py test` το cache
        ΔΕΝ πάει σε Redis: το Redis δεν κάνει rollback μεταξύ tests, οπότε
        cache/session/throttle counters θα διέρρεαν και θα έκαναν τα tests
        order-dependent (π.χ. DRF throttling).
        """
        s = _load_settings({'REDIS_CACHE_URL': 'redis://redis:6379/1'},
                           as_test_run=True)
        self.assertEqual(
            s.CACHES['default']['BACKEND'],
            'django.core.cache.backends.db.DatabaseCache',
        )

    def test_django_redis_is_declared_in_requirements(self):
        """Το πακέτο πρέπει να είναι δηλωμένο, όχι προαιρετικό."""
        req = (BASE_DIR / 'requirements.txt').read_text(encoding='utf-8')
        self.assertIn('django-redis', req)


class ProductionComposeTest(SimpleTestCase):
    """Εύρημα 3 + startup: το compose πρέπει να είναι πλήρες."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.compose = yaml.safe_load(
            (BASE_DIR / 'docker-compose.prod.yml').read_text(encoding='utf-8'))
        cls.env = cls.compose['services']['web']['environment']

    def test_django_env_is_production(self):
        """
        Χωρίς DJANGO_ENV το manage.py (settings_local) πέφτει στο
        development branch: DEBUG=True, ALLOWED_HOSTS=['*'], χωρίς
        secure cookies/HSTS — και παρακάμπτει τα prod fail-closed guards.
        """
        self.assertEqual(str(self.env.get('DJANGO_ENV', '')).lower(),
                         'production')

    def test_startup_creates_cache_table(self):
        """
        Το database cache απαιτεί createcachetable· χωρίς αυτό κάθε
        cache/throttling λειτουργία αποτυγχάνει στο πρώτο request.
        """
        command = self.compose['services']['web']['command']
        self.assertIn('createcachetable', command)
        self.assertIn('migrate', command)

    def test_redis_url_is_wired_to_the_redis_service(self):
        """Το compose πρέπει να δείχνει στο redis service, όχι localhost."""
        redis_url = str(self.env.get('REDIS_URL', ''))
        self.assertTrue(redis_url)
        self.assertNotIn('localhost', redis_url)
        self.assertIn('redis', redis_url)


class SettingsLocalEnvironmentTest(SimpleTestCase):
    """Το settings_local πρέπει να τιμά το DJANGO_ENV=production."""

    #: Ελάχιστο valid production περιβάλλον — ικανοποιεί τα fail-closed
    #: guards του settings.py ώστε να ελέγχεται η ΣΥΜΠΕΡΙΦΟΡΑ, όχι το
    #: hard-fail.
    PROD_ENV = {
        'SECRET_KEY': 'x' * 60,
        'DEBUG': 'False',
        'ALLOWED_HOSTS': 'example.gr',
        'FRITZ_API_TOKEN': 'y' * 40,
        'DATA_ENCRYPTION_KEY_CURRENT':
            'jhgAUo9ScsDy8CjlAM8XO5cFANKz_Nb2i01amVUla0c=',
        'ENFORCE_CLIENT_ASSIGNMENT': 'True',
    }

    def _load_settings_local(self, env):
        """
        Φορτώνει καθαρά το webcrm.settings_local — δηλαδή ΑΚΡΙΒΩΣ το
        settings module που χρησιμοποιεί το manage.py — με το δοσμένο
        environment, χωρίς να πειράξει τα settings της διεργασίας.
        """
        saved = {k: sys.modules.pop(k, None)
                 for k in ('webcrm.settings_local', 'webcrm.settings')}
        try:
            with mock.patch.dict(os.environ, env, clear=False):
                if 'DJANGO_ENV' not in env:
                    os.environ.pop('DJANGO_ENV', None)
                return importlib.import_module('webcrm.settings_local')
        finally:
            for key, value in saved.items():
                sys.modules.pop(key, None)
                if value is not None:
                    sys.modules[key] = value

    def test_production_branch_disables_debug(self):
        mod = self._load_settings_local(
            {**self.PROD_ENV, 'DJANGO_ENV': 'production'})
        self.assertFalse(mod.DEBUG)
        self.assertNotIn('*', mod.ALLOWED_HOSTS)

    def test_debug_false_without_django_env_fails_closed(self):
        """
        Η παγίδα της χειροκίνητης εγκατάστασης — πλέον fail closed.

        Παλιότερα αυτός ο συνδυασμός κατέληγε σιωπηλά σε development:
        DEBUG=True, ALLOWED_HOSTS=['*'] και **δημόσια /media/** (το urls.py
        διαλέγει `static()` αντί για το authenticated view με βάση το
        DEBUG). Η εφαρμογή ξεκινούσε κανονικά και έμοιαζε σωστά ρυθμισμένη.

        Πλέον σκάει αντί να μαντεύει.
        """
        # Προσομοίωση πραγματικού entry point (π.χ. `manage.py migrate`):
        # αλλιώς ισχύει η εξαίρεση του test runner, αφού αυτό εδώ τρέχει
        # μέσα από `manage.py test`.
        with mock.patch.object(sys, 'argv', ['manage.py', 'migrate']):
            with self.assertRaises(ImproperlyConfigured) as ctx:
                self._load_settings_local({**self.PROD_ENV})

        message = str(ctx.exception)
        self.assertIn('DJANGO_ENV', message)
        # Το μήνυμα πρέπει να λέει στον χειριστή τι ακριβώς να ορίσει.
        self.assertIn('production', message)
        self.assertIn('development', message)

    def test_missing_django_env_allows_explicit_debug_true(self):
        """
        Τοπικό runserver χωρίς πλήρες .env: το ρητό DEBUG=True είναι σαφής
        δήλωση πρόθεσης και επιτρέπεται.
        """
        env = {k: v for k, v in self.PROD_ENV.items() if k != 'DEBUG'}
        mod = self._load_settings_local({**env, 'DEBUG': 'True'})
        self.assertTrue(mod.DEBUG)

    def test_unknown_django_env_values_fail_closed(self):
        """
        Typo σε production ΔΕΝ γίνεται σιωπηλά development.

        Χωρίς αυτό, ένα `DJANGO_ENV=prodction` σε production server θα
        έδινε DEBUG=True και δημόσια έγγραφα πελατών.
        """
        for value in ('prod', 'prodction', 'Production!', '   ', '',
                      'dev', 'staging'):
            with self.subTest(django_env=value):
                with self.assertRaises(ImproperlyConfigured):
                    self._load_settings_local(
                        {**self.PROD_ENV, 'DJANGO_ENV': value})

    def test_valid_values_tolerate_case_and_whitespace(self):
        """
        `  ProDuction  ` είναι σαφής πρόθεση, όχι typo — κανονικοποιείται
        αντί να σκάει, ώστε ένα κενό στο .env να μη ρίχνει την παραγωγή.
        """
        mod = self._load_settings_local(
            {**self.PROD_ENV, 'DJANGO_ENV': '  ProDuction  '})
        self.assertFalse(mod.DEBUG)

        mod = self._load_settings_local(
            {**self.PROD_ENV, 'DJANGO_ENV': 'DEVELOPMENT'})
        self.assertTrue(mod.DEBUG)

    def test_test_runner_works_without_django_env(self):
        """
        Ο test runner δεν πρέπει να απαιτεί env setup.

        Δεν είναι θεωρητικό: το CI `test` job ορίζει DEBUG=False ΧΩΡΙΣ
        DJANGO_ENV. Αν το fail-closed δεν εξαιρούσε τον test runner, θα
        έσπαγε ολόκληρο το CI. (Το `security-smoke` job ορίζει ρητά
        production, οπότε η production διαδρομή παραμένει καλυμμένη.)

        Το ότι τρέχει αυτό το ίδιο το test μέσα από `manage.py test` είναι
        η ζωντανή απόδειξη· εδώ κλειδώνεται και ρητά.
        """
        with mock.patch.object(sys, 'argv', ['manage.py', 'test']):
            mod = self._load_settings_local({**self.PROD_ENV})
        self.assertTrue(mod.DEBUG)

    def test_production_serves_media_through_authenticated_view(self):
        """
        Το πραγματικό στοίχημα: με DJANGO_ENV=production τα /media/ πάνε
        στο authenticated `serve_protected_media`, όχι στο `static()`.

        Ελέγχεται το URLconf που παράγει το ίδιο το settings module, ώστε
        να μην αρκεστούμε στο ότι «το DEBUG είναι False».
        """
        mod = self._load_settings_local(
            {**self.PROD_ENV, 'DJANGO_ENV': 'production'})
        self.assertFalse(mod.DEBUG)

        saved = sys.modules.pop('webcrm.urls', None)
        try:
            with mock.patch.dict(os.environ, {'DJANGO_ENV': 'production'},
                                 clear=False):
                with mock.patch('django.conf.settings.DEBUG', False):
                    urls = importlib.import_module('webcrm.urls')
                    names = {
                        getattr(p, 'name', None)
                        for p in urls.urlpatterns
                    }
            self.assertIn(
                'protected_media', names,
                'Σε production τα /media/ πρέπει να περνούν από το '
                'authenticated serve_protected_media.')
        finally:
            sys.modules.pop('webcrm.urls', None)
            if saved is not None:
                sys.modules['webcrm.urls'] = saved

    def test_production_env_yields_secure_transport_settings(self):
        """Το DJANGO_ENV=production δίνει secure cookies και HSTS."""
        mod = self._load_settings_local(
            {**self.PROD_ENV, 'DJANGO_ENV': 'production'})
        self.assertTrue(mod.SESSION_COOKIE_SECURE)
        self.assertTrue(mod.CSRF_COOKIE_SECURE)
        self.assertTrue(mod.SECURE_SSL_REDIRECT)


class ProductionEnvTemplateTest(SimpleTestCase):
    """
    Το .env.production.example είναι το σημείο εκκίνησης κάθε deployment —
    ό,τι λείπει από εκεί λείπει και από την εγκατάσταση.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.text = (BASE_DIR / '.env.production.example').read_text(
            encoding='utf-8')

    def _values(self, key):
        return [line.split('=', 1)[1].strip()
                for line in self.text.splitlines()
                if line.strip().startswith(f'{key}=')]

    def test_django_env_is_present_and_production(self):
        values = self._values('DJANGO_ENV')
        self.assertEqual(
            values, ['production'],
            'Το .env.production.example πρέπει να ορίζει DJANGO_ENV=production· '
            'χωρίς αυτό κάθε manage.py εντολή τρέχει με DEBUG=True.')

    def test_django_env_is_documented_as_mandatory(self):
        """Να μη μείνει γυμνή γραμμή χωρίς την εξήγηση της παγίδας."""
        deployment = (BASE_DIR / 'DEPLOYMENT.md').read_text(encoding='utf-8')
        self.assertIn('DJANGO_ENV', deployment)
        checklist = (BASE_DIR / 'PRODUCTION_CHECKLIST.md').read_text(
            encoding='utf-8')
        self.assertIn('DJANGO_ENV', checklist)
