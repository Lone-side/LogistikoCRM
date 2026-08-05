# -*- coding: utf-8 -*-
"""
Tests για το security hardening των κωδικών πελατών:
- ClientCredential: κρυπτογράφηση round-trip
- API: τα credential πεδία ΔΕΝ εκτίθενται πλέον στο clients API
- Reveal: permission + audit log
- RBAC: ClientScopedQuerysetMixin με ENFORCE_CLIENT_ASSIGNMENT
"""
from django.contrib.auth.models import Permission, User
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase
from tests.utils.helpers import grant_accounting_model_perms

from accounting.models import ClientCredential, ClientProfile
from common.models import AuditLog

REMOVED_FIELDS = [
    'onoma_xristi_taxisnet', 'kodikos_taxisnet',
    'onoma_xristi_ika_ergodoti', 'kodikos_ika_ergodoti',
    'onoma_xristi_gemi', 'kodikos_gemi',
]


def perm(codename):
    return Permission.objects.get(codename=codename)


class ClientCredentialModelTest(APITestCase):
    def setUp(self):
        self.client_profile = ClientProfile.objects.create(
            afm='123456789', eponimia='ΔΟΚΙΜΗ ΑΕ', eidos_ipoxreou='company',
        )

    def test_secret_encrypt_roundtrip(self):
        cred = ClientCredential(
            client=self.client_profile,
            service=ClientCredential.Service.TAXISNET,
            username='user1',
        )
        cred.secret = 'μυστικό-123'
        cred.save()

        cred.refresh_from_db()
        # Αποθηκευμένο κρυπτογραφημένο (Fernet tokens ξεκινούν με gAAAAA)
        self.assertTrue(cred._secret_encrypted.startswith('gAAAAA'))
        self.assertNotIn('μυστικό-123', cred._secret_encrypted)
        self.assertEqual(cred.secret, 'μυστικό-123')
        self.assertTrue(cred.has_secret)

    def test_empty_secret(self):
        cred = ClientCredential.objects.create(
            client=self.client_profile, service='GEMI', username='u',
        )
        self.assertIsNone(cred.secret)
        self.assertFalse(cred.has_secret)


class ClientApiNoCredentialExposureTest(APITestCase):
    """Regression: τα 6 παλιά πεδία δεν εμφανίζονται/γράφονται στο clients API."""

    def setUp(self):
        self.user = User.objects.create_user('employee', password='x')
        self.user = grant_accounting_model_perms(self.user)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        self.client_profile = ClientProfile.objects.create(
            afm='123456789', eponimia='ΔΟΚΙΜΗ ΑΕ', eidos_ipoxreou='company',
        )

    def test_detail_has_no_credential_fields(self):
        response = self.api.get(f'/accounting/api/v1/clients/{self.client_profile.id}/')
        self.assertEqual(response.status_code, 200)
        for field in REMOVED_FIELDS:
            self.assertNotIn(field, response.data)
        self.assertNotIn('taxisnet', str(response.content))

    def test_patch_with_credential_fields_is_ignored(self):
        response = self.api.patch(
            f'/accounting/api/v1/clients/{self.client_profile.id}/',
            {'kodikos_taxisnet': 'leak', 'eponimia': 'ΝΕΑ ΕΠΩΝΥΜΙΑ'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('kodikos_taxisnet', response.data)
        # Δεν δημιουργήθηκε πουθενά credential από το client endpoint
        self.assertEqual(ClientCredential.objects.count(), 0)


class CredentialApiTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('accountant', password='x')
        self.user = grant_accounting_model_perms(self.user)
        self.user.user_permissions.add(
            perm('view_clientcredential'), perm('add_clientcredential'),
            perm('change_clientcredential'), perm('delete_clientcredential'),
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        self.client_profile = ClientProfile.objects.create(
            afm='123456789', eponimia='ΔΟΚΙΜΗ ΑΕ', eidos_ipoxreou='company',
        )
        self.cred = ClientCredential(
            client=self.client_profile, service='TAXISNET', username='user1',
        )
        self.cred.secret = 'top-secret'
        self.cred.save()
        self.base = f'/accounting/api/v1/clients/{self.client_profile.id}/credentials/'

    def test_list_is_masked(self):
        response = self.api.get(self.base)
        self.assertEqual(response.status_code, 200)
        data = response.data[0] if isinstance(response.data, list) else response.data['results'][0]
        self.assertEqual(data['secret_masked'], '••••••••')
        self.assertTrue(data['has_secret'])
        self.assertNotIn('top-secret', str(response.content))
        self.assertNotIn('_secret_encrypted', data)

    def test_reveal_requires_permission(self):
        response = self.api.post(f'{self.base}{self.cred.id}/reveal/')
        self.assertEqual(response.status_code, 403)
        # Καταγράφηκε η απόπειρα
        self.assertTrue(AuditLog.objects.filter(
            username='accountant', action='permission_denied',
        ).exists())

    def test_reveal_with_permission_returns_secret_and_audits(self):
        self.user.user_permissions.add(perm('view_client_credential_secret'))
        self.user = User.objects.get(pk=self.user.pk)  # refresh perm cache
        self.api.force_authenticate(user=self.user)

        response = self.api.post(f'{self.base}{self.cred.id}/reveal/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['secret'], 'top-secret')
        log = AuditLog.objects.filter(action='view', severity='high').first()
        self.assertIsNotNone(log)
        self.assertNotIn('top-secret', log.description)

    def test_create_credential_audits_without_values(self):
        response = self.api.post(self.base, {
            'service': 'EFKA', 'username': 'u2', 'secret': 'efka-pass',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertNotIn('efka-pass', str(response.content))
        log = AuditLog.objects.filter(action='create').latest('timestamp')
        self.assertNotIn('efka-pass', str(log.changes))
        self.assertTrue(log.changes.get('secret_set'))


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class RbacScopingTest(APITestCase):
    def setUp(self):
        self.assigned = grant_accounting_model_perms(User.objects.create_user('assigned', password='x'))
        self.stranger = grant_accounting_model_perms(User.objects.create_user('stranger', password='x'))
        self.supervisor = grant_accounting_model_perms(User.objects.create_user('supervisor', password='x'))
        self.supervisor.user_permissions.add(perm('view_all_clients'))

        self.client_profile = ClientProfile.objects.create(
            afm='123456789', eponimia='ΔΟΚΙΜΗ ΑΕ', eidos_ipoxreou='company',
        )
        self.client_profile.assigned_users.add(self.assigned)
        self.api = APIClient()

    def _list_count(self, user):
        self.api.force_authenticate(user=user)
        response = self.api.get('/accounting/api/v1/clients/')
        self.assertEqual(response.status_code, 200)
        return response.data['count'] if 'count' in response.data else len(response.data)

    def test_assigned_user_sees_client(self):
        self.assertEqual(self._list_count(self.assigned), 1)

    def test_stranger_sees_nothing(self):
        self.assertEqual(self._list_count(self.stranger), 0)
        self.api.force_authenticate(user=self.stranger)
        response = self.api.get(f'/accounting/api/v1/clients/{self.client_profile.id}/')
        self.assertEqual(response.status_code, 404)

    def test_view_all_clients_permission_sees_all(self):
        self.assertEqual(self._list_count(self.supervisor), 1)

    @override_settings(ENFORCE_CLIENT_ASSIGNMENT=False)
    def test_flag_off_keeps_old_behavior(self):
        self.assertEqual(self._list_count(self.stranger), 1)
