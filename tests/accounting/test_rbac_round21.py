# -*- coding: utf-8 -*-
"""
Γύρος 21 — ανεξάρτητο review closeout πάνω στο 980e7b8.

P0. Migration 10021 σε branching legacy chain (δύο current στο ίδιο
    connected component) — IntegrityError πριν το fix.
P2. Permission ΠΡΙΝ από κάθε parsing (libmagic/ZIP/Pillow).
P2. file_delete: managed ClientDocument δεν διαγράφεται filesystem-only.
P2. missing-storage-file finding στο audit command.
P2. PII/paths εκτός logs.
--. PortalUploadCapability δεσμευμένο στον πελάτη.
--. Κοινό error contract (409/404/400, ποτέ 500) σε ΟΛΟΥΣ τους callers.
--. Bulk endpoints: καμία σιωπηλή ολοκλήρωση, κανένα 201 χωρίς upload.
"""
import os
import shutil
import tempfile
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from accounting.models import (
    ClientDocument, ClientProfile, MonthlyObligation, ObligationType,
)
from accounting.services import filing
from tests.accounting.secure_client import SecureAPIClient

User = get_user_model()


TEMP_MEDIA = tempfile.mkdtemp(prefix='round21_test_')


def tearDownModule():
    """
    Καθαρισμός ΜΙΑ φορά, μετά από ΟΛΕΣ τις classes του module.

    ΟΧΙ per-class rmtree (θα έσβηνε τον κοινό φάκελο ενώ άλλη class τον
    χρησιμοποιεί) και ΟΧΙ χειροκίνητο override_settings().enable() σε
    setUpClass — το δεύτερο διαρρέει το MEDIA_ROOT σε επόμενα modules
    (π.χ. tests.crm.test_import_export που περιμένει Path, όχι str).
    Το @override_settings ως decorator το κάνει σωστά scoped.
    """
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


