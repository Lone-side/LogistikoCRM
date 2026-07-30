# -*- coding: utf-8 -*-
"""
Tests για το MyDataService.submit_invoice / cancel_invoice —
το μονοπάτι αποστολής τιμολογίων στο myDATA (με mocked client).
"""
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from django.test import TestCase, override_settings

from accounting.models import ClientProfile
from inventory.models import Invoice, InvoiceItem, MyDataSyncLog
from mydata.client import MyDataValidationError
from mydata.services import MyDataService

SUCCESS_XML = (
    '<ResponseDoc><response><index>1</index>'
    '<invoiceUid>UID-1</invoiceUid>'
    '<invoiceMark>400001234567890</invoiceMark>'
    '<statusCode>Success</statusCode></response></ResponseDoc>'
)
ERROR_XML = (
    '<ResponseDoc><response><index>1</index>'
    '<statusCode>ValidationError</statusCode>'
    '<errors><error><message>Λάθος ΑΦΜ</message><code>101</code></error></errors>'
    '</response></ResponseDoc>'
)
CANCEL_XML = (
    '<ResponseDoc><response><index>1</index>'
    '<cancellationMark>400009999999999</cancellationMark>'
    '<statusCode>Success</statusCode></response></ResponseDoc>'
)


@override_settings(
    MYDATA_USER_ID='office_user',
    MYDATA_SUBSCRIPTION_KEY='office_key',
    MYDATA_IS_SANDBOX=True,
    MYDATA_ISSUER_VAT='999863881',
)
class SubmitInvoiceTest(TestCase):
    def setUp(self):
        self.client_profile = ClientProfile.objects.create(
            afm='123456783', eponimia='ΠΕΛΑΤΗΣ ΑΕ', eidos_ipoxreou='company'
        )
        self.invoice = Invoice.objects.create(
            series='Α', number='101', invoice_type='2.1',
            issue_date=date(2026, 7, 30),
            counterpart=self.client_profile,
            counterpart_vat='123456783',
            counterpart_name='ΠΕΛΑΤΗΣ ΑΕ',
            is_outgoing=True,
        )
        InvoiceItem.objects.create(
            invoice=self.invoice, line_number=1,
            description='Λογιστικές υπηρεσίες Ιουλίου',
            quantity=Decimal('1'), unit='SRV',
            unit_price=Decimal('100.00'), net_value=Decimal('100.00'),
            vat_category=1, vat_amount=Decimal('24.00'),
        )
        self.service = MyDataService()
        self.service.client = MagicMock()

    def test_success_stores_mark_and_logs(self):
        self.service.client.send_invoices.return_value = SUCCESS_XML

        result = self.service.submit_invoice(self.invoice)

        self.assertTrue(result['success'])
        self.assertEqual(result['mark'], 400001234567890)

        self.invoice.refresh_from_db()
        self.assertTrue(self.invoice.mydata_sent)
        self.assertEqual(self.invoice.mydata_mark, 400001234567890)
        self.assertEqual(self.invoice.mydata_uid, 'UID-1')
        self.assertIsNotNone(self.invoice.mydata_sent_at)

        log = MyDataSyncLog.objects.get(sync_type='PUSH_INVOICE')
        self.assertEqual(log.status, 'SUCCESS')
        self.assertIsNotNone(log.completed_at)

        # Το XML που στάλθηκε περιέχει τον σωστό εκδότη και αντισυμβαλλόμενο
        sent_xml = self.service.client.send_invoices.call_args.args[0]
        self.assertIn('<vatNumber>999863881</vatNumber>', sent_xml)
        self.assertIn('<vatNumber>123456783</vatNumber>', sent_xml)
        self.assertIn('<invoiceType>2.1</invoiceType>', sent_xml)

    def test_aade_rejection_raises_and_logs_error(self):
        self.service.client.send_invoices.return_value = ERROR_XML

        with self.assertRaises(MyDataValidationError) as ctx:
            self.service.submit_invoice(self.invoice)
        self.assertIn('Λάθος ΑΦΜ', str(ctx.exception))

        self.invoice.refresh_from_db()
        self.assertFalse(self.invoice.mydata_sent)
        self.assertIsNone(self.invoice.mydata_mark)

        log = MyDataSyncLog.objects.filter(sync_type='PUSH_INVOICE').latest('started_at')
        self.assertEqual(log.status, 'ERROR')
        self.assertIn('101', log.error_message)

    def test_already_sent_guard(self):
        self.invoice.mydata_sent = True
        self.invoice.mydata_mark = 400000000000001
        self.invoice.save()

        with self.assertRaises(ValueError):
            self.service.submit_invoice(self.invoice)
        self.service.client.send_invoices.assert_not_called()

    def test_incoming_invoice_guard(self):
        self.invoice.is_outgoing = False
        self.invoice.save()
        with self.assertRaises(ValueError):
            self.service.submit_invoice(self.invoice)

    def test_no_items_guard(self):
        self.invoice.items.all().delete()
        with self.assertRaises(ValueError):
            self.service.submit_invoice(self.invoice)

    @override_settings(MYDATA_ISSUER_VAT='')
    def test_missing_issuer_vat_guard(self):
        with self.assertRaises(ValueError) as ctx:
            self.service.submit_invoice(self.invoice)
        self.assertIn('MYDATA_ISSUER_VAT', str(ctx.exception))
        self.service.client.send_invoices.assert_not_called()

    def test_number_must_be_positive_integer(self):
        self.invoice.number = 'A15'
        self.invoice.save()
        with self.assertRaises(ValueError) as ctx:
            self.service.submit_invoice(self.invoice)
        self.assertIn('θετικός', str(ctx.exception))
        self.service.client.send_invoices.assert_not_called()

    def test_claim_released_after_rejection_allows_retry(self):
        """Μετά από απόρριψη ΑΑΔΕ το claim αποδεσμεύεται — επιτρέπεται retry."""
        self.service.client.send_invoices.return_value = ERROR_XML
        with self.assertRaises(MyDataValidationError):
            self.service.submit_invoice(self.invoice)

        self.invoice.refresh_from_db()
        self.assertFalse(self.invoice.mydata_sent)

        # Δεύτερη προσπάθεια με σωστή απάντηση περνάει
        self.service.client.send_invoices.return_value = SUCCESS_XML
        result = self.service.submit_invoice(self.invoice)
        self.assertTrue(result['success'])

    def test_success_without_mark_treated_as_error(self):
        no_mark = ('<ResponseDoc><response><index>1</index>'
                   '<statusCode>Success</statusCode></response></ResponseDoc>')
        self.service.client.send_invoices.return_value = no_mark
        with self.assertRaises(MyDataValidationError):
            self.service.submit_invoice(self.invoice)
        self.invoice.refresh_from_db()
        self.assertFalse(self.invoice.mydata_sent)

    def test_garbage_response_raises_server_error(self):
        from mydata.client import MyDataServerError
        self.service.client.send_invoices.return_value = 'not xml'
        with self.assertRaises(MyDataServerError):
            self.service.submit_invoice(self.invoice)
        # Το raw response σώζεται στο log για χειροκίνητο έλεγχο
        log = MyDataSyncLog.objects.get(sync_type='PUSH_INVOICE')
        self.assertEqual(log.status, 'ERROR')
        self.assertIn('not xml', str(log.details))

    def test_sent_xml_amounts_match_invoice(self):
        """Τα ποσά στο XML που στέλνεται ταυτίζονται με το τιμολόγιο."""
        import xml.etree.ElementTree as ET
        self.service.client.send_invoices.return_value = SUCCESS_XML
        self.service.submit_invoice(self.invoice)

        sent_xml = self.service.client.send_invoices.call_args.args[0]
        NS = {'m': 'http://www.aade.gr/myDATA/invoice/v1.0'}
        root = ET.fromstring(sent_xml)
        summary = root.find('m:invoice/m:invoiceSummary', NS)
        self.assertEqual(summary.find('m:totalNetValue', NS).text, '100.00')
        self.assertEqual(summary.find('m:totalVatAmount', NS).text, '24.00')
        self.assertEqual(summary.find('m:totalGrossValue', NS).text, '124.00')
        details = root.findall('m:invoice/m:invoiceDetails', NS)
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0].find('m:netValue', NS).text, '100.00')
        self.assertEqual(details[0].find('m:vatCategory', NS).text, '1')

    def test_client_exception_logged_as_error(self):
        from mydata.client import MyDataServerError
        self.service.client.send_invoices.side_effect = MyDataServerError('AADE down')

        with self.assertRaises(MyDataServerError):
            self.service.submit_invoice(self.invoice)

        log = MyDataSyncLog.objects.get(sync_type='PUSH_INVOICE')
        self.assertEqual(log.status, 'ERROR')
        self.assertIn('AADE down', log.error_message)


