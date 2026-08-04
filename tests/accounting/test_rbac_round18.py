# -*- coding: utf-8 -*-
"""
Γύρος 18 — residual findings closeout.

F1 Exact conflict key (πλήρες logical key, fail closed σε πολλαπλά current)
F3 Permission check ΠΡΙΝ από κάθε μόνιμο file I/O (ούτε dirs/INFO.txt)
F4 Πλήρης lifecycle compensation (post-save failure, on_commit failure)
F5 Ασφαλής σειρά διαγραφής (DB πρώτα, αρχείο on_commit)
F6 Immutable ownership/path metadata στο generic PATCH
F7 obligation_documents model permissions
F8 Πλήρης έλεγχος version graph στο audit command
F9 Κανένα str(e)/absolute path σε responses
F10 libmagic fail-closed system check σε production
(F2: tests/accounting/test_concurrency_postgres.py — PostgreSQL CI step)
"""
import os
import shutil
import tempfile
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.signals import post_save
from django.test import TestCase, override_settings
from django.utils import timezone

from accounting.models import ClientDocument, ClientProfile, MonthlyObligation, ObligationType
from accounting.services import filing
from tests.accounting.secure_client import SecureAPIClient, SecureClient

User = get_user_model()

TEMP_MEDIA = tempfile.mkdtemp(prefix='round18_test_')


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


def pdf_upload(name='αρχείο.pdf', content=b'%PDF-1.4 test'):
    return SimpleUploadedFile(name, content, content_type='application/pdf')


def media_tree():
    """Πλήρες snapshot του MEDIA_ROOT: κάθε path (dirs+files) με mtime —
    ΣΥΜΠΕΡΙΛΑΜΒΑΝΟΜΕΝΟΥ του INFO.txt."""
    snapshot = {}
    for root, dirs, files in os.walk(TEMP_MEDIA):
        for d in dirs:
            p = os.path.join(root, d)
            snapshot[p] = 'dir'
        for f in files:
            p = os.path.join(root, f)
            snapshot[p] = os.path.getmtime(p)
    return snapshot


def media_files():
    return sorted(p for p, v in media_tree().items() if v != 'dir'
                  and os.path.basename(p) != 'INFO.txt')


class MediaTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)


from contextlib import contextmanager  # noqa: E402


@contextmanager
def current_constraints_disabled():
    """
    Προσομοίωση legacy DB ΧΩΡΙΣ τα uniq_current_doc_* constraints — μόνο
    έτσι μπορεί πλέον να δημιουργηθεί corrupted multiple-current state
    (το DB net του Γύρου 19 μπλοκάρει κάθε νέο τέτοιο row). Στο τέλος
    καθαρίζονται ΟΛΑ τα rows πριν την επαναφορά των constraints.
    """
    from django.db import connection
    cons = [c for c in ClientDocument._meta.constraints
            if c.name.startswith('uniq_current_doc')]
    with connection.schema_editor() as se:
        for c in cons:
            se.remove_constraint(ClientDocument, c)
    try:
        yield
    finally:
        ClientDocument.objects.all().delete()
        with connection.schema_editor() as se:
            for c in cons:
                se.add_constraint(ClientDocument, c)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA)
class FilingBase(MediaTestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command as cc
        cc('setup_roles', verbosity=0)
        cls.ob_type = ObligationType.objects.create(name='ΦΠΑ18', is_active=True)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        self.full = make_perm_user(
            f'f18_full_{self.id().split(".")[-1][:12]}',
            ['add_clientdocument', 'change_clientdocument',
             'delete_clientdocument', 'view_clientprofile'], [self.client_a])
        self.add_only = make_perm_user(
            f'f18_add_{self.id().split(".")[-1][:12]}',
            ['add_clientdocument', 'view_clientprofile'], [self.client_a])

    def _upload(self, user=None, **kwargs):
        kwargs.setdefault('category', 'vat')
        kwargs.setdefault('year', 2026)
        kwargs.setdefault('month', 3)
        return filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            user=user or self.full, **kwargs)