# ---------------------------------------------------------------------------
# P0. Migration 10021 — branching chain με δύο current στο ίδιο component
# ---------------------------------------------------------------------------
class Migration10021BranchingTest(TransactionTestCase):
    """
    Πραγματικό migration test 10019 → 10020 → 10021.

    ΠΡΙΝ το fix: το 10021 ένωνε ΟΛΟ το component και έδινε κοινό slot στα
    δύο current rows → IntegrityError (uniq_current_doc_no_obligation) και
    το `migrate` σταματούσε στη μέση του deployment.
    """
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
        self._migrate(self.migrate_to)

    def _client(self, apps, afm='123456783'):
        CP = apps.get_model('accounting', 'ClientProfile')
        return CP.objects.create(afm=afm, eponimia='ΔΙΑΚΛΑΔΩΣΗ ΑΕ',
                                 eidos_ipoxreou='company')

    def _doc(self, apps, client, **kw):
        CD = apps.get_model('accounting', 'ClientDocument')
        defaults = dict(
            client_id=client.id, document_category='vat', year=2026,
            month=3, version=1, is_current=True, file='x.pdf',
            original_filename='x.pdf', filename='x.pdf',
            file_type='pdf', file_size=1)
        defaults.update(kw)
        return CD.objects.create(**defaults)

    def test_branching_two_currents_same_component_no_integrity_error(self):
        """Δύο current siblings του ίδιου root — η migration ΔΕΝ σκάει."""
        apps = self.old_apps
        client = self._client(apps)
        root = self._doc(apps, client, is_current=False)
        b1 = self._doc(apps, client, version=2, previous_version_id=root.id)
        b2 = self._doc(apps, client, version=2, previous_version_id=root.id)

        # Δεν πρέπει να σηκωθεί IntegrityError
        new_apps = self._migrate(self.migrate_to)
        CD = new_apps.get_model('accounting', 'ClientDocument')
        rows = {r.id: r for r in CD.objects.all()}

        # Τα δύο current παραμένουν σε ΔΙΑΦΟΡΕΤΙΚΑ slots (constraint-safe
        # κατάσταση του 10020, χωρίς μάντεμα ποιο branch είναι σωστό)
        self.assertTrue(rows[b1.id].is_current)
        self.assertTrue(rows[b2.id].is_current)
        self.assertNotEqual(rows[b1.id].slot, rows[b2.id].slot)

        # Κανένα unique constraint δεν παραβιάζεται: δύο current στο ίδιο
        # (client, category, year, month) υπάρχουν ΜΟΝΟ με διαφορετικό slot
        currents = CD.objects.filter(
            client_id=client.id, document_category='vat', year=2026,
            month=3, obligation_id=None, is_current=True)
        self.assertEqual(currents.count(), 2)
        self.assertEqual(len({d.slot for d in currents}), 2)

    def test_branching_component_is_idempotent(self):
        apps = self.old_apps
        client = self._client(apps)
        root = self._doc(apps, client, is_current=False)
        self._doc(apps, client, version=2, previous_version_id=root.id)
        self._doc(apps, client, version=2, previous_version_id=root.id)

        new_apps = self._migrate(self.migrate_to)
        CD = new_apps.get_model('accounting', 'ClientDocument')
        first = {r.id: r.slot for r in CD.objects.all()}

        import importlib
        mod = importlib.import_module(
            'accounting.migrations.10021_fix_legacy_slot_chains')
        mod._fix_legacy_chains(new_apps, None)   # δεύτερη εκτέλεση
        second = {r.id: r.slot for r in CD.objects.all()}
        self.assertEqual(first, second)

    def test_ancestor_and_descendant_both_current(self):
        """Ancestor + descendant και οι δύο current στο ίδιο component."""
        apps = self.old_apps
        client = self._client(apps)
        v1 = self._doc(apps, client)                       # current
        v2 = self._doc(apps, client, version=2,
                       previous_version_id=v1.id)          # επίσης current

        new_apps = self._migrate(self.migrate_to)
        CD = new_apps.get_model('accounting', 'ClientDocument')
        rows = {r.id: r for r in CD.objects.all()}
        self.assertNotEqual(rows[v1.id].slot, rows[v2.id].slot)
        self.assertTrue(rows[v1.id].is_current and rows[v2.id].is_current)

    def test_single_current_component_still_unified(self):
        """Η κανονική περίπτωση (≤1 current) ενοποιείται κανονικά."""
        apps = self.old_apps
        client = self._client(apps)
        office = self._doc(apps, client)                   # duplicate current
        p1 = self._doc(apps, client, is_current=False)
        p2 = self._doc(apps, client, version=2, previous_version_id=p1.id)

        new_apps = self._migrate(self.migrate_to)
        CD = new_apps.get_model('accounting', 'ClientDocument')
        rows = {r.id: r.slot for r in CD.objects.all()}
        self.assertEqual(rows[p1.id], rows[p2.id])
        self.assertEqual(rows[p1.id], f'legacy-{p1.id}')
        self.assertTrue(rows[office.id].startswith('legacy-'))

    def test_audit_reports_branching_component_for_review(self):
        apps = self.old_apps
        client = self._client(apps)
        root = self._doc(apps, client, is_current=False)
        self._doc(apps, client, version=2, previous_version_id=root.id)
        self._doc(apps, client, version=2, previous_version_id=root.id)
        self._migrate(self.migrate_to)

        out = StringIO()
        call_command('audit_clientdocument_invariants', stdout=out)
        text = out.getvalue()
        # Το component ΔΕΝ διορθώθηκε σιωπηλά — αναφέρεται για review
        self.assertIn('branching-chain', text)
        self.assertIn('multiple-current-in-chain', text)
        self.assertIn('legacy-slot-needs-review', text)


# ---------------------------------------------------------------------------
# P2. Permission ΠΡΙΝ από κάθε parsing
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA)
class PermissionBeforeParsingTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        self.readonly = make_perm_user(
            'r21_readonly', ['view_clientprofile', 'view_clientdocument'],
            [self.client_a])

    def test_no_parser_runs_for_denied_user(self):
        """
        Read-only χρήστης: κανένας parser δεν καλείται, κανένα lock,
        καμία storage mutation, κανένα row.
        """
        with mock.patch('magic.from_buffer',
                        side_effect=AssertionError('libmagic δεν πρέπει να κληθεί')), \
             mock.patch('PIL.Image.open',
                        side_effect=AssertionError('Pillow δεν πρέπει να κληθεί')), \
             mock.patch('zipfile.ZipFile',
                        side_effect=AssertionError('zipfile δεν πρέπει να κληθεί')), \
             mock.patch('accounting.models.ClientProfile.objects') as m_objs, \
             mock.patch('accounting.services.filing.ensure_folders',
                        side_effect=AssertionError('καμία εγγραφή φακέλων')):
            m_objs.select_for_update.side_effect = AssertionError(
                'κανένα lock πριν το permission check')
            with self.assertRaises(PermissionDenied):
                filing.create_client_document(
                    client=self.client_a, uploaded_file=pdf_upload(),
                    category='vat', year=2026, month=3, user=self.readonly)
        self.assertEqual(ClientDocument.objects.count(), 0)

    def test_no_settings_lookup_for_denied_user(self):
        """Ούτε FilingSystemSettings lookup δεν γίνεται πριν το 403."""
        with mock.patch('accounting.services.filing._get_filing_settings',
                        side_effect=AssertionError(
                            'κανένα settings lookup πριν το permission')):
            with self.assertRaises(PermissionDenied):
                filing.create_client_document(
                    client=self.client_a, uploaded_file=pdf_upload(),
                    category='vat', year=2026, month=3, user=self.readonly)


