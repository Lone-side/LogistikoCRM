# -*- coding: utf-8 -*-
"""
VATPortalService — unit tests (pure, no HTTP)
=============================================
Locks the domain logic that feeds the client portal /me/vat/ endpoint:
output/input split, cancelled exclusion, 2dp quantization, per-client
isolation, and the optional year/period_type filters.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from accounting.models import ClientProfile
from mydata.models import VATRecord, VATPeriodResult
from mydata.services import VATPortalService


def _record(client, mark, rec_type, net, vat, *, cancelled=False, issue=date(2026, 5, 10)):
    return VATRecord.objects.create(
        client=client,
        mark=mark,
        issue_date=issue,
        rec_type=rec_type,
        inv_type='1.1' if rec_type == 1 else 'ΕΙΣΡΟΕΣ_361',
        vat_category=1,
        net_value=Decimal(str(net)),
        vat_amount=Decimal(str(vat)),
        is_cancelled=cancelled,
    )


class VATPortalServiceSummaryTest(TestCase):
    def setUp(self):
        self.a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α', eidos_ipoxreou='company')
        self.b = ClientProfile.objects.create(
            afm='094160855', eponimia='Β', eidos_ipoxreou='company')

    def test_output_input_split(self):
        _record(self.a, 1001, 1, '1000.00', '240.00')   # output
        _record(self.a, 1002, 1, '500.00', '120.00')    # output
        _record(self.a, 1003, 2, '300.00', '72.00')     # input
        s = VATPortalService.get_summary(self.a)
        self.assertEqual(s['output']['net'], Decimal('1500.00'))
        self.assertEqual(s['output']['vat'], Decimal('360.00'))
        self.assertEqual(s['input']['net'], Decimal('300.00'))
        self.assertEqual(s['input']['vat'], Decimal('72.00'))

    def test_cancelled_excluded(self):
        _record(self.a, 1001, 1, '1000.00', '240.00')
        _record(self.a, 1002, 1, '999.00', '239.76', cancelled=True)
        s = VATPortalService.get_summary(self.a)
        self.assertEqual(s['output']['net'], Decimal('1000.00'))
        self.assertEqual(s['output']['vat'], Decimal('240.00'))

    def test_empty_returns_zero_2dp(self):
        s = VATPortalService.get_summary(self.a)
        self.assertEqual(s['output']['net'], Decimal('0.00'))
        self.assertEqual(s['output']['vat'], Decimal('0.00'))
        self.assertEqual(s['input']['net'], Decimal('0.00'))
        self.assertEqual(s['input']['vat'], Decimal('0.00'))

    def test_quantization_is_2dp(self):
        # Integer-ish sum must still come back at 2dp.
        _record(self.a, 1001, 1, '100', '24')
        s = VATPortalService.get_summary(self.a)
        self.assertEqual(str(s['output']['net']), '100.00')
        self.assertEqual(str(s['output']['vat']), '24.00')

    def test_isolation_a_not_counted_for_b(self):
        _record(self.a, 1001, 1, '1000.00', '240.00')
        _record(self.b, 2001, 1, '5000.00', '1200.00')
        s = VATPortalService.get_summary(self.a)
        self.assertEqual(s['output']['net'], Decimal('1000.00'))


class VATPortalServicePeriodsTest(TestCase):
    def setUp(self):
        self.a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α', eidos_ipoxreou='company')
        self.p_2026_5 = VATPeriodResult.objects.create(
            client=self.a, period_type='monthly', year=2026, period=5,
            vat_output=Decimal('360.00'), vat_input=Decimal('72.00'),
            vat_difference=Decimal('288.00'), final_result=Decimal('288.00'))
        self.p_2025_12 = VATPeriodResult.objects.create(
            client=self.a, period_type='monthly', year=2025, period=12,
            final_result=Decimal('100.00'))
        self.p_q = VATPeriodResult.objects.create(
            client=self.a, period_type='quarterly', year=2026, period=2,
            final_result=Decimal('50.00'))

    def test_default_ordered_desc(self):
        result = list(VATPortalService.get_periods(self.a))
        self.assertEqual(result[0], self.p_2026_5)  # newest year+period first

    def test_filter_by_year(self):
        result = list(VATPortalService.get_periods(self.a, year=2025))
        self.assertEqual(result, [self.p_2025_12])

    def test_filter_by_period_type(self):
        result = list(VATPortalService.get_periods(self.a, period_type='quarterly'))
        self.assertEqual(result, [self.p_q])


class VATPortalServiceRecordsTest(TestCase):
    def setUp(self):
        self.a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α', eidos_ipoxreou='company')

    def test_limit_and_truncation(self):
        for i in range(60):
            _record(self.a, 1000 + i, 1, '10.00', '2.40', issue=date(2026, 5, 1))
        result = VATPortalService.get_recent_records(self.a, limit=50)
        self.assertEqual(len(list(result)), 50)

    def test_cancelled_excluded(self):
        _record(self.a, 1001, 1, '10.00', '2.40')
        _record(self.a, 1002, 1, '10.00', '2.40', cancelled=True)
        result = list(VATPortalService.get_recent_records(self.a, limit=50))
        self.assertEqual(len(result), 1)

    def test_filter_by_year(self):
        _record(self.a, 1001, 1, '10.00', '2.40', issue=date(2026, 5, 1))
        _record(self.a, 1002, 1, '10.00', '2.40', issue=date(2025, 5, 1))
        result = list(VATPortalService.get_recent_records(self.a, limit=50, year=2026))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].issue_date.year, 2026)

    def test_ordered_by_issue_date_desc(self):
        old = _record(self.a, 1001, 1, '10.00', '2.40', issue=date(2026, 1, 1))
        new = _record(self.a, 1002, 1, '10.00', '2.40', issue=date(2026, 6, 1))
        result = list(VATPortalService.get_recent_records(self.a, limit=50))
        self.assertEqual(result[0], new)
        self.assertEqual(result[1], old)
