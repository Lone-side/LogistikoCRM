# -*- coding: utf-8 -*-
"""
Tests για την ενιαία υπηρεσία αρχειοθέτησης (accounting.services.filing).

Καλύπτει:
- validate_upload βάσει FilingSystemSettings (καταλήξεις/μέγεθος, ελληνικά μηνύματα)
- get_document_dir για permanent/monthly/yearend (και ελληνικούς μήνες)
- ensure_folders (idempotent, νέο έτος, INFO.txt)
- create_client_document (δημιουργία, versioning, φάκελοι on-demand)
- Endpoint upload υποχρέωσης: δημιουργεί ClientDocument, όχι deprecated attachment
- file_download: απόρριψη path traversal
"""
import os
import shutil
import tempfile
from datetime import date

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounting.models import ClientDocument, ClientProfile, MonthlyObligation, ObligationType
from accounting.services import filing
from settings.models import FilingSystemSettings

TEMP_MEDIA = tempfile.mkdtemp(prefix='filing_test_')


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class FilingServiceBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.client_profile = ClientProfile.objects.create(
            afm='123456782',
            eponimia='ΔΟΚΙΜΑΣΤΙΚΗ ΕΤΑΙΡΕΙΑ ΑΕ',
            eidos_ipoxreou='company',
            doy="Α' ΑΘΗΝΩΝ",
        )
        self.filing_settings = FilingSystemSettings.get_settings()
        # Γύρος 17: το versioning/replace απαιτεί πλέον permissions —
        # τα tests εδώ ελέγχουν τη μηχανική, όχι το matrix
        from django.contrib.auth import get_user_model
        self.doc_user = get_user_model().objects.create_superuser(
            f'filing_su_{self.id().split(".")[-1][:20]}', 'su@t.com', 'x')


