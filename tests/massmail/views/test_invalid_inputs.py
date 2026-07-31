from django.test import tag
from django.urls import reverse

from common.utils.helpers import USER_MODEL
from tests.base_test_classes import BaseTestCase

# manage.py test tests.massmail.views.test_invalid_inputs --keepdb

NONEXISTENT_ID = 2147483647


@tag('TestCase')
class TestInvalidInputs(BaseTestCase):
    """Invalid client input must return 400/404, not 500."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = USER_MODEL.objects.get(username="Adam.Admin")

    def setUp(self):
        print("Run Test Method:", self._testMethodName)
        self.client.force_login(self.user)

    def test_message_preview_nonexistent(self):
        url = reverse("message_preview", args=(NONEXISTENT_ID,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_signature_preview_invalid_id(self):
        url = reverse("signature_preview") + "?signature=abc"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

    def test_signature_preview_nonexistent(self):
        url = reverse("signature_preview") + f"?signature={NONEXISTENT_ID}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_copy_message_nonexistent(self):
        url = reverse("copy_message", args=(NONEXISTENT_ID,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_exclude_recipients_nonexistent(self):
        url = reverse("exclude_recipients", args=(NONEXISTENT_ID,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_view_recipient_ids_nonexistent(self):
        url = reverse("successful_ids", args=(NONEXISTENT_ID,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_send_failed_recipients_nonexistent(self):
        url = reverse("send_failed_recipients", args=(NONEXISTENT_ID,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_send_test_nonexistent(self):
        url = reverse("send_test", args=(NONEXISTENT_ID,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_request_authorization_code_nonexistent(self):
        url = reverse("request_authorization_code", args=(NONEXISTENT_ID,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_get_refresh_token_unknown_account(self):
        url = reverse("get_refresh_token") + "?user=unknown@example.com"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