@override_settings(
    MYDATA_USER_ID='office_user',
    MYDATA_SUBSCRIPTION_KEY='office_key',
    MYDATA_IS_SANDBOX=True,
    MYDATA_ISSUER_VAT='999863881',
)
class CancelInvoiceTest(TestCase):
    def setUp(self):
        self.client_profile = ClientProfile.objects.create(
            afm='123456783', eponimia='ΠΕΛΑΤΗΣ ΑΕ', eidos_ipoxreou='company'
        )
        self.invoice = Invoice.objects.create(
            series='Α', number='101', invoice_type='2.1',
            issue_date=date(2026, 7, 30),
            counterpart=self.client_profile,
            counterpart_vat='123456783',
            counterpart_name='ΠΕΛΑΤΗΣ ΑΕ',
            is_outgoing=True,
            mydata_sent=True,
            mydata_mark=400001234567890,
        )
        self.service = MyDataService()
        self.service.client = MagicMock()

    def test_cancel_success(self):
        self.service.client.cancel_invoice.return_value = CANCEL_XML

        result = self.service.cancel_invoice(self.invoice)

        self.assertTrue(result['success'])
        self.assertEqual(result['cancellation_mark'], 400009999999999)
        self.service.client.cancel_invoice.assert_called_once_with(400001234567890)

        self.invoice.refresh_from_db()
        self.assertIn('400009999999999', self.invoice.notes)

        log = MyDataSyncLog.objects.get(sync_type='CANCEL_INVOICE')
        self.assertEqual(log.status, 'SUCCESS')

    def test_cancel_unsent_invoice_guard(self):
        self.invoice.mydata_sent = False
        self.invoice.mydata_mark = None
        self.invoice.save()

        with self.assertRaises(ValueError):
            self.service.cancel_invoice(self.invoice)
        self.service.client.cancel_invoice.assert_not_called()

    def test_cancel_incoming_guard(self):
        self.invoice.is_outgoing = False
        self.invoice.save()
        with self.assertRaises(ValueError):
            self.service.cancel_invoice(self.invoice)
        self.service.client.cancel_invoice.assert_not_called()

    def test_double_cancel_guard(self):
        self.service.client.cancel_invoice.return_value = CANCEL_XML
        self.service.cancel_invoice(self.invoice)

        self.invoice.refresh_from_db()
        self.assertTrue(self.invoice.mydata_cancelled)
        self.assertEqual(self.invoice.mydata_cancellation_mark, 400009999999999)
        self.assertIsNotNone(self.invoice.mydata_cancelled_at)

        with self.assertRaises(ValueError) as ctx:
            self.service.cancel_invoice(self.invoice)
        self.assertIn('ήδη ακυρωμένο', str(ctx.exception))
        self.assertEqual(self.service.client.cancel_invoice.call_count, 1)

    def test_cancel_rejection_logs_error(self):
        self.service.client.cancel_invoice.return_value = ERROR_XML

        with self.assertRaises(MyDataValidationError):
            self.service.cancel_invoice(self.invoice)

        log = MyDataSyncLog.objects.get(sync_type='CANCEL_INVOICE')
        self.assertEqual(log.status, 'ERROR')


@override_settings(
    MYDATA_USER_ID='office_user',
    MYDATA_SUBSCRIPTION_KEY='office_key',
    MYDATA_IS_SANDBOX=True,
)
class ProcessInvoiceMarkGuardTest(TestCase):
    """Τιμολόγιο από myDATA χωρίς MARK δεν πρέπει να αποθηκεύεται."""

    def test_missing_mark_raises_and_creates_nothing(self):
        service = MyDataService()
        service.client = MagicMock()

        for bad in ({}, {'mark': ''}, {'mark': None}):
            with self.assertRaises(ValueError):
                service._process_invoice(
                    {**bad, 'series': 'Α', 'aa': '1'}, is_outgoing=False
                )
        self.assertEqual(Invoice.objects.count(), 0)
