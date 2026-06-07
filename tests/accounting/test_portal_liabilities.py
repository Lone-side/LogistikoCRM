# -*- coding: utf-8 -*-
"""
Client portal — Οφειλές (ΑΑΔΕ/ΕΦΚΑ) endpoint
=============================================
Read-only ενημερωτικές οφειλές που καταχωρεί ο λογιστής. Tests: απομόνωση
(πελάτης βλέπει ΜΟΝΟ τις δικές του), staff→403, σχήμα απάντησης + deep-links,
read-only (καμία write από πελάτη).
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from accounting.models import ClientProfile, ClientLiability

URL = '/accounting/api/client/me/liabilities/'


@override_settings(
    AADE_DEBTS_URL='https://aade.example/debts',
    EFKA_DEBTS_URL='https://efka.example/debts',
)
class PortalLiabilitiesTest(APITestCase):
    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Πελάτης Α', eidos_ipoxreou='company'
        )
        self.client_b = ClientProfile.objects.create(
            afm='094160855', eponimia='Πελάτης Β', eidos_ipoxreou='company'
        )
        self.user_a = self.client_a.create_portal_user(password='PassA123!')
        self.staff = User.objects.create_user('staff', password='x', is_staff=True)

        ClientLiability.objects.create(
            client=self.client_a, source='aade', description='ΦΠΑ Α τριμ.',
            amount=Decimal('100.00'), status='outstanding',
        )
        ClientLiability.objects.create(
            client=self.client_a, source='efka', description='Ρύθμιση ΚΕΑΟ',
            amount=Decimal('50.00'), status='arranged',
        )
        ClientLiability.objects.create(
            client=self.client_a, source='aade', description='Παλιά (εξοφλημένη)',
            amount=Decimal('999.00'), status='paid',
        )
        # Οφειλή του ΑΛΛΟΥ πελάτη — δεν πρέπει να φανεί ποτέ.
        ClientLiability.objects.create(
            client=self.client_b, source='aade', description='ΞΕΝΗ',
            amount=Decimal('777.00'), status='outstanding',
        )

    def test_client_sees_only_own_liabilities(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.get(URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content[:200])
        descriptions = {r['description'] for r in resp.data['results']}
        self.assertEqual(descriptions, {'ΦΠΑ Α τριμ.', 'Ρύθμιση ΚΕΑΟ', 'Παλιά (εξοφλημένη)'})
        self.assertNotIn('ΞΕΝΗ', descriptions)

    def test_totals_exclude_paid_and_group_by_source(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.get(URL)
        # aade: μόνο η outstanding 100 (η paid 999 εξαιρείται)· efka: 50.
        self.assertEqual(resp.data['totals'].get('aade'), '100.00')
        self.assertEqual(resp.data['totals'].get('efka'), '50.00')

    def test_response_includes_deeplinks(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.get(URL)
        self.assertEqual(resp.data['links']['aade'], 'https://aade.example/debts')
        self.assertEqual(resp.data['links']['efka'], 'https://efka.example/debts')

    def test_staff_forbidden(self):
        self.client.force_authenticate(self.staff)
        resp = self.client.get(URL)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_requires_auth(self):
        resp = self.client.get(URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_read_only_no_post(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.post(URL, {'source': 'aade', 'description': 'x', 'amount': '1'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        # Καμία νέα εγγραφή δεν δημιουργήθηκε για τον πελάτη.
        self.assertEqual(ClientLiability.objects.filter(client=self.client_a).count(), 3)
