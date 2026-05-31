"""
Tests for the Email Service
Author: ddiplas
Description: Tests for EmailTemplate, EmailLog, and EmailService functionality
"""

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone
from decimal import Decimal

from accounting.models import (
    ClientProfile,
    ObligationType,
    MonthlyObligation,
    EmailTemplate,
    EmailLog
)
from accounting.services.email_service import EmailService

User = get_user_model()


class EmailTemplateModelTest(TestCase):
    """Tests for the EmailTemplate model"""

    def setUp(self):
        """Set up test data"""
        self.template = EmailTemplate.objects.create(
            name='Test Template',
            description='Test description',
            subject='Hello {client_name}',
            body_html='<p>Dear {client_name}, your {obligation_type} is complete.</p>',
            is_active=True
        )

    def test_template_creation(self):
        """Test that template is created correctly"""
        self.assertEqual(self.template.name, 'Test Template')
        self.assertTrue(self.template.is_active)

    def test_template_str(self):
        """Test template string representation"""
        self.assertEqual(str(self.template), 'Test Template')

    def test_render_simple_basic(self):
        """Test simple variable replacement"""
        variables = {
            'client_name': 'ΤΕΣΤ ΠΕΛΑΤΗΣ ΑΕ',
            'obligation_type': 'ΦΠΑ'
        }
        subject, body = self.template.render_simple(variables)

        self.assertEqual(subject, 'Hello ΤΕΣΤ ΠΕΛΑΤΗΣ ΑΕ')
        self.assertIn('ΤΕΣΤ ΠΕΛΑΤΗΣ ΑΕ', body)
        self.assertIn('ΦΠΑ', body)

    def test_render_simple_missing_variables(self):
        """Test handling of missing variables"""
        variables = {
            'client_name': 'Test Client'
            # obligation_type is missing
        }
        subject, body = self.template.render_simple(variables)

        # Missing variables should be replaced with empty string
        self.assertNotIn('{obligation_type}', body)

    def test_render_simple_greek_characters(self):
        """Test with Greek characters"""
        variables = {
            'client_name': 'ΔΟΚΙΜΑΣΤΙΚΗ ΕΤΑΙΡΕΙΑ ΑΕ',
            'obligation_type': 'Φόρος Προστιθέμενης Αξίας'
        }
        subject, body = self.template.render_simple(variables)

        self.assertIn('ΔΟΚΙΜΑΣΤΙΚΗ ΕΤΑΙΡΕΙΑ ΑΕ', subject)
        self.assertIn('Φόρος Προστιθέμενης Αξίας', body)

    def test_get_available_variables(self):
        """Test that available variables list is returned"""
        variables = EmailTemplate.get_available_variables()
        self.assertIsInstance(variables, list)
        self.assertTrue(len(variables) > 0)
        # Check some expected variables
        variable_names = [v[0] for v in variables]
        self.assertIn('{client_name}', variable_names)
        self.assertIn('{obligation_type}', variable_names)


