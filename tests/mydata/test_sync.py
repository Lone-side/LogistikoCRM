# -*- coding: utf-8 -*-
"""
Tests για τα sync μονοπάτια του myDATA:
- MyDataService.sync_received_invoices / sync_transmitted_invoices
- Management command mydata_sync_vat (fetch-first + ατομική αντικατάσταση)
"""
from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from accounting.models import ClientProfile
from inventory.models import Invoice, MyDataSyncLog
from mydata.client import MyDataAPIError, VatInfoRecord
from mydata.models import MyDataCredentials, VATRecord, VATSyncLog
from mydata.services import MyDataService


def make_inv_data(mark='400001111111111', aa='7', **overrides):
    data = {
        'mark': mark,
        'uid': 'UID-7',
        'series': 'Α',
        'aa': aa,
        'invoice_type': '2.1',
        'issue_date': '2026-07-15',
        'issuer_vat': '999863881',
        'counterpart_vat': '123456783',
        'total_net': '100.00',
        'total_vat': '24.00',
        'total_gross': '124.00',
        'details': [
            {'itemDescr': 'Υπηρεσίες', 'quantity': 1, 'netValue': 100.0,
             'vatCategory': 1, 'vatAmount': 24.0},
        ],
    }
    data.update(overrides)
    return data


@override_settings(
    MYDATA_USER_ID='office_user',
    MYDATA_SUBSCRIPTION_KEY='office_key',
    MYDATA_IS_SANDBOX=True,
)
class SyncInvoicesTest(TestCase):
    def setUp(self):
        self.client_profile = ClientProfile.objects.create(
            afm='123456783', eponimia='ΠΕΛΑΤΗΣ ΑΕ'
        )
        # Ο εκδότης των εισερχόμενων: το Invoice.counterpart είναι NOT NULL,
        # οπότε πρέπει να υπάρχει ως ClientProfile
        self.supplier_profile = ClientProfile.objects.create(
            afm='999863881', eponimia='ΠΡΟΜΗΘΕΥΤΗΣ ΑΕ'
        )
        self.service = MyDataService()
        self.service.client = MagicMock()

    def _run_received(self, invoices):
        self.service.client.request_docs.return_value = '<xml/>'
        self.service.client.parse_invoice_response.return_value = invoices
        return self.service.sync_received_invoices(days_back=7)

    def test_creates_invoice_with_items_and_logs_success(self):
        created, updated, errors = self._run_received([make_inv_data()])

        self.assertEqual((created, updated, errors), (1, 0, []))
        invoice = Invoice.objects.get(mydata_mark='400001111111111')
        self.assertFalse(invoice.is_outgoing)
        # Στα εισερχόμενα ο αντισυμβαλλόμενος είναι ο εκδότης (προμηθευτής)
        self.assertEqual(invoice.counterpart, self.supplier_profile)
        self.assertEqual(invoice.total_gross, Decimal('124.00'))
        self.assertEqual(invoice.items.count(), 1)

        log = MyDataSyncLog.objects.get(sync_type='PULL_RECEIVED')
        self.assertEqual(log.status, 'SUCCESS')
        self.assertEqual(log.records_created, 1)

    def test_existing_mark_updates_instead_of_duplicating(self):
        self._run_received([make_inv_data()])
        created, updated, errors = self._run_received(
            [make_inv_data(total_net='150.00', total_vat='36.00',
                           total_gross='186.00')]
        )

        self.assertEqual((created, updated, errors), (0, 1, []))
        self.assertEqual(
            Invoice.objects.filter(mydata_mark='400001111111111').count(), 1
        )
        invoice = Invoice.objects.get(mydata_mark='400001111111111')
        self.assertEqual(invoice.total_gross, Decimal('186.00'))

    def test_missing_mark_counted_as_error_and_nothing_saved(self):
        created, updated, errors = self._run_received([make_inv_data(mark='')])

        self.assertEqual((created, updated), (0, 0))
        self.assertEqual(len(errors), 1)
        self.assertEqual(Invoice.objects.count(), 0)
        log = MyDataSyncLog.objects.get(sync_type='PULL_RECEIVED')
        self.assertEqual(log.status, 'ERROR')
        self.assertEqual(log.records_failed, 1)

    def test_api_failure_marks_log_error_and_raises(self):
        self.service.client.request_docs.side_effect = MyDataAPIError('boom')

        with self.assertRaises(MyDataAPIError):
            self.service.sync_received_invoices(days_back=7)

        log = MyDataSyncLog.objects.get(sync_type='PULL_RECEIVED')
        self.assertEqual(log.status, 'ERROR')
        self.assertIn('boom', log.error_message)

    def test_transmitted_creates_outgoing_invoice(self):
        self.service.client.request_transmitted_docs.return_value = '<xml/>'
        self.service.client.parse_invoice_response.return_value = [
            make_inv_data(mark='400002222222222')
        ]

        created, updated, errors = self.service.sync_transmitted_invoices(7)

        self.assertEqual((created, updated, errors), (1, 0, []))
        invoice = Invoice.objects.get(mydata_mark='400002222222222')
        self.assertTrue(invoice.is_outgoing)
        log = MyDataSyncLog.objects.get(sync_type='PULL_TRANSMITTED')
        self.assertEqual(log.status, 'SUCCESS')


