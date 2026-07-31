from django.contrib.contenttypes.models import ContentType
from django.test import tag
from django.urls import reverse

from common.utils.helpers import USER_MODEL
from crm.models import Country
from tests.base_test_classes import BaseTestCase

# manage.py test tests.common.views.test_invalid_inputs --keepdb

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

    def test_copy_department_missing_id(self):
        response = self.client.post(reverse("copy_department"), {})
        self.assertEqual(response.status_code, 400)

    def test_copy_department_invalid_id(self):
        response = self.client.post(
            reverse("copy_department"), {'department': 'abc'})
        self.assertEqual(response.status_code, 400)

    def test_copy_department_nonexistent(self):
        response = self.client.post(
            reverse("copy_department"), {'department': NONEXISTENT_ID})
        self.assertEqual(response.status_code, 404)

    def test_user_transfer_missing_ids(self):
        response = self.client.post(reverse("user_transfer"), {})
        self.assertEqual(response.status_code, 400)

    def test_user_transfer_invalid_ids(self):
        response = self.client.post(
            reverse("user_transfer"),
            {'owner': 'abc', 'department': 'abc'}
        )
        self.assertEqual(response.status_code, 400)

    def test_user_transfer_nonexistent_owner(self):
        response = self.client.post(
            reverse("user_transfer"),
            {'owner': NONEXISTENT_ID, 'department': NONEXISTENT_ID}
        )
        self.assertEqual(response.status_code, 404)

    def test_select_emails_import_post_missing_ea_id(self):
        response = self.client.post(
            reverse("select_emails_import_request"), {})
        self.assertEqual(response.status_code, 400)

    def test_select_emails_import_post_invalid_ea_id(self):
        response = self.client.post(
            reverse("select_emails_import_request"), {'ea_id': 'abc'})
        self.assertEqual(response.status_code, 400)

    def test_select_emails_import_post_nonexistent_ea(self):
        response = self.client.post(
            reverse("select_emails_import_request"),
            {'ea_id': NONEXISTENT_ID}
        )
        self.assertEqual(response.status_code, 404)

    def test_select_emails_import_get_invalid_ea(self):
        response = self.client.get(
            reverse("select_emails_import_request") + "?ea=abc")
        self.assertEqual(response.status_code, 400)

    def test_select_emails_import_get_nonexistent_ea(self):
        response = self.client.get(
            reverse("select_emails_import_request") + f"?ea={NONEXISTENT_ID}")
        self.assertEqual(response.status_code, 404)

    def test_select_email_account_get_without_eas(self):
        response = self.client.get(reverse("select_email_account"))
        self.assertEqual(response.status_code, 400)

    def test_toggle_default_sorting_unknown_model(self):
        response = self.client.get(
            reverse("toggle_default_sorting"),
            {'model': 'Unknown', 'next_url': '/'}
        )
        self.assertEqual(response.status_code, 400)

    def test_toggle_default_sorting_missing_next_url(self):
        response = self.client.get(
            reverse("toggle_default_sorting"), {'model': 'Task'})
        self.assertEqual(response.status_code, 400)

    def test_export_objects_invalid_content_type(self):
        response = self.client.get(
            reverse("export_objects") + "?content_type=abc")
        self.assertEqual(response.status_code, 400)

    def test_export_objects_missing_content_type(self):
        response = self.client.get(reverse("export_objects"))
        self.assertEqual(response.status_code, 400)

    def test_export_objects_nonexistent_content_type(self):
        response = self.client.get(
            reverse("export_objects") + f"?content_type={NONEXISTENT_ID}")
        self.assertEqual(response.status_code, 404)

    def test_export_objects_unsupported_content_type(self):
        ct = ContentType.objects.get_for_model(Country)
        response = self.client.get(
            reverse("export_objects") + f"?content_type={ct.id}")
        self.assertEqual(response.status_code, 400)
