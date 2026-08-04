# -*- coding: utf-8 -*-
"""
Γύρος 23 — ευρήματα ανεξάρτητου review πάνω στο 5387a94.

P1. Atomic revocation για ΟΛΑ τα SharedLinks (και τα unlimited):
    `try_record_access()` με τον κοινό `_revocation_guard_q()` σε
    preview/download/έκδοση access token.
P1. myDATA `_sync_period_months()` — δομημένο αποτέλεσμα· ποτέ ψευδές
    success=True σε ολική/μερική αποτυχία, ποτέ σιωπηλή χρήση stale data.
P2. `obligation_upload_file` — MultipleCurrentDocumentsError → 409.
"""
import shutil
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from accounting.models import (
    ClientDocument, ClientProfile, MonthlyObligation, ObligationType,
    SharedLink, SharedLinkAccess,
)
from accounting.services import filing
from tests.accounting.secure_client import SecureAPIClient

User = get_user_model()

TEMP_MEDIA = tempfile.mkdtemp(prefix='round23_test_')


def tearDownModule():
    shutil.rmtree(TEMP_MEDIA, ignore_errors=True)


def pdf_upload(name='αρχείο.pdf', content=b'%PDF-1.4 test payload'):
    return SimpleUploadedFile(name, content, content_type='application/pdf')


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


# ===========================================================================
# P1 — Atomic revocation και για UNLIMITED links
# ===========================================================================
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA)
class UnlimitedLinkAtomicAccessTest(TestCase):
    """
    Links ΧΩΡΙΣ max_downloads περνούσαν από μη-atomic `record_access()`:
    ανάκληση/λήξη/αλλαγή ρυθμίσεων ανάμεσα στο αρχικό validation και στην
    απόκριση δεν εμπόδιζε την επιστροφή αρχείου ή access token.
    """

    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        self.user = make_perm_user(
            'r23_link', ['add_clientdocument', 'view_clientprofile'],
            [self.client_a])
        self.doc = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=3, user=self.user)
        # UNLIMITED: κανένα max_downloads
        self.link = SharedLink.objects.create(
            document=self.doc, access_level='download', max_downloads=None)
        self.web = SecureAPIClient()

    def _revoke(self, **fields):
        SharedLink.objects.filter(pk=self.link.pk).update(**fields)

    def _counts(self):
        link = SharedLink.objects.get(pk=self.link.pk)
        return (link.view_count, link.download_count,
                SharedLinkAccess.objects.filter(shared_link=link).count())

    # --- try_record_access: ο guard ισχύει και χωρίς όριο λήψεων ---

    def test_record_access_rejected_after_deactivation(self):
        self._revoke(is_active=False)
        self.assertFalse(self.link.try_record_access())
        self.assertEqual(self._counts(), (0, 0, 0))

    def test_record_access_rejected_after_expiry(self):
        self._revoke(expires_at=timezone.now() - timezone.timedelta(hours=1))
        self.assertFalse(self.link.try_record_access())
        self.assertEqual(self._counts(), (0, 0, 0))

    def test_record_access_rejected_after_token_regeneration(self):
        from accounting.models import generate_share_token
        self._revoke(token=generate_share_token())
        self.assertFalse(self.link.try_record_access())

    def test_record_access_rejected_after_password_change(self):
        self._revoke(password_hash='pbkdf2_sha256$νέο')
        self.assertFalse(self.link.try_record_access())

    def test_record_access_rejected_after_requires_email_change(self):
        self._revoke(requires_email=True)
        self.assertFalse(self.link.try_record_access())

    def test_record_access_rejected_after_target_change(self):
        other = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=4, user=self.user)
        self._revoke(document=other)
        self.assertFalse(self.link.try_record_access())

    def test_record_access_rejected_after_access_level_change(self):
        self._revoke(access_level='view')
        self.assertFalse(self.link.try_record_access())

    def test_record_access_succeeds_on_valid_link(self):
        self.assertTrue(self.link.try_record_access())
        views, downloads, _ = self._counts()
        self.assertEqual((views, downloads), (1, 0))

    # --- Δημόσιες διαδρομές: κανένα περιεχόμενο/token μετά την ανάκληση ---

    def test_public_get_returns_no_token_after_revocation(self):
        """
        Ανάκληση ΑΦΟΥ περάσει το αρχικό validation: το view δεν πρέπει να
        εκδώσει access token ούτε να γράψει success access log.
        """
        real_guard = SharedLink._revocation_guard_q

        def revoke_then_guard(link_self):
            SharedLink.objects.filter(pk=self.link.pk).update(is_active=False)
            return real_guard(link_self)

        with mock.patch.object(SharedLink, '_revocation_guard_q',
                               revoke_then_guard):
            resp = self.web.get(f'/accounting/share/{self.link.token}/')

        self.assertEqual(resp.status_code, 410)
        self.assertNotIn('access_token', resp.data)
        self.assertEqual(self._counts(), (0, 0, 0))

    def test_unlimited_preview_rejected_after_revocation(self):
        real_guard = SharedLink._revocation_guard_q

        def revoke_then_guard(link_self):
            SharedLink.objects.filter(pk=self.link.pk).update(is_active=False)
            return real_guard(link_self)

        with mock.patch.object(SharedLink, '_revocation_guard_q',
                               revoke_then_guard):
            resp = self.web.get(
                f'/accounting/share/{self.link.token}/preview/')

        self.assertEqual(resp.status_code, 410)
        # Κανένα byte, κανένας counter, κανένα log
        self.assertEqual(self._counts(), (0, 0, 0))

    def test_unlimited_preview_succeeds_when_link_valid(self):
        resp = self.web.get(f'/accounting/share/{self.link.token}/preview/')
        try:
            self.assertEqual(resp.status_code, 200)
            views, downloads, logs = self._counts()
            self.assertEqual(views, 1)
            self.assertEqual(downloads, 0)     # unlimited: όχι quota
            self.assertEqual(logs, 1)
        finally:
            resp.close()

    def test_public_get_issues_token_when_link_valid(self):
        resp = self.web.get(f'/accounting/share/{self.link.token}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access_token', resp.data)
        views, _, logs = self._counts()
        self.assertEqual((views, logs), (1, 1))


