# -*- coding: utf-8 -*-
"""
Tests για την εξαγωγή κειμένου εγγράφων (accounting.services.text_extraction)
και τα σχετικά features: πρόταση κατηγορίας, έλεγχος ΑΦΜ, αναζήτηση
περιεχομένου, suggest endpoint.
"""
import io
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounting.models import ClientDocument, ClientProfile
from accounting.services import filing, text_extraction
from common.utils.afm import find_afm_candidates, validate_afm

TEMP_MEDIA = tempfile.mkdtemp(prefix='ocr_test_')


def make_pdf(text):
    """Δημιουργεί PDF bytes με το δοσμένο κείμενο (μέσω xhtml2pdf)."""
    from xhtml2pdf import pisa
    buf = io.BytesIO()
    pisa.CreatePDF(f"<html><body><p>{text}</p></body></html>", dest=buf)
    return buf.getvalue()


class AfmUtilsTest(TestCase):
    def test_validate_afm(self):
        self.assertTrue(validate_afm('123456783'))   # έγκυρο checksum
        self.assertTrue(validate_afm('999863881'))   # έγκυρο checksum
        self.assertFalse(validate_afm('123456789'))  # λάθος checksum
        self.assertFalse(validate_afm('12345'))
        self.assertFalse(validate_afm(''))

    def test_find_afm_candidates_filters_checksum(self):
        text = 'ΑΦΜ πελάτη: 123456783, άσχετος αριθμός 123456789, τηλ 2101234567'
        self.assertEqual(find_afm_candidates(text), ['123456783'])

    def test_find_afm_ignores_longer_numbers(self):
        # 10ψήφιο δεν πρέπει να δώσει 9ψήφιο υποψήφιο
        self.assertEqual(find_afm_candidates('1234567820'), [])


class SuggestCategoryTest(TestCase):
    def test_vat_keywords(self):
        self.assertEqual(text_extraction.suggest_category('ΠΕΡΙΟΔΙΚΗ ΔΗΛΩΣΗ ΦΠΑ'), 'vat')

    def test_payroll_keywords(self):
        self.assertEqual(text_extraction.suggest_category('Κατάσταση μισθοδοσίας Ιουλίου'), 'payroll')

    def test_filename_fallback(self):
        self.assertEqual(text_extraction.suggest_category('', filename='τιμολόγιο_45.pdf'),
                         'invoices_issued')

    def test_unknown(self):
        self.assertIsNone(text_extraction.suggest_category('άσχετο περιεχόμενο'))


@override_settings(MEDIA_ROOT=TEMP_MEDIA, DOCUMENT_OCR_SYNC=True)
class ProcessDocumentTest(TestCase):
    def _doc_user(self):
        """Χρήστης γραφείου (Γύρος 20: user=None μόνο με portal capability)."""
        from django.contrib.auth import get_user_model
        U = get_user_model()
        user = U.objects.filter(username='tx_doc_user').first()
        if user is None:
            user = U.objects.create_superuser('tx_doc_user', 'tx@t.com', 'x')
        return user

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.client_profile = ClientProfile.objects.create(
            afm='123456782',
            eponimia='ΕΤΑΙΡΕΙΑ ΤΕΣΤ ΑΕ',
            eidos_ipoxreou='company',
        )

    def _create_doc(self, name, content):
        with self.captureOnCommitCallbacks(execute=True):
            doc = filing.create_client_document(
                client=self.client_profile,
                uploaded_file=SimpleUploadedFile(name, content),
                category='vat', year=2026, month=3,
                user=self._doc_user(),
            )
        doc.refresh_from_db()
        return doc

    def test_pdf_text_extracted_and_matching_afm(self):
        pdf = make_pdf('ΔΗΛΩΣΗ ΦΠΑ - ΑΦΜ 123456782')
        doc = self._create_doc('fpa.pdf', pdf)
        self.assertEqual(doc.ocr_status, 'done')
        self.assertIn('123456782', doc.extracted_text)
        self.assertFalse(doc.afm_mismatch)
        self.assertIsNotNone(doc.ocr_processed_at)

    def test_afm_mismatch_detected(self):
        # 999863881: έγκυρο checksum, διαφορετικό από τον πελάτη
        pdf = make_pdf('ΤΙΜΟΛΟΓΙΟ - ΑΦΜ 999863881')
        doc = self._create_doc('inv.pdf', pdf)
        self.assertEqual(doc.ocr_status, 'done')
        self.assertTrue(doc.afm_mismatch)

    def test_corrupt_pdf_fails_without_breaking_upload(self):
        doc = self._create_doc(
            'bad.pdf', b'%PDF-1.4\ngarbage without valid xref\n')
        self.assertEqual(doc.ocr_status, 'failed')
        self.assertTrue(ClientDocument.objects.filter(id=doc.id).exists())

    def test_non_pdf_skipped(self):
        import io as _io, zipfile as _zip
        _buf = _io.BytesIO()
        with _zip.ZipFile(_buf, 'w') as _zf:
            _zf.writestr('a.txt', 'x')
        doc = self._create_doc('data.zip', _buf.getvalue())
        self.assertEqual(doc.ocr_status, 'skipped')

    def test_txt_extracted(self):
        doc = self._create_doc('note.txt', 'Σημείωση ΦΠΑ 123456782'.encode('utf-8'))
        self.assertEqual(doc.ocr_status, 'done')
        self.assertIn('ΦΠΑ', doc.extracted_text)


