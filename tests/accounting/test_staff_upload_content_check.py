# -*- coding: utf-8 -*-
"""
SECURITY: ο staff upload path πρέπει να απορρίπτει αρχείο του οποίου το
περιεχόμενο δεν ταιριάζει με την επέκταση (π.χ. εκτελέσιμο μετονομασμένο σε
.pdf), όπως ακριβώς και ο client portal path.

Ιστορικό: ο έλεγχος τύπου βασιζόταν σε `import magic` (python-magic/libmagic).
Στο τοπικό περιβάλλον το `import magic` κάνει hard **segfault** (exit 139), που
ΔΕΝ πιάνεται από try/except ImportError — οπότε κάθε staff upload ρίσκαρε να
ρίξει τον worker. Πλέον χρησιμοποιείται dependency-free magic-bytes έλεγχος
(common/utils/file_validation.py::content_matches_extension).

RequestFactory χρησιμοποιείται για να αποφευχθεί το Py3.14 test-client
HTML-error issue και επειδή ο staff view είναι plain Django view.
"""
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, RequestFactory

from accounting.models import ClientProfile, ClientDocument
from accounting.api_document_upload import upload_document_with_version
from common.utils.file_validation import (
    validate_file_upload,
    content_matches_extension,
)


# .exe (PE) magic bytes — "MZ" header.
EXE_CONTENT = b'MZ\x90\x00\x03\x00\x00\x00'
PDF_CONTENT = b'%PDF-1.7\n%binary\n'


class ValidateFileUploadContentTest(TestCase):
    """Unit-level έλεγχος του validate_file_upload (χωρίς HTTP)."""

    def test_rejects_exe_renamed_to_pdf(self):
        f = SimpleUploadedFile('evil.pdf', EXE_CONTENT,
                               content_type='application/pdf')
        with self.assertRaises(ValidationError):
            validate_file_upload(f)

    def test_accepts_real_pdf(self):
        f = SimpleUploadedFile('ok.pdf', PDF_CONTENT,
                               content_type='application/pdf')
        self.assertTrue(validate_file_upload(f))

    def test_rejects_disallowed_extension(self):
        f = SimpleUploadedFile('hack.exe', EXE_CONTENT,
                               content_type='application/octet-stream')
        with self.assertRaises(ValidationError):
            validate_file_upload(f)

    def test_content_matches_extension_helper(self):
        exe_as_pdf = SimpleUploadedFile('x.pdf', EXE_CONTENT)
        real_pdf = SimpleUploadedFile('x.pdf', PDF_CONTENT)
        self.assertFalse(content_matches_extension(exe_as_pdf, '.pdf'))
        self.assertTrue(content_matches_extension(real_pdf, '.pdf'))
        # Επέκταση χωρίς γνωστή υπογραφή -> επιτρέπεται (το allowlist έχει τρέξει).
        any_txt = SimpleUploadedFile('x.txt', b'anything at all')
        self.assertTrue(content_matches_extension(any_txt, '.txt'))


class StaffUploadContentCheckTest(TestCase):
    """Ο staff endpoint upload_document_with_version πρέπει να απορρίπτει
    περιεχόμενο που δεν ταιριάζει με την επέκταση."""

    def setUp(self):
        self.factory = RequestFactory()
        self.staff = User.objects.create_user(
            username='staff', password='x', is_staff=True)
        self.client_profile = ClientProfile.objects.create(
            afm='094160855', eponimia='ΠΕΛΑΤΗΣ ΑΕ', eidos_ipoxreou='company')

    def _post(self, uploaded):
        req = self.factory.post('/accounting/api/documents/upload-version/', {
            'file': uploaded,
            'client_id': str(self.client_profile.id),
            'category': 'general',
        })
        req.user = self.staff
        return upload_document_with_version(req)

    def test_staff_upload_rejects_exe_renamed_to_pdf(self):
        resp = self._post(SimpleUploadedFile(
            'evil.pdf', EXE_CONTENT, content_type='application/pdf'))
        self.assertEqual(resp.status_code, 400)
        # Τίποτα δεν γράφτηκε για τον πελάτη.
        self.assertFalse(
            ClientDocument.objects.filter(client=self.client_profile).exists())

    def test_staff_upload_accepts_real_pdf(self):
        resp = self._post(SimpleUploadedFile(
            'ok.pdf', PDF_CONTENT, content_type='application/pdf'))
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        self.assertTrue(
            ClientDocument.objects.filter(client=self.client_profile).exists())
