# -*- coding: utf-8 -*-
"""
Tests για την αναζήτηση εγγράφων (accounting/services/search.py) και το
cleanup των stale sync logs.

Τα search tests τρέχουν σε SQLite τοπικά (icontains branch) ΚΑΙ σε
PostgreSQL στο CI (SearchVector branch) — ίδια tests, δύο υλοποιήσεις.
"""
from datetime import timedelta

from django.contrib.auth.models import User
from tests.utils.helpers import grant_accounting_model_perms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from accounting.models import ClientDocument, ClientProfile
from accounting.services.search import apply_document_search


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


class GreekConfusablesSearchTest(TestCase):
    """
    Οι χαρακτήρες που παράγει η εξαγωγή κειμένου από PDF δεν είναι πάντα
    οι πραγματικοί ελληνικοί. Δύο επιβεβαιωμένες περιπτώσεις από παραγωγή:
    «∆» U+2206 INCREMENT αντί «Δ» U+0394, και λατινικοί σωσίες («ΦΠA»
    με λατινικό A). Πριν τη διόρθωση καμία από τις δύο δεν βρισκόταν.
    """
    def setUp(self):
        self.client_profile = ClientProfile.objects.create(
            afm='123456783', eponimia='ΕΤΑΙΡΕΙΑ ΑΕ', eidos_ipoxreou='company'
        )

    def _search(self, term):
        return apply_document_search(
            ClientDocument.objects.all(), term, include_client_fields=False
        )

    def _make(self, name, text):
        from accounting.services.text_normalization import normalize_search_text
        # Το extracted_text αποθηκεύεται πάντα κανονικοποιημένο από το
        # process_document — εδώ αναπαράγεται η ίδια συνθήκη.
        return make_document(self.client_profile, name,
                             extracted_text=normalize_search_text(text))

    def test_increment_sign_in_document_found_by_greek_delta(self):
        doc = self._make('a.pdf', '∆ΟΚΙΜΩΝ ΕΤΑΙΡΕΙΑ')
        self.assertEqual(list(self._search('ΔΟΚΙΜΩΝ')), [doc])

    def test_greek_delta_in_document_found_by_increment_sign(self):
        doc = self._make('b.pdf', 'ΔΟΚΙΜΩΝ ΕΤΑΙΡΕΙΑ')
        self.assertEqual(list(self._search('∆ΟΚΙΜΩΝ')), [doc])

    def test_latin_lookalike_in_document_found_by_greek_term(self):
        # «ΦΠA» με λατινικό A (U+0041)
        doc = self._make('c.pdf', 'ΦΠA ΙΑΝΟΥΑΡΙΟΥ')
        self.assertEqual(list(self._search('ΦΠΑ')), [doc])

    def test_greek_term_with_latin_lookalike_query(self):
        doc = self._make('d.pdf', 'ΦΠΑ ΙΑΝΟΥΑΡΙΟΥ')
        self.assertEqual(list(self._search('ΦΠA')), [doc])

    def test_accent_and_case_insensitive(self):
        doc = self._make('e.pdf', 'Περιοδική δήλωση ΦΠΑ')
        self.assertEqual(list(self._search('δηλωση')), [doc])
        self.assertEqual(list(self._search('ΔΉΛΩΣΗ')), [doc])

    def test_final_sigma_folds(self):
        doc = self._make('f.pdf', 'Κατάσταση εσόδων εξόδων')
        self.assertEqual(list(self._search('κατασταση')), [doc])

    def test_latin_only_term_still_matches_filename(self):
        # Ο μη-κανονικοποιημένος όρος διατηρείται για filename/description,
        # ώστε λατινικά ονόματα να μη «χαθούν» στη χαρτογράφηση.
        doc = make_document(self.client_profile, 'ACME_invoice.pdf')
        self.assertEqual(list(self._search('ACME')), [doc])

    def test_empty_and_plain_terms_unaffected(self):
        doc = self._make('g.pdf', 'Μισθοδοσία προσωπικού')
        self.assertEqual(list(self._search('μισθοδοσια')), [doc])
        self.assertEqual(list(self._search('ανύπαρκτο')), [])
