# -*- coding: utf-8 -*-
"""
Tests για τις διορθώσεις του security review:
- Fritz token: απόρριψη default, μόνο header, constant-time σύγκριση
- Admin-gating στα destroy πελατών/υποχρεώσεων
- Throttle μόνο στο POST του public portal
- Escape σε chat admin και «Προβολή αρχικού email»
"""
import json
from datetime import date

from django.contrib.auth.models import User
from tests.utils.helpers import grant_accounting_model_perms
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.utils.safestring import SafeString
from rest_framework.test import APIRequestFactory

from accounting.models import ClientProfile, MonthlyObligation, ObligationType
from accounting.permissions import INSECURE_DEFAULT_TOKEN, IsVoIPMonitor

FRITZ_URL = '/accounting/api/fritz-webhook/'
VALID_TOKEN = 'a-long-random-test-token-1234567890'


class IsVoIPMonitorTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.perm = IsVoIPMonitor()

    @override_settings(FRITZ_API_TOKEN=VALID_TOKEN)
    def test_valid_header_granted(self):
        request = self.factory.get('/', HTTP_X_API_KEY=VALID_TOKEN)
        self.assertTrue(self.perm.has_permission(request, None))

    @override_settings(FRITZ_API_TOKEN=VALID_TOKEN)
    def test_query_param_no_longer_accepted(self):
        request = self.factory.get(f'/?api_key={VALID_TOKEN}')
        self.assertFalse(self.perm.has_permission(request, None))

    @override_settings(FRITZ_API_TOKEN=INSECURE_DEFAULT_TOKEN)
    def test_default_token_always_denied(self):
        request = self.factory.get('/', HTTP_X_API_KEY=INSECURE_DEFAULT_TOKEN)
        self.assertFalse(self.perm.has_permission(request, None))

    @override_settings(FRITZ_API_TOKEN=VALID_TOKEN)
    def test_wrong_token_denied(self):
        request = self.factory.get('/', HTTP_X_API_KEY='wrong')
        self.assertFalse(self.perm.has_permission(request, None))


class FritzWebhookTest(TestCase):
    @override_settings(FRITZ_API_TOKEN=INSECURE_DEFAULT_TOKEN)
    def test_default_token_is_server_misconfiguration(self):
        resp = self.client.post(
            FRITZ_URL, data='{}', content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {INSECURE_DEFAULT_TOKEN}',
        )
        self.assertEqual(resp.status_code, 500)

    @override_settings(FRITZ_API_TOKEN=VALID_TOKEN)
    def test_wrong_token_unauthorized(self):
        resp = self.client.post(
            FRITZ_URL, data='{}', content_type='application/json',
            HTTP_AUTHORIZATION='Bearer wrong',
        )
        self.assertEqual(resp.status_code, 401)

    @override_settings(FRITZ_API_TOKEN=VALID_TOKEN)
    def test_valid_token_passes_auth(self):
        resp = self.client.post(
            FRITZ_URL,
            data=json.dumps({'action': 'unknown'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {VALID_TOKEN}',
        )
        # Περνά το auth — ό,τι κι αν επιστρέψει το business logic, όχι 401/500
        self.assertNotIn(resp.status_code, (401, 500))


class DestroyRequiresAdminTest(TestCase):
    def setUp(self):
        self.staff = grant_accounting_model_perms(User.objects.create_user(
            'plain-staff', 'staff@office.gr', 'pass12345', is_staff=False
        ))
        self.admin = User.objects.create_user(
            'admin-staff', 'admin@office.gr', 'pass12345', is_staff=True
        )
        self.crm_client = ClientProfile.objects.create(
            afm='123456783', eponimia='ΠΕΛΑΤΗΣ ΑΕ', eidos_ipoxreou='company',
        )
        self.obl_type = ObligationType.objects.create(
            code='TEST_FPA', name='ΦΠΑ Test', frequency='monthly',
        )
        self.obligation = MonthlyObligation.objects.create(
            client=self.crm_client, obligation_type=self.obl_type,
            year=2026, month=7, deadline=date(2026, 7, 20),
        )

    def test_non_admin_cannot_delete_client(self):
        self.client.force_login(self.staff)
        resp = self.client.delete(f'/accounting/api/v1/clients/{self.crm_client.pk}/')
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(ClientProfile.objects.filter(pk=self.crm_client.pk).exists())

    def test_admin_can_delete_client(self):
        self.client.force_login(self.admin)
        resp = self.client.delete(f'/accounting/api/v1/clients/{self.crm_client.pk}/')
        self.assertEqual(resp.status_code, 204)

    def test_non_admin_cannot_delete_obligation(self):
        self.client.force_login(self.staff)
        resp = self.client.delete(f'/accounting/api/v1/obligations/{self.obligation.pk}/')
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_delete_obligation(self):
        self.client.force_login(self.admin)
        resp = self.client.delete(f'/accounting/api/v1/obligations/{self.obligation.pk}/')
        self.assertEqual(resp.status_code, 204)

    def test_non_admin_can_still_update(self):
        self.client.force_login(self.staff)
        resp = self.client.patch(
            f'/accounting/api/v1/obligations/{self.obligation.pk}/',
            data=json.dumps({'status': 'completed'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)


class SharedLinkAuthThrottleTest(TestCase):
    def test_get_is_not_throttled(self):
        from accounting.api_file_manager import SharedLinkAuthThrottle

        class FakeView:
            throttle_scope = 'shared_link_auth'

        factory = APIRequestFactory()
        throttle = SharedLinkAuthThrottle()
        request = factory.get('/share/x/')
        self.assertTrue(throttle.allow_request(request, FakeView()))


class XssEscapingTest(TestCase):
    def test_chat_admin_escapes_message_content(self):
        from chat.site.chatmessageadmin import ChatMessageAdmin

        class Obj:
            content = '<script>alert(1)</script>'
            answer_to = None

        html = ChatMessageAdmin.message(Obj())
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_email_template_sandboxes_body(self):
        payload = '<script>alert("xss")</script>'
        html = render_to_string('crm/email.html', {
            'subject': 'Test', 'from_field': 'a@b.gr', 'date': '',
            'to': 'c@d.gr', 'cc': '', 'body': payload, 'attachments': [],
        })
        self.assertIn('sandbox', html)
        self.assertIn('srcdoc', html)
        # Το script δεν εμφανίζεται raw στη σελίδα — μόνο escaped μέσα στο attribute
        self.assertNotIn(payload, html)

    def test_view_original_email_body_not_marked_safe(self):
        from email.message import EmailMessage
        from crm.views.view_original_email import get_context

        msg = EmailMessage()
        msg['From'] = 'a@b.gr'
        msg['To'] = 'c@d.gr'
        msg['Subject'] = 'Test'
        msg.set_content('plain')
        msg.add_alternative('<script>alert(1)</script>', subtype='html')

        context, err = get_context(msg)
        self.assertFalse(err)
        self.assertNotIsInstance(context['body'], SafeString)
