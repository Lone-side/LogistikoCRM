# -*- coding: utf-8 -*-
"""
Tests για την αναζήτηση εγγράφων (accounting/services/search.py) και το
cleanup των stale sync logs.

Τα search tests τρέχουν σε SQLite τοπικά (icontains branch) ΚΑΙ σε
PostgreSQL στο CI (SearchVector branch) — ίδια tests, δύο υλοποιήσεις.
"""
from datetime import timedelta

from unittest import skipUnless

from django.contrib.auth.models import User
from tests.utils.helpers import grant_accounting_model_perms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from accounting.models import ClientDocument, ClientProfile
from accounting.services.search import _to_greek, apply_document_search


def make_document(client, filename, extracted_text='', description=''):
    # Γύρος 19: μοναδικό slot ανά fixture — δύο ανεξάρτητα current έγγραφα
    # στο ίδιο key απαγορεύονται πλέον από το DB constraint
    return ClientDocument.objects.create(
        client=client,
        file=SimpleUploadedFile(filename, b'%PDF-1.4 test'),
        filename=filename,
        original_filename=filename,
        extracted_text=extracted_text,
        description=description,
        document_category='general',
        year=2026,
        month=7,
        slot=f'test-{filename}'[:64],
    )


class DocumentSearchTest(TestCase):
    def setUp(self):
        self.client_profile = ClientProfile.objects.create(
            afm='123456783', eponimia='ΕΤΑΙΡΕΙΑ ΔΟΚΙΜΩΝ ΑΕ', eidos_ipoxreou='company'
        )
        self.doc_vat = make_document(
            self.client_profile, 'dilosi.pdf',
            extracted_text='Περιοδική δήλωση ΦΠΑ περιόδου Ιουλίου 2026',
        )
        self.doc_payroll = make_document(
            self.client_profile, 'misthodosia_iouliou.pdf',
            extracted_text='Κατάσταση μισθοδοσίας προσωπικού',
        )

    def _search(self, term, include_client_fields=True):
        return apply_document_search(
            ClientDocument.objects.all(), term, include_client_fields
        )

    def test_search_in_extracted_text(self):
        results = self._search('μισθοδοσίας')
        self.assertEqual(list(results), [self.doc_payroll])

    def test_search_in_filename(self):
        results = self._search('dilosi')
        self.assertEqual(list(results), [self.doc_vat])

    def test_search_no_results(self):
        self.assertEqual(self._search('ανύπαρκτος-όρος-xyz').count(), 0)

    def test_empty_term_returns_queryset_unchanged(self):
        self.assertEqual(self._search('').count(), 2)

    def test_client_fields_flag(self):
        # Με client fields: βρίσκει μέσω επωνυμίας πελάτη
        self.assertEqual(self._search('ΔΟΚΙΜΩΝ').count(), 2)
        # Χωρίς client fields: όχι
        self.assertEqual(
            self._search('ΔΟΚΙΜΩΝ', include_client_fields=False).count(), 0
        )

    def test_file_manager_endpoint_search(self):
        user = grant_accounting_model_perms(User.objects.create_user('staff1', 's@test.com', 'pass12345'))
        self.client.force_login(user)
        resp = self.client.get(
            '/accounting/api/v1/file-manager/documents/', {'search': 'μισθοδοσίας'}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        results = data['results'] if isinstance(data, dict) else data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['filename'], 'misthodosia_iouliou.pdf')


