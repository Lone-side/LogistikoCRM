# -*- coding: utf-8 -*-
"""
Regression tests: άκυρο client input πρέπει να επιστρέφει 400 (ή clamped
αποτέλεσμα), ποτέ 500.
"""
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounting.models import ClientProfile


class InvalidInputAPITest(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@test.com', password='adminpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.test_client = ClientProfile.objects.create(
            afm="123456782",
            eponimia="Test Company",
            eidos_ipoxreou="company",
            doy="A' ΑΘΗΝΩΝ",
        )

    # 1. vat_summary
    def test_vat_summary_invalid_year(self):
        response = self.client.get('/accounting/api/reports/vat-summary/?year=abc')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_vat_summary_invalid_period(self):
        response = self.client.get('/accounting/api/reports/vat-summary/?period=abc')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_vat_summary_out_of_range_period(self):
        response = self.client.get('/accounting/api/reports/vat-summary/?period=13')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # 2. dashboard calendar (clamp)
    def test_dashboard_calendar_out_of_range_year(self):
        response = self.client.get('/accounting/api/dashboard/calendar/?year=99999')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_dashboard_calendar_zero_year(self):
        response = self.client.get('/accounting/api/dashboard/calendar/?year=0')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # 3. obligations calendar action
    def test_obligations_calendar_invalid_year(self):
        response = self.client.get('/accounting/api/v1/obligations/calendar/?year=abc')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_obligations_calendar_out_of_range_year(self):
        response = self.client.get('/accounting/api/v1/obligations/calendar/?year=0')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # 4. bulk_create
    def test_bulk_create_invalid_month(self):
        response = self.client.post(
            '/accounting/api/v1/obligations/bulk_create/',
            {'client_ids': [self.test_client.id], 'obligation_type': 999,
             'month': 'abc', 'year': 2025},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_create_out_of_range_month(self):
        response = self.client.post(
            '/accounting/api/v1/obligations/bulk_create/',
            {'client_ids': [self.test_client.id], 'obligation_type': 999,
             'month': 13, 'year': 2025},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_create_out_of_range_year(self):
        response = self.client.post(
            '/accounting/api/v1/obligations/bulk_create/',
            {'client_ids': [self.test_client.id], 'obligation_type': 999,
             'month': 1, 'year': 99999},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # 5. generate-month
    def test_generate_month_out_of_range_year(self):
        response = self.client.post(
            '/accounting/api/v1/obligations/generate-month/',
            {'month': 1, 'year': 99999},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # 6. email history pagination (defaults)
    def test_email_history_invalid_pagination(self):
        response = self.client.get(
            '/accounting/api/v1/email/history/?page=abc&page_size=abc'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['page'], 1)
        self.assertEqual(response.data['page_size'], 20)

    # 7. client documents
    def test_client_documents_invalid_year(self):
        response = self.client.get(
            f'/accounting/api/v1/clients/{self.test_client.id}/documents/?year=abc'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_client_documents_invalid_month(self):
        response = self.client.get(
            f'/accounting/api/v1/clients/{self.test_client.id}/documents/?month=abc'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # 8-9. client emails / calls pagination (defaults)
    def test_client_emails_invalid_pagination(self):
        response = self.client.get(
            f'/accounting/api/v1/clients/{self.test_client.id}/emails/?page=abc&page_size=abc'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['page'], 1)

    def test_client_calls_invalid_pagination(self):
        response = self.client.get(
            f'/accounting/api/v1/clients/{self.test_client.id}/calls/?page=abc&page_size=-3'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # 10. file manager recent
    def test_recent_documents_invalid_limit(self):
        response = self.client.get('/accounting/api/v1/file-manager/recent/?limit=abc')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_recent_documents_negative_limit(self):
        response = self.client.get('/accounting/api/v1/file-manager/recent/?limit=-5')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # 11. file manager browse
    def test_browse_folders_invalid_client_id(self):
        response = self.client.get('/accounting/api/v1/file-manager/browse/?client_id=abc')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_browse_folders_invalid_year(self):
        response = self.client.get(
            f'/accounting/api/v1/file-manager/browse/?client_id={self.test_client.id}&year=abc'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_browse_folders_invalid_month(self):
        response = self.client.get(
            f'/accounting/api/v1/file-manager/browse/?client_id={self.test_client.id}&year=2025&month=abc'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # 12. door logs
    def test_door_logs_invalid_limit(self):
        response = self.client.get('/accounting/api/v1/door/logs/?limit=abc')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
