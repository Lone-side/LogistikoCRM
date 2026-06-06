# -*- coding: utf-8 -*-
"""
MyDataDashboardView — characterization + query-count regression
================================================================
Το dashboard έχτιζε per-client summaries μέσα σε loop (4 aggregate queries ανά
πελάτη → ~4N). Αυτά τα tests κλειδώνουν το ΑΚΡΙΒΕΣ output contract και ότι το
endpoint δεν κάνει N+1 (σταθερό πλήθος queries ανεξαρτήτως πλήθους πελατών),
ώστε ο refactor σε grouped aggregation να παραμείνει ισοδύναμος.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection

from accounting.models import ClientProfile
from mydata.models import MyDataCredentials, VATRecord

URL = '/accounting/api/mydata/dashboard/?year=2026&month=5'


class DashboardCharacterizationTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username='staff', password='x', is_staff=True, is_superuser=True
        )
        cls.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Πελάτης Α', eidos_ipoxreou='company'
        )
        cls.client_b = ClientProfile.objects.create(
            afm='094160855', eponimia='Πελάτης Β', eidos_ipoxreou='company'
        )
        MyDataCredentials.objects.create(client=cls.client_a)
        MyDataCredentials.objects.create(client=cls.client_b)

        # client_a: ένα income (cat 1) + ένα expense (cat 2)· client_b: τίποτα.
        VATRecord.objects.create(
            client=cls.client_a, mark=1, is_cancelled=False,
            issue_date=date(2026, 5, 10), rec_type=1, inv_type='1.1',
            vat_category=1, net_value=Decimal('100.00'), vat_amount=Decimal('24.00'),
        )
        VATRecord.objects.create(
            client=cls.client_a, mark=2, is_cancelled=False,
            issue_date=date(2026, 5, 12), rec_type=1, inv_type='1.1',
            vat_category=1, net_value=Decimal('50.00'), vat_amount=Decimal('12.00'),
        )
        VATRecord.objects.create(
            client=cls.client_a, mark=3, is_cancelled=False,
            issue_date=date(2026, 5, 15), rec_type=2, inv_type='13.1',
            vat_category=2, net_value=Decimal('40.00'), vat_amount=Decimal('5.20'),
        )
        # Ακυρωμένο + εκτός περιόδου: ΔΕΝ πρέπει να μετρηθούν.
        VATRecord.objects.create(
            client=cls.client_a, mark=4, is_cancelled=True,
            issue_date=date(2026, 5, 20), rec_type=1, inv_type='1.1',
            vat_category=1, net_value=Decimal('999.00'), vat_amount=Decimal('999.00'),
        )
        VATRecord.objects.create(
            client=cls.client_a, mark=5, is_cancelled=False,
            issue_date=date(2026, 4, 30), rec_type=1, inv_type='1.1',
            vat_category=1, net_value=Decimal('777.00'), vat_amount=Decimal('777.00'),
        )

    def _get(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.get(URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content[:300])
        return resp.data

    def _client_entry(self, data, afm):
        return next(c for c in data['clients'] if c['client_afm'] == afm)

    def test_overview_totals(self):
        d = self._get()
        ov = d['overview']
        # income: 100+50 net, 24+12 vat (ακυρωμένο & Απρίλιος εξαιρούνται)
        self.assertEqual(ov['total_income_net'], Decimal('150.00'))
        self.assertEqual(ov['total_income_vat'], Decimal('36.00'))
        self.assertEqual(ov['total_expense_net'], Decimal('40.00'))
        self.assertEqual(ov['total_expense_vat'], Decimal('5.20'))
        self.assertEqual(ov['total_clients'], 2)
        self.assertEqual(ov['clients_with_credentials'], 2)

    def test_per_client_summary_and_breakdown(self):
        d = self._get()
        a = self._client_entry(d, '123456783')
        s = a['current_period']
        self.assertEqual(s['income_net'], Decimal('150.00'))
        self.assertEqual(s['income_vat'], Decimal('36.00'))
        self.assertEqual(s['income_gross'], Decimal('186.00'))
        self.assertEqual(s['income_count'], 2)
        self.assertEqual(s['expense_net'], Decimal('40.00'))
        self.assertEqual(s['expense_vat'], Decimal('5.20'))
        self.assertEqual(s['expense_gross'], Decimal('45.20'))
        self.assertEqual(s['expense_count'], 1)
        self.assertEqual(s['net_difference'], Decimal('110.00'))
        self.assertEqual(s['vat_difference'], Decimal('30.80'))

        # income breakdown: μία κατηγορία (1), net 150 vat 36 count 2
        inc = a['income_by_category']
        self.assertEqual(len(inc), 1)
        self.assertEqual(inc[0]['vat_category'], 1)
        self.assertEqual(inc[0]['vat_rate'], 24)
        self.assertEqual(inc[0]['net_value'], Decimal('150.00'))
        self.assertEqual(inc[0]['vat_amount'], Decimal('36.00'))
        self.assertEqual(inc[0]['count'], 2)

        exp = a['expense_by_category']
        self.assertEqual(len(exp), 1)
        self.assertEqual(exp[0]['vat_category'], 2)
        self.assertEqual(exp[0]['net_value'], Decimal('40.00'))
        self.assertEqual(exp[0]['count'], 1)

    def test_client_with_no_records_has_zero_summary(self):
        d = self._get()
        b = self._client_entry(d, '094160855')
        s = b['current_period']
        self.assertEqual(s['income_net'], Decimal('0.00'))
        self.assertEqual(s['income_vat'], Decimal('0.00'))
        self.assertEqual(s['income_count'], 0)
        self.assertEqual(s['expense_count'], 0)
        self.assertEqual(b['income_by_category'], [])
        self.assertEqual(b['expense_by_category'], [])

    def test_dashboard_query_count_does_not_grow_per_client(self):
        # Προσθέτω 3 ακόμη πελάτες με credentials + από 1 record. Το πλήθος
        # queries πρέπει να μείνει ίδιο με/χωρίς αυτούς (όχι N+1).
        self.client.force_authenticate(user=self.staff)

        def count_queries():
            with CaptureQueriesContext(connection) as ctx:
                resp = self.client.get(URL)
                self.assertEqual(resp.status_code, 200)
            return len(ctx)

        baseline = count_queries()

        for i, afm in enumerate(['111111114', '222222225', '333333336']):
            c = ClientProfile.objects.create(
                afm=afm, eponimia=f'Extra {i}', eidos_ipoxreou='company'
            )
            MyDataCredentials.objects.create(client=c)
            VATRecord.objects.create(
                client=c, mark=100 + i, is_cancelled=False,
                issue_date=date(2026, 5, 5), rec_type=1, inv_type='1.1',
                vat_category=1, net_value=Decimal('10.00'), vat_amount=Decimal('2.40'),
            )

        after = count_queries()
        self.assertEqual(
            baseline, after,
            f'Query count grew with #clients ({baseline} -> {after}) — N+1 regression',
        )
