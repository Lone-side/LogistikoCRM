# -*- coding: utf-8 -*-
"""
Sentry error-monitoring — safe wiring
=====================================
Το sentry-sdk ήταν dependency αλλά ανενεργό· τώρα αρχικοποιείται gated από
SENTRY_DSN. Tests: (α) ανενεργό by default (dev/CI δεν στέλνουν τίποτα),
(β) GDPR — δεν στέλνεται PII πελατών (send_default_pii=False).
"""
import inspect

from django.conf import settings
from django.test import SimpleTestCase


class SentryConfigTest(SimpleTestCase):
    def test_disabled_by_default(self):
        # Χωρίς SENTRY_DSN env → no-op. Κρίσιμο: να μη «ξυπνάει» σε dev/CI.
        self.assertEqual(settings.SENTRY_DSN, '')

    def test_sentry_sdk_and_django_integration_importable(self):
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        self.assertTrue(callable(sentry_sdk.init))
        self.assertTrue(DjangoIntegration)

    def test_pii_sending_disabled_in_config(self):
        # GDPR guard: η αρχικοποίηση ΔΕΝ πρέπει ποτέ να στέλνει PII πελατών.
        import webcrm.settings as s
        src = inspect.getsource(s)
        self.assertIn('send_default_pii=False', src)
        # Και ότι παραμένει gated πίσω από το DSN (όχι always-on).
        self.assertIn('if SENTRY_DSN:', src)