def make_vat_record(mark=900000000000001, **overrides):
    kwargs = dict(
        mark=mark,
        is_cancelled=False,
        issue_date=date(2026, 7, 10),
        rec_type=1,
        inv_type='ΕΚΡΟΕΣ',
        vat_category=1,
        vat_exemption_category='',
        net_value=Decimal('200.00'),
        vat_amount=Decimal('48.00'),
        counter_vat_number='',
        vat_offset_amount=None,
        deductions_amount=None,
    )
    kwargs.update(overrides)
    return VatInfoRecord(**kwargs)


class SyncVatCommandTest(TestCase):
    def setUp(self):
        self.client_profile = ClientProfile.objects.create(
            afm='123456783', eponimia='ΠΕΛΑΤΗΣ ΑΕ'
        )
        self.credentials = MyDataCredentials.objects.create(
            client=self.client_profile, is_active=True, is_sandbox=True
        )
        self.credentials.user_id = 'user'
        self.credentials.subscription_key = 'key'
        self.credentials.save()

        # Υπάρχον record της περιόδου — δεν πρέπει να χαθεί αν το API αποτύχει
        self.old_record = VATRecord.objects.create(
            client=self.client_profile,
            mark=900000000000000,
            issue_date=date(2026, 7, 5),
            rec_type=1,
            inv_type='ΕΚΡΟΕΣ',
            vat_category=1,
            net_value=Decimal('50.00'),
            vat_amount=Decimal('12.00'),
        )

    def _call(self, api_client):
        out = StringIO()
        with patch.object(
            MyDataCredentials, 'get_api_client', return_value=api_client
        ):
            call_command(
                'mydata_sync_vat', '--client=123456783',
                '--year=2026', '--month=7',
                stdout=out,
            )
        return out.getvalue()

    def test_api_failure_preserves_existing_records(self):
        api_client = MagicMock()
        api_client.request_vat_info.side_effect = MyDataAPIError('AADE down')

        self._call(api_client)

        # Το παλιό record της περιόδου επιβίωσε — δεν διαγράφτηκε πριν το fetch
        self.assertTrue(VATRecord.objects.filter(pk=self.old_record.pk).exists())
        log = VATSyncLog.objects.get(client=self.client_profile)
        self.assertEqual(log.status, 'ERROR')

    def test_successful_sync_replaces_period_records(self):
        api_client = MagicMock()
        api_client.request_vat_info.return_value = iter(
            [make_vat_record(), make_vat_record(mark=900000000000002, rec_type=2,
                                                inv_type='ΕΙΣΡΟΕΣ')]
        )

        self._call(api_client)

        marks = set(
            VATRecord.objects.filter(client=self.client_profile)
            .values_list('mark', flat=True)
        )
        self.assertEqual(marks, {900000000000001, 900000000000002})
        log = VATSyncLog.objects.get(client=self.client_profile)
        self.assertEqual(log.status, 'SUCCESS')
        self.assertEqual(log.records_created, 2)