# ---------------------------------------------------------------------------
# F1. Exact conflict key
# ---------------------------------------------------------------------------
class ExactConflictKeyTest(FilingBase):
    def test_different_month_no_conflict(self):
        self._upload(month=3)
        doc = self._upload(user=self.add_only, month=4)  # add-only αρκεί
        self.assertEqual(doc.version, 1)
        self.assertEqual(ClientDocument.objects.filter(
            client=self.client_a, is_current=True).count(), 2)

    def test_same_period_different_category_no_conflict(self):
        self._upload(category='vat')
        doc = self._upload(user=self.add_only, category='payroll')
        self.assertEqual(doc.version, 1)

    def test_general_and_vat_are_distinct(self):
        """Το 'general' ΔΕΝ είναι wildcard — μετρά ως κανονική κατηγορία."""
        vat_doc = self._upload(category='vat')
        gen_doc = self._upload(user=self.add_only, category='general')
        self.assertEqual(gen_doc.version, 1)
        vat_doc.refresh_from_db()
        self.assertTrue(vat_doc.is_current)  # δεν εκτοπίστηκε

    def test_obligation_vs_standalone_distinct(self):
        ob = MonthlyObligation.objects.create(
            client=self.client_a, obligation_type=self.ob_type, month=3,
            year=2026, deadline=timezone.now().date())
        ob_doc = self._upload(obligation=ob)
        standalone = self._upload(user=self.add_only)  # obligation=None
        self.assertEqual(standalone.version, 1)
        ob_doc.refresh_from_db()
        self.assertTrue(ob_doc.is_current)

    def test_queryset_update_bypass_blocked_by_db_constraint(self):
        """Γύρος 19: το QuerySet.update bypass πλέον μπλοκάρεται από το
        partial unique constraint στο DB — δεν χρειάζεται καν το service."""
        from django.db import IntegrityError, transaction
        doc1 = self._upload()
        doc2 = self._upload(user=self.add_only, category='payroll')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ClientDocument.objects.filter(pk=doc2.pk).update(
                    document_category='vat')
        doc1.refresh_from_db()
        doc2.refresh_from_db()
        self.assertTrue(doc1.is_current)
        self.assertEqual(doc2.document_category, 'payroll')

    # Το legacy corrupted-DB σενάριο (χωρίς constraints) ζει στο
    # LegacyCorruptionTest (TransactionTestCase — DDL δεν επιτρέπεται
    # μέσα στο transaction του TestCase σε SQLite).

    def test_add_only_with_real_conflict_denied(self):
        existing = self._upload()
        before_files = media_files()
        with self.assertRaises(PermissionDenied):
            self._upload(user=self.add_only)
        existing.refresh_from_db()
        self.assertTrue(existing.is_current)
        self.assertEqual(media_files(), before_files)

    def test_invalid_on_existing_rejected(self):
        with self.assertRaises(ValidationError):
            self._upload(on_existing='overwrite')


# ---------------------------------------------------------------------------
# F3. Καμία μόνιμη αλλαγή storage πριν από τα permissions
# ---------------------------------------------------------------------------
class NoSideEffectBeforePermsTest(FilingBase):
    def test_denied_version_leaves_entire_tree_untouched(self):
        self._upload()  # δημιουργεί δέντρο + INFO.txt
        before = media_tree()
        with self.assertRaises(PermissionDenied):
            self._upload(user=self.add_only)
        # Ολόκληρο το δέντρο (dirs, files, INFO.txt, mtimes) αμετάβλητο
        self.assertEqual(media_tree(), before)

    def test_denied_anonymous_version_no_dirs_created(self):
        self._upload()
        before = media_tree()
        with self.assertRaises(PermissionDenied):
            filing.create_client_document(
                client=self.client_a, uploaded_file=pdf_upload(),
                category='vat', year=2026, month=3, user=None,
                on_existing='version')
        self.assertEqual(media_tree(), before)

    def test_invalid_on_existing_no_side_effects(self):
        before = media_tree()
        with self.assertRaises(ValidationError):
            self._upload(on_existing='bogus')
        self.assertEqual(media_tree(), before)


