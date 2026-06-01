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

    # ----- staff-gated endpoints: client → 403 (default-deny) -----
    def test_client_forbidden_on_staff_endpoints(self):
        self.client.force_authenticate(user=self.user_a)
        staff_only = [
            '/accounting/api/v1/search/?q=test',
            '/accounting/api/dashboard/stats/',
            '/accounting/api/reports/stats/',
            '/accounting/api/v1/email/history/',
            f'/accounting/api/reports/client-statement/{self.client_b.id}/',
        ]
        for url in staff_only:
            resp = self.client.get(url)
            self.assertEqual(
                resp.status_code, status.HTTP_403_FORBIDDEN,
                f'{url} → {resp.status_code} (αναμενόταν 403)',
            )

    def test_client_cannot_read_staff_stats(self):
        # calls/tickets stats: ο πελάτης δεν λαμβάνει 200 (403 ή 404 λόγω routing).
        self.client.force_authenticate(user=self.user_a)
        for url in ['/accounting/api/v1/calls/stats/', '/accounting/api/v1/tickets/stats/']:
            resp = self.client.get(url)
            self.assertNotEqual(resp.status_code, status.HTTP_200_OK, url)

    def test_staff_allowed_on_staff_endpoints(self):
        # Sanity: το staff ΔΕΝ παίρνει 403 στα ίδια endpoints.
        self.client.force_authenticate(user=self.staff)
        for url in ['/accounting/api/dashboard/stats/', '/accounting/api/reports/stats/']:
            resp = self.client.get(url)
            self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN, url)

    # ----- credential fields NOT leaked to client -----
    def test_client_profile_has_no_credentials(self):
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.get(f'/accounting/api/v1/clients/{self.client_a.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ('kodikos_taxisnet', 'kodikos_ika_ergodoti', 'kodikos_gemi',
                      'onoma_xristi_taxisnet'):
            self.assertNotIn(field, resp.data, f'credential {field} leaked to client!')

    def test_staff_still_sees_credentials(self):
        # Το staff πρέπει να συνεχίζει να βλέπει τα credentials (staff UI).
        self.client.force_authenticate(user=self.staff)
        resp = self.client.get(f'/accounting/api/v1/clients/{self.client_a.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('kodikos_taxisnet', resp.data)

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


# =============================================================================
# /me/vat — απομόνωση δεδομένων ΦΠΑ
# =============================================================================

class PortalVATIsolationTest(APITestCase):
    def setUp(self):
        from decimal import Decimal
        from datetime import date
        from mydata.models import VATRecord, VATPeriodResult

        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='A', eidos_ipoxreou='company'
        )
        self.client_b = ClientProfile.objects.create(
            afm='094160855', eponimia='B', eidos_ipoxreou='company'
        )
        self.user_a = self.client_a.create_portal_user(password='PassA123!')
        self.user_b = self.client_b.create_portal_user(password='PassB123!')

        # VAT data: ένα record + period για κάθε πελάτη
        VATRecord.objects.create(
            client=self.client_a, mark=1001, is_cancelled=False,
            issue_date=date(2026, 5, 10), rec_type=1, inv_type='1.1',
            vat_category=1, net_value=Decimal('100'), vat_amount=Decimal('24'),
        )
        VATRecord.objects.create(
            client=self.client_b, mark=2001, is_cancelled=False,
            issue_date=date(2026, 5, 10), rec_type=1, inv_type='1.1',
            vat_category=1, net_value=Decimal('999'), vat_amount=Decimal('239'),
        )
        VATPeriodResult.objects.create(
            client=self.client_a, period_type='monthly', year=2026, period=5,
            vat_output=Decimal('24'), vat_input=Decimal('0'),
            vat_difference=Decimal('24'), final_result=Decimal('24'),
        )
        VATPeriodResult.objects.create(
            client=self.client_b, period_type='monthly', year=2026, period=5,
            vat_output=Decimal('239'), vat_input=Decimal('0'),
            vat_difference=Decimal('239'), final_result=Decimal('239'),
        )

    def test_client_sees_only_own_vat(self):
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.get('/accounting/api/client/me/vat/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Μόνο τα δικά του records (mark=1001), όχι το 2001
        marks = {r['mark'] for r in resp.data['records']}
        self.assertEqual(marks, {1001})
        # Μόνο το δικό του period
        period_finals = {p['final_result'] for p in resp.data['periods']}
        self.assertEqual(period_finals, {'24.00'})

    def test_staff_forbidden_on_me_vat(self):
        staff = User.objects.create_user(username='s', password='x', is_staff=True)
        self.client.force_authenticate(user=staff)
        resp = self.client.get('/accounting/api/client/me/vat/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_response_contract_shape(self):
        # Regression guard: το frontend εξαρτάται από αυτό ΑΚΡΙΒΩΣ το shape.
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.get('/accounting/api/client/me/vat/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        d = resp.data
        self.assertEqual(set(d.keys()), {'summary', 'periods', 'records', 'records_truncated'})
        self.assertEqual(set(d['summary'].keys()), {'output', 'input'})
        self.assertEqual(set(d['summary']['output'].keys()), {'net', 'vat'})
        rec = d['records'][0]
        self.assertEqual(
            set(rec.keys()),
            {'id', 'mark', 'issue_date', 'rec_type', 'kind', 'inv_type',
             'net_value', 'vat_amount'},
        )
        self.assertEqual(rec['kind'], 'output')
        self.assertFalse(d['records_truncated'])

    def test_summary_is_2dp(self):
        # client_a έχει output vat=24, net=100 → πρέπει '24.00'/'100.00' (όχι '24').
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.get('/accounting/api/client/me/vat/')
        self.assertEqual(resp.data['summary']['output']['vat'], '24.00')
        self.assertEqual(resp.data['summary']['output']['net'], '100.00')
        # Καμία εισροή → πρέπει '0.00' (όχι '0').
        self.assertEqual(resp.data['summary']['input']['vat'], '0.00')
        self.assertEqual(resp.data['summary']['input']['net'], '0.00')


# =============================================================================
# /me/documents/upload — ο πελάτης ανεβάζει ΑΛΛΑ πάντα στον εαυτό του
# =============================================================================

class PortalUploadIsolationTest(APITestCase):
    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='A', eidos_ipoxreou='company'
        )
        self.client_b = ClientProfile.objects.create(
            afm='094160855', eponimia='B', eidos_ipoxreou='company'
        )
        self.user_a = self.client_a.create_portal_user(password='PassA123!')

    def _file(self, name='doc.pdf', content=b'%PDF-1.4 test', content_type='application/pdf'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile(name, content, content_type=content_type)

    def test_client_can_upload_for_self(self):
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.post(
            '/accounting/api/client/me/documents/upload/',
            {'file': self._file(), 'document_category': 'invoices', 'description': 'test'},
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content[:300])
        doc = ClientDocument.objects.get(id=resp.data['id'])
        self.assertEqual(doc.client_id, self.client_a.id)
        self.assertEqual(doc.uploaded_by_id, self.user_a.id)
        self.assertEqual(doc.document_category, 'invoices')

    def test_upload_ignores_spoofed_client_id(self):
        # Ο πελάτης Α προσπαθεί να ανεβάσει για τον Β μέσω client_id στο body.
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.post(
            '/accounting/api/client/me/documents/upload/',
            {'file': self._file(), 'client_id': self.client_b.id},
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # Παρά το client_id στο body, αποδίδεται στον client_a.
        doc = ClientDocument.objects.get(id=resp.data['id'])
        self.assertEqual(doc.client_id, self.client_a.id)
        self.assertNotEqual(doc.client_id, self.client_b.id)

    def test_upload_rejects_bad_extension(self):
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.post(
            '/accounting/api/client/me/documents/upload/',
            {'file': self._file(name='hack.exe', content=b'MZ\x90')},
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_rejects_missing_file(self):
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.post(
            '/accounting/api/client/me/documents/upload/',
            {'document_category': 'general'},
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_staff_forbidden_on_me_upload(self):
        staff = User.objects.create_user(username='s', password='x', is_staff=True)
        self.client.force_authenticate(user=staff)
        resp = self.client.post(
            '/accounting/api/client/me/documents/upload/',
            {'file': self._file()},
            format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
