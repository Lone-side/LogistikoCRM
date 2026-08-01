# -*- coding: utf-8 -*-
"""
Tests για τα κρίσιμα fixes του code review:
- Cross-client guard στο document upload
- Atomic claim στα scheduled emails
"""
from django.contrib.auth.models import User
from tests.utils.helpers import grant_accounting_model_perms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from accounting.models import (
    ClientProfile, MonthlyObligation, ObligationType, ScheduledEmail,
)


class UploadCrossClientGuardTest(TestCase):
    """Το upload δεν πρέπει να δέχεται υποχρέωση άλλου πελάτη."""

    def setUp(self):
        user = grant_accounting_model_perms(User.objects.create_user('tester', password='x', is_staff=True))
        self.client.force_login(user)

        self.client_a = ClientProfile.objects.create(
            afm='123456789', eponimia='ΠΕΛΑΤΗΣ Α'
        )
        self.client_b = ClientProfile.objects.create(
            afm='987654321', eponimia='ΠΕΛΑΤΗΣ Β'
        )
        obligation_type = ObligationType.objects.create(
            name='ΦΠΑ', code='FPA', frequency='monthly'
        )
        self.obligation_b = MonthlyObligation.objects.create(
            client=self.client_b,
            obligation_type=obligation_type,
            year=2026, month=7,
            deadline=timezone.now().date(),
        )

    def _upload(self, client_id, obligation_id):
        return self.client.post(
            '/accounting/api/v1/documents/upload/',
            {
                'file': SimpleUploadedFile(
                    'test.pdf', b'%PDF-1.4 test', content_type='application/pdf'
                ),
                'client_id': client_id,
                'obligation_id': obligation_id,
            },
        )

    def test_obligation_of_other_client_rejected(self):
        response = self._upload(self.client_a.id, self.obligation_b.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn('διαφορετικό πελάτη', response.json()['error'])

    def test_obligation_of_same_client_accepted(self):
        response = self._upload(self.client_b.id, self.obligation_b.id)
        self.assertEqual(response.status_code, 201)


class ScheduledEmailClaimTest(TestCase):
    """Το process_scheduled_emails δεν πρέπει να ξαναστέλνει claimed emails."""

    def _make_email(self, status='pending'):
        return ScheduledEmail.objects.create(
            recipient_email='a@example.com',
            recipient_name='Α',
            subject='Δοκιμή',
            body_html='<p>Γεια</p>',
            send_at=timezone.now() - timezone.timedelta(minutes=5),
            status=status,
        )

    def test_pending_email_sent_and_marked(self):
        from accounting.tasks import process_scheduled_emails

        email = self._make_email()
        process_scheduled_emails()
        email.refresh_from_db()
        self.assertEqual(email.status, 'sent')

    def test_already_claimed_email_skipped(self):
        from unittest.mock import patch
        from accounting.tasks import process_scheduled_emails

        email = self._make_email()
        # Προσομοίωση δεύτερου worker που πρόλαβε το claim: το status
        # αλλάζει σε 'sending' αφού έγινε το αρχικό queryset fetch
        ScheduledEmail.objects.filter(pk=email.pk).update(status='sending')

        with patch('django.core.mail.EmailMessage.send') as mock_send:
            process_scheduled_emails()
            mock_send.assert_not_called()

        email.refresh_from_db()
        self.assertEqual(email.status, 'sending')
