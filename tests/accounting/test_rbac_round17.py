# -*- coding: utf-8 -*-
"""
Γύρος 17 — final document/storage/myDATA authorization closeout.

1. Generic ClientDocument upload bypass κλειστό (405 / read-only file /
   dangerous content / oversized → κανένα row, κανένα storage file)
2. Permission matrix create/version/replace (add / add+change /
   add+change+delete) σε όλες τις filing διαδρομές
3. Storage/DB lifecycle: failure injection → no orphans, παλιό αρχείο/row
   διατηρούνται, ποτέ δύο current versions
4. mydata.sync_vatdata σε ΚΑΘΕ external VAT sync endpoint + audit
5. Strict boolean parsing (sync_first κ.λπ.) — "false"/"0" → όχι sync,
   άκυρη τιμή → 400
6. Dashboard: καμία credential-existence διαρροή χωρίς view_mydatacredentials
7. DocumentRequest: send_client_email βάσει requested flag, όχι ύπαρξης email
8. audit_clientdocument_invariants command (report-only, --fail-on-findings)
9. Attachment resolver hardening (string ids, duplicates, missing file)
"""
import os
import shutil
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from io import StringIO

from accounting.models import ClientDocument, ClientProfile, MonthlyObligation, ObligationType
from accounting.services import filing
from tests.accounting.secure_client import SecureAPIClient, SecureClient

User = get_user_model()

TEMP_MEDIA = tempfile.mkdtemp(prefix='round17_test_')


def make_role_user(username, role, clients=(), **extra):
    user = User.objects.create_user(username=username, password='x', **extra)
    user.groups.add(Group.objects.get(name=role))
    for c in clients:
        c.assigned_users.add(user)
    return User.objects.get(pk=user.pk)


def make_perm_user(username, codenames, clients=()):
    user = User.objects.create_user(username=username, password='x')
    for codename in codenames:
        app = 'accounting'
        if '.' in codename:
            app, codename = codename.split('.', 1)
        user.user_permissions.add(Permission.objects.get(
            codename=codename, content_type__app_label=app))
    for c in clients:
        c.assigned_users.add(user)
    return User.objects.get(pk=user.pk)


def media_files():
    """Λίστα φυσικών αρχείων στο MEDIA_ROOT (χωρίς INFO.txt)."""
    out = []
    for root, _dirs, files in os.walk(TEMP_MEDIA):
        for f in files:
            if f != 'INFO.txt':
                out.append(os.path.join(root, f))
    return sorted(out)


def pdf_upload(name='αρχείο.pdf', content=b'%PDF-1.4 test'):
    return SimpleUploadedFile(name, content, content_type='application/pdf')


class MediaTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)


