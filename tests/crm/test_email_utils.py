"""
Tests for CRM email utilities (send_email.py)
Critical for production email functionality
"""
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.messages import get_messages
from unittest.mock import patch, MagicMock, Mock
from smtplib import SMTPAuthenticationError, SMTPConnectError

from crm.models import CrmEmail, Company, Contact, Deal
from crm.utils.send_email import send_email, parse_addr
from massmail.models import EmailAccount


class ParseAddrTest(TestCase):
    """Test email address parsing utility"""

    def test_parse_single_email(self):
        """Test parsing single email address"""
        result = parse_addr("test@example.com")
        self.assertEqual(result, ["test@example.com"])

    def test_parse_multiple_emails(self):
        """Test parsing multiple email addresses"""
        result = parse_addr("test1@example.com, test2@example.com")
        self.assertEqual(len(result), 2)
        self.assertIn("test1@example.com", result)
        self.assertIn("test2@example.com", result)

    def test_parse_email_with_name(self):
        """Test parsing email with display name"""
        result = parse_addr("John Doe <john@example.com>")
        self.assertEqual(result, ["john@example.com"])

    def test_parse_mixed_format_emails(self):
        """Test parsing mixed format emails"""
        result = parse_addr("test1@example.com, John Doe <john@example.com>, test3@example.com")
        self.assertEqual(len(result), 3)
        self.assertIn("test1@example.com", result)
        self.assertIn("john@example.com", result)
        self.assertIn("test3@example.com", result)

    def test_parse_empty_string(self):
        """Test parsing empty string"""
        result = parse_addr("")
        self.assertEqual(result, [])

    def test_parse_invalid_email_filtered_out(self):
        """Test that invalid emails are filtered out"""
        result = parse_addr("test@example.com, invalid-email, john@example.com")
        # Invalid ones should be skipped
        self.assertIn("test@example.com", result)
        self.assertIn("john@example.com", result)


