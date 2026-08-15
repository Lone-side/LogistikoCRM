"""
Tests for Accounting management commands
"""
from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone
from io import StringIO
from datetime import datetime

from accounting.models import (
    ClientProfile, ObligationType, ClientObligation,
    MonthlyObligation, ObligationProfile
)


class GenerateMonthlyObligationsCommandTest(TestCase):
    """Test generate_monthly_obligations management command"""

    def setUp(self):
        # Create test client
        self.client = ClientProfile.objects.create(
            afm="123456789",
            eponimia="Test Client Ltd",
            eidos_ipoxreou="company"
        )

        # Create obligation types
        self.monthly_obl_type = ObligationType.objects.create(
            name="ΦΠΑ Μηνιαία",
            code="VAT_MONTHLY",
            frequency="monthly",
            deadline_type="last_day",
            priority=1
        )

        self.quarterly_obl_type = ObligationType.objects.create(
            name="ΦΠΑ Τριμηνιαία",
            code="VAT_QUARTERLY",
            frequency="quarterly",
            deadline_type="last_day",
            applicable_months="3,6,9,12",
            priority=2
        )

        # Create client obligation
        # Το signal δημιουργεί αυτόματα ClientObligation με το ClientProfile
        self.client_obl, _ = ClientObligation.objects.get_or_create(client=self.client)
        self.client_obl.is_active = True
        self.client_obl.save()
        self.client_obl.obligation_types.add(
            self.monthly_obl_type,
            self.quarterly_obl_type
        )

    def test_command_generates_monthly_obligations(self):
        """Test that command generates monthly obligations"""
        out = StringIO()

        # Run for March 2024
        call_command(
            'generate_monthly_obligations',
            year=2024,
            month=3,
            stdout=out
        )

        # Check monthly obligation was created
        monthly_obls = MonthlyObligation.objects.filter(
            client=self.client,
            year=2024,
            month=3
        )

        # Should have 2 obligations (both monthly and quarterly apply to March)
        self.assertEqual(monthly_obls.count(), 2)

        # Check monthly obligation
        monthly = monthly_obls.get(obligation_type=self.monthly_obl_type)
        self.assertEqual(monthly.deadline.day, 31)  # Last day of March
        # Η deadline (2024) είναι περασμένη, οπότε το save() τη μαρκάρει overdue
        self.assertEqual(monthly.status, 'overdue')

    def test_command_skips_non_applicable_months(self):
        """Test that quarterly obligations are only created for specific months"""
        out = StringIO()

        # Run for February 2024 (not a quarterly month)
        call_command(
            'generate_monthly_obligations',
            year=2024,
            month=2,
            stdout=out
        )

        monthly_obls = MonthlyObligation.objects.filter(
            client=self.client,
            year=2024,
            month=2
        )

        # Should only have 1 obligation (monthly, not quarterly)
        self.assertEqual(monthly_obls.count(), 1)
        self.assertEqual(
            monthly_obls.first().obligation_type,
            self.monthly_obl_type
        )

    def test_command_dry_run(self):
        """Test dry-run mode doesn't save anything"""
        out = StringIO()

        call_command(
            'generate_monthly_obligations',
            year=2024,
            month=4,
            dry_run=True,
            stdout=out
        )

        # Nothing should be saved
        self.assertEqual(
            MonthlyObligation.objects.filter(
                year=2024,
                month=4
            ).count(),
            0
        )

        # Output should mention dry-run
        output = out.getvalue()
        self.assertIn('DRY-RUN', output)

    def test_command_specific_client(self):
        """Test generating obligations for specific client only"""
        # Create second client
        client2 = ClientProfile.objects.create(
            afm="987654321",
            eponimia="Client 2",
            eidos_ipoxreou="company"
        )

        client_obl2, _ = ClientObligation.objects.get_or_create(client=client2)
        client_obl2.is_active = True
        client_obl2.save()
        client_obl2.obligation_types.add(self.monthly_obl_type)

        out = StringIO()

        # Run for only first client
        call_command(
            'generate_monthly_obligations',
            year=2024,
            month=5,
            client=self.client.afm,
            stdout=out
        )

        # Only first client should have obligations
        self.assertTrue(
            MonthlyObligation.objects.filter(
                client=self.client,
                year=2024,
                month=5
            ).exists()
        )

        self.assertFalse(
            MonthlyObligation.objects.filter(
                client=client2,
                year=2024,
                month=5
            ).exists()
        )

    def test_command_force_recreate(self):
        """Test force flag recreates existing obligations"""
        # Create existing obligation
        existing = MonthlyObligation.objects.create(
            client=self.client,
            obligation_type=self.monthly_obl_type,
            year=2024,
            month=6,
            deadline=datetime(2024, 6, 30).date(),
            status='completed',
            notes='Old notes'
        )

        out = StringIO()

        # Run with force
        call_command(
            'generate_monthly_obligations',
            year=2024,
            month=6,
            force=True,
            stdout=out
        )

        # Obligation should be recreated
        new_obl = MonthlyObligation.objects.get(
            client=self.client,
            obligation_type=self.monthly_obl_type,
            year=2024,
            month=6
        )

        # Recreated (όχι πλέον completed)· με περασμένη deadline γίνεται overdue
        self.assertEqual(new_obl.status, 'overdue')
        self.assertEqual(new_obl.notes, '')

    def test_command_inactive_clients_skipped(self):
        """Test that inactive clients are skipped"""
        # Make client obligation inactive
        self.client_obl.is_active = False
        self.client_obl.save()

        out = StringIO()

        call_command(
            'generate_monthly_obligations',
            year=2024,
            month=7,
            stdout=out
        )

        # No obligations should be created
        self.assertEqual(
            MonthlyObligation.objects.filter(
                year=2024,
                month=7
            ).count(),
            0
        )

    def test_command_with_obligation_profiles(self):
        """Test generating obligations from obligation profiles"""
        # Create profile
        profile = ObligationProfile.objects.create(
            name="Μισθοδοσία Package"
        )

        payroll_obl = ObligationType.objects.create(
            name="Μισθοδοσία",
            code="PAYROLL",
            frequency="monthly",
            deadline_type="specific_day",
            deadline_day=25
        )

        profile.obligation_types.add(payroll_obl)

        # Add profile to client
        self.client_obl.obligation_profiles.add(profile)

        out = StringIO()

        call_command(
            'generate_monthly_obligations',
            year=2024,
            month=8,
            stdout=out
        )

        # Should have obligations from profile + individual types
        monthly_obls = MonthlyObligation.objects.filter(
            client=self.client,
            year=2024,
            month=8
        )

        # Monthly + payroll (quarterly doesn't apply to month 8)
        self.assertEqual(monthly_obls.count(), 2)

        # Check payroll obligation
        payroll = monthly_obls.get(obligation_type=payroll_obl)
        self.assertEqual(payroll.deadline.day, 25)

    def test_command_default_month_is_next_month(self):
        """Test that default month is next month if not specified"""
        out = StringIO()

        current_month = timezone.now().month
        current_year = timezone.now().year

        # Calculate expected next month
        if current_month == 12:
            expected_month = 1
            expected_year = current_year + 1
        else:
            expected_month = current_month + 1
            expected_year = current_year

        # Run without specifying month
        call_command(
            'generate_monthly_obligations',
            stdout=out
        )

        # Check that obligations were created for next month
        self.assertTrue(
            MonthlyObligation.objects.filter(
                year=expected_year,
                month=expected_month
            ).exists()
        )

    def test_command_quiet_mode(self):
        """Test quiet mode produces minimal output"""
        out = StringIO()

        call_command(
            'generate_monthly_obligations',
            year=2024,
            month=9,
            quiet=True,
            stdout=out
        )

        output = out.getvalue()

        # Should have minimal output
        self.assertNotIn('===', output)  # No headers
        self.assertIn('Created:', output)  # Just stats

    def test_command_verbose_mode(self):
        """Test verbose mode produces detailed output"""
        out = StringIO()

        call_command(
            'generate_monthly_obligations',
            year=2024,
            month=10,
            verbose=True,
            stdout=out
        )

        output = out.getvalue()

        # Should have detailed output
        self.assertIn('Test Client', output)
        self.assertIn('ΦΠΑ', output)


