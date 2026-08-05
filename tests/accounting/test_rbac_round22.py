# -*- coding: utf-8 -*-
"""
Γύρος 22 — closeout ευρημάτων ανεξάρτητου review πάνω στο 980e7b8.

P0. Migration 10021 σε branching chain (parent → δύο current children):
    ολοκληρώνεται χωρίς IntegrityError, τα δύο current μένουν σε
    διακριτά exact keys, το audit δίνει deterministic finding
    (legacy-branching-chain-needs-review), και κάθε επόμενη
    promote/delete/version λειτουργία είναι fail closed.
P1. SharedLink target invariant: document XOR client (serializer, model,
    DB CheckConstraint, admin/service paths, ασφαλές __str__).
P1/P2. Atomic revocation: ταυτόχρονη ανάκληση/λήξη/αλλαγή ρυθμίσεων
    ακυρώνει download/upload πριν από κάθε mutation.
P2. ClientViewSet.upload_document με ξένο/άκυρο obligation_id.
P3. Download quota + αποτυχία storage.open().
"""
import os
import shutil
import tempfile
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from accounting.models import (
    ClientDocument, ClientProfile, MonthlyObligation, ObligationType,
    SharedLink, SharedLinkAccess,
)
from accounting.services import filing
from tests.accounting.secure_client import SecureAPIClient

User = get_user_model()

