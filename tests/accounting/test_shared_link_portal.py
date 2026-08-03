# -*- coding: utf-8 -*-
"""
Tests για το portal πελάτη μέσω SharedLink:
- Upload από πελάτη (χωρίς login) → ClientDocument στον φάκελο του πελάτη
- Έλεγχοι: κωδικός/access token, email, όρια uploads, validation αρχείων
- Διορθώσεις ασφαλείας download: κωδικός + doc_id σε folder links
"""
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounting.models import ClientDocument, ClientProfile, SharedLink, SharedLinkAccess

TEMP_MEDIA = tempfile.mkdtemp(prefix='portal_test_')


@override_settings(MEDIA_ROOT=TEMP_MEDIA, DOCUMENT_OCR_SYNC=True)
class SharedLinkPortalBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.client_profile = ClientProfile.objects.create(
            afm='123456783',
            eponimia='ΠΕΛΑΤΗΣ ΠΟΡΤΑΛ ΑΕ',
            eidos_ipoxreou='company',
        )

    def _make_link(self, **kwargs):
        defaults = {'client': self.client_profile, 'allow_upload': True}
        defaults.update(kwargs)
        password = defaults.pop('password', None)
        link = SharedLink(**defaults)
        if password:
            link.set_password(password)
        link.save()
        return link

    def _upload_url(self, link):
        return reverse('accounting:shared_link_upload', args=[link.token])