# ===========================================================================
# P2 — obligation_upload_file: 409 σε multiple current
# ===========================================================================
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA)
class ObligationUploadConflictTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        ob_type = ObligationType.objects.create(
            name='ΦΠΑ23', code='FPA23', is_active=True)
        self.ob = MonthlyObligation.objects.create(
            client=self.client_a, obligation_type=ob_type, month=3,
            year=2026, deadline=timezone.now().date())
        self.user = make_perm_user(
            'r23_up',
            ['add_clientdocument', 'change_clientdocument',
             'view_clientdocument', 'view_clientprofile',
             'view_monthlyobligation', 'change_monthlyobligation'],
            [self.client_a])
        self.user.is_staff = True
        self.user.save()
        self.web = SecureAPIClient()
        self.web.force_login(self.user)

    def test_multiple_current_returns_409_without_side_effects(self):
        url = f'/accounting/obligations/{self.ob.id}/upload/'
        before_docs = ClientDocument.objects.count()

        with mock.patch(
                'accounting.services.filing.find_current_for_key',
                side_effect=filing.MultipleCurrentDocumentsError(
                    'Πολλαπλά τρέχοντα έγγραφα')):
            resp = self.web.post(url, {'file': pdf_upload()})

        self.assertEqual(resp.status_code, 409, resp.content[:200])
        body = resp.json()
        self.assertFalse(body['success'])
        # Ουδέτερο μήνυμα — κανένα path/filename/ΑΦΜ/raw exception
        self.assertNotIn('Traceback', body['error'])
        self.assertNotIn(self.client_a.afm, body['error'])
        # Κανένα partial write, καμία ολοκλήρωση υποχρέωσης
        self.assertEqual(ClientDocument.objects.count(), before_docs)
        self.ob.refresh_from_db()
        self.assertNotEqual(self.ob.status, 'completed')

    def test_plain_validation_error_still_400(self):
        url = f'/accounting/obligations/{self.ob.id}/upload/'
        resp = self.web.post(url, {'file': SimpleUploadedFile(
            'κακό.exe', b'MZ binary', content_type='application/exe')})
        self.assertEqual(resp.status_code, 400)

    def test_valid_upload_still_succeeds(self):
        url = f'/accounting/obligations/{self.ob.id}/upload/'
        resp = self.web.post(url, {'file': pdf_upload()})
        self.assertEqual(resp.status_code, 200, resp.content[:200])
        self.assertEqual(ClientDocument.objects.count(), 1)


# ===========================================================================
# P1 — myDATA sync: δομημένο αποτέλεσμα, ποτέ ψευδές success
# ===========================================================================
class _SyncBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def setUp(self):
        from mydata.models import VATPeriodResult
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        self.user = User.objects.create_user('r23_mydata', password='x',
                                             is_staff=True)
        for codename, app in (('sync_vatdata', 'mydata'),
                              ('view_vatperiodresult', 'mydata'),
                              ('change_vatperiodresult', 'mydata'),
                              ('view_clientprofile', 'accounting')):
            try:
                self.user.user_permissions.add(Permission.objects.get(
                    codename=codename, content_type__app_label=app))
            except Permission.DoesNotExist:
                pass
        self.client_a.assigned_users.add(self.user)
        self.user = User.objects.get(pk=self.user.pk)
        # Quarterly ώστε να υπάρχουν 3 μήνες (χρειάζεται για το partial)
        self.period = VATPeriodResult.objects.create(
            client=self.client_a, year=2026, period_type='quarterly',
            period=1)
        self.api = SecureAPIClient()
        self.api.force_authenticate(self.user)

    def _view(self):
        from mydata.views import VATPeriodResultViewSet
        return VATPeriodResultViewSet()


