# -*- coding: utf-8 -*-
"""
Tests για το mydata/client.py — transport layer (χωρίς πραγματικά HTTP calls).

Mock seam: αντικαθιστούμε το client.session με Mock και μηδενίζουμε
rate limiting / retry sleeps ώστε τα tests να είναι γρήγορα.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from mydata.client import (
    MyDataAPIError,
    MyDataAuthError,
    MyDataClient,
    MyDataRateLimitError,
    MyDataServerError,
    MyDataValidationError,
)


def make_response(status_code=200, text='', content_type='application/xml', json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.content = text.encode('utf-8') if text else b''
    resp.headers = {'Content-Type': content_type}
    if json_data is not None:
        import json as _json
        resp.json.return_value = json_data
        resp.text = _json.dumps(json_data)
        resp.content = resp.text.encode('utf-8')
        resp.headers = {'Content-Type': 'application/json'}
    return resp


class ClientTestBase(SimpleTestCase):
    def setUp(self):
        self.client_obj = MyDataClient(
            user_id='testuser', subscription_key='testkey', is_sandbox=True
        )
        # Μηδενισμός rate limiting + session mock
        self.client_obj.rate_limiter.wait = lambda: None
        self.client_obj.session = MagicMock()
        # Τα retries να μην κοιμούνται
        patcher = patch('mydata.client.time.sleep', lambda s: None)
        patcher.start()
        self.addCleanup(patcher.stop)


class InitTest(SimpleTestCase):
    def test_base_url_selection(self):
        sandbox = MyDataClient('u', 'k', is_sandbox=True)
        prod = MyDataClient('u', 'k', is_sandbox=False)
        self.assertIn('mydataapidev', sandbox.base_url)
        self.assertIn('mydatapi.aade.gr', prod.base_url)
        self.assertNotEqual(sandbox.base_url, prod.base_url)

    def test_missing_credentials_raise(self):
        with self.assertRaises(ValueError):
            MyDataClient('', 'key')
        with self.assertRaises(ValueError):
            MyDataClient('user', '')

    def test_session_headers(self):
        c = MyDataClient('myuser', 'mykey')
        self.assertEqual(c.session.headers['aade-user-id'], 'myuser')
        self.assertEqual(c.session.headers['Ocp-Apim-Subscription-Key'], 'mykey')


class RaiseForStatusTest(ClientTestBase):
    def _call(self, status_code):
        self.client_obj.session.request.return_value = make_response(
            status_code=status_code, text='error body'
        )
        return self.client_obj._make_request('GET', '/Test')

    def test_400_validation_error(self):
        with self.assertRaises(MyDataValidationError):
            self._call(400)

    def test_401_and_403_auth_error(self):
        for code in (401, 403):
            with self.assertRaises(MyDataAuthError):
                self._call(code)

    def test_429_rate_limit_retried_then_raises(self):
        with self.assertRaises(MyDataRateLimitError):
            self._call(429)
        # retry_with_backoff: 1 αρχική + 4 retries
        self.assertEqual(self.client_obj.session.request.call_count, 5)

    def test_500_server_error_retried_then_raises(self):
        with self.assertRaises(MyDataServerError):
            self._call(500)
        self.assertEqual(self.client_obj.session.request.call_count, 5)

    def test_auth_error_not_retried(self):
        with self.assertRaises(MyDataAuthError):
            self._call(401)
        self.assertEqual(self.client_obj.session.request.call_count, 1)

    def test_unknown_code_generic_error(self):
        with self.assertRaises(MyDataAPIError):
            self._call(302)


class MakeRequestReturnTypesTest(ClientTestBase):
    def test_xml_returns_text(self):
        self.client_obj.session.request.return_value = make_response(
            text='<xml>data</xml>', content_type='application/xml'
        )
        result = self.client_obj._make_request('GET', '/Test')
        self.assertEqual(result, '<xml>data</xml>')

    def test_json_returns_dict(self):
        self.client_obj.session.request.return_value = make_response(
            json_data={'key': 'value'}
        )
        result = self.client_obj._make_request('GET', '/Test')
        self.assertEqual(result, {'key': 'value'})

    def test_empty_body_returns_empty_dict(self):
        self.client_obj.session.request.return_value = make_response(text='')
        result = self.client_obj._make_request('GET', '/Test')
        self.assertEqual(result, {})

    def test_timeout_becomes_server_error(self):
        import requests
        self.client_obj.session.request.side_effect = requests.exceptions.Timeout()
        with self.assertRaises(MyDataServerError):
            self.client_obj._make_request('GET', '/Test')


class SendInvoicesTest(ClientTestBase):
    RESPONSE = (
        '<ResponseDoc><response><index>1</index>'
        '<statusCode>Success</statusCode></response></ResponseDoc>'
    )

    def test_posts_xml_body_with_content_type(self):
        self.client_obj.session.request.return_value = make_response(text=self.RESPONSE)
        xml_doc = '<InvoicesDoc>...</InvoicesDoc>'
        result = self.client_obj.send_invoices(xml_doc)

        self.assertEqual(result, self.RESPONSE)
        call = self.client_obj.session.request.call_args
        self.assertEqual(call.args[0], 'POST')
        self.assertTrue(call.args[1].endswith('/SendInvoices'))
        self.assertEqual(call.kwargs['data'], xml_doc.encode('utf-8'))
        self.assertEqual(call.kwargs['headers']['Content-Type'], 'application/xml')

    def test_send_not_retried_on_server_error(self):
        """Μη-idempotent POST: timeout/5xx ΔΕΝ κάνει retry (διπλή υποβολή)."""
        self.client_obj.session.request.return_value = make_response(
            status_code=500, text='boom'
        )
        with self.assertRaises(MyDataServerError):
            self.client_obj.send_invoices('<InvoicesDoc/>')
        self.assertEqual(self.client_obj.session.request.call_count, 1)

    def test_session_headers_not_mutated(self):
        """Το bug που διορθώθηκε: το send_invoices άλλαζε τα session headers."""
        real_client = MyDataClient('u', 'k', is_sandbox=True)
        real_client.rate_limiter.wait = lambda: None
        headers_before = dict(real_client.session.headers)
        with patch.object(real_client.session, 'request',
                          return_value=make_response(text=self.RESPONSE)):
            real_client.send_invoices('<InvoicesDoc/>')
        self.assertEqual(dict(real_client.session.headers), headers_before)


class CancelInvoiceTest(ClientTestBase):
    def test_cancel_uses_mark_query_param_no_body(self):
        response_xml = (
            '<ResponseDoc><response><index>1</index>'
            '<cancellationMark>400123</cancellationMark>'
            '<statusCode>Success</statusCode></response></ResponseDoc>'
        )
        self.client_obj.session.request.return_value = make_response(text=response_xml)
        result = self.client_obj.cancel_invoice(400001234567890)

        self.assertEqual(result, response_xml)
        call = self.client_obj.session.request.call_args
        self.assertEqual(call.args[0], 'POST')
        self.assertTrue(call.args[1].endswith('/CancelInvoice'))
        self.assertEqual(call.kwargs['params'], {'mark': 400001234567890})
        self.assertNotIn('json', call.kwargs)
        self.assertNotIn('data', call.kwargs)


class VatInfoParseTest(ClientTestBase):
    def test_unparseable_response_raises(self):
        # Μη αναγνώσιμη απάντηση δεν πρέπει να μοιάζει με κενή περίοδο
        from mydata.client import MyDataAPIError
        with self.assertRaises(MyDataAPIError):
            self.client_obj._parse_vat_info_response('<html>Gateway Timeout')

    def test_empty_response_returns_no_records(self):
        records, pagination = self.client_obj._parse_vat_info_response('')
        self.assertEqual(records, [])
        self.assertFalse(pagination.has_more)


VAT_PAGE_1 = """<RequestedVatInfo>
  <continuationToken>
    <nextPartitionKey>P2</nextPartitionKey>
    <nextRowKey>R2</nextRowKey>
  </continuationToken>
  <VatInfo>
    <Mark>900000000000001</Mark>
    <IssueDate>2026-07-10</IssueDate>
    <Vat303>200.00</Vat303>
    <Vat333>48.00</Vat333>
  </VatInfo>