class ValidateUploadTest(FilingServiceBase):
    def test_blocked_extension_greek_error(self):
        f = SimpleUploadedFile('malware.exe', b'MZ')
        with self.assertRaises(ValidationError) as ctx:
            filing.validate_upload(f)
        self.assertIn('δεν επιτρέπεται', str(ctx.exception.messages[0]))

    def test_oversize_file_greek_error(self):
        self.filing_settings.max_file_size_mb = 1
        self.filing_settings.save()
        f = SimpleUploadedFile('big.pdf', b'x' * (1024 * 1024 + 1))
        with self.assertRaises(ValidationError) as ctx:
            filing.validate_upload(f)
        self.assertIn('πολύ μεγάλο', str(ctx.exception.messages[0]))

    def test_valid_file_passes(self):
        f = SimpleUploadedFile('δήλωση_φπα.pdf', b'%PDF-1.4')
        filing.validate_upload(f)  # δεν πρέπει να σκάσει

    def test_settings_extensions_respected(self):
        # Επιτρέπουμε ΜΟΝΟ .pdf — τα .xlsx πρέπει πλέον να απορρίπτονται
        self.filing_settings.allowed_extensions = '.pdf'
        self.filing_settings.save()
        with self.assertRaises(ValidationError):
            filing.validate_upload(SimpleUploadedFile('data.xlsx', b'PK'))
        filing.validate_upload(SimpleUploadedFile(
            'doc.pdf', b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n'))


class GetDocumentDirTest(FilingServiceBase):
    def test_permanent_path(self):
        path = filing.get_document_dir(self.client_profile, 'contracts')
        self.assertIn('00_ΜΟΝΙΜΑ', path)
        self.assertTrue(path.endswith(os.path.join('00_ΜΟΝΙΜΑ', 'contracts')))
        self.assertTrue(path.startswith(os.path.join('clients', '123456782_')))

    def test_monthly_path(self):
        path = filing.get_document_dir(self.client_profile, 'vat', year=2026, month=3)
        self.assertTrue(path.endswith(os.path.join('2026', '03', 'vat')))

    def test_yearend_path(self):
        path = filing.get_document_dir(self.client_profile, 'e1', year=2026, month=7)
        self.assertTrue(path.endswith(os.path.join('2026', '13_ΕΤΗΣΙΑ', 'e1')))

    def test_greek_month_names(self):
        self.filing_settings.use_greek_month_names = True
        self.filing_settings.save()
        path = filing.get_document_dir(self.client_profile, 'vat', year=2026, month=1)
        self.assertIn('01_Ιανουάριος', path)


class EnsureFoldersTest(FilingServiceBase):
    def test_creates_tree_and_info(self):
        base = filing.ensure_folders(self.client_profile, year=2026)
        self.assertIsNotNone(base)
        self.assertTrue(os.path.isdir(os.path.join(base, '00_ΜΟΝΙΜΑ', 'contracts')))
        self.assertTrue(os.path.isdir(os.path.join(base, '2026', '05', 'vat')))
        self.assertTrue(os.path.isdir(os.path.join(base, '2026', '13_ΕΤΗΣΙΑ', 'e1')))
        info = os.path.join(base, 'INFO.txt')
        self.assertTrue(os.path.isfile(info))
        with open(info, encoding='utf-8') as f:
            content = f.read()
        self.assertIn('ΔΟΚΙΜΑΣΤΙΚΗ ΕΤΑΙΡΕΙΑ ΑΕ', content)
        self.assertIn('123456782', content)

    def test_idempotent(self):
        base1 = filing.ensure_folders(self.client_profile, year=2026)
        base2 = filing.ensure_folders(self.client_profile, year=2026)
        self.assertEqual(base1, base2)

    def test_new_year_rollover(self):
        filing.ensure_folders(self.client_profile, year=2027)
        base = filing.get_client_folder_path(self.client_profile)
        self.assertTrue(os.path.isdir(os.path.join(base, '2027', '12', 'payroll')))


class CreateClientDocumentTest(FilingServiceBase):
    def _upload(self, name='test.pdf', **kwargs):
        kwargs.setdefault('user', self.doc_user)
        return filing.create_client_document(
            client=self.client_profile,
            uploaded_file=SimpleUploadedFile(name, b'%PDF-1.4 test'),
            **kwargs,
        )

    def test_creates_document(self):
        doc = self._upload(category='vat', year=2026, month=2)
        self.assertEqual(doc.document_category, 'vat')
        self.assertEqual((doc.year, doc.month), (2026, 2))
        self.assertEqual(doc.version, 1)
        self.assertTrue(doc.is_current)
        self.assertIn(os.path.join('2026', '02', 'vat'), doc.file.name)

    def test_versioning_same_combo(self):
        doc1 = self._upload(category='vat', year=2026, month=2)
        doc2 = self._upload(category='vat', year=2026, month=2)
        doc1.refresh_from_db()
        self.assertFalse(doc1.is_current)
        self.assertEqual(doc2.version, 2)
        self.assertTrue(doc2.is_current)
        self.assertEqual(doc2.previous_version_id, doc1.id)

    def test_invalid_file_rejected(self):
        with self.assertRaises(ValidationError):
            self._upload(name='script.sh')

    def test_folders_created_for_document_year(self):
        self._upload(category='vat', year=2028, month=6)
        base = filing.get_client_folder_path(self.client_profile)
        self.assertTrue(os.path.isdir(os.path.join(base, '2028', '11', 'myf')))


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ObligationUploadEndpointTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.admin = User.objects.create_superuser('uploader', 'u@test.com', 'pass12345')
        self.client.force_login(self.admin)
        self.client_profile = ClientProfile.objects.create(
            afm='123456782',
            eponimia='ΕΤΑΙΡΕΙΑ ΤΕΣΤ',
            eidos_ipoxreou='company',
        )
        self.obligation_type = ObligationType.objects.create(code='ΦΠΑ', name='ΦΠΑ')
        self.obligation = MonthlyObligation.objects.create(
            client=self.client_profile,
            obligation_type=self.obligation_type,
            year=2026, month=3,
            deadline=date(2026, 4, 20),
        )

    def test_upload_creates_client_document(self):
        url = reverse('accounting:obligation_upload_file', args=[self.obligation.id])
        resp = self.client.post(url, {'file': SimpleUploadedFile('fpa.pdf', b'%PDF-1.4')})
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertTrue(data['success'])
        doc = ClientDocument.objects.get(obligation=self.obligation)
        self.assertEqual(doc.document_category, 'vat')
        self.assertEqual((doc.year, doc.month), (2026, 3))
        # Δεν γράφει πλέον στο deprecated πεδίο attachment
        self.obligation.refresh_from_db()
        self.assertFalse(self.obligation.attachment)

    def test_upload_rejects_blocked_extension(self):
        url = reverse('accounting:obligation_upload_file', args=[self.obligation.id])
        resp = self.client.post(url, {'file': SimpleUploadedFile('hack.exe', b'MZ')})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('δεν επιτρέπεται', resp.json()['error'])

    def test_non_pdf_allowed_types_accepted(self):
        # Το παλιό endpoint δεχόταν μόνο PDF — τώρα ισχύουν οι ρυθμίσεις
        url = reverse('accounting:obligation_upload_file', args=[self.obligation.id])
        # Γύρος 20: απαιτείται ΠΡΑΓΜΑΤΙΚΟ OOXML container (σκέτο 'PK'
        # απορρίπτεται πλέον ως κατεστραμμένο)
        import io as _io, zipfile as _zip
        _buf = _io.BytesIO()
        with _zip.ZipFile(_buf, 'w') as _zf:
            _zf.writestr('[Content_Types].xml', '<?xml version="1.0"?><T/>')
            _zf.writestr('xl/workbook.xml', '<?xml version="1.0"?><w/>')
        resp = self.client.post(
            url, {'file': SimpleUploadedFile('data.xlsx', _buf.getvalue())})
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_download_rejects_traversal(self):
        url = reverse(
            'accounting:file_download',
            args=[self.client_profile.id, '../../../etc/passwd'],
        )
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (403, 404))
        if resp.status_code == 403:
            self.assertIn(b'Access denied', resp.content)


class AutoNamingTest(FilingServiceBase):
    """Ο Κανόνας Ονοματολογίας των ρυθμίσεων εφαρμόζεται στο upload."""

    def _upload(self, name='Τιμολόγιο (3).pdf', **kwargs):
        kwargs.setdefault('user', self.doc_user)
        return filing.create_client_document(
            client=self.client_profile,
            uploaded_file=SimpleUploadedFile(name, b'%PDF-1.4'),
            **kwargs,
        )

    def test_original_convention_keeps_name(self):
        doc = self._upload(category='vat', year=2026, month=2)
        self.assertIn('Τιμολόγιο', doc.filename)

    def test_original_filename_is_pre_sanitize(self):
        doc = self._upload(name='..κακό/όνομα.pdf', category='vat', year=2026, month=2)
        self.assertEqual(doc.original_filename, '..κακό/όνομα.pdf'.split('/')[-1])

    def test_structured_convention(self):
        self.filing_settings.file_naming_convention = 'structured'
        self.filing_settings.save()
        doc = self._upload(category='vat', year=2026, month=3)
        # {YYYYMMDD}_{ΑΦΜ}_{κατηγορία}_{όνομα}.pdf με ημερομηνία την 1η της περιόδου
        self.assertTrue(doc.filename.startswith('20260301_123456782_vat_'), doc.filename)
        self.assertIn('Τιμολόγιο', doc.original_filename)

    def test_date_prefix_convention(self):
        self.filing_settings.file_naming_convention = 'date_prefix'
        self.filing_settings.save()
        doc = self._upload(category='myf', year=2027, month=11)
        self.assertTrue(doc.filename.startswith('20271101_'), doc.filename)

    def test_afm_prefix_convention(self):
        self.filing_settings.file_naming_convention = 'afm_prefix'
        self.filing_settings.save()
        doc = self._upload(category='vat', year=2026, month=2)
        self.assertTrue(doc.filename.startswith('123456782_'), doc.filename)

    def test_version_suffix_in_new_versions(self):
        doc1 = self._upload(category='vat', year=2026, month=5)
        doc2 = self._upload(category='vat', year=2026, month=5)
        self.assertEqual(doc2.version, 2)
        self.assertIn('_v2', doc2.filename)
        self.assertEqual(doc2.original_filename, 'Τιμολόγιο (3).pdf')
        doc1.refresh_from_db()
        self.assertFalse(doc1.is_current)

    def test_replace_semantics(self):
        doc1 = self._upload(category='vat', year=2026, month=6)
        doc2 = filing.create_client_document(
            client=self.client_profile,
            uploaded_file=SimpleUploadedFile('νέο.pdf', b'%PDF-1.4'),
            category='vat', year=2026, month=6,
            on_existing='replace', user=self.doc_user,
        )
        self.assertEqual(doc2.version, 1)
        self.assertTrue(doc2.is_current)
        self.assertFalse(ClientDocument.objects.filter(id=doc1.id).exists())