class SendEmailTest(TestCase):
    """Test send_email functionality"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpass123'
        )

        self.company = Company.objects.create(
            full_name="Test Company",
            email="company@example.com"
        )

        self.contact = Contact.objects.create(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            company=self.company
        )

        self.deal = Deal.objects.create(
            name="Test Deal",
            next_step_date=timezone.now().date()
        )

        # Create email account
        self.email_account = EmailAccount.objects.create(
            name="Test Account",
            from_email="sender@example.com",
            owner=self.user,
            main=True,
            email_host="smtp.example.com",
            email_host_user="sender@example.com",
            email_host_password="password123"
        )

    def _create_request(self):
        """Helper to create request with message storage"""
        request = self.factory.post('/')
        request.user = self.user
        # Add message storage
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        return request

    def test_send_email_requires_subject(self):
        """Test that email requires subject"""
        email = CrmEmail.objects.create(
            to="recipient@example.com",
            subject="",  # Empty subject
            content="Test content",
            owner=self.user
        )

        request = self._create_request()
        response = send_email(request, email)

        # Should redirect back to email edit
        self.assertEqual(response.status_code, 302)
        self.assertIn("/crm/crmemail/", response.url)

        # Should have error message
        messages_list = list(get_messages(request))
        self.assertTrue(any('subject' in str(m).lower() for m in messages_list))

    def test_send_email_requires_content(self):
        """Test that email requires content"""
        email = CrmEmail.objects.create(
            to="recipient@example.com",
            subject="Test Subject",
            content="<br>",  # Empty content (just BR tag)
            owner=self.user
        )

        request = self._create_request()
        response = send_email(request, email)

        # Should redirect back to email edit
        self.assertEqual(response.status_code, 302)

        # Should have error message
        messages_list = list(get_messages(request))
        self.assertTrue(any('text' in str(m).lower() for m in messages_list))

    def test_send_email_requires_main_email_account(self):
        """Test that sending requires a main email account"""
        # Delete the main email account
        self.email_account.delete()

        email = CrmEmail.objects.create(
            to="recipient@example.com",
            subject="Test Subject",
            content="Test content",
            owner=self.user
        )

        request = self._create_request()
        response = send_email(request, email)

        # Should redirect back to email edit
        self.assertEqual(response.status_code, 302)

        # Should have error message about email account
        messages_list = list(get_messages(request))
        self.assertTrue(any('email account' in str(m).lower() for m in messages_list))

    @patch('crm.utils.send_email.email_creator')
    def test_send_email_success(self, mock_email_creator):
        """Test successful email sending"""
        # Mock email message
        mock_msg = MagicMock()
        mock_msg.send = MagicMock(return_value=1)
        mock_email_creator.return_value = mock_msg

        email = CrmEmail.objects.create(
            to="recipient@example.com",
            subject="Test Subject",
            content="Test content",
            owner=self.user,
            contact=self.contact
        )

        request = self._create_request()
        response = send_email(request, email)

        # Email should be marked as sent
        email.refresh_from_db()
        self.assertTrue(email.sent)

        # Should redirect to email list
        self.assertIn("/crm/crmemail/", response.url)

        # Should have success message
        messages_list = list(get_messages(request))
        self.assertTrue(any('sent' in str(m).lower() for m in messages_list))

        # Email creator should be called
        mock_email_creator.assert_called_once()

    @patch('crm.utils.send_email.email_creator')
    def test_send_email_with_cc_and_bcc(self, mock_email_creator):
        """Test sending email with CC and BCC"""
        mock_msg = MagicMock()
        mock_msg.send = MagicMock(return_value=1)
        mock_email_creator.return_value = mock_msg

        email = CrmEmail.objects.create(
            to="recipient@example.com",
            cc="cc@example.com",
            bcc="bcc@example.com",
            subject="Test Subject",
            content="Test content",
            owner=self.user
        )

        request = self._create_request()
        response = send_email(request, email)

        # Check email_creator was called with CC and BCC
        call_args = mock_email_creator.call_args
        self.assertIsNotNone(call_args[0][2])  # CC
        self.assertIsNotNone(call_args[0][3])  # BCC

    @patch('crm.utils.send_email.email_creator')
    def test_send_email_adds_to_deal_workflow(self, mock_email_creator):
        """Test that sending email adds entry to deal workflow"""
        mock_msg = MagicMock()
        mock_msg.send = MagicMock(return_value=1)
        mock_email_creator.return_value = mock_msg

        email = CrmEmail.objects.create(
            to="recipient@example.com",
            subject="Deal Email",
            content="Test content",
            owner=self.user,
            deal=self.deal,
            contact=self.contact
        )

        request = self._create_request()
        send_email(request, email)

        # Deal workflow should be updated
        self.deal.refresh_from_db()
        self.assertIsNotNone(self.deal.workflow)

    @patch('crm.utils.send_email.email_creator')
    def test_send_email_smtp_authentication_error(self, mock_email_creator):
        """Test handling SMTP authentication error"""
        mock_msg = MagicMock()
        mock_msg.send.side_effect = SMTPAuthenticationError(535, "Authentication failed")
        mock_email_creator.return_value = mock_msg

        email = CrmEmail.objects.create(
            to="recipient@example.com",
            subject="Test Subject",
            content="Test content",
            owner=self.user
        )

        request = self._create_request()
        response = send_email(request, email)

        # Email should NOT be marked as sent
        email.refresh_from_db()
        self.assertFalse(email.sent)

        # Should redirect back to email edit
        self.assertIn("/crm/crmemail/", response.url)

        # Should have error message
        messages_list = list(get_messages(request))
        self.assertTrue(any('failed' in str(m).lower() for m in messages_list))

    @patch('crm.utils.send_email.email_creator')
    def test_send_email_smtp_connect_error(self, mock_email_creator):
        """Test handling SMTP connection error"""
        mock_msg = MagicMock()
        mock_msg.send.side_effect = SMTPConnectError(421, "Connection refused")
        mock_email_creator.return_value = mock_msg

        email = CrmEmail.objects.create(
            to="recipient@example.com",
            subject="Test Subject",
            content="Test content",
            owner=self.user
        )

        request = self._create_request()
        response = send_email(request, email)

        # Should handle error gracefully
        email.refresh_from_db()
        self.assertFalse(email.sent)

        # Should have error message
        messages_list = list(get_messages(request))
        self.assertTrue(any('failed' in str(m).lower() for m in messages_list))

    @patch('crm.utils.send_email.email_creator')
    def test_send_email_multiple_recipients(self, mock_email_creator):
        """Test sending to multiple recipients"""
        mock_msg = MagicMock()
        mock_msg.send = MagicMock(return_value=3)
        mock_email_creator.return_value = mock_msg

        email = CrmEmail.objects.create(
            to="recipient1@example.com, recipient2@example.com, recipient3@example.com",
            subject="Test Subject",
            content="Test content",
            owner=self.user
        )

        request = self._create_request()
        response = send_email(request, email)

        # Should succeed
        email.refresh_from_db()
        self.assertTrue(email.sent)

        # Check that TO was parsed correctly
        call_args = mock_email_creator.call_args
        # email_creator(obj, eac, to, ...) - το to είναι το 3ο positional
        to_list = call_args[0][2]
        self.assertEqual(len(to_list), 3)


class CrmEmailModelTest(TestCase):
    """Test CrmEmail model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        self.company = Company.objects.create(
            full_name="Test Company",
            email="company@example.com"
        )

        self.contact = Contact.objects.create(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            company=self.company
        )

    def test_create_crm_email(self):
        """Test creating a CRM email"""
        email = CrmEmail.objects.create(
            to="test@example.com",
            subject="Test Subject",
            content="Test content",
            owner=self.user
        )

        self.assertEqual(email.to, "test@example.com")
        self.assertEqual(email.subject, "Test Subject")
        self.assertFalse(email.sent)
        self.assertFalse(email.incoming)

    def test_crm_email_auto_set_company_from_contact(self):
        """Test that company is auto-set from contact"""
        email = CrmEmail.objects.create(
            to="test@example.com",
            subject="Test",
            content="Test",
            owner=self.user,
            contact=self.contact
            # No company specified
        )

        # Company should be auto-set from contact
        self.assertEqual(email.company, self.company)

    def test_crm_email_with_deal(self):
        """Test CRM email linked to deal"""
        deal = Deal.objects.create(
            name="Test Deal",
            next_step_date=timezone.now().date()
        )

        email = CrmEmail.objects.create(
            to="test@example.com",
            subject="Deal Email",
            content="Content",
            owner=self.user,
            deal=deal
        )

        self.assertEqual(email.deal, deal)
        self.assertIn(email, deal.deal_emails.all())

    def test_crm_email_incoming_flag(self):
        """Test incoming email flag"""
        email = CrmEmail.objects.create(
            to="test@example.com",
            from_field="sender@example.com",
            subject="Incoming Email",
            content="Content",
            owner=self.user,
            incoming=True
        )

        self.assertTrue(email.incoming)
        self.assertEqual(email.from_field, "sender@example.com")

    def test_crm_email_with_imap_metadata(self):
        """Test email with IMAP metadata"""
        email = CrmEmail.objects.create(
            to="test@example.com",
            subject="IMAP Email",
            content="Content",
            owner=self.user,
            uid=12345,
            imap_host="imap.example.com",
            email_host_user="user@example.com",
            message_id="<unique-id@example.com>"
        )

        self.assertEqual(email.uid, 12345)
        self.assertEqual(email.imap_host, "imap.example.com")
        self.assertEqual(email.message_id, "<unique-id@example.com>")

    def test_crm_email_str_representation(self):
        """Test email string representation"""
        email = CrmEmail.objects.create(
            to="test@example.com",
            subject="Test Email Subject",
            content="Content",
            owner=self.user
        )

        self.assertEqual(str(email), "Test Email Subject")

    def test_crm_email_absolute_url(self):
        """Test email absolute URL"""
        email = CrmEmail.objects.create(
            to="test@example.com",
            subject="Test",
            content="Content",
            owner=self.user
        )

        url = email.get_absolute_url()
        self.assertIn("/crm/crmemail/", url)
        self.assertIn(str(email.id), url)
