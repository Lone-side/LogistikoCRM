# -*- coding: utf-8 -*-
"""
Regression tests: άκυρο client input στα accounting views πρέπει να
επιστρέφει 400 (ή να αγνοείται) — όχι HTTP 500.
"""
import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone

from accounting.models import (
    ClientProfile, MonthlyObligation, ObligationType, VoIPCall,
)
from accounting.views.obligations import bulk_complete_view


class InvalidInputsBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from tests.utils.helpers import grant_accounting_model_perms
        cls.staff = grant_accounting_model_perms(User.objects.create_user(
            username='staff_invalid', password='pass', is_staff=True,
        ))
        cls.client_profile = ClientProfile.objects.create(
            afm='123456783',
            eponimia='ΠΕΛΑΤΗΣ ΤΕΣΤ',
            eidos_ipoxreou='company',
        )
        cls.obligation_type = ObligationType.objects.create(code='ΦΠΑ', name='ΦΠΑ')
        today = timezone.now().date()
        cls.obligation = MonthlyObligation.objects.create(
            client=cls.client_profile,
            obligation_type=cls.obligation_type,
            year=today.year, month=today.month,
            deadline=today + timedelta(days=5),
            status='pending',
        )

    def setUp(self):
        self.client.force_login(self.staff)


class CheckObligationDuplicateTest(InvalidInputsBase):
    def test_invalid_client_param_returns_400(self):
        url = reverse('accounting:check_obligation')
        response = self.client.get(url, {
            'client': 'abc', 'type': '1', 'year': '2025', 'month': '1',
        })
        self.assertEqual(response.status_code, 400)

    def test_invalid_month_param_returns_400(self):
        url = reverse('accounting:check_obligation')
        response = self.client.get(url, {
            'client': str(self.client_profile.id),
            'type': str(self.obligation_type.id),
            'year': '2025', 'month': 'xx',
        })
        self.assertEqual(response.status_code, 400)

    def test_valid_params_still_work(self):
        url = reverse('accounting:check_obligation')
        response = self.client.get(url, {
            'client': str(self.client_profile.id),
            'type': str(self.obligation_type.id),
            'year': str(self.obligation.year),
            'month': str(self.obligation.month),
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['exists'])


class QuickCompleteInvalidJSONTest(InvalidInputsBase):
    def test_malformed_json_body_returns_400(self):
        url = reverse('accounting:quick_complete', args=[self.obligation.id])
        response = self.client.post(
            url, data='{not valid json', content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


class BulkCompleteViewInvalidInputTest(InvalidInputsBase):
    """Το bulk_complete_view δεν έχει δικό του URL — καλείται απευθείας."""

    def _request(self, data):
        request = RequestFactory().post('/bulk-complete/', data)
        request.user = self.staff
        return request

    def test_malformed_obligation_ids_returns_400(self):
        response = bulk_complete_view(self._request({
            'obligation_ids': '{broken json',
        }))
        self.assertEqual(response.status_code, 400)

    def test_invalid_time_spent_returns_400(self):
        response = bulk_complete_view(self._request({
            'obligation_ids': json.dumps([self.obligation.id]),
            'time_spent': 'abc',
        }))
        self.assertEqual(response.status_code, 400)


class ReportsDashboardInvalidParamsTest(InvalidInputsBase):
    def test_reports_invalid_months_returns_200(self):
        response = self.client.get(reverse('accounting:reports'), {'months': 'abc'})
        self.assertEqual(response.status_code, 200)

    def test_reports_months_clamped(self):
        response = self.client.get(reverse('accounting:reports'), {'months': '9999'})
        self.assertEqual(response.status_code, 200)

    def test_dashboard_invalid_dates_ignored(self):
        response = self.client.get(reverse('accounting:dashboard'), {
            'date_from': 'garbage', 'date_to': '2025-99-99',
        })
        self.assertEqual(response.status_code, 200)


class VoIPCallUpdateInvalidNotesTest(InvalidInputsBase):
    def setUp(self):
        super().setUp()
        self.call = VoIPCall.objects.create(
            call_id='test-call-1',
            phone_number='2101234567',
            direction='incoming',
            started_at=timezone.now(),
        )

    def test_non_string_notes_returns_400(self):
        url = reverse('accounting:voip_call_update', args=[self.call.id])
        response = self.client.post(
            url, data=json.dumps({'notes': 123}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_null_notes_returns_400(self):
        url = reverse('accounting:voip_call_update', args=[self.call.id])
        response = self.client.post(
            url, data=json.dumps({'notes': None}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_string_notes_still_work(self):
        url = reverse('accounting:voip_call_update', args=[self.call.id])
        response = self.client.post(
            url, data=json.dumps({'notes': 'σημείωση'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.call.refresh_from_db()
        self.assertEqual(self.call.notes, 'σημείωση')