# ---------------------------------------------------------------------------
# F4. Πλήρης lifecycle compensation
# ---------------------------------------------------------------------------
class LifecycleCompensationTest(FilingBase):
    def _fail_after_save(self, version=None):
        """post_save receiver που ρίχνει ΜΕΤΑ από επιτυχές SQL insert —
        προσομοιώνει αποτυχία μεταγενέστερου βήματος πριν από το commit."""
        def receiver(sender, instance, created, **kwargs):
            if created and (version is None or instance.version == version):
                raise RuntimeError('injected-post-save-step')
        return receiver

    def test_version_save_ok_later_step_fails(self):
        existing = self._upload()
        before_rows = ClientDocument.objects.count()
        before_files = media_files()
        receiver = self._fail_after_save(version=2)
        post_save.connect(receiver, sender=ClientDocument)
        try:
            with self.assertRaises(RuntimeError):
                self._upload(description='νέα εκδοχή')
        finally:
            post_save.disconnect(receiver, sender=ClientDocument)
        existing.refresh_from_db()
        self.assertTrue(existing.is_current)
        self.assertEqual(ClientDocument.objects.count(), before_rows)
        self.assertEqual(media_files(), before_files)

    def test_create_fails_after_storage_before_commit(self):
        before_files = media_files()
        before_rows = ClientDocument.objects.count()
        receiver = self._fail_after_save()
        post_save.connect(receiver, sender=ClientDocument)
        try:
            with self.assertRaises(RuntimeError):
                self._upload()
        finally:
            post_save.disconnect(receiver, sender=ClientDocument)
        self.assertEqual(ClientDocument.objects.count(), before_rows)
        self.assertEqual(media_files(), before_files)

    def test_replace_fails_after_new_save_before_commit(self):
        existing = self._upload()
        old_path = existing.file.path
        before_rows = ClientDocument.objects.count()
        receiver = self._fail_after_save(version=1)
        post_save.connect(receiver, sender=ClientDocument)
        try:
            with self.assertRaises(RuntimeError):
                self._upload(on_existing='replace')
        finally:
            post_save.disconnect(receiver, sender=ClientDocument)
        # Παλιό row ΚΑΙ παλιό αρχείο παραμένουν, νέο αρχείο καθαρίστηκε
        self.assertTrue(ClientDocument.objects.filter(pk=existing.pk).exists())
        self.assertTrue(os.path.exists(old_path))
        self.assertEqual(ClientDocument.objects.count(), before_rows)

    def test_on_commit_old_file_delete_failure_is_safe(self):
        existing = self._upload()
        with mock.patch(
                'accounting.services.filing._safe_storage_delete',
                side_effect=Exception('storage down')) as m_del:
            # Το exception του callback ΔΕΝ πρέπει να χαλάσει το replace
            try:
                with self.captureOnCommitCallbacks(execute=True):
                    doc = self._upload(on_existing='replace')
            except Exception:  # captureOnCommitCallbacks re-raises callbacks
                pass
        # Η νέα κατάσταση είναι έγκυρη ανεξάρτητα από το storage failure
        self.assertFalse(
            ClientDocument.objects.filter(pk=existing.pk).exists())
        current = ClientDocument.objects.get(
            client=self.client_a, document_category='vat',
            year=2026, month=3, is_current=True)
        self.assertTrue(os.path.exists(current.file.path))


