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

    # ----- /api/client/me/ endpoints -----
    def test_me_profile_returns_own_profile(self):
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.get('/accounting/api/client/me/profile/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['id'], self.client_a.id)
        self.assertEqual(resp.data['afm'], self.client_a.afm)

    def test_me_obligations_returns_only_own(self):
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.get('/accounting/api/client/me/obligations/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = {o['id'] for o in resp.data['results']}
        self.assertEqual(ids, {self.obl_a.id})
        self.assertNotIn(self.obl_b.id, ids)

    def test_me_endpoints_forbidden_for_staff(self):
        # Τα /me/ είναι αποκλειστικά για πελάτες· staff παίρνει 403.
        self.client.force_authenticate(user=self.staff)
        for ep in ['profile', 'obligations', 'documents', 'calls']:
            resp = self.client.get(f'/accounting/api/client/me/{ep}/')
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, ep)

    def test_me_endpoints_require_auth(self):
        resp = self.client.get('/accounting/api/client/me/profile/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # ----- write isolation: ο πελάτης είναι read-only (403 σε ΟΛΑ τα writes) -----
    def test_client_cannot_update_other_client(self):
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.patch(
            f'/accounting/api/v1/clients/{self.client_b.id}/',
            {'eponimia': 'HACKED'}, format='json',
        )
        # Read-only για πελάτες → 403 (ισχυρότερο από 404).
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.client_b.refresh_from_db()
        self.assertNotEqual(self.client_b.eponimia, 'HACKED')

    def test_client_cannot_update_own_client(self):
        # Ακόμα και το ΔΙΚΟ του προφίλ δεν επιτρέπεται να το μεταβάλει (read-only).
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.patch(
            f'/accounting/api/v1/clients/{self.client_a.id}/',
            {'eponimia': 'SELF EDIT'}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_client_cannot_create_obligation(self):
        # Πελάτης δεν μπορεί να δημιουργήσει υποχρέωση (ούτε για τον εαυτό του).
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.post(
            '/accounting/api/v1/obligations/',
            {'client': self.client_b.id, 'obligation_type': self.otype.id,
             'year': 2027, 'month': 5, 'deadline': '2027-05-31'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_client_cannot_delete_other_obligation(self):
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.delete(f'/accounting/api/v1/obligations/{self.obl_b.id}/')
        # Read-only → 403 (η υποχρέωση παραμένει).
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(MonthlyObligation.objects.filter(id=self.obl_b.id).exists())

    # ----- password set flow -----
    def test_set_password_flow(self):
        # Νέος πελάτης χωρίς usable password.
        client_c = ClientProfile.objects.create(
            afm="111111114", eponimia="Πελάτης Γ", eidos_ipoxreou="company"
        )
        user_c = client_c.create_portal_user()  # χωρίς password
        self.assertFalse(user_c.has_usable_password())

        link = client_c.get_password_set_link()
        resp = self.client.post(
            '/accounting/api/client/set-password/',
            {'uid': link['uid'], 'token': link['token'], 'password': 'NewPass123!'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content[:200])

        # Τώρα μπορεί να συνδεθεί.
        login = self.client.post(
            '/accounting/api/auth/login/',
            {'username': user_c.username, 'password': 'NewPass123!'},
            format='json',
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertTrue(login.data['user']['is_client'])

    def test_set_password_rejects_bad_token(self):
        link = self.client_a.get_password_set_link()
        resp = self.client.post(
            '/accounting/api/client/set-password/',
            {'uid': link['uid'], 'token': 'invalid-token', 'password': 'NewPass123!'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_set_password_rejects_short_password(self):
        link = self.client_a.get_password_set_link()
        resp = self.client.post(
            '/accounting/api/client/set-password/',
            {'uid': link['uid'], 'token': link['token'], 'password': 'short'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
