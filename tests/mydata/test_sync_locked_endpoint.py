# -*- coding: utf-8 -*-
"""
Το endpoint συγχρονισμού ΦΠΑ (MyDataCredentialsViewSet.sync) ΔΕΝ πρέπει να
αναφέρει ψεύτικη «επιτυχία» όταν ο locked-period guard παραλείπει εντελώς τον
συγχρονισμό. Πρέπει να επιστρέφει καθαρό σήμα skipped/locked ώστε το frontend να
ενημερώνει σωστά τον χρήστη.

Σημείωση: ο guard ενεργοποιείται ΠΡΙΝ από οποιαδήποτε κλήση στο myDATA API
(δες mydata_sync_vat: ο έλεγχος κλειδωμένων περιόδων προηγείται του get_api_client),
οπότε το test δεν χρειάζεται mock δικτύου.

APIRequestFactory για αποφυγή του Py3.14 + Django test-client θέματος.
"""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounting.models import ClientProfile
from mydata.models import MyDataCredentials, VATPeriodResult
from mydata.views import MyDataCredentialsViewSet


def _sync_view():
    return MyDataCredentialsViewSet.as_view({'post': 'sync'})


class SyncLockedFeedbackTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.staff = User.objects.create_user(
            username='staff', password='x', is_staff=True)
        self.client_p = ClientProfile.objects.create(
            afm='159053680', eponimia='ΔΟΚΙΜΗ ΑΕ', eidos_ipoxreou='company')
        self.creds = MyDataCredentials(client=self.client_p, is_active=True)
        self.creds.user_id = 'user'            # property setter → encrypt
        self.creds.subscription_key = 'key'    # property setter → encrypt
        self.creds.save()
        # Κλειδωμένο Q1 2026 (1 Ιαν – 31 Μαρ): επικαλύπτει κάθε sync Ιαν–Μαρ.
        self.locked_q1 = VATPeriodResult.objects.create(
            client=self.client_p,
            period_type='quarterly',
            year=2026,
            period=1,
            is_locked=True,
        )

    def _post_sync(self, **data):
        req = self.factory.post('/x', data, format='json')
        force_authenticate(req, user=self.staff)
        return _sync_view()(req, pk=self.creds.pk)

    def test_locked_period_sync_reports_skipped_not_success(self):
        # Sync Φεβρουαρίου 2026 — μέσα στο κλειδωμένο Q1.
        resp = self._post_sync(year=2026, month=2)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get('skipped'))
        self.assertTrue(resp.data.get('locked'))
        self.assertFalse(resp.data.get('success'))
        # Μήνυμα στα ελληνικά που εξηγεί ότι η περίοδος είναι κλειδωμένη.
        self.assertIn('κλειδωμέν', (resp.data.get('message') or '').lower())

    def test_unlocked_period_sync_is_not_flagged_skipped(self):
        # Χωρίς κλειδωμένη περίοδο ο guard δεν κόβει. Mock-άρουμε το
        # call_command (no-op, χωρίς δίκτυο/logs) → κανονικό success, όχι skipped.
        self.locked_q1.is_locked = False
        self.locked_q1.save(update_fields=['is_locked'])
        with patch('django.core.management.call_command'):
            resp = self._post_sync(year=2026, month=2)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data.get('skipped'))
        self.assertNotEqual(resp.data.get('locked'), True)
        self.assertTrue(resp.data.get('success'))