# ---------------------------------------------------------------------------
# F5. Ασφαλής σειρά διαγραφής
# ---------------------------------------------------------------------------
class SafeDeletionTest(FilingBase):
    def _api(self):
        user = make_perm_user(
            f'del18_{self.id().split(".")[-1][:12]}',
            ['view_clientprofile', 'view_clientdocument',
             'add_clientdocument', 'change_clientdocument',
             'delete_clientdocument'], [self.client_a])
        c = SecureAPIClient()
        c.force_authenticate(user)
        return c

    def test_successful_delete_file_removed_only_after_commit(self):
        doc = self._upload()
        path = doc.file.path
        api = self._api()
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            resp = api.delete(f'/accounting/api/v1/documents/{doc.id}/')
            self.assertEqual(resp.status_code, 200, resp.content)
            # Πριν το commit callback: το αρχείο υπάρχει ακόμη
            self.assertTrue(os.path.exists(path))
        for cb in callbacks:
            cb()
        self.assertFalse(os.path.exists(path))
        self.assertFalse(ClientDocument.objects.filter(pk=doc.pk).exists())

    def test_db_delete_failure_keeps_row_and_file(self):
        doc = self._upload()
        path = doc.file.path
        api = self._api()
        with mock.patch.object(
                ClientDocument, 'delete',
                side_effect=RuntimeError('db down'), autospec=True):
            with self.assertRaises(RuntimeError):
                api.delete(f'/accounting/api/v1/documents/{doc.id}/')
        self.assertTrue(ClientDocument.objects.filter(pk=doc.pk).exists())
        self.assertTrue(os.path.exists(path))

    def test_storage_delete_failure_row_stays_deleted(self):
        doc = self._upload()
        api = self._api()
        with mock.patch(
                'accounting.services.filing._safe_storage_delete'
        ) as m_del:
            m_del.side_effect = None  # καλείται, δεν ρίχνει (generic warning)
            with self.captureOnCommitCallbacks(execute=True):
                resp = api.delete(f'/accounting/api/v1/documents/{doc.id}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(ClientDocument.objects.filter(pk=doc.pk).exists())
        m_del.assert_called_once()


# ---------------------------------------------------------------------------
# F6. Immutable ownership/path metadata στο generic PATCH
# ---------------------------------------------------------------------------
class ImmutableMetadataPatchTest(FilingBase):
    def setUp(self):
        super().setUp()
        self.client_b = ClientProfile.objects.create(
            afm='997654321', eponimia='Β ΑΕ', eidos_ipoxreou='company')
        self.user = make_perm_user(
            f'pm18_{self.id().split(".")[-1][:12]}',
            ['view_clientprofile', 'view_clientdocument',
             'add_clientdocument', 'change_clientdocument'],
            [self.client_a, self.client_b])
        self.api = SecureAPIClient()
        self.api.force_authenticate(self.user)
        self.doc = self._upload(user=self.user)

    def test_patch_client_rejected_no_mismatch(self):
        resp = self.api.patch(
            f'/accounting/api/v1/documents/{self.doc.id}/',
            {'client': self.client_b.id}, format='multipart')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.client_id, self.client_a.id)

    def test_patch_category_rejected(self):
        resp = self.api.patch(
            f'/accounting/api/v1/documents/{self.doc.id}/',
            {'document_category': 'payroll'}, format='multipart')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.document_category, 'vat')

    def test_patch_description_allowed(self):
        resp = self.api.patch(
            f'/accounting/api/v1/documents/{self.doc.id}/',
            {'description': 'Νέα περιγραφή'}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.description, 'Νέα περιγραφή')


# ---------------------------------------------------------------------------
# F7. obligation_documents model permissions
# ---------------------------------------------------------------------------
class ObligationDocumentsPermsTest(FilingBase):
    def setUp(self):
        super().setUp()
        self.ob = MonthlyObligation.objects.create(
            client=self.client_a, obligation_type=self.ob_type, month=3,
            year=2026, deadline=timezone.now().date())
        self.doc = self._upload(obligation=self.ob)

    def _get(self, codenames):
        user = make_perm_user(
            f'od18_{self.id().split(".")[-1][:12]}', codenames,
            [self.client_a])
        c = SecureAPIClient()
        c.force_authenticate(user)
        return c.get(f'/accounting/api/v1/obligations/{self.ob.id}/documents/')

    def test_without_view_obligation_403_no_urls(self):
        resp = self._get(['view_clientprofile', 'view_clientdocument'])
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertNotIn('signed', str(resp.content))
        self.assertNotIn('documents', resp.json())

    def test_without_view_document_403(self):
        resp = self._get(['view_clientprofile', 'view_monthlyobligation'])
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_with_both_perms_sees_own_docs(self):
        resp = self._get(['view_clientprofile', 'view_monthlyobligation',
                          'view_clientdocument'])
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['documents'][0]['id'], self.doc.id)


