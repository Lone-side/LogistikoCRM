# -*- coding: utf-8 -*-
"""
Portal invite email: when a client gets a portal account, they receive an email
with a set-password link (uid+token) pointing at the frontend PORTAL_URL.
"""
from django.core import mail
from django.test import TestCase, override_settings

from accounting.models import ClientProfile
from accounting.services.email_service import EmailService


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PORTAL_URL='https://portal.example.gr',
)
class PortalInviteEmailTest(TestCase):
    def setUp(self):
        mail.outbox = []
        self.client_p = ClientProfile.objects.create(
            afm='123456783', eponimia='ΔΟΚΙΜΗ ΑΕ',
            eidos_ipoxreou='company', email='client@example.gr')

    def test_invite_sends_email_with_setpassword_link(self):
        user = self.client_p.create_portal_user()
        ok = EmailService.send_portal_invite(self.client_p)

        self.assertTrue(ok)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['client@example.gr'])
        # Link points at the frontend set-password page with uid+token.
        link = self.client_p.get_password_set_link(base_url='https://portal.example.gr')
        self.assertIn('https://portal.example.gr/set-password?uid=', msg.body)
        self.assertIn('token=', msg.body)
        # The uid in the email matches this user's uid.
        self.assertIn(link['uid'], msg.body)
        # Greek, client-addressed subject.
        self.assertIn('ΔΟΚΙΜΗ ΑΕ', msg.body + msg.subject)

    def test_invite_fails_gracefully_without_email(self):
        self.client_p.email = ''
        self.client_p.save(update_fields=['email'])
        self.client_p.create_portal_user()
        ok = EmailService.send_portal_invite(self.client_p)
        self.assertFalse(ok)
        self.assertEqual(len(mail.outbox), 0)

    def test_invite_requires_portal_user(self):
        # No portal user yet → cannot build a link → no email.
        ok = EmailService.send_portal_invite(self.client_p)
        self.assertFalse(ok)
        self.assertEqual(len(mail.outbox), 0)
