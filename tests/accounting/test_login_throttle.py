# -*- coding: utf-8 -*-
"""
SECURITY: /api/auth/login/ must be rate-limited against brute-force /
credential-stuffing. Keyed by client IP (username varies in stuffing attacks).
"""
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from accounting.models import ClientProfile


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    'LOCATION': 'login-throttle-test',
}})
class LoginThrottleTest(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.api = APIClient()
        # A real client user so a correct login is possible.
        self.client_p = ClientProfile.objects.create(
            afm='123456783', eponimia='Α', eidos_ipoxreou='company')
        self.user = self.client_p.create_portal_user(password='Right1234!')

    def _login(self, password):
        return self.api.post(
            '/accounting/api/auth/login/',
            {'username': self.user.username, 'password': password},
            format='json',
        )

    def test_configured_rate_present(self):
        from django.conf import settings as dj
        self.assertIn('login', dj.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'])

    def test_repeated_bad_logins_get_throttled(self):
        # Rate is 5/min (see settings). 6th attempt within the window → 429.
        codes = [self._login('wrong').status_code for _ in range(6)]
        # The first attempts are 401 (bad creds); once the limit is hit → 429.
        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, codes)
        self.assertEqual(codes[-1], status.HTTP_429_TOO_MANY_REQUESTS)

    def test_throttle_blocks_even_correct_credentials_after_limit(self):
        # Exhaust the limit with bad attempts, then a correct one is still blocked
        # (the throttle is on the endpoint, protecting against stuffing).
        for _ in range(6):
            self._login('wrong')
        resp = self._login('Right1234!')
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
