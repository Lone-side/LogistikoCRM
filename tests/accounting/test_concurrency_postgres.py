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


@override_settings(MEDIA_ROOT=TEMP_MEDIA, ENFORCE_CLIENT_ASSIGNMENT=True)
class AdminDeleteTOCTOUTest(TransactionTestCase):
    """TOCTOU στα single-object admin delete paths (Γύρος Ε).

    Ένα thread κρατά select_for_update lock και αλλάζει τη σχέση/πελάτη
    ΠΡΙΝ ολοκληρωθεί η διαγραφή· η διαγραφή πρέπει να κάνει authorization
    ΠΑΝΩ στο locked (τρέχον) state, όχι στο stale obj/call_id.
    """

    def setUp(self):
        if connection.vendor != 'postgresql':
            import os
            if os.environ.get('REQUIRE_POSTGRES_TESTS') == '1':
                self.fail(
                    'REQUIRE_POSTGRES_TESTS=1 απαιτεί PostgreSQL — το TOCTOU '
                    'test δεν έτρεξε πραγματικά.')
            self.skipTest('Απαιτεί PostgreSQL (blocking στο CI test job).')
        from accounting.models import Ticket, VoIPCall
        from django.contrib.auth.models import Permission
        self.Ticket, self.VoIPCall = Ticket, VoIPCall
        self.mine = ClientProfile.objects.create(
            afm='094014201', eponimia='OWNER')
        self.theirs = ClientProfile.objects.create(
            afm='998877665', eponimia='FOREIGN')
        u = User.objects.create_user('toctou', password='x', is_staff=True)
        for cn in ('view_ticket', 'delete_ticket', 'view_voipcall',
                   'delete_voipcall', 'change_voipcall', 'change_ticket'):
            u.user_permissions.add(Permission.objects.get(
                codename=cn, content_type__app_label='accounting'))
        self.mine.assigned_users.add(u)
        self.user_pk = u.pk

    def _client(self):
        from django.test import Client
        c = Client()
        c.force_login(User.objects.get(pk=self.user_pk))
        return c

    def _call(self, cid, client_profile):
        return self.VoIPCall.objects.create(
            call_id=cid, phone_number='2101234567', direction='incoming',
            status='missed', started_at=timezone.now(), client=client_profile)

    def _deletion_count(self, model, pk):
        from django.contrib.admin.models import DELETION, LogEntry
        from django.contrib.contenttypes.models import ContentType
        return LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(model),
            object_id=str(pk), action_flag=DELETION).count()

    def _delete_url(self, ticket_pk):
        from django.urls import reverse
        return reverse('admin:accounting_ticket_delete', args=[ticket_pk])

    def _run_with_attacker(self, ticket_pk, mutate, *, lock='ticket',
                           save_ticket=True):
        """attacker: lock (ticket ή call), wait barrier, mutate, commit.
        main: μετά το barrier κάνε delete_call POST (μπλοκάρει στο lock).

        lock='ticket': ο attacker μεταλλάσσει το ΙΔΙΟ το ticket (repoint/
        detach) κρατώντας το ticket lock — δεν αγγίζει call row, οπότε
        δεν διασταυρώνεται με την ενιαία σειρά call→ticket.

        lock='call': ο attacker μεταλλάσσει την ΚΛΗΣΗ, οπότε κρατά το
        call lock ΠΡΩΤΑ — όπως ο πραγματικός mutator (change_call_client).
        Η παλιά εκδοχή κρατούσε το ticket lock και έγραφε την κλήση
        (ticket→call), δηλαδή την αντεστραμμένη σειρά που ο κώδικας
        πλέον ΔΕΝ χρησιμοποιεί πουθενά — με την ενιαία σειρά του admin
        (call→ticket) αυτό κατέληγε σε τεχνητό AB/BA deadlock που κανένα
        πραγματικό path δεν μπορεί πια να προκαλέσει. Το TOCTOU ζητούμενο
        (auth στο locked state, όχι στο stale obj) εξασκείται ίδια: το
        get_object διαβάζει stale, το mutate γίνεται πριν αποκτηθούν τα
        locks του delete, ο έλεγχος βλέπει το τρέχον state.
        """
        from django.db import transaction
        barrier = threading.Barrier(2)
        errors = []

        import time

        def attacker():
            try:
                with transaction.atomic():
                    if lock == 'ticket':
                        locked = (self.Ticket.objects.select_for_update()
                                  .get(pk=ticket_pk))
                    else:
                        ticket_row = self.Ticket.objects.get(pk=ticket_pk)
                        locked = (self.VoIPCall.objects.select_for_update()
                                  .get(pk=ticket_row.call_id))
                    barrier.wait()
                    # Κράτα το lock ώστε το admin request να προλάβει να
                    # κάνει get_object (stale read) και ΜΕΤΑ να μπλοκάρει
                    # στο select_for_update· μόνο τότε εφάρμοσε το mutate.
                    # Έτσι εξασκείται ντετερμινιστικά το stale-vs-locked
                    # path (όχι απλώς attacker-commits-first).
                    time.sleep(0.8)
                    mutate(locked)
                    if save_ticket and lock == 'ticket':
                        locked.save()
            except Exception as e:  # noqa: BLE001
                errors.append(e)
            finally:
                connections.close_all()

        t = threading.Thread(target=attacker)
        t.start()
        barrier.wait()
        resp = self._client().post(
            self._delete_url(ticket_pk),
            {'delete_call': '1', 'post': 'yes'}, secure=True)
        t.join()
        self.assertEqual(errors, [])
        return resp

    def test_A_ticket_repointed_to_foreign_call_fails_closed(self):
        call_mine = self._call('A-MINE', self.mine)
        call_foreign = self._call('A-FOR', self.theirs)
        ticket = self.Ticket.objects.create(
            client=self.mine, call=call_mine, title='t',
            description='-', status='open')

        def repoint(locked):
            locked.call = call_foreign

        resp = self._run_with_attacker(ticket.pk, repoint)

        # Το locked ticket δείχνει πλέον σε foreign call → 403
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(self.Ticket.objects.filter(pk=ticket.pk).exists())
        self.assertTrue(self.VoIPCall.objects.filter(pk=call_mine.pk).exists())
        self.assertTrue(
            self.VoIPCall.objects.filter(pk=call_foreign.pk).exists())
        self.assertEqual(self._deletion_count(self.Ticket, ticket.pk), 0)
        self.assertEqual(
            self._deletion_count(self.VoIPCall, call_foreign.pk), 0)
        self.assertEqual(self._deletion_count(self.VoIPCall, call_mine.pk), 0)

    def test_B_call_client_changed_to_foreign_fails_closed(self):
        call_mine = self._call('B-MINE', self.mine)
        ticket = self.Ticket.objects.create(
            client=self.mine, call=call_mine, title='t',
            description='-', status='open')

        def steal_call_client(locked_call):
            # αλλάζει τον πελάτη της κλήσης σε foreign — πάνω στο locked
            # call row, όπως ο πραγματικός mutator (change_call_client)
            self.VoIPCall.objects.filter(pk=locked_call.pk).update(
                client=self.theirs)

        resp = self._run_with_attacker(
            ticket.pk, steal_call_client, lock='call')

        # authorization πάνω στο locked (foreign πλέον) call → 403
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(self.Ticket.objects.filter(pk=ticket.pk).exists())
        self.assertTrue(self.VoIPCall.objects.filter(pk=call_mine.pk).exists())
        self.assertEqual(self._deletion_count(self.Ticket, ticket.pk), 0)
        self.assertEqual(self._deletion_count(self.VoIPCall, call_mine.pk), 0)

    def test_C_relationship_removed_does_not_delete_stale_call(self):
        call_mine = self._call('C-MINE', self.mine)
        ticket = self.Ticket.objects.create(
            client=self.mine, call=call_mine, title='t',
            description='-', status='open')

        def detach(locked):
            locked.call = None

        resp = self._run_with_attacker(ticket.pk, detach)

        # Η σχέση αφαιρέθηκε → διαγράφεται ΜΟΝΟ το ticket, ΟΧΙ το stale call
        self.assertIn(resp.status_code, (200, 302))
        self.assertFalse(self.Ticket.objects.filter(pk=ticket.pk).exists())
        self.assertTrue(self.VoIPCall.objects.filter(pk=call_mine.pk).exists())
        self.assertEqual(self._deletion_count(self.Ticket, ticket.pk), 1)
        self.assertEqual(self._deletion_count(self.VoIPCall, call_mine.pk), 0)