class EmailTemplateSelectionTest(TestCase):
    """Tests for automatic template selection"""

    def setUp(self):
        """Set up test data"""
        self.obligation_type = ObligationType.objects.create(
            name='ΦΠΑ',
            code='FPA',
            frequency='monthly'
        )

        self.client = ClientProfile.objects.create(
            afm='123456789',
            eponimia='Test Company',
            email='test@example.com'
        )

        self.obligation = MonthlyObligation.objects.create(
            client=self.client,
            obligation_type=self.obligation_type,
            year=2025,
            month=1,
            deadline=timezone.now().date(),
            status='completed'
        )

        # Template specific to obligation type
        self.specific_template = EmailTemplate.objects.create(
            name='ΦΠΑ Template',
            subject='ΦΠΑ {period_display}',
            body_html='<p>ΦΠΑ completed</p>',
            obligation_type=self.obligation_type,
            is_active=True
        )

        # General template
        self.general_template = EmailTemplate.objects.create(
            name='Ολοκλήρωση Υποχρέωσης',
            subject='Ολοκλήρωση {obligation_type}',
            body_html='<p>General completion</p>',
            is_active=True
        )

    def test_get_template_for_specific_type(self):
        """Test that specific template is selected for obligation type"""
        template = EmailTemplate.get_template_for_obligation(self.obligation)
        self.assertEqual(template, self.specific_template)

    def test_get_template_fallback(self):
        """Test fallback to general template"""
        # Remove specific template
        self.specific_template.delete()

        # A general (non-type-specific) active template should be returned.
        # We assert on behaviour rather than identity, because a migration
        # seeds a default "Ολοκλήρωση Υποχρέωσης" template with the same name.
        template = EmailTemplate.get_template_for_obligation(self.obligation)
        self.assertIsNotNone(template)
        self.assertTrue(template.is_active)
        self.assertIsNone(template.obligation_type)


class EmailLogModelTest(TestCase):
    """Tests for the EmailLog model"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpass123'
        )

        self.client = ClientProfile.objects.create(
            afm='123456789',
            eponimia='Test Company',
            email='client@example.com'
        )

    def test_email_log_creation(self):
        """Test creating an email log entry"""
        log = EmailLog.objects.create(
            recipient_email='client@example.com',
            recipient_name='Test Company',
            client=self.client,
            subject='Test Subject',
            body='Test Body',
            status='sent',
            sent_by=self.user
        )

        self.assertEqual(log.status, 'sent')
        self.assertEqual(log.recipient_email, 'client@example.com')

    def test_email_log_str(self):
        """Test email log string representation"""
        log = EmailLog.objects.create(
            recipient_email='client@example.com',
            recipient_name='Test Company',
            subject='Test Subject',
            body='Test Body',
            status='sent'
        )

        str_repr = str(log)
        self.assertIn('client@example.com', str_repr)

    def test_email_log_status_display(self):
        """Test status display property"""
        log = EmailLog.objects.create(
            recipient_email='client@example.com',
            recipient_name='Test Company',
            subject='Test Subject',
            body='Test Body',
            status='sent'
        )

        self.assertIn('Απεστάλη', log.status_display)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='noreply@test.com'
)
class EmailServiceTest(TestCase):
    """Tests for the EmailService class"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpass123'
        )

        self.obligation_type = ObligationType.objects.create(
            name='ΦΠΑ',
            code='FPA',
            frequency='monthly'
        )

        self.client = ClientProfile.objects.create(
            afm='123456789',
            eponimia='ΤΕΣΤ ΕΤΑΙΡΕΙΑ ΑΕ',
            email='client@example.com'
        )

        self.obligation = MonthlyObligation.objects.create(
            client=self.client,
            obligation_type=self.obligation_type,
            year=2025,
            month=1,
            deadline=timezone.now().date(),
            status='completed'
        )

        self.template = EmailTemplate.objects.create(
            name='Ολοκλήρωση Υποχρέωσης',
            subject='Ολοκλήρωση {obligation_type} - {period_display}',
            body_html='<p>Αγαπητέ {client_name}, η υποχρέωση {obligation_type} ολοκληρώθηκε.</p>',
            is_active=True
        )

    def test_get_context_for_obligation(self):
        """Test context generation for obligation"""
        context = EmailService.get_context_for_obligation(self.obligation, self.user)

        self.assertEqual(context['client_name'], 'ΤΕΣΤ ΕΤΑΙΡΕΙΑ ΑΕ')
        self.assertEqual(context['client_afm'], '123456789')
        self.assertEqual(context['obligation_type'], 'ΦΠΑ')
        self.assertEqual(context['period_month'], '01')
        self.assertEqual(context['period_year'], '2025')

    def test_render_template(self):
        """Test template rendering"""
        subject, body = EmailService.render_template(
            template=self.template,
            obligation=self.obligation,
            user=self.user
        )

        self.assertIn('ΦΠΑ', subject)
        self.assertIn('01/2025', subject)
        self.assertIn('ΤΕΣΤ ΕΤΑΙΡΕΙΑ ΑΕ', body)

    def test_send_email(self):
        """Test sending email"""
        success, result = EmailService.send_email(
            recipient_email='test@example.com',
            subject='Test Subject',
            body='<p>Test Body</p>',
            client=self.client,
            template=self.template,
            user=self.user
        )

        self.assertTrue(success)
        self.assertIsInstance(result, EmailLog)
        self.assertEqual(result.status, 'sent')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Test Subject')

    def test_send_email_creates_log(self):
        """Test that sending email creates a log entry"""
        initial_count = EmailLog.objects.count()

        EmailService.send_email(
            recipient_email='test@example.com',
            subject='Test Subject',
            body='<p>Test Body</p>',
            client=self.client,
            user=self.user
        )

        self.assertEqual(EmailLog.objects.count(), initial_count + 1)

    def test_send_obligation_completion_email(self):
        """Test sending completion email for obligation"""
        success, result = EmailService.send_obligation_completion_email(
            obligation=self.obligation,
            user=self.user
        )

        self.assertTrue(success)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('ΦΠΑ', mail.outbox[0].subject)

    def test_send_obligation_completion_email_no_client_email(self):
        """Test handling when client has no email"""
        self.client.email = ''
        self.client.save()

        success, result = EmailService.send_obligation_completion_email(
            obligation=self.obligation,
            user=self.user
        )

        self.assertFalse(success)
        self.assertEqual(len(mail.outbox), 0)

    def test_preview_email(self):
        """Test email preview functionality"""
        preview = EmailService.preview_email(
            template=self.template,
            obligation=self.obligation,
            user=self.user
        )

        self.assertIn('subject', preview)
        self.assertIn('body', preview)
        self.assertIn('recipient', preview)
        self.assertEqual(preview['recipient'], 'client@example.com')
        self.assertIn('ΦΠΑ', preview['subject'])

    def test_send_bulk_emails(self):
        """Test sending bulk emails"""
        # Create another obligation
        obligation2 = MonthlyObligation.objects.create(
            client=self.client,
            obligation_type=self.obligation_type,
            year=2025,
            month=2,
            deadline=timezone.now().date(),
            status='completed'
        )

        results = EmailService.send_bulk_emails(
            obligations=[self.obligation, obligation2],
            template=self.template,
            user=self.user
        )

        self.assertEqual(results['sent'], 2)
        self.assertEqual(results['failed'], 0)
        self.assertEqual(len(mail.outbox), 2)