class CleanupStaleSyncLogsTest(TestCase):
    def test_stale_pending_marked_error_recent_untouched(self):
        from inventory.models import MyDataSyncLog
        from mydata.models import VATSyncLog
        from accounting.tasks import cleanup_stale_sync_logs

        stale_invoice = MyDataSyncLog.objects.create(
            sync_type='PUSH_INVOICE', status='PENDING'
        )
        fresh_invoice = MyDataSyncLog.objects.create(
            sync_type='PUSH_INVOICE', status='PENDING'
        )
        stale_vat = VATSyncLog.objects.create(sync_type='VAT_INFO', status='PENDING')
        done = MyDataSyncLog.objects.create(sync_type='PUSH_INVOICE', status='SUCCESS')

        # started_at είναι auto_now_add — πήγαινε τα stale 2 ώρες πίσω
        two_hours_ago = timezone.now() - timedelta(hours=2)
        MyDataSyncLog.objects.filter(pk=stale_invoice.pk).update(started_at=two_hours_ago)
        VATSyncLog.objects.filter(pk=stale_vat.pk).update(started_at=two_hours_ago)

        result = cleanup_stale_sync_logs()
        self.assertIn('2', result)

        stale_invoice.refresh_from_db()
        self.assertEqual(stale_invoice.status, 'ERROR')
        self.assertIn('stale', stale_invoice.error_message)
        self.assertIsNotNone(stale_invoice.completed_at)

        stale_vat.refresh_from_db()
        self.assertEqual(stale_vat.status, 'ERROR')

        fresh_invoice.refresh_from_db()
        self.assertEqual(fresh_invoice.status, 'PENDING')
        done.refresh_from_db()
        self.assertEqual(done.status, 'SUCCESS')

    def test_custom_threshold(self):
        from inventory.models import MyDataSyncLog
        from accounting.tasks import cleanup_stale_sync_logs

        log = MyDataSyncLog.objects.create(sync_type='PUSH_INVOICE', status='PENDING')
        MyDataSyncLog.objects.filter(pk=log.pk).update(
            started_at=timezone.now() - timedelta(minutes=10)
        )
        # Με κατώφλι 5' το 10λεπτο log είναι stale
        cleanup_stale_sync_logs(stale_minutes=5)
        log.refresh_from_db()
        self.assertEqual(log.status, 'ERROR')


