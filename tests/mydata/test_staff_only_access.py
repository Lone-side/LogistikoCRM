# -*- coding: utf-8 -*-
"""
SECURITY: the staff myDATA API (/api/mydata/*) must be STAFF-ONLY.

These are management endpoints (not the client portal — clients use
/api/client/me/vat/). Before the fix, every view was IsAuthenticated-only with
no client scoping, so a logged-in CLIENT could read EVERY client's VAT records,
credentials status, sync logs, and dashboards (cross-tenant breach). These tests
lock the staff-only contract.

Uses APIRequestFactory to avoid the Py3.14 + Django test-client HTML-error issue.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounting.models import ClientProfile
from mydata.models import VATRecord, MyDataCredentials, VATSyncLog
from mydata import views


class MyDataStaffOnlyTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        # A CLIENT user (the attacker): not staff, linked to client_a.
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α', eidos_ipoxreou='company')
        self.attacker = self.client_a.create_portal_user(password='x')
        # Another client's data the attacker must NOT see.
        self.victim = ClientProfile.objects.create(
            afm='094160855', eponimia='ΘΥΜΑ ΑΕ', eidos_ipoxreou='company')
        VATRecord.objects.create(
            client=self.victim, mark=9001, issue_date='2026-05-01', rec_type=1,
            inv_type='1.1', vat_category=1,
            net_value=Decimal('1000'), vat_amount=Decimal('240'))
        MyDataCredentials.objects.create(client=self.victim)
        VATSyncLog.objects.create(client=self.victim, sync_type='VAT_INFO', status='SUCCESS')
        # A staff user (legitimate).
        self.staff = User.objects.create_user(username='staff', password='x', is_staff=True)

    def _client_gets_403(self, view, method='get', **kwargs):
        req = getattr(self.factory, method)('/api/mydata/x/', kwargs or None)
        force_authenticate(req, user=self.attacker)
        resp = view(req)
        return resp.status_code

    # ----- list/read viewsets -----
    def test_records_list_forbidden_for_client(self):
        view = views.VATRecordViewSet.as_view({'get': 'list'})
        self.assertEqual(self._client_gets_403(view), status.HTTP_403_FORBIDDEN)

    def test_credentials_list_forbidden_for_client(self):
        view = views.MyDataCredentialsViewSet.as_view({'get': 'list'})
        self.assertEqual(self._client_gets_403(view), status.HTTP_403_FORBIDDEN)

    def test_synclogs_list_forbidden_for_client(self):
        view = views.VATSyncLogViewSet.as_view({'get': 'list'})
        self.assertEqual(self._client_gets_403(view), status.HTTP_403_FORBIDDEN)

    def test_periods_list_forbidden_for_client(self):
        view = views.VATPeriodResultViewSet.as_view({'get': 'list'})
        self.assertEqual(self._client_gets_403(view), status.HTTP_403_FORBIDDEN)

    # ----- APIViews -----
    def test_dashboard_forbidden_for_client(self):
        view = views.MyDataDashboardView.as_view()
        self.assertEqual(self._client_gets_403(view), status.HTTP_403_FORBIDDEN)

    def test_client_detail_forbidden_for_client(self):
        # Attacker tries to read the victim's VAT by AFM.
        req = self.factory.get('/api/mydata/client/094160855/')
        force_authenticate(req, user=self.attacker)
        resp = views.ClientVATDetailView.as_view()(req, afm='094160855')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_trend_forbidden_for_client(self):
        view = views.MonthlyTrendView.as_view()
        self.assertEqual(self._client_gets_403(view), status.HTTP_403_FORBIDDEN)

    def test_calculator_forbidden_for_client(self):
        view = views.VATPeriodCalculatorView.as_view()
        self.assertEqual(self._client_gets_403(view), status.HTTP_403_FORBIDDEN)

    # ----- staff still allowed (no regression) -----
    def test_records_list_allowed_for_staff(self):
        view = views.VATRecordViewSet.as_view({'get': 'list'})
        req = self.factory.get('/api/mydata/records/')
        force_authenticate(req, user=self.staff)
        resp = view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_dashboard_allowed_for_staff(self):
        req = self.factory.get('/api/mydata/dashboard/')
        force_authenticate(req, user=self.staff)
        resp = views.MyDataDashboardView.as_view()(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