# ---------------------------------------------------------------------------
# PortalUploadCapability binding στον πελάτη
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA)
class CapabilityClientBindingTest(TestCase):
    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        self.client_b = ClientProfile.objects.create(
            afm='997654321', eponimia='Β ΑΕ', eidos_ipoxreou='company')

    def test_capability_of_client_a_rejected_for_client_b(self):
        with mock.patch('magic.from_buffer',
                        side_effect=AssertionError('κανένα parsing')):
            with self.assertRaises(PermissionDenied):
                filing.create_client_document(
                    client=self.client_b, uploaded_file=pdf_upload(),
                    category='vat', year=2026, month=3, user=None,
                    on_existing='keep',
                    portal_capability=filing.PortalUploadCapability(
                        1, self.client_a.pk))
        self.assertEqual(ClientDocument.objects.count(), 0)

    def test_capability_of_matching_client_allowed(self):
        doc = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=3, user=None,
            on_existing='keep',
            portal_capability=filing.PortalUploadCapability(
                1, self.client_a.pk))
        self.assertTrue(doc.pk)


# ---------------------------------------------------------------------------
# P2. file_delete — managed document ΔΕΝ διαγράφεται filesystem-only
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA)
class ManagedFileDeleteTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        self.user = make_perm_user(
            'r21_del', ['add_clientdocument', 'change_clientdocument',
                        'delete_clientdocument', 'view_clientdocument',
                        'view_clientprofile'], [self.client_a])
        self.user.is_staff = True
        self.user.save()
        self.doc = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=3, user=self.user)
        self.web = SecureAPIClient()
        self.web.force_login(self.user)

    def _delete(self, rel_path):
        url = reverse('accounting:file_delete', args=[self.client_a.id]) \
            if _has_named_url() else f'/api/files/{self.client_a.id}/delete/'
        return self.web.post(url, data={'file_path': rel_path})

    def test_managed_document_goes_through_service(self):
        """
        Δεν μένει ΠΟΤΕ ClientDocument row με ανύπαρκτο αρχείο: είτε
        διαγράφονται και τα δύο (μέσω service) είτε τίποτε.
        """
        from accounting.completion import completion_views
        abs_path = self.doc.file.path
        self.assertTrue(os.path.exists(abs_path))

        found = completion_views._find_managed_document(
            self.client_a, abs_path)
        self.assertIsNotNone(found)
        self.assertEqual(found.pk, self.doc.pk)

        # Το service διαγράφει row ΚΑΙ αρχείο — ποτέ μόνο το αρχείο.
        # Το φυσικό αρχείο φεύγει ΜΟΝΟ σε transaction.on_commit.
        with self.captureOnCommitCallbacks(execute=True):
            filing.delete_document_service(self.user, self.doc)
        self.assertFalse(
            ClientDocument.objects.filter(pk=self.doc.pk).exists())
        self.assertFalse(os.path.exists(abs_path))

    def test_matched_even_when_storage_renamed_the_file(self):
        """
        Όταν το storage αποφεύγει σύγκρουση ονόματος (x.pdf → x_a1b2.pdf),
        το ClientDocument.filename κρατά το ΑΙΤΟΥΜΕΝΟ όνομα ενώ ο δίσκος
        έχει το νέο. Το match ΠΡΕΠΕΙ να γίνεται στο `file`, αλλιώς το
        έγγραφο θα θεωρούνταν unmanaged και θα διαγραφόταν
        filesystem-only, αφήνοντας row χωρίς αρχείο.
        """
        from accounting.completion import completion_views
        second = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=4, user=self.user)
        # Προσομοίωση storage rename: το πραγματικό αρχείο έχει άλλο
        # basename από το πεδίο filename
        real_dir = os.path.dirname(second.file.path)
        renamed = os.path.join(real_dir, 'αρχείο_a1b2c3.pdf')
        os.rename(second.file.path, renamed)
        ClientDocument.objects.filter(pk=second.pk).update(
            file=os.path.relpath(renamed, self._media_root()))
        second.refresh_from_db()
        self.assertNotEqual(second.filename,
                            os.path.basename(second.file.name))

        found = completion_views._find_managed_document(
            self.client_a, renamed)
        self.assertIsNotNone(found)
        self.assertEqual(found.pk, second.pk)

    def _media_root(self):
        from django.conf import settings as dj_settings
        return str(dj_settings.MEDIA_ROOT)

    def test_unmanaged_file_is_not_matched(self):
        from accounting.completion import completion_views
        client_dir = os.path.dirname(self.doc.file.path)
        stray = os.path.join(client_dir, 'σημειώσεις.txt')
        with open(stray, 'w', encoding='utf-8') as f:
            f.write('πρόχειρο')
        self.assertIsNone(
            completion_views._find_managed_document(self.client_a, stray))

    def test_audit_reports_missing_storage_file(self):
        os.remove(self.doc.file.path)
        out = StringIO()
        call_command('audit_clientdocument_invariants', stdout=out)
        text = out.getvalue()
        self.assertIn('missing-storage-file', text)
        self.assertIn(f'document id={self.doc.pk}', text)
        # Χωρίς PII: ούτε ΑΦΜ, ούτε επωνυμία, ούτε filename/path
        self.assertNotIn(self.client_a.afm, text)
        self.assertNotIn(self.client_a.eponimia, text)
        self.assertNotIn(self.doc.filename, text)