TEMP_MEDIA = tempfile.mkdtemp(prefix='round22_test_')


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
# P0 — Migration 10021: parent με δύο current children
# ===========================================================================
class Migration10021ParentTwoCurrentChildrenTest(TransactionTestCase):
    """
    Το ακριβές σχήμα του ευρήματος:

              parent (historical)
              /              \\
        current_1          current_2      (ίδιο exact logical key)

    Πριν το fix, το 10021 έδινε σε parent + current_1 + current_2 το ΙΔΙΟ
    `legacy-{min_id}` slot και το δεύτερο UPDATE έσπαγε το
    uniq_current_doc_no_obligation → IntegrityError στη μέση του
    production migrate.
    """
    migrate_from = ('accounting', '10019_export_clientprofile_permission')
    migrate_to = ('accounting', '10022_sharedlink_target_invariant')

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

    def _build_branching(self, apps):
        CP = apps.get_model('accounting', 'ClientProfile')
        CD = apps.get_model('accounting', 'ClientDocument')
        client = CP.objects.create(afm='123456783', eponimia='ΔΙΑΚΛΑΔΩΣΗ ΑΕ',
                                   eidos_ipoxreou='company')
        common = dict(
            client_id=client.id, document_category='vat', year=2026,
            month=3, file='x.pdf', original_filename='x.pdf',
            filename='x.pdf', file_type='pdf', file_size=1)
        parent = CD.objects.create(version=1, is_current=False, **common)
        c1 = CD.objects.create(version=2, is_current=True,
                               previous_version_id=parent.id, **common)
        c2 = CD.objects.create(version=2, is_current=True,
                               previous_version_id=parent.id, **common)
        return client, parent, c1, c2

    def test_migration_completes_without_integrity_error(self):
        client, parent, c1, c2 = self._build_branching(self.old_apps)

        new_apps = self._migrate(self.migrate_to)   # δεν πρέπει να σκάσει
        CD = new_apps.get_model('accounting', 'ClientDocument')
        rows = {r.id: r for r in CD.objects.all()}

        # Και τα δύο current επιβιώνουν, σε ΔΙΑΚΡΙΤΑ exact keys
        self.assertTrue(rows[c1.id].is_current)
        self.assertTrue(rows[c2.id].is_current)
        self.assertNotEqual(rows[c1.id].slot, rows[c2.id].slot)
        # Κανένα demote/delete: ο parent παραμένει historical και υπαρκτός
        self.assertFalse(rows[parent.id].is_current)
        self.assertEqual(CD.objects.count(), 3)

    def test_db_constraints_still_enforced_after_migration(self):
        client, parent, c1, c2 = self._build_branching(self.old_apps)
        self._migrate(self.migrate_to)

        # Το partial unique constraint είναι ΕΝΕΡΓΟ: τρίτο current στο
        # ίδιο (client, category, year, month, slot='') απορρίπτεται
        existing_slot = ClientDocument.objects.get(pk=c1.id).slot
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ClientDocument.objects.create(
                    client_id=client.id, document_category='vat', year=2026,
                    month=3, slot=existing_slot, version=9, is_current=True,
                    file='z.pdf', original_filename='z.pdf',
                    filename='z.pdf', file_type='pdf', file_size=1)

    def test_audit_reports_one_deterministic_branching_finding(self):
        self._build_branching(self.old_apps)
        self._migrate(self.migrate_to)

        out = StringIO()
        call_command('audit_clientdocument_invariants', stdout=out)
        text = out.getvalue()
        self.assertEqual(text.count('legacy-branching-chain-needs-review'), 1)
        # Μόνο internal IDs — κανένα ΑΦΜ/filename/path
        self.assertNotIn('123456783', text)
        self.assertNotIn('ΔΙΑΚΛΑΔΩΣΗ', text)
        self.assertNotIn('x.pdf', text)

    def test_second_run_is_idempotent(self):
        self._build_branching(self.old_apps)
        new_apps = self._migrate(self.migrate_to)
        CD = new_apps.get_model('accounting', 'ClientDocument')
        first = {r.id: r.slot for r in CD.objects.all()}

        import importlib
        mod = importlib.import_module(
            'accounting.migrations.10021_fix_legacy_slot_chains')
        mod._fix_legacy_chains(new_apps, None)
        second = {r.id: r.slot for r in CD.objects.all()}
        self.assertEqual(first, second)

    def test_delete_on_ambiguous_chain_fails_closed(self):
        """
        Διαγραφή του current που θα προήγαγε τον parent σε ΗΔΗ
        κατειλημμένο exact key → ελεγχόμενο 409, ΟΧΙ δεύτερο current.
        """
        client, parent, c1, c2 = self._build_branching(self.old_apps)
        self._migrate(self.migrate_to)

        user = make_perm_user(
            'r22_del', ['add_clientdocument', 'change_clientdocument',
                        'delete_clientdocument'])
        target = ClientDocument.objects.get(pk=c2.id)
        parent_row = ClientDocument.objects.get(pk=parent.id)
        sibling = ClientDocument.objects.get(pk=c1.id)
        # Το σενάριο απαιτεί ο parent να μοιράζεται slot με το sibling
        if parent_row.slot != sibling.slot:
            ClientDocument.objects.filter(pk=parent_row.pk).update(
                slot=sibling.slot)

        with self.assertRaises(filing.DocumentKeyConflict):
            filing.delete_document_service(user, target)

        # Τίποτε δεν άλλαξε: κανένα row δεν χάθηκε, κανένα διπλό current
        self.assertEqual(ClientDocument.objects.count(), 3)
        self.assertFalse(
            ClientDocument.objects.get(pk=parent.id).is_current)
        currents = ClientDocument.objects.filter(
            client_id=client.id, is_current=True)
        self.assertEqual(currents.count(), 2)
        self.assertEqual(len({d.slot for d in currents}), 2)

    def test_promote_on_ambiguous_chain_keeps_one_current_per_key(self):
        client, parent, c1, c2 = self._build_branching(self.old_apps)
        self._migrate(self.migrate_to)
        user = make_perm_user('r22_prom', ['change_clientdocument'])

        parent_row = ClientDocument.objects.get(pk=parent.id)
        filing.promote_to_current_service(user, parent_row)

        # Η προαγωγή κατεβάζει ΜΟΝΟ τα siblings του ΙΔΙΟΥ exact key —
        # ποτέ δεν αφήνει δύο current στο ίδιο slot
        by_slot = {}
        for d in ClientDocument.objects.filter(client_id=client.id,
                                               is_current=True):
            by_slot.setdefault(d.slot, []).append(d.pk)
        for slot, pks in by_slot.items():
            self.assertEqual(len(pks), 1, f'διπλό current στο slot {slot!r}')


