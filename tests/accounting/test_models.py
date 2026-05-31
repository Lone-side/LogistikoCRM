"""
Comprehensive tests for Accounting app models
Tests for: ClientProfile, ObligationType, MonthlyObligation, EmailTemplate,
VoIPCall, Ticket, ClientDocument
"""
from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from datetime import datetime, timedelta
from decimal import Decimal
import os

from accounting.models import (
    ClientProfile, ObligationGroup, ObligationProfile, ObligationType,
    ClientObligation, MonthlyObligation, ArchiveConfiguration,
    EmailTemplate, EmailAutomationRule, ScheduledEmail,
    VoIPCall, VoIPCallLog, Ticket, ClientDocument
)
from crm.models import Company, Contact


class ClientProfileModelTest(TestCase):
    """Test ClientProfile model"""

    def setUp(self):
        self.company = Company.objects.create(
            full_name="Test Company Ltd",
            email="test@company.com"
        )

    def test_create_client_profile_with_company(self):
        """Test creating a client profile linked to a company"""
        client = ClientProfile.objects.create(
            company=self.company,
            afm="123456789",
            doy="A' ΑΘΗΝΩΝ",
            eponimia="Test Company Ltd",
            eidos_ipoxreou="company",
            katigoria_vivlion="A"
        )

        self.assertEqual(client.afm, "123456789")
        self.assertEqual(client.eponimia, "Test Company Ltd")
        self.assertEqual(client.eidos_ipoxreou, "company")
        self.assertTrue(client.is_active)
        self.assertIsNotNone(client.created_at)
        self.assertEqual(str(client), "123456789 - Test Company Ltd")

    def test_create_client_profile_individual(self):
        """Test creating an individual client profile"""
        client = ClientProfile.objects.create(
            afm="987654321",
            doy="Β' ΑΘΗΝΩΝ",
            eponimia="Παπαδόπουλος",
            onoma="Γιώργος",
            onoma_patros="Νικόλαος",
            eidos_ipoxreou="individual",
            filo="M",
            imerominia_gennisis=datetime(1980, 5, 15).date()
        )

        self.assertEqual(client.onoma, "Γιώργος")
        self.assertEqual(client.eidos_ipoxreou, "individual")
        self.assertEqual(client.filo, "M")
        self.assertIsNotNone(client.imerominia_gennisis)

    def test_client_profile_unique_afm(self):
        """Test that AFM must be unique"""
        ClientProfile.objects.create(
            afm="111111111",
            eponimia="Client 1",
            eidos_ipoxreou="individual"
        )

        with self.assertRaises(Exception):
            ClientProfile.objects.create(
                afm="111111111",  # Duplicate AFM
                eponimia="Client 2",
                eidos_ipoxreou="individual"
            )

    def test_client_profile_optional_fields(self):
        """Test client profile with minimal required fields"""
        client = ClientProfile.objects.create(
            afm="222222222",
            eponimia="Minimal Client",
            eidos_ipoxreou="professional"
        )

        # Check optional fields have default values
        self.assertEqual(client.doy, '')
        self.assertEqual(client.onoma, '')
        self.assertFalse(client.agrotis)
        self.assertTrue(client.is_active)