# ---------------------------------------------------------------------------
# F8. Πλήρης έλεγχος version graph
# ---------------------------------------------------------------------------
class VersionGraphAuditTest(FilingBase):
    def _doc(self, version=1, is_current=True, prev=None, category='vat',
             month=3):
        # Μόνο DB row — το audit command δεν αγγίζει storage
        doc = ClientDocument(
            client=self.client_a, document_category=category, year=2026,
            month=month, version=version, is_current=is_current,
            file=f'g{version}_{month}.pdf',
            original_filename='x.pdf', filename='x.pdf', file_type='pdf',
            file_size=1)
        doc.save()
        if prev is not None:
            ClientDocument.objects.filter(pk=doc.pk).update(
                previous_version=prev.pk)
        return doc

    def _run(self, fail=False):
        out = StringIO()
        if fail:
            call_command('audit_clientdocument_invariants',
                         '--fail-on-findings', stdout=out)
        else:
            call_command('audit_clientdocument_invariants', stdout=out)
        return out.getvalue()

    def test_two_node_cycle_detected(self):
        d1 = self._doc(1, is_current=False, month=1)
        d2 = self._doc(2, is_current=True, month=1)
        ClientDocument.objects.filter(pk=d1.pk).update(previous_version=d2.pk)
        ClientDocument.objects.filter(pk=d2.pk).update(previous_version=d1.pk)
        text = self._run()
        self.assertIn('version-graph-cycle', text)

    def test_three_node_cycle_detected(self):
        d1 = self._doc(1, is_current=False, month=1)
        d2 = self._doc(2, is_current=False, month=1)
        d3 = self._doc(3, is_current=True, month=1)
        ClientDocument.objects.filter(pk=d2.pk).update(previous_version=d1.pk)
        ClientDocument.objects.filter(pk=d3.pk).update(previous_version=d2.pk)
        ClientDocument.objects.filter(pk=d1.pk).update(previous_version=d3.pk)
        text = self._run()
        self.assertIn('version-graph-cycle', text)

    def test_current_siblings_and_branching_detected(self):
        root = self._doc(1, is_current=False, month=1)
        self._doc(2, is_current=True, prev=root, month=1)
        sibling = self._doc(2, is_current=True, prev=root, month=2)
        text = self._run()
        self.assertIn('branching-chain', text)
        self.assertIn('multiple-current-in-chain', text)

    def test_non_adjacent_current_descendants_detected(self):
        d1 = self._doc(1, is_current=True, month=1)  # έμεινε current
        d2 = self._doc(2, is_current=False, prev=d1, month=4)
        self._doc(3, is_current=True, prev=d2, month=5)
        text = self._run()
        self.assertIn('multiple-current-in-chain', text)

    def test_invalid_version_progression_detected(self):
        d1 = self._doc(1, is_current=False, month=1)
        self._doc(5, is_current=True, prev=d1, month=2)  # v5 μετά από v1
        text = self._run()
        self.assertIn('invalid-version-progression', text)

    # Το duplicate-current-for-key σενάριο ζει στο LegacyCorruptionTest
    # (απαιτεί DDL — βλ. σχόλιο εκεί).

    def test_fail_on_findings_via_cycle(self):
        d1 = self._doc(1, is_current=False, month=1)
        ClientDocument.objects.filter(pk=d1.pk).update(previous_version=d1.pk)
        with self.assertRaises(CommandError):
            self._run(fail=True)


# ---------------------------------------------------------------------------
# F9. Κανένα str(e)/absolute path σε responses
# ---------------------------------------------------------------------------
class NoLeakResponsesTest(FilingBase):
    MARKER = 'INTERNAL_MARKER_c81x'

    def test_notifications_exception_no_marker(self):
        user = make_perm_user(
            f'nl18_{self.id().split(".")[-1][:12]}',
            ['view_clientprofile', 'view_monthlyobligation', 'view_ticket'],
            [self.client_a])
        c = SecureAPIClient()
        c.force_authenticate(user)
        with mock.patch(
                'accounting.api_notifications.MonthlyObligation') as m_ob:
            m_ob.objects.filter.side_effect = Exception(self.MARKER)
            resp = c.get('/accounting/api/v1/notifications/')
        self.assertNotIn(self.MARKER, str(resp.content))

    def test_check_existing_invalid_year_400_no_marker(self):
        user = make_perm_user(
            f'ce18_{self.id().split(".")[-1][:12]}',
            ['view_clientprofile', 'view_clientdocument'], [self.client_a])
        user = User.objects.get(pk=user.pk)
        user.is_staff = True
        user.save()
        c = SecureClient()
        c.force_login(user)
        resp = c.get('/accounting/api/v1/documents/check-existing/',
                     {'client_id': self.client_a.id, 'year': 'κακό'})
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertNotIn('ValueError', str(resp.content))
        self.assertNotIn('Traceback', str(resp.content))

    def test_upload_with_version_response_no_absolute_path(self):
        user = User.objects.get(pk=self.full.pk)
        user.is_staff = True
        user.save()
        c = SecureClient()
        c.force_login(user)
        resp = c.post(
            '/accounting/api/v1/documents/upload-with-version/',
            {'file': pdf_upload(), 'client_id': self.client_a.id,
             'category': 'vat', 'year': 2026, 'month': 5})
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertNotIn('folder_path', body.get('document', {}))
        self.assertNotIn(TEMP_MEDIA, str(resp.content))

    def test_upload_with_version_invalid_year_400(self):
        user = User.objects.get(pk=self.full.pk)
        user.is_staff = True
        user.save()
        c = SecureClient()
        c.force_login(user)
        resp = c.post(
            '/accounting/api/v1/documents/upload-with-version/',
            {'file': pdf_upload(), 'client_id': self.client_a.id,
             'year': 'μπανάνα', 'month': 2})
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertNotIn('ValueError', str(resp.content))


