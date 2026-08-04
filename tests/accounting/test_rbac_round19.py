# -*- coding: utf-8 -*-
"""
Γύρος 19 — production-ready hardening closeout.

1. Κεντρικό invariant «ένα current ανά exact key» + DB partial unique
   constraints (με slot για τα portal 'keep' uploads)
2. Attach/detach μέσω κοινού transactional service (locks, exact target-key
   conflict, controlled 409, audit)
3. Ενιαίος exact-conflict helper (find_current_for_key) παντού
4. 'keep' → μοναδικό slot: ποτέ δεύτερο current στο ίδιο key, ποτέ
   εκτοπισμός εγγράφων γραφείου
5. Πλήρες input validation (year/month/category/on_existing) πριν από
   lock/storage — 400, ποτέ 500
6. Production fail-closed libmagic στην πραγματική upload διαδρομή
7. Επέκταση invariant audit (cross-key edges, zero-current, roots,
   duplicate versions, current-not-terminal)
8. Πολιτική διαγραφής versioned documents (descendants → 400, current →
   προαγωγή προηγούμενης)
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
from django.test import TestCase, override_settings
from django.utils import timezone

from accounting.models import ClientDocument, ClientProfile, MonthlyObligation, ObligationType
from accounting.services import filing
from tests.accounting.secure_client import SecureAPIClient, SecureClient

User = get_user_model()

TEMP_MEDIA = tempfile.mkdtemp(prefix='round19_test_')


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
    snapshot = {}
    for root, dirs, files in os.walk(TEMP_MEDIA):
        for d in dirs:
            snapshot[os.path.join(root, d)] = 'dir'
        for f in files:
            p = os.path.join(root, f)
            snapshot[p] = os.path.getmtime(p)
    return snapshot


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA)
class Round19Base(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.ob_type = ObligationType.objects.create(name='ΦΠΑ19', is_active=True)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        self.full = make_perm_user(
            f'r19_{self.id().split(".")[-1][:16]}',
            ['add_clientdocument', 'change_clientdocument',
             'delete_clientdocument', 'view_clientdocument',
             'view_clientprofile', 'view_monthlyobligation'],
            [self.client_a])
        self.api = SecureAPIClient()
        self.api.force_authenticate(self.full)

    def _ob(self, month=3, year=2026, client=None):
        return MonthlyObligation.objects.create(
            client=client or self.client_a, obligation_type=self.ob_type,
            month=month, year=year, deadline=timezone.now().date())

    def _upload(self, user=None, **kwargs):
        kwargs.setdefault('category', 'vat')
        kwargs.setdefault('year', 2026)
        kwargs.setdefault('month', 3)
        return filing.create_client_document(
            client=kwargs.pop('client', self.client_a),
            uploaded_file=pdf_upload(), user=user or self.full, **kwargs)


# ---------------------------------------------------------------------------
# 1+2. Attach/detach service + invariant
# ---------------------------------------------------------------------------
class AttachDetachServiceTest(Round19Base):
    def test_attach_to_occupied_exact_key_409(self):
        ob = self._ob()
        self._upload(obligation=ob)          # κατέχει το key με obligation
        standalone = self._upload()          # ίδιο category/period, χωρίς ob
        before = media_tree()
        resp = self.api.post(
            f'/accounting/api/v1/documents/{standalone.id}/attach-to-obligation/',
            {'obligation_id': ob.id}, format='multipart')
        self.assertEqual(resp.status_code, 409, resp.content)
        standalone.refresh_from_db()
        self.assertIsNone(standalone.obligation_id)
        self.assertEqual(media_tree(), before)

    def test_detach_to_occupied_null_key_409(self):
        ob = self._ob()
        attached = self._upload(obligation=ob)
        self._upload()                        # κατέχει το null-obligation key
        resp = self.api.post(
            f'/accounting/api/v1/documents/{attached.id}/detach-from-obligation/',
            {}, format='multipart')
        self.assertEqual(resp.status_code, 409, resp.content)
        attached.refresh_from_db()
        self.assertEqual(attached.obligation_id, ob.id)

    def test_attach_free_key_succeeds_with_audit(self):
        from common.models import AuditLog
        ob = self._ob()
        doc = self._upload()
        before = AuditLog.objects.filter(model_name='ClientDocument').count()
        resp = self.api.post(
            f'/accounting/api/v1/documents/{doc.id}/attach-to-obligation/',
            {'obligation_id': ob.id}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.content)
        doc.refresh_from_db()
        self.assertEqual(doc.obligation_id, ob.id)
        audits = AuditLog.objects.filter(model_name='ClientDocument')
        self.assertEqual(audits.count(), before + 1)
        self.assertNotIn(self.client_a.afm, audits.latest('id').description)
        self.assertNotIn(TEMP_MEDIA, audits.latest('id').description)

    def test_attach_period_mismatch_400(self):
        ob = self._ob(month=5)
        doc = self._upload(month=3)
        resp = self.api.post(
            f'/accounting/api/v1/documents/{doc.id}/attach-to-obligation/',
            {'obligation_id': ob.id}, format='multipart')
        self.assertEqual(resp.status_code, 400, resp.content)
        doc.refresh_from_db()
        self.assertIsNone(doc.obligation_id)

    def test_legacy_attach_endpoint_same_policy(self):
        """Το legacy attach-document δεν παρακάμπτει το service (409)."""
        ob = self._ob()
        self._upload(obligation=ob)
        standalone = self._upload()
        resp = self.api.post(
            f'/accounting/api/v1/obligations/{ob.id}/attach-document/',
            {'document_id': standalone.id}, format='multipart')
        self.assertEqual(resp.status_code, 409, resp.content)
        standalone.refresh_from_db()
        self.assertIsNone(standalone.obligation_id)

    def test_attach_without_change_perm_denied_no_mutation(self):
        ob = self._ob()
        doc = self._upload()
        viewer = make_perm_user(
            'r19_viewer', ['view_clientprofile', 'view_clientdocument',
                           'view_monthlyobligation'], [self.client_a])
        c = SecureAPIClient()
        c.force_authenticate(viewer)
        resp = c.post(
            f'/accounting/api/v1/documents/{doc.id}/attach-to-obligation/',
            {'obligation_id': ob.id}, format='multipart')
        self.assertEqual(resp.status_code, 403, resp.content)
        doc.refresh_from_db()
        self.assertIsNone(doc.obligation_id)


# ---------------------------------------------------------------------------
# 3. Ενιαίος exact-conflict helper
# ---------------------------------------------------------------------------
class SharedHelperTest(Round19Base):
    def test_check_existing_without_obligation_ignores_obligation_docs(self):
        ob = self._ob()
        self._upload(obligation=ob)
        found = ClientDocument.check_existing(
            client=self.client_a, obligation=None, category='vat',
            year=2026, month=3)
        self.assertIsNone(found)

    def test_general_category_exact_matching(self):
        self._upload(category='general')
        self.assertIsNone(ClientDocument.check_existing(
            client=self.client_a, category='vat', year=2026, month=3))
        self.assertIsNotNone(ClientDocument.check_existing(
            client=self.client_a, category='general', year=2026, month=3))

    def test_check_existing_api_multiple_current_409(self):
        user = User.objects.get(pk=self.full.pk)
        user.is_staff = True
        user.save()
        c = SecureClient()
        c.force_login(user)
        with mock.patch(
                'accounting.services.filing.find_current_for_key',
                side_effect=filing.MultipleCurrentDocumentsError('x')):
            resp = c.get('/accounting/api/v1/documents/check-existing/',
                         {'client_id': self.client_a.id, 'category': 'vat',
                          'year': 2026, 'month': 3})
        self.assertEqual(resp.status_code, 409, resp.content)

    def test_check_existing_api_invalid_params_400(self):
        user = User.objects.get(pk=self.full.pk)
        user.is_staff = True
        user.save()
        c = SecureClient()
        c.force_login(user)
        resp = c.get('/accounting/api/v1/documents/check-existing/',
                     {'client_id': self.client_a.id, 'year': 'κακό'})
        self.assertEqual(resp.status_code, 400, resp.content)


# ---------------------------------------------------------------------------
# 4. 'keep' semantics με slot
# ---------------------------------------------------------------------------
class KeepSlotTest(Round19Base):
    def test_keep_on_occupied_key_no_displacement_unique_slot(self):
        office = self._upload()               # slot ''
        kept = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=3, user=None,
            on_existing='keep',
            portal_capability=filing.PortalUploadCapability(1, self.client_a.pk))
        office.refresh_from_db()
        self.assertTrue(office.is_current)     # ΔΕΝ εκτοπίστηκε
        self.assertTrue(kept.is_current)
        self.assertNotEqual(kept.slot, '')     # δικό του slot/key
        # Invariant: ένα current ανά (key+slot)
        self.assertEqual(ClientDocument.objects.filter(
            client=self.client_a, document_category='vat', year=2026,
            month=3, obligation__isnull=True, is_current=True,
            slot='').count(), 1)

    def test_two_keep_uploads_both_current_distinct_slots(self):
        k1 = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=3, user=None,
            on_existing='keep',
            portal_capability=filing.PortalUploadCapability(1, self.client_a.pk))
        k2 = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=3, user=None,
            on_existing='keep',
            portal_capability=filing.PortalUploadCapability(1, self.client_a.pk))
        self.assertNotEqual(k1.slot, k2.slot)
        self.assertTrue(k1.is_current and k2.is_current)

    def test_keep_version_inherits_slot(self):
        kept = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=3, user=None,
            on_existing='keep',
            portal_capability=filing.PortalUploadCapability(1, self.client_a.pk))
        v2 = kept.create_new_version(new_file=pdf_upload(), user=self.full)
        self.assertEqual(v2.slot, kept.slot)


# ---------------------------------------------------------------------------
# 5. Input validation
# ---------------------------------------------------------------------------
class InputValidationTest(Round19Base):
    def _post_upload(self, **params):
        data = {'file': pdf_upload(), 'client_id': self.client_a.id}
        data.update(params)
        user = User.objects.get(pk=self.full.pk)
        user.is_staff = True
        user.save()
        c = SecureClient()
        c.force_login(user)
        return c.post('/accounting/api/v1/documents/upload-with-version/', data)

    def test_invalid_year_string_400(self):
        before = media_tree()
        resp = self._post_upload(year='χίλια', month=3)
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(media_tree(), before)

    def test_invalid_month_string_400(self):
        resp = self._post_upload(year=2026, month='τρίτος')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_month_zero_and_13_400(self):
        for m in (0, 13):
            resp = self._post_upload(year=2026, month=m)
            self.assertEqual(resp.status_code, 400,
                             f'month={m}: {resp.content}')

    def test_invalid_category_400_no_side_effects(self):
        before = media_tree()
        with self.assertRaises(ValidationError):
            self._upload(category='hacked')
        self.assertEqual(media_tree(), before)

    def test_year_out_of_range_service_400(self):
        with self.assertRaises(ValidationError):
            self._upload(year=1901)

    def test_missing_obligation_404(self):
        resp = self.api.post(
            '/accounting/api/v1/documents/upload/',
            {'file': pdf_upload(), 'client_id': self.client_a.id,
             'obligation_id': 999999}, format='multipart')
        self.assertEqual(resp.status_code, 404, resp.content)

    def test_foreign_client_obligation_neutral_404(self):
        foreign = ClientProfile.objects.create(
            afm='997654321', eponimia='ΞΕΝΟΣ', eidos_ipoxreou='company')
        f_ob = self._ob(client=foreign)
        resp = self.api.post(
            '/accounting/api/v1/documents/upload/',
            {'file': pdf_upload(), 'client_id': self.client_a.id,
             'obligation_id': f_ob.id}, format='multipart')
        self.assertEqual(resp.status_code, 404, resp.content)
        self.assertEqual(ClientDocument.objects.count(), 0)


# ---------------------------------------------------------------------------
# 6. Production fail-closed libmagic στην upload διαδρομή
# ---------------------------------------------------------------------------
class LibmagicFailClosedUploadTest(Round19Base):
    def test_import_error_production_rejects(self):
        with override_settings(DEBUG=False), \
             mock.patch.dict('sys.modules', {'magic': None}):
            with self.assertRaises(ValidationError):
                self._upload()
        self.assertEqual(ClientDocument.objects.count(), 0)

    def test_runtime_exception_production_rejects(self):
        import magic as real_magic
        with override_settings(DEBUG=False), \
             mock.patch.object(real_magic, 'from_buffer',
                               side_effect=RuntimeError('native crash')):
            with self.assertRaises(ValidationError):
                self._upload()
        self.assertEqual(ClientDocument.objects.count(), 0)

    def test_empty_mime_production_rejects(self):
        import magic as real_magic
        with override_settings(DEBUG=False), \
             mock.patch.object(real_magic, 'from_buffer', return_value=''):
            with self.assertRaises(ValidationError):
                self._upload()

    def test_disallowed_mime_production_rejects(self):
        import magic as real_magic
        with override_settings(DEBUG=False), \
             mock.patch.object(real_magic, 'from_buffer',
                               return_value='video/mp4'):
            with self.assertRaises(ValidationError):
                self._upload()

    def test_pdf_extension_html_content_rejected_any_mode(self):
        with self.assertRaises(ValidationError):
            filing.create_client_document(
                client=self.client_a,
                uploaded_file=SimpleUploadedFile(
                    'x.pdf', b'<!DOCTYPE html><script>1</script>'),
                category='vat', year=2026, month=3, user=self.full)

    def test_development_import_error_warns_only(self):
        with override_settings(DEBUG=True), \
             mock.patch.dict('sys.modules', {'magic': None}):
            doc = self._upload()
        self.assertTrue(doc.pk)

    def test_require_libmagic_setting_forces_fail_closed_in_debug(self):
        with override_settings(DEBUG=True, REQUIRE_LIBMAGIC=True), \
             mock.patch.dict('sys.modules', {'magic': None}):
            with self.assertRaises(ValidationError):
                self._upload()


# ---------------------------------------------------------------------------
# 7. Επέκταση invariant audit
# ---------------------------------------------------------------------------
class ExtendedAuditTest(Round19Base):
    def _row(self, **kw):
        defaults = dict(
            client=self.client_a, document_category='vat', year=2026,
            month=kw.pop('month', 1), version=kw.pop('version', 1),
            is_current=kw.pop('is_current', True),
            file=f"a{kw.pop('n', 0)}.pdf", original_filename='x.pdf',
            filename='x.pdf', file_type='pdf', file_size=1)
        defaults.update(kw)
        doc = ClientDocument(**defaults)
        doc.save()
        return doc

    def _run(self):
        out = StringIO()
        call_command('audit_clientdocument_invariants', stdout=out)
        return out.getvalue()

    def test_chain_without_current_detected(self):
        d1 = self._row(month=1, is_current=False, n=1)
        d2 = self._row(month=2, is_current=False, n=2, version=2)
        ClientDocument.objects.filter(pk=d2.pk).update(previous_version=d1.pk)
        text = self._run()
        self.assertIn('chain-without-current', text)

    def test_cross_key_previous_version_detected(self):
        d1 = self._row(month=1, is_current=False, n=1)
        d2 = self._row(month=5, version=2, n=2)  # άλλος μήνας = άλλο key
        ClientDocument.objects.filter(pk=d2.pk).update(previous_version=d1.pk)
        text = self._run()
        self.assertIn('cross-key-previous-version', text)

    def test_root_version_not_1_detected(self):
        d1 = self._row(month=1, version=3, is_current=False, n=1)
        d2 = self._row(month=1, version=4, n=2, slot='s2')
        ClientDocument.objects.filter(pk=d2.pk).update(
            previous_version=d1.pk, slot='')
        text = self._run()
        self.assertIn('root-version-not-1', text)

    def test_current_not_terminal_detected(self):
        d1 = self._row(month=1, is_current=True, n=1)
        d2 = self._row(month=1, version=2, is_current=False, n=2, slot='s2')
        ClientDocument.objects.filter(pk=d2.pk).update(
            previous_version=d1.pk, slot='')
        text = self._run()
        self.assertIn('current-not-terminal', text)

    def test_duplicate_version_in_chain_detected(self):
        d1 = self._row(month=1, is_current=False, version=2, n=1)
        d2 = self._row(month=1, version=2, n=2, slot='s2')
        ClientDocument.objects.filter(pk=d2.pk).update(
            previous_version=d1.pk, slot='')
        text = self._run()
        self.assertIn('duplicate-version-in-chain', text)

    def test_clean_versioned_chain_no_findings(self):
        """Η κανονική εφαρμογή (version + keep slots) ΔΕΝ αναφέρεται
        ως corruption."""
        doc = self._upload()
        filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=3, user=self.full)  # v2
        filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=3, user=None,
            on_existing='keep',
            portal_capability=filing.PortalUploadCapability(1, self.client_a.pk))  # portal slot
        text = self._run()
        self.assertIn('Κανένα invariant finding', text)


# ---------------------------------------------------------------------------
# 8. Πολιτική διαγραφής versioned documents
# ---------------------------------------------------------------------------
class DeletionPolicyTest(Round19Base):
    def _chain(self):
        v1 = self._upload()
        v2 = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=3, user=self.full)
        return ClientDocument.objects.get(pk=v1.pk), v2

    def test_delete_current_promotes_previous(self):
        v1, v2 = self._chain()
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.api.delete(
                f'/accounting/api/v1/documents/{v2.id}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(ClientDocument.objects.filter(pk=v2.pk).exists())
        v1.refresh_from_db()
        self.assertTrue(v1.is_current)  # καμία chain χωρίς current

    def test_delete_historical_with_descendants_denied(self):
        v1, v2 = self._chain()
        resp = self.api.delete(f'/accounting/api/v1/documents/{v1.id}/')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertTrue(ClientDocument.objects.filter(pk=v1.pk).exists())
        v2.refresh_from_db()
        self.assertTrue(v2.is_current)

    def test_delete_single_current_simple(self):
        doc = self._upload()
        path = doc.file.path
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.api.delete(f'/accounting/api/v1/documents/{doc.id}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(ClientDocument.objects.filter(pk=doc.pk).exists())
        self.assertFalse(os.path.exists(path))

    def test_delete_whole_chain_tail_first(self):
        v1, v2 = self._chain()
        with self.captureOnCommitCallbacks(execute=True):
            self.api.delete(f'/accounting/api/v1/documents/{v2.id}/')
            resp = self.api.delete(f'/accounting/api/v1/documents/{v1.id}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(ClientDocument.objects.count(), 0)

    def test_delete_without_perm_denied(self):
        doc = self._upload()
        no_del = make_perm_user(
            'r19_nodel', ['view_clientprofile', 'view_clientdocument',
                          'add_clientdocument', 'change_clientdocument'],
            [self.client_a])
        c = SecureAPIClient()
        c.force_authenticate(no_del)
        resp = c.delete(f'/accounting/api/v1/documents/{doc.id}/')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertTrue(ClientDocument.objects.filter(pk=doc.pk).exists())


# ---------------------------------------------------------------------------
# 9. DB constraint integrity
# ---------------------------------------------------------------------------
class DbConstraintTest(Round19Base):
    def test_duplicate_current_insert_blocked(self):
        from django.db import IntegrityError, transaction
        self._upload()
        dup = ClientDocument(
            client=self.client_a, document_category='vat', year=2026,
            month=3, version=1, is_current=True, file='dup.pdf',
            original_filename='x.pdf', filename='x.pdf', file_type='pdf',
            file_size=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                dup.save()

    def test_non_current_duplicate_allowed(self):
        self._upload()
        old = ClientDocument(
            client=self.client_a, document_category='vat', year=2026,
            month=3, version=1, is_current=False, file='old.pdf',
            original_filename='x.pdf', filename='x.pdf', file_type='pdf',
            file_size=1)
        old.save()  # ιστορικές εκδόσεις δεν περιορίζονται
        self.assertTrue(old.pk)

    def test_obligation_key_constraint_blocked(self):
        from django.db import IntegrityError, transaction
        ob = self._ob()
        self._upload(obligation=ob)
        dup = ClientDocument(
            client=self.client_a, obligation=ob, document_category='vat',
            year=2026, month=3, version=1, is_current=True, file='d2.pdf',
            original_filename='x.pdf', filename='x.pdf', file_type='pdf',
            file_size=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                dup.save()