</RequestedVatInfo>"""

VAT_PAGE_2 = """<RequestedVatInfo>
  <VatInfo>
    <Mark>900000000000002</Mark>
    <IssueDate>2026-07-11</IssueDate>
    <Vat361>100.00</Vat361>
    <Vat381>24.00</Vat381>
  </VatInfo>
</RequestedVatInfo>"""


class RequestVatInfoTest(ClientTestBase):
    def test_pagination_and_record_parsing(self):
        from datetime import date
        from decimal import Decimal

        with patch.object(
            self.client_obj, '_make_request',
            side_effect=[VAT_PAGE_1, VAT_PAGE_2],
        ) as mock_request:
            records = list(self.client_obj.request_vat_info(
                date_from=date(2026, 7, 1), date_to=date(2026, 7, 31)
            ))

        self.assertEqual(len(records), 2)
        # Σελίδα 1: εκροές (rec_type=1)
        self.assertEqual(records[0].mark, 900000000000001)
        self.assertEqual(records[0].rec_type, 1)
        self.assertEqual(records[0].net_value, Decimal('200.00'))
        self.assertEqual(records[0].vat_amount, Decimal('48.00'))
        self.assertEqual(records[0].issue_date, date(2026, 7, 10))
        # Σελίδα 2: εισροές (rec_type=2)
        self.assertEqual(records[1].mark, 900000000000002)
        self.assertEqual(records[1].rec_type, 2)
        self.assertEqual(records[1].net_value, Decimal('100.00'))

        # Δύο requests: το δεύτερο με τα pagination keys του πρώτου
        self.assertEqual(mock_request.call_count, 2)
        second_params = mock_request.call_args_list[1].kwargs.get(
            'params'
        ) or mock_request.call_args_list[1][0][2]
        self.assertEqual(second_params.get('nextPartitionKey'), 'P2')
        self.assertEqual(second_params.get('nextRowKey'), 'R2')

    def test_wcf_wrapped_response_is_unwrapped(self):
        wrapped = (
            '<string xmlns="http://schemas.microsoft.com/2003/10/Serialization/">'
            '&lt;RequestedVatInfo&gt;&lt;VatInfo&gt;'
            '&lt;Mark&gt;900000000000003&lt;/Mark&gt;'
            '&lt;IssueDate&gt;2026-07-12&lt;/IssueDate&gt;'
            '&lt;Vat303&gt;10.00&lt;/Vat303&gt;&lt;Vat333&gt;2.40&lt;/Vat333&gt;'
            '&lt;/VatInfo&gt;&lt;/RequestedVatInfo&gt;'
            '</string>'
        )
        records, pagination = self.client_obj._parse_vat_info_response(wrapped)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].mark, 900000000000003)
        self.assertFalse(pagination.has_more)