# ===========================================================================
# P1 — SharedLink target invariant
# ===========================================================================
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA)
class SharedLinkTargetInvariantTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        self.client_b = ClientProfile.objects.create(
            afm='997654321', eponimia='Β ΑΕ', eidos_ipoxreou='company')
        self.user = make_perm_user(
            'r22_link',
            ['add_clientdocument', 'view_clientdocument', 'view_clientprofile',
             'add_sharedlink', 'change_sharedlink', 'view_sharedlink',
             'delete_sharedlink'],
            [self.client_a, self.client_b])
        self.doc = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=3, user=self.user)
        self.api = SecureAPIClient()
        self.api.force_authenticate(self.user)

    def _create(self, payload):
        return self.api.post('/accounting/api/v1/file-manager/shared-links/',
                             payload, format='json')

    def test_create_with_two_targets_rejected(self):
        resp = self._create({'document_id': self.doc.id,
                             'client_id': self.client_b.id})
        self.assertEqual(resp.status_code, 400, resp.content[:200])
        self.assertEqual(SharedLink.objects.count(), 0)

    def test_create_without_target_rejected(self):
        resp = self._create({'name': 'χωρίς στόχο'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(SharedLink.objects.count(), 0)

    def test_patch_document_link_adding_client_rejected(self):
        link = SharedLink.objects.create(document=self.doc,
                                         created_by=self.user)
        resp = self.api.patch(
            f'/accounting/api/v1/file-manager/shared-links/{link.id}/',
            {'client': self.client_b.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content[:200])
        link.refresh_from_db()
        self.assertIsNone(link.client_id)

    def test_patch_client_link_adding_document_rejected(self):
        link = SharedLink.objects.create(client=self.client_b,
                                         created_by=self.user)
        resp = self.api.patch(
            f'/accounting/api/v1/file-manager/shared-links/{link.id}/',
            {'document': self.doc.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content[:200])
        link.refresh_from_db()
        self.assertIsNone(link.document_id)

    def test_patch_removing_only_target_rejected(self):
        link = SharedLink.objects.create(document=self.doc,
                                         created_by=self.user)
        resp = self.api.patch(
            f'/accounting/api/v1/file-manager/shared-links/{link.id}/',
            {'document': None}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content[:200])
        link.refresh_from_db()
        self.assertEqual(link.document_id, self.doc.id)

    def test_model_save_rejects_two_targets(self):
        with self.assertRaises(ValidationError):
            SharedLink.objects.create(document=self.doc,
                                      client=self.client_b)

    def test_model_save_rejects_no_target(self):
        with self.assertRaises(ValidationError):
            SharedLink.objects.create(name='ορφανό')

    def test_db_constraint_blocks_direct_orm_update(self):
        link = SharedLink.objects.create(document=self.doc)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                # Παράκαμψη του model save() — το DB constraint κρατά
                SharedLink.objects.filter(pk=link.pk).update(
                    client=self.client_b)

    def test_inactive_orphan_allowed_but_reactivation_blocked(self):
        # Legacy orphan διατηρείται ΑΝΕΝΕΡΓΟ (χωρίς διαγραφή)
        link = SharedLink.objects.create(document=self.doc)
        SharedLink.objects.filter(pk=link.pk).update(
            is_active=False, document=None)
        link.refresh_from_db()
        self.assertIsNone(link.document_id)
        self.assertFalse(link.is_active)

        # Reactivation χωρίς στόχο απορρίπτεται
        link.is_active = True
        with self.assertRaises(ValidationError):
            link.save()

    def test_str_safe_for_orphan_row(self):
        link = SharedLink.objects.create(document=self.doc)
        # Πλήρως ορφανό legacy row: χωρίς στόχο ΚΑΙ χωρίς name
        SharedLink.objects.filter(pk=link.pk).update(
            is_active=False, document=None, name='')
        link.refresh_from_db()
        # Δεν πρέπει να σκάσει με AttributeError και δίνει σαφές fallback
        self.assertIn('χωρίς στόχο', str(link))

    def test_str_safe_when_only_name_survives(self):
        link = SharedLink.objects.create(document=self.doc, name='Συμβόλαιο')
        SharedLink.objects.filter(pk=link.pk).update(
            is_active=False, document=None)
        link.refresh_from_db()
        self.assertEqual(str(link).split(' (')[0], 'Συμβόλαιο')

    def test_all_three_layers_agree_on_same_scenarios(self):
        """
        Model .save(), serializer (create/update) και DB constraint
        πρέπει να συμφωνούν: ό,τι απορρίπτει ο ένας, το απορρίπτουν όλοι.
        """
        scenarios = [
            ('δύο στόχοι', dict(document=self.doc, client=self.client_b)),
            ('κανένας στόχος', dict(document=None, client=None)),
        ]
        for label, kwargs in scenarios:
            with self.subTest(layer='model.save', scenario=label):
                with self.assertRaises(ValidationError):
                    SharedLink(is_active=True, **kwargs).save()

            with self.subTest(layer='serializer.create', scenario=label):
                payload = {}
                if kwargs['document']:
                    payload['document_id'] = kwargs['document'].id
                if kwargs['client']:
                    payload['client_id'] = kwargs['client'].id
                resp = self._create(payload)
                self.assertEqual(resp.status_code, 400, f'{label}: {resp.data}')

            with self.subTest(layer='db constraint', scenario=label):
                link = SharedLink.objects.create(document=self.doc)
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        SharedLink.objects.filter(pk=link.pk).update(
                            document=kwargs['document'], client=kwargs['client'])
                link.delete()

        # Και το ΕΓΚΥΡΟ σενάριο περνά και από τα τρία επίπεδα
        valid = SharedLink(document=self.doc)
        valid.save()
        self.assertEqual(valid.document_id, self.doc.id)
        self.assertIsNone(valid.client_id)

    def test_document_link_uploads_target_document_client(self):
        link = SharedLink.objects.create(document=self.doc, allow_upload=True)
        self.assertEqual(link.upload_target_client, self.doc.client)
        self.assertEqual(link.upload_target_client, self.client_a)


# ===========================================================================
# P1/P2 — Atomic revocation
# ===========================================================================
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA)
class SharedLinkAtomicRevocationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        self.user = make_perm_user(
            'r22_rev', ['add_clientdocument', 'view_clientprofile'],
            [self.client_a])
        self.doc = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=3, user=self.user)
        self.link = SharedLink.objects.create(
            document=self.doc, access_level='download', allow_upload=True,
            max_downloads=5, max_uploads=5)

    def _mutate(self, **fields):
        """Ταυτόχρονη αλλαγή, όπως θα την έβλεπε το in-memory instance."""
        SharedLink.objects.filter(pk=self.link.pk).update(**fields)

    def test_download_rejected_after_concurrent_deactivation(self):
        self._mutate(is_active=False)
        self.assertFalse(self.link.try_record_download())
        self.link.refresh_from_db()
        self.assertEqual(self.link.download_count, 0)

    def test_download_rejected_after_concurrent_expiration(self):
        self._mutate(expires_at=timezone.now() - timezone.timedelta(hours=1))
        self.assertFalse(self.link.try_record_download())
        self.link.refresh_from_db()
        self.assertEqual(self.link.download_count, 0)

    def test_download_rejected_after_password_change(self):
        self._mutate(password_hash='pbkdf2_sha256$νέο')
        self.assertFalse(self.link.try_record_download())
        self.assertEqual(
            SharedLink.objects.get(pk=self.link.pk).download_count, 0)

    def test_download_rejected_after_requires_email_change(self):
        self._mutate(requires_email=True)
        self.assertFalse(self.link.try_record_download())

    def test_download_rejected_after_token_regeneration(self):
        from accounting.models import generate_share_token
        self._mutate(token=generate_share_token())
        self.assertFalse(self.link.try_record_download())

    def test_download_rejected_after_access_level_downgrade(self):
        self._mutate(access_level='view')
        self.assertFalse(self.link.try_record_download())

    def test_download_rejected_after_target_change(self):
        other = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=4, user=self.user)
        self._mutate(document=other)
        self.assertFalse(self.link.try_record_download())

    def test_uploads_rejected_after_allow_upload_revoked(self):
        self._mutate(allow_upload=False)
        self.assertFalse(self.link.try_reserve_uploads(1))
        self.assertEqual(
            SharedLink.objects.get(pk=self.link.pk).upload_count, 0)

    def test_uploads_rejected_after_deactivation(self):
        self._mutate(is_active=False)
        self.assertFalse(self.link.try_reserve_uploads(1))

    def test_last_quota_slot_goes_to_exactly_one_caller(self):
        SharedLink.objects.filter(pk=self.link.pk).update(
            max_downloads=1, download_count=0)
        self.link.refresh_from_db()
        second = SharedLink.objects.get(pk=self.link.pk)
        self.assertTrue(self.link.try_record_download())
        self.assertFalse(second.try_record_download())
        self.assertEqual(
            SharedLink.objects.get(pk=self.link.pk).download_count, 1)

    def test_valid_link_still_works(self):
        self.assertTrue(self.link.try_record_download())
        self.assertTrue(self.link.try_reserve_uploads(2))


# ===========================================================================
# P3 — Download quota vs storage failure
# ===========================================================================
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA)
class DownloadQuotaStorageFailureTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        self.user = make_perm_user(
            'r22_dl', ['add_clientdocument', 'view_clientprofile'],
            [self.client_a])
        self.doc = filing.create_client_document(
            client=self.client_a, uploaded_file=pdf_upload(),
            category='vat', year=2026, month=3, user=self.user)
        self.link = SharedLink.objects.create(
            document=self.doc, access_level='download', max_downloads=1)
        self.web = SecureAPIClient()

    def test_storage_failure_does_not_consume_quota_or_log(self):
        url = f'/accounting/share/{self.link.token}/download/'
        with mock.patch(
                'django.db.models.fields.files.FieldFile.open',
                side_effect=OSError('storage κάτω')):
            resp = self.web.get(url)
        self.assertEqual(resp.status_code, 404)

        self.link.refresh_from_db()
        # Το slot ΔΕΝ καταναλώθηκε — ο πελάτης μπορεί να ξαναδοκιμάσει
        self.assertEqual(self.link.download_count, 0)
        # Κανένα success access log
        self.assertEqual(
            SharedLinkAccess.objects.filter(
                shared_link=self.link, action='download').count(), 0)

    def test_successful_download_consumes_exactly_one_slot(self):
        url = f'/accounting/share/{self.link.token}/download/'
        resp = self.web.get(url)
        try:
            self.assertEqual(resp.status_code, 200)

            # ΠΡΟΣΟΧΗ (σειρά): τα DB assertions ΠΡΙΝ το resp.close(). Το
            # close() ενός FileResponse πυροδοτεί το signal
            # `request_finished`, που κλείνει το DB connection — σε
            # PostgreSQL κάθε επόμενο query σκάει με InterfaceError
            # (σε SQLite περνάει σιωπηλά).
            self.link.refresh_from_db()
            self.assertEqual(self.link.download_count, 1)
            self.assertEqual(
                SharedLinkAccess.objects.filter(
                    shared_link=self.link, action='download').count(), 1)
        finally:
            # Το FileResponse κλείνει ΠΑΝΤΑ, ακόμη κι αν αποτύχει
            # κάποιο assertion — κανένα streaming handle δεν διαρρέει.
            resp.close()

    def test_file_handle_closed_when_guard_rejects(self):
        """
        Όταν ο atomic guard απορρίπτει (ταυτόχρονη ανάκληση), κανένα file
        handle δεν μένει ανοιχτό: το άνοιγμα γίνεται ΜΕΤΑ τη δέσμευση.
        """
        opened = []
        real_open = ClientDocument.file.field.attr_class.open

        def tracking_open(self_field, mode='rb'):
            handle = real_open(self_field, mode)
            opened.append(handle)
            return handle

        SharedLink.objects.filter(pk=self.link.pk).update(is_active=False)
        with mock.patch.object(
                ClientDocument.file.field.attr_class, 'open', tracking_open):
            resp = self.web.get(
                f'/accounting/share/{self.link.token}/download/')
        self.assertEqual(resp.status_code, 410)
        # Ούτε καν ανοίχτηκε αρχείο — άρα τίποτε δεν έμεινε ανοιχτό
        self.assertEqual(opened, [])
        self.assertEqual(
            SharedLinkAccess.objects.filter(shared_link=self.link).count(), 0)

    def test_release_does_not_compensate_another_requests_download(self):
        """
        Το release_download() ενός αποτυχημένου request δεν επιτρέπεται να
        «σβήσει» το slot ενός ΑΛΛΟΥ επιτυχημένου download.
        """
        SharedLink.objects.filter(pk=self.link.pk).update(max_downloads=2)
        first = SharedLink.objects.get(pk=self.link.pk)
        second = SharedLink.objects.get(pk=self.link.pk)

        self.assertTrue(first.try_record_download())    # επιτυχημένο
        self.assertTrue(second.try_record_download())   # θα αποτύχει στο storage
        second.release_download()                       # compensation

        self.link.refresh_from_db()
        # Μένει ακριβώς το slot του πρώτου request
        self.assertEqual(self.link.download_count, 1)

    def test_release_download_cannot_underflow(self):
        self.link.release_download()
        self.link.release_download()
        self.link.refresh_from_db()
        self.assertEqual(self.link.download_count, 0)


