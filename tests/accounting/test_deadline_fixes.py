# -*- coding: utf-8 -*-
"""
Regression: ObligationType.get_deadline_for_month — specific_day clamp
=====================================================================
Bug: deadline_type='specific_day' με deadline_day=31 καλούσε datetime(year, 2, 31)
→ ValueError, που (μέσα στο atomic block του generate_month_obligations) ακύρωνε
ΟΛΟ το batch δημιουργίας υποχρεώσεων. Fix: clamp στην τελευταία ημέρα του μήνα.
"""
from datetime import date

from django.test import TestCase

from accounting.models import ObligationType


class SpecificDayDeadlineClampTest(TestCase):
    def _otype(self, day):
        return ObligationType.objects.create(
            name=f"Τεστ {day}", code=f"T{day}", frequency="monthly",
            deadline_type="specific_day", deadline_day=day,
        )

    def test_day_31_in_february_clamps_to_last_day(self):
        ot = self._otype(31)
        # Φεβρουάριος 2026 (28 ημέρες) — δεν πρέπει να σκάσει.
        self.assertEqual(ot.get_deadline_for_month(2026, 2), date(2026, 2, 28))

    def test_day_31_in_leap_february(self):
        ot = self._otype(31)
        self.assertEqual(ot.get_deadline_for_month(2024, 2), date(2024, 2, 29))

    def test_day_31_in_30_day_month(self):
        ot = self._otype(31)
        self.assertEqual(ot.get_deadline_for_month(2026, 4), date(2026, 4, 30))

    def test_valid_day_unchanged(self):
        ot = self._otype(20)
        self.assertEqual(ot.get_deadline_for_month(2026, 3), date(2026, 3, 20))

    def test_day_31_in_31_day_month_unchanged(self):
        ot = self._otype(31)
        self.assertEqual(ot.get_deadline_for_month(2026, 1), date(2026, 1, 31))