class EmailServiceGreekCharactersTest(TestCase):
    """Tests for Greek character handling in emails"""

    def setUp(self):
        """Set up test data with Greek characters"""
        self.obligation_type = ObligationType.objects.create(
            name='Φόρος Προστιθέμενης Αξίας',
            code='ΦΠΑ',
            frequency='monthly'
        )

        self.client = ClientProfile.objects.create(
            afm='123456789',
            eponimia='ΔΟΚΙΜΑΣΤΙΚΗ ΕΤΑΙΡΕΙΑ ΜΟΝΟΠΡΟΣΩΠΗ ΙΚΕ',
            email='info@dokimastiki.gr'
        )

        self.template = EmailTemplate.objects.create(
            name='Ελληνικό Template',
            subject='Ολοκλήρωση {obligation_type} για {client_name}',
            body_html='''
                <p>Αγαπητοί κύριοι,</p>
                <p>Σας ενημερώνουμε ότι η υποχρέωση {obligation_type}
                για την περίοδο {period_display} ολοκληρώθηκε.</p>
                <p>Με εκτίμηση,<br>{accountant_name}</p>
            ''',
            is_active=True
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='noreply@test.com',
        ACCOUNTANT_NAME='Ιωάννης Παπαδόπουλος'
    )
    def test_greek_characters_in_email(self):
        """Test that Greek characters are preserved in emails"""
        obligation = MonthlyObligation.objects.create(
            client=self.client,
            obligation_type=self.obligation_type,
            year=2025,
            month=3,
            deadline=timezone.now().date(),
            status='completed'
        )

        success, result = EmailService.send_obligation_completion_email(
            obligation=obligation
        )

        self.assertTrue(success)
        self.assertEqual(len(mail.outbox), 1)

        # Check subject contains Greek
        self.assertIn('Φόρος Προστιθέμενης Αξίας', mail.outbox[0].subject)
        self.assertIn('ΔΟΚΙΜΑΣΤΙΚΗ', mail.outbox[0].subject)


