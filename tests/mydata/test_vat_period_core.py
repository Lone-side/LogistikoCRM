# -*- coding: utf-8 -*-
"""
VATPeriodResult core-logic hardening
====================================
- set_credit API rejects negative previous_credit (400) and recalculates
  atomically on the happy path.
- VATPeriodResult.full_clean() rejects negative previous_credit (model guard).
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status

from datetime import date

from accounting.models import ClientProfile
from mydata.models import VATPeriodResult, VATRecord
from mydata.views import VATPeriodResultViewSet


class SetCreditApiTest(TestCase):
    """
    Uses APIRequestFactory (not the Django test client) to avoid the
    Python 3.14 + Django test-client HTML-error-render incompatibility on
    non-2xx responses. We exercise the real view + permissions.
    """

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = VATPeriodResultViewSet.as_view({'post': 'set_credit'})
        self.staff = User.objects.create_user(
            username='staff', password='x', is_staff=True)
        self.client_p = ClientProfile.objects.create(
            afm='123456783', eponimia='Α', eidos_ipoxreou='company')
        # Real records in May 2026: output VAT 100, input VAT 40 → difference 60.
        # set_credit recalculates from records, so these drive the result.
        VATRecord.objects.create(
            client=self.client_p, mark=1, issue_date=date(2026, 5, 5), rec_type=1,
            inv_type='1.1', vat_category=1,
            net_value=Decimal('416.67'), vat_amount=Decimal('100.00'))
        VATRecord.objects.create(
            client=self.client_p, mark=2, issue_date=date(2026, 5, 6), rec_type=2,
            inv_type='ΕΙΣΡΟΕΣ_361', vat_category=1,
            net_value=Decimal('166.67'), vat_amount=Decimal('40.00'))
        self.period = VATPeriodResult.objects.create(
            client=self.client_p, period_type='monthly', year=2026, period=5,
            vat_output=Decimal('100.00'), vat_input=Decimal('40.00'),
            vat_difference=Decimal('60.00'), final_result=Decimal('60.00'))

    def _post(self, body):
        req = self.factory.post(
            f'/api/mydata/periods/{self.period.id}/set_credit/', body, format='json')
        force_authenticate(req, user=self.staff)
        return self.view(req, pk=self.period.id)

    def test_negative_credit_rejected(self):
        resp = self._post({'previous_credit': '-50.00'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.period.refresh_from_db()
        self.assertEqual(self.period.previous_credit, Decimal('0.00'))  # unchanged

    def test_positive_credit_recalculates(self):
        resp = self._post({'previous_credit': '20.00'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.period.refresh_from_db()
        self.assertEqual(self.period.previous_credit, Decimal('20.00'))
        # final_result recalculated: vat_difference(60) - previous_credit(20) = 40
        self.assertEqual(self.period.final_result, Decimal('40.00'))


class PeriodCleanTest(TestCase):
    def setUp(self):
        self.client_p = ClientProfile.objects.create(
            afm='123456783', eponimia='Α', eidos_ipoxreou='company')

    def test_full_clean_rejects_negative_credit(self):
        period = VATPeriodResult(
            client=self.client_p, period_type='monthly', year=2026, period=5,
            previous_credit=Decimal('-10.00'))
        with self.assertRaises(ValidationError):
            period.full_clean()

    def test_full_clean_allows_zero_and_positive(self):
        for val in (Decimal('0.00'), Decimal('100.00')):
            period = VATPeriodResult(
                client=self.client_p, period_type='monthly', year=2026, period=6,
                previous_credit=val)
            # Should not raise on previous_credit (other fields have defaults).
            try:
                period.full_clean()
            except ValidationError as e:
                self.assertNotIn('previous_credit', e.message_dict)
