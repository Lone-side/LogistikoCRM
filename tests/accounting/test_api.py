"""
API Tests for Accounting app REST endpoints
Tests for: ClientProfile API, ObligationType API, Health Check endpoints
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from accounting.models import ClientProfile, ObligationType, MonthlyObligation


class ClientAPITest(APITestCase):
    """Test Client REST API endpoints"""

    def setUp(self):
        # Staff user — το CRM API είναι staff-only (μετά το client-portal
        # default-deny, ένας μη-staff μη-client χρήστης δεν βλέπει δεδομένα).
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            is_staff=True,
        )
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='adminpass123'
        )
        self.client = APIClient()

        # Create test client profile
        self.test_client = ClientProfile.objects.create(
            afm="123456783",  # Valid checksum
            eponimia="Test Company",
            eidos_ipoxreou="company",
            doy="A' ΑΘΗΝΩΝ"
        )

    def test_list_clients_unauthenticated(self):
        """Test that unauthenticated users cannot access client list"""
        response = self.client.get('/accounting/api/v1/clients/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_clients_authenticated(self):
        """Test that authenticated users can list clients"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/accounting/api/v1/clients/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_client_detail(self):
        """Test retrieving client detail"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/accounting/api/v1/clients/{self.test_client.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['afm'], '123456783')

    def test_client_search(self):
        """Test client search by AFM"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/accounting/api/v1/clients/?search=123456')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_client_with_valid_afm(self):
        """Test creating client with valid AFM"""
        self.client.force_authenticate(user=self.user)
        data = {
            'afm': '094160855',  # Valid checksum (distinct from setUp client)
            'eponimia': 'New Company',
            'eidos_ipoxreou': 'company',
        }
        response = self.client.post('/accounting/api/v1/clients/', data)
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])


class ObligationAPITest(APITestCase):
    """Test Obligation REST API endpoints"""

    def setUp(self):
        # Staff user: αυτά είναι staff-facing management endpoints (obligations,
        # obligation-types catalog). Το obligation-types είναι πλέον IsStaffUser.
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            is_staff=True,
        )
        self.client_api = APIClient()

        # Create test data
        self.test_client = ClientProfile.objects.create(
            afm="123456783",
            eponimia="Test Company",
            eidos_ipoxreou="company"
        )
        self.obligation_type = ObligationType.objects.create(
            code="VAT",
            name="ΦΠΑ",
            frequency="monthly",
            deadline_type="fixed_day",
            deadline_day=20
        )

    def test_list_obligations(self):
        """Test listing obligations"""
        self.client_api.force_authenticate(user=self.user)
        response = self.client_api.get('/accounting/api/v1/obligations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_obligation_types(self):
        """Test listing obligation types"""
        self.client_api.force_authenticate(user=self.user)
        response = self.client_api.get('/accounting/api/v1/obligation-types/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class HealthCheckAPITest(APITestCase):
    """Test Health Check API endpoints"""

    def test_basic_health_check(self):
        """Test basic health check endpoint (public)"""
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
        self.assertIn('version', response.data)

    def test_health_live(self):
        """Test liveness probe"""
        response = self.client.get('/api/health/live/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('alive'))

    def test_health_ready(self):
        """Test readiness probe"""
        response = self.client.get('/api/health/ready/')
        # Should return 200 if database is connected
        self.assertIn(response.status_code, [200, 503])

    def test_health_detailed_requires_auth(self):
        """Test that detailed health check requires admin auth"""
        response = self.client.get('/api/health/detailed/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_health_detailed_admin(self):
        """Test detailed health check with admin user"""
        admin = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='adminpass123'
        )
        self.client.force_authenticate(user=admin)
        response = self.client.get('/api/health/detailed/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('components', response.data)
        self.assertIn('database', response.data['components'])


class DoorAccessLogAPITest(APITestCase):
    """Test Door Access Log API endpoints"""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='adminpass123'
        )
        self.regular_user = User.objects.create_user(
            username='user',
            email='user@test.com',
            password='userpass123'
        )

    def test_door_status_requires_auth(self):
        """Test that door status requires authentication"""
        response = self.client.get('/accounting/api/v1/door/status/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_door_open_requires_admin(self):
        """Test that door open requires admin privileges"""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post('/accounting/api/v1/door/open/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_door_logs_requires_admin(self):
        """Test that door logs endpoint requires admin"""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/accounting/api/v1/door/logs/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class FileValidationTest(TestCase):
    """Test file upload validation utilities"""

    def test_validate_allowed_extension(self):
        """Test that allowed extensions pass validation"""
        from common.utils.file_validation import ALLOWED_EXTENSIONS
        self.assertIn('.pdf', ALLOWED_EXTENSIONS)
        self.assertIn('.xlsx', ALLOWED_EXTENSIONS)
        self.assertIn('.jpg', ALLOWED_EXTENSIONS)

    def test_sanitize_filename(self):
        """Test filename sanitization"""
        from common.utils.file_validation import sanitize_filename

        # Test path traversal prevention — basename strips all path components
        self.assertEqual(sanitize_filename('../../../etc/passwd'), 'passwd')
        self.assertEqual(sanitize_filename('..\\..\\windows\\system32'), 'system32')

        # Test null byte removal
        self.assertEqual(sanitize_filename('file\x00.pdf'), 'file_.pdf')

        # Test leading dot removal
        self.assertEqual(sanitize_filename('.hidden'), 'hidden')

        # Test empty filename
        self.assertEqual(sanitize_filename(''), 'unnamed_file')


class AFMValidationTest(TestCase):
    """Test AFM (Greek Tax ID) validation"""

    def test_valid_afm(self):
        """Test valid AFM passes validation"""
        from accounting.api_clients import ClientCreateUpdateSerializer
        serializer = ClientCreateUpdateSerializer()

        # Valid AFM with correct checksum
        valid_afm = '123456783'
        result = serializer.validate_afm(valid_afm)
        self.assertEqual(result, valid_afm)

    def test_invalid_afm_length(self):
        """Test AFM with wrong length fails"""
        from rest_framework import serializers
        from accounting.api_clients import ClientCreateUpdateSerializer
        serializer = ClientCreateUpdateSerializer()

        with self.assertRaises(serializers.ValidationError):
            serializer.validate_afm('12345678')  # 8 digits

        with self.assertRaises(serializers.ValidationError):
            serializer.validate_afm('1234567890')  # 10 digits

    def test_invalid_afm_checksum(self):
        """Test AFM with invalid checksum fails"""
        from rest_framework import serializers
        from accounting.api_clients import ClientCreateUpdateSerializer
        serializer = ClientCreateUpdateSerializer()

        with self.assertRaises(serializers.ValidationError):
            serializer.validate_afm('123456789')  # Invalid checksum
