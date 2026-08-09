# tests/crm/views/test_public_form_protection.py
"""
Regression tests για την anti-abuse προστασία των public CRM intake
endpoints (P1-02):

- reCAPTCHA fail-closed: configured reCAPTCHA δεν παρακάμπτεται με
  παράλειψη του token· provider timeout/network/malformed response
  απορρίπτουν τη φόρμα· μερική key configuration = configuration error.
- Cache-backed rate limiting (30/hour default, configurable) και στα
  δύο endpoints, ανά client IP, χωρίς εμπιστοσύνη σε αυθαίρετο
  X-Forwarded-For όταν δεν υπάρχει proxy configuration.

Κανένα πραγματικό request προς την Google — το requests.post γίνεται
πάντα mock.
"""
from unittest.mock import patch

import requests as requests_lib
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings, tag
from django.urls import reverse

from common.models import Department
from crm.models import CrmEmail, Request
from crm.models.others import LeadSource
from crm.views.add_request import add_request
from tests.base_test_classes import BaseTestCase

# manage.py test tests.crm.views.test_public_form_protection --keepdb


def make_request_data(leadsource_token):
    return {
        'name': 'Γιώργος Παπαδόπουλος',
        'email': 'giorgos@example.com',
        'subject': 'test inquiry',
        'phone': '+302101234567',
        'message': 'test message',
        'country': '',
        'city': '',
        'company': 'Εταιρεία ΕΠΕ',
        'leadsource_token': leadsource_token,
    }