class PortalUploadTest(SharedLinkPortalBase):
    def test_upload_creates_client_document(self):
        link = self._make_link(upload_category='vat')
        resp = self.client.post(self._upload_url(link), {
            'files': SimpleUploadedFile('φπα_μαρτίου.pdf', b'%PDF-1.4'),
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertTrue(data['success'])
        doc = ClientDocument.objects.get(client=self.client_profile)
        self.assertEqual(doc.document_category, 'vat')
        self.assertIsNone(doc.uploaded_by)
        self.assertIn('portal', doc.description)
        link.refresh_from_db()
        self.assertEqual(link.upload_count, 1)
        self.assertTrue(
            SharedLinkAccess.objects.filter(shared_link=link, action='upload').exists()
        )

    def test_upload_multiple_files(self):
        link = self._make_link()
        resp = self.client.post(self._upload_url(link), {
            'files': [
                SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
                SimpleUploadedFile('b.pdf', b'%PDF-1.4'),
            ],
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.json()['uploaded']), 2)
        self.assertEqual(ClientDocument.objects.filter(client=self.client_profile).count(), 2)

    def test_upload_denied_without_allow_upload(self):
        link = self._make_link(allow_upload=False)
        resp = self.client.post(self._upload_url(link), {
            'files': SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
        })
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(ClientDocument.objects.count(), 0)

    def test_upload_denied_on_expired_link(self):
        from datetime import timedelta
        from django.utils import timezone
        link = self._make_link(expires_at=timezone.now() - timedelta(days=1))
        resp = self.client.post(self._upload_url(link), {
            'files': SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
        })
        self.assertEqual(resp.status_code, 403)

    def test_password_protected_requires_auth(self):
        link = self._make_link(password='μυστικό123')
        # Χωρίς κωδικό/token → 401
        resp = self.client.post(self._upload_url(link), {
            'files': SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
        })
        self.assertEqual(resp.status_code, 401)
        # Σκέτος κωδικός στο body ΔΕΝ αρκεί πλέον — απαιτείται access token
        resp2 = self.client.post(self._upload_url(link), {
            'files': SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
            'password': 'μυστικό123',
        })
        self.assertEqual(resp2.status_code, 401)
        # Με token από το auth POST → OK
        auth = self.client.post(
            reverse('accounting:shared_link_access', args=[link.token]),
            data='{"password": "μυστικό123"}',
            content_type='application/json',
        ).json()
        resp3 = self.client.post(self._upload_url(link), {
            'files': SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
            'auth': auth['access_token'],
        })
        self.assertEqual(resp3.status_code, 201, resp3.content)

    def test_access_token_flow(self):
        """GET με σωστό κωδικό εκδίδει token που δουλεύει για upload."""
        link = self._make_link(password='pass123')
        auth_resp = self.client.post(
            reverse('accounting:shared_link_access', args=[link.token]),
            data='{"password": "pass123"}',
            content_type='application/json',
        )
        self.assertEqual(auth_resp.status_code, 200, auth_resp.content)
        token = auth_resp.json()['access_token']
        resp = self.client.post(self._upload_url(link), {
            'files': SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
            'auth': token,
        })
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_requires_email(self):
        link = self._make_link(requires_email=True)
        # Χωρίς token → 401 (το requires_email καθιστά το link προστατευμένο)
        resp = self.client.post(self._upload_url(link), {
            'files': SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
        })
        self.assertEqual(resp.status_code, 401)
        # Σκέτο email στο body ΔΕΝ αρκεί — θέλει token από το auth POST
        resp2 = self.client.post(self._upload_url(link), {
            'files': SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
            'email': 'pelatis@example.com',
        })
        self.assertEqual(resp2.status_code, 401)
        auth = self.client.post(
            reverse('accounting:shared_link_access', args=[link.token]),
            data='{"email": "pelatis@example.com"}',
            content_type='application/json',
        ).json()
        resp3 = self.client.post(self._upload_url(link), {
            'files': SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
            'email': 'pelatis@example.com',
            'auth': auth['access_token'],
        })
        self.assertEqual(resp3.status_code, 201, resp3.content)
        log = SharedLinkAccess.objects.get(shared_link=link, action='upload')
        self.assertEqual(log.email_provided, 'pelatis@example.com')

    def test_max_uploads_enforced(self):
        link = self._make_link(max_uploads=1)
        resp = self.client.post(self._upload_url(link), {
            'files': SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
        })
        self.assertEqual(resp.status_code, 201)
        resp2 = self.client.post(self._upload_url(link), {
            'files': SimpleUploadedFile('b.pdf', b'%PDF-1.4'),
        })
        self.assertEqual(resp2.status_code, 403)  # can_upload → όριο εξαντλήθηκε

    def test_invalid_extension_rejected(self):
        link = self._make_link()
        resp = self.client.post(self._upload_url(link), {
            'files': SimpleUploadedFile('hack.exe', b'MZ'),
        })
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(ClientDocument.objects.count(), 0)
        self.assertIn('δεν επιτρέπεται', resp.json()['errors'][0]['error'])

    def test_upload_visible_in_portal_content(self):
        """Το GET του link επιστρέφει allow_upload + upload_note."""
        link = self._make_link(upload_note='Χρειαζόμαστε: τιμολόγια Μαρτίου')
        resp = self.client.get(reverse('accounting:shared_link_access', args=[link.token]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['allow_upload'])
        self.assertIn('τιμολόγια Μαρτίου', data['upload_note'])
        self.assertIn('access_token', data)


class DownloadSecurityFixTest(SharedLinkPortalBase):
    def _make_doc(self):
        from accounting.services import filing
        return filing.create_client_document(
            client=self.client_profile,
            uploaded_file=SimpleUploadedFile('doc.pdf', b'%PDF-1.4'),
            category='vat', year=2026, month=1,
        )

    def test_password_link_download_requires_token(self):
        """Πριν: το download αγνοούσε εντελώς τον κωδικό."""
        doc = self._make_doc()
        link = self._make_link(document=doc, client=None, allow_upload=False,
                               password='pass123', access_level='download')
        url = reverse('accounting:shared_link_download', args=[link.token])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 401)
        # Με token από auth → OK
        auth = self.client.post(
            reverse('accounting:shared_link_access', args=[link.token]),
            data='{"password": "pass123"}',
            content_type='application/json',
        ).json()
        resp2 = self.client.get(url, {'auth': auth['access_token']})
        self.assertEqual(resp2.status_code, 200)

    def test_folder_link_download_with_doc_id(self):
        """Πριν: τα folder links δεν μπορούσαν να κατεβάσουν τίποτα."""
        doc = self._make_doc()
        link = self._make_link(allow_upload=False, access_level='download')
        url = reverse('accounting:shared_link_download', args=[link.token])
        resp = self.client.get(url, {'doc_id': doc.id})
        self.assertEqual(resp.status_code, 200)

    def test_folder_link_download_rejects_foreign_doc(self):
        """doc_id άλλου πελάτη → 404 (όχι διαρροή)."""
        other = ClientProfile.objects.create(
            afm='999863881', eponimia='ΑΛΛΟΣ ΠΕΛΑΤΗΣ', eidos_ipoxreou='company',
        )
        from accounting.services import filing
        foreign_doc = filing.create_client_document(
            client=other,
            uploaded_file=SimpleUploadedFile('ξένο.pdf', b'%PDF-1.4'),
            category='vat', year=2026, month=1,
        )
        link = self._make_link(allow_upload=False, access_level='download')
        url = reverse('accounting:shared_link_download', args=[link.token])
        resp = self.client.get(url, {'doc_id': foreign_doc.id})
        self.assertEqual(resp.status_code, 404)


class PortalSecurityHardeningTest(SharedLinkPortalBase):
    def test_portal_upload_never_displaces_staff_document(self):
        """HIGH fix: το upload πελάτη δεν γίνεται «νέα έκδοση» εγγράφου του γραφείου."""
        from accounting.services import filing
        staff_doc = filing.create_client_document(
            client=self.client_profile,
            uploaded_file=SimpleUploadedFile('φπα_γραφείου.pdf', b'%PDF-1.4'),
            category='vat',
        )
        link = self._make_link(upload_category='vat')
        resp = self.client.post(self._upload_url(link), {
            'files': SimpleUploadedFile('junk.pdf', b'%PDF-1.4'),
        })
        self.assertEqual(resp.status_code, 201)
        staff_doc.refresh_from_db()
        self.assertTrue(staff_doc.is_current)  # ΔΕΝ εκτοπίστηκε
        portal_doc = ClientDocument.objects.exclude(id=staff_doc.id).get()
        self.assertEqual(portal_doc.version, 1)
        self.assertIsNone(portal_doc.previous_version_id)

    def test_html_disguised_as_pdf_rejected(self):
        """MEDIUM fix: magic-byte έλεγχος — HTML μεταμφιεσμένο σε .pdf απορρίπτεται."""
        try:
            import magic  # noqa: F401
        except ImportError:
            self.skipTest('python-magic μη διαθέσιμο')
        link = self._make_link()
        html = b'<!DOCTYPE html><html><body><script>alert(1)</script></body></html>'
        resp = self.client.post(self._upload_url(link), {
            'files': SimpleUploadedFile('report.pdf', html),
        })
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(ClientDocument.objects.count(), 0)

    def test_token_invalid_after_password_change(self):
        """LOW fix: αλλαγή κωδικού ακυρώνει τα εκδοθέντα access tokens."""
        link = self._make_link(password='old-pass')
        auth = self.client.post(
            reverse('accounting:shared_link_access', args=[link.token]),
            data='{"password": "old-pass"}',
            content_type='application/json',
        ).json()
        token = auth['access_token']
        link.set_password('new-pass')
        link.save()
        resp = self.client.post(self._upload_url(link), {
            'files': SimpleUploadedFile('a.pdf', b'%PDF-1.4'),
            'auth': token,
        })
        self.assertEqual(resp.status_code, 401)
