# -*- coding: utf-8 -*-
"""
Tests για το προστατευμένο σερβίρισμα media (common/views/protected_media.py).

Γύρος 14 — document-aware authorization: ένα ενεργό session ΔΕΝ αρκεί
για κάθε αρχείο. Τα ClientDocument αρχεία απαιτούν view_clientdocument +
πρόσβαση στον πελάτη. Τα CRM συνημμένα (common.TheFile) κρατούν το
προηγούμενο μοντέλο (session ή signed token δεμένο στο path). Path χωρίς
αντιστοίχιση σε μοντέλο → 404 (fail closed).
"""
import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import Permission, User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings

from accounting.models import ClientProfile
from common.models import TheFile
from common.utils.media_tokens import (
    make_media_token,
    signed_media_url,
    verify_media_token,
)

TEMP_MEDIA = tempfile.mkdtemp(prefix='test_media_')


@override_settings(MEDIA_ROOT=TEMP_MEDIA, MEDIA_ACCEL_REDIRECT=False,
                   DOCUMENT_OCR_SYNC=True)
class ProtectedMediaViewTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.client_profile = ClientProfile.objects.create(
            afm='123456783', eponimia='ΠΕΛΑΤΗΣ ΑΕ', eidos_ipoxreou='company')
        from accounting.services import filing
        self.doc = filing.create_client_document(
            client=self.client_profile,
            uploaded_file=SimpleUploadedFile('test.pdf', b'%PDF-1.4 test content'),
            category='vat', year=2026, month=1,
        )
        self.rel_path = self.doc.file.name

    def _url(self):
        return f'/media/{self.rel_path}'

    def _user(self, username, codenames=(), assign=True):
        user = User.objects.create_user(username, f'{username}@t.com', 'pass12345')
        for codename in codenames:
            user.user_permissions.add(Permission.objects.get(
                codename=codename, content_type__app_label='accounting'))
        if assign:
            self.client_profile.assigned_users.add(user)
        return User.objects.get(pk=user.pk)

    def test_anonymous_without_token_is_denied(self):
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 403)

    def test_authorized_user_serves_file(self):
        user = self._user('reader', ['view_clientdocument'])
        self.client.force_login(user)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        content = b''.join(resp.streaming_content)
        self.assertIn(b'test content', content)

    def test_authenticated_without_model_perm_denied(self):
        # Session μόνο του δεν αρκεί: χωρίς view_clientdocument → 404
        user = self._user('noperm', [])
        self.client.force_login(user)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 404)

    def test_generic_token_does_not_serve_client_doc(self):
        # Ο γενικός signed token ΔΕΝ παρακάμπτει πλέον το client scoping
        token = make_media_token(self.rel_path)
        resp = self.client.get(self._url(), {'mt': token})
        self.assertEqual(resp.status_code, 403)

    def test_unmapped_path_fails_closed(self):
        orphan = Path(TEMP_MEDIA) / 'orphan.pdf'
        orphan.write_bytes(b'x')
        superuser = User.objects.create_superuser(
            'su', 'su@t.com', 'pass12345')
        self.client.force_login(superuser)
        resp = self.client.get('/media/orphan.pdf')
        self.assertEqual(resp.status_code, 404)

    def test_path_traversal_denied(self):
        from common.views.protected_media import _resolve_media_path
        from django.http import Http404
        with self.assertRaises(Http404):
            _resolve_media_path('../manage.py')

    @override_settings(MEDIA_ACCEL_REDIRECT=True,
                       MEDIA_ACCEL_PREFIX='/protected-media/')
    def test_accel_redirect_mode(self):
        user = self._user('accel', ['view_clientdocument'])
        self.client.force_login(user)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertIn('/protected-media/clients/', resp['X-Accel-Redirect'])
        # Ελληνικοί χαρακτήρες: percent-encoded για το nginx
        self.assertNotIn('ΠΕΛΑΤΗΣ', resp['X-Accel-Redirect'])
        self.assertEqual(resp.content, b'')


@override_settings(MEDIA_ROOT=TEMP_MEDIA, MEDIA_ACCEL_REDIRECT=False)
class CrmFileMediaTest(TestCase):
    """
    Γύρος 15: CRM συνημμένα (TheFile) → object-level authorization βάσει
    του content_object. Δεν αρκεί session, ούτε γενικός ?mt= token.
    Πλήρης owner/department κάλυψη στο test_rbac_round15.TheFileAuthTest·
    εδώ ελέγχεται το fail-closed για μη-CRM content_object.
    """
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.client_profile = ClientProfile.objects.create(
            afm='123456783', eponimia='ΠΕΛΑΤΗΣ ΑΕ', eidos_ipoxreou='company')
        ct = ContentType.objects.get_for_model(ClientProfile)
        self.the_file = TheFile(content_type=ct,
                                object_id=self.client_profile.pk)
        self.the_file.file.save('note.txt', ContentFile(b'crm note'), save=True)
        self.rel_path = self.the_file.file.name

    def _url(self):
        return f'/media/{self.rel_path}'

    def test_crm_file_session_alone_denied(self):
        # ClientProfile content_object δεν υποστηρίζει CRM policy → 404
        user = User.objects.create_user('plain', 'p@t.com', 'pass12345')
        self.client.force_login(user)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 404)

    def test_crm_file_token_denied(self):
        resp = self.client.get(self._url(),
                               {'mt': make_media_token(self.rel_path)})
        self.assertEqual(resp.status_code, 404)

    def test_crm_file_anonymous_denied(self):
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 404)

    def test_crm_file_superuser_serves(self):
        su = User.objects.create_superuser('su_crm', 'su@t.com', 'pass12345')
        self.client.force_login(su)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)


class MediaTokenTest(TestCase):
    def test_roundtrip(self):
        token = make_media_token('a/b/γ.pdf')
        self.assertTrue(verify_media_token(token, 'a/b/γ.pdf'))
        self.assertFalse(verify_media_token(token, 'a/b/other.pdf'))
        self.assertFalse(verify_media_token('garbage', 'a/b/γ.pdf'))

    def test_signed_media_url_contains_token(self):
        class FakeField:
            name = 'clients/x/file.pdf'
            url = '/media/clients/x/file.pdf'

        url = signed_media_url(FakeField())
        self.assertIn('/media/clients/x/file.pdf?mt=', url)
        token = url.split('mt=')[1]
        from urllib.parse import unquote
        self.assertTrue(verify_media_token(unquote(token), 'clients/x/file.pdf'))

    def test_signed_media_url_none(self):
        self.assertIsNone(signed_media_url(None))
