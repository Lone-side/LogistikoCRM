# -*- coding: utf-8 -*-
"""
Regression tests: άκυρα query params στα myDATA endpoints πρέπει να
επιστρέφουν HTTP 400 (όχι 500 με ValueError/AssertionError).

Σύμβαση υλοποίησης: το helper _parse_int (mydata/views.py) σηκώνει
rest_framework ValidationError → 400 για μη-αριθμητικές ή εκτός ορίων
τιμές. Εξαίρεση: το ?months του trend γίνεται clamp στο 1..36 (200 για
εκτός ορίων αριθμούς, 400 μόνο για μη-αριθμητικά).
"""
from django.contrib.auth.models import User
from django.test import TestCase

from accounting.models import ClientProfile

BASE = '/accounting/api/mydata/'


class InvalidInputTestCase(TestCase):
    def setUp(self):
        from django.contrib.auth.models import Permission
        from tests.utils.helpers import grant_mydata_model_perms
        self.user = grant_mydata_model_perms(
            User.objects.create_user('tester', 't@test.com', 'pass12345')
        )
        # Το dashboard/detail επιστρέφει client metadata → απαιτεί πλέον
        # και accounting.view_clientprofile (γύρος 14)
        self.user.user_permissions.add(Permission.objects.get(
            codename='view_clientprofile',
            content_type__app_label='accounting'))
        self.user = User.objects.get(pk=self.user.pk)
        self.client.force_login(self.user)
        self.profile = ClientProfile.objects.create(
            afm='123456783', eponimia='ΠΕΛΑΤΗΣ ΑΕ', eidos_ipoxreou='company'
        )
        self.profile.assigned_users.add(self.user)

    # ---- VATRecordViewSet list filters ----

    def test_records_invalid_int_filters_return_400(self):
        for param in ('year', 'month', 'rec_type', 'vat_category'):
            resp = self.client.get(f'{BASE}records/', {param: 'abc'})
            self.assertEqual(resp.status_code, 400, param)

    def test_records_month_out_of_range_returns_400(self):
        resp = self.client.get(f'{BASE}records/', {'month': '13'})
        self.assertEqual(resp.status_code, 400)

    def test_records_valid_filters_return_200(self):
        resp = self.client.get(f'{BASE}records/', {'year': '2026', 'month': '7'})
        self.assertEqual(resp.status_code, 200)

    # ---- summary / by_category actions ----

    def test_summary_invalid_year_returns_400(self):
        resp = self.client.get(
            f'{BASE}records/summary/', {'afm': self.profile.afm, 'year': 'abc'}
        )
        self.assertEqual(resp.status_code, 400)

    def test_summary_month_out_of_range_returns_400(self):
        resp = self.client.get(
            f'{BASE}records/summary/', {'afm': self.profile.afm, 'month': '0'}
        )
        self.assertEqual(resp.status_code, 400)

    def test_by_category_invalid_params_return_400(self):
        for params in ({'year': 'abc'}, {'month': 'abc'}, {'rec_type': 'abc'}):
            resp = self.client.get(
                f'{BASE}records/by_category/', {'afm': self.profile.afm, **params}
            )
            self.assertEqual(resp.status_code, 400, params)

    # ---- VATSyncLogViewSet ----

    def test_logs_invalid_limit_returns_400(self):
        resp = self.client.get(f'{BASE}logs/', {'limit': 'abc'})
        self.assertEqual(resp.status_code, 400)

    def test_logs_negative_limit_returns_400(self):
        resp = self.client.get(f'{BASE}logs/', {'limit': '-1'})
        self.assertEqual(resp.status_code, 400)

    def test_logs_default_limit_ok(self):
        resp = self.client.get(f'{BASE}logs/')
        self.assertEqual(resp.status_code, 200)

    # ---- Dashboard ----

    def test_dashboard_invalid_year_month_return_400(self):
        for params in ({'year': 'abc'}, {'month': 'abc'}, {'month': '13'}):
            resp = self.client.get(f'{BASE}dashboard/', params)
            self.assertEqual(resp.status_code, 400, params)

    # ---- ClientVATDetailView ----

    def test_client_detail_invalid_year_returns_400(self):
        resp = self.client.get(
            f'{BASE}client/{self.profile.afm}/', {'year': 'abc'}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn('traceback', resp.json())

    def test_client_detail_month_out_of_range_returns_400(self):
        resp = self.client.get(
            f'{BASE}client/{self.profile.afm}/', {'month': '13'}
        )
        self.assertEqual(resp.status_code, 400)

    def test_client_detail_quarter_out_of_range_returns_400(self):
        resp = self.client.get(
            f'{BASE}client/{self.profile.afm}/',
            {'period_type': 'quarter', 'quarter': '9'},
        )
        self.assertEqual(resp.status_code, 400)

    def test_client_detail_invalid_period_type_returns_400(self):
        resp = self.client.get(
            f'{BASE}client/{self.profile.afm}/', {'period_type': 'bogus'}
        )
        self.assertEqual(resp.status_code, 400)

    def test_client_detail_valid_returns_200(self):
        resp = self.client.get(f'{BASE}client/{self.profile.afm}/')
        self.assertEqual(resp.status_code, 200)

    # ---- MonthlyTrendView ----

    def test_trend_invalid_months_returns_400(self):
        resp = self.client.get(f'{BASE}trend/', {'months': 'abc'})
        self.assertEqual(resp.status_code, 400)

    def test_trend_months_clamped(self):
        # Εκτός ορίων αριθμοί γίνονται clamp στο 1..36 → 200
        resp = self.client.get(f'{BASE}trend/', {'months': '999'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 36)
        resp = self.client.get(f'{BASE}trend/', {'months': '-5'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 1)

    # ---- VATPeriodResultViewSet ----

    def test_periods_invalid_year_returns_400(self):
        resp = self.client.get(f'{BASE}periods/', {'year': 'abc'})
        self.assertEqual(resp.status_code, 400)

    # ---- VATPeriodCalculatorView ----

    def test_calculator_invalid_year_returns_400(self):
        resp = self.client.get(
            f'{BASE}calculator/',
            {'afm': self.profile.afm, 'year': 'abc', 'period': '1'},
        )
        self.assertEqual(resp.status_code, 400)

    def test_calculator_invalid_period_returns_400(self):
        resp = self.client.get(
            f'{BASE}calculator/',
            {'afm': self.profile.afm, 'year': '2026', 'period': 'abc'},
        )
        self.assertEqual(resp.status_code, 400)

    def test_calculator_invalid_period_type_returns_400(self):
        resp = self.client.get(
            f'{BASE}calculator/',
            {'afm': self.profile.afm, 'year': '2026', 'period': '1',
             'period_type': 'weekly'},
        )
        self.assertEqual(resp.status_code, 400)

    def test_calculator_monthly_period_out_of_range_returns_400(self):
        resp = self.client.get(
            f'{BASE}calculator/',
            {'afm': self.profile.afm, 'year': '2026', 'period': '13',
             'period_type': 'monthly'},
        )
        self.assertEqual(resp.status_code, 400)

    def test_calculator_quarterly_period_out_of_range_returns_400(self):
        resp = self.client.get(
            f'{BASE}calculator/',
            {'afm': self.profile.afm, 'year': '2026', 'period': '5',
             'period_type': 'quarterly'},
        )
        self.assertEqual(resp.status_code, 400)
