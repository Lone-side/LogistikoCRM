# -*- coding: utf-8 -*-
"""
Regression tests για το Zadarma webhook (POST /voip/zd/): κακοσχηματισμένα
payloads δεν πρέπει να προκαλούν HTTP 500 (TypeError/binascii.Error).
"""
from unittest.mock import patch

from django.test import TestCase, RequestFactory, override_settings

from voip.views.voipwebhook import is_authenticated

WEBHOOK_URL = '/voip/zd/'

TEST_VOIP = [{
    'BACKEND': 'voip.backends.zadarmabackend.ZadarmaAPI',
    'PROVIDER': 'Zadarma',
    'IP': '127.0.0.1',
    'OPTIONS': {'key': 'k', 'secret': 'test-secret'},
}]


class WebhookMissingFieldsTest(TestCase):
    def test_notify_out_end_missing_fields_no_500(self):
        response = self.client.post(WEBHOOK_URL, {'event': 'NOTIFY_OUT_END'})
        self.assertEqual(response.status_code, 200)

    def test_notify_end_missing_fields_no_500(self):
        response = self.client.post(WEBHOOK_URL, {'event': 'NOTIFY_END'})
        self.assertEqual(response.status_code, 200)

    def test_unknown_event_no_500(self):
        response = self.client.post(WEBHOOK_URL, {'event': 'SOMETHING_ELSE'})
        self.assertEqual(response.status_code, 200)


@override_settings(VOIP=TEST_VOIP, VOIP_FORWARDING_IP='', VOIP_FORWARD_DATA=False)
class IsAuthenticatedInvalidSignatureTest(TestCase):
    def _request(self, headers=None):
        return RequestFactory().post(
            WEBHOOK_URL, {'event': 'NOTIFY_END'}, headers=headers or {},
        )

    def test_missing_signature_returns_false(self):
        self.assertFalse(is_authenticated(self._request(), 'some-data'))

    def test_invalid_base64_signature_returns_false(self):
        request = self._request(headers={'Signature': '%%%not-base64%%%'})
        self.assertFalse(is_authenticated(request, 'some-data'))

    def test_empty_data_returns_false(self):
        self.assertFalse(is_authenticated(self._request(), ''))


@override_settings(VOIP=TEST_VOIP, VOIP_FORWARDING_IP='', VOIP_FORWARD_DATA=False)
class WebhookInvalidDurationTest(TestCase):
    @patch('voip.views.voipwebhook.find_objects_by_phone',
           return_value=(None, None, None, ''))
    @patch('voip.views.voipwebhook.is_authenticated', return_value=True)
    def test_missing_duration_no_500(self, mock_auth, mock_find):
        response = self.client.post(WEBHOOK_URL, {
            'event': 'NOTIFY_END',
            'caller_id': '2101234567',
            'called_did': '100',
            'call_start': '2026-01-01 10:00:00',
        })
        self.assertEqual(response.status_code, 200)

    @patch('voip.views.voipwebhook.find_objects_by_phone',
           return_value=(None, None, None, ''))
    @patch('voip.views.voipwebhook.is_authenticated', return_value=True)
    def test_non_numeric_duration_no_500(self, mock_auth, mock_find):
        response = self.client.post(WEBHOOK_URL, {
            'event': 'NOTIFY_END',
            'caller_id': '2101234567',
            'called_did': '100',
            'call_start': '2026-01-01 10:00:00',
            'duration': 'abc',
        })
        self.assertEqual(response.status_code, 200)
