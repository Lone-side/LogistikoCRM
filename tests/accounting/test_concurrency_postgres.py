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
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

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


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ConcurrentStructuralMutationTest(TransactionTestCase):
    """
    Γύρος 20: ταυτόχρονο structural mutation + delete/version στο ΙΔΙΟ
    document. Αποδεικνύει ότι το reload+lock του document μέσα στο
    transaction δεν αφήνει stale state:
    - κανένα deleted row δεν αναδημιουργείται
    - κανένα stale obligation assignment
    - κανένα duplicate current
    - μόνο controlled αποτελέσματα (success / conflict / not-found)
    - κανένα raw IntegrityError
    """

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
        self.user = User.objects.create_user('pg_sm_user', password='x')
        for codename in ('add_clientdocument', 'change_clientdocument',
                         'delete_clientdocument'):
            self.user.user_permissions.add(Permission.objects.get(
                codename=codename, content_type__app_label='accounting'))
        self.user = User.objects.get(pk=self.user.pk)
        ot = ObligationType.objects.create(
            name='ΦΠΑ-SM', code='FPA-SM', is_active=True)
        self.ob = MonthlyObligation.objects.create(
            client=self.client_profile, obligation_type=ot, month=3,
            year=2026, deadline=timezone.now().date())

    def _mk_doc(self, obligation=None):
        return filing.create_client_document(
            client=self.client_profile,
            uploaded_file=SimpleUploadedFile('sm.pdf', b'%PDF-1.4 x'),
            category='vat', year=2026, month=3, obligation=obligation,
            user=self.user)

    def _run_pair(self, fn_a, fn_b):
        barrier = threading.Barrier(2)
        results = {}

        def wrap(name, fn):
            def inner():
                try:
                    barrier.wait(timeout=10)
                    fn()
                    results[name] = 'ok'
                except filing.DocumentGone:
                    results[name] = 'gone'
                except filing.DocumentKeyConflict:
                    results[name] = 'conflict'
                except filing.MultipleCurrentDocumentsError:
                    results[name] = 'multiple'
                except ValidationError:
                    results[name] = 'invalid'
                except Exception as e:  # pragma: no cover - διαγνωστικό
                    results[name] = f'ERROR:{type(e).__name__}:{e}'
                finally:
                    connections.close_all()
            return inner

        threads = [threading.Thread(target=wrap('a', fn_a)),
                   threading.Thread(target=wrap('b', fn_b))]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        for name, value in results.items():
            self.assertFalse(
                str(value).startswith('ERROR:'),
                f'Ανεξέλεγκτο σφάλμα στο thread {name}: {value}')
        return results

    def _assert_consistent(self, doc_pk):
        """Καμία διπλή current, κανένα row χωρίς αρχείο, κανένα resurrect."""
        currents = ClientDocument.objects.filter(
            client=self.client_profile, document_category='vat',
            year=2026, month=3, is_current=True)
        by_key = {}
        for d in currents:
            key = (d.obligation_id, d.slot)
            by_key.setdefault(key, []).append(d.pk)
        for key, ids in by_key.items():
            self.assertEqual(len(ids), 1, f'Διπλό current στο key {key}: {ids}')
        for d in ClientDocument.objects.all():
            self.assertTrue(d.file and d.file.name,
                            'Committed row χωρίς αρχείο')

    def test_concurrent_attach_and_delete(self):
        doc = self._mk_doc()
        stale = ClientDocument.objects.get(pk=doc.pk)
        results = self._run_pair(
            lambda: filing.attach_document_service(self.user, stale, self.ob),
            lambda: filing.delete_document_service(self.user, doc),
        )
        self.assertTrue(set(results.values()) <= {'ok', 'gone', 'conflict'},
                        results)
        # Αν το delete κέρδισε, το attach ΔΕΝ αναδημιούργησε το row
        if results.get('b') == 'ok':
            self.assertFalse(
                ClientDocument.objects.filter(pk=doc.pk).exists())
        self._assert_consistent(doc.pk)

    def test_concurrent_detach_and_delete(self):
        doc = self._mk_doc(self.ob)
        stale = ClientDocument.objects.get(pk=doc.pk)
        results = self._run_pair(
            lambda: filing.detach_document_service(self.user, stale),
            lambda: filing.delete_document_service(self.user, doc),
        )
        self.assertTrue(set(results.values()) <= {'ok', 'gone', 'conflict'},
                        results)
        if results.get('b') == 'ok':
            self.assertFalse(
                ClientDocument.objects.filter(pk=doc.pk).exists())
        self._assert_consistent(doc.pk)

    def test_concurrent_attach_and_version(self):
        doc = self._mk_doc()
        stale = ClientDocument.objects.get(pk=doc.pk)
        results = self._run_pair(
            lambda: filing.attach_document_service(self.user, stale, self.ob),
            lambda: filing.create_client_document(
                client=self.client_profile,
                uploaded_file=SimpleUploadedFile('v2.pdf', b'%PDF-1.4 y'),
                category='vat', year=2026, month=3, user=self.user,
                on_existing='version'),
        )
        self.assertTrue(
            set(results.values()) <= {'ok', 'gone', 'conflict', 'invalid'},
            results)
        self._assert_consistent(doc.pk)

    def test_concurrent_detach_and_version(self):
        doc = self._mk_doc(self.ob)
        stale = ClientDocument.objects.get(pk=doc.pk)
        results = self._run_pair(
            lambda: filing.detach_document_service(self.user, stale),
            lambda: filing.create_client_document(
                client=self.client_profile,
                uploaded_file=SimpleUploadedFile('v2.pdf', b'%PDF-1.4 y'),
                category='vat', year=2026, month=3, obligation=self.ob,
                user=self.user, on_existing='version'),
        )
        self.assertTrue(
            set(results.values()) <= {'ok', 'gone', 'conflict', 'invalid'},
            results)
        self._assert_consistent(doc.pk)