# =============================================================================
# NEW TESTS FOR EMAIL IMPROVEMENTS (v3.0)
# =============================================================================

class EmailLogRetryCountTest(TestCase):
    """Tests for the retry_count field on EmailLog"""

    def test_email_log_has_retry_count(self):
        """Test that EmailLog has retry_count field"""
        log = EmailLog.objects.create(
            recipient_email='test@example.com',
            recipient_name='Test',
            subject='Test',
            body='Test',
            status='pending'
        )
        self.assertEqual(log.retry_count, 0)

    def test_email_log_retry_count_increments(self):
        """Test that retry_count can be incremented"""
        log = EmailLog.objects.create(
            recipient_email='test@example.com',
            recipient_name='Test',
            subject='Test',
            body='Test',
            status='pending'
        )
        log.retry_count = 3
        log.save()
        log.refresh_from_db()
        self.assertEqual(log.retry_count, 3)

    def test_email_log_queued_status(self):
        """Test queued status for async emails"""
        log = EmailLog.objects.create(
            recipient_email='test@example.com',
            recipient_name='Test',
            subject='Test',
            body='Test',
            status='queued'
        )
        self.assertEqual(log.status, 'queued')
        self.assertIn('📤', str(log))


class EmailUtilsRateLimiterTest(TestCase):
    """Tests for the RateLimiter class"""

    def test_rate_limiter_creation(self):
        """Test RateLimiter can be created"""
        from accounting.services.email_utils import RateLimiter
        limiter = RateLimiter(requests_per_second=2.0)
        self.assertIsNotNone(limiter)

    def test_rate_limiter_wait(self):
        """Test RateLimiter wait method"""
        from accounting.services.email_utils import RateLimiter
        import time

        limiter = RateLimiter(requests_per_second=10.0)  # High rate for fast test

        start = time.time()
        limiter.wait()
        limiter.wait()
        elapsed = time.time() - start

        # Should have waited at least min_interval (0.1s for 10 req/s)
        self.assertGreaterEqual(elapsed, 0.05)

    def test_rate_limiter_reset(self):
        """Test RateLimiter reset"""
        from accounting.services.email_utils import RateLimiter
        limiter = RateLimiter()
        limiter.wait()
        limiter.reset()
        self.assertEqual(limiter.last_request_time, 0.0)


class EmailUtilsRetryDecoratorTest(TestCase):
    """Tests for the retry_with_backoff decorator"""

    def test_retry_decorator_success(self):
        """Test that decorator passes through on success"""
        from accounting.services.email_utils import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = success_func()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 1)

    def test_retry_decorator_retries_on_failure(self):
        """Test that decorator retries on retriable exceptions"""
        from accounting.services.email_utils import retry_with_backoff, RETRIABLE_EXCEPTIONS
        from smtplib import SMTPServerDisconnected

        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise SMTPServerDisconnected("Connection lost")
            return "success"

        result = fail_then_succeed()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 2)


