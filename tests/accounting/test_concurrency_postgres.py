# -*- coding: utf-8 -*-
"""
PostgreSQL concurrency tests για το filing service (Γύρος 18 — F2).

Το select_for_update είναι no-op στο SQLite, οπότε η απόδειξη του race
protection γίνεται ΜΟΝΟ σε πραγματικό PostgreSQL: δύο ταυτόχρονα
first-create uploads στο ίδιο exact conflict key δεν πρέπει να αφήνουν
δύο current rows — το parent lock (ClientProfile / MonthlyObligation)
σειριοποιεί τα requests.

Τρέχει στο CI job `postgres-concurrency` (postgres service). ΔΕΝ είναι
skipped: αν κληθεί σε μη-PostgreSQL βάση αποτυγχάνει με σαφές μήνυμα,
ώστε να μην μπορεί να «περάσει» σιωπηλά χωρίς να τρέξει.
"""
import shutil
import tempfile
import threading

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, connections
from django.test import TransactionTestCase, override_settings

from accounting.models import ClientDocument, ClientProfile
from accounting.services import filing

User = get_user_model()

TEMP_MEDIA = tempfile.mkdtemp(prefix='pg_conc_test_')


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ConcurrentFirstCreateTest(TransactionTestCase):
    """Δύο ταυτόχρονα πρώτα uploads στο ίδιο key → ακριβώς ένα current."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        if connection.vendor != 'postgresql':
            import os
            if os.environ.get('REQUIRE_POSTGRES_TESTS') == '1':
                # CI: ΔΕΝ επιτρέπεται σιωπηλό skip — hard failure
                self.fail(
                    'Το REQUIRE_POSTGRES_TESTS=1 απαιτεί PostgreSQL backend '
                    '— το concurrency test δεν έτρεξε πραγματικά.')
            self.skipTest(
                'Απαιτεί PostgreSQL — τρέχει blocking στο CI test job '
                '(REQUIRE_POSTGRES_TESTS=1).')
        self.client_profile = ClientProfile.objects.create(
            afm='123456783', eponimia='PG ΑΕ', eidos_ipoxreou='company')
        self.user = User.objects.create_user('pg_user', password='x')
        for codename in ('add_clientdocument', 'change_clientdocument'):
            self.user.user_permissions.add(Permission.objects.get(
                codename=codename, content_type__app_label='accounting'))
        self.user = User.objects.get(pk=self.user.pk)

    def test_two_concurrent_first_creates_single_current(self):
        barrier = threading.Barrier(2)
        errors = []

        def upload(idx):
            try:
                barrier.wait(timeout=10)
                filing.create_client_document(
                    client=self.client_profile,
                    uploaded_file=SimpleUploadedFile(
                        f'ταυτόχρονο_{idx}.pdf', b'%PDF-1.4 concurrent'),
                    category='vat', year=2026, month=3,
                    user=self.user, on_existing='version',
                )
            except Exception as e:  # pragma: no cover - διαγνωστικό
                errors.append(e)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=upload, args=(i,))
                   for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        self.assertFalse(errors, f'Σφάλματα στα threads: {errors}')
        docs = ClientDocument.objects.filter(
            client=self.client_profile, document_category='vat',
            year=2026, month=3, obligation__isnull=True)
        self.assertEqual(docs.count(), 2)
        currents = docs.filter(is_current=True)
        # Η ουσία του race protection: ΠΟΤΕ δύο current rows
        self.assertEqual(currents.count(), 1)
        self.assertEqual(currents.first().version, 2)


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ConcurrentAttachTest(TransactionTestCase):
    """Γύρος 19: ταυτόχρονα structural mutations στο ίδιο target key."""

    def setUp(self):
        if connection.vendor != 'postgresql':
            import os
            if os.environ.get('REQUIRE_POSTGRES_TESTS') == '1':
                self.fail(
                    'Το REQUIRE_POSTGRES_TESTS=1 απαιτεί PostgreSQL backend '
                    '— το concurrency test δεν έτρεξε πραγματικά.')
            self.skipTest('Απαιτεί PostgreSQL — τρέχει blocking στο CI.')
        from accounting.models import MonthlyObligation, ObligationType
        from django.utils import timezone
        self.client_profile = ClientProfile.objects.create(
            afm='123456783', eponimia='PG ΑΕ', eidos_ipoxreou='company')
        self.user = User.objects.create_user('pg_at_user', password='x')
        for codename in ('add_clientdocument', 'change_clientdocument'):
            self.user.user_permissions.add(Permission.objects.get(
                codename=codename, content_type__app_label='accounting'))
        self.user = User.objects.get(pk=self.user.pk)
        ob_type = ObligationType.objects.create(
            name='ΦΠΑ-PG', code='FPA-PG', is_active=True)
        ob_type2 = ObligationType.objects.create(
            name='ΑΠΔ-PG', code='APD-PG', is_active=True)
        self.ob1 = MonthlyObligation.objects.create(
            client=self.client_profile, obligation_type=ob_type, month=3,
            year=2026, deadline=timezone.now().date())
        self.ob2 = MonthlyObligation.objects.create(
            client=self.client_profile, obligation_type=ob_type2, month=3,
            year=2026, deadline=timezone.now().date())

    def _mk_doc(self, obligation=None):
        return filing.create_client_document(
            client=self.client_profile,
            uploaded_file=SimpleUploadedFile('pg.pdf', b'%PDF-1.4 x'),
            category='vat', year=2026, month=3, obligation=obligation,
            user=self.user)

    def test_two_concurrent_attach_same_target_key(self):
        doc_a = self._mk_doc()             # standalone (vat, 2026/3, null)
        doc_b = self._mk_doc(self.ob2)     # (vat, 2026/3, ob2)
        barrier = threading.Barrier(2)
        results = {}

        def attach(name, doc):
            try:
                barrier.wait(timeout=10)
                filing.attach_document_service(self.user, doc, self.ob1)
                results[name] = 'ok'
            except filing.DocumentKeyConflict:
                results[name] = 'conflict'
            except Exception as e:  # pragma: no cover
                results[name] = f'error:{e}'
            finally:
                connections.close_all()

        threads = [threading.Thread(target=attach, args=('a', doc_a)),
                   threading.Thread(target=attach, args=('b', doc_b))]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        # Ακριβώς ένας κερδίζει — ο άλλος παίρνει controlled conflict
        self.assertCountEqual(results.values(), ['ok', 'conflict'], results)
        currents = ClientDocument.objects.filter(
            client=self.client_profile, document_category='vat', year=2026,
            month=3, obligation=self.ob1, is_current=True, slot='')
        self.assertEqual(currents.count(), 1)

    def test_concurrent_attach_and_upload_same_key(self):
        doc_a = self._mk_doc()             # standalone — θα γίνει attach
        barrier = threading.Barrier(2)
        errors = []

        def do_attach():
            try:
                barrier.wait(timeout=10)
                filing.attach_document_service(self.user, doc_a, self.ob1)
            except (filing.DocumentKeyConflict, Exception) as e:
                if not isinstance(e, filing.DocumentKeyConflict):
                    errors.append(e)
            finally:
                connections.close_all()

        def do_upload():
            try:
                barrier.wait(timeout=10)
                filing.create_client_document(
                    client=self.client_profile,
                    uploaded_file=SimpleUploadedFile('u.pdf', b'%PDF-1.4 y'),
                    category='vat', year=2026, month=3, obligation=self.ob1,
                    user=self.user, on_existing='version')
            except Exception as e:  # pragma: no cover
                errors.append(e)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=do_attach),
                   threading.Thread(target=do_upload)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        self.assertFalse(errors, f'Σφάλματα: {errors}')
        currents = ClientDocument.objects.filter(
            client=self.client_profile, document_category='vat', year=2026,
            month=3, obligation=self.ob1, is_current=True, slot='')
        # ΠΟΤΕ δύο current στο target key — ό,τι σειρά κι αν κέρδισε
        self.assertEqual(currents.count(), 1)
