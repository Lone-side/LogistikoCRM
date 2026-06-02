# -*- coding: utf-8 -*-
"""
Ανάκτηση/ορισμός κωδικού portal — δύο συμπληρωματικές διαδρομές:

1. Staff ορίζει κωδικό απευθείας (χωρίς email):
   POST /api/clients/{id}/set-portal-password/  (ClientViewSet.set_portal_password)
2. Self-service «ξέχασα κωδικό» (ο πελάτης ζητά link με email/ΑΦΜ):
   POST /api/client/request-password-reset/     (api_portal.request_password_reset)

APIRequestFactory για αποφυγή του Py3.14 + Django test-client θέματος.
Cache → locmem ώστε ο throttle να μη χτυπά τον (απών στα tests) db cache table.
"""
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounting.models import ClientProfile
from accounting.api_clients import ClientViewSet
from accounting.api_portal import request_password_reset, PasswordResetThrottle


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class StaffSetPortalPasswordTest(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.staff = User.objects.create_user('staff', password='x', is_staff=True)
        self.client_p = ClientProfile.objects.create(
            afm='123456783', eponimia='ΔΟΚΙΜΗ ΑΕ', eidos_ipoxreou='company',
            email='c@example.gr')

    def _set_pw(self, user, **body):
        req = self.factory.post('/x', body, format='json')
        force_authenticate(req, user=user)
        return ClientViewSet.as_view({'post': 'set_portal_password'})(
            req, pk=self.client_p.pk)

    def test_staff_sets_password_directly(self):
        self.client_p.create_portal_user()
        resp = self._set_pw(self.staff, password='Sup3rStr0ng!pw')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.client_p.refresh_from_db()
        self.assertTrue(self.client_p.user.check_password('Sup3rStr0ng!pw'))

    def test_weak_password_rejected(self):
        self.client_p.create_portal_user()
        resp = self._set_pw(self.staff, password='123')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_portal_account_returns_400(self):
        resp = self._set_pw(self.staff, password='Sup3rStr0ng!pw')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_client_user_forbidden(self):
        self.client_p.create_portal_user()
        attacker_c = ClientProfile.objects.create(
            afm='094160855', eponimia='Β', eidos_ipoxreou='company')
        attacker = attacker_c.create_portal_user(password='x')
        resp = self._set_pw(attacker, password='Sup3rStr0ng!pw')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PORTAL_URL='https://portal.example.gr')
class SelfServicePasswordResetTest(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.client_p = ClientProfile.objects.create(
            afm='123456783', eponimia='ΔΟΚΙΜΗ ΑΕ', eidos_ipoxreou='company',
            email='c@example.gr')
        self.client_p.create_portal_user()

    def _request(self, **body):
        req = self.factory.post('/x', body, format='json')
        return request_password_reset(req)

    def test_sends_link_for_matching_email(self):
        mail.outbox = []
        resp = self._request(identifier='c@example.gr')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

    def test_matching_afm_also_works(self):
        mail.outbox = []
        resp = self._request(identifier='123456783')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

    def test_unknown_identifier_no_email_same_response(self):
        mail.outbox = []
        resp = self._request(identifier='nobody@nowhere.gr')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)
        # Ίδιο γενικό μήνυμα — no enumeration oracle.
        self.assertIn('Αν υπάρχει λογαριασμός', resp.data['detail'])

    def test_client_without_portal_account_excluded(self):
        ClientProfile.objects.create(
            afm='094160855', eponimia='ΧΩΡΙΣ ACCOUNT',
            eidos_ipoxreou='company', email='noacct@example.gr')
        mail.outbox = []
        resp = self._request(identifier='noacct@example.gr')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)

    def test_throttle_is_attached(self):
        self.assertIn(PasswordResetThrottle, request_password_reset.cls.throttle_classes)
