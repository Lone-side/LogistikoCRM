# -*- coding: utf-8 -*-
"""
seed_demo management command — TDD contract
===========================================
A repeatable, idempotent demo-data seeder so demos and manual verification are
one command instead of ad-hoc scripts. Produces a client with a portal login,
obligations (mixed status), and multi-year VAT data (so the year-selector has
something to show).
"""
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from accounting.models import ClientProfile, MonthlyObligation, ObligationType
from accounting.portal import is_client_user
from mydata.models import VATRecord, VATPeriodResult

DEMO_AFM = '099000117'  # valid checksum


def _run(**kwargs):
    out = StringIO()
    call_command('seed_demo', stdout=out, **kwargs)
    return out.getvalue()


class SeedDemoTest(TestCase):
    def test_creates_demo_client_with_portal_login(self):
        _run()
        client = ClientProfile.objects.get(afm=DEMO_AFM)
        self.assertIsNotNone(client.user)              # has a portal user
        self.assertTrue(is_client_user(client.user))    # is a client, not staff
        self.assertFalse(client.user.is_staff)

    def test_portal_user_can_authenticate(self):
        _run()
        client = ClientProfile.objects.get(afm=DEMO_AFM)
        # The command must set a usable, known password and print it.
        self.assertTrue(client.user.has_usable_password())

    def test_creates_obligations_mixed_status(self):
        _run()
        client = ClientProfile.objects.get(afm=DEMO_AFM)
        obls = MonthlyObligation.objects.filter(client=client)
        self.assertGreaterEqual(obls.count(), 3)
        statuses = set(obls.values_list('status', flat=True))
        # At least pending + completed present (a realistic demo).
        self.assertIn('pending', statuses)
        self.assertIn('completed', statuses)

    def test_creates_multi_year_vat(self):
        # The year-selector (#2) needs >1 year of VAT data to be meaningful.
        _run()
        client = ClientProfile.objects.get(afm=DEMO_AFM)
        years = set(VATRecord.objects.filter(client=client)
                    .values_list('issue_date__year', flat=True))
        self.assertGreaterEqual(len(years), 2)
        # Period results too.
        self.assertGreaterEqual(
            VATPeriodResult.objects.filter(client=client).count(), 1)

    def test_vat_records_have_both_directions(self):
        _run()
        client = ClientProfile.objects.get(afm=DEMO_AFM)
        rec_types = set(VATRecord.objects.filter(client=client)
                        .values_list('rec_type', flat=True))
        self.assertIn(1, rec_types)  # output / εκροές
        self.assertIn(2, rec_types)  # input / εισροές

    def test_idempotent_rerun(self):
        _run()
        _run()  # second run must not crash or duplicate the client
        self.assertEqual(ClientProfile.objects.filter(afm=DEMO_AFM).count(), 1)
        self.assertEqual(User.objects.filter(username=DEMO_AFM).count(), 1)

    def test_reset_flag_clears_and_reseeds(self):
        _run()
        client = ClientProfile.objects.get(afm=DEMO_AFM)
        VATRecord.objects.filter(client=client).delete()  # simulate drift
        _run(reset=True)
        # --reset deletes & recreates the client, so re-fetch by AFM.
        client = ClientProfile.objects.get(afm=DEMO_AFM)
        self.assertEqual(ClientProfile.objects.filter(afm=DEMO_AFM).count(), 1)
        self.assertGreaterEqual(
            VATRecord.objects.filter(client=client).count(), 1)

    def test_prints_credentials(self):
        output = _run()
        self.assertIn(DEMO_AFM, output)
        # Credentials must be surfaced so the operator can log in.
        self.assertRegex(output.lower(), r'password|κωδικ')

    def test_output_is_cp1253_safe(self):
        # Windows console is cp1253; emoji/✓ (non-cp1253) crash the command.
        output = _run()
        try:
            output.encode('cp1253')
        except UnicodeEncodeError as e:
            self.fail(f'Output not cp1253-safe (Windows console would crash): {e}')