# ===========================================================================
# P2 — Nested client document upload με άκυρο obligation
# ===========================================================================
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA)
class NestedUploadObligationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        self.client_b = ClientProfile.objects.create(
            afm='997654321', eponimia='Β ΑΕ', eidos_ipoxreou='company')
        ob_type = ObligationType.objects.create(
            name='ΦΠΑ22', code='FPA22', is_active=True)
        self.foreign_ob = MonthlyObligation.objects.create(
            client=self.client_b, obligation_type=ob_type, month=3,
            year=2026, deadline=timezone.now().date())
        self.own_ob = MonthlyObligation.objects.create(
            client=self.client_a, obligation_type=ob_type, month=4,
            year=2026, deadline=timezone.now().date())
        self.user = make_perm_user(
            'r22_nested',
            ['add_clientdocument', 'view_clientdocument', 'view_clientprofile',
             'view_monthlyobligation'],
            [self.client_a])
        self.api = SecureAPIClient()
        self.api.force_authenticate(self.user)

    def _upload(self, obligation_id):
        return self.api.post(
            f'/accounting/api/v1/clients/{self.client_a.id}/documents/upload/',
            {'file': pdf_upload(), 'category': 'vat',
             'obligation_id': obligation_id},
            format='multipart')

    def _media_files(self):
        found = []
        for root, _dirs, files in os.walk(TEMP_MEDIA):
            found.extend(os.path.join(root, f) for f in files)
        return set(found)

    def test_foreign_obligation_returns_neutral_404_without_side_effects(self):
        before_docs = ClientDocument.objects.count()
        before_files = self._media_files()
        resp = self._upload(self.foreign_ob.id)
        self.assertEqual(resp.status_code, 404, resp.content[:200])
        self.assertEqual(ClientDocument.objects.count(), before_docs)
        self.assertEqual(self._media_files(), before_files)

    def test_nonexistent_obligation_returns_same_neutral_404(self):
        resp_missing = self._upload(99999999)
        resp_foreign = self._upload(self.foreign_ob.id)
        # Ίδιο status ΚΑΙ ίδιο σώμα — καμία αποκάλυψη ύπαρξης
        self.assertEqual(resp_missing.status_code, 404)
        self.assertEqual(resp_missing.status_code, resp_foreign.status_code)
        self.assertEqual(resp_missing.data, resp_foreign.data)

    def test_invalid_format_returns_400(self):
        resp = self._upload('όχι-αριθμός')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(ClientDocument.objects.count(), 0)

    def test_missing_obligation_permission_returns_403(self):
        no_perm = make_perm_user(
            'r22_noperm',
            ['add_clientdocument', 'view_clientdocument',
             'view_clientprofile'],
            [self.client_a])
        api = SecureAPIClient()
        api.force_authenticate(no_perm)
        resp = api.post(
            f'/accounting/api/v1/clients/{self.client_a.id}/documents/upload/',
            {'file': pdf_upload(), 'obligation_id': self.own_ob.id},
            format='multipart')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(ClientDocument.objects.count(), 0)

    def test_own_obligation_still_works(self):
        resp = self._upload(self.own_ob.id)
        self.assertEqual(resp.status_code, 201, resp.content[:200])
        doc = ClientDocument.objects.get()
        self.assertEqual(doc.obligation_id, self.own_ob.id)
        self.assertEqual(doc.client_id, self.client_a.id)

    def test_no_obligation_id_still_works(self):
        resp = self.api.post(
            f'/accounting/api/v1/clients/{self.client_a.id}/documents/upload/',
            {'file': pdf_upload(), 'category': 'vat'}, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.content[:200])
        self.assertIsNone(ClientDocument.objects.get().obligation_id)
