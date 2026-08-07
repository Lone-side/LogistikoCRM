# -*- coding: utf-8 -*-
"""
Γύρος 14 — regression tests:
1. Protected media: document-aware authorization (όχι «authenticated = όλα»)
2. Shared-link preview/download: DB-backed έλεγχος κατάστασης σε κάθε request
3. Κεντρικό transactional service για αλλαγή πελάτη κλήσης (invariant)
4. Upload quota lifecycle (invalid request_item, partial failure, exception)
5. Email proof δεμένο με το email του upload
6. Λοιπά model-permission gaps (export/import, email API, myDATA, admin import)
7. Χωρίς raw exception leakage
"""
import json
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounting.models import ClientProfile, SharedLink
from tests.accounting.secure_client import SecureAPIClient, SecureClient

User = get_user_model()

TEMP_MEDIA = tempfile.mkdtemp(prefix='round14_test_')


def make_role_user(username, role, clients=(), **extra):
    user = User.objects.create_user(username=username, password='x', **extra)
    user.groups.add(Group.objects.get(name=role))
    for c in clients:
        c.assigned_users.add(user)
    return User.objects.get(pk=user.pk)


def make_perm_user(username, codenames, clients=(), app_label='accounting'):
    user = User.objects.create_user(username=username, password='x')
    for codename in codenames:
        user.user_permissions.add(
            Permission.objects.get(
                codename=codename, content_type__app_label=app_label))
    for c in clients:
        c.assigned_users.add(user)
    return User.objects.get(pk=user.pk)