# ---------------------------------------------------------------------------
# 1. Generic upload bypass
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA)
class GenericUploadBypassTest(MediaTestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        self.user = make_perm_user(
            'gu_full', ['view_clientprofile', 'view_clientdocument',
                        'add_clientdocument', 'change_clientdocument',
                        'delete_clientdocument'], [self.client_a])
        self.api = SecureAPIClient()
        self.api.force_authenticate(self.user)

    def test_generic_post_returns_405_no_row_no_file(self):
        before_rows = ClientDocument.objects.count()
        before_files = media_files()
        resp = self.api.post(
            '/accounting/api/v1/documents/',
            {'client': self.client_a.id, 'file': pdf_upload()},
            format='multipart')
        self.assertEqual(resp.status_code, 405, resp.content)
        self.assertEqual(ClientDocument.objects.count(), before_rows)
        self.assertEqual(media_files(), before_files)

    def test_generic_patch_file_rejected_no_mutation(self):
        doc = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(), user=self.user)
        old_name = doc.file.name
        resp = self.api.patch(
            f'/accounting/api/v1/documents/{doc.id}/',
            {'file': pdf_upload('άλλο.pdf', b'%PDF-1.4 other')},
            format='multipart')
        self.assertEqual(resp.status_code, 400, resp.content)
        doc.refresh_from_db()
        self.assertEqual(doc.file.name, old_name)

    def test_upload_html_disguised_as_pdf_rejected(self):
        before_rows = ClientDocument.objects.count()
        before_files = media_files()
        bad = SimpleUploadedFile(
            'έγγραφο.pdf',
            b'<!DOCTYPE html><html><script>alert(1)</script></html>',
            content_type='application/pdf')
        resp = self.api.post(
            '/accounting/api/v1/documents/upload/',
            {'file': bad, 'client_id': self.client_a.id},
            format='multipart')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(ClientDocument.objects.count(), before_rows)
        self.assertEqual(media_files(), before_files)

    def test_upload_oversized_rejected_no_row_no_file(self):
        before_rows = ClientDocument.objects.count()
        before_files = media_files()
        big = SimpleUploadedFile(
            'μεγάλο.pdf', b'%PDF-1.4' + b'0' * (11 * 1024 * 1024),
            content_type='application/pdf')
        resp = self.api.post(
            '/accounting/api/v1/documents/upload/',
            {'file': big, 'client_id': self.client_a.id},
            format='multipart')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(ClientDocument.objects.count(), before_rows)
        self.assertEqual(media_files(), before_files)

    def test_official_upload_action_still_works(self):
        resp = self.api.post(
            '/accounting/api/v1/documents/upload/',
            {'file': pdf_upload(), 'client_id': self.client_a.id},
            format='multipart')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(ClientDocument.objects.filter(
            client=self.client_a).count(), 1)

    def test_attach_document_upload_goes_through_filing(self):
        """Το upload branch του attach-document περνά από το filing —
        dangerous content απορρίπτεται και εκεί (πριν: direct create)."""
        ob_type = ObligationType.objects.create(name='ΦΠΑ17a', is_active=True)
        ob = MonthlyObligation.objects.create(
            client=self.client_a, obligation_type=ob_type, month=1,
            year=2026, deadline=timezone.now().date())
        before_rows = ClientDocument.objects.count()
        bad = SimpleUploadedFile(
            'x.pdf', b'<html><body>not a pdf</body></html>',
            content_type='application/pdf')
        resp = self.api.post(
            f'/accounting/api/v1/obligations/{ob.id}/attach-document/',
            {'file': bad}, format='multipart')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(ClientDocument.objects.count(), before_rows)


# ---------------------------------------------------------------------------
# 2. Permission matrix create/version/replace
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA)
class MutationPermMatrixTest(MediaTestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        self.add_only = make_perm_user(
            'pm_add', ['add_clientdocument', 'view_clientprofile'],
            [self.client_a])
        self.add_change = make_perm_user(
            'pm_addch', ['add_clientdocument', 'change_clientdocument',
                         'view_clientprofile'], [self.client_a])
        self.full = make_perm_user(
            'pm_full', ['add_clientdocument', 'change_clientdocument',
                        'delete_clientdocument', 'view_clientprofile'],
            [self.client_a])

    def _seed(self, user):
        return filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(), category='vat',
            user=user)

    def test_add_only_creates_new_document(self):
        doc = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='payroll', user=self.add_only)
        self.assertTrue(doc.is_current)
        self.assertEqual(doc.version, 1)

    def test_add_only_cannot_version(self):
        existing = self._seed(self.full)
        before_rows = ClientDocument.objects.count()
        before_files = media_files()
        with self.assertRaises(PermissionDenied):
            filing.create_client_document(
                client=self.client_a, uploaded_file=pdf_upload(),
                category='vat', user=self.add_only, on_existing='version')
        existing.refresh_from_db()
        self.assertTrue(existing.is_current)
        self.assertEqual(ClientDocument.objects.count(), before_rows)
        self.assertEqual(media_files(), before_files)

    def test_add_change_can_version(self):
        existing = self._seed(self.full)
        doc = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', user=self.add_change, on_existing='version')
        existing.refresh_from_db()
        self.assertFalse(existing.is_current)
        self.assertTrue(doc.is_current)
        self.assertEqual(doc.version, 2)
        self.assertEqual(doc.previous_version_id, existing.id)

    def test_add_change_cannot_replace(self):
        existing = self._seed(self.full)
        old_file = existing.file.name
        before_rows = ClientDocument.objects.count()
        before_files = media_files()
        with self.assertRaises(PermissionDenied):
            filing.create_client_document(
                client=self.client_a, uploaded_file=pdf_upload(),
                category='vat', user=self.add_change, on_existing='replace')
        existing.refresh_from_db()
        self.assertTrue(existing.is_current)
        self.assertEqual(existing.file.name, old_file)
        self.assertEqual(ClientDocument.objects.count(), before_rows)
        self.assertEqual(media_files(), before_files)

    def test_full_perms_can_replace(self):
        existing = self._seed(self.full)
        old_pk = existing.pk
        with self.captureOnCommitCallbacks(execute=True):
            doc = filing.create_client_document(
                client=self.client_a, uploaded_file=pdf_upload(),
                category='vat', user=self.full, on_existing='replace')
        self.assertFalse(ClientDocument.objects.filter(pk=old_pk).exists())
        self.assertTrue(doc.is_current)
        self.assertEqual(doc.version, 1)

    def test_anonymous_user_never_versions(self):
        """user=None (portal) επιτρέπεται μόνο για create — ποτέ version."""
        self._seed(self.full)
        with self.assertRaises(PermissionDenied):
            filing.create_client_document(
                client=self.client_a, uploaded_file=pdf_upload(),
                category='vat', user=None, on_existing='version')

    def test_endpoint_add_only_version_403(self):
        """Το matrix ισχύει και μέσω HTTP (upload-with-version)."""
        self._seed(self.full)
        user = User.objects.get(pk=self.add_only.pk)
        user.is_staff = True
        user.save()
        c = SecureClient()
        c.force_login(user)
        resp = c.post(
            '/accounting/api/v1/documents/upload-with-version/',
            {'file': pdf_upload(), 'client_id': self.client_a.id,
             'category': 'vat', 'version_action': 'new_version'})
        self.assertEqual(resp.status_code, 403, resp.content)