class ObligationTypeModelTest(TestCase):
    """Test ObligationType model and deadline calculations"""

    def setUp(self):
        self.group = ObligationGroup.objects.create(
            name="ΦΠΑ Ομάδα",
            description="Αλληλοαποκλειόμενες υποχρεώσεις ΦΠΑ"
        )

        self.profile = ObligationProfile.objects.create(
            name="Μισθοδοσία",
            description="Όλες οι υποχρεώσεις μισθοδοσίας"
        )

    def test_create_monthly_obligation_type(self):
        """Test creating a monthly obligation type"""
        obl_type = ObligationType.objects.create(
            name="ΦΠΑ Μηνιαία",
            code="VAT_MONTHLY",
            frequency="monthly",
            deadline_type="last_day",
            priority=1
        )

        self.assertEqual(obl_type.name, "ΦΠΑ Μηνιαία")
        self.assertEqual(obl_type.frequency, "monthly")
        self.assertTrue(obl_type.is_active)
        self.assertEqual(str(obl_type), "ΦΠΑ Μηνιαία")

    def test_deadline_calculation_last_day(self):
        """Test deadline calculation for last day of month"""
        obl_type = ObligationType.objects.create(
            name="Test Obligation",
            code="TEST",
            frequency="monthly",
            deadline_type="last_day"
        )

        # February 2024 (leap year)
        deadline = obl_type.get_deadline_for_month(2024, 2)
        self.assertEqual(deadline.day, 29)

        # February 2023 (non-leap year)
        deadline = obl_type.get_deadline_for_month(2023, 2)
        self.assertEqual(deadline.day, 28)

        # March
        deadline = obl_type.get_deadline_for_month(2024, 3)
        self.assertEqual(deadline.day, 31)

    def test_deadline_calculation_specific_day(self):
        """Test deadline calculation for specific day"""
        obl_type = ObligationType.objects.create(
            name="Test Obligation",
            code="TEST",
            frequency="monthly",
            deadline_type="specific_day",
            deadline_day=15
        )

        deadline = obl_type.get_deadline_for_month(2024, 3)
        self.assertEqual(deadline.day, 15)
        self.assertEqual(deadline.month, 3)
        self.assertEqual(deadline.year, 2024)

    def test_applies_to_month_monthly(self):
        """Test that monthly obligations apply to all months"""
        obl_type = ObligationType.objects.create(
            name="Monthly Obligation",
            code="MONTHLY",
            frequency="monthly",
            deadline_type="last_day"
        )

        for month in range(1, 13):
            self.assertTrue(obl_type.applies_to_month(month))

    def test_applies_to_month_quarterly(self):
        """Test quarterly obligations apply only to specific months"""
        obl_type = ObligationType.objects.create(
            name="Quarterly Obligation",
            code="QUARTERLY",
            frequency="quarterly",
            deadline_type="last_day",
            applicable_months="3,6,9,12"
        )

        self.assertTrue(obl_type.applies_to_month(3))
        self.assertTrue(obl_type.applies_to_month(6))
        self.assertFalse(obl_type.applies_to_month(1))
        self.assertFalse(obl_type.applies_to_month(2))


class ClientObligationModelTest(TestCase):
    """Test ClientObligation model"""

    def setUp(self):
        self.client = ClientProfile.objects.create(
            afm="123456789",
            eponimia="Test Client",
            eidos_ipoxreou="company"
        )

        self.obl_type1 = ObligationType.objects.create(
            name="ΦΠΑ",
            code="VAT",
            frequency="monthly",
            deadline_type="last_day"
        )

        self.obl_type2 = ObligationType.objects.create(
            name="ΜΥΦ",
            code="MYF",
            frequency="monthly",
            deadline_type="specific_day",
            deadline_day=20
        )

        self.profile = ObligationProfile.objects.create(
            name="Μισθοδοσία"
        )
        self.profile.obligation_types.add(self.obl_type1, self.obl_type2)

    def test_create_client_obligation(self):
        """Test creating client obligations"""
        # A ClientObligation is auto-created via signal on ClientProfile creation,
        # and client is a OneToOneField — reuse the existing instance.
        client_obl, _ = ClientObligation.objects.update_or_create(
            client=self.client,
            defaults={'is_active': True}
        )
        client_obl.obligation_types.add(self.obl_type1)

        self.assertEqual(client_obl.client, self.client)
        self.assertTrue(client_obl.is_active)
        self.assertIn(self.obl_type1, client_obl.obligation_types.all())

    def test_get_all_obligation_types(self):
        """Test getting all obligations from both individual and profiles"""
        obl_type3 = ObligationType.objects.create(
            name="Standalone",
            code="STAND",
            frequency="annual",
            deadline_type="last_day"
        )

        client_obl = ClientObligation.objects.create(
            client=self.client
        )
        client_obl.obligation_types.add(obl_type3)
        client_obl.obligation_profiles.add(self.profile)

        all_obligations = client_obl.get_all_obligation_types()

        # Should include standalone + profile obligations
        self.assertIn(obl_type3, all_obligations)
        self.assertIn(self.obl_type1, all_obligations)
        self.assertIn(self.obl_type2, all_obligations)


