# -*- coding: utf-8 -*-
"""
Γύρος 13 — regression tests για τα ευρήματα του τελικού ελέγχου:
1. SharedLink: πλήρες enforcement του requires_email (token gates)
7. SharedLink: atomic quotas (max_downloads / max_uploads)
(τα υπόλοιπα ευρήματα σε ξεχωριστές κλάσεις παρακάτω)
"""
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounting.models import ClientProfile, SharedLink
from tests.accounting.secure_client import SecureAPIClient, SecureClient

TEMP_MEDIA = tempfile.mkdtemp(prefix='round13_test_')


@override_settings(MEDIA_ROOT=TEMP_MEDIA, DOCUMENT_OCR_SYNC=True)
class SharedLinkGatesBase(TestCase):
    client_class = SecureClient
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.client_profile = ClientProfile.objects.create(
            afm='123456783',
            eponimia='ΠΕΛΑΤΗΣ ΓΥΡΟΥ 13 ΑΕ',
            eidos_ipoxreou='company',
        )

    def _make_doc(self):
        from accounting.services import filing
        return filing.create_client_document(
            client=self.client_profile,
            uploaded_file=SimpleUploadedFile('έγγραφο.pdf', b'%PDF-1.4'),
            category='vat', year=2026, month=1,
        )

    def _make_link(self, **kwargs):
        defaults = {'client': self.client_profile, 'access_level': 'download'}
        defaults.update(kwargs)
        password = defaults.pop('password', None)
        link = SharedLink(**defaults)
        if password:
            link.set_password(password)
        link.save()
        return link

    def _access_url(self, link):
        return reverse('accounting:shared_link_access', args=[link.token])

    def _download_url(self, link):
        return reverse('accounting:shared_link_download', args=[link.token])

    def _upload_url(self, link):
        return reverse('accounting:shared_link_upload', args=[link.token])

    def _auth(self, link, payload):
        import json
        return self.client.post(
            self._access_url(link), data=json.dumps(payload),
            content_type='application/json',
        )