class ShowProgressEncodingTest(TestCase):
    """Regression: η μπάρα προόδου δεν πρέπει να ρίχνει την εντολή.

    Το show_progress έγραφε κατευθείαν στο sys.stdout χαρακτήρες █/░ και
    ελληνικό κείμενο. Σε ελληνική κονσόλα Windows (cp1253) αυτό σκάει με
    UnicodeEncodeError και παρασέρνει ολόκληρη την εντολή — 135 τέτοια
    σφάλματα έκαναν το τοπικό backend suite να αποτυγχάνει ολοσχερώς.
    """

    def _command(self):
        from accounting.management.commands.generate_monthly_obligations import Command
        return Command()

    def test_progress_is_skipped_when_stdout_is_not_a_tty(self):
        """Σε tests/CI/cron/docker logs δεν γράφεται τίποτα."""
        import sys
        from unittest import mock

        stream = StringIO()  # StringIO.isatty() -> False
        with mock.patch.object(sys, 'stdout', stream):
            self._command().show_progress(1, 10, 'Επεξεργασία: ΔΟΚΙΜΗ ΑΕ')

        self.assertEqual(stream.getvalue(), '')

    def test_progress_falls_back_to_ascii_on_encoding_error(self):
        """Σε cp1253 terminal δεν σκάει· υποχωρεί σε ASCII."""
        import sys
        from unittest import mock

        class Cp1253Tty:
            """Terminal που δεν κωδικοποιεί ελληνικά ή block characters."""
            encoding = 'cp1253'

            def __init__(self):
                self.written = []

            def isatty(self):
                return True

            def write(self, text):
                # Ό,τι δεν χωρά στο cp1253 σκάει, όπως στην πραγματική κονσόλα.
                text.encode('cp1253')
                self.written.append(text)

            def flush(self):
                pass

        stream = Cp1253Tty()
        with mock.patch.object(sys, 'stdout', stream):
            # Δεν πρέπει να σηκώσει UnicodeEncodeError.
            self._command().show_progress(5, 10, 'Επεξεργασία: ΔΟΚΙΜΗ ΑΕ')

        output = ''.join(stream.written)
        self.assertIn('50%', output)
        self.assertIn('#', output)          # ASCII μπάρα
        self.assertNotIn('█', output)       # όχι block characters
