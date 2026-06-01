# -*- coding: utf-8 -*-
"""
Staff API for managing client portal accounts (so the accountant never needs the
Django admin). All actions are STAFF-ONLY; a client user must get 403.

APIRequestFactory used to avoid the Py3.14 + Django test-client HTML-error issue.
"""
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounting.models import ClientProfile
from accounting.api_clients import ClientViewSet


def _view(actions):
    return ClientViewSet.as_view(actions)


class PortalAccountApiTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.staff = User.objects.create_user(
            username='staff', password='x', is_staff=True)
        self.client_p = ClientProfile.objects.create(
            afm='123456783', eponimia='ΔΟΚΙΜΗ ΑΕ',
            eidos_ipoxreou='company', email='client@example.gr')

    # ----- portal status -----
    def test_status_reports_no_account_initially(self):
        req = self.factory.get('/x')
        force_authenticate(req, user=self.staff)
        resp = _view({'get': 'portal_status'})(req, pk=self.client_p.pk)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['has_portal_account'])

    # ----- create account + invite -----
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                       PORTAL_URL='https://portal.example.gr')
    def test_create_account_creates_user_and_sends_invite(self):
        mail.outbox = []
        req = self.factory.post('/x')
        force_authenticate(req, user=self.staff)
        resp = _view({'post': 'create_portal_account'})(req, pk=self.client_p.pk)
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        self.client_p.refresh_from_db()
        self.assertIsNotNone(self.client_p.user)
        self.assertEqual(self.client_p.user.username, self.client_p.afm)
        # Invite email sent.
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(resp.data['has_portal_account'])
        self.assertTrue(resp.data.get('invite_sent'))

    def test_create_account_idempotent(self):
        self.client_p.create_portal_user()
        req = self.factory.post('/x')
        force_authenticate(req, user=self.staff)
        resp = _view({'post': 'create_portal_account'})(req, pk=self.client_p.pk)
        # Already exists → still 200, not a duplicate.
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.filter(username=self.client_p.afm).count(), 1)

    # ----- resend invite -----
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                       PORTAL_URL='https://portal.example.gr')
    def test_resend_invite(self):
        self.client_p.create_portal_user()
        mail.outbox = []
        req = self.factory.post('/x')
        force_authenticate(req, user=self.staff)
        resp = _view({'post': 'resend_portal_invite'})(req, pk=self.client_p.pk)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_without_account_is_400(self):
        req = self.factory.post('/x')
        force_authenticate(req, user=self.staff)
        resp = _view({'post': 'resend_portal_invite'})(req, pk=self.client_p.pk)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ----- SECURITY: client users are forbidden -----
    def test_client_forbidden_on_create(self):
        attacker_client = ClientProfile.objects.create(
            afm='094160855', eponimia='Β', eidos_ipoxreou='company')
        attacker = attacker_client.create_portal_user(password='x')
        req = self.factory.post('/x')
        force_authenticate(req, user=attacker)
        resp = _view({'post': 'create_portal_account'})(req, pk=self.client_p.pk)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        # Target unchanged.
        self.client_p.refresh_from_db()
        self.assertIsNone(self.client_p.user)

    def test_client_forbidden_on_status(self):
        attacker_client = ClientProfile.objects.create(
            afm='094160855', eponimia='Β', eidos_ipoxreou='company')
        attacker = attacker_client.create_portal_user(password='x')
        req = self.factory.get('/x')
        force_authenticate(req, user=attacker)
        resp = _view({'get': 'portal_status'})(req, pk=self.client_p.pk)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