class SharedLinkEmailGateTest(SharedLinkGatesBase):
    client_class = SecureClient
    """Εύρημα 1: το requires_email πρέπει να προστατεύει download/upload."""

    def test_open_link_no_gates(self):
        """Χωρίς password/email: download χωρίς token."""
        doc = self._make_doc()
        link = self._make_link(document=doc, client=None)
        resp = self.client.get(self._download_url(link))
        self.assertEqual(resp.status_code, 200)

    def test_password_only_download_requires_token(self):
        doc = self._make_doc()
        link = self._make_link(document=doc, client=None, password='pass123')
        self.assertEqual(self.client.get(self._download_url(link)).status_code, 401)
        token = self._auth(link, {'password': 'pass123'}).json()['access_token']
        resp = self.client.get(self._download_url(link), {'auth': token})
        self.assertEqual(resp.status_code, 200)

    def test_requires_email_only_download_requires_token(self):
        """Το κρίσιμο bypass: requires_email χωρίς password άφηνε το download ανοιχτό."""
        doc = self._make_doc()
        link = self._make_link(document=doc, client=None, requires_email=True)
        # Direct download χωρίς προηγούμενο authentication → 401
        self.assertEqual(self.client.get(self._download_url(link)).status_code, 401)
        # Το GET δεν εκδίδει usable token — μόνο αναφέρει τα gates
        info = self.client.get(self._access_url(link))
        self.assertEqual(info.status_code, 200)
        self.assertTrue(info.json().get('requires_auth'))
        self.assertNotIn('access_token', info.json())
        # POST χωρίς email → 400, με άκυρο email → 400
        self.assertEqual(self._auth(link, {}).status_code, 400)
        self.assertEqual(self._auth(link, {'email': 'όχι-email'}).status_code, 400)
        # POST με email → token που δουλεύει
        token = self._auth(link, {'email': 'pelatis@example.com'}).json()['access_token']
        resp = self.client.get(self._download_url(link), {'auth': token})
        self.assertEqual(resp.status_code, 200)

    def test_password_and_email_both_required(self):
        doc = self._make_doc()
        link = self._make_link(document=doc, client=None,
                               password='pass123', requires_email=True)
        # Μόνο κωδικός → 400 (λείπει email)
        self.assertEqual(self._auth(link, {'password': 'pass123'}).status_code, 400)
        # Μόνο email → 401 (λάθος κωδικός)
        self.assertEqual(
            self._auth(link, {'email': 'a@b.gr', 'password': ''}).status_code, 401)
        token = self._auth(
            link, {'password': 'pass123', 'email': 'a@b.gr'}).json()['access_token']
        self.assertEqual(
            self.client.get(self._download_url(link), {'auth': token}).status_code, 200)

    def test_upload_requires_token_on_protected_link(self):
        link = self._make_link(allow_upload=True, requires_email=True)
        resp = self.client.post(self._upload_url(link), {
            'files': SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
        })
        self.assertEqual(resp.status_code, 401)

    def test_wrong_expired_or_foreign_token_rejected(self):
        from django.core import signing
        from accounting.api_file_manager import (
            ACCESS_TOKEN_SALT, make_shared_access_token,
        )
        doc = self._make_doc()
        link = self._make_link(document=doc, client=None, password='pass123')
        other = self._make_link(password='pass123')
        url = self._download_url(link)
        # Σκουπίδι
        self.assertEqual(self.client.get(url, {'auth': 'garbage'}).status_code, 401)
        # Token άλλου link
        other_token = make_shared_access_token(other)
        self.assertEqual(self.client.get(url, {'auth': other_token}).status_code, 401)
        # Ληγμένο token (ίδιο payload, παλιό timestamp)
        valid = make_shared_access_token(link)
        payload = signing.loads(valid, salt=ACCESS_TOKEN_SALT)
        with self.settings():
            import time
            from unittest import mock
            real_time = time.time
            with mock.patch('time.time', lambda: real_time() - 5 * 3600):
                expired = signing.dumps(payload, salt=ACCESS_TOKEN_SALT)
        self.assertEqual(self.client.get(url, {'auth': expired}).status_code, 401)

    def test_config_change_invalidates_tokens(self):
        doc = self._make_doc()
        link = self._make_link(document=doc, client=None, password='pass123')
        token = self._auth(link, {'password': 'pass123'}).json()['access_token']
        # Αλλαγή κωδικού → το παλιό token ακυρώνεται
        link.set_password('άλλος-κωδικός')
        link.save()
        self.assertEqual(
            self.client.get(self._download_url(link), {'auth': token}).status_code, 401)
        # Ενεργοποίηση requires_email σε link χωρίς password → παλιό token άκυρο
        doc2 = self._make_doc()
        link2 = self._make_link(document=doc2, client=None)
        from accounting.api_file_manager import make_shared_access_token
        pre_token = make_shared_access_token(link2)
        link2.requires_email = True
        link2.save()
        self.assertEqual(
            self.client.get(self._download_url(link2), {'auth': pre_token}).status_code,
            401,
        )

    def test_token_carries_email_proof_not_email(self):
        """Το token περιέχει hash του email, όχι το ίδιο το email."""
        from django.core import signing
        from accounting.api_file_manager import ACCESS_TOKEN_SALT
        link = self._make_link(requires_email=True, allow_upload=True)
        token = self._auth(link, {'email': 'Pelatis@Example.com'}).json()['access_token']
        payload = signing.loads(token, salt=ACCESS_TOKEN_SALT)
        self.assertNotIn('pelatis', str(payload).lower().replace('•', ''))
        self.assertTrue(payload.get('e'))
        self.assertNotIn('@', payload['e'])


class SharedLinkQuotaTest(SharedLinkGatesBase):
    client_class = SecureClient
    """Εύρημα 7: atomic quotas — conditional updates στη βάση."""

    def test_concurrent_last_download_slot(self):
        doc = self._make_doc()
        link = self._make_link(document=doc, client=None, max_downloads=1)
        # Δύο "ταυτόχρονες" δεσμεύσεις στο ίδιο slot: μόνο μία περνά
        first = SharedLink.objects.get(pk=link.pk)
        second = SharedLink.objects.get(pk=link.pk)
        self.assertTrue(first.try_record_download())
        self.assertFalse(second.try_record_download())
        second.refresh_from_db()
        self.assertEqual(second.download_count, 1)

    def test_download_endpoint_atomic_limit(self):
        doc = self._make_doc()
        link = self._make_link(document=doc, client=None, max_downloads=1)
        self.assertEqual(self.client.get(self._download_url(link)).status_code, 200)
        self.assertEqual(self.client.get(self._download_url(link)).status_code, 410)
        link.refresh_from_db()
        self.assertEqual(link.download_count, 1)

    def test_concurrent_upload_reservation(self):
        link = self._make_link(allow_upload=True, max_uploads=1)
        first = SharedLink.objects.get(pk=link.pk)
        second = SharedLink.objects.get(pk=link.pk)
        self.assertTrue(first.try_reserve_uploads(1))
        self.assertFalse(second.try_reserve_uploads(1))
        second.refresh_from_db()
        self.assertEqual(second.upload_count, 1)

    def test_multi_file_upload_near_limit(self):
        link = self._make_link(allow_upload=True, max_uploads=3)
        SharedLink.objects.filter(pk=link.pk).update(upload_count=2)
        # 2 αρχεία με 1 διαθέσιμο slot → 400, χωρίς αύξηση counter
        resp = self.client.post(self._upload_url(link), {
            'files': [
                SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
                SimpleUploadedFile('b.pdf', b'%PDF-1.4'),
            ],
        })
        self.assertEqual(resp.status_code, 400)
        link.refresh_from_db()
        self.assertEqual(link.upload_count, 2)
        # 1 αρχείο → OK, φτάνει στο όριο
        resp2 = self.client.post(self._upload_url(link), {
            'files': SimpleUploadedFile('c.pdf', b'%PDF-1.4'),
        })
        self.assertEqual(resp2.status_code, 201, resp2.content)
        link.refresh_from_db()
        self.assertEqual(link.upload_count, 3)

    def test_failed_files_release_reserved_slots(self):
        link = self._make_link(allow_upload=True, max_uploads=2)
        resp = self.client.post(self._upload_url(link), {
            'files': [
                SimpleUploadedFile('καλό.pdf', b'%PDF-1.4'),
                SimpleUploadedFile('hack.exe', b'MZ'),
            ],
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.json()['uploaded']), 1)
        link.refresh_from_db()
        # Το slot του αποτυχημένου αρχείου αποδεσμεύτηκε
        self.assertEqual(link.upload_count, 1)


