# -*- coding: utf-8 -*-
"""
Zadarma VoIP webhook authentication — security regression
=========================================================
Το webhook δημιουργεί CRM ενέργειες από εξωτερικό input, οπότε ο έλεγχος
γνησιότητας πρέπει να είναι σωστός: IP allowlist + HMAC. Tests κλειδώνουν τη
διόρθωση: constant-time σύγκριση + fail-closed σε missing/malformed Signature
(πριν: b64decode(None) → TypeError → 500).
"""
import hmac
from hashlib import sha1
from base64 import b64encode

from django.test import SimpleTestCase, RequestFactory, override_settings

from voip.views.voipwebhook import is_authenticated

_SECRET = 'test-secret-key'
_VOIP = [{'PROVIDER': 'Zadarma', 'IP': '185.45.152.42', 'OPTIONS': {'secret': _SECRET}}]


@override_settings(VOIP=_VOIP, VOIP_FORWARDING_IP='10.0.0.9')
class VoipWebhookAuthTest(SimpleTestCase):
    rf = RequestFactory()

    def _sig(self, data, secret=_SECRET):
        h = hmac.new(secret.encode(), data.encode(), sha1)
        return b64encode(h.hexdigest().encode()).decode()

    def _req(self, ip='185.45.152.42', signature=None):
        extra = {'REMOTE_ADDR': ip}
        if signature is not None:
            extra['HTTP_SIGNATURE'] = signature
        return self.rf.post('/voip/webhook/', data={}, **extra)

    def test_valid_signature_from_allowed_ip(self):
        data = 'internal123start'
        self.assertTrue(is_authenticated(self._req(signature=self._sig(data)), data))

    def test_wrong_signature_rejected(self):
        data = 'internal123start'
        self.assertFalse(is_authenticated(self._req(signature=self._sig('tampered')), data))

    def test_missing_signature_header_no_crash(self):
        # Πριν: b64decode(None) → TypeError → 500. Τώρα fail-closed.
        self.assertFalse(is_authenticated(self._req(signature=None), 'data'))

    def test_malformed_signature_no_crash(self):
        self.assertFalse(is_authenticated(self._req(signature='!!!not base64!!!'), 'data'))

    def test_wrong_ip_rejected(self):
        data = 'data'
        self.assertFalse(is_authenticated(self._req(ip='1.2.3.4', signature=self._sig(data)), data))

    def test_forwarding_ip_allowed(self):
        data = 'data'
        self.assertTrue(is_authenticated(self._req(ip='10.0.0.9', signature=self._sig(data)), data))

    def test_empty_data_rejected(self):
        self.assertFalse(is_authenticated(self._req(signature=self._sig('')), ''))