class PublicFormProtectionTestCase(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        department = Department.objects.get(name='Global sales')
        cls.ls = LeadSource.objects.create(name='', department=department)
        # Το iframe view χρειάζεται LeadSource με πραγματικά templates.
        cls.iframe_ls = LeadSource.objects.filter(
            name="website form (iframe)").first()
        cls.add_request_url = reverse(add_request)
        cls.contact_form_url = reverse(
            'contact_form', args=(cls.iframe_ls.uuid,))

    def setUp(self):
        # Τα throttle counters ζουν στο cache και δεν γίνονται rollback
        # με τη βάση — καθάρισμα για test isolation.
        cache.clear()
        mail.outbox = []
        self.data = make_request_data(self.ls.uuid)

    def assert_no_intake_writes(self):
        self.assertEqual(Request.objects.count(), 0)
        self.assertEqual(CrmEmail.objects.count(), 0)


@tag('TestCase')
class RecaptchaFailClosedTest(PublicFormProtectionTestCase):
    """Configured reCAPTCHA πρέπει να αποτυγχάνει κλειστά."""

    RECAPTCHA_ON = {
        'GOOGLE_RECAPTCHA_SITE_KEY': 'test-site-key',
        'GOOGLE_RECAPTCHA_SECRET_KEY': 'test-secret-key',
    }

    def test_missing_token_rejected_no_db_write(self):
        """Configured reCAPTCHA + λείπει το token ⇒ reject, μηδέν writes."""
        with override_settings(**self.RECAPTCHA_ON), \
                patch('crm.forms.contact_form.requests.post') as mock_post:
            response = self.client.post(self.add_request_url, self.data)
            # Χωρίς token δεν πρέπει καν να κληθεί ο provider.
            mock_post.assert_not_called()
        self.assertEqual(response.status_code, 409)
        self.assert_no_intake_writes()

    def test_missing_token_rejected_on_contact_form(self):
        with override_settings(**self.RECAPTCHA_ON), \
                patch('crm.forms.contact_form.requests.post') as mock_post:
            response = self.client.post(self.contact_form_url, self.data)
            mock_post.assert_not_called()
        # Το iframe view ξανασερβίρει τη φόρμα (200) χωρίς να γράψει τίποτα.
        self.assertEqual(response.status_code, 200)
        self.assert_no_intake_writes()

    def test_invalid_token_rejected(self):
        self.data['g-recaptcha-response'] = 'invalid-token'
        with override_settings(**self.RECAPTCHA_ON), \
                patch('crm.forms.contact_form.requests.post') as mock_post:
            mock_post.return_value.json.return_value = {'success': False}
            response = self.client.post(self.add_request_url, self.data)
            mock_post.assert_called_once()
        self.assertEqual(response.status_code, 409)
        self.assert_no_intake_writes()

    def test_verification_timeout_fails_closed(self):
        self.data['g-recaptcha-response'] = 'a-token'
        with override_settings(**self.RECAPTCHA_ON), \
                patch('crm.forms.contact_form.requests.post') as mock_post:
            mock_post.side_effect = requests_lib.Timeout('timed out')
            response = self.client.post(self.add_request_url, self.data)
        self.assertEqual(response.status_code, 409)
        self.assert_no_intake_writes()

    def test_verification_network_error_fails_closed(self):
        self.data['g-recaptcha-response'] = 'a-token'
        with override_settings(**self.RECAPTCHA_ON), \
                patch('crm.forms.contact_form.requests.post') as mock_post:
            mock_post.side_effect = requests_lib.ConnectionError('down')
            response = self.client.post(self.add_request_url, self.data)
        self.assertEqual(response.status_code, 409)
        self.assert_no_intake_writes()

    def test_malformed_provider_json_fails_closed(self):
        self.data['g-recaptcha-response'] = 'a-token'
        with override_settings(**self.RECAPTCHA_ON), \
                patch('crm.forms.contact_form.requests.post') as mock_post:
            mock_post.return_value.json.side_effect = ValueError('not json')
            response = self.client.post(self.add_request_url, self.data)
        self.assertEqual(response.status_code, 409)
        self.assert_no_intake_writes()

    def test_non_dict_provider_payload_fails_closed(self):
        self.data['g-recaptcha-response'] = 'a-token'
        with override_settings(**self.RECAPTCHA_ON), \
                patch('crm.forms.contact_form.requests.post') as mock_post:
            mock_post.return_value.json.return_value = ['unexpected']
            response = self.client.post(self.add_request_url, self.data)
        self.assertEqual(response.status_code, 409)
        self.assert_no_intake_writes()

    def test_missing_success_key_fails_closed(self):
        self.data['g-recaptcha-response'] = 'a-token'
        with override_settings(**self.RECAPTCHA_ON), \
                patch('crm.forms.contact_form.requests.post') as mock_post:
            mock_post.return_value.json.return_value = {}
            response = self.client.post(self.add_request_url, self.data)
        self.assertEqual(response.status_code, 409)
        self.assert_no_intake_writes()

    def test_valid_token_passes_and_uses_timeout(self):
        """Έγκυρο token ⇒ επιτυχία, με explicit timeout στο request."""
        self.data['g-recaptcha-response'] = 'valid-token'
        with override_settings(**self.RECAPTCHA_ON), \
                patch('crm.forms.contact_form.requests.post') as mock_post:
            mock_post.return_value.json.return_value = {'success': True}
            response = self.client.post(self.add_request_url, self.data)
            mock_post.assert_called_once()
            self.assertIn('timeout', mock_post.call_args.kwargs)
            self.assertGreater(mock_post.call_args.kwargs['timeout'], 0)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Request.objects.count(), 1)

    def test_partial_configuration_is_configuration_error(self):
        """Μόνο ένα key ορισμένο ⇒ καθαρό configuration failure."""
        from crm.forms.contact_form import ContactForm

        for site_key, secret_key in (('test-site-key', ''),
                                     ('', 'test-secret-key')):
            with override_settings(GOOGLE_RECAPTCHA_SITE_KEY=site_key,
                                   GOOGLE_RECAPTCHA_SECRET_KEY=secret_key):
                form = ContactForm(self.data)
                with self.assertRaises(ImproperlyConfigured):
                    form.is_valid()

    def test_unconfigured_recaptcha_keeps_existing_behavior(self):
        """Χωρίς keys η φόρμα περνά χωρίς token (υφιστάμενη συμπεριφορά)."""
        with override_settings(GOOGLE_RECAPTCHA_SITE_KEY='',
                               GOOGLE_RECAPTCHA_SECRET_KEY=''), \
                patch('crm.forms.contact_form.requests.post') as mock_post:
            response = self.client.post(self.add_request_url, self.data)
            mock_post.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Request.objects.count(), 1)


