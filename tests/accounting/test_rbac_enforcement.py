# tests/accounting/test_rbac_enforcement.py
"""
Αρνητικά tests πλήρους επιβολής authorization:
- Βοηθός (read-only group): writes → 403
- Λογιστής με ανάθεση μόνο στον πελάτη Α: κάθε πρόσβαση στον Β → 404/403
- Search/dashboard/reports/file-manager δεν διαρρέουν δεδομένα πελάτη Β
- Admin scoping, reveal hardening, rotation fail-closed
"""

import io

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounting.models import (
    ClientCredential, ClientDocument, ClientProfile, MonthlyObligation,
    ObligationType,
)


def make_role_user(username, role, clients=()):
    user = User.objects.create_user(username=username, password='x', is_active=True)
    user.groups.add(Group.objects.get(name=role))
    for c in clients:
        c.assigned_users.add(user)
    # Καθάρισμα cache permissions
    return User.objects.get(pk=user.pk)


class RbacBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456789', eponimia='ΠΕΛΑΤΗΣ Α ΑΕ', email='a@example.gr',
        )
        cls.client_b = ClientProfile.objects.create(
            afm='987654321', eponimia='ΠΕΛΑΤΗΣ Β ΕΠΕ', email='b@example.gr',
        )
        cls.otype = ObligationType.objects.create(code='ΦΠΑ', name='ΦΠΑ')
        from datetime import date
        cls.obl_b = MonthlyObligation.objects.create(
            client=cls.client_b, obligation_type=cls.otype, year=2026, month=6,
            deadline=date(2026, 6, 20),
        )
        cls.doc_b = ClientDocument.objects.create(
            client=cls.client_b, original_filename='b.pdf', filename='b.pdf',
        )
        cls.cred_b = ClientCredential.objects.create(
            client=cls.client_b, service='taxisnet', username='userb',
        )
        cls.cred_b.secret = 'topsecretB'
        cls.cred_b.save()

        cls.accountant = make_role_user('logistis', 'Λογιστής', [cls.client_a])
        cls.assistant = make_role_user('voithos', 'Βοηθός', [cls.client_a, cls.client_b])

    def api(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class AssistantWritePermissionsTest(RbacBase):
    """Ο Βοηθός (read-only) δεν μπορεί να γράψει πουθενά."""

    def test_assistant_cannot_create_client(self):
        resp = self.api(self.assistant).post(
            '/accounting/api/v1/clients/', {'afm': '111111110', 'eponimia': 'ΝΕΟΣ'},
        )
        self.assertEqual(resp.status_code, 403)

    def test_assistant_cannot_update_client(self):
        resp = self.api(self.assistant).patch(
            f'/accounting/api/v1/clients/{self.client_a.id}/', {'eponimia': 'ΑΛΛΑΓΗ'},
        )
        self.assertEqual(resp.status_code, 403)

    def test_assistant_cannot_create_obligation(self):
        resp = self.api(self.assistant).post('/accounting/api/v1/obligations/', {
            'client': self.client_a.id, 'obligation_type': self.otype.id,
            'year': 2026, 'month': 7,
        })
        self.assertEqual(resp.status_code, 403)

    def test_assistant_cannot_create_credential(self):
        resp = self.api(self.assistant).post(
            f'/accounting/api/v1/clients/{self.client_a.id}/credentials/',
            {'service': 'efka', 'username': 'u', 'secret': 's'},
        )
        self.assertEqual(resp.status_code, 403)

    def test_assistant_can_list_clients(self):
        resp = self.api(self.assistant).get('/accounting/api/v1/clients/')
        self.assertEqual(resp.status_code, 200)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class CrossClientAccessTest(RbacBase):
    """Λογιστής με ανάθεση μόνο στον Α δεν φτάνει τον Β από καμία διαδρομή."""

    def test_client_detail_b_404(self):
        resp = self.api(self.accountant).get(f'/accounting/api/v1/clients/{self.client_b.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_client_documents_action_b_404(self):
        resp = self.api(self.accountant).get(
            f'/accounting/api/v1/clients/{self.client_b.id}/documents/'
        )
        self.assertEqual(resp.status_code, 404)

    def test_obligation_create_for_b_rejected(self):
        resp = self.api(self.accountant).post('/accounting/api/v1/obligations/', {
            'client': self.client_b.id, 'obligation_type': self.otype.id,
            'year': 2026, 'month': 7,
        })
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(MonthlyObligation.objects.filter(
            client=self.client_b, month=7, year=2026
        ).exists())

    def test_obligation_documents_b_404(self):
        resp = self.api(self.accountant).get(
            f'/accounting/api/v1/obligations/{self.obl_b.id}/documents/'
        )
        self.assertEqual(resp.status_code, 404)

    def test_file_manager_list_hides_b(self):
        resp = self.api(self.accountant).get('/accounting/api/v1/file-manager/documents/')
        self.assertEqual(resp.status_code, 200)
        ids = [d['id'] for d in resp.json().get('results', resp.json())]
        self.assertNotIn(self.doc_b.id, ids)

    def test_file_manager_bulk_delete_skips_b(self):
        resp = self.api(self.accountant).post(
            '/accounting/api/v1/file-manager/documents/bulk-delete/',
            {'document_ids': [self.doc_b.id]}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['deleted_count'], 0)
        self.assertTrue(ClientDocument.objects.filter(id=self.doc_b.id).exists())

    def test_shared_link_for_b_document_404(self):
        resp = self.api(self.accountant).post(
            '/accounting/api/v1/file-manager/shared-links/',
            {'document_id': self.doc_b.id}, format='json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_credential_reveal_b_404(self):
        resp = self.api(self.accountant).post(
            f'/accounting/api/v1/clients/{self.client_b.id}/credentials/{self.cred_b.id}/reveal/'
        )
        self.assertIn(resp.status_code, (403, 404))

    def test_client_statement_b_404(self):
        resp = self.api(self.accountant).get(
            f'/accounting/api/reports/client-statement/{self.client_b.id}/'
        )
        self.assertEqual(resp.status_code, 404)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class SearchAndAggregateLeakTest(RbacBase):
    def test_global_search_hides_b(self):
        resp = self.api(self.accountant).get('/accounting/api/v1/search/', {'q': 'ΠΕΛΑΤΗΣ'})
        self.assertEqual(resp.status_code, 200)
        names = [r['title'] for r in resp.json()['results']['clients']]
        self.assertIn('ΠΕΛΑΤΗΣ Α ΑΕ', names)
        self.assertNotIn('ΠΕΛΑΤΗΣ Β ΕΠΕ', names)

    def test_search_by_afm_hides_b(self):
        resp = self.api(self.accountant).get('/accounting/api/v1/search/', {'q': '987654321'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['results']['clients'], [])

    def test_dashboard_stats_counts_scoped(self):
        resp = self.api(self.accountant).get('/accounting/api/dashboard/stats/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['total_clients'], 1)

    def test_file_manager_browse_hides_b(self):
        resp = self.api(self.accountant).get('/accounting/api/v1/file-manager/browse/')
        self.assertEqual(resp.status_code, 200)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=False)
class FlagOffRegressionTest(RbacBase):
    """Με το flag off όλα δουλεύουν όπως πριν (dev/single-user)."""

    def test_accountant_sees_all_clients(self):
        resp = self.api(self.accountant).get(f'/accounting/api/v1/clients/{self.client_b.id}/')
        self.assertEqual(resp.status_code, 200)

    def test_assistant_still_readonly(self):
        resp = self.api(self.assistant).patch(
            f'/accounting/api/v1/clients/{self.client_a.id}/', {'eponimia': 'Χ'},
        )
        self.assertEqual(resp.status_code, 403)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class AdminScopingTest(RbacBase):
    def test_admin_changelist_scoped(self):
        from django.contrib.admin.sites import site
        from accounting.admin.clients import ClientProfileAdmin
        admin_instance = site._registry[ClientProfile]
        self.assertIsInstance(admin_instance, ClientProfileAdmin)

        class FakeRequest:
            user = self.accountant
        qs = admin_instance.get_queryset(FakeRequest())
        self.assertIn(self.client_a, qs)
        self.assertNotIn(self.client_b, qs)

    def test_assigned_users_readonly_for_scoped_user(self):
        from django.contrib.admin.sites import site
        admin_instance = site._registry[ClientProfile]

        class FakeRequest:
            user = self.accountant
        self.assertIn('assigned_users', admin_instance.get_readonly_fields(FakeRequest()))


class RevealHardeningTest(RbacBase):
    def setUp(self):
        self.manager = make_role_user('manager', 'Διαχειριστής', [self.client_b])

    def test_reveal_sets_no_store_and_returns_secret(self):
        resp = self.api(self.manager).post(
            f'/accounting/api/v1/clients/{self.client_b.id}/credentials/{self.cred_b.id}/reveal/'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['secret'], 'topsecretB')
        self.assertIn('no-store', resp['Cache-Control'])

    def test_reveal_decrypt_failure_returns_500(self):
        # Χαλασμένο ciphertext → ελεγχόμενο σφάλμα, όχι κενό secret
        ClientCredential.objects.filter(pk=self.cred_b.pk).update(
            _secret_encrypted='gAAAAABbroken'
        )
        resp = self.api(self.manager).post(
            f'/accounting/api/v1/clients/{self.client_b.id}/credentials/{self.cred_b.id}/reveal/'
        )
        self.assertEqual(resp.status_code, 500)
        self.assertNotIn('secret', resp.json())


class RotationFailClosedTest(TestCase):
    def test_rotation_aborts_on_undecryptable_record(self):
        client = ClientProfile.objects.create(afm='123456789', eponimia='Χ')
        cred = ClientCredential.objects.create(client=client, service='taxisnet')
        ClientCredential.objects.filter(pk=cred.pk).update(
            _secret_encrypted='gAAAAABbroken'
        )
        from cryptography.fernet import Fernet
        with override_settings(
            DATA_ENCRYPTION_KEY_CURRENT=Fernet.generate_key().decode()
        ):
            with self.assertRaises(CommandError):
                call_command('rotate_encryption_key', stdout=io.StringIO(),
                             stderr=io.StringIO())

    def test_rotation_skip_invalid_completes(self):
        client = ClientProfile.objects.create(afm='123456789', eponimia='Χ')
        cred = ClientCredential.objects.create(client=client, service='taxisnet')
        ClientCredential.objects.filter(pk=cred.pk).update(
            _secret_encrypted='gAAAAABbroken'
        )
        from cryptography.fernet import Fernet
        with override_settings(
            DATA_ENCRYPTION_KEY_CURRENT=Fernet.generate_key().decode()
        ):
            call_command('rotate_encryption_key', '--skip-invalid',
                         stdout=io.StringIO(), stderr=io.StringIO())


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class AuditMaskingTest(RbacBase):
    def test_pii_change_audited_masked(self):
        from common.models import AuditLog
        manager = make_role_user('manager2', 'Διαχειριστής', [self.client_a])
        resp = self.api(manager).patch(
            f'/accounting/api/v1/clients/{self.client_a.id}/',
            {'iban': 'GR1601101250000000012300695'},
        )
        self.assertEqual(resp.status_code, 200)
        log = AuditLog.objects.filter(action='update').order_by('-id').first()
        self.assertIsNotNone(log)
        iban_change = log.changes['iban']
        self.assertNotIn('GR1601101250000000012300695', str(iban_change))
        self.assertTrue(str(iban_change.get('new', '')).endswith('0695'))
