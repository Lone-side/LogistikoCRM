# -*- coding: utf-8 -*-
"""
Tests για τα myDATA API endpoints αποστολής τιμολογίων
(/accounting/api/mydata/invoices/).
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from accounting.models import ClientProfile
from inventory.models import Invoice, InvoiceItem

BASE = '/accounting/api/mydata/invoices/'

SUCCESS_XML = (
    '<ResponseDoc><response><index>1</index>'
    '<invoiceUid>UID-1</invoiceUid>'
    '<invoiceMark>400001234567890</invoiceMark>'
    '<statusCode>Success</statusCode></response></ResponseDoc>'
)


@override_settings(
    MYDATA_USER_ID='office_user',
    MYDATA_SUBSCRIPTION_KEY='office_key',
    MYDATA_IS_SANDBOX=True,
    MYDATA_ISSUER_VAT='999863881',
)
class InvoiceAPITest(TestCase):
    def setUp(self):
        # Send/cancel απαιτούν staff (υποβολή φορολογικών παραστατικών)
        self.user = User.objects.create_user(
            'staff1', 's@test.com', 'pass12345', is_staff=True
        )
        # Το send/cancel απαιτεί πλέον και το model permission του Invoice
        from django.contrib.auth.models import Permission
        self.user.user_permissions.add(
            Permission.objects.get(codename='change_invoice',
                                   content_type__app_label='inventory'),
            Permission.objects.get(codename='view_invoice',
                                   content_type__app_label='inventory'),
        )
        self.user = User.objects.get(pk=self.user.pk)
        self.client.force_login(self.user)

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
            description='Υπηρεσίες', quantity=Decimal('1'), unit='SRV',
            unit_price=Decimal('100.00'), net_value=Decimal('100.00'),
            vat_category=1, vat_amount=Decimal('24.00'),
        )
        # Εισερχόμενο — δεν εμφανίζεται στο default φίλτρο
        Invoice.objects.create(
            series='Β', number='55', invoice_type='1.1',
            issue_date=date(2026, 7, 1),
            counterpart=self.client_profile,
            counterpart_vat='123456783',
            counterpart_name='ΠΕΛΑΤΗΣ ΑΕ',
            is_outgoing=False,
        )

    def test_requires_authentication(self):
        self.client.logout()
        resp = self.client.get(BASE)
        self.assertIn(resp.status_code, (401, 403))

    def test_list_defaults_to_outgoing(self):
        resp = self.client.get(BASE)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        results = data['results'] if isinstance(data, dict) else data
        self.assertEqual(len(results), 1)
        inv = results[0]
        self.assertEqual(inv['series'], 'Α')
        self.assertFalse(inv['mydata_sent'])
        self.assertEqual(len(inv['items']), 1)
        self.assertEqual(inv['invoice_type_display'], 'Τιμολόγιο Παροχής Υπηρεσιών')

    def test_list_filter_unsent(self):
        Invoice.objects.filter(pk=self.invoice.pk).update(
            mydata_sent=True, mydata_mark=400000000000001
        )
        unsent = Invoice.objects.create(
            series='Α', number='102', invoice_type='2.1',
            issue_date=date(2026, 7, 31),
            counterpart=self.client_profile,
            counterpart_vat='123456783',
            counterpart_name='ΠΕΛΑΤΗΣ ΑΕ',
            is_outgoing=True,
        )
        resp = self.client.get(BASE, {'mydata_sent': 'false'})
        data = resp.json()
        results = data['results'] if isinstance(data, dict) else data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], unsent.pk)
        self.assertFalse(results[0]['mydata_sent'])

        resp = self.client.get(BASE, {'mydata_sent': 'true'})
        data = resp.json()
        results = data['results'] if isinstance(data, dict) else data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], self.invoice.pk)

    def test_send_requires_staff(self):
        from django.contrib.auth.models import Permission
        plain = User.objects.create_user('plain', 'p@test.com', 'pass12345')
        plain.user_permissions.add(
            Permission.objects.get(codename='view_invoice',
                                   content_type__app_label='inventory')
        )
        plain = User.objects.get(pk=plain.pk)
        self.client.force_login(plain)
        with patch('mydata.services.MyDataClient'):
            resp = self.client.post(f'{BASE}{self.invoice.pk}/send/')
        self.assertEqual(resp.status_code, 403)
        # Το list παραμένει διαθέσιμο σε χρήστες με view_invoice
        resp = self.client.get(BASE)
        self.assertEqual(resp.status_code, 200)

    def test_aade_rejection_returns_422(self):
        error_xml = (
            '<ResponseDoc><response><index>1</index>'
            '<statusCode>ValidationError</statusCode>'
            '<errors><error><message>Λάθος ΑΦΜ</message><code>101</code></error></errors>'
            '</response></ResponseDoc>'
        )
        with patch('mydata.services.MyDataClient') as MockClient:
            MockClient.return_value.send_invoices.return_value = error_xml
            resp = self.client.post(f'{BASE}{self.invoice.pk}/send/')
        self.assertEqual(resp.status_code, 422)
        self.assertIn('Λάθος ΑΦΜ', resp.json()['error'])

    def test_send_endpoint_success(self):
        with patch('mydata.services.MyDataClient') as MockClient:
            MockClient.return_value.send_invoices.return_value = SUCCESS_XML
            resp = self.client.post(f'{BASE}{self.invoice.pk}/send/')

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['mark'], 400001234567890)
        self.assertTrue(data['invoice']['mydata_sent'])

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.mydata_mark, 400001234567890)

    def test_send_already_sent_returns_400(self):
        Invoice.objects.filter(pk=self.invoice.pk).update(
            mydata_sent=True, mydata_mark=400000000000001
        )
        with patch('mydata.services.MyDataClient'):
            resp = self.client.post(f'{BASE}{self.invoice.pk}/send/')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ήδη', resp.json()['error'])

    def test_send_aade_error_returns_502(self):
        from mydata.client import MyDataServerError
        with patch('mydata.services.MyDataClient') as MockClient:
            MockClient.return_value.send_invoices.side_effect = (
                MyDataServerError('AADE down')
            )
            resp = self.client.post(f'{BASE}{self.invoice.pk}/send/')
        self.assertEqual(resp.status_code, 502)

    def test_cancel_endpoint(self):
        Invoice.objects.filter(pk=self.invoice.pk).update(
            mydata_sent=True, mydata_mark=400000000000001
        )
        cancel_xml = (
            '<ResponseDoc><response><index>1</index>'
            '<cancellationMark>400009999999999</cancellationMark>'
            '<statusCode>Success</statusCode></response></ResponseDoc>'
        )
        with patch('mydata.services.MyDataClient') as MockClient:
            MockClient.return_value.cancel_invoice.return_value = cancel_xml
            resp = self.client.post(f'{BASE}{self.invoice.pk}/cancel/')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['cancellation_mark'], 400009999999999)

    def test_cancel_unsent_returns_400(self):
        with patch('mydata.services.MyDataClient'):
            resp = self.client.post(f'{BASE}{self.invoice.pk}/cancel/')
        self.assertEqual(resp.status_code, 400)