# ---------------------------------------------------------------------------
# 3. Storage/DB lifecycle — failure injection
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA)
class LifecycleFailureInjectionTest(MediaTestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        self.user = make_perm_user(
            'lf_full', ['add_clientdocument', 'change_clientdocument',
                        'delete_clientdocument', 'view_clientprofile'],
            [self.client_a])

    def _seed(self):
        return filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', user=self.user)

    def test_failure_before_model_save_no_row_no_file(self):
        before_files = media_files()
        before_rows = ClientDocument.objects.count()
        with mock.patch.object(
                ClientDocument, 'save',
                side_effect=RuntimeError('injected-pre-save'), autospec=True):
            with self.assertRaises(RuntimeError):
                filing.create_client_document(
                    client=self.client_a, uploaded_file=pdf_upload(),
                    category='payroll', user=self.user)
        self.assertEqual(ClientDocument.objects.count(), before_rows)
        self.assertEqual(media_files(), before_files)

    def test_failure_after_storage_before_commit_cleans_orphan(self):
        before_files = media_files()
        before_rows = ClientDocument.objects.count()
        real_save = ClientDocument.save

        def save_then_fail(self_doc, *a, **k):
            real_save(self_doc, *a, **k)  # γράφει αρχείο + row
            raise RuntimeError('injected-post-save')

        with mock.patch.object(ClientDocument, 'save', save_then_fail):
            with self.assertRaises(RuntimeError):
                filing.create_client_document(
                    client=self.client_a, uploaded_file=pdf_upload(),
                    category='payroll', user=self.user)
        # Rollback του row + compensating cleanup του αρχείου
        self.assertEqual(ClientDocument.objects.count(), before_rows)
        self.assertEqual(media_files(), before_files)

    def test_version_failure_old_stays_current_no_orphan(self):
        existing = self._seed()
        before_files = media_files()
        before_rows = ClientDocument.objects.count()
        real_save = ClientDocument.save

        def save_then_fail(self_doc, *a, **k):
            real_save(self_doc, *a, **k)
            raise RuntimeError('injected-version')

        with mock.patch.object(ClientDocument, 'save', save_then_fail):
            with self.assertRaises(RuntimeError):
                filing.create_client_document(
                    client=self.client_a, uploaded_file=pdf_upload(),
                    category='vat', user=self.user, on_existing='version')
        existing.refresh_from_db()
        self.assertTrue(existing.is_current)
        self.assertEqual(ClientDocument.objects.count(), before_rows)
        self.assertEqual(media_files(), before_files)

    def test_replace_failure_keeps_old_row_and_file(self):
        existing = self._seed()
        old_file_path = existing.file.path
        before_rows = ClientDocument.objects.count()
        real_save = ClientDocument.save

        def save_then_fail(self_doc, *a, **k):
            real_save(self_doc, *a, **k)
            raise RuntimeError('injected-replace')

        with mock.patch.object(ClientDocument, 'save', save_then_fail):
            with self.assertRaises(RuntimeError):
                filing.create_client_document(
                    client=self.client_a, uploaded_file=pdf_upload(),
                    category='vat', user=self.user, on_existing='replace')
        # Παλιό row ΚΑΙ παλιό φυσικό αρχείο παραμένουν
        self.assertTrue(ClientDocument.objects.filter(pk=existing.pk).exists())
        self.assertTrue(os.path.exists(old_file_path))
        self.assertEqual(ClientDocument.objects.count(), before_rows)

    def test_replace_success_deletes_old_file_only_after_commit(self):
        existing = self._seed()
        old_file_path = existing.file.path
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            filing.create_client_document(
                client=self.client_a, uploaded_file=pdf_upload(),
                category='vat', user=self.user, on_existing='replace')
        self.assertTrue(callbacks)  # η διαγραφή προγραμματίστηκε on_commit
        self.assertFalse(os.path.exists(old_file_path))

    def test_stale_version_attempt_never_two_current(self):
        existing = self._seed()
        existing.create_new_version(new_file=pdf_upload(), user=self.user)
        # Δεύτερο attempt πάνω στο ΙΔΙΟ (πλέον stale) αντικείμενο
        stale = ClientDocument.objects.get(pk=existing.pk)
        stale.is_current = True  # προσομοίωση stale in-memory state
        with self.assertRaises(ValidationError):
            stale.create_new_version(new_file=pdf_upload(), user=self.user)
        currents = ClientDocument.objects.filter(
            client=self.client_a, document_category='vat', is_current=True)
        self.assertEqual(currents.count(), 1)


# ---------------------------------------------------------------------------
# 4. myDATA sync permission παντού
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class MyDataSyncPermEverywhereTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        cls.client_b = ClientProfile.objects.create(
            afm='997654321', eponimia='Β ΑΕ', eidos_ipoxreou='company')

    def setUp(self):
        from mydata.models import MyDataCredentials
        self.creds_a = MyDataCredentials.objects.create(client=self.client_a)
        self.creds_b = MyDataCredentials.objects.create(client=self.client_b)

    def api(self, user):
        c = SecureAPIClient()
        c.force_authenticate(user)
        return c

    def _sync(self, user, creds):
        from mydata.models import MyDataCredentials
        with mock.patch('django.core.management.call_command') as m_cmd, \
             mock.patch.object(MyDataCredentials, 'has_credentials',
                               new_callable=mock.PropertyMock,
                               return_value=True):
            resp = self.api(user).post(
                f'/accounting/api/mydata/credentials/{creds.id}/sync/',
                {'days': 30}, format='json')
        return resp, m_cmd

    def test_change_creds_without_sync_perm_403_no_call(self):
        user = make_perm_user(
            'sy_nosync', ['view_clientprofile',
                          'mydata.change_mydatacredentials',
                          'mydata.view_mydatacredentials'], [self.client_a])
        resp, m_cmd = self._sync(user, self.creds_a)
        self.assertEqual(resp.status_code, 403, resp.content)
        m_cmd.assert_not_called()

    def test_sync_perm_scoped_client_success_audit(self):
        from common.models import AuditLog
        user = make_perm_user(
            'sy_ok', ['view_clientprofile',
                      'mydata.change_mydatacredentials',
                      'mydata.view_mydatacredentials',
                      'mydata.sync_vatdata'], [self.client_a])
        before = AuditLog.objects.filter(model_name='MyDataSync').count()
        resp, m_cmd = self._sync(user, self.creds_a)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(m_cmd.call_count, 1)
        audits = AuditLog.objects.filter(model_name='MyDataSync')
        self.assertEqual(audits.count(), before + 1)
        self.assertNotIn(self.client_a.afm, audits.latest('id').description)

    def test_sync_foreign_client_neutral_404_no_call(self):
        user = make_perm_user(
            'sy_foreign', ['view_clientprofile',
                           'mydata.change_mydatacredentials',
                           'mydata.view_mydatacredentials',
                           'mydata.sync_vatdata'], [self.client_a])
        resp, m_cmd = self._sync(user, self.creds_b)
        self.assertEqual(resp.status_code, 404, resp.content)
        m_cmd.assert_not_called()

    def test_assistant_403_no_side_effects(self):
        assistant = make_role_user('sy_assist', 'Βοηθός', [self.client_a])
        resp, m_cmd = self._sync(assistant, self.creds_a)
        self.assertEqual(resp.status_code, 403, resp.content)
        m_cmd.assert_not_called()


# ---------------------------------------------------------------------------
# 5. Strict boolean parsing για sync_first
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class StrictBoolSyncFirstTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')

    def _user(self, name, with_sync):
        perms = ['view_clientprofile', 'mydata.change_vatperiodresult',
                 'mydata.view_vatperiodresult']
        if with_sync:
            perms.append('mydata.sync_vatdata')
        return make_perm_user(name, perms, [self.client_a])

    def _calc(self, user, payload):
        from mydata.models import VATPeriodResult
        period = VATPeriodResult.objects.create(
            client=self.client_a, year=2026,
            period=VATPeriodResult.objects.count() + 1,
            period_type='monthly')
        c = SecureAPIClient()
        c.force_authenticate(user)
        # Ο stub δηλώνει ΕΠΙΤΥΧΗ συγχρονισμό — το test αφορά το αυστηρό
        # boolean parsing του `sync_first` (πόσες φορές καλείται το sync),
        # όχι την έκβασή του (Γύρος 23: δομημένο αποτέλεσμα).
        with mock.patch(
                'mydata.views.VATPeriodResultViewSet._sync_period_months',
                return_value={'status': 'success', 'reason': '',
                              'successful_months': [1],
                              'failed_months': [], 'errors': []}
        ) as m_sync:
            resp = c.post(
                f'/accounting/api/mydata/periods/{period.id}/calculate/',
                payload, format='json')
        return resp, m_sync

    def test_json_false_no_sync(self):
        resp, m_sync = self._calc(self._user('sb1', True), {'sync_first': False})
        self.assertEqual(resp.status_code, 200, resp.content)
        m_sync.assert_not_called()

    def test_string_false_no_sync(self):
        resp, m_sync = self._calc(self._user('sb2', True), {'sync_first': 'false'})
        self.assertEqual(resp.status_code, 200, resp.content)
        m_sync.assert_not_called()

    def test_string_zero_no_sync(self):
        resp, m_sync = self._calc(self._user('sb3', True), {'sync_first': '0'})
        self.assertEqual(resp.status_code, 200, resp.content)
        m_sync.assert_not_called()

    def test_true_without_perm_403(self):
        resp, m_sync = self._calc(self._user('sb4', False), {'sync_first': True})
        self.assertEqual(resp.status_code, 403, resp.content)
        m_sync.assert_not_called()

    def test_true_with_perm_one_sync_one_audit(self):
        from common.models import AuditLog
        before = AuditLog.objects.filter(model_name='MyDataSync').count()
        resp, m_sync = self._calc(self._user('sb5', True), {'sync_first': True})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(m_sync.call_count, 1)
        self.assertEqual(
            AuditLog.objects.filter(model_name='MyDataSync').count(),
            before + 1)

    def test_invalid_value_400_not_500(self):
        resp, m_sync = self._calc(self._user('sb6', True),
                                  {'sync_first': 'μπανάνα'})
        self.assertEqual(resp.status_code, 400, resp.content)
        m_sync.assert_not_called()


# ---------------------------------------------------------------------------
# 6. Dashboard credential-existence side channel
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class DashboardSideChannelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='ΜΕ CREDS', eidos_ipoxreou='company')
        cls.client_b = ClientProfile.objects.create(
            afm='997654321', eponimia='ΧΩΡΙΣ CREDS', eidos_ipoxreou='company')
        cls.foreign = ClientProfile.objects.create(
            afm='111111110', eponimia='ΞΕΝΟΣ', eidos_ipoxreou='company')

    def setUp(self):
        from mydata.models import MyDataCredentials
        MyDataCredentials.objects.create(client=self.client_a)

    def _get(self, user):
        c = SecureAPIClient()
        c.force_authenticate(user)
        resp = c.get('/accounting/api/mydata/dashboard/')
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()

    def test_without_perm_membership_does_not_leak(self):
        user = make_perm_user(
            'ds_noperm', ['view_clientprofile', 'mydata.view_vatrecord'],
            [self.client_a, self.client_b])
        body = self._get(user)
        afms = {c['client_afm'] for c in body['clients']}
        # ΚΑΙ οι δύο προσβάσιμοι πελάτες εμφανίζονται — η λίστα δεν
        # αποκαλύπτει ποιος έχει credentials row
        self.assertEqual(afms, {self.client_a.afm, self.client_b.afm})
        for entry in body['clients']:
            self.assertIsNone(entry['has_credentials'])
            self.assertIsNone(entry['is_verified'])
            self.assertIsNone(entry['last_sync'])
        self.assertIsNone(body['overview']['clients_with_credentials'])

    def test_with_perm_fields_present(self):
        user = make_perm_user(
            'ds_perm', ['view_clientprofile', 'mydata.view_vatrecord',
                        'mydata.view_mydatacredentials'],
            [self.client_a, self.client_b])
        body = self._get(user)
        by_afm = {c['client_afm']: c for c in body['clients']}
        self.assertIsNotNone(by_afm[self.client_a.afm]['has_credentials'])
        self.assertIsNotNone(by_afm[self.client_b.afm]['has_credentials'])
        self.assertEqual(body['overview']['clients_with_credentials'], 1)

    def test_foreign_clients_never_listed(self):
        user = make_perm_user(
            'ds_scope', ['view_clientprofile', 'mydata.view_vatrecord',
                         'mydata.view_mydatacredentials'], [self.client_a])
        body = self._get(user)
        afms = {c['client_afm'] for c in body['clients']}
        self.assertNotIn(self.foreign.afm, afms)
        self.assertNotIn(self.client_b.afm, afms)


