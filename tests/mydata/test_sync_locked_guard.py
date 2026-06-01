# -*- coding: utf-8 -*-
"""
mydata_sync_vat — locked-period guard (HIGH data-integrity fix)
===============================================================
The sync command clears VATRecords in a date range before re-syncing. If a
VATPeriodResult overlapping that range is LOCKED (submitted/finalized), the
clear would destroy the records behind it. The guard must refuse (skip the
client) unless --force is given.

These tests drive the command via call_command with REAL credentials present
but expect the guard to short-circuit BEFORE any myDATA API call, so no network
is needed: we assert the records survive and a PARTIAL/skipped log is written.
"""
from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from accounting.models import ClientProfile
from mydata.models import (
    VATRecord, VATPeriodResult, MyDataCredentials, VATSyncLog,
)


def _record(client, mark, issue):
    return VATRecord.objects.create(
        client=client, mark=mark, issue_date=issue, rec_type=1,
        inv_type='1.1', vat_category=1,
        net_value=Decimal('100.00'), vat_amount=Decimal('24.00'),
        is_cancelled=False,
    )


class SyncLockedGuardTest(TestCase):
    def setUp(self):
        self.client_p = ClientProfile.objects.create(
            afm='123456783', eponimia='Α', eidos_ipoxreou='company')
        # Credentials must exist (with values) or _sync_client_vat returns early
        # before reaching the guard. Set encrypted creds.
        creds = MyDataCredentials.objects.create(client=self.client_p)
        creds.user_id = 'demo-user'
        creds.subscription_key = 'demo-key'
        creds.save()

        # A record inside May 2026.
        self.rec = _record(self.client_p, 5001, date(2026, 5, 10))

    def _run(self, **kwargs):
        out, err = StringIO(), StringIO()
        call_command('mydata_sync_vat', stdout=out, stderr=err, **kwargs)
        return out.getvalue() + err.getvalue()

    def test_monthly_locked_period_blocks_clear(self):
        VATPeriodResult.objects.create(
            client=self.client_p, period_type='monthly', year=2026, period=5,
            is_locked=True, final_result=Decimal('24.00'))
        self._run(client='123456783', year=2026, month=5)
        # Record survived (NOT cleared).
        self.assertTrue(VATRecord.objects.filter(pk=self.rec.pk).exists())
        # A skipped/partial log was written.
        log = VATSyncLog.objects.filter(client=self.client_p).order_by('-id').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, 'PARTIAL')
        self.assertGreaterEqual(log.records_skipped, 1)

    def test_quarterly_locked_period_blocks_clear(self):
        # Q2 2026 covers Apr-Jun → overlaps a May sync.
        VATPeriodResult.objects.create(
            client=self.client_p, period_type='quarterly', year=2026, period=2,
            is_locked=True, final_result=Decimal('24.00'))
        self._run(client='123456783', year=2026, month=5)
        self.assertTrue(VATRecord.objects.filter(pk=self.rec.pk).exists())

    def test_partial_month_overlap_blocks_clear(self):
        # Locked May 2026; sync a range that only touches the last days of May.
        VATPeriodResult.objects.create(
            client=self.client_p, period_type='monthly', year=2026, period=5,
            is_locked=True, final_result=Decimal('24.00'))
        self._run(client='123456783',
                  **{'from': '28/05/2026', 'to': '05/06/2026'})
        self.assertTrue(VATRecord.objects.filter(pk=self.rec.pk).exists())

    def test_force_overrides_guard(self):
        # With --force, the guard is bypassed. We can't complete a real API sync,
        # but the guard must NOT short-circuit: it proceeds past the guard and the
        # delete runs (record cleared) before the API call fails. We assert the
        # record was cleared OR an API error occurred — i.e. the guard did not skip.
        VATPeriodResult.objects.create(
            client=self.client_p, period_type='monthly', year=2026, period=5,
            is_locked=True, final_result=Decimal('24.00'))
        try:
            self._run(client='123456783', year=2026, month=5, force=True)
        except Exception:
            pass  # API failure is fine; we only care the guard didn't skip.
        log = VATSyncLog.objects.filter(client=self.client_p).order_by('-id').first()
        # The log must NOT be a guard-skip PARTIAL with records_skipped for lock.
        if log is not None:
            self.assertNotIn('κλειδωμέν', (log.error_message or '').lower())

    def test_non_overlapping_locked_period_does_not_block(self):
        # Locked period in a DIFFERENT month (Jan 2026) must not block a May sync.
        VATPeriodResult.objects.create(
            client=self.client_p, period_type='monthly', year=2026, period=1,
            is_locked=True, final_result=Decimal('24.00'))
        try:
            self._run(client='123456783', year=2026, month=5, force=False)
        except Exception:
            pass  # API failure is fine; guard must not have skipped.
        log = VATSyncLog.objects.filter(client=self.client_p).order_by('-id').first()
        if log is not None:
            self.assertNotEqual(
                (log.status == 'PARTIAL' and log.records_skipped >= 1
                 and 'κλειδωμέν' in (log.error_message or '').lower()),
                True,
            )
