# -*- coding: utf-8 -*-
"""
Tests για τα νέα στατιστικά του dashboard:
- team_workload (φόρτος ανά υπάλληλο)
- type_breakdown (κατανομή μήνα ανά τύπο με καταστάσεις)
- monthly_trend (σωστή αριθμητική μηνών — π.χ. δεν χάνεται ο Φεβρουάριος)
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounting.models import ClientProfile, MonthlyObligation, ObligationType
from accounting.views.helpers import _calculate_monthly_stats


class DashboardStatsAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('boss', 'b@test.com', 'pass12345', is_staff=True)
        self.employee = User.objects.create_user(
            'maria', 'm@test.com', 'pass12345', first_name='Μαρία', last_name='Π.'
        )
        self.client.force_login(self.user)
        self.client_profile = ClientProfile.objects.create(
            afm='123456783', eponimia='ΠΕΛΑΤΗΣ ΑΕ', eidos_ipoxreou='company',
        )
        self.vat_type = ObligationType.objects.create(code='ΦΠΑ', name='ΦΠΑ')
        today = timezone.now().date()
        # Ανοιχτή ανατεθειμένη στη Μαρία
        MonthlyObligation.objects.create(
            client=self.client_profile, obligation_type=self.vat_type,
            year=today.year, month=today.month,
            deadline=today + timedelta(days=5),
            status='pending', assigned_to=self.employee,
        )
        # Ολοκληρωμένη αυτόν τον μήνα από τη Μαρία (άλλος πελάτης —
        # unique constraint ανά client/type/year/month)
        other_client = ClientProfile.objects.create(
            afm='999863881', eponimia='ΔΕΥΤΕΡΟΣ ΠΕΛΑΤΗΣ', eidos_ipoxreou='company',
        )
        MonthlyObligation.objects.create(
            client=other_client, obligation_type=self.vat_type,
            year=today.year, month=today.month,
            deadline=today + timedelta(days=10),
            status='completed', completed_by=self.employee,
            completed_date=today,
        )

    def _get_stats(self):
        resp = self.client.get('/accounting/api/dashboard/stats/')
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    def test_team_workload(self):
        data = self._get_stats()
        workload = data['team_workload']
        self.assertEqual(len(workload), 1)
        maria = workload[0]
        self.assertEqual(maria['name'], 'Μαρία Π.')
        self.assertEqual(maria['open'], 1)
        self.assertEqual(maria['overdue'], 0)
        self.assertEqual(maria['completed_this_month'], 1)

    def test_type_breakdown(self):
        data = self._get_stats()
        breakdown = data['type_breakdown']
        self.assertEqual(len(breakdown), 1)
        vat = breakdown[0]
        self.assertEqual(vat['obligation_type__code'], 'ΦΠΑ')
        self.assertEqual(vat['total'], 2)
        self.assertEqual(vat['completed'], 1)
        self.assertEqual(vat['pending'], 1)

    def test_monthly_trend_six_consecutive_months(self):
        data = self._get_stats()
        trend = data['monthly_trend']
        self.assertEqual(len(trend), 6)
        # Οι μήνες πρέπει να είναι συνεχόμενοι (κανένας δεν λείπει/διπλός)
        months = [(t['year'], t['month']) for t in trend]
        for (y1, m1), (y2, m2) in zip(months, months[1:]):
            expected = (y1, m1 + 1) if m1 < 12 else (y1 + 1, 1)
            self.assertEqual((y2, m2), expected)
        # Ο τελευταίος είναι ο τρέχων μήνας
        now = timezone.now()
        self.assertEqual(months[-1], (now.year, now.month))
        self.assertEqual(trend[-1]['total'], 2)
        self.assertEqual(trend[-1]['completed'], 1)


class MonthlyStatsHelperTest(TestCase):
    """Το παλιό timedelta(days=30*i) παρέλειπε μήνες (π.χ. Φεβρουάριο)."""

    def test_six_consecutive_months_from_march(self):
        obligations = MonthlyObligation.objects.all()

        class FakeNow:
            year = 2026
            month = 3

        stats = _calculate_monthly_stats(obligations, FakeNow)
        self.assertEqual(len(stats), 6)
        labels = [s['month'] for s in stats]
        # Με το παλιό bug ο Φεβρουάριος εξαφανιζόταν από 1η Μαρτίου
        self.assertIn('Φεβρουάριος 2026', labels)
        self.assertEqual(labels[0], 'Μάρτιος 2026')
        self.assertEqual(labels[-1], 'Οκτώβριος 2025')