@override_settings(MEDIA_ROOT=TEMP_MEDIA, DOCUMENT_OCR_SYNC=True)
class Round14Base(TestCase):
    client_class = SecureClient

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.client_profile = ClientProfile.objects.create(
            afm='123456783',
            eponimia='ΠΕΛΑΤΗΣ ΓΥΡΟΥ 14 ΑΕ',
            eidos_ipoxreou='company',
        )

    def _make_doc(self, client=None):
        from accounting.services import filing
        # on_existing='keep' + portal capability: ανεξάρτητα fixtures
        # απαγορεύεται πλέον από το permission matrix (Γύρος 17)
        return filing.create_client_document(
            client=client or self.client_profile,
            uploaded_file=SimpleUploadedFile('έγγραφο.pdf', b'%PDF-1.4'),
            category='vat', year=2026, month=1, on_existing='keep',
            # Γύρος 20: ανώνυμο 'keep' απαιτεί explicit portal capability
            portal_capability=filing.PortalUploadCapability(1, (client or self.client_profile).pk),
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

    def _auth(self, link, payload):
        return self.client.post(
            reverse('accounting:shared_link_access', args=[link.token]),
            data=json.dumps(payload), content_type='application/json',
        )

    def _upload(self, link, data):
        return self.client.post(
            reverse('accounting:shared_link_upload', args=[link.token]), data)


class UploadQuotaLifecycleTest(Round14Base):
    """Εύρημα 4: κανένα αποτυχημένο upload δεν καταναλώνει μόνιμα quota."""

    def test_invalid_request_item_does_not_consume_quota(self):
        link = self._make_link(allow_upload=True, max_uploads=2)
        resp = self._upload(link, {
            'files': SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
            'request_item_id': 999999,
        })
        self.assertEqual(resp.status_code, 400)
        link.refresh_from_db()
        self.assertEqual(link.upload_count, 0)

    def test_already_received_item_does_not_consume_quota(self):
        from accounting.models import DocumentRequest, DocumentRequestItem
        link = self._make_link(allow_upload=True, max_uploads=2)
        doc_request = DocumentRequest.objects.create(
            client=self.client_profile, shared_link=link, title='Δικ.')
        item = DocumentRequestItem.objects.create(
            request=doc_request, label='Τιμολόγια',
            is_received=True, received_at=timezone.now())
        resp = self._upload(link, {
            'files': SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
            'request_item_id': item.id,
        })
        self.assertEqual(resp.status_code, 400)
        link.refresh_from_db()
        self.assertEqual(link.upload_count, 0)

    def test_partial_failure_releases_exact_slots(self):
        link = self._make_link(allow_upload=True, max_uploads=5)
        resp = self._upload(link, {
            'files': [
                SimpleUploadedFile('καλό.pdf', b'%PDF-1.4'),
                SimpleUploadedFile('hack.exe', b'MZ'),
                SimpleUploadedFile('bad2.bat', b'x'),
            ],
        })
        self.assertEqual(resp.status_code, 201)
        link.refresh_from_db()
        self.assertEqual(link.upload_count, 1)

    def test_all_failed_releases_all_slots(self):
        link = self._make_link(allow_upload=True, max_uploads=2)
        resp = self._upload(link, {
            'files': SimpleUploadedFile('hack.exe', b'MZ'),
        })
        self.assertEqual(resp.status_code, 400)
        link.refresh_from_db()
        self.assertEqual(link.upload_count, 0)

    def test_unexpected_exception_releases_slots(self):
        from unittest import mock
        link = self._make_link(allow_upload=True, max_uploads=2)
        with mock.patch(
            'accounting.services.filing.create_client_document',
            side_effect=RuntimeError('disk full'),
        ):
            with self.assertRaises(RuntimeError):
                self._upload(link, {
                    'files': SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
                })
        link.refresh_from_db()
        self.assertEqual(link.upload_count, 0)


class EmailProofBindingTest(Round14Base):
    """Εύρημα 5: token για email Α δεν καταγράφει email Β ή κενό."""

    def _token_for(self, link, email):
        return self._auth(link, {'email': email}).json()['access_token']

    def test_upload_email_must_match_token_proof(self):
        from accounting.models import SharedLinkAccess
        link = self._make_link(allow_upload=True, requires_email=True)
        token = self._token_for(link, 'alpha@example.com')
        # Άλλο email από αυτό του token → 401
        resp = self._upload(link, {
            'files': SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
            'auth': token, 'email': 'beta@example.com',
        })
        self.assertEqual(resp.status_code, 401)
        # Κενό email με requires_email → 401
        resp2 = self._upload(link, {
            'files': SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
            'auth': token,
        })
        self.assertEqual(resp2.status_code, 401)
        # Σωστό email (case/space-insensitive) → OK, και καταγράφεται αυτό
        resp3 = self._upload(link, {
            'files': SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
            'auth': token, 'email': '  Alpha@Example.com ',
        })
        self.assertEqual(resp3.status_code, 201, resp3.content)
        log = SharedLinkAccess.objects.get(shared_link=link, action='upload')
        self.assertEqual(log.email_provided.strip().lower(),
                         'alpha@example.com')


# ---------------------------------------------------------------------------
# Εύρημα 1: protected media — document-aware authorization
# ---------------------------------------------------------------------------
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from django.test import RequestFactory

from common.utils.media_tokens import make_media_token
from common.views.protected_media import serve_protected_media


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class ProtectedMediaAuthTest(Round14Base):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def setUp(self):
        super().setUp()
        self.foreign_client = ClientProfile.objects.create(
            afm='997654321', eponimia='ΞΕΝΟΣ ΠΕΛΑΤΗΣ ΑΕ',
            eidos_ipoxreou='company')
        self.own_doc = self._make_doc(self.client_profile)
        self.foreign_doc = self._make_doc(self.foreign_client)
        self.factory = RequestFactory()

    def _serve(self, path, user=None, token=None):
        url = f'/media/{path}'
        if token:
            url += f'?mt={token}'
        request = self.factory.get(url)
        if user is not None:
            request.user = user
        else:
            from django.contrib.auth.models import AnonymousUser
            request.user = AnonymousUser()
        return serve_protected_media(request, path)

    def test_scoped_user_cannot_open_foreign_client_path(self):
        user = make_perm_user('media_scoped', ['view_clientdocument'],
                              [self.client_profile])
        # Δικό του έγγραφο → OK
        resp = self._serve(self.own_doc.file.name, user=user)
        self.assertEqual(resp.status_code, 200)
        # Ξένο έγγραφο, με το ακριβές path → 404
        with self.assertRaises(Http404):
            self._serve(self.foreign_doc.file.name, user=user)

    def test_assistant_session_cannot_open_foreign_document(self):
        assistant = make_role_user('media_voithos', 'Βοηθός',
                                   [self.client_profile])
        with self.assertRaises(Http404):
            self._serve(self.foreign_doc.file.name, user=assistant)

    def test_media_token_does_not_bypass_assignment(self):
        # Το token ταυτοποιεί χρήστη· ΔΕΝ παραχωρεί πρόσβαση. Token
        # δεμένο σε χρήστη εκτός ανάθεσης → 404 ακόμη και χωρίς session.
        user = make_perm_user('media_tok', ['view_clientdocument'],
                              [self.client_profile])
        token = make_media_token(self.foreign_doc.file.name, user)
        with self.assertRaises(Http404):
            self._serve(self.foreign_doc.file.name, token=token)
        with self.assertRaises(Http404):
            self._serve(self.foreign_doc.file.name, user=user, token=token)
        # Άκυρο token χωρίς session → κανένας χρήστης → 403
        with self.assertRaises(DjangoPermissionDenied):
            self._serve(self.foreign_doc.file.name, token='garbage')

    def test_session_without_model_perm_denied(self):
        user = make_perm_user('media_noperm', [], [self.client_profile])
        with self.assertRaises(Http404):
            self._serve(self.own_doc.file.name, user=user)

    def test_unmapped_path_fails_closed(self):
        import os
        orphan = os.path.join(TEMP_MEDIA, 'orphan.pdf')
        with open(orphan, 'wb') as f:
            f.write(b'%PDF-1.4')
        manager = make_role_user('media_mgr', 'Διαχειριστής')
        with self.assertRaises(Http404):
            self._serve('orphan.pdf', user=manager)

    def test_see_all_manager_can_open_any_client_doc(self):
        manager = make_role_user('media_mgr2', 'Διαχειριστής')
        resp = self._serve(self.foreign_doc.file.name, user=manager)
        self.assertEqual(resp.status_code, 200)

    def test_crm_thefile_object_level_policy(self):
        # Γύρος 15: ένα CRM TheFile δεν είναι πλέον προσβάσιμο μόνο επειδή ο
        # χρήστης είναι authenticated — η πρόσβαση κρίνεται object-level από
        # το content_object. Ένα TheFile σε content_object που δεν
        # υποστηρίζει την CRM πολιτική (π.χ. ClientProfile) → fail closed.
        from django.contrib.contenttypes.models import ContentType
        from django.core.files.base import ContentFile
        from common.models import TheFile
        ct = ContentType.objects.get_for_model(ClientProfile)
        the_file = TheFile(content_type=ct, object_id=self.client_profile.pk)
        the_file.file.save('σημειωση.txt', ContentFile(b'crm note'), save=True)
        plain = User.objects.create_user('media_plain', password='x')
        with self.assertRaises(Http404):
            self._serve(the_file.file.name, user=plain)
        # Το token επίσης δεν παρακάμπτει (fail closed): ταυτοποιεί τον
        # χρήστη και η CRM object-level πολιτική τρέχει κανονικά γι' αυτόν.
        token = make_media_token(the_file.file.name, plain)
        with self.assertRaises(Http404):
            self._serve(the_file.file.name, token=token)


# ---------------------------------------------------------------------------
# Εύρημα 2: shared-link preview — DB-backed έλεγχος σε κάθε request
# ---------------------------------------------------------------------------
class SharedLinkPreviewTest(Round14Base):
    def _preview_url(self, link, doc_id=None, auth=None):
        url = reverse('accounting:shared_link_preview', args=[link.token])
        params = []
        if doc_id is not None:
            params.append(f'doc_id={doc_id}')
        if auth:
            params.append(f'auth={auth}')
        if params:
            url += '?' + '&'.join(params)
        return url

    def test_portal_preview_url_is_link_aware(self):
        doc = self._make_doc()
        link = self._make_link(document=doc, client=None)
        resp = self.client.get(
            reverse('accounting:shared_link_access', args=[link.token]))
        preview_url = resp.json()['document']['preview_url']
        self.assertIn(f'/share/{link.token}/preview/', preview_url)
        self.assertNotIn('mt=', preview_url)
        self.assertNotIn('/media/', preview_url)

    def test_preview_fails_after_state_changes(self):
        doc = self._make_doc()
        link = self._make_link(document=doc, client=None)
        url = self._preview_url(link)
        self.assertEqual(self.client.get(url).status_code, 200)
        # Deactivation
        SharedLink.objects.filter(pk=link.pk).update(is_active=False)
        self.assertEqual(self.client.get(url).status_code, 410)
        SharedLink.objects.filter(pk=link.pk).update(is_active=True)
        # Expiration
        SharedLink.objects.filter(pk=link.pk).update(
            expires_at=timezone.now() - timezone.timedelta(days=1))
        self.assertEqual(self.client.get(url).status_code, 410)
        SharedLink.objects.filter(pk=link.pk).update(expires_at=None)
        # Token regeneration → παλιό URL 404
        SharedLink.objects.filter(pk=link.pk).update(token='x' * 43)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_preview_auth_invalidated_by_config_change(self):
        doc = self._make_doc()
        link = self._make_link(document=doc, client=None, password='pass123')
        auth = self._auth(link, {'password': 'pass123'}).json()['access_token']
        url = self._preview_url(link, auth=auth)
        self.assertEqual(self.client.get(url).status_code, 200)
        # Password change → 401
        link.set_password('νέος-κωδικός')
        link.save()
        self.assertEqual(self.client.get(url).status_code, 401)
        # requires_email toggle σε ανοιχτό link → παλιά tokens άκυρα
        doc2 = self._make_doc()
        link2 = self._make_link(document=doc2, client=None, password='pass123')
        auth2 = self._auth(link2, {'password': 'pass123'}).json()['access_token']
        link2.requires_email = True
        link2.save()
        self.assertEqual(
            self.client.get(self._preview_url(link2, auth=auth2)).status_code,
            401)

    def test_preview_respects_max_downloads(self):
        doc = self._make_doc()
        link = self._make_link(document=doc, client=None, max_downloads=1)
        url = self._preview_url(link)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 410)
        link.refresh_from_db()
        self.assertEqual(link.download_count, 1)

    def test_folder_link_rejects_foreign_doc_id(self):
        foreign_client = ClientProfile.objects.create(
            afm='997654321', eponimia='ΞΕΝΟΣ ΑΕ', eidos_ipoxreou='company')
        foreign_doc = self._make_doc(foreign_client)
        link = self._make_link()  # folder link του client_profile
        resp = self.client.get(self._preview_url(link, doc_id=foreign_doc.id))
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Εύρημα 3: κεντρικό service αλλαγής πελάτη κλήσης
# ---------------------------------------------------------------------------
from accounting.models import Ticket, VoIPCall


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class CallClientServiceTest(TestCase):
    client_class = SecureClient

    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='ΠΕΛΑΤΗΣ Α ΑΕ',
            eidos_ipoxreou='company', kinito_tilefono='6971234567')
        cls.client_b = ClientProfile.objects.create(
            afm='997654321', eponimia='ΠΕΛΑΤΗΣ Β ΑΕ',
            eidos_ipoxreou='company', email='b@example.com')
        cls.manager = make_role_user('svc_mgr', 'Διαχειριστής')

    def api(self, user):
        client = SecureAPIClient()
        client.force_authenticate(user)
        return client

    def _pair(self, client=None, ticket_client='same'):
        call = VoIPCall.objects.create(
            call_id=f'svc-{VoIPCall.objects.count()}',
            phone_number='2101234567', direction='incoming',
            status='missed', started_at=timezone.now(), client=client)
        tclient = client if ticket_client == 'same' else ticket_client
        ticket = Ticket.objects.create(
            call=call, client=tclient, title='SVC', status='open')
        return call, ticket

    def test_match_client_updates_both_sides(self):
        call, ticket = self._pair(self.client_a)
        resp = self.api(self.manager).post(
            f'/accounting/api/v1/calls/{call.id}/match_client/',
            {'client_id': self.client_b.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        call.refresh_from_db()
        ticket.refresh_from_db()
        self.assertEqual(call.client_id, self.client_b.id)
        self.assertEqual(ticket.client_id, self.client_b.id)
        self.assertEqual(call.client_email, 'b@example.com')

    def test_match_client_without_change_ticket_rejected(self):
        call, ticket = self._pair(self.client_a)
        user = make_perm_user(
            'svc_nochg',
            ['view_voipcall', 'change_voipcall', 'view_clientprofile'],
            [self.client_a, self.client_b])
        resp = self.api(user).post(
            f'/accounting/api/v1/calls/{call.id}/match_client/',
            {'client_id': self.client_b.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        call.refresh_from_db()
        ticket.refresh_from_db()
        # Σε αποτυχία ΚΑΜΙΑ πλευρά δεν άλλαξε
        self.assertEqual(call.client_id, self.client_a.id)
        self.assertEqual(ticket.client_id, self.client_a.id)

    def test_auto_match_claims_linked_unassigned_ticket(self):
        call, ticket = self._pair(None)
        # Το τηλέφωνο ταιριάζει με τον client_a
        VoIPCall.objects.filter(pk=call.pk).update(phone_number='6971234567')
        call.refresh_from_db()
        resp = self.api(self.manager).post(
            f'/accounting/api/v1/calls/{call.id}/auto_match/')
        self.assertEqual(resp.status_code, 200, resp.content)
        call.refresh_from_db()
        ticket.refresh_from_db()
        self.assertEqual(call.client_id, self.client_a.id)
        self.assertEqual(ticket.client_id, self.client_a.id)

    def test_auto_match_skips_call_with_foreign_bound_ticket(self):
        # Κλήση unassigned, ticket bound στον B, τηλέφωνο ταιριάζει στον A
        call, ticket = self._pair(None, ticket_client=self.client_b)
        VoIPCall.objects.filter(pk=call.pk).update(phone_number='6971234567')
        call.refresh_from_db()
        resp = self.api(self.manager).post(
            f'/accounting/api/v1/calls/{call.id}/auto_match/')
        self.assertEqual(resp.status_code, 404)
        call.refresh_from_db()
        ticket.refresh_from_db()
        self.assertIsNone(call.client_id)
        self.assertEqual(ticket.client_id, self.client_b.id)

    def test_batch_auto_match_preserves_invariant(self):
        from accounting.phone_utils import batch_auto_match_calls
        call, ticket = self._pair(None, ticket_client=self.client_b)
        VoIPCall.objects.filter(pk=call.pk).update(phone_number='6971234567')
        batch_auto_match_calls(dry_run=False)
        call.refresh_from_db()
        ticket.refresh_from_db()
        # Δεν έγινε mismatch: ή έμεινε unassigned ή πήγε στον B
        if call.client_id is not None:
            self.assertEqual(call.client_id, ticket.client_id)
        else:
            self.assertEqual(ticket.client_id, self.client_b.id)

    def test_unassign_clears_client_email(self):
        call = VoIPCall.objects.create(
            call_id='svc-unassign', phone_number='2101111111',
            direction='incoming', status='missed',
            started_at=timezone.now(), client=self.client_b,
            client_email='b@example.com')
        resp = self.api(self.manager).patch(
            f'/accounting/api/v1/calls/{call.id}/',
            {'client_id': None}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        call.refresh_from_db()
        self.assertIsNone(call.client_id)
        self.assertEqual(call.client_email, '')


# ---------------------------------------------------------------------------
# Εύρημα 6: export/import, email API, myDATA, admin import — perm matrices
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class ExportImportMatrixTest(TestCase):
    client_class = SecureClient

    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='ΔΙΚΟΣ ΜΑΣ ΑΕ', eidos_ipoxreou='company')
        cls.foreign = ClientProfile.objects.create(
            afm='997654321', eponimia='ΞΕΝΟΣ ΑΕ', eidos_ipoxreou='company')

    def api(self, user):
        client = SecureAPIClient()
        client.force_authenticate(user)
        return client

    def test_export_obligations_requires_full_perm_set(self):
        url = '/accounting/api/v1/export/client-obligations/csv/'
        partial = make_perm_user(
            'exp_partial', ['view_clientprofile', 'export_clientprofile'])
        self.assertEqual(self.api(partial).get(url).status_code, 403)
        full = make_perm_user('exp_full', [
            'view_clientprofile', 'export_clientprofile',
            'view_clientobligation', 'view_obligationprofile',
            'view_obligationtype'])
        self.assertEqual(self.api(full).get(url).status_code, 200)

    def test_import_obligations_requires_clientobligation_perms(self):
        import io as io_mod
        url = '/accounting/api/v1/import/client-obligations/csv/'
        csv_bytes = 'ΑΦΜ,Profiles,Τύποι\n123456783,,\n'.encode('utf-8-sig')

        def _file():
            f = io_mod.BytesIO(csv_bytes)
            f.name = 'assignments.csv'
            return f

        partial = make_perm_user('impob_p', ['change_clientprofile'],
                                 [self.client_a])
        resp = self.api(partial).post(url, {'file': _file()},
                                      format='multipart')
        self.assertEqual(resp.status_code, 403)
        full = make_perm_user('impob_f', [
            'add_clientobligation', 'change_clientobligation',
            'view_obligationprofile', 'view_obligationtype'],
            [self.client_a])
        resp2 = self.api(full).post(url, {'file': _file()},
                                    format='multipart')
        self.assertEqual(resp2.status_code, 200, resp2.content)

    def test_client_import_does_not_reveal_foreign_afm(self):
        import io as io_mod
        try:
            import openpyxl
        except ImportError:
            self.skipTest('openpyxl not installed')
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['Α.Φ.Μ.', 'Επωνυμία/Επώνυμο'])
        ws.append(['997654321', 'ΝΕΟΣ ΜΕ ΞΕΝΟ ΑΦΜ'])
        buf = io_mod.BytesIO()
        wb.save(buf)
        buf.seek(0)
        buf.name = 'import.xlsx'
        scoped = make_perm_user(
            'impafm', ['add_clientprofile', 'change_clientprofile',
                       'view_clientprofile'], [self.client_a])
        resp = self.api(scoped).post(
            '/accounting/api/v1/import/clients/csv/',
            {'file': buf, 'mode': 'update'}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.content)
        body = str(resp.json())
        # Καμία διάκριση «εκτός ανάθεσης» — μόνο ουδέτερη αποτυχία
        self.assertNotIn('εκτός ανάθεσης', body)
        self.assertEqual(
            ClientProfile.objects.filter(afm='997654321').count(), 1)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class EmailPermMatrixTest(TestCase):
    client_class = SecureClient

    @classmethod
    def setUpTestData(cls):
        from accounting.models import EmailTemplate, MonthlyObligation, ObligationType
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='EMAIL ΑΕ', eidos_ipoxreou='company',
            email='a@example.com')
        cls.template = EmailTemplate.objects.create(
            name='T14', subject='Θέμα', body_html='Σώμα', is_active=True)
        ob_type = ObligationType.objects.create(name='ΦΠΑ14', is_active=True)
        cls.obligation = MonthlyObligation.objects.create(
            client=cls.client_a, obligation_type=ob_type, month=1, year=2026,
            deadline=timezone.now().date(), status='pending')

    def api(self, user):
        client = SecureAPIClient()
        client.force_authenticate(user)
        return client

    def test_preview_with_obligation_requires_view_monthlyobligation(self):
        user = make_perm_user(
            'em_prev', ['view_emailtemplate', 'view_clientprofile'],
            [self.client_a])
        resp = self.api(user).post('/accounting/api/v1/email/preview/', {
            'template_id': self.template.id,
            'obligation_id': self.obligation.id,
        }, format='json')
        self.assertEqual(resp.status_code, 403)
        user2 = make_perm_user(
            'em_prev2', ['view_emailtemplate', 'view_clientprofile',
                         'view_monthlyobligation'], [self.client_a])
        resp2 = self.api(user2).post('/accounting/api/v1/email/preview/', {
            'template_id': self.template.id,
            'obligation_id': self.obligation.id,
        }, format='json')
        self.assertEqual(resp2.status_code, 200, resp2.content)

    def test_send_requires_view_clientprofile(self):
        user = make_perm_user('em_send', ['send_client_email'],
                              [self.client_a])
        resp = self.api(user).post('/accounting/api/v1/email/send/', {
            'client_id': self.client_a.id, 'subject': 'Δ', 'body': 'Σ',
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_send_with_missing_template_is_4xx_not_500(self):
        user = make_perm_user(
            'em_tmpl', ['send_client_email', 'view_clientprofile',
                        'view_emailtemplate'], [self.client_a])
        resp = self.api(user).post('/accounting/api/v1/email/send/', {
            'client_id': self.client_a.id, 'template_id': 999999,
            'subject': 'Δ', 'body': 'Σ',
        }, format='json')
        self.assertIn(resp.status_code, (400, 404), resp.content)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class MyDataRound14Test(TestCase):
    client_class = SecureClient

    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='MYDATA ΑΕ', eidos_ipoxreou='company')

    def api(self, user):
        client = SecureAPIClient()
        client.force_authenticate(user)
        return client

    def _mixed_perm_user(self, username, accounting_perms, mydata_perms,
                         clients=()):
        user = User.objects.create_user(username, password='x')
        for codename in accounting_perms:
            user.user_permissions.add(Permission.objects.get(
                codename=codename, content_type__app_label='accounting'))
        for codename in mydata_perms:
            user.user_permissions.add(Permission.objects.get(
                codename=codename, content_type__app_label='mydata'))
        for c in clients:
            c.assigned_users.add(user)
        return User.objects.get(pk=user.pk)

    def test_dashboard_requires_view_clientprofile(self):
        user = self._mixed_perm_user(
            'md_novr', [], ['view_vatrecord'], [self.client_a])
        resp = self.api(user).get('/accounting/api/mydata/dashboard/')
        self.assertEqual(resp.status_code, 403)

    def test_dashboard_hides_credential_status_without_perm(self):
        from mydata.models import MyDataCredentials
        MyDataCredentials.objects.create(client=self.client_a)
        user = self._mixed_perm_user(
            'md_nocred', ['view_clientprofile'], ['view_vatrecord'],
            [self.client_a])
        resp = self.api(user).get('/accounting/api/mydata/dashboard/')
        self.assertEqual(resp.status_code, 200, resp.content)
        for entry in resp.json().get('clients', []):
            self.assertIsNone(entry.get('has_credentials'))
            self.assertIsNone(entry.get('is_verified'))

    def test_sync_bounds_and_credit_validation(self):
        from mydata.models import MyDataCredentials
        creds = MyDataCredentials.objects.create(client=self.client_a)
        manager = make_role_user('md_mgr', 'Διαχειριστής')
        api = self.api(manager)
        base = f'/accounting/api/mydata/credentials/{creds.id}'
        # Άκυρο days → 400 (όχι 500/command run)
        resp = api.post(f'{base}/sync/', {'days': 'πολλά'}, format='json')
        self.assertIn(resp.status_code, (400,), resp.content)
        resp2 = api.post(f'{base}/sync/', {'days': 99999}, format='json')
        self.assertEqual(resp2.status_code, 400)
        # InvalidOperation στο initial credit → 400 χωρίς exception text
        resp3 = api.post(f'{base}/set_initial_credit/',
                         {'initial_credit_balance': 'abc'}, format='json')
        self.assertEqual(resp3.status_code, 400, resp3.content)
        self.assertNotIn('InvalidOperation', str(resp3.content))


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class AdminImportPermTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def test_see_all_without_write_perms_cannot_import(self):
        from django.contrib import admin as django_admin
        from django.contrib.messages.storage.fallback import FallbackStorage
        from accounting.models import ClientProfile as CP
        factory = RequestFactory()
        admin_instance = django_admin.site._registry[CP]
        # Χρήστης με view_all_clients αλλά ΧΩΡΙΣ add/change_clientprofile
        user = make_perm_user('adm_seeall', ['view_all_clients'])
        user.is_staff = True
        user.save()
        request = factory.get('/import/')
        request.user = User.objects.get(pk=user.pk)
        request.session = {}
        request._messages = FallbackStorage(request)
        with self.assertRaises(DjangoPermissionDenied):
            admin_instance.import_view(request)


class ErrorLeakageTest(TestCase):
    client_class = SecureClient

    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def test_import_error_has_no_exception_markers(self):
        import io as io_mod
        manager = make_role_user('leak_mgr', 'Διαχειριστής')
        api = SecureAPIClient()
        api.force_authenticate(manager)
        garbage = io_mod.BytesIO(b'\x00\x01 not an excel file')
        garbage.name = 'x.xlsx'
        resp = api.post('/accounting/api/v1/import/clients/csv/',
                        {'file': garbage}, format='multipart')
        self.assertEqual(resp.status_code, 400)
        body = str(resp.json())
        for marker in ('Traceback', 'Exception', 'zipfile', 'BadZip',
                       'openpyxl'):
            self.assertNotIn(marker, body)