@override_settings(MEDIA_ROOT=TEMP_MEDIA, DOCUMENT_OCR_SYNC=True)
class ContentSearchAndSuggestTest(TestCase):
    def _doc_user(self):
        """Χρήστης γραφείου (Γύρος 20: user=None μόνο με portal capability)."""
        from django.contrib.auth import get_user_model
        U = get_user_model()
        user = U.objects.filter(username='tx_doc_user').first()
        if user is None:
            user = U.objects.create_superuser('tx_doc_user', 'tx@t.com', 'x')
        return user

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.admin = User.objects.create_superuser('ocradmin', 'a@test.com', 'pass12345')
        self.client.force_login(self.admin)
        self.client_profile = ClientProfile.objects.create(
            afm='123456782',
            eponimia='ΕΤΑΙΡΕΙΑ ΤΕΣΤ ΑΕ',
            eidos_ipoxreou='company',
        )

    def test_search_by_content(self):
        pdf = make_pdf('ΜΟΝΑΔΙΚΗΛΕΞΗ ΞΕΝΟΔΟΧΕΙΟ ΑΚΡΟΠΟΛΙΣ')
        with self.captureOnCommitCallbacks(execute=True):
            filing.create_client_document(
                client=self.client_profile,
                uploaded_file=SimpleUploadedFile('doc.pdf', pdf),
                category='general', year=2026, month=1,
                user=self._doc_user(),
            )
        url = f'/accounting/api/v1/clients/{self.client_profile.id}/documents/'
        resp = self.client.get(url, {'search': 'ΜΟΝΑΔΙΚΗΛΕΞΗ'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['total_count'], 1)
        resp2 = self.client.get(url, {'search': 'ΑΝΥΠΑΡΚΤΗΛΕΞΗ'})
        self.assertEqual(resp2.json()['total_count'], 0)

    def test_suggest_endpoint(self):
        pdf = make_pdf('ΠΕΡΙΟΔΙΚΗ ΔΗΛΩΣΗ ΦΠΑ - ΑΦΜ 999863881')
        url = reverse('accounting:api_suggest_document_metadata')
        resp = self.client.post(url, {
            'file': SimpleUploadedFile('doc.pdf', pdf),
            'client_id': self.client_profile.id,
        })
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(data['suggested_category'], 'vat')
        self.assertEqual(data['detected_afm'], '999863881')
        self.assertFalse(data['afm_matches_client'])

    def test_suggest_rejects_bad_extension(self):
        url = reverse('accounting:api_suggest_document_metadata')
        resp = self.client.post(url, {'file': SimpleUploadedFile('x.exe', b'MZ')})
        self.assertEqual(resp.status_code, 400)
