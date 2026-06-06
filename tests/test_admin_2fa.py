# -*- coding: utf-8 -*-
"""
Admin 2FA (SD-002) — wiring & safety
====================================
Το 2FA επιβάλλεται στο admin μόνο όταν ENABLE_ADMIN_2FA=True (βλ. webcrm/urls.py).
Τα tests κλειδώνουν: (α) ασφαλές default (OFF — κανένα lockout), (β) σωστό wiring
(apps + middleware order), (γ) ότι το OTPAdminSite μπλοκάρει staff χωρίς verified
OTP device και επιτρέπει με device.
"""
from types import MethodType

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory

from django_otp.admin import OTPAdminSite
from django_otp.middleware import OTPMiddleware


class Admin2FAConfigTest(TestCase):
    def test_disabled_by_default_no_lockout(self):
        # Κρίσιμο: το default ΠΡΕΠΕΙ να είναι False ώστε να μην κλειδωθεί κανείς.
        self.assertFalse(settings.ENABLE_ADMIN_2FA)

    def test_otp_apps_and_middleware_wired(self):
        for app in ('django_otp', 'django_otp.plugins.otp_totp', 'django_otp.plugins.otp_static'):
            self.assertIn(app, settings.INSTALLED_APPS)
        mw = settings.MIDDLEWARE
        self.assertIn('django_otp.middleware.OTPMiddleware', mw)
        # OTPMiddleware ΠΡΕΠΕΙ να είναι μετά το AuthenticationMiddleware.
        self.assertLess(
            mw.index('django.contrib.auth.middleware.AuthenticationMiddleware'),
            mw.index('django_otp.middleware.OTPMiddleware'),
        )


class OTPAdminSiteEnforcementTest(TestCase):
    def _request(self, user):
        req = RequestFactory().get('/admin/')
        req.session = {}  # OTPMiddleware διαβάζει το session για το verified device
        req.user = user
        # Το OTPMiddleware προσθέτει is_verified()/otp_device στο request.user.
        OTPMiddleware(lambda r: None)(req)
        return req

    def test_blocks_staff_without_verified_otp(self):
        staff = User.objects.create_user('s', password='x', is_staff=True, is_superuser=True)
        req = self._request(staff)
        site = OTPAdminSite(name='otptest')
        # Staff αλλά χωρίς OTP verification → ΟΧΙ πρόσβαση στο admin.
        self.assertFalse(site.has_permission(req))

    def test_allows_staff_with_verified_otp(self):
        from django_otp.plugins.otp_static.models import StaticDevice
        staff = User.objects.create_user('s2', password='x', is_staff=True, is_superuser=True)
        device = StaticDevice.objects.create(user=staff, name='backup', confirmed=True)
        req = self._request(staff)
        # Προσομοίωση επιτυχημένης OTP επαλήθευσης (όπως μετά το login flow).
        req.user.otp_device = device
        req.user.is_verified = MethodType(lambda self: self.otp_device is not None, req.user)
        site = OTPAdminSite(name='otptest2')
        self.assertTrue(site.has_permission(req))

    def test_non_staff_never_allowed(self):
        client_user = User.objects.create_user('c', password='x', is_staff=False)
        req = self._request(client_user)
        site = OTPAdminSite(name='otptest3')
        self.assertFalse(site.has_permission(req))