class SyncPeriodMonthsResultTest(_SyncBase):
    """Το `_sync_period_months` επιστρέφει δομημένο, ειλικρινές αποτέλεσμα."""

    def test_missing_credentials_reported_as_failed(self):
        result = self._view()._sync_period_months(self.period)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['reason'], 'missing_credentials')
        self.assertEqual(result['successful_months'], [])
        self.assertTrue(result['failed_months'])

    def _with_credentials(self):
        from mydata.models import MyDataCredentials
        creds = MyDataCredentials(client=self.client_a)
        creds.user_id = 'test-user'
        creds.subscription_key = 'test-key'
        creds.save()
        self.client_a.refresh_from_db()
        return creds

    def test_authentication_failure_reported(self):
        self._with_credentials()
        with mock.patch('django.core.management.call_command',
                        side_effect=CommandError('401 Unauthorized')):
            result = self._view()._sync_period_months(self.period)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['reason'], 'authentication')
        self.assertEqual(result['successful_months'], [])

    def test_total_api_failure_reported(self):
        self._with_credentials()
        with mock.patch('django.core.management.call_command',
                        side_effect=CommandError('service unavailable')):
            result = self._view()._sync_period_months(self.period)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['reason'], 'api_failure')

    def test_partial_failure_reported(self):
        self._with_credentials()
        self.assertGreaterEqual(len(self.period.months_in_period), 2)
        calls = {'n': 0}

        def flaky(*args, **kwargs):
            calls['n'] += 1
            if calls['n'] == 1:
                raise CommandError('service unavailable')
            return None

        with mock.patch('django.core.management.call_command',
                        side_effect=flaky):
            result = self._view()._sync_period_months(self.period)
        self.assertEqual(result['status'], 'partial')
        self.assertTrue(result['failed_months'])
        self.assertTrue(result['successful_months'])

    def test_full_success_reported(self):
        self._with_credentials()
        with mock.patch('django.core.management.call_command',
                        return_value=None):
            result = self._view()._sync_period_months(self.period)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['failed_months'], [])
        self.assertEqual(result['reason'], '')


class CalculateSyncStatusTest(_SyncBase):
    """Το endpoint δεν παρουσιάζει ποτέ αποτυχημένο sync ως επιτυχία."""

    def _calculate(self, sync_result):
        url = f'/accounting/api/mydata/periods/{self.period.id}/calculate/'
        with mock.patch(
                'mydata.views.VATPeriodResultViewSet._sync_period_months',
                return_value=sync_result):
            return self.api.post(url, {'sync_first': True}, format='json')

    def test_failed_sync_blocks_calculation(self):
        resp = self._calculate({
            'status': 'failed', 'reason': 'api_failure',
            'successful_months': [], 'failed_months': [3], 'errors': ['x'],
        })
        self.assertIn(resp.status_code, (422, 502), resp.content[:200])
        self.assertFalse(resp.data['success'])
        self.assertEqual(resp.data['sync_status'], 'failed')

    def test_missing_credentials_returns_422(self):
        resp = self._calculate({
            'status': 'failed', 'reason': 'missing_credentials',
            'successful_months': [], 'failed_months': [3], 'errors': ['x'],
        })
        self.assertEqual(resp.status_code, 422)

    def test_partial_sync_is_flagged_not_silent(self):
        resp = self._calculate({
            'status': 'partial', 'reason': 'api_failure',
            'successful_months': [1], 'failed_months': [2], 'errors': ['x'],
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['sync_status'], 'partial')
        self.assertIn('warning', resp.data)
        self.assertEqual(resp.data['failed_months'], [2])

    def test_successful_sync_reports_success(self):
        resp = self._calculate({
            'status': 'success', 'reason': '',
            'successful_months': [1, 2, 3], 'failed_months': [], 'errors': [],
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['sync_status'], 'success')
        self.assertNotIn('warning', resp.data)

    def test_audit_records_failure_not_success(self):
        from common.models import AuditLog
        self._calculate({
            'status': 'failed', 'reason': 'api_failure',
            'successful_months': [], 'failed_months': [3], 'errors': ['x'],
        })
        entry = AuditLog.objects.filter(model_name='MyDataSync').last()
        self.assertIsNotNone(entry)
        self.assertIn('αποτυχία', entry.description)
        self.assertNotIn('επιτυχία', entry.description)

    def test_unrecognised_sync_result_is_treated_as_failure(self):
        """
        Fail-closed: αν το _sync_period_months επιστρέψει κάτι μη
        αναγνωρίσιμο (None, σκέτο object), ΔΕΝ θεωρείται επιτυχία και
        δεν εκτελείται υπολογισμός πάνω σε stale δεδομένα.
        """
        for bogus in (None, 'ok', 123, {}, {'status': 'weird'}):
            with self.subTest(result=bogus):
                resp = self._calculate(bogus)
                self.assertIn(resp.status_code, (422, 502),
                              f'{bogus!r} → {resp.status_code}')
                self.assertFalse(resp.data['success'])
                self.assertEqual(resp.data['sync_status'], 'failed')

    def test_audit_records_partial_as_failure(self):
        from common.models import AuditLog
        self._calculate({
            'status': 'partial', 'reason': 'api_failure',
            'successful_months': [1], 'failed_months': [2], 'errors': ['x'],
        })
        entry = AuditLog.objects.filter(model_name='MyDataSync').last()
        self.assertIsNotNone(entry)
        self.assertIn('αποτυχία', entry.description)