class MonthlyObligationModelTest(TestCase):
    """Test MonthlyObligation model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        self.client = ClientProfile.objects.create(
            afm="123456789",
            eponimia="Test Client",
            eidos_ipoxreou="company"
        )

        self.obl_type = ObligationType.objects.create(
            name="ΦΠΑ Μηνιαία",
            code="VAT_MONTHLY",
            frequency="monthly",
            deadline_type="last_day"
        )

    def test_create_monthly_obligation(self):
        """Test creating a monthly obligation"""
        # Use a future deadline so save() does not auto-flip status to 'overdue'
        future = timezone.now().date() + timedelta(days=30)

        monthly_obl = MonthlyObligation.objects.create(
            client=self.client,
            obligation_type=self.obl_type,
            year=future.year,
            month=future.month,
            deadline=future,
            status='pending'
        )

        self.assertEqual(monthly_obl.status, 'pending')
        self.assertEqual(monthly_obl.year, future.year)
        self.assertEqual(monthly_obl.month, future.month)
        self.assertIsNone(monthly_obl.completed_date)

    def test_monthly_obligation_cost_calculation(self):
        """Test cost calculation based on time spent and hourly rate"""
        monthly_obl = MonthlyObligation.objects.create(
            client=self.client,
            obligation_type=self.obl_type,
            year=2024,
            month=3,
            deadline=datetime(2024, 3, 31).date(),
            time_spent=Decimal('2.5'),
            hourly_rate=Decimal('50.00')
        )

        expected_cost = 2.5 * 50.0
        self.assertEqual(monthly_obl.cost, expected_cost)

    def test_monthly_obligation_is_overdue(self):
        """Test overdue detection"""
        # Create past deadline
        past_deadline = timezone.now().date() - timedelta(days=5)

        monthly_obl = MonthlyObligation.objects.create(
            client=self.client,
            obligation_type=self.obl_type,
            year=2024,
            month=2,
            deadline=past_deadline,
            status='pending'
        )

        self.assertTrue(monthly_obl.is_overdue)

        # Completed obligations are not overdue
        monthly_obl.status = 'completed'
        monthly_obl.save()
        self.assertFalse(monthly_obl.is_overdue)

    def test_days_until_deadline(self):
        """Test days calculation until deadline"""
        future_deadline = timezone.now().date() + timedelta(days=10)

        monthly_obl = MonthlyObligation.objects.create(
            client=self.client,
            obligation_type=self.obl_type,
            year=2024,
            month=4,
            deadline=future_deadline,
            status='pending'
        )

        self.assertEqual(monthly_obl.days_until_deadline, 10)

    def test_deadline_status_calculation(self):
        """Test deadline status for display"""
        # Completed
        monthly_obl = MonthlyObligation.objects.create(
            client=self.client,
            obligation_type=self.obl_type,
            year=2024,
            month=1,
            deadline=timezone.now().date(),
            status='completed'
        )
        self.assertEqual(monthly_obl.deadline_status, 'completed')

        # Overdue
        monthly_obl2 = MonthlyObligation.objects.create(
            client=self.client,
            obligation_type=self.obl_type,
            year=2024,
            month=2,
            deadline=timezone.now().date() - timedelta(days=1),
            status='pending'
        )
        self.assertEqual(monthly_obl2.deadline_status, 'overdue')

        # Today
        monthly_obl3 = MonthlyObligation.objects.create(
            client=self.client,
            obligation_type=self.obl_type,
            year=2024,
            month=3,
            deadline=timezone.now().date(),
            status='pending'
        )
        self.assertEqual(monthly_obl3.deadline_status, 'today')

        # Urgent (within 3 days)
        monthly_obl4 = MonthlyObligation.objects.create(
            client=self.client,
            obligation_type=self.obl_type,
            year=2024,
            month=4,
            deadline=timezone.now().date() + timedelta(days=2),
            status='pending'
        )
        self.assertEqual(monthly_obl4.deadline_status, 'urgent')

    def test_auto_set_completed_date_on_save(self):
        """Test that completed_date is auto-set when status changes to completed"""
        monthly_obl = MonthlyObligation.objects.create(
            client=self.client,
            obligation_type=self.obl_type,
            year=2024,
            month=3,
            deadline=datetime(2024, 3, 31).date(),
            status='pending'
        )

        self.assertIsNone(monthly_obl.completed_date)

        # Mark as completed
        monthly_obl.status = 'completed'
        monthly_obl.save()

        self.assertIsNotNone(monthly_obl.completed_date)
        self.assertEqual(monthly_obl.completed_date, timezone.now().date())

    def test_auto_status_overdue_on_save(self):
        """Test that status auto-changes to overdue if past deadline"""
        past_deadline = timezone.now().date() - timedelta(days=1)

        monthly_obl = MonthlyObligation.objects.create(
            client=self.client,
            obligation_type=self.obl_type,
            year=2024,
            month=2,
            deadline=past_deadline,
            status='pending'
        )

        # Should auto-change to overdue
        self.assertEqual(monthly_obl.status, 'overdue')

    def test_unique_constraint(self):
        """Test that client + obligation_type + year + month must be unique"""
        MonthlyObligation.objects.create(
            client=self.client,
            obligation_type=self.obl_type,
            year=2024,
            month=3,
            deadline=datetime(2024, 3, 31).date()
        )

        # Try to create duplicate
        with self.assertRaises(Exception):
            MonthlyObligation.objects.create(
                client=self.client,
                obligation_type=self.obl_type,
                year=2024,
                month=3,  # Same month/year/client/type
                deadline=datetime(2024, 3, 31).date()
            )


class EmailTemplateModelTest(TestCase):
    """Test EmailTemplate model"""

    def test_create_email_template(self):
        """Test creating an email template"""
        template = EmailTemplate.objects.create(
            name="Υπενθύμιση Προθεσμίας",
            description="Template για υπενθύμιση προθεσμιών",
            subject="Υπενθύμιση: {{obligation.name}}",
            body_html="<p>Αγαπητέ {{client.eponimia}},</p><p>Η προθεσμία για {{obligation.name}} λήγει στις {{obligation.deadline}}.</p>",
            is_active=True
        )

        self.assertEqual(template.name, "Υπενθύμιση Προθεσμίας")
        self.assertTrue(template.is_active)

    def test_email_template_render(self):
        """Test rendering email template with context"""
        template = EmailTemplate.objects.create(
            name="Test Template",
            subject="Υπενθύμιση: {{obligation_name}}",
            body_html="<p>Αγαπητέ {{client_name}}, η προθεσμία λήγει στις {{deadline}}.</p>"
        )

        context = {
            'obligation_name': 'ΦΠΑ',
            'client_name': 'Test Client',
            'deadline': '31/03/2024'
        }

        subject, body = template.render(context)

        self.assertIn('ΦΠΑ', subject)
        self.assertIn('Test Client', body)
        self.assertIn('31/03/2024', body)


class VoIPCallModelTest(TestCase):
    """Test VoIPCall model"""

    def setUp(self):
        self.client = ClientProfile.objects.create(
            afm="123456789",
            eponimia="Test Client",
            eidos_ipoxreou="company"
        )

    def test_create_voip_call(self):
        """Test creating a VoIP call"""
        call = VoIPCall.objects.create(
            call_id="CALL_12345",
            phone_number="+306912345678",
            direction="incoming",
            status="active",
            started_at=timezone.now()
        )

        self.assertEqual(call.call_id, "CALL_12345")
        self.assertEqual(call.direction, "incoming")
        self.assertEqual(call.duration_seconds, 0)

    def test_voip_call_duration_calculation(self):
        """Test automatic duration calculation"""
        started = timezone.now()
        ended = started + timedelta(minutes=5, seconds=30)

        call = VoIPCall.objects.create(
            call_id="CALL_12346",
            phone_number="+306912345678",
            direction="outgoing",
            status="completed",
            started_at=started,
            ended_at=ended
        )

        expected_seconds = 5 * 60 + 30  # 330 seconds
        self.assertEqual(call.duration_seconds, expected_seconds)
        self.assertEqual(call.duration_formatted, "00:05:30")

    def test_voip_call_with_client(self):
        """Test linking VoIP call to client"""
        call = VoIPCall.objects.create(
            call_id="CALL_12347",
            phone_number="+306912345678",
            direction="incoming",
            status="completed",
            started_at=timezone.now(),
            client=self.client
        )

        self.assertEqual(call.client, self.client)
        self.assertIn(call, self.client.voip_calls.all())

    def test_is_missed_property(self):
        """Test is_missed property"""
        call = VoIPCall.objects.create(
            call_id="CALL_MISSED",
            phone_number="+306912345678",
            direction="incoming",
            status="missed",
            started_at=timezone.now()
        )

        self.assertTrue(call.is_missed)


class TicketModelTest(TestCase):
    """Test Ticket model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        self.client = ClientProfile.objects.create(
            afm="123456789",
            eponimia="Test Client",
            eidos_ipoxreou="company"
        )

        self.call = VoIPCall.objects.create(
            call_id="CALL_MISSED_001",
            phone_number="+306912345678",
            direction="incoming",
            status="missed",
            started_at=timezone.now(),
            client=self.client
        )

    def test_create_ticket_from_missed_call(self):
        """Test creating a ticket from missed call"""
        ticket = Ticket.objects.create(
            call=self.call,
            client=self.client,
            title="Αναπάντητη κλήση από Test Client",
            description="Αναπάντητη κλήση στις " + timezone.now().strftime("%d/%m/%Y %H:%M"),
            status="open",
            priority="high"
        )

        self.assertEqual(ticket.call, self.call)
        self.assertEqual(ticket.client, self.client)
        self.assertEqual(ticket.status, "open")
        self.assertEqual(ticket.priority, "high")
        self.assertTrue(ticket.is_open)
        self.assertFalse(ticket.is_resolved)

    def test_ticket_assignment(self):
        """Test assigning ticket to user"""
        ticket = Ticket.objects.create(
            call=self.call,
            client=self.client,
            title="Test Ticket",
            status="open"
        )

        self.assertIsNone(ticket.assigned_to)
        self.assertIsNone(ticket.assigned_at)

        ticket.mark_as_assigned(self.user)

        self.assertEqual(ticket.assigned_to, self.user)
        self.assertIsNotNone(ticket.assigned_at)
        self.assertEqual(ticket.status, "assigned")

    def test_ticket_lifecycle(self):
        """Test ticket status transitions"""
        ticket = Ticket.objects.create(
            call=self.call,
            client=self.client,
            title="Test Ticket",
            status="open"
        )

        # Assign
        ticket.mark_as_assigned(self.user)
        self.assertEqual(ticket.status, "assigned")

        # In progress
        ticket.mark_as_in_progress()
        self.assertEqual(ticket.status, "in_progress")
        self.assertTrue(ticket.is_open)

        # Resolve
        ticket.mark_as_resolved()
        self.assertEqual(ticket.status, "resolved")
        self.assertIsNotNone(ticket.resolved_at)
        self.assertTrue(ticket.is_resolved)

        # Close
        ticket.mark_as_closed()
        self.assertEqual(ticket.status, "closed")
        self.assertIsNotNone(ticket.closed_at)

    def test_ticket_days_since_created(self):
        """Test days since ticket creation"""
        ticket = Ticket.objects.create(
            call=self.call,
            client=self.client,
            title="Test Ticket"
        )

        # Should be 0 days for just created ticket
        self.assertEqual(ticket.days_since_created, 0)