@tag('TestCase')
@override_settings(PUBLIC_FORM_THROTTLE_RATE='3/hour')
class PublicFormThrottleTest(PublicFormProtectionTestCase):
    """Cache-backed throttle ανά client IP και endpoint."""

    def post_add_request(self, **extra):
        return self.client.post(self.add_request_url, self.data, **extra)

    def test_requests_up_to_limit_allowed(self):
        for _ in range(3):
            response = self.post_add_request()
            self.assertEqual(response.status_code, 200)
        self.assertEqual(Request.objects.count(), 3)

    def test_request_over_limit_gets_429_and_no_writes(self):
        for _ in range(3):
            self.assertEqual(self.post_add_request().status_code, 200)
        writes_before = Request.objects.count()
        emails_before = CrmEmail.objects.count()
        outbox_before = len(mail.outbox)

        response = self.post_add_request()

        self.assertEqual(response.status_code, 429)
        # Generic response χωρίς εσωτερικές πληροφορίες.
        self.assertEqual(response.content, b'')
        # Κανένα νέο Request, CrmEmail ή notification.
        self.assertEqual(Request.objects.count(), writes_before)
        self.assertEqual(CrmEmail.objects.count(), emails_before)
        self.assertEqual(len(mail.outbox), outbox_before)

    def test_contact_form_post_throttled_too(self):
        for _ in range(3):
            response = self.client.post(self.contact_form_url, self.data)
            self.assertEqual(response.status_code, 200)
        response = self.client.post(self.contact_form_url, self.data)
        self.assertEqual(response.status_code, 429)

    def test_contact_form_get_not_throttled(self):
        """Το GET (render του iframe) δεν καταναλώνει/χτυπά το όριο."""
        for _ in range(5):
            response = self.client.get(self.contact_form_url)
            self.assertEqual(response.status_code, 200)

    def test_endpoints_have_separate_counters(self):
        """Το όριο μετράει ανά endpoint/source."""
        for _ in range(3):
            self.assertEqual(self.post_add_request().status_code, 200)
        self.assertEqual(self.post_add_request().status_code, 429)
        # Το contact_form έχει δικό του counter και ακόμη επιτρέπεται.
        response = self.client.post(self.contact_form_url, self.data)
        self.assertEqual(response.status_code, 200)

    def test_separate_ips_do_not_share_counter(self):
        for _ in range(3):
            self.assertEqual(
                self.post_add_request(REMOTE_ADDR='10.0.0.1').status_code, 200
            )
        self.assertEqual(
            self.post_add_request(REMOTE_ADDR='10.0.0.1').status_code, 429
        )
        # Άλλη IP: δικός της counter.
        self.assertEqual(
            self.post_add_request(REMOTE_ADDR='10.0.0.2').status_code, 200
        )

    def test_spoofed_xff_does_not_bypass_without_proxy_config(self):
        """
        Χωρίς NUM_PROXIES configuration, αυθαίρετο X-Forwarded-For δεν
        δίνει νέο counter — μετράει μόνο το REMOTE_ADDR.
        """
        for i in range(3):
            response = self.post_add_request(
                REMOTE_ADDR='10.0.0.9',
                HTTP_X_FORWARDED_FOR=f'1.2.3.{i}',
            )
            self.assertEqual(response.status_code, 200)
        response = self.post_add_request(
            REMOTE_ADDR='10.0.0.9',
            HTTP_X_FORWARDED_FOR='5.6.7.8',
        )
        self.assertEqual(response.status_code, 429)

    def test_default_rate_is_30_per_hour(self):
        from crm.utils.public_rate_limit import (
            DEFAULT_PUBLIC_FORM_THROTTLE_RATE,
            PublicFormRateThrottle,
        )
        self.assertEqual(DEFAULT_PUBLIC_FORM_THROTTLE_RATE, '30/hour')
        with override_settings(PUBLIC_FORM_THROTTLE_RATE='30/hour'):
            throttle = PublicFormRateThrottle('add_request')
            self.assertEqual(throttle.num_requests, 30)
            self.assertEqual(throttle.duration, 3600)
