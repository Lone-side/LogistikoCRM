# -*- coding: utf-8 -*-
"""
Tests για το προστατευμένο σερβίρισμα media (common/views/protected_media.py).

Σε production (DEBUG=False — όπως τρέχουν και τα tests) τα /media/ URLs
απαιτούν είτε συνδεδεμένο χρήστη είτε έγκυρο signed token (?mt=...).
"""
import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from common.utils.media_tokens import (
    make_media_token,
    signed_media_url,
    verify_media_token,
)

TEMP_MEDIA = tempfile.mkdtemp(prefix='test_media_')


@override_settings(MEDIA_ROOT=TEMP_MEDIA, MEDIA_ACCEL_REDIRECT=False)
class ProtectedMediaViewTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rel_path = 'clients/123456783_ΠΕΛΑΤΗΣ/2026/01/ΦΠΑ/test.pdf'
        full = Path(TEMP_MEDIA) / cls.rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(b'%PDF-1.4 test content')

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def _url(self):
        return f'/media/{self.rel_path}'

    def test_anonymous_without_token_is_denied(self):
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 403)

    def test_valid_token_serves_file(self):
        token = make_media_token(self.rel_path)
        resp = self.client.get(self._url(), {'mt': token})
        self.assertEqual(resp.status_code, 200)
        content = b''.join(resp.streaming_content)
        self.assertIn(b'test content', content)

    def test_token_bound_to_path(self):
        # Token για άλλο αρχείο δεν ανοίγει αυτό
        token = make_media_token('clients/other/file.pdf')
        resp = self.client.get(self._url(), {'mt': token})
        self.assertEqual(resp.status_code, 403)

    def test_tampered_token_is_denied(self):
        token = make_media_token(self.rel_path)
        resp = self.client.get(self._url(), {'mt': token[:-3] + 'xxx'})
        self.assertEqual(resp.status_code, 403)

    def test_authenticated_user_without_token(self):
        User.objects.create_user('staff1', 's@test.com', 'pass12345')
        self.client.login(username='staff1', password='pass12345')
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)

    def test_missing_file_with_valid_token_404(self):
        path = 'clients/does/not/exist.pdf'
        resp = self.client.get(f'/media/{path}', {'mt': make_media_token(path)})
        self.assertEqual(resp.status_code, 404)

    def test_path_traversal_denied(self):
        # Ακόμα και με συνδεδεμένο χρήστη, έξοδος από το MEDIA_ROOT → 404
        from common.views.protected_media import _resolve_media_path
        from django.http import Http404
        with self.assertRaises(Http404):
            _resolve_media_path('../manage.py')

    @override_settings(MEDIA_ACCEL_REDIRECT=True, MEDIA_ACCEL_PREFIX='/protected-media/')
    def test_accel_redirect_mode(self):
        token = make_media_token(self.rel_path)
        resp = self.client.get(self._url(), {'mt': token})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('/protected-media/clients/', resp['X-Accel-Redirect'])
        # Ελληνικοί χαρακτήρες: percent-encoded για το nginx
        self.assertNotIn('ΠΕΛΑΤΗΣ', resp['X-Accel-Redirect'])
        self.assertEqual(resp.content, b'')


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
