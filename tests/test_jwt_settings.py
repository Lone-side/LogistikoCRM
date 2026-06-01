# -*- coding: utf-8 -*-
"""
SECURITY (SD-001): access tokens must be short-lived so a stolen token (e.g. via
XSS from localStorage) is useful only briefly. Refresh-token rotation keeps this
transparent to the user.
"""
from datetime import timedelta

from django.conf import settings
from django.test import TestCase


class JwtLifetimeTest(TestCase):
    def test_access_token_is_short_lived(self):
        access = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']
        # ≤ 30 minutes for financial data.
        self.assertLessEqual(access, timedelta(minutes=30))

    def test_refresh_rotation_and_blacklist_enabled(self):
        self.assertTrue(settings.SIMPLE_JWT['ROTATE_REFRESH_TOKENS'])
        self.assertTrue(settings.SIMPLE_JWT['BLACKLIST_AFTER_ROTATION'])