class EmailUtilsConnectionPoolTest(TestCase):
    """Tests for the EmailConnectionPool class"""

    def test_connection_pool_creation(self):
        """Test ConnectionPool can be created"""
        from accounting.services.email_utils import EmailConnectionPool
        pool = EmailConnectionPool(max_connections=3)
        self.assertEqual(pool.max_connections, 3)

    def test_connection_pool_stats(self):
        """Test ConnectionPool stats"""
        from accounting.services.email_utils import EmailConnectionPool
        pool = EmailConnectionPool(max_connections=3)
        stats = pool.stats
        self.assertIn('pooled', stats)
        self.assertIn('active', stats)
        self.assertIn('max', stats)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='noreply@test.com'
)
class EmailServiceNewFeaturesTest(TestCase):
    """Tests for new EmailService features in v3.0"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpass123'
        )

        self.client = ClientProfile.objects.create(
            afm='123456789',
            eponimia='Test Company',
            email='client@example.com'
        )

    def test_send_email_with_retry_disabled(self):
        """Test sending email with retry disabled"""
        success, result = EmailService.send_email(
            recipient_email='test@example.com',
            subject='Test',
            body='<p>Test</p>',
            client=self.client,
            use_retry=False
        )
        self.assertTrue(success)
        self.assertEqual(len(mail.outbox), 1)

    def test_send_email_with_rate_limit_disabled(self):
        """Test sending email with rate limit disabled"""
        success, result = EmailService.send_email(
            recipient_email='test@example.com',
            subject='Test',
            body='<p>Test</p>',
            client=self.client,
            use_rate_limit=False
        )
        self.assertTrue(success)
        self.assertEqual(len(mail.outbox), 1)

    def test_send_email_creates_log_with_retry_count(self):
        """Test that EmailLog is created with retry_count=0"""
        success, result = EmailService.send_email(
            recipient_email='test@example.com',
            subject='Test',
            body='<p>Test</p>',
            client=self.client
        )
        self.assertTrue(success)
        self.assertIsInstance(result, EmailLog)
        self.assertEqual(result.retry_count, 0)

    def test_send_email_from_log(self):
        """Test sending email from existing EmailLog"""
        # Create a pending log entry
        log = EmailLog.objects.create(
            recipient_email='test@example.com',
            recipient_name='Test',
            client=self.client,
            subject='Test Subject',
            body='<p>Test Body</p>',
            status='pending'
        )

        success, error = EmailService.send_email_from_log(log.id)
        self.assertTrue(success)
        self.assertIsNone(error)

        log.refresh_from_db()
        self.assertEqual(log.status, 'sent')

    def test_send_email_from_log_already_sent(self):
        """Test that already sent emails are not re-sent"""
        log = EmailLog.objects.create(
            recipient_email='test@example.com',
            recipient_name='Test',
            client=self.client,
            subject='Test',
            body='Test',
            status='sent'
        )

        success, error = EmailService.send_email_from_log(log.id)
        self.assertTrue(success)
        # No new emails should be sent
        self.assertEqual(len(mail.outbox), 0)

    def test_send_bulk_emails_with_connection_pool(self):
        """Test bulk email with connection pooling"""
        obligation_type = ObligationType.objects.create(
            name='Test', code='TST', frequency='monthly'
        )

        template = EmailTemplate.objects.create(
            name='Test Template',
            subject='Test {client_name}',
            body_html='<p>Test</p>',
            is_active=True
        )

        obligations = []
        for i in range(3):
            obligations.append(MonthlyObligation.objects.create(
                client=self.client,
                obligation_type=obligation_type,
                year=2025,
                month=i + 1,
                deadline=timezone.now().date(),
                status='completed'
            ))

        results = EmailService.send_bulk_emails(
            obligations=obligations,
            template=template,
            use_connection_pool=True
        )

        self.assertEqual(results['sent'], 3)
        self.assertEqual(results['failed'], 0)
        self.assertEqual(len(mail.outbox), 3)