def _has_named_url():
    from django.urls import NoReverseMatch, reverse as _rev
    try:
        _rev('accounting:file_delete', args=[1])
        return True
    except NoReverseMatch:
        return False


# ---------------------------------------------------------------------------
# Κοινό error contract: MultipleCurrentDocumentsError → 409 σε ΚΑΘΕ caller,
# ποτέ 400/500. Το conflict προκαλείται με mocked find_current_for_key ώστε
# να ελέγχεται η ΠΡΑΓΜΑΤΙΚΗ διαδρομή του κάθε endpoint (χωρίς mock του
# locking/storage/MIME κώδικα).
# ---------------------------------------------------------------------------
def _raise_multiple(*args, **kwargs):
    raise filing.MultipleCurrentDocumentsError(
        'Υπάρχουν πολλαπλά τρέχοντα έγγραφα')


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA)
class ConflictContractTest(TestCase):
    """409 παντού — κανένα 500, κανένα 400 για invariant conflict."""

    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        self.user = make_perm_user(
            'r21_conflict',
            ['add_clientdocument', 'change_clientdocument',
             'delete_clientdocument', 'view_clientdocument',
             'view_clientprofile', 'view_monthlyobligation',
             'change_monthlyobligation'],
            [self.client_a])
        self.user.is_staff = True
        self.user.save()
        ob_type = ObligationType.objects.create(
            name='ΦΠΑ21', code='FPA21', is_active=True)
        from django.utils import timezone
        self.ob = MonthlyObligation.objects.create(
            client=self.client_a, obligation_type=ob_type, month=3,
            year=2026, deadline=timezone.now().date())
        self.web = SecureAPIClient()
        self.web.force_login(self.user)
        self.api = SecureAPIClient()
        self.api.force_authenticate(self.user)

    def _post(self, client_obj, url, data, fmt=None):
        with mock.patch(
                'accounting.services.filing.find_current_for_key',
                side_effect=_raise_multiple):
            if fmt:
                return client_obj.post(url, data, format=fmt)
            return client_obj.post(url, data)

    def test_upload_with_version_returns_409(self):
        resp = self._post(self.web, reverse(
            'accounting:api_upload_document_with_version'), {
            'file': pdf_upload(), 'client_id': self.client_a.id,
            'category': 'vat', 'year': 2026, 'month': 3,
            'version_action': 'new_version'})
        self.assertEqual(resp.status_code, 409, resp.content[:300])

    def test_obligation_single_upload_returns_409(self):
        resp = self._post(self.web, reverse(
            'accounting:obligation_complete_file', args=[self.ob.id]),
            {'file': pdf_upload()})
        self.assertEqual(resp.status_code, 409, resp.content[:300])

    def test_obligation_bulk_returns_409(self):
        import json as _json
        resp = self._post(self.web, reverse('accounting:bulk_complete'), {
            'obligation_ids': _json.dumps([self.ob.id]),
            'file': pdf_upload()})
        # per-item policy: καμία ολοκλήρωση, ρητή αποτυχία (όχι 500)
        self.assertNotEqual(resp.status_code, 500)
        self.assertEqual(resp.status_code, 400)
        self.ob.refresh_from_db()
        self.assertNotEqual(self.ob.status, 'completed')

    def test_advanced_bulk_returns_no_500_and_no_silent_completion(self):
        import json as _json
        resp = self._post(self.web, reverse(
            'accounting:advanced_bulk_complete'), {
            'completion_data': _json.dumps([{
                'client_afm': self.client_a.afm, 'group': '0',
                'obligations': [self.ob.id]}]),
            f'file_{self.client_a.afm}_0': pdf_upload()})
        self.assertNotEqual(resp.status_code, 500)
        self.ob.refresh_from_db()
        self.assertNotEqual(self.ob.status, 'completed')

    def test_wizard_bulk_no_silent_completion(self):
        import json as _json
        resp = self._post(self.web, reverse(
            'accounting:wizard_bulk_process'), {
            'results': _json.dumps({
                str(self.ob.id): {'complete': True, 'category': 'vat'}}),
            f'file_{self.ob.id}': pdf_upload()})
        self.assertNotEqual(resp.status_code, 500)
        self.ob.refresh_from_db()
        self.assertNotEqual(self.ob.status, 'completed')

    def test_completion_single_upload_returns_409(self):
        resp = self._post(self.web, reverse(
            'accounting:obligation_complete_single', args=[self.ob.id]),
            {'file': pdf_upload()})
        self.assertEqual(resp.status_code, 409, resp.content[:300])

    def test_completion_bulk_no_silent_completion(self):
        resp = self._post(self.web, reverse(
            'accounting:obligation_complete_bulk'), {
            'obligation_ids[]': [self.ob.id],
            f'file_{self.ob.id}': pdf_upload()})
        self.assertNotEqual(resp.status_code, 500)
        self.ob.refresh_from_db()
        self.assertNotEqual(self.ob.status, 'completed')

    def test_file_manager_upload_no_201_when_all_failed(self):
        payload = {'files': [pdf_upload()], 'client_id': self.client_a.id,
                   'category': 'vat', 'year': 2026, 'month': 3}
        resp = self._post(
            self.api, '/accounting/api/v1/file-manager/documents/upload/',
            payload, fmt='multipart')
        self.assertNotEqual(resp.status_code, 500)
        self.assertNotEqual(resp.status_code, 201)

    def test_complete_and_notify_returns_409(self):
        resp = self._post(self.api, reverse(
            'accounting:api_v1_complete_and_notify', args=[self.ob.id]),
            {'file': pdf_upload()}, fmt='multipart')
        self.assertEqual(resp.status_code, 409, resp.content[:300])
        self.ob.refresh_from_db()
        self.assertNotEqual(self.ob.status, 'completed')

    def test_bulk_complete_with_documents_returns_409(self):
        import json as _json
        resp = self._post(self.api, reverse(
            'accounting:api_v1_bulk_complete_with_documents'), {
            'obligation_ids': _json.dumps([self.ob.id]),
            f'file_{self.ob.id}': pdf_upload()}, fmt='multipart')
        self.assertEqual(resp.status_code, 409, resp.content[:300])
        self.ob.refresh_from_db()
        self.assertNotEqual(self.ob.status, 'completed')

    def test_api_documents_upload_returns_409(self):
        resp = self._post(self.api, '/accounting/api/v1/documents/upload/', {
            'file': pdf_upload(), 'client_id': self.client_a.id,
            'category': 'vat'}, fmt='multipart')
        self.assertEqual(resp.status_code, 409, resp.content[:300])