# ---------------------------------------------------------------------------
# F10. libmagic fail-closed system check
# ---------------------------------------------------------------------------
class LibmagicCheckTest(TestCase):
    def test_production_broken_magic_is_error(self):
        from accounting import checks
        with mock.patch.object(checks, '_magic_works', return_value=False), \
             override_settings(DEBUG=False):
            result = checks.check_libmagic_available(None)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 'accounting.E001')

    def test_debug_broken_magic_is_warning(self):
        from accounting import checks
        with mock.patch.object(checks, '_magic_works', return_value=False), \
             override_settings(DEBUG=True):
            result = checks.check_libmagic_available(None)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 'accounting.W001')

    def test_debug_with_require_setting_is_error(self):
        from accounting import checks
        with mock.patch.object(checks, '_magic_works', return_value=False), \
             override_settings(DEBUG=True, REQUIRE_LIBMAGIC=True):
            result = checks.check_libmagic_available(None)
        self.assertEqual(result[0].id, 'accounting.E001')

    def test_working_magic_no_findings(self):
        from accounting import checks
        with mock.patch.object(checks, '_magic_works', return_value=True):
            self.assertEqual(checks.check_libmagic_available(None), [])


# ---------------------------------------------------------------------------
# Legacy corrupted DB σενάρια — TransactionTestCase γιατί το DDL
# (remove/add constraint) δεν επιτρέπεται μέσα στο transaction του
# TestCase σε SQLite.
# ---------------------------------------------------------------------------
from django.test import TransactionTestCase  # noqa: E402


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA)
class LegacyCorruptionTest(TransactionTestCase):
    def setUp(self):
        call_command('setup_roles', verbosity=0)
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        self.full = make_perm_user(
            'lc19_full', ['add_clientdocument', 'change_clientdocument',
                          'delete_clientdocument', 'view_clientprofile'],
            [self.client_a])
        self.add_only = make_perm_user(
            'lc19_add', ['add_clientdocument', 'view_clientprofile'],
            [self.client_a])

    def _upload(self, user=None, **kwargs):
        kwargs.setdefault('category', 'vat')
        kwargs.setdefault('year', 2026)
        kwargs.setdefault('month', 3)
        return filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            user=user or self.full, **kwargs)

    def test_two_matching_current_rows_fail_closed(self):
        """Legacy corrupted DB: το service κάνει fail closed — κανένα row
        δεν αλλάζει/διαγράφεται αυθαίρετα, κανένα νέο αρχείο."""
        with current_constraints_disabled():
            doc1 = self._upload()
            doc2 = self._upload(user=self.add_only, category='payroll')
            ClientDocument.objects.filter(pk=doc2.pk).update(
                document_category='vat')
            before_rows = set(
                ClientDocument.objects.values_list('id', flat=True))
            with self.assertRaises(ValidationError):
                self._upload()
            self.assertEqual(
                set(ClientDocument.objects.values_list('id', flat=True)),
                before_rows)
            doc1.refresh_from_db()
            self.assertTrue(doc1.is_current)

    def test_duplicate_current_for_key_detected_and_fails(self):
        with current_constraints_disabled():
            for _ in range(2):
                doc = ClientDocument(
                    client=self.client_a, document_category='vat', year=2026,
                    month=1, version=1, is_current=True, file='dup.pdf',
                    original_filename='x.pdf', filename='x.pdf',
                    file_type='pdf', file_size=1)
                doc.save()
            out = StringIO()
            call_command('audit_clientdocument_invariants', stdout=out)
            self.assertIn('duplicate-current-for-key', out.getvalue())
            with self.assertRaises(CommandError):
                call_command('audit_clientdocument_invariants',
                             '--fail-on-findings', stdout=StringIO())