# ---------------------------------------------------------------------------
# Εύρημα 2: VoIPCall ↔ Ticket relationship invariant
# ---------------------------------------------------------------------------
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from accounting.models import Ticket, VoIPCall

User = get_user_model()


def make_role_user(username, role, clients=(), **extra):
    user = User.objects.create_user(username=username, password='x', **extra)
    user.groups.add(Group.objects.get(name=role))
    for c in clients:
        c.assigned_users.add(user)
    return User.objects.get(pk=user.pk)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class VoipTicketInvariantTest(TestCase):
    client_class = SecureClient
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='ΠΕΛΑΤΗΣ Α ΑΕ', eidos_ipoxreou='company')
        cls.client_b = ClientProfile.objects.create(
            afm='997654321', eponimia='ΠΕΛΑΤΗΣ Β ΑΕ', eidos_ipoxreou='company')
        cls.manager = make_role_user('manager13', 'Διαχειριστής')
        cls.accountant = make_role_user(
            'logistis13', 'Λογιστής', [cls.client_a, cls.client_b])

    def api(self, user):
        client = SecureAPIClient()
        client.force_authenticate(user)
        return client

    def _pair(self, client=None):
        """Κλήση + ticket στον ίδιο πελάτη (ή unassigned)."""
        call = VoIPCall.objects.create(
            call_id=f'c-{VoIPCall.objects.count()}', phone_number='2101234567',
            direction='incoming', status='missed', started_at=timezone.now(), client=client)
        ticket = Ticket.objects.create(
            call=call, client=client, title='Αναπάντητη', status='open')
        return call, ticket

    def test_patch_ticket_client_without_call_field_rejected(self):
        call, ticket = self._pair(self.client_a)
        resp = self.api(self.manager).patch(
            f'/accounting/api/v1/tickets/{ticket.id}/',
            {'client_id': self.client_b.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        ticket.refresh_from_db()
        self.assertEqual(ticket.client_id, self.client_a.id)

    def test_patch_ticket_unassign_with_bound_call_rejected(self):
        call, ticket = self._pair(self.client_a)
        resp = self.api(self.manager).patch(
            f'/accounting/api/v1/tickets/{ticket.id}/',
            {'client_id': None}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_patch_call_client_propagates_to_ticket_atomically(self):
        call, ticket = self._pair(self.client_a)
        resp = self.api(self.manager).patch(
            f'/accounting/api/v1/calls/{call.id}/',
            {'client_id': self.client_b.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        call.refresh_from_db()
        ticket.refresh_from_db()
        self.assertEqual(call.client_id, self.client_b.id)
        self.assertEqual(ticket.client_id, self.client_b.id)

    def test_patch_call_unassign_with_bound_ticket_rejected(self):
        call, ticket = self._pair(self.client_a)
        resp = self.api(self.manager).patch(
            f'/accounting/api/v1/calls/{call.id}/',
            {'client_id': None}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        call.refresh_from_db()
        self.assertEqual(call.client_id, self.client_a.id)

    def test_model_clean_blocks_admin_unassign_ticket(self):
        call, ticket = self._pair(self.client_a)
        ticket.client = None
        with self.assertRaises(DjangoValidationError):
            ticket.full_clean()

    def test_model_clean_blocks_admin_unassign_call(self):
        call, ticket = self._pair(self.client_a)
        call.client = None
        with self.assertRaises(DjangoValidationError):
            call.full_clean()

    def test_model_clean_blocks_admin_cross_client(self):
        call, ticket = self._pair(self.client_a)
        ticket.client = self.client_b
        with self.assertRaises(DjangoValidationError):
            ticket.full_clean()
        call.refresh_from_db()
        call.client = self.client_b
        with self.assertRaises(DjangoValidationError):
            call.full_clean()

    def test_create_ticket_with_foreign_client_call_rejected(self):
        foreign_call = VoIPCall.objects.create(
            call_id='c-foreign', phone_number='2109999999',
            direction='incoming', status='missed', started_at=timezone.now(), client=self.client_b)
        scoped = make_role_user('scoped13', 'Λογιστής', [self.client_a])
        resp = self.api(scoped).post(
            '/accounting/api/v1/tickets/',
            {'title': 'Δοκιμή', 'call': foreign_call.id,
             'client': self.client_a.id},
            format='json')
        self.assertIn(resp.status_code, (400, 404), resp.content)
        self.assertFalse(Ticket.objects.filter(call=foreign_call).exists())

    def test_update_ticket_to_cross_client_call_rejected(self):
        call, ticket = self._pair(self.client_a)
        other_call = VoIPCall.objects.create(
            call_id='c-other', phone_number='2108888888',
            direction='incoming', status='missed', started_at=timezone.now(), client=self.client_b)
        resp = self.api(self.manager).patch(
            f'/accounting/api/v1/tickets/{ticket.id}/',
            {'call_id': other_call.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_create_ticket_for_bound_call_inherits_client(self):
        call = VoIPCall.objects.create(
            call_id='c-inherit', phone_number='2107777777',
            direction='incoming', status='missed', started_at=timezone.now(), client=self.client_a)
        resp = self.api(self.manager).post(
            '/accounting/api/v1/tickets/',
            {'title': 'Χωρίς πελάτη', 'call': call.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        ticket = Ticket.objects.get(call=call)
        self.assertEqual(ticket.client_id, self.client_a.id)

    def test_serializer_hides_foreign_call_phone(self):
        from accounting.api_voip import TicketSerializer
        call = VoIPCall.objects.create(
            call_id='c-legacy', phone_number='2106666666',
            direction='incoming', status='missed', started_at=timezone.now(), client=self.client_b)
        # Legacy inconsistency φτιαγμένη απευθείας στο ORM
        ticket = Ticket(call=call, client=self.client_a, title='Legacy')
        ticket.save()
        data = TicketSerializer(ticket).data
        self.assertIsNone(data['call']['phone_number'])

    def test_unassigned_call_triage_still_allowed(self):
        call = VoIPCall.objects.create(
            call_id='c-triage', phone_number='2105555555',
            direction='incoming', status='missed', started_at=timezone.now())
        resp = self.api(self.manager).post(
            '/accounting/api/v1/tickets/',
            {'title': 'Triage', 'call': call.id, 'client': self.client_a.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)


# ---------------------------------------------------------------------------
# Εύρημα 3: child-model permissions στα nested ClientViewSet actions + counts
# ---------------------------------------------------------------------------
from django.contrib.auth.models import Permission


def make_perm_user(username, codenames, clients=()):
    """Χρήστης ΜΟΝΟ με συγκεκριμένα permissions (χωρίς groups)."""
    user = User.objects.create_user(username=username, password='x')
    for codename in codenames:
        user.user_permissions.add(
            Permission.objects.get(
                codename=codename, content_type__app_label='accounting'))
    for c in clients:
        c.assigned_users.add(user)
    return User.objects.get(pk=user.pk)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class ClientNestedActionPermsTest(TestCase):
    client_class = SecureClient
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='ΠΕΛΑΤΗΣ NESTED ΑΕ',
            eidos_ipoxreou='company')

    def api(self, user):
        client = SecureAPIClient()
        client.force_authenticate(user)
        return client

    def test_obligations_requires_child_view_perm(self):
        only_client = make_perm_user(
            'nested_c', ['view_clientprofile'], [self.client_a])
        url = f'/accounting/api/v1/clients/{self.client_a.id}/obligations/'
        self.assertEqual(self.api(only_client).get(url).status_code, 403)
        with_child = make_perm_user(
            'nested_co', ['view_clientprofile', 'view_monthlyobligation'],
            [self.client_a])
        self.assertEqual(self.api(with_child).get(url).status_code, 200)

    def test_documents_requires_child_view_perm(self):
        only_client = make_perm_user(
            'nested_d', ['view_clientprofile'], [self.client_a])
        url = f'/accounting/api/v1/clients/{self.client_a.id}/documents/'
        self.assertEqual(self.api(only_client).get(url).status_code, 403)
        with_child = make_perm_user(
            'nested_dd', ['view_clientprofile', 'view_clientdocument'],
            [self.client_a])
        self.assertEqual(self.api(with_child).get(url).status_code, 200)

    def test_other_nested_actions_require_child_perms(self):
        only_client = make_perm_user(
            'nested_x', ['view_clientprofile'], [self.client_a])
        api = self.api(only_client)
        base = f'/accounting/api/v1/clients/{self.client_a.id}'
        for suffix in ('emails', 'calls', 'tickets', 'full'):
            self.assertEqual(
                api.get(f'{base}/{suffix}/').status_code, 403, suffix)

    def test_tickets_post_requires_add_perms(self):
        viewer = make_perm_user(
            'nested_t', ['view_clientprofile', 'view_ticket'], [self.client_a])
        url = f'/accounting/api/v1/clients/{self.client_a.id}/tickets/'
        resp = self.api(viewer).post(url, {'title': 'Δοκιμή'}, format='json')
        self.assertEqual(resp.status_code, 403)
        creator = make_perm_user(
            'nested_tc',
            ['view_clientprofile', 'view_ticket', 'add_ticket', 'add_voipcall'],
            [self.client_a])
        resp2 = self.api(creator).post(url, {'title': 'Δοκιμή'}, format='json')
        self.assertEqual(resp2.status_code, 201, resp2.content)

    def test_detail_counts_null_without_child_perms(self):
        only_client = make_perm_user(
            'nested_n', ['view_clientprofile'], [self.client_a])
        url = f'/accounting/api/v1/clients/{self.client_a.id}/'
        data = self.api(only_client).get(url).json()
        self.assertIsNone(data['obligations_count'])
        self.assertIsNone(data['documents_count'])
        self.assertIsNone(data['pending_obligations_count'])
        # Με μόνο view_monthlyobligation: obligations ναι, documents όχι
        obl_user = make_perm_user(
            'nested_no', ['view_clientprofile', 'view_monthlyobligation'],
            [self.client_a])
        data2 = self.api(obl_user).get(url).json()
        self.assertIsNotNone(data2['obligations_count'])
        self.assertIsNone(data2['documents_count'])


# ---------------------------------------------------------------------------
# Εύρημα 4: completion views — perms, accessible querysets, ασφαλή inputs
# ---------------------------------------------------------------------------
from accounting.models import MonthlyObligation, ObligationType


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class CompletionViewsRound13Test(TestCase):
    client_class = SecureClient
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='ΠΕΛΑΤΗΣ COMPLETION ΑΕ',
            eidos_ipoxreou='company')
        cls.client_b = ClientProfile.objects.create(
            afm='997654321', eponimia='ΞΕΝΟΣ ΠΕΛΑΤΗΣ ΑΕ',
            eidos_ipoxreou='company')
        cls.ob_type = ObligationType.objects.create(name='ΦΠΑ13', is_active=True)
        cls.foreign_ob = MonthlyObligation.objects.create(
            client=cls.client_b, obligation_type=cls.ob_type,
            month=1, year=2026, deadline=timezone.now().date(),
            status='pending')

    def _staff_no_perms(self):
        user = User.objects.create_user(
            'staffnp13', password='x', is_staff=True)
        self.client.force_login(user)
        return user

    def _staff_scoped_change(self):
        """Staff με change perm αλλά scoped ΜΟΝΟ στον client_a."""
        user = User.objects.create_user('staffsc13', password='x', is_staff=True)
        for codename in ('change_monthlyobligation', 'view_monthlyobligation'):
            user.user_permissions.add(Permission.objects.get(
                codename=codename, content_type__app_label='accounting'))
        self.client_a.assigned_users.add(user)
        self.client.force_login(User.objects.get(pk=user.pk))
        return user

    def test_datatables_api_requires_model_perm(self):
        self._staff_no_perms()
        resp = self.client.get('/accounting/obligations/api/')
        self.assertEqual(resp.status_code, 403)

    def test_list_view_requires_model_perm(self):
        self._staff_no_perms()
        resp = self.client.get('/accounting/obligations/')
        self.assertEqual(resp.status_code, 403)

    def test_datatables_api_invalid_ints_no_500(self):
        user = User.objects.create_user('staffok13', password='x', is_staff=True)
        user.user_permissions.add(Permission.objects.get(
            codename='view_monthlyobligation',
            content_type__app_label='accounting'))
        self.client.force_login(User.objects.get(pk=user.pk))
        resp = self.client.get('/accounting/obligations/api/', {
            'draw': 'x', 'start': '-5', 'length': '99999',
            'month': 'abc', 'client': 'zzz',
        })
        self.assertEqual(resp.status_code, 200)

    def test_scoped_user_cannot_complete_foreign_obligation(self):
        self._staff_scoped_change()
        resp = self.client.post(
            f'/accounting/obligations/{self.foreign_ob.id}/complete/')
        self.assertEqual(resp.status_code, 404)
        self.foreign_ob.refresh_from_db()
        self.assertEqual(self.foreign_ob.status, 'pending')

    def test_staff_without_perm_cannot_complete(self):
        self._staff_no_perms()
        resp = self.client.post(
            f'/accounting/obligations/{self.foreign_ob.id}/complete/')
        self.assertEqual(resp.status_code, 403)


# ---------------------------------------------------------------------------
# Εύρημα 5: Excel import — credential permissions + explicit opt-in
# ---------------------------------------------------------------------------
try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

import io
import unittest


def _import_xlsx(rows):
    """Φτιάχνει in-memory xlsx με header ΑΦΜ/Επωνυμία/Κωδικός Taxis Net."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(['Α.Φ.Μ.', 'Επωνυμία/Επώνυμο', 'Όνομα Χρήστη Taxis Net',
               'Κωδικός Taxis Net'])
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    buf.name = 'import.xlsx'
    return buf


@unittest.skipUnless(HAS_OPENPYXL, 'openpyxl not installed')
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class ImportCredentialPermsTest(TestCase):
    client_class = SecureClient
    URL = '/accounting/api/v1/import/clients/csv/'

    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def api_user(self, username, codenames):
        user = make_perm_user(username, codenames)
        client = SecureAPIClient()
        client.force_authenticate(user)
        return user, client

    def _post(self, client, rows, import_credentials=True):
        data = {'file': _import_xlsx(rows), 'mode': 'update'}
        if import_credentials:
            data['import_credentials'] = 'true'
        return client.post(self.URL, data, format='multipart')

    def test_client_perms_only_cannot_import_credentials(self):
        from accounting.models import ClientCredential
        user, api = self.api_user(
            'imp_c', ['add_clientprofile', 'change_clientprofile',
                      'view_clientprofile'])
        resp = self._post(api, [['111111110', 'ΝΕΟΣ ΑΕ', 'user1', 'secret1']])
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        # Η γραμμή παραλείφθηκε ολόκληρη — ούτε client ούτε credential
        self.assertEqual(data['created_count'], 0)
        self.assertFalse(ClientProfile.objects.filter(afm='111111110').exists())
        self.assertEqual(ClientCredential.objects.count(), 0)
        # Χωρίς secret τιμές στα errors
        self.assertNotIn('secret1', str(data))

    def test_without_flag_credentials_silently_skipped_client_created(self):
        from accounting.models import ClientCredential
        user, api = self.api_user(
            'imp_f', ['add_clientprofile', 'change_clientprofile',
                      'view_clientprofile'])
        resp = self._post(api, [['111111110', 'ΝΕΟΣ ΑΕ', 'user1', 'secret1']],
                          import_credentials=False)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(ClientProfile.objects.filter(afm='111111110').exists())
        self.assertEqual(ClientCredential.objects.count(), 0)
        self.assertIn('import_credentials', str(resp.json()['errors']))

    def test_add_credential_only_cannot_change_existing(self):
        from accounting.models import ClientCredential
        from accounting.services.credentials import store_client_credentials
        existing = ClientProfile.objects.create(
            afm='111111110', eponimia='ΥΠΑΡΧΩΝ ΑΕ', eidos_ipoxreou='company')
        store_client_credentials(
            existing, {'TAXISNET': {'username': 'old', 'secret': 'oldpass'}})
        user, api = self.api_user(
            'imp_a', ['add_clientprofile', 'change_clientprofile',
                      'view_clientprofile', 'add_clientcredential'])
        existing.assigned_users.add(user)
        resp = self._post(api, [['111111110', 'ΥΠΑΡΧΩΝ ΑΕ', 'νέος', 'νέο-secret']])
        self.assertEqual(resp.status_code, 200, resp.content)
        cred = ClientCredential.objects.get(client=existing, service='TAXISNET')
        self.assertEqual(cred.username, 'old')  # ΔΕΝ άλλαξε
        self.assertEqual(resp.json()['updated_count'], 0)

    def test_change_credential_only_cannot_create_new(self):
        from accounting.models import ClientCredential
        user, api = self.api_user(
            'imp_ch', ['add_clientprofile', 'change_clientprofile',
                       'view_clientprofile', 'change_clientcredential'])
        resp = self._post(api, [['111111110', 'ΝΕΟΣ ΑΕ', 'user1', 'secret1']])
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(ClientProfile.objects.filter(afm='111111110').exists())
        self.assertEqual(ClientCredential.objects.count(), 0)

    def test_full_perms_import_credentials(self):
        from accounting.models import ClientCredential
        user, api = self.api_user(
            'imp_all', ['add_clientprofile', 'change_clientprofile',
                        'view_clientprofile', 'add_clientcredential',
                        'change_clientcredential'])
        resp = self._post(api, [['111111110', 'ΝΕΟΣ ΑΕ', 'user1', 'secret1']])
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['created_count'], 1)
        cred = ClientCredential.objects.get(
            client__afm='111111110', service='TAXISNET')
        self.assertEqual(cred.username, 'user1')
        self.assertEqual(cred.secret, 'secret1')
        # Χωρίς secret τιμές στο response
        self.assertNotIn('secret1', str(resp.json()))


# ---------------------------------------------------------------------------
# Εύρημα 6: DocumentRequest — boolean parsing + reminder race
# ---------------------------------------------------------------------------
from unittest import mock

from accounting.models import DocumentRequest, DocumentRequestItem


@override_settings(
    ENFORCE_CLIENT_ASSIGNMENT=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class DocumentRequestRound13Test(TestCase):
    client_class = SecureClient
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.manager = make_role_user('docreq13', 'Διαχειριστής')
        cls.client_profile = ClientProfile.objects.create(
            afm='123456783', eponimia='ΠΕΛΑΤΗΣ DOCREQ ΑΕ',
            eidos_ipoxreou='company', email='pelatis@example.com')

    def setUp(self):
        self.link = SharedLink.objects.create(
            client=self.client_profile, name='Portal', access_level='view',
            allow_upload=True,
            expires_at=timezone.now() + timezone.timedelta(days=30))
        self.doc_request = DocumentRequest.objects.create(
            client=self.client_profile, shared_link=self.link,
            title='Δικαιολογητικά')
        self.item = DocumentRequestItem.objects.create(
            request=self.doc_request, label='Τιμολόγια')
        self.api = SecureAPIClient()
        self.api.force_authenticate(self.manager)

    def _mark(self, payload):
        return self.api.post(
            f'/accounting/api/v1/document-requests/{self.doc_request.id}/mark-item/',
            payload, format='json')

    def test_mark_item_false_string_means_false(self):
        DocumentRequestItem.objects.filter(pk=self.item.pk).update(
            is_received=True, received_at=timezone.now())
        resp = self._mark({'item_id': self.item.id, 'is_received': 'false'})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_received)

    def test_mark_item_boolean_variants(self):
        for value, expected in [(False, False), ('0', False),
                                (True, True), ('true', True)]:
            DocumentRequestItem.objects.filter(pk=self.item.pk).update(
                is_received=not expected, received_at=None,
                received_document=None)
            resp = self._mark({'item_id': self.item.id, 'is_received': value})
            self.assertEqual(resp.status_code, 200, resp.content)
            self.item.refresh_from_db()
            self.assertEqual(self.item.is_received, expected, value)

    def test_mark_item_invalid_values_rejected(self):
        self.assertEqual(
            self._mark({'item_id': self.item.id,
                        'is_received': 'μήπως'}).status_code, 400)
        self.assertEqual(self._mark({'item_id': 'abc'}).status_code, 400)

    def _reminder(self):
        return self.api.post(
            f'/accounting/api/v1/document-requests/{self.doc_request.id}/send-reminder/')

    def test_reminder_cooldown_atomic(self):
        resp = self._reminder()
        self.assertEqual(resp.status_code, 200, resp.content)
        # Το δεύτερο (εντός cooldown) απορρίπτεται από το conditional update
        self.assertEqual(self._reminder().status_code, 400)
        self.doc_request.refresh_from_db()
        self.assertEqual(self.doc_request.reminder_count, 1)

    def test_reminder_failure_restores_cooldown_state(self):
        with mock.patch(
            'accounting.tasks._send_document_request_email',
            side_effect=RuntimeError('smtp down'),
        ):
            resp = self._reminder()
        self.assertEqual(resp.status_code, 502)
        self.doc_request.refresh_from_db()
        self.assertEqual(self.doc_request.reminder_count, 0)
        self.assertIsNone(self.doc_request.last_reminder_sent_at)
        # Μετά την αποτυχία, νέα προσπάθεια επιτρέπεται
        self.assertEqual(self._reminder().status_code, 200)


# ---------------------------------------------------------------------------
# Εύρημα 8: PII στα application logs
# ---------------------------------------------------------------------------
class PiiLoggingTest(TestCase):
    client_class = SecureClient
    def test_afm_checksum_warning_masks_afm(self):
        from accounting.api_clients import ClientCreateUpdateSerializer
        serializer = ClientCreateUpdateSerializer()
        bad_checksum_afm = '123456780'  # 9 ψηφία, λάθος check digit
        with self.assertLogs('accounting.api_clients', level='WARNING') as logs:
            serializer.validate_afm(bad_checksum_afm)
        output = '\n'.join(logs.output)
        self.assertNotIn(bad_checksum_afm, output)
        self.assertIn('failed checksum', output)

    def test_mydata_vat_detail_error_masks_afm(self):
        from accounting.services.access import mask_pii_value
        self.assertEqual(mask_pii_value('123456780'), '•••••6780')

    def test_phone_lookup_logs_masked(self):
        from accounting import phone_utils
        with self.assertLogs('accounting.phone_utils', level='DEBUG') as logs:
            phone_utils.find_client_by_phone('2101234567')
        output = '\n'.join(logs.output)
        self.assertNotIn('2101234567', output)


# ---------------------------------------------------------------------------
# Εύρημα 9: route audit — υπολειπόμενα κενά (legacy views, backup, collections)
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class RouteAuditRound13Test(TestCase):
    client_class = SecureClient
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='ΠΕΛΑΤΗΣ AUDIT ΑΕ',
            eidos_ipoxreou='company')

    def _staff_no_perms(self, username='audit_np'):
        user = User.objects.create_user(username, password='x', is_staff=True)
        self.client.force_login(user)
        return user

    def test_legacy_door_requires_staff(self):
        plain = User.objects.create_user('audit_plain', password='x')
        self.client.force_login(plain)
        resp = self.client.post('/accounting/open-door/')
        # staff_member_required → redirect στο admin login (302), όχι εκτέλεση
        self.assertIn(resp.status_code, (302, 403))

    def test_legacy_reads_require_model_perms(self):
        self._staff_no_perms()
        for url in ('/accounting/dashboard/', '/accounting/calendar/',
                    '/accounting/voip/dashboard/',
                    f'/accounting/client/{self.client_a.id}/'):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 403, url)
        resp = self.client.get('/accounting/api/calendar-events/')
        self.assertEqual(resp.status_code, 403)
        resp = self.client.get('/accounting/voip/api/calls/')
        self.assertEqual(resp.status_code, 403)

    def test_backup_endpoints_require_specific_perms(self):
        # Σκέτο is_staff ΔΕΝ αρκεί πλέον για backup create/download/restore
        user = self._staff_no_perms('audit_bk')
        api = SecureAPIClient()
        api.force_authenticate(user)
        self.assertEqual(
            api.get('/accounting/api/settings/backup/list/').status_code, 403)
        self.assertEqual(
            api.get('/accounting/api/settings/backup/settings/').status_code, 403)
        self.assertEqual(
            api.post('/accounting/api/settings/backup/create/').status_code, 403)
        # Διαχειριστής (μέσω setup_roles) έχει τα backup perms
        manager = make_role_user('audit_mgr', 'Διαχειριστής')
        api2 = SecureAPIClient()
        api2.force_authenticate(manager)
        self.assertEqual(
            api2.get('/accounting/api/settings/backup/list/').status_code, 200)

    def test_shared_collection_not_editable_by_non_owner(self):
        from accounting.models import DocumentCollection
        owner = make_role_user('audit_own', 'Λογιστής', [self.client_a])
        other = make_role_user('audit_oth', 'Λογιστής', [self.client_a])
        collection = DocumentCollection.objects.create(
            name='Κοινή συλλογή', owner=owner, is_shared=True)
        api = SecureAPIClient()
        api.force_authenticate(other)
        resp = api.patch(
            f'/accounting/api/v1/file-manager/collections/{collection.id}/',
            {'name': 'Παραβίαση'}, format='json')
        self.assertEqual(resp.status_code, 403)
        resp2 = api.delete(
            f'/accounting/api/v1/file-manager/collections/{collection.id}/')
        self.assertEqual(resp2.status_code, 403)
        collection.refresh_from_db()
        self.assertEqual(collection.name, 'Κοινή συλλογή')

    def test_afm_lookup_requires_view_clientprofile(self):
        user = User.objects.create_user('audit_afm', password='x')
        api = SecureAPIClient()
        api.force_authenticate(user)
        resp = api.post('/accounting/api/v1/afm-lookup/',
                        {'afm': '123456783'}, format='json')
        self.assertEqual(resp.status_code, 403)
