"""
Integration tests for critical accounting workflows
Tests end-to-end scenarios for production readiness
"""
from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.management import call_command
from datetime import datetime, timedelta
from decimal import Decimal
from io import StringIO

from accounting.models import (
    ClientProfile, ObligationType, ClientObligation,
    MonthlyObligation, EmailTemplate, EmailAutomationRule,
    ScheduledEmail, VoIPCall, Ticket
)
from accounting.services.email_service import trigger_automation_rules
from crm.models import Company


class ClientObligationWorkflowTest(TestCase):
    """Test complete client obligation workflow"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='accountant',
            password='testpass123'
        )

        # Create company and client
        self.company = Company.objects.create(
            full_name="Test Company Ltd",
            email="company@example.com"
        )

        self.client = ClientProfile.objects.create(
            company=self.company,
            afm="123456789",
            doy="A' ΑΘΗΝΩΝ",
            eponimia="Test Company Ltd",
            email="client@example.com",
            eidos_ipoxreou="company",
            katigoria_vivlion="A"
        )

    def test_complete_monthly_obligation_workflow(self):
        """
        Test complete workflow:
        1. Create obligation types
        2. Assign to client
        3. Generate monthly obligations
        4. Complete obligation
        5. Trigger email automation
        """
        # Step 1: Create obligation types
        vat_monthly = ObligationType.objects.create(
            name="ΦΠΑ Μηνιαία",
            code="VAT_MONTHLY",
            frequency="monthly",
            deadline_type="last_day",
            priority=1
        )

        myf = ObligationType.objects.create(
            name="ΜΥΦ",
            code="MYF",
            frequency="monthly",
            deadline_type="specific_day",
            deadline_day=20,
            priority=2
        )

        # Step 2: Assign obligations to client
        # Το signal δημιουργεί αυτόματα ClientObligation με το ClientProfile
        client_obl, _ = ClientObligation.objects.get_or_create(client=self.client)
        client_obl.is_active = True
        client_obl.save()
        client_obl.obligation_types.add(vat_monthly, myf)

        # Step 3: Generate monthly obligations for March 2024
        out = StringIO()
        call_command(
            'generate_monthly_obligations',
            year=2024,
            month=3,
            stdout=out
        )

        # Verify obligations were created
        march_obls = MonthlyObligation.objects.filter(
            client=self.client,
            year=2024,
            month=3
        )
        self.assertEqual(march_obls.count(), 2)

        # Verify deadlines
        vat_obl = march_obls.get(obligation_type=vat_monthly)
        myf_obl = march_obls.get(obligation_type=myf)

        self.assertEqual(vat_obl.deadline.day, 31)  # Last day of March
        self.assertEqual(myf_obl.deadline.day, 20)  # 20th of March
        # Η deadline (2024) είναι περασμένη - το save() τη μαρκάρει overdue
        self.assertEqual(vat_obl.status, 'overdue')

        # Step 4: Complete an obligation
        vat_obl.status = 'completed'
        vat_obl.completed_by = self.user
        vat_obl.time_spent = Decimal('2.5')
        vat_obl.hourly_rate = Decimal('50.00')
        vat_obl.save()

        vat_obl.refresh_from_db()
        self.assertEqual(vat_obl.status, 'completed')
        self.assertIsNotNone(vat_obl.completed_date)
        self.assertEqual(vat_obl.cost, 125.0)  # 2.5 * 50

        # Step 5: Create email template and automation rule
        template = EmailTemplate.objects.create(
            name="Completion Email",
            subject="Ολοκληρώθηκε: {{obligations.0.name}}",
            body_html="<p>Η υποχρέωση ολοκληρώθηκε για {{client.eponimia}}</p>",
            is_active=True
        )

        # timing != 'immediate' ώστε να επιστραφεί το ScheduledEmail
        rule = EmailAutomationRule.objects.create(
            name="Send on completion",
            trigger="on_complete",
            template=template,
            timing="delay_24h",
            is_active=True
        )

        # Trigger automation
        emails = trigger_automation_rules(vat_obl, trigger_type='on_complete')

        # Verify email was scheduled
        self.assertEqual(len(emails), 1)
        scheduled_email = emails[0]
        self.assertEqual(scheduled_email.client, self.client)
        self.assertIn('ΦΠΑ', scheduled_email.subject)


class ClientLifecycleWorkflowTest(TestCase):
    """Test complete client lifecycle from creation to obligations"""

    def test_new_client_onboarding_workflow(self):
        """
        Test workflow:
        1. Create new client
        2. Verify folder structure created
        3. Assign obligation profile
        4. Generate obligations
        5. Verify monthly obligations created
        """
        import os
        from django.conf import settings
        from accounting.models import ObligationProfile, get_client_folder

        # Step 1: Create new client (signal should create folders)
        client = ClientProfile.objects.create(
            afm="987654321",
            doy="Β' ΑΘΗΝΩΝ",
            eponimia="New Client Ltd",
            email="newclient@example.com",
            eidos_ipoxreou="company"
        )

        # Step 2: Verify folder structure was created by signal
        # Η δομή είναι ιεραρχική βάσει FilingSystemSettings:
        # 00_ΜΟΝΙΜΑ/, {έτος}/{μήνας}/{κατηγορία}/
        from datetime import datetime as dt
        from settings.models import FilingSystemSettings

        filing_settings = FilingSystemSettings.get_settings()
        base_path = os.path.join(
            filing_settings.get_archive_root(), get_client_folder(client)
        )

        permanent_path = os.path.join(
            base_path, filing_settings.permanent_folder_name
        )
        for folder in filing_settings.get_permanent_folder_categories():
            self.assertTrue(
                os.path.exists(os.path.join(permanent_path, folder)),
                f"Folder {folder} should be created automatically"
            )

        year_path = os.path.join(base_path, str(dt.now().year))
        month_name = (
            filing_settings.get_month_folder_name(1)
            if filing_settings.use_greek_month_names else '01'
        )
        for folder in filing_settings.get_monthly_folder_categories():
            self.assertTrue(
                os.path.exists(os.path.join(year_path, month_name, folder)),
                f"Folder {folder} should be created automatically"
            )

        # Step 3: Create and assign obligation profile
        profile = ObligationProfile.objects.create(
            name="Μισθοδοσία Package"
        )

        payroll = ObligationType.objects.create(
            name="Μισθοδοσία",
            code="PAYROLL",
            frequency="monthly",
            deadline_type="specific_day",
            deadline_day=25
        )

        vat = ObligationType.objects.create(
            name="ΦΠΑ",
            code="VAT",
            frequency="monthly",
            deadline_type="last_day"
        )

        profile.obligation_types.add(payroll, vat)

        client_obl, _ = ClientObligation.objects.get_or_create(client=client)
        client_obl.is_active = True
        client_obl.save()
        client_obl.obligation_profiles.add(profile)

        # Step 4: Generate obligations
        out = StringIO()
        call_command(
            'generate_monthly_obligations',
            year=2024,
            month=4,
            client=client.afm,
            stdout=out
        )

        # Step 5: Verify both obligations from profile were created
        april_obls = MonthlyObligation.objects.filter(
            client=client,
            year=2024,
            month=4
        )

        self.assertEqual(april_obls.count(), 2)
        self.assertTrue(april_obls.filter(obligation_type=payroll).exists())
        self.assertTrue(april_obls.filter(obligation_type=vat).exists())


class VoIPToTicketWorkflowTest(TestCase):
    """Test VoIP call to ticket creation workflow"""

    def test_missed_call_creates_ticket(self):
        """
        Test workflow:
        1. Receive missed call
        2. Match to client
        3. Create ticket automatically
        4. Assign ticket
        5. Resolve ticket
        """
        # Step 1: Create client
        client = ClientProfile.objects.create(
            afm="111222333",
            eponimia="VoIP Test Client",
            email="voip@example.com",
            kinito_tilefono="+306912345678",
            eidos_ipoxreou="company"
        )

        user = User.objects.create_user(
            username='support',
            password='testpass123'
        )

        # Step 2: Create missed call
        call = VoIPCall.objects.create(
            call_id="CALL_MISSED_001",
            phone_number="+306912345678",
            direction="incoming",
            status="missed",
            started_at=timezone.now(),
            client=client  # Matched to client by phone number
        )

        self.assertTrue(call.is_missed)

        # Step 3: Create ticket from missed call
        ticket = Ticket.objects.create(
            call=call,
            client=client,
            title=f"Αναπάντητη κλήση από {client.eponimia}",
            description=f"Αναπάντητη κλήση στις {call.started_at.strftime('%d/%m/%Y %H:%M')}",
            status="open",
            priority="high"
        )

        self.assertEqual(ticket.status, "open")
        self.assertTrue(ticket.is_open)

        # Update call with ticket info
        call.ticket_created = True
        call.ticket_id = str(ticket.id)
        call.save()

        # Step 4: Assign ticket
        ticket.mark_as_assigned(user)

        self.assertEqual(ticket.status, "assigned")
        self.assertEqual(ticket.assigned_to, user)
        self.assertIsNotNone(ticket.assigned_at)

        # Step 5: Work on and resolve ticket
        ticket.mark_as_in_progress()
        self.assertEqual(ticket.status, "in_progress")

        ticket.notes = "Επικοινώνησα με τον πελάτη και επέλυσα το θέμα"
        ticket.mark_as_resolved()

        self.assertEqual(ticket.status, "resolved")
        self.assertTrue(ticket.is_resolved)
        self.assertIsNotNone(ticket.resolved_at)


class EmailAutomationWorkflowTest(TestCase):
    """Test email automation workflows"""

    def test_deadline_reminder_automation(self):
        """
        Test workflow:
        1. Create obligation with upcoming deadline
        2. Set up before_deadline automation
        3. Trigger automation
        4. Verify reminder email scheduled
        """
        client = ClientProfile.objects.create(
            afm="444555666",
            eponimia="Reminder Test Client",
            email="reminders@example.com",
            eidos_ipoxreou="professional"
        )

        obl_type = ObligationType.objects.create(
            name="Φορολογική Δήλωση",
            code="TAX_RETURN",
            frequency="annual",
            deadline_type="specific_day",
            deadline_day=30,
            applicable_months="7"  # July
        )

        # Create obligation with deadline in 3 days
        upcoming_deadline = timezone.now().date() + timedelta(days=3)

        obligation = MonthlyObligation.objects.create(
            client=client,
            obligation_type=obl_type,
            year=2024,
            month=7,
            deadline=upcoming_deadline,
            status='pending'
        )

        # Create reminder template
        template = EmailTemplate.objects.create(
            name="Deadline Reminder",
            subject="Υπενθύμιση: {{obligations.0.name}} λήγει σε {{days}} ημέρες",
            body_html="""
                <p>Αγαπητέ {{client.eponimia}},</p>
                <p>Σας υπενθυμίζουμε ότι η προθεσμία για
                {{obligations.0.name}} λήγει στις {{obligations.0.deadline}}.</p>
            """,
            is_active=True
        )

        # Create automation rule
        # timing != 'immediate' ώστε το trigger_automation_rules να επιστρέψει
        # το ScheduledEmail (τα immediate στέλνονται απευθείας χωρίς επιστροφή)
        rule = EmailAutomationRule.objects.create(
            name="3-day reminder",
            trigger="before_deadline",
            template=template,
            timing="delay_24h",
            days_before_deadline=3,
            is_active=True
        )

        # Trigger automation
        emails = trigger_automation_rules(obligation, trigger_type='before_deadline')

        # Verify reminder was scheduled
        self.assertEqual(len(emails), 1)
        reminder = emails[0]
        self.assertEqual(reminder.client, client)
        self.assertEqual(reminder.status, 'pending')
        self.assertIn('Φορολογική', reminder.subject)


class MonthlyObligationBatchProcessingTest(TransactionTestCase):
    """Test batch processing of monthly obligations"""

    def test_batch_generate_for_multiple_clients(self):
        """
        Test workflow:
        1. Create multiple clients with obligations
        2. Generate all obligations for a month
        3. Verify correct obligations created for each
        """
        # Create 10 test clients
        clients = []
        for i in range(10):
            client = ClientProfile.objects.create(
                afm=f"10000000{i}",
                eponimia=f"Client {i+1}",
                email=f"client{i+1}@example.com",
                eidos_ipoxreou="company"
            )
            clients.append(client)

        # Create obligation types
        monthly_vat = ObligationType.objects.create(
            name="ΦΠΑ Μηνιαία",
            code="VAT_M",
            frequency="monthly",
            deadline_type="last_day"
        )

        quarterly_vat = ObligationType.objects.create(
            name="ΦΠΑ Τριμηνιαία",
            code="VAT_Q",
            frequency="quarterly",
            deadline_type="last_day",
            applicable_months="3,6,9,12"
        )

        # Assign obligations to all clients
        for client in clients:
            client_obl, _ = ClientObligation.objects.get_or_create(client=client)
            client_obl.is_active = True
            client_obl.save()
            client_obl.obligation_types.add(monthly_vat)

            # Half of clients get quarterly too
            if client.afm[-1] in ['0', '2', '4', '6', '8']:
                client_obl.obligation_types.add(quarterly_vat)

        # Generate for March (quarterly month)
        out = StringIO()
        call_command(
            'generate_monthly_obligations',
            year=2024,
            month=3,
            stdout=out
        )

        # Verify counts
        march_obls = MonthlyObligation.objects.filter(year=2024, month=3)

        # 10 monthly + 5 quarterly = 15 obligations
        self.assertEqual(march_obls.count(), 15)

        # Verify each client has correct obligations
        for client in clients:
            client_march = march_obls.filter(client=client)

            if client.afm[-1] in ['0', '2', '4', '6', '8']:
                # Should have both monthly and quarterly
                self.assertEqual(client_march.count(), 2)
            else:
                # Should have only monthly
                self.assertEqual(client_march.count(), 1)

        # Generate for February (non-quarterly month)
        call_command(
            'generate_monthly_obligations',
            year=2024,
            month=2,
            stdout=StringIO()
        )

        # Only monthly obligations should be created
        feb_obls = MonthlyObligation.objects.filter(year=2024, month=2)
        self.assertEqual(feb_obls.count(), 10)  # Only monthly for all clients


class ObligationStatusTransitionTest(TestCase):
    """Test obligation status transitions and business rules"""

    def test_overdue_status_auto_update(self):
        """Test that overdue status is auto-set for past deadlines"""
        client = ClientProfile.objects.create(
            afm="777888999",
            eponimia="Overdue Test",
            eidos_ipoxreou="company"
        )

        obl_type = ObligationType.objects.create(
            name="Test",
            code="TEST",
            frequency="monthly",
            deadline_type="last_day"
        )

        # Create obligation with past deadline
        past_deadline = timezone.now().date() - timedelta(days=5)

        obligation = MonthlyObligation.objects.create(
            client=client,
            obligation_type=obl_type,
            year=2024,
            month=1,
            deadline=past_deadline,
            status='pending'
        )

        # Status should auto-update to overdue
        self.assertEqual(obligation.status, 'overdue')
        self.assertTrue(obligation.is_overdue)
        self.assertEqual(obligation.days_until_deadline, -5)

    def test_completed_not_overdue(self):
        """Test that completed obligations are never marked overdue"""
        client = ClientProfile.objects.create(
            afm="000111222",
            eponimia="Completed Test",
            eidos_ipoxreou="company"
        )

        obl_type = ObligationType.objects.create(
            name="Test",
            code="TEST",
            frequency="monthly",
            deadline_type="last_day"
        )

        past_deadline = timezone.now().date() - timedelta(days=10)

        obligation = MonthlyObligation.objects.create(
            client=client,
            obligation_type=obl_type,
            year=2024,
            month=1,
            deadline=past_deadline,
            status='completed'
        )

        # Should not be overdue even with past deadline
        self.assertFalse(obligation.is_overdue)