# ---------------------------------------------------------------------------
# 7. DocumentRequest send_email authorization
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, PORTAL_EMAIL_SYNC=True,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class DocumentRequestSendEmailTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def setUp(self):
        self.no_email_client = ClientProfile.objects.create(
            afm='123456783', eponimia='ΧΩΡΙΣ EMAIL', eidos_ipoxreou='company')
        self.email_client = ClientProfile.objects.create(
            afm='997654321', eponimia='ΜΕ EMAIL', eidos_ipoxreou='company',
            email='c@example.com')

    def api(self, user):
        c = SecureAPIClient()
        c.force_authenticate(user)
        return c

    def _payload(self, client, **over):
        data = {'client_id': client.id, 'title': 'Αίτημα',
                'items': [{'label': 'Τιμολόγιο', 'category': ''}]}
        data.update(over)
        return data

    def _user(self, name, send_perm, clients):
        perms = ['view_clientprofile', 'add_documentrequest',
                 'add_sharedlink', 'view_documentrequest']
        if send_perm:
            perms.append('send_client_email')
        return make_perm_user(name, perms, clients)

    def test_send_true_no_client_email_no_perm_403_zero_rows(self):
        from accounting.models import DocumentRequest, SharedLink
        user = self._user('dr1', False, [self.no_email_client])
        resp = self.api(user).post(
            '/accounting/api/v1/document-requests/',
            self._payload(self.no_email_client, send_email=True),
            format='json')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertEqual(DocumentRequest.objects.count(), 0)
        self.assertEqual(SharedLink.objects.count(), 0)

    def test_send_false_without_perm_allowed(self):
        from accounting.models import DocumentRequest
        user = self._user('dr2', False, [self.no_email_client])
        resp = self.api(user).post(
            '/accounting/api/v1/document-requests/',
            self._payload(self.no_email_client, send_email=False),
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(DocumentRequest.objects.count(), 1)

    def test_send_true_perm_no_email_created_without_dispatch(self):
        user = self._user('dr3', True, [self.no_email_client])
        with mock.patch(
                'accounting.tasks.send_document_request_email') as m_task:
            with self.captureOnCommitCallbacks(execute=True):
                resp = self.api(user).post(
                    '/accounting/api/v1/document-requests/',
                    self._payload(self.no_email_client, send_email=True),
                    format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertFalse(resp.json()['email_sent'])
        m_task.assert_not_called()

    def test_send_true_perm_with_email_one_dispatch(self):
        user = self._user('dr4', True, [self.email_client])
        with mock.patch(
                'accounting.tasks.send_document_request_email') as m_task:
            with self.captureOnCommitCallbacks(execute=True):
                resp = self.api(user).post(
                    '/accounting/api/v1/document-requests/',
                    self._payload(self.email_client, send_email=True),
                    format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(resp.json()['email_sent'])
        self.assertEqual(m_task.call_count, 1)


# ---------------------------------------------------------------------------
# 8. audit_clientdocument_invariants command
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class InvariantAuditCommandTest(MediaTestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.ob_type = ObligationType.objects.create(name='ΦΠΑ17b', is_active=True)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company',
            email='a@example.com')
        self.client_b = ClientProfile.objects.create(
            afm='997654321', eponimia='Β ΑΕ', eidos_ipoxreou='company',
            email='b@example.com')
        self.ob_b = MonthlyObligation.objects.create(
            client=self.client_b, obligation_type=self.ob_type, month=1,
            year=2026, deadline=timezone.now().date())
        self.user = make_perm_user(
            'ia_full', ['add_clientdocument', 'view_clientprofile'],
            [self.client_a, self.client_b])
        self.doc = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', user=self.user)
        # Corrupt row μέσω QuerySet.update — παρακάμπτει το save guard
        ClientDocument.objects.filter(pk=self.doc.pk).update(
            obligation=self.ob_b)

    def test_command_detects_corrupt_row(self):
        out = StringIO()
        call_command('audit_clientdocument_invariants', stdout=out)
        text = out.getvalue()
        self.assertIn('cross-client-obligation', text)
        self.assertIn(f'document id={self.doc.pk}', text)
        # Χωρίς πλήρες ΑΦΜ ή filename στα ευρήματα
        self.assertNotIn(self.client_a.afm, text)
        self.assertNotIn(self.doc.filename, text)

    def test_fail_on_findings_raises(self):
        with self.assertRaises(CommandError):
            call_command('audit_clientdocument_invariants',
                         '--fail-on-findings', stdout=StringIO())

    def test_clean_db_passes(self):
        ClientDocument.objects.all().delete()
        out = StringIO()
        call_command('audit_clientdocument_invariants', '--fail-on-findings',
                     stdout=out)
        self.assertIn('συνεπή', out.getvalue())

    def test_email_path_does_not_use_inconsistent_document(self):
        """Το corrupt doc (client A, obligation B) ΔΕΝ επισυνάπτεται σε
        email του πελάτη Β — ο resolver φιλτράρει με client."""
        from django.core import mail
        sender = make_perm_user(
            'ia_send', ['send_client_email', 'view_clientprofile',
                        'view_clientdocument'], [self.client_a, self.client_b])
        sender = User.objects.get(pk=sender.pk)
        sender.is_staff = True
        sender.save()
        mail.outbox = []
        c = SecureClient()
        c.force_login(sender)
        resp = c.post('/accounting/api/v1/email/send/',
                      data={'client_id': self.client_b.id, 'subject': 'S',
                            'body': 'B', 'attachment_ids': [self.doc.pk]},
                      content_type='application/json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(len(mail.outbox), 0)


# ---------------------------------------------------------------------------
# 9. Attachment resolver hardening
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ResolverHardeningTest(MediaTestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company',
            email='a@example.com')
        self.user = make_perm_user(
            'rh_user', ['send_client_email', 'view_clientprofile',
                        'view_clientdocument', 'add_clientdocument'],
            [self.client_a])
        self.user = User.objects.get(pk=self.user.pk)
        self.user.is_staff = True
        self.user.save()
        self.doc = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', user=self.user)

    def _send(self, attachment_ids):
        from django.core import mail
        mail.outbox = []
        c = SecureClient()
        c.force_login(self.user)
        resp = c.post('/accounting/api/v1/email/send/',
                      data={'client_id': self.client_a.id, 'subject': 'S',
                            'body': 'B', 'attachment_ids': attachment_ids},
                      content_type='application/json')
        return resp, mail.outbox

    def test_string_ids_rejected_direct(self):
        from django.test.client import RequestFactory
        from accounting.services.access import (
            AttachmentResolutionError, resolve_email_attachment_documents,
        )
        req = RequestFactory().post('/x')
        req.user = self.user
        with self.assertRaises(AttachmentResolutionError):
            resolve_email_attachment_documents(
                req, self.client_a, str(self.doc.pk))

    def test_duplicate_ids_attach_once(self):
        resp, outbox = self._send([self.doc.pk, self.doc.pk])
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(outbox), 1)
        self.assertEqual(len(outbox[0].attachments), 1)

    def test_missing_physical_file_rejects_whole_request(self):
        self.doc.file.storage.delete(self.doc.file.name)
        resp, outbox = self._send([self.doc.pk])
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(len(outbox), 0)
        # Το μήνυμα δεν αποκαλύπτει ΠΟΙΟ ID ήταν το πρόβλημα
        self.assertNotIn(str(self.doc.pk), resp.json().get('error', ''))
