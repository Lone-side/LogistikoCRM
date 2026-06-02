# -*- coding: utf-8 -*-
"""
Client self-sync ΦΠΑ: POST /api/client/me/vat/sync/

Ο πελάτης τραβάει ΜΟΝΟΣ του τα δικά του δεδομένα ΦΠΑ. Αυστηρά guardrails:
scoped στον εαυτό του, throttle, μόνο τρέχων/προηγούμενος μήνας, σέβεται locked.

- Cache → locmem ώστε ο throttle να μη χτυπά τον (απών στα tests) db cache table.
- APIRequestFactory για αποφυγή του Py3.14 + Django test-client θέματος.
- Ο locked-period guard ενεργοποιείται ΠΡΙΝ από κλήση myDATA API → χωρίς δίκτυο.
"""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounting.models import ClientProfile
from accounting.api_portal import me_sync_vat, VatSyncThrottle
from mydata.models import MyDataCredentials, VATPeriodResult


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class PortalVatSyncTest(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.client_p = ClientProfile.objects.create(
            afm='159053680', eponimia='ΔΟΚΙΜΗ ΑΕ', eidos_ipoxreou='company')
        self.user = self.client_p.create_portal_user(password='x')
        # myDATA credentials (ορισμένα από το λογιστήριο)
        self.creds = MyDataCredentials(client=self.client_p, is_active=True)
        self.creds.user_id = 'user'
        self.creds.subscription_key = 'key'
        self.creds.save()

    def _post(self, user=None, **body):
        req = self.factory.post('/x', body, format='json')
        force_authenticate(req, user=user or self.user)
        return me_sync_vat(req)

    # ---- happy path (μοκαρισμένο command, χωρίς δίκτυο) ----
    def test_client_can_trigger_sync_current_month(self):
        with patch('django.core.management.call_command') as m:
            resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get('success'))
        self.assertFalse(resp.data.get('skipped'))
        # Κλήθηκε το σωστό command για ΤΟΝ δικό του ΑΦΜ.
        args, _ = m.call_args
        self.assertEqual(args[0], 'mydata_sync_vat')
        self.assertIn(self.client_p.afm, args)

    # ---- locked period → skipped/locked (πραγματικό command, χωρίς δίκτυο) ----
    def test_locked_period_reports_skipped_not_success(self):
        today = timezone.localdate()
        VATPeriodResult.objects.create(
            client=self.client_p, period_type='monthly',
            year=today.year, period=today.month, is_locked=True)
        resp = self._post()  # default = τρέχων μήνας → επικαλύπτει το locked
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get('skipped'))
        self.assertTrue(resp.data.get('locked'))
        self.assertFalse(resp.data.get('success'))

    # ---- isolation / role ----
    def test_staff_user_forbidden(self):
        staff = User.objects.create_user('staff', password='x', is_staff=True)
        resp = self._post(user=staff)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ---- missing credentials ----
    def test_missing_credentials_returns_400(self):
        other = ClientProfile.objects.create(
            afm='094160855', eponimia='ΧΩΡΙΣ CREDS', eidos_ipoxreou='company')
        other_user = other.create_portal_user(password='x')
        resp = self._post(user=other_user)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ---- period restriction ----
    def test_old_month_rejected_400(self):
        with patch('django.core.management.call_command'):
            resp = self._post(year=2000, month=1)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_previous_month_allowed(self):
        today = timezone.localdate()
        py, pm = ((today.year - 1, 12) if today.month == 1
                  else (today.year, today.month - 1))
        with patch('django.core.management.call_command'):
            resp = self._post(year=py, month=pm)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    # ---- throttle wired ----
    def test_throttle_is_attached(self):
        self.assertIn(VatSyncThrottle, me_sync_vat.cls.throttle_classes)
