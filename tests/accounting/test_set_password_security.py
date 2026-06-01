# -*- coding: utf-8 -*-
"""
SECURITY hardening for /api/client/set-password/:
- throttled at 3/hour (brute-force guard)
- constant-time / no enumeration oracle: a non-existent uid and a valid-uid-but-
  bad-token produce the IDENTICAL generic 400, and the token check always runs.
"""
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase, override_settings
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounting.models import ClientProfile
from accounting import api_portal


def _post(body):
    factory = APIRequestFactory()
    req = factory.post('/accounting/api/client/set-password/', body, format='json')
    return api_portal.set_password(req)


class SetPasswordOracleTest(TestCase):
    """No enumeration oracle: bad-uid and bad-token look identical."""

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α', eidos_ipoxreou='company')
        self.user = self.client_a.create_portal_user()

    def test_nonexistent_uid_returns_generic_invalid_link(self):
        bad_uid = urlsafe_base64_encode(force_bytes(99999999))
        resp = _post({'uid': bad_uid, 'token': 'whatever', 'password': 'NewPass123!'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['detail'], api_portal._INVALID_LINK)

    def test_valid_uid_bad_token_returns_same_generic_message(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        resp = _post({'uid': uid, 'token': 'invalid-token', 'password': 'NewPass123!'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # IDENTICAL message to the non-existent-uid case → no oracle.
        self.assertEqual(resp.data['detail'], api_portal._INVALID_LINK)

    def test_malformed_uid_returns_generic_message(self):
        resp = _post({'uid': '!!!not-base64!!!', 'token': 't', 'password': 'NewPass123!'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['detail'], api_portal._INVALID_LINK)

    def test_staff_user_uid_rejected_as_invalid(self):
        # A non-client (staff) uid must not be usable here, same generic error.
        from django.contrib.auth.models import User
        staff = User.objects.create_user(username='s', password='x', is_staff=True)
        uid = urlsafe_base64_encode(force_bytes(staff.pk))
        token = default_token_generator.make_token(staff)
        resp = _post({'uid': uid, 'token': token, 'password': 'NewPass123!'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['detail'], api_portal._INVALID_LINK)

    def test_valid_link_still_succeeds(self):
        link = self.client_a.get_password_set_link()
        resp = _post({'uid': link['uid'], 'token': link['token'], 'password': 'NewPass123!'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    'LOCATION': 'throttle-test',
}})
class SetPasswordThrottleTest(TestCase):
    """The endpoint is throttled at 3/hour (configured rate + enforcement)."""

    def test_configured_rate_is_3_per_hour(self):
        from django.conf import settings as dj
        self.assertEqual(
            dj.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['set_password'], '3/hour')

    def test_fourth_attempt_is_throttled(self):
        from django.core.cache import cache
        cache.clear()
        # Go through DRF's full view machinery so the throttle runs.
        from rest_framework.test import APIClient
        client = APIClient()
        body = {'uid': 'x', 'token': 'y', 'password': 'z'}  # always-invalid is fine
        codes = [
            client.post('/accounting/api/client/set-password/', body, format='json').status_code
            for _ in range(4)
        ]
        # First 3 allowed (400 invalid link), 4th throttled (429).
        self.assertEqual(codes[:3], [status.HTTP_400_BAD_REQUEST] * 3)
        self.assertEqual(codes[3], status.HTTP_429_TOO_MANY_REQUESTS)