# ===========================================================================
# Γύρος 22 — SharedLink: πραγματικά concurrency tests σε PostgreSQL
# ===========================================================================
@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class SharedLinkConcurrencyTest(TransactionTestCase):
    """
    Πραγματικά ταυτόχρονα threads/connections πάνω στο ίδιο SharedLink.

    Αποδεικνύει ότι ο conditional-UPDATE guard (`_revocation_guard_q`)
    σειριοποιεί τις μεταβολές quota και ότι μια ταυτόχρονη ανάκληση/
    λήξη/αλλαγή ασφαλείας ακυρώνει την ενέργεια χωρίς download, counter
    mutation ή success access log.
    """

    def setUp(self):
        if connection.vendor != 'postgresql':
            import os
            if os.environ.get('REQUIRE_POSTGRES_TESTS') == '1':
                self.fail(
                    'Το REQUIRE_POSTGRES_TESTS=1 απαιτεί PostgreSQL backend '
                    '— το concurrency test δεν έτρεξε πραγματικά.')
            self.skipTest('Απαιτεί PostgreSQL — τρέχει blocking στο CI.')
        from accounting.models import SharedLink
        self.client_profile = ClientProfile.objects.create(
            afm='123456783', eponimia='PG SHARE ΑΕ', eidos_ipoxreou='company')
        self.user = User.objects.create_user('pg_share_user', password='x')
        for codename in ('add_clientdocument', 'view_clientprofile'):
            self.user.user_permissions.add(Permission.objects.get(
                codename=codename, content_type__app_label='accounting'))
        self.user = User.objects.get(pk=self.user.pk)
        self.doc = filing.create_client_document(
            client=self.client_profile,
            uploaded_file=SimpleUploadedFile('share.pdf', b'%PDF-1.4 share'),
            category='vat', year=2026, month=3, user=self.user)
        self.link = SharedLink.objects.create(
            document=self.doc, access_level='download', allow_upload=True,
            max_downloads=1, max_uploads=1)

    def _fresh(self):
        from accounting.models import SharedLink
        return SharedLink.objects.get(pk=self.link.pk)

    def _run_pair(self, fn_a, fn_b):
        barrier = threading.Barrier(2)
        results = {}

        def wrap(name, fn):
            def runner():
                try:
                    barrier.wait(timeout=10)
                    results[name] = fn()
                except Exception as e:      # pragma: no cover - διαγνωστικό
                    results[name] = f'error:{type(e).__name__}'
                finally:
                    connections.close_all()
            return runner

        threads = [threading.Thread(target=wrap('a', fn_a)),
                   threading.Thread(target=wrap('b', fn_b))]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        return results

    def _counters(self):
        link = self._fresh()
        return link.download_count, link.upload_count

    def test_two_downloads_on_last_quota_slot(self):
        """Ακριβώς ένας κερδίζει το τελευταίο slot· counter δεν ξεπερνά το όριο."""
        link_a, link_b = self._fresh(), self._fresh()
        results = self._run_pair(link_a.try_record_download,
                                 link_b.try_record_download)
        self.assertCountEqual(list(results.values()), [True, False], results)
        downloads, _ = self._counters()
        self.assertEqual(downloads, 1)

    def test_download_concurrent_with_revoke(self):
        """Ταυτόχρονο revoke: είτε κερδίζει το download είτε ακυρώνεται."""
        from accounting.models import SharedLink
        link_a = self._fresh()

        def revoke():
            SharedLink.objects.filter(pk=self.link.pk).update(is_active=False)
            return 'revoked'

        results = self._run_pair(link_a.try_record_download, revoke)
        downloads, _ = self._counters()
        if results.get('a') is True:
            self.assertEqual(downloads, 1)
        else:
            # Ακυρώθηκε → ΚΑΝΕΝΑ slot δεν καταναλώθηκε
            self.assertEqual(downloads, 0)
        self.assertLessEqual(downloads, 1)

    def test_download_concurrent_with_expiry_change(self):
        from accounting.models import SharedLink
        link_a = self._fresh()

        def expire():
            SharedLink.objects.filter(pk=self.link.pk).update(
                expires_at=timezone.now() - timezone.timedelta(minutes=5))
            return 'expired'

        results = self._run_pair(link_a.try_record_download, expire)
        downloads, _ = self._counters()
        self.assertIn(results.get('a'), (True, False))
        self.assertEqual(downloads, 1 if results.get('a') else 0)

    def test_download_concurrent_with_security_change(self):
        """Αλλαγή password fingerprint ταυτόχρονα με το download."""
        from accounting.models import SharedLink
        link_a = self._fresh()

        def change_password():
            SharedLink.objects.filter(pk=self.link.pk).update(
                password_hash='pbkdf2_sha256$αλλαγμένο')
            return 'changed'

        results = self._run_pair(link_a.try_record_download, change_password)
        downloads, _ = self._counters()
        self.assertEqual(downloads, 1 if results.get('a') else 0)

    def test_storage_failure_compensation_does_not_steal_other_download(self):
        """
        Δύο ταυτόχρονα downloads σε link με 2 slots· το ένα αποτυγχάνει
        στο storage και κάνει compensation. Το ΕΠΙΤΥΧΗΜΕΝΟ download δεν
        πρέπει να χάσει το slot του και ο counter δεν γίνεται αρνητικός.
        """
        from accounting.models import SharedLink
        SharedLink.objects.filter(pk=self.link.pk).update(max_downloads=2)
        link_ok, link_fail = self._fresh(), self._fresh()

        def ok_download():
            return link_ok.try_record_download()

        def failing_download():
            reserved = link_fail.try_record_download()
            if reserved:
                link_fail.release_download()   # compensation
            return f'reserved={reserved}'

        self._run_pair(ok_download, failing_download)
        downloads, _ = self._counters()
        # Ένα επιτυχημένο download παραμένει μετρημένο, ποτέ αρνητικό
        self.assertEqual(downloads, 1)
        self.assertGreaterEqual(downloads, 0)

    def test_concurrent_release_cannot_drive_counter_negative(self):
        link_a, link_b = self._fresh(), self._fresh()
        self.assertTrue(self._fresh().try_record_download())
        self._run_pair(link_a.release_download, link_b.release_download)
        downloads, _ = self._counters()
        self.assertGreaterEqual(downloads, 0)
        self.assertEqual(downloads, 0)

    def test_two_upload_reservations_on_last_slot(self):
        link_a, link_b = self._fresh(), self._fresh()
        results = self._run_pair(lambda: link_a.try_reserve_uploads(1),
                                 lambda: link_b.try_reserve_uploads(1))
        self.assertCountEqual(list(results.values()), [True, False], results)
        _, uploads = self._counters()
        self.assertEqual(uploads, 1)

    def test_upload_concurrent_with_allow_upload_revoke(self):
        from accounting.models import SharedLink
        link_a = self._fresh()

        def revoke_upload():
            SharedLink.objects.filter(pk=self.link.pk).update(
                allow_upload=False)
            return 'revoked'

        results = self._run_pair(lambda: link_a.try_reserve_uploads(1),
                                 revoke_upload)
        _, uploads = self._counters()
        self.assertEqual(uploads, 1 if results.get('a') else 0)

    def test_no_extra_access_logs_on_rejected_download(self):
        """Απορριφθέν download → ΚΑΝΕΝΑ access log, κανένας counter."""
        from accounting.models import SharedLink, SharedLinkAccess
        link_a = self._fresh()
        SharedLink.objects.filter(pk=self.link.pk).update(is_active=False)
        self.assertFalse(link_a.try_record_download())
        self.assertEqual(
            SharedLinkAccess.objects.filter(shared_link=self.link).count(), 0)
        downloads, _ = self._counters()
        self.assertEqual(downloads, 0)


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class UnlimitedSharedLinkConcurrencyTest(TransactionTestCase):
    """
    Γύρος 23 — links ΧΩΡΙΣ `max_downloads` (unlimited).

    Πριν, αυτά περνούσαν από μη-atomic `record_access()`: μια ταυτόχρονη
    ανάκληση/λήξη/αλλαγή ασφαλείας δεν εμπόδιζε την επιστροφή αρχείου ή
    access token. Τώρα χρησιμοποιούν τον ίδιο `_revocation_guard_q()`
    μέσω `try_record_access()`.
    """

    def setUp(self):
        if connection.vendor != 'postgresql':
            import os
            if os.environ.get('REQUIRE_POSTGRES_TESTS') == '1':
                self.fail(
                    'Το REQUIRE_POSTGRES_TESTS=1 απαιτεί PostgreSQL backend '
                    '— το concurrency test δεν έτρεξε πραγματικά.')
            self.skipTest('Απαιτεί PostgreSQL — τρέχει blocking στο CI.')
        from accounting.models import SharedLink
        self.client_profile = ClientProfile.objects.create(
            afm='123456783', eponimia='PG UNLIM ΑΕ', eidos_ipoxreou='company')
        self.user = User.objects.create_user('pg_unlim_user', password='x')
        for codename in ('add_clientdocument', 'view_clientprofile'):
            self.user.user_permissions.add(Permission.objects.get(
                codename=codename, content_type__app_label='accounting'))
        self.user = User.objects.get(pk=self.user.pk)
        self.doc = filing.create_client_document(
            client=self.client_profile,
            uploaded_file=SimpleUploadedFile('u.pdf', b'%PDF-1.4 unlimited'),
            category='vat', year=2026, month=3, user=self.user)
        # ΧΩΡΙΣ όριο λήψεων
        self.link = SharedLink.objects.create(
            document=self.doc, access_level='download', max_downloads=None)

    def _fresh(self):
        from accounting.models import SharedLink
        return SharedLink.objects.get(pk=self.link.pk)

    def _state(self):
        from accounting.models import SharedLinkAccess
        link = self._fresh()
        return (link.view_count, link.download_count,
                SharedLinkAccess.objects.filter(shared_link=link).count())

    def _run_pair(self, fn_a, fn_b):
        barrier = threading.Barrier(2)
        results = {}

        def wrap(name, fn):
            def runner():
                try:
                    barrier.wait(timeout=10)
                    results[name] = fn()
                except Exception as e:      # pragma: no cover - διαγνωστικό
                    results[name] = f'error:{type(e).__name__}'
                finally:
                    connections.close_all()
            return runner

        threads = [threading.Thread(target=wrap('a', fn_a)),
                   threading.Thread(target=wrap('b', fn_b))]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        return results

    def test_unlimited_access_concurrent_with_revoke(self):
        from accounting.models import SharedLink
        link_a = self._fresh()

        def revoke():
            SharedLink.objects.filter(pk=self.link.pk).update(is_active=False)
            return 'revoked'

        results = self._run_pair(link_a.try_record_access, revoke)
        views, downloads, _logs = self._state()
        # Είτε πέρασε πριν την ανάκληση, είτε ακυρώθηκε πλήρως
        self.assertEqual(views, 1 if results.get('a') else 0)
        self.assertEqual(downloads, 0)

    def test_unlimited_access_concurrent_with_expiry(self):
        from accounting.models import SharedLink
        link_a = self._fresh()

        def expire():
            SharedLink.objects.filter(pk=self.link.pk).update(
                expires_at=timezone.now() - timezone.timedelta(minutes=5))
            return 'expired'

        results = self._run_pair(link_a.try_record_access, expire)
        views, _d, _l = self._state()
        self.assertEqual(views, 1 if results.get('a') else 0)

    def test_unlimited_access_concurrent_with_security_change(self):
        from accounting.models import SharedLink
        link_a = self._fresh()

        def change_security():
            SharedLink.objects.filter(pk=self.link.pk).update(
                password_hash='pbkdf2_sha256$αλλαγμένο', requires_email=True)
            return 'changed'

        results = self._run_pair(link_a.try_record_access, change_security)
        views, _d, _l = self._state()
        self.assertEqual(views, 1 if results.get('a') else 0)

    def test_unlimited_access_concurrent_with_token_regeneration(self):
        from accounting.models import SharedLink, generate_share_token
        link_a = self._fresh()

        def regenerate():
            SharedLink.objects.filter(pk=self.link.pk).update(
                token=generate_share_token())
            return 'regenerated'

        results = self._run_pair(link_a.try_record_access, regenerate)
        views, _d, _l = self._state()
        self.assertEqual(views, 1 if results.get('a') else 0)

    def test_no_bytes_or_token_after_revocation(self):
        """
        Μετά την ανάκληση, ούτε το public content endpoint ούτε το
        preview επιστρέφουν δεδομένα ή token — και δεν γράφεται log.
        """
        from accounting.models import SharedLink
        from tests.accounting.secure_client import SecureAPIClient
        SharedLink.objects.filter(pk=self.link.pk).update(is_active=False)
        web = SecureAPIClient()

        content = web.get(f'/accounting/share/{self.link.token}/')
        self.assertEqual(content.status_code, 410)
        self.assertNotIn('access_token', getattr(content, 'data', {}) or {})

        preview = web.get(f'/accounting/share/{self.link.token}/preview/')
        self.assertEqual(preview.status_code, 410)

        views, downloads, logs = self._state()
        self.assertEqual((views, downloads, logs), (0, 0, 0))

    def test_two_concurrent_unlimited_accesses_both_counted(self):
        """Unlimited: δύο ταυτόχρονες προσβάσεις μετρώνται και οι δύο."""
        link_a, link_b = self._fresh(), self._fresh()
        results = self._run_pair(link_a.try_record_access,
                                 link_b.try_record_access)
        self.assertEqual(list(results.values()), [True, True], results)
        views, downloads, _l = self._state()
        self.assertEqual(views, 2)
        self.assertEqual(downloads, 0)