class GreekDeltaSearchTest(TestCase):
    """
    Η αναζήτηση όταν το «Δ» δεν είναι «Δ».

    Το pypdf 6.15.0 εξήγαγε το ελληνικό Δ (U+0394) ως ∆ (U+2206, INCREMENT).
    Η έκδοση είναι πλέον καρφωμένη στο 6.14.2, αλλά **τα ήδη αποθηκευμένα
    extracted_text δεν ξαναγράφονται**: όποιο έγγραφο επεξεργάστηκε με τη
    χαλασμένη έκδοση κουβαλά U+2206 για πάντα. Για λογιστικό γραφείο αυτό
    σημαίνει ότι ΔΗΛΩΣΗ, ΔΟΥ, ΑΔΕΙΑ, ΔΙΑΒΙΒΑΣΗ γίνονται μη ευρέσιμα.

    Τα tests παρακάτω ΔΕΝ υποθέτουν καμία υπάρχουσα normalization — μετρούν
    τη συμπεριφορά της πραγματικής διαδρομής αναζήτησης
    (apply_document_search) και για τις δύο γραφές.
    """

    def setUp(self):
        self.client_profile = ClientProfile.objects.create(
            afm='123456783', eponimia='ΕΤΑΙΡΕΙΑ ΔΟΚΙΜΩΝ ΑΕ',
            eidos_ipoxreou='company',
        )
        # Έγγραφο με ΣΩΣΤΟ ελληνικό Δ (U+0394) — pypdf 6.14.2
        self.doc_correct = make_document(
            self.client_profile, 'sosto.pdf',
            extracted_text='ΔΗΛΩΣΗ ΦΠΑ προς ΔΟΥ Αθηνών',
        )
        # Έγγραφο με ∆ (U+2206) — ό,τι άφησε πίσω το pypdf 6.15.0
        self.doc_increment = make_document(
            self.client_profile, 'xalasmeno.pdf',
            extracted_text='∆ΗΛΩΣΗ ΦΠΑ προς '
                           '∆ΟΥ Θεσσαλονίκης',
        )

    def _search(self, term):
        return list(apply_document_search(
            ClientDocument.objects.all(), term, include_client_fields=False))

    def test_fixture_really_contains_increment_sign(self):
        """Δίχτυ: αν το fixture δεν έχει U+2206, τα υπόλοιπα tests είναι κενά."""
        self.doc_increment.refresh_from_db()
        self.assertIn('∆', self.doc_increment.extracted_text)
        self.assertNotIn('Δ', self.doc_increment.extracted_text)
        self.doc_correct.refresh_from_db()
        self.assertIn('Δ', self.doc_correct.extracted_text)

    def test_normal_delta_finds_normal_document(self):
        """Βάση αναφοράς: το σωστό Δ βρίσκει το σωστό έγγραφο."""
        self.assertIn(self.doc_correct, self._search('ΔΗΛΩΣΗ'))

    def test_normal_delta_finds_increment_document(self):
        """Ο χρήστης γράφει Δ (U+0394) — πρέπει να βρει και το ∆ έγγραφο."""
        self.assertIn(
            self.doc_increment, self._search('ΔΗΛΩΣΗ'),
            'έγγραφο με ∆ (U+2206) δεν βρίσκεται όταν ο χρήστης γράφει Δ')

    def test_increment_sign_finds_normal_document(self):
        """Και το αντίστροφο: επικόλληση ∆ πρέπει να βρίσκει το σωστό Δ."""
        self.assertIn(
            self.doc_correct, self._search('∆ΗΛΩΣΗ'),
            'έγγραφο με σωστό Δ δεν βρίσκεται όταν ο όρος έχει ∆')

    @skipUnless(
        connection.vendor == 'postgresql',
        'Το LIKE του SQLite κάνει case-folding μόνο σε ASCII: το «δ» δεν '
        'ταιριάζει ποτέ με «Δ», ανεξάρτητα από αυτή τη διόρθωση. Η παραγωγή '
        'τρέχει PostgreSQL, όπου ο έλεγχος γίνεται πλήρης.',
    )
    def test_lowercase_delta_finds_both(self):
        """Πεζό δ: η αναζήτηση είναι case-insensitive και για τις δύο γραφές."""
        results = self._search('δηλωση')
        self.assertIn(self.doc_correct, results, 'πεζό δ δεν βρήκε το σωστό Δ')
        self.assertIn(self.doc_increment, results, 'πεζό δ δεν βρήκε το ∆')

    def test_uppercase_delta_finds_both_on_every_backend(self):
        """
        Η ίδια κάλυψη χωρίς εξάρτηση από case-folding, ώστε να ελέγχεται και
        στο SQLite: κεφαλαίος όρος, κεφαλαία δεδομένα, δύο γραφές του Δ.
        """
        results = self._search('ΔΗΛΩΣΗ')
        self.assertIn(self.doc_correct, results)
        self.assertIn(self.doc_increment, results)

    def test_delta_inside_word_is_found(self):
        """ΔΟΥ μέσα σε πρόταση — και στις δύο γραφές."""
        self.assertIn(self.doc_correct, self._search('ΔΟΥ'))
        self.assertIn(self.doc_increment, self._search('ΔΟΥ'))

    def test_unrelated_math_symbols_are_not_normalized(self):
        """
        Φράχτης εύρους: ΜΟΝΟ το ∆ (U+2206) κανονικοποιείται.

        Τα ∑ (U+2211) και ∏ (U+220F) είναι κανονικά μαθηματικά σύμβολα με
        δική τους σημασία — αν τα μεταφράζαμε σε Σ/Π, μια αναζήτηση για
        «ΣΥΝΟΛΟ» θα επέστρεφε ψευδώς έγγραφο που γράφει «∑ x». Το test
        κλειδώνει ότι δεν συμβαίνει, ώστε να μην ξαναμπούν speculative
        mappings χωρίς fail-before απόδειξη.
        """
        doc_math = make_document(
            self.client_profile, 'mathimatika.pdf',
            extracted_text='Τύπος: ∑ x_i και ∏ y_i',
        )

        # Το σύμβολο μένει ανέπαφο στο επίπεδο της συνάρτησης...
        self.assertEqual(_to_greek('∑ ∏ µ'), '∑ ∏ µ')
        # ...και το ∆ εξακολουθεί να μεταφράζεται.
        self.assertEqual(_to_greek('∆'), 'Δ')

        # Αναζήτηση με ελληνικό γράμμα ΔΕΝ πρέπει να πιάνει το σύμβολο.
        self.assertNotIn(
            doc_math, self._search('Σ x_i'),
            'το ∑ κανονικοποιήθηκε σε Σ — ψευδές αποτέλεσμα αναζήτησης')
        self.assertNotIn(
            doc_math, self._search('Π y_i'),
            'το ∏ κανονικοποιήθηκε σε Π — ψευδές αποτέλεσμα αναζήτησης')

        # Το ίδιο το σύμβολο παραμένει ευρέσιμο ως έχει.
        self.assertIn(doc_math, self._search('∑ x_i'))