class VoIPCallLogSnapshotRaceTest(TransactionTestCase):
    """
    Race «δημιουργία VoIPCallLog ταυτόχρονα με αλλαγή πελάτη» (εύρημα
    ανεξάρτητου review): ένα log που ξεκίνησε με stale VoIPCall instance
    ΔΕΝ επιτρέπεται να εισαχθεί μετά το commit του change_call_client με
    παλιό client snapshot — θα άφηνε μόνιμο client-mismatch που κανένα
    resync δεν ξαναπιάνει.

    Deterministic: ο changer κρατά FOR UPDATE στην κλήση όσο ο creator
    επιχειρεί το create. Το VoIPCallLog.save() διαβάζει τα snapshots από
    τη βάση με FOR UPDATE στη γραμμή της κλήσης, οπότε μπλοκάρει μέχρι
    το commit και γράφει τον ΝΕΟ πελάτη. (Πριν το fix: αντέγραφε από το
    in-memory stale instance → client=None → το test αποτυγχάνει.)
    """

    def setUp(self):
        if connection.vendor != 'postgresql':
            import os
            if os.environ.get('REQUIRE_POSTGRES_TESTS') == '1':
                self.fail(
                    'Το REQUIRE_POSTGRES_TESTS=1 απαιτεί PostgreSQL backend '
                    '— το concurrency test δεν έτρεξε πραγματικά.')
            self.skipTest('Απαιτεί PostgreSQL (REQUIRE_POSTGRES_TESTS=1).')
        from accounting.models import VoIPCall
        self.owner = ClientProfile.objects.create(
            afm='094014201', eponimia='RACE ΑΕ')
        self.call = VoIPCall.objects.create(
            call_id='RACE-1', phone_number='2101234567',
            direction='incoming', status='missed',
            started_at=timezone.now(), client=None)

    def test_log_from_stale_call_instance_gets_fresh_snapshot(self):
        import time
        from django.db import transaction
        from accounting.models import VoIPCall, VoIPCallLog
        from accounting.services.call_assignment import change_call_client

        barrier = threading.Barrier(2, timeout=15)
        errors = {}
        created = {}

        def changer():
            try:
                with transaction.atomic():
                    VoIPCall.objects.select_for_update().get(pk=self.call.pk)
                    barrier.wait()
                    # Ο creator τώρα μπλοκάρει στο FOR UPDATE του save()
                    time.sleep(0.8)
                    fresh = VoIPCall.objects.get(pk=self.call.pk)
                    change_call_client(fresh, self.owner)
            except Exception as exc:  # pragma: no cover
                errors['changer'] = f'{type(exc).__name__}: {exc}'
            finally:
                connections.close_all()

        def creator():
            try:
                # Stale instance: φορτωμένο ΠΡΙΝ την αλλαγή (client=None)
                stale = VoIPCall.objects.get(pk=self.call.pk)
                assert stale.client_id is None
                barrier.wait()
                log = VoIPCallLog.objects.create(call=stale, action='started')
                created['pk'] = log.pk
            except Exception as exc:  # pragma: no cover
                errors['creator'] = f'{type(exc).__name__}: {exc}'
            finally:
                connections.close_all()

        threads = [threading.Thread(target=changer),
                   threading.Thread(target=creator)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(20)

        self.assertFalse(errors, f'threads απέτυχαν: {errors}')
        from accounting.models import VoIPCallLog
        log = VoIPCallLog.objects.get(pk=created['pk'])
        self.assertEqual(
            log.client_id, self.owner.pk,
            'log από stale instance εισήχθη με παλιό client snapshot — '
            'μόνιμο client-mismatch')

        # Και το audit gate συμφωνεί
        from django.core.management import call_command
        call_command('audit_voipcalllog_snapshots', '--fail-on-findings')


class CallTicketLockOrderTest(TransactionTestCase):
    """
    Deadlock fix: ταυτόχρονη διαγραφή του ίδιου Call–Ticket ζεύγους από
    VoIPCallAdmin (κλειδώνει call → ticket) και TicketAdmin.

    Με την παλιά σειρά του TicketAdmin (ticket → call) το ΑΒ/ΒΑ
    αναπαρήχθη σε PostgreSQL 14 ως «deadlock detected». Πλέον ΚΑΙ τα
    ticket paths κλειδώνουν call → ticket (_lock_calls_then_tickets),
    οπότε το σενάριο σειριοποιείται.

    Deterministic: T1 μιμείται το call-side mid-flight (κρατά το call
    lock, μετά θέλει το ticket), ενώ T2 τρέχει το ΠΡΑΓΜΑΤΙΚΟ
    TicketAdmin.delete_queryset. Με τη νέα σειρά ο T2 μπλοκάρει στο
    call lock και ολοκληρώνει μετά τον T1. Με την παλιά, ο T2 έπαιρνε
    πρώτος το ticket lock και το ζεύγος κατέληγε σε deadlock.
    """

    def setUp(self):
        if connection.vendor != 'postgresql':
            import os
            if os.environ.get('REQUIRE_POSTGRES_TESTS') == '1':
                self.fail(
                    'Το REQUIRE_POSTGRES_TESTS=1 απαιτεί PostgreSQL backend '
                    '— το concurrency test δεν έτρεξε πραγματικά.')
            self.skipTest('Απαιτεί PostgreSQL (REQUIRE_POSTGRES_TESTS=1).')
        from accounting.models import Ticket, VoIPCall
        self.owner = ClientProfile.objects.create(
            afm='094014201', eponimia='LOCK ΑΕ')
        self.call = VoIPCall.objects.create(
            call_id='LOCK-1', phone_number='2101234567',
            direction='incoming', status='missed',
            started_at=timezone.now(), client=self.owner)
        self.ticket = Ticket.objects.create(
            client=self.owner, call=self.call, title='τ', description='-',
            status='open')
        self.superuser = User.objects.create_superuser(
            'lock_admin', 'l@test.com', 'x')

    def test_concurrent_pair_deletion_does_not_deadlock(self):
        import time
        from django.contrib.admin.sites import site
        from django.db import transaction
        from django.test import RequestFactory
        from accounting.models import Ticket, VoIPCall

        admin_instance = site._registry[Ticket]
        request = RequestFactory().post('/')
        request.user = self.superuser

        barrier = threading.Barrier(2, timeout=15)
        errors = {}

        def call_side_mid_flight():
            # Ό,τι κάνει το VoIPCallAdmin: κρατά call lock, μετά ticket
            try:
                with transaction.atomic():
                    VoIPCall.objects.select_for_update().get(pk=self.call.pk)
                    barrier.wait()
                    time.sleep(0.5)
                    Ticket.objects.select_for_update().filter(
                        call_id=self.call.pk).first()
            except Exception as exc:  # pragma: no cover
                errors['call_side'] = f'{type(exc).__name__}: {exc}'
            finally:
                connections.close_all()

        def ticket_side_real_admin():
            try:
                barrier.wait()
                admin_instance.delete_queryset(
                    request, Ticket.objects.filter(pk=self.ticket.pk))
            except Exception as exc:  # pragma: no cover
                errors['ticket_side'] = f'{type(exc).__name__}: {exc}'
            finally:
                connections.close_all()

        threads = [threading.Thread(target=call_side_mid_flight),
                   threading.Thread(target=ticket_side_real_admin)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(20)

        self.assertFalse(
            errors,
            f'deadlock ή αποτυχία στο ταυτόχρονο Call–Ticket ζεύγος: '
            f'{errors}')
        self.assertFalse(
            Ticket.objects.filter(pk=self.ticket.pk).exists(),
            'το ticket δεν διαγράφηκε')
        self.assertTrue(
            VoIPCall.objects.filter(pk=self.call.pk).exists(),
            'η κλήση δεν έπρεπε να διαγραφεί από αυτό το path')


class CallDeleteTOCTOUTest(TransactionTestCase):
    """
    NIGHT SHIFT test 15 — TOCTOU στη διαγραφή κλήσης: η σχέση
    call-ticket αλλάζει ΜΕΤΑΞΥ του lookup του view και της μετάλλαξης.

    Ο χρήστης έχει delete_voipcall αλλά ΟΧΙ change_ticket. Στο lookup η
    κλήση δεν έχει ticket· όσο ο attacker κρατά το call lock, συνδέει
    ticket. Το delete_call() επανελέγχει στο LOCKED state (όχι στο stale
    instance) → fail closed με PermissionDenied, η κλήση και το ticket
    επιβιώνουν. Χωρίς revalidation, η διαγραφή θα άφηνε το νέο ticket
    με call=None χωρίς change_ticket δικαίωμα.
    """

    def setUp(self):
        if connection.vendor != 'postgresql':
            import os
            if os.environ.get('REQUIRE_POSTGRES_TESTS') == '1':
                self.fail(
                    'Το REQUIRE_POSTGRES_TESTS=1 απαιτεί PostgreSQL backend '
                    '— το concurrency test δεν έτρεξε πραγματικά.')
            self.skipTest('Απαιτεί PostgreSQL (REQUIRE_POSTGRES_TESTS=1).')
        from accounting.models import VoIPCall
        self.owner = ClientProfile.objects.create(
            afm='094014201', eponimia='TOCTOU DEL ΑΕ')
        self.call = VoIPCall.objects.create(
            call_id='TDEL-1', phone_number='2101234567',
            direction='incoming', status='missed',
            started_at=timezone.now(), client=self.owner)
        user = User.objects.create_user('tdel_user', password='x',
                                        is_staff=True)
        for codename in ('view_voipcall', 'delete_voipcall'):
            user.user_permissions.add(Permission.objects.get(
                codename=codename, content_type__app_label='accounting'))
        self.user = User.objects.get(pk=user.pk)

    def test_relation_change_between_lookup_and_delete_fails_closed(self):
        import time
        from django.core.exceptions import PermissionDenied
        from django.db import transaction
        from accounting.models import Ticket, VoIPCall
        from accounting.services.call_assignment import delete_call

        barrier = threading.Barrier(2, timeout=15)
        errors = {}
        outcome = {}

        def attacker():
            try:
                with transaction.atomic():
                    VoIPCall.objects.select_for_update().get(pk=self.call.pk)
                    barrier.wait()
                    time.sleep(0.8)  # ο deleter μπλοκάρει στο call lock
                    Ticket.objects.create(
                        client=self.owner, call_id=self.call.pk,
                        title='linked mid-flight', description='-',
                        status='open')
            except Exception as exc:  # pragma: no cover
                errors['attacker'] = f'{type(exc).__name__}: {exc}'
            finally:
                connections.close_all()

        def deleter():
            try:
                # Lookup ΠΡΙΝ τη σύνδεση: χωρίς ticket
                stale = VoIPCall.objects.get(pk=self.call.pk)
                assert not Ticket.objects.filter(call=stale).exists()
                barrier.wait()
                try:
                    delete_call(stale, user=self.user)
                    outcome['result'] = 'deleted'
                except PermissionDenied:
                    outcome['result'] = 'denied'
            except Exception as exc:  # pragma: no cover
                errors['deleter'] = f'{type(exc).__name__}: {exc}'
            finally:
                connections.close_all()

        threads = [threading.Thread(target=attacker),
                   threading.Thread(target=deleter)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(20)

        self.assertFalse(errors, f'threads απέτυχαν: {errors}')
        self.assertEqual(
            outcome.get('result'), 'denied',
            'η διαγραφή ΔΕΝ έκανε fail closed μετά την αλλαγή της σχέσης')
        from accounting.models import Ticket, VoIPCall
        self.assertTrue(VoIPCall.objects.filter(pk=self.call.pk).exists())
        ticket = Ticket.objects.get(call_id=self.call.pk)
        self.assertEqual(ticket.call_id, self.call.pk)


class ConcurrentCreateTicketTest(TransactionTestCase):
    """
    NIGHT SHIFT test 16 — ταυτόχρονο διπλό create-ticket στην ίδια
    κλήση: το create_ticket_for_call() κλειδώνει την κλήση και
    επανελέγχει την ύπαρξη ticket, οπότε ο δεύτερος παίρνει καθαρό
    ValidationError — ποτέ δύο tickets, ποτέ 500/μερικά flags.
    """

    def setUp(self):
        if connection.vendor != 'postgresql':
            import os
            if os.environ.get('REQUIRE_POSTGRES_TESTS') == '1':
                self.fail(
                    'Το REQUIRE_POSTGRES_TESTS=1 απαιτεί PostgreSQL backend '
                    '— το concurrency test δεν έτρεξε πραγματικά.')
            self.skipTest('Απαιτεί PostgreSQL (REQUIRE_POSTGRES_TESTS=1).')
        from accounting.models import VoIPCall
        self.owner = ClientProfile.objects.create(
            afm='094014201', eponimia='DOUBLE CT ΑΕ')
        self.call = VoIPCall.objects.create(
            call_id='DCT-1', phone_number='2101234567',
            direction='incoming', status='missed',
            started_at=timezone.now(), client=self.owner)

    def test_concurrent_double_create_ticket_yields_exactly_one(self):
        from accounting.models import Ticket, VoIPCall
        from accounting.services.call_assignment import create_ticket_for_call

        barrier = threading.Barrier(2, timeout=15)
        results = {}

        def worker(name):
            try:
                call = VoIPCall.objects.get(pk=self.call.pk)
                barrier.wait()
                try:
                    ticket = create_ticket_for_call(call)
                    results[name] = ('created', ticket.pk)
                except ValidationError:
                    results[name] = ('rejected', None)
            except Exception as exc:
                results[name] = ('error', f'{type(exc).__name__}: {exc}')
            finally:
                connections.close_all()

        threads = [threading.Thread(target=worker, args=(n,))
                   for n in ('t1', 't2')]
        for t in threads:
            t.start()
        for t in threads:
            t.join(20)

        outcomes = sorted(v[0] for v in results.values())
        self.assertEqual(outcomes, ['created', 'rejected'],
                         f'μη αναμενόμενα αποτελέσματα: {results}')
        tickets = Ticket.objects.filter(call_id=self.call.pk)
        self.assertEqual(tickets.count(), 1)
        call = VoIPCall.objects.get(pk=self.call.pk)
        self.assertTrue(call.ticket_created)
        self.assertEqual(call.ticket_id, str(tickets.first().pk))


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class StaleAccessRevalidationTest(TransactionTestCase):
    """
    Blocker «stale object authorization μετά το lock»: το view κάνει
    client scoping ΠΡΙΝ το lock, οπότε αν το primary object αλλάξει
    πελάτη (A→B) μεταξύ lookup και lock, scoped χρήστης του Α θα
    μετέβαλλε πόρο του Β. Τα services επανελέγχουν πλέον την πρόσβαση
    ΠΑΝΩ στο locked state (_require_locked_access) — fail closed χωρίς
    καμία μετάλλαξη.

    Deterministic: ο attacker κρατά FOR UPDATE στο row, ο victim καλεί
    το service με stale instance και μπλοκάρει στο lock· μετά το commit
    του attacker (client=Β) το revalidation αρνείται.
    """

    def setUp(self):
        if connection.vendor != 'postgresql':
            import os
            if os.environ.get('REQUIRE_POSTGRES_TESTS') == '1':
                self.fail(
                    'Το REQUIRE_POSTGRES_TESTS=1 απαιτεί PostgreSQL backend '
                    '— το concurrency test δεν έτρεξε πραγματικά.')
            self.skipTest('Απαιτεί PostgreSQL (REQUIRE_POSTGRES_TESTS=1).')
        self.a = ClientProfile.objects.create(
            afm='094014201', eponimia='STALE Α')
        self.b = ClientProfile.objects.create(
            afm='998877665', eponimia='STALE Β')
        user = User.objects.create_user('stale_user', password='x',
                                        is_staff=True)
        for codename in ('view_voipcall', 'change_voipcall',
                         'delete_voipcall', 'view_ticket', 'change_ticket',
                         'delete_ticket', 'add_ticket'):
            user.user_permissions.add(Permission.objects.get(
                codename=codename, content_type__app_label='accounting'))
        self.user = User.objects.get(pk=user.pk)
        self.a.assigned_users.add(self.user)

    def _make_call(self, client, cid='STALE-C1'):
        from accounting.models import VoIPCall
        return VoIPCall.objects.create(
            call_id=cid, phone_number='2101234567',
            direction='incoming', status='missed',
            started_at=timezone.now(), client=client)

    def _race(self, model, pk, mutate, victim_action):
        """attacker: lock row → barrier → sleep → mutate → commit·
        victim: barrier → victim_action(). Επιστρέφει (outcome, errors)."""
        import time
        from django.core.exceptions import PermissionDenied
        from django.db import transaction

        barrier = threading.Barrier(2, timeout=15)
        errors = {}
        outcome = {}

        def attacker():
            try:
                with transaction.atomic():
                    model.objects.select_for_update().get(pk=pk)
                    barrier.wait()
                    time.sleep(0.8)
                    mutate()
            except Exception as exc:  # pragma: no cover
                errors['attacker'] = f'{type(exc).__name__}: {exc}'
            finally:
                connections.close_all()

        def victim():
            try:
                barrier.wait()
                try:
                    victim_action()
                    outcome['result'] = 'mutated'
                except PermissionDenied:
                    outcome['result'] = 'denied'
            except Exception as exc:  # pragma: no cover
                errors['victim'] = f'{type(exc).__name__}: {exc}'
            finally:
                connections.close_all()

        threads = [threading.Thread(target=attacker),
                   threading.Thread(target=victim)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(20)
        return outcome, errors

    def test_1_delete_call_stale_reassigned_denied(self):
        from accounting.models import VoIPCall
        from accounting.services.call_assignment import delete_call

        call = self._make_call(self.a)
        stale = VoIPCall.objects.get(pk=call.pk)

        outcome, errors = self._race(
            VoIPCall, call.pk,
            lambda: VoIPCall.objects.filter(pk=call.pk).update(
                client=self.b),
            lambda: delete_call(stale, user=self.user))
        self.assertFalse(errors, errors)
        self.assertEqual(outcome.get('result'), 'denied',
                         'scoped χρήστης διέγραψε ξένη (πλέον) κλήση')
        self.assertTrue(VoIPCall.objects.filter(pk=call.pk,
                                                client=self.b).exists())

    def test_2_create_ticket_stale_reassigned_denied(self):
        from accounting.models import Ticket, VoIPCall, VoIPCallLog
        from accounting.services.call_assignment import create_ticket_for_call

        call = self._make_call(self.a, 'STALE-C2')
        stale = VoIPCall.objects.get(pk=call.pk)

        outcome, errors = self._race(
            VoIPCall, call.pk,
            lambda: VoIPCall.objects.filter(pk=call.pk).update(
                client=self.b),
            lambda: create_ticket_for_call(stale, user=self.user))
        self.assertFalse(errors, errors)
        self.assertEqual(outcome.get('result'), 'denied')
        self.assertFalse(Ticket.objects.filter(call_id=call.pk).exists())
        self.assertFalse(VoIPCallLog.objects.filter(
            call_id=call.pk, action='ticket_created').exists())
        fresh = VoIPCall.objects.get(pk=call.pk)
        self.assertFalse(fresh.ticket_created)

    def test_3_change_call_client_stale_reassigned_denied(self):
        from accounting.models import VoIPCall
        from accounting.services.call_assignment import change_call_client

        call = self._make_call(self.a, 'STALE-C3')
        stale = VoIPCall.objects.get(pk=call.pk)

        outcome, errors = self._race(
            VoIPCall, call.pk,
            lambda: VoIPCall.objects.filter(pk=call.pk).update(
                client=self.b),
            lambda: change_call_client(stale, self.a, user=self.user))
        self.assertFalse(errors, errors)
        self.assertEqual(outcome.get('result'), 'denied',
                         'scoped χρήστης ξανάγραψε τον πελάτη ξένης κλήσης')
        self.assertTrue(VoIPCall.objects.filter(pk=call.pk,
                                                client=self.b).exists())

    def test_4_delete_ticket_stale_reassigned_denied(self):
        from accounting.models import Ticket
        from accounting.services.call_assignment import delete_ticket

        ticket = Ticket.objects.create(
            client=self.a, title='stale τ', description='-', status='open')
        stale = Ticket.objects.get(pk=ticket.pk)

        outcome, errors = self._race(
            Ticket, ticket.pk,
            lambda: Ticket.objects.filter(pk=ticket.pk).update(
                client=self.b),
            lambda: delete_ticket(stale, user=self.user))
        self.assertFalse(errors, errors)
        self.assertEqual(outcome.get('result'), 'denied')
        self.assertTrue(Ticket.objects.filter(pk=ticket.pk,
                                              client=self.b).exists())

    def test_5_sync_ticket_call_client_stale_denied(self):
        from accounting.models import Ticket, VoIPCall
        from accounting.services.call_assignment import (
            sync_ticket_call_client,
        )

        call = self._make_call(None, 'STALE-C5')
        ticket = Ticket.objects.create(
            client=self.a, call=call, title='stale sync', description='-',
            status='open')
        stale = Ticket.objects.get(pk=ticket.pk)

        outcome, errors = self._race(
            Ticket, ticket.pk,
            lambda: Ticket.objects.filter(pk=ticket.pk).update(
                client=self.b),
            lambda: sync_ticket_call_client(stale, user=self.user))
        self.assertFalse(errors, errors)
        self.assertEqual(outcome.get('result'), 'denied')
        # Πλήρες rollback: η κλήση παραμένει unassigned
        self.assertTrue(VoIPCall.objects.filter(pk=call.pk,
                                                client__isnull=True).exists())

    def test_6_positive_controls_accessible_objects_still_work(self):
        from accounting.models import Ticket, VoIPCall
        from accounting.services.call_assignment import (
            change_call_client, create_ticket_for_call, delete_call,
            delete_ticket,
        )

        call = self._make_call(None, 'STALE-OK1')
        change_call_client(call, self.a, user=self.user)
        ticket = create_ticket_for_call(call, user=self.user)
        delete_ticket(ticket, user=self.user)
        delete_call(call, user=self.user)
        self.assertFalse(VoIPCall.objects.filter(pk=call.pk).exists())
        self.assertFalse(Ticket.objects.filter(pk=ticket.pk).exists())

    def test_7_system_user_none_not_restricted(self):
        from accounting.models import VoIPCall
        from accounting.services.call_assignment import change_call_client

        call = self._make_call(self.b, 'STALE-SYS')
        # System automation (auto-match κλπ): user=None δεν περιορίζεται
        change_call_client(call, self.a)
        self.assertTrue(VoIPCall.objects.filter(pk=call.pk,
                                                client=self.a).exists())