class ClientDocumentModelTest(TestCase):
    """Test ClientDocument model"""

    def setUp(self):
        self.client = ClientProfile.objects.create(
            afm="123456789",
            eponimia="Test Client",
            eidos_ipoxreou="company"
        )

    def test_create_client_document(self):
        """Test creating a client document"""
        test_file = SimpleUploadedFile(
            "test_invoice.pdf",
            b"file_content",
            content_type="application/pdf"
        )

        doc = ClientDocument.objects.create(
            client=self.client,
            file=test_file,
            document_category="invoices",
            description="Test invoice document"
        )

        self.assertEqual(doc.client, self.client)
        self.assertEqual(doc.document_category, "invoices")
        self.assertEqual(doc.file_type, "pdf")
        self.assertIn("test_invoice.pdf", doc.filename)

    def test_client_document_auto_filename(self):
        """Test automatic filename extraction"""
        test_file = SimpleUploadedFile(
            "important_contract.docx",
            b"file_content",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

        doc = ClientDocument.objects.create(
            client=self.client,
            file=test_file,
            document_category="contracts"
        )

        self.assertIn("important_contract", doc.filename)
        self.assertEqual(doc.file_type, "docx")


class ArchiveConfigurationModelTest(TestCase):
    """Test ArchiveConfiguration model"""

    def setUp(self):
        self.client = ClientProfile.objects.create(
            afm="123456789",
            eponimia="Test Client Ltd",
            eidos_ipoxreou="company"
        )

        self.obl_type = ObligationType.objects.create(
            name="ΦΠΑ Μηνιαία",
            code="VAT_MONTHLY",
            frequency="monthly",
            deadline_type="last_day"
        )

        self.monthly_obl = MonthlyObligation.objects.create(
            client=self.client,
            obligation_type=self.obl_type,
            year=2024,
            month=3,
            deadline=datetime(2024, 3, 31).date()
        )

    def test_archive_configuration_creation(self):
        """Test creating archive configuration"""
        config = ArchiveConfiguration.objects.create(
            obligation_type=self.obl_type,
            filename_pattern="{type_code}_{month}_{year}.pdf",
            folder_pattern="clients/{client_afm}/{year}/{month}/",
            auto_rename=True
        )

        self.assertEqual(config.obligation_type, self.obl_type)
        self.assertTrue(config.auto_rename)

    def test_get_archive_path(self):
        """Test archive path generation"""
        config = ArchiveConfiguration.objects.create(
            obligation_type=self.obl_type,
            filename_pattern="{type_code}_{month}_{year}.pdf",
            folder_pattern="clients/{client_afm}_{client_name}/{year}/{month}/"
        )

        path = config.get_archive_path(self.monthly_obl, "test.pdf")

        self.assertIn("123456789", path)  # AFM
        self.assertIn("2024", path)  # Year
        self.assertIn("03", path)  # Month
        self.assertIn("VAT_MONTHLY", path)  # Type code
