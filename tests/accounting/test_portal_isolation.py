# -*- coding: utf-8 -*-
"""
Client Portal — Data Isolation Tests
====================================
Το ΠΙΟ σημαντικό test του portal: ένας πελάτης πρέπει να βλέπει ΜΟΝΟ τα δικά
του δεδομένα, ποτέ άλλου πελάτη. Επίσης το staff πρέπει να συνεχίζει να βλέπει
τα πάντα (καμία regression).
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounting.models import (
    ClientProfile, ObligationType, MonthlyObligation, ClientDocument,
    VoIPCall, Ticket,
)
from accounting.portal import is_client_user


class PortalDataIsolationTest(APITestCase):
    """Επιβεβαίωση ότι client A δεν βλέπει δεδομένα client B."""

    def setUp(self):
        # Δύο πελάτες, ο καθένας με δικό του portal user.
        self.client_a = ClientProfile.objects.create(
            afm="123456783", eponimia="Πελάτης Α ΑΕ", eidos_ipoxreou="company"
        )
        self.client_b = ClientProfile.objects.create(
            afm="094160855", eponimia="Πελάτης Β ΑΕ", eidos_ipoxreou="company"
        )
        self.user_a = self.client_a.create_portal_user(password="PassA123!")
        self.user_b = self.client_b.create_portal_user(password="PassB123!")

        # Staff user (βλέπει τα πάντα).
        self.staff = User.objects.create_user(
            username="staffer", password="StaffPass123!", is_staff=True
        )

        # Obligation type + obligations για κάθε πελάτη.
        self.otype = ObligationType.objects.create(
            name="ΦΠΑ", code="VAT", frequency="monthly", deadline_type="last_day"
        )
        future = timezone.now().date() + timedelta(days=20)
        self.obl_a = MonthlyObligation.objects.create(
            client=self.client_a, obligation_type=self.otype,
            year=future.year, month=future.month, deadline=future,
        )
        # Διαφορετικός μήνας για να μη συγκρούεται το unique_together.
        future_b = future + timedelta(days=32)
        self.obl_b = MonthlyObligation.objects.create(
            client=self.client_b, obligation_type=self.otype,
            year=future_b.year, month=future_b.month, deadline=future_b,
        )

    # ----- helpers -----
    def _list_ids(self, url):
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content[:200])
        data = resp.data
        results = data['results'] if isinstance(data, dict) and 'results' in data else data
        return {item['id'] for item in results}

    # ----- role detection -----
    def test_portal_user_is_client_not_staff(self):
        self.assertTrue(is_client_user(self.user_a))
        self.assertFalse(self.user_a.is_staff)
        self.assertFalse(is_client_user(self.staff))

    # ----- clients endpoint -----
    def test_client_sees_only_own_profile(self):
        self.client.force_authenticate(user=self.user_a)
        ids = self._list_ids('/accounting/api/v1/clients/')
        self.assertEqual(ids, {self.client_a.id})
        self.assertNotIn(self.client_b.id, ids)

    def test_client_cannot_retrieve_other_client(self):
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.get(f'/accounting/api/v1/clients/{self.client_b.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ----- obligations endpoint -----
    def test_client_sees_only_own_obligations(self):
        self.client.force_authenticate(user=self.user_a)
        ids = self._list_ids('/accounting/api/v1/obligations/')
        self.assertEqual(ids, {self.obl_a.id})
        self.assertNotIn(self.obl_b.id, ids)

    def test_client_cannot_retrieve_other_obligation(self):
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.get(f'/accounting/api/v1/obligations/{self.obl_b.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ----- login response carries client role -----
    def test_login_response_marks_client(self):
        resp = self.client.post(
            '/accounting/api/auth/login/',
            {'username': self.user_a.username, 'password': 'PassA123!'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content[:200])
        user = resp.data['user']
        self.assertTrue(user['is_client'])
        self.assertEqual(user['client_id'], self.client_a.id)
        self.assertEqual(user['client_afm'], self.client_a.afm)
        self.assertFalse(user['is_staff'])

    def test_login_response_marks_staff_not_client(self):
        resp = self.client.post(
            '/accounting/api/auth/login/',
            {'username': self.staff.username, 'password': 'StaffPass123!'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content[:200])
        user = resp.data['user']
        self.assertFalse(user['is_client'])
        self.assertIsNone(user['client_id'])
        self.assertTrue(user['is_staff'])

    # ----- staff still sees everything -----
    def test_staff_sees_all_clients(self):
        self.client.force_authenticate(user=self.staff)
        ids = self._list_ids('/accounting/api/v1/clients/')
        self.assertIn(self.client_a.id, ids)
        self.assertIn(self.client_b.id, ids)

    def test_staff_sees_all_obligations(self):
        self.client.force_authenticate(user=self.staff)
        ids = self._list_ids('/accounting/api/v1/obligations/')
        self.assertIn(self.obl_a.id, ids)
        self.assertIn(self.obl_b.id, ids)
