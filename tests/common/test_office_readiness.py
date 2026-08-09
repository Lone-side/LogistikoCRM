# -*- coding: utf-8 -*-
"""
Regression tests για το Local Office Operational Readiness profile.

Καλύπτει:

1. SECURE_REDIRECT_EXEMPT για τα anonymous health endpoints: με
   DJANGO_ENV=production το SECURE_SSL_REDIRECT γίνεται True και το
   container healthcheck (plain HTTP απευθείας στο gunicorn) έπαιρνε 301
   σε https → TLS handshake σε plaintext socket → ο web container έμενε
   μόνιμα unhealthy.

2. Δομή του docker-compose.office.yml overlay: τα published ports του
   nginx δένουν ΜΟΝΟ στο ${OFFICE_BIND_IP} (LAN interface), κανένα
   service δεν εκθέτει db/redis/web στο host, και το X-Forwarded-Proto
   ενεργοποιείται υποχρεωτικά.

3. .env.office.example: χωρίς πραγματικά secrets (tripwire), sandbox
   myDATA, RBAC enforcement, https-only origins, χωρίς wildcard hosts.

4. nginx/office.conf: TLS termination με parity στα location blocks του
   nginx/nginx.conf ώστε να μην αποκλίνουν σιωπηλά τα δύο configs.
"""
import re
from pathlib import Path

import yaml
from django.conf import settings
from django.test import TestCase, override_settings, tag

from tests.settings.test_runtime_config import _load_settings

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# CI-only Fernet key — ίδιο με το security-smoke job στο tests.yml,
# δεν χρησιμοποιείται πουθενά πραγματικά.
_CI_FERNET_KEY = 'jhgAUo9ScsDy8CjlAM8XO5cFANKz_Nb2i01amVUla0c='

_PRODUCTION_ENV = {
    'DJANGO_ENV': 'production',
    'DEBUG': 'False',
    'FRITZ_API_TOKEN': 'office-tests-fritz-token',
    'DATA_ENCRYPTION_KEY_CURRENT': _CI_FERNET_KEY,
    'ENFORCE_CLIENT_ASSIGNMENT': 'True',
}


@tag('TestCase')
class ProductionRedirectExemptTest(TestCase):
    """Τα anonymous health endpoints πρέπει να εξαιρούνται του redirect."""

    def test_production_settings_define_redirect_exempt(self):
        """DJANGO_ENV=production ⇒ redirect ενεργό ΚΑΙ exempt λίστα."""
        s = _load_settings(_PRODUCTION_ENV, as_test_run=False)
        self.assertTrue(s.SECURE_SSL_REDIRECT)
        self.assertEqual(s.SECURE_REDIRECT_EXEMPT, s.HEALTH_CHECK_EXEMPT_URLS)
        self.assertIn(r'^api/health/$', s.SECURE_REDIRECT_EXEMPT)

    def test_detailed_endpoint_is_not_exempt(self):
        """Το admin-only detailed endpoint μένει πίσω από HTTPS."""
        s = _load_settings(_PRODUCTION_ENV, as_test_run=False)
        for pattern in s.SECURE_REDIRECT_EXEMPT:
            self.assertIsNone(
                re.match(pattern, 'api/health/detailed/'),
                msg=f'pattern {pattern!r} ταιριάζει το detailed endpoint',
            )

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_REDIRECT_EXEMPT=settings.HEALTH_CHECK_EXEMPT_URLS,
    )
    def test_health_endpoints_answer_plain_http(self):
        """Insecure request στα health endpoints δεν παίρνει 301."""
        for path in ('/api/health/', '/api/health/ready/',
                     '/api/health/live/'):
            response = self.client.get(path, secure=False)
            self.assertNotEqual(response.status_code, 301, msg=path)
            self.assertIn(response.status_code, (200, 503), msg=path)

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_REDIRECT_EXEMPT=settings.HEALTH_CHECK_EXEMPT_URLS,
    )
    def test_other_paths_still_redirect(self):
        """Το exempt αφορά ΜΟΝΟ τα health endpoints — τίποτα άλλο."""
        for path in ('/api/health/detailed/', '/api/clients/',
                     '/contact_form/x/'):
            response = self.client.get(path, secure=False)
            self.assertEqual(response.status_code, 301, msg=path)

    def test_compose_healthcheck_url_is_exempt(self):
        """Το healthcheck URL του prod compose ταιριάζει στη λίστα."""
        compose = yaml.safe_load(
            (BASE_DIR / 'docker-compose.prod.yml').read_text(encoding='utf-8')
        )
        test_cmd = ' '.join(compose['services']['web']['healthcheck']['test'])
        match = re.search(r'http://localhost:8000(/[^"\')\s]+)', test_cmd)
        self.assertIsNotNone(match, msg=test_cmd)
        path = match.group(1).lstrip('/')
        self.assertTrue(
            any(re.match(p, path) for p in settings.HEALTH_CHECK_EXEMPT_URLS),
            msg=f'healthcheck path {path!r} δεν εξαιρείται από το redirect',
        )
