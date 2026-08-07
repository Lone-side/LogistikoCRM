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

    def test_production_branch_disables_debug(self):
        saved = {k: sys.modules.pop(k, None)
                 for k in ('webcrm.settings_local', 'webcrm.settings')}
        try:
            with mock.patch.dict(os.environ, {
                'DJANGO_ENV': 'production',
                'SECRET_KEY': 'x' * 60,
                'DEBUG': 'False',
                'ALLOWED_HOSTS': 'example.gr',
                'FRITZ_API_TOKEN': 'y' * 40,
                'DATA_ENCRYPTION_KEY_CURRENT':
                    'jhgAUo9ScsDy8CjlAM8XO5cFANKz_Nb2i01amVUla0c=',
                'ENFORCE_CLIENT_ASSIGNMENT': 'True',
            }, clear=False):
                mod = importlib.import_module('webcrm.settings_local')
                self.assertFalse(mod.DEBUG)
                self.assertNotIn('*', mod.ALLOWED_HOSTS)
        finally:
            for key, value in saved.items():
                sys.modules.pop(key, None)
                if value is not None:
                    sys.modules[key] = value
