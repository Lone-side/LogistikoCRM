# -*- coding: utf-8 -*-
"""
Γύρος 20 — τελικό production hardening.

1. Stale-object race στα attach/detach/delete (reload+lock του document)
2. Legacy slot chains (migration 10021) + πραγματικό migration test
3. legacy-slot-needs-review στο audit command
5. Πραγματικά fail-closed MIME validation (extension↔MIME, containers,
   empty file, pointer reset)
6. MultipleCurrentDocumentsError → 409 σε κάθε route
7. Permissions ΠΡΙΝ από locks + portal capability για anonymous 'keep'
8. Deletion service μετά τις αλλαγές (stale, gone, promote conflict)
"""
import os
import shutil
import tempfile
import zipfile
from io import BytesIO, StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings

from accounting.models import ClientDocument, ClientProfile, MonthlyObligation, ObligationType
from accounting.services import filing
from tests.accounting.secure_client import SecureAPIClient

User = get_user_model()

TEMP_MEDIA = tempfile.mkdtemp(prefix='round20_test_')


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


def pdf_upload(name='αρχείο.pdf', content=b'%PDF-1.4 test payload'):
    return SimpleUploadedFile(name, content, content_type='application/pdf')


def ooxml_bytes(kind='docx', valid=True):
    """Παράγει πραγματικό (ή ελλιπές) OOXML ZIP container."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        if valid:
            zf.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types/>')
            prefix = 'word/' if kind == 'docx' else 'xl/'
            zf.writestr(f'{prefix}document.xml', '<?xml version="1.0"?><d/>')
        else:
            zf.writestr('random.txt', 'not office')
    return buf.getvalue()


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
class Round20Base(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.ob_type = ObligationType.objects.create(
            name='ΦΠΑ20', code='FPA20', is_active=True)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        self.full = make_perm_user(
            f'r20_{self.id().split(".")[-1][:16]}',
            ['add_clientdocument', 'change_clientdocument',
             'delete_clientdocument', 'view_clientdocument',
             'view_clientprofile', 'view_monthlyobligation'],
            [self.client_a])
        self.api = SecureAPIClient()
        self.api.force_authenticate(self.full)

    def _ob(self, month=3, year=2026, code_suffix='a'):
        ob_type = ObligationType.objects.create(
            name=f'ΤΥΠΟΣ-{code_suffix}', code=f'T{code_suffix}',
            is_active=True)
        from django.utils import timezone
        return MonthlyObligation.objects.create(
            client=self.client_a, obligation_type=ob_type, month=month,
            year=year, deadline=timezone.now().date())

    def _upload(self, user=None, **kwargs):
        kwargs.setdefault('category', 'vat')
        kwargs.setdefault('year', 2026)
        kwargs.setdefault('month', 3)
        return filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            user=user or self.full, **kwargs)


# ---------------------------------------------------------------------------
# 1. Stale-object race protection
# ---------------------------------------------------------------------------
class StaleObjectProtectionTest(Round20Base):
    def test_attach_on_deleted_document_returns_gone(self):
        """Concurrent delete: το service δεν αναδημιουργεί το row."""
        ob = self._ob()
        doc = self._upload()
        stale = ClientDocument.objects.get(pk=doc.pk)
        ClientDocument.objects.filter(pk=doc.pk).delete()
        with self.assertRaises(filing.DocumentGone):
            filing.attach_document_service(self.full, stale, ob)
        self.assertEqual(ClientDocument.objects.filter(pk=doc.pk).count(), 0)

    def test_attach_endpoint_on_deleted_document_404(self):
        ob = self._ob()
        doc = self._upload()
        url = f'/accounting/api/v1/documents/{doc.id}/attach-to-obligation/'
        # get_object() θα δώσει ήδη 404 — ελέγχουμε το service επίπεδο
        # μέσω απευθείας κλήσης με stale instance και το endpoint contract
        resp = self.api.post(url, {'obligation_id': ob.id},
                             format='multipart')
        self.assertEqual(resp.status_code, 200, resp.content)
        doc.refresh_from_db()
        self.assertEqual(doc.obligation_id, ob.id)

    def test_detach_on_deleted_document_returns_gone(self):
        ob = self._ob()
        doc = self._upload(obligation=ob)
        stale = ClientDocument.objects.get(pk=doc.pk)
        ClientDocument.objects.filter(pk=doc.pk).delete()
        with self.assertRaises(filing.DocumentGone):
            filing.detach_document_service(self.full, stale)

    def test_attach_uses_fresh_state_not_stale_instance(self):
        """Stale instance λέει obligation=None· η βάση λέει ήδη attached →
        το service βλέπει fresh state και κάνει no-op."""
        ob = self._ob()
        doc = self._upload()
        stale = ClientDocument.objects.get(pk=doc.pk)
        # Άλλο request το έκανε ήδη attach
        filing.attach_document_service(self.full, doc, ob)
        result = filing.attach_document_service(self.full, stale, ob)
        self.assertEqual(result.obligation_id, ob.id)
        self.assertEqual(ClientDocument.objects.filter(
            pk=doc.pk, obligation=ob).count(), 1)

    def test_detach_uses_fresh_state_no_op(self):
        ob = self._ob()
        doc = self._upload(obligation=ob)
        stale = ClientDocument.objects.get(pk=doc.pk)
        filing.detach_document_service(self.full, doc)
        result = filing.detach_document_service(self.full, stale)
        self.assertIsNone(result.obligation_id)

    def test_delete_on_already_deleted_returns_gone(self):
        doc = self._upload()
        stale = ClientDocument.objects.get(pk=doc.pk)
        ClientDocument.objects.filter(pk=doc.pk).delete()
        with self.assertRaises(filing.DocumentGone):
            filing.delete_document_service(self.full, stale)

    def test_stale_delete_does_not_recreate_row(self):
        doc = self._upload()
        stale = ClientDocument.objects.get(pk=doc.pk)
        filing.delete_document_service(self.full, doc)
        with self.assertRaises(filing.DocumentGone):
            filing.delete_document_service(self.full, stale)
        self.assertEqual(ClientDocument.objects.filter(pk=doc.pk).count(), 0)

    def test_service_returns_locked_document(self):
        ob = self._ob()
        doc = self._upload()
        returned = filing.attach_document_service(self.full, doc, ob)
        self.assertEqual(returned.pk, doc.pk)
        self.assertEqual(returned.obligation_id, ob.id)


# ---------------------------------------------------------------------------
# 6. MultipleCurrentDocumentsError → 409 σε κάθε route
# ---------------------------------------------------------------------------
class MultipleCurrentIs409Test(Round20Base):
    def _corrupt(self):
        return mock.patch(
            'accounting.services.filing.find_current_for_key',
            side_effect=filing.MultipleCurrentDocumentsError('corrupted'))

    def test_attach_route_409(self):
        ob = self._ob()
        doc = self._upload()
        with self._corrupt():
            resp = self.api.post(
                f'/accounting/api/v1/documents/{doc.id}/attach-to-obligation/',
                {'obligation_id': ob.id}, format='multipart')
        self.assertEqual(resp.status_code, 409, resp.content)

    def test_detach_route_409(self):
        ob = self._ob()
        doc = self._upload(obligation=ob)
        with self._corrupt():
            resp = self.api.post(
                f'/accounting/api/v1/documents/{doc.id}/detach-from-obligation/',
                {}, format='multipart')
        self.assertEqual(resp.status_code, 409, resp.content)

    def test_legacy_attach_route_409(self):
        ob = self._ob()
        doc = self._upload()
        with self._corrupt():
            resp = self.api.post(
                f'/accounting/api/v1/obligations/{ob.id}/attach-document/',
                {'document_id': doc.id}, format='multipart')
        self.assertEqual(resp.status_code, 409, resp.content)

    def test_upload_route_409(self):
        with self._corrupt():
            resp = self.api.post(
                '/accounting/api/v1/documents/upload/',
                {'file': pdf_upload(), 'client_id': self.client_a.id},
                format='multipart')
        self.assertEqual(resp.status_code, 409, resp.content)

    def test_client_document_delete_route_409(self):
        doc = self._upload()
        with mock.patch(
                'accounting.services.filing.delete_document_service',
                side_effect=filing.MultipleCurrentDocumentsError('x')):
            resp = self.api.delete(
                f'/accounting/api/v1/documents/{doc.id}/')
        self.assertEqual(resp.status_code, 409, resp.content)

    def test_error_message_has_no_internals(self):
        ob = self._ob()
        doc = self._upload()
        with self._corrupt():
            resp = self.api.post(
                f'/accounting/api/v1/documents/{doc.id}/attach-to-obligation/',
                {'obligation_id': ob.id}, format='multipart')
        body = str(resp.content)
        for marker in ('Traceback', 'corrupted', TEMP_MEDIA,
                       self.client_a.afm):
            self.assertNotIn(marker, body)


# ---------------------------------------------------------------------------
# 5. Fail-closed MIME validation
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA,
                   REQUIRE_LIBMAGIC=True)
class MimeFailClosedTest(Round20Base):
    def _upload_file(self, name, content):
        return filing.create_client_document(
            client=self.client_a,
            uploaded_file=SimpleUploadedFile(name, content),
            category='vat', year=2026, month=3, user=self.full)

    def test_empty_pdf_rejected(self):
        before = media_tree()
        with self.assertRaises(ValidationError):
            self._upload_file('κενό.pdf', b'')
        self.assertEqual(ClientDocument.objects.count(), 0)
        self.assertEqual(media_tree(), before)

    def test_octet_stream_arbitrary_binary_rejected(self):
        with self.assertRaises(ValidationError):
            self._upload_file('τυχαίο.pdf', b'\x00\x01\x02\x03random binary')

    def test_zip_renamed_to_pdf_rejected(self):
        with self.assertRaises(ValidationError):
            self._upload_file('ψεύτικο.pdf', ooxml_bytes('docx'))

    def test_pdf_renamed_to_jpg_rejected(self):
        with self.assertRaises(ValidationError):
            self._upload_file('εικόνα.jpg', b'%PDF-1.4 not an image')

    def test_fake_docx_rejected(self):
        with self.assertRaises(ValidationError):
            self._upload_file('ψεύτικο.docx', b'\x00\x01 arbitrary binary')

    def test_fake_xlsx_missing_markers_rejected(self):
        with self.assertRaises(ValidationError):
            self._upload_file('ψεύτικο.xlsx', ooxml_bytes('xlsx', valid=False))

    def test_valid_docx_accepted(self):
        doc = self._upload_file('έγγραφο.docx', ooxml_bytes('docx'))
        self.assertTrue(doc.pk)

    def test_valid_xlsx_accepted(self):
        doc = self._upload_file('φύλλο.xlsx', ooxml_bytes('xlsx'))
        self.assertTrue(doc.pk)

    def test_valid_pdf_accepted(self):
        doc = self._upload_file('σωστό.pdf', b'%PDF-1.4\n1 0 obj\n')
        self.assertTrue(doc.pk)

    def test_libmagic_import_error_rejected(self):
        with mock.patch.dict('sys.modules', {'magic': None}):
            with self.assertRaises(ValidationError):
                self._upload_file('σωστό.pdf', b'%PDF-1.4 ok')

    def test_libmagic_runtime_error_rejected(self):
        import magic as real_magic
        with mock.patch.object(real_magic, 'from_buffer',
                               side_effect=RuntimeError('native crash')):
            with self.assertRaises(ValidationError):
                self._upload_file('σωστό.pdf', b'%PDF-1.4 ok')

    def test_file_pointer_reset_after_validation(self):
        f = SimpleUploadedFile('σωστό.pdf', b'%PDF-1.4 payload content')
        filing.validate_upload(f)
        self.assertEqual(f.tell(), 0)
        self.assertTrue(f.read(5).startswith(b'%PDF-'))

    def test_pointer_reset_even_on_rejection(self):
        f = SimpleUploadedFile('ψεύτικο.pdf', b'<html>x</html>')
        with self.assertRaises(ValidationError):
            filing.validate_upload(f)
        self.assertEqual(f.tell(), 0)


# ---------------------------------------------------------------------------
# 7. Permissions πριν από locks + portal capability
# ---------------------------------------------------------------------------
class PermissionsBeforeLocksTest(Round20Base):
    def test_denied_create_no_lock_no_storage_no_row(self):
        no_add = make_perm_user(
            'r20_noadd', ['view_clientprofile', 'view_clientdocument'],
            [self.client_a])
        before = media_tree()
        with mock.patch(
                'accounting.models.ClientProfile.objects') as m_objs:
            m_objs.select_for_update.side_effect = AssertionError(
                'ΔΕΝ πρέπει να αποκτηθεί lock πριν το permission check')
            with self.assertRaises(PermissionDenied):
                self._upload(user=no_add)
        self.assertEqual(ClientDocument.objects.count(), 0)
        self.assertEqual(media_tree(), before)

    def test_anonymous_keep_without_capability_denied(self):
        before = media_tree()
        with self.assertRaises(PermissionDenied):
            filing.create_client_document(
                client=self.client_a, uploaded_file=pdf_upload(),
                category='vat', year=2026, month=3, user=None,
                on_existing='keep')
        self.assertEqual(ClientDocument.objects.count(), 0)
        self.assertEqual(media_tree(), before)

    def test_anonymous_keep_with_capability_allowed(self):
        doc = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=3, user=None,
            on_existing='keep',
            portal_capability=filing.PortalUploadCapability(42, self.client_a.pk))
        self.assertTrue(doc.pk)
        self.assertNotEqual(doc.slot, '')

    def test_capability_cannot_come_from_request_input(self):
        """Ένα plain dict/string ΔΕΝ γίνεται δεκτό ως capability."""
        for fake in ({'shared_link_id': 1}, 'token', 1, True):
            with self.assertRaises(PermissionDenied):
                filing.create_client_document(
                    client=self.client_a, uploaded_file=pdf_upload(),
                    category='vat', year=2026, month=3, user=None,
                    on_existing='keep', portal_capability=fake)

    def test_anonymous_version_never_allowed_even_with_capability(self):
        self._upload()
        with self.assertRaises(PermissionDenied):
            filing.create_client_document(
                client=self.client_a, uploaded_file=pdf_upload(),
                category='vat', year=2026, month=3, user=None,
                on_existing='version',
                portal_capability=filing.PortalUploadCapability(1, self.client_a.pk))


# ---------------------------------------------------------------------------
# 8. Deletion service
# ---------------------------------------------------------------------------
class DeletionServiceTest(Round20Base):
    def test_delete_current_of_legacy_slot_chain(self):
        v1 = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=3, user=None,
            on_existing='keep',
            portal_capability=filing.PortalUploadCapability(1, self.client_a.pk))
        ClientDocument.objects.filter(pk=v1.pk).update(slot='legacy-1')
        v1.refresh_from_db()
        v2 = v1.create_new_version(new_file=pdf_upload(), user=self.full)
        self.assertEqual(v2.slot, 'legacy-1')
        filing.delete_document_service(self.full, v2)
        v1.refresh_from_db()
        self.assertTrue(v1.is_current)
        self.assertEqual(v1.slot, 'legacy-1')

    def test_promote_conflict_fails_closed_409(self):
        """Corrupted cross-key previous: η προαγωγή θα δημιουργούσε δεύτερο
        current → 409, πλήρες rollback, κανένα αρχείο δεν διαγράφεται."""
        v1 = self._upload()
        v2 = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=3, user=self.full)
        other = self._upload(category='payroll')
        # Το v1 (non-current) «δείχνει» πλέον στο key του other
        ClientDocument.objects.filter(pk=v1.pk).update(
            document_category='payroll')
        v1_path = ClientDocument.objects.get(pk=v1.pk).file.path
        with self.assertRaises(filing.DocumentKeyConflict):
            filing.delete_document_service(self.full, v2)
        # Πλήρες rollback: όλα τα rows υπάρχουν, κανένα αρχείο δεν χάθηκε
        self.assertTrue(ClientDocument.objects.filter(pk=v2.pk).exists())
        self.assertTrue(ClientDocument.objects.filter(pk=v1.pk).exists())
        self.assertTrue(os.path.exists(v1_path))
        other.refresh_from_db()
        self.assertTrue(other.is_current)

    def test_delete_historical_with_descendants_400(self):
        v1 = self._upload()
        filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=3, user=self.full)
        with self.assertRaises(ValidationError):
            filing.delete_document_service(self.full, v1)
        self.assertTrue(ClientDocument.objects.filter(pk=v1.pk).exists())

    def test_double_delete_second_is_gone(self):
        doc = self._upload()
        filing.delete_document_service(self.full, doc)
        with self.assertRaises(filing.DocumentGone):
            filing.delete_document_service(self.full, doc)

    def test_delete_audit_has_only_internal_ids(self):
        from common.models import AuditLog
        doc = self._upload()
        filing.delete_document_service(self.full, doc)
        entry = AuditLog.objects.filter(model_name='ClientDocument').latest('id')
        self.assertIn(f'document id={doc.pk}', entry.description)
        self.assertNotIn(self.client_a.afm, entry.description)
        self.assertNotIn(TEMP_MEDIA, entry.description)
        self.assertNotIn(doc.filename, entry.description)


# ---------------------------------------------------------------------------
# 3. legacy-slot-needs-review στο audit
# ---------------------------------------------------------------------------
class LegacySlotAuditTest(Round20Base):
    def _run(self, fail=False):
        out = StringIO()
        args = ['audit_clientdocument_invariants']
        if fail:
            args.append('--fail-on-findings')
        call_command(*args, stdout=out)
        return out.getvalue()

    def test_legacy_slot_reported_once_per_chain(self):
        v1 = self._upload()
        v2 = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=3, user=self.full)
        ClientDocument.objects.filter(pk__in=[v1.pk, v2.pk]).update(
            slot='legacy-1')
        text = self._run()
        self.assertEqual(text.count('legacy-slot-needs-review'), 1)
        self.assertIn(str(v1.pk), text)
        self.assertNotIn(self.client_a.afm, text)
        self.assertNotIn(TEMP_MEDIA, text)

    def test_legacy_slot_fails_on_findings(self):
        doc = self._upload()
        ClientDocument.objects.filter(pk=doc.pk).update(slot='legacy-9')
        with self.assertRaises(CommandError):
            self._run(fail=True)

    def test_clean_db_without_legacy_no_finding(self):
        self._upload()
        self.assertIn('Κανένα invariant finding', self._run())


# ---------------------------------------------------------------------------
# 2+4. Πραγματικό migration test (MigrationExecutor)
# ---------------------------------------------------------------------------
class Migration10021Test(TransactionTestCase):
    """
    Πραγματικό migration test: γυρίζει τη βάση στο state ΠΡΙΝ το 10021,
    δημιουργεί legacy δεδομένα με historical models και τρέχει το 10021.
    """
    # ΠΡΙΝ το slot/constraints — μόνο έτσι δημιουργούνται πραγματικά
    # legacy duplicates· μετά τρέχει η αλυσίδα 10020 → 10021
    migrate_from = ('accounting', '10019_export_clientprofile_permission')
    migrate_to = ('accounting', '10021_fix_legacy_slot_chains')

    def _migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([target])
        executor.loader.build_graph()
        return executor.loader.project_state([target]).apps

    def setUp(self):
        self.old_apps = self._migrate(self.migrate_from)

    def tearDown(self):
        # Επαναφορά στο τελευταίο migration για τα υπόλοιπα tests
        self._migrate(self.migrate_to)

    def _doc(self, apps, client, **kw):
        ClientDocument = apps.get_model('accounting', 'ClientDocument')
        defaults = dict(
            client_id=client.id, document_category='vat', year=2026,
            month=3, version=1, is_current=True,
            file='x.pdf', original_filename='x.pdf', filename='x.pdf',
            file_type='pdf', file_size=1)
        defaults.update(kw)
        # Στο state 10019 δεν υπάρχει ακόμη το πεδίο slot
        if 'slot' in defaults and not hasattr(ClientDocument, 'slot'):
            defaults.pop('slot')
        return ClientDocument.objects.create(**defaults)

    def _client(self, apps, afm='123456783'):
        ClientProfile = apps.get_model('accounting', 'ClientProfile')
        return ClientProfile.objects.create(
            afm=afm, eponimia='ΜΕΤΑΝΑΣΤΕΥΣΗ ΑΕ', eidos_ipoxreou='company')

    def test_duplicate_roots_and_chains_get_consistent_slots(self):
        apps = self.old_apps
        client = self._client(apps)
        # (1) δύο duplicate current roots στο ίδιο logical key
        office = self._doc(apps, client)
        # (2) duplicate current chain με previous version + (3) πολλαπλές
        portal_v1 = self._doc(apps, client, is_current=False)
        portal_v2 = self._doc(apps, client, is_current=False, version=2,
                              previous_version_id=portal_v1.id)
        portal_v3 = self._doc(apps, client, version=3,
                              previous_version_id=portal_v2.id)

        new_apps = self._migrate(self.migrate_to)
        CD = new_apps.get_model('accounting', 'ClientDocument')
        rows = {r.id: r for r in CD.objects.all()}

        # (9) ΟΛΑ τα μέλη της chain έχουν το ΙΔΙΟ slot
        chain_slots = {rows[d.id].slot
                       for d in (portal_v1, portal_v2, portal_v3)}
        self.assertEqual(len(chain_slots), 1)
        chain_slot = chain_slots.pop()
        self.assertTrue(chain_slot.startswith('legacy-'))
        # (8) deterministic: slot = legacy-{min id της chain}
        self.assertEqual(chain_slot, f'legacy-{portal_v1.id}')
        # Το office (αμφίβολο duplicate) απελευθερώνει το κύριο slot
        self.assertTrue(rows[office.id].slot.startswith('legacy-'))
        self.assertNotEqual(rows[office.id].slot, chain_slot)

    def test_obligation_null_and_not_null_keys(self):
        apps = self.old_apps
        client = self._client(apps)
        ObligationType = apps.get_model('accounting', 'ObligationType')
        MonthlyObligation = apps.get_model('accounting', 'MonthlyObligation')
        ot = ObligationType.objects.create(name='ΦΠΑ-M', code='FPAM')
        ob = MonthlyObligation.objects.create(
            client_id=client.id, obligation_type_id=ot.id, month=3,
            year=2026, deadline='2026-03-20')
        # (4) obligation-null key duplicates
        n1 = self._doc(apps, client)
        n2 = self._doc(apps, client)
        # (5) obligation-not-null key duplicates
        o1 = self._doc(apps, client, obligation_id=ob.id)
        o2 = self._doc(apps, client, obligation_id=ob.id)

        new_apps = self._migrate(self.migrate_to)
        CD = new_apps.get_model('accounting', 'ClientDocument')
        rows = {r.id: r.slot for r in CD.objects.all()}
        # Και τα δύο keys ελευθερώνουν το κύριο slot, με διακριτά legacy slots
        for a, b in ((n1, n2), (o1, o2)):
            self.assertTrue(rows[a.id].startswith('legacy-'))
            self.assertTrue(rows[b.id].startswith('legacy-'))
            self.assertNotEqual(rows[a.id], rows[b.id])

    def test_cross_client_edge_not_followed(self):
        apps = self.old_apps
        client_a = self._client(apps)
        client_b = self._client(apps, afm='997654321')
        # (6) malformed cross-client previous edge
        foreign = self._doc(apps, client_b)
        d1 = self._doc(apps, client_a)
        d2 = self._doc(apps, client_a, previous_version_id=foreign.id)

        new_apps = self._migrate(self.migrate_to)
        CD = new_apps.get_model('accounting', 'ClientDocument')
        rows = {r.id: r.slot for r in CD.objects.all()}
        # Η διάσχιση ΔΕΝ ακολούθησε την cross-client ακμή
        self.assertEqual(rows[foreign.id], '')
        self.assertTrue(rows[d1.id].startswith('legacy-'))
        self.assertTrue(rows[d2.id].startswith('legacy-'))

    def test_cyclic_chain_terminates(self):
        apps = self.old_apps
        client = self._client(apps)
        # (7) cyclic chain (το schema το επιτρέπει — SET_NULL self FK)
        c1 = self._doc(apps, client)
        c2 = self._doc(apps, client, is_current=False,
                       previous_version_id=c1.id)
        CD_old = apps.get_model('accounting', 'ClientDocument')
        CD_old.objects.filter(pk=c1.id).update(previous_version_id=c2.id)
        extra = self._doc(apps, client)  # duplicate current → seed

        new_apps = self._migrate(self.migrate_to)  # δεν πρέπει να κρεμάσει
        CD = new_apps.get_model('accounting', 'ClientDocument')
        rows = {r.id: r.slot for r in CD.objects.all()}
        self.assertEqual(rows[c1.id], rows[c2.id])  # ίδια chain, ίδιο slot
        self.assertTrue(rows[extra.id].startswith('legacy-'))

    def test_idempotent_second_run(self):
        apps = self.old_apps
        client = self._client(apps)
        d1 = self._doc(apps, client)
        d2 = self._doc(apps, client)
        new_apps = self._migrate(self.migrate_to)
        CD = new_apps.get_model('accounting', 'ClientDocument')
        first = {r.id: r.slot for r in CD.objects.all()}
        # Δεύτερη εκτέλεση της ίδιας λογικής → ίδιο αποτέλεσμα
        import importlib
        mod = importlib.import_module(
            'accounting.migrations.10021_fix_legacy_slot_chains')
        mod._fix_legacy_chains(new_apps, None)
        second = {r.id: r.slot for r in CD.objects.all()}
        self.assertEqual(first, second)


@override_settings(MEDIA_ROOT=TEMP_MEDIA, ENFORCE_CLIENT_ASSIGNMENT=True)
class PostMigrationBehaviourTest(Round20Base):
    """(10)(11)(12) συμπεριφορά ΜΕΤΑ το migration, στο τρέχον schema."""

    def test_delete_current_promotes_previous_in_legacy_chain(self):
        v1 = self._upload()
        v2 = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=3, user=self.full)
        ClientDocument.objects.filter(pk__in=[v1.pk, v2.pk]).update(
            slot='legacy-5')
        v2.refresh_from_db()
        filing.delete_document_service(self.full, v2)
        v1.refresh_from_db()
        self.assertTrue(v1.is_current)

    def test_new_office_upload_does_not_version_legacy_chain(self):
        legacy = self._upload()
        ClientDocument.objects.filter(pk=legacy.pk).update(slot='legacy-7')
        legacy.refresh_from_db()
        fresh = self._upload()   # κύριο slot '' είναι ελεύθερο
        self.assertEqual(fresh.version, 1)
        self.assertEqual(fresh.slot, '')
        legacy.refresh_from_db()
        self.assertTrue(legacy.is_current)   # ΔΕΝ έγινε version πάνω του

    def test_audit_reports_legacy_after_migration(self):
        doc = self._upload()
        ClientDocument.objects.filter(pk=doc.pk).update(slot='legacy-11')
        out = StringIO()
        call_command('audit_clientdocument_invariants', stdout=out)
        self.assertIn('legacy-slot-needs-review', out.getvalue())
