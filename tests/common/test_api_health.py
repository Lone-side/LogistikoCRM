# tests/common/test_api_health.py
"""
Regression tests για το aggregation του /api/health/detailed/ (P1-03).

Το overall status πρέπει να υπολογίζεται και από τα τέσσερα components
(database, cache, Celery, disk) — όχι μόνο από database/cache — ώστε
πεσμένοι Celery workers ή critical disk να μην επιστρέφουν "healthy".

Όλα τα component checks γίνονται mock — κανένα πραγματικό Celery/disk
probe. Το endpoint παραμένει admin-only.
"""
from unittest.mock import patch

from django.test import TestCase, tag
from rest_framework.test import APIRequestFactory, force_authenticate

from common.api_health import health_check_detailed
from common.utils.helpers import USER_MODEL

HEALTHY = {'status': 'healthy'}
DETAILED_URL = '/api/health/detailed/'


def call_detailed(user=None):
    factory = APIRequestFactory()
    request = factory.get(DETAILED_URL)
    if user is not None:
        force_authenticate(request, user=user)
    return health_check_detailed(request)


def mock_components(db=HEALTHY, cache=HEALTHY, celery=HEALTHY, disk=HEALTHY):
    return patch.multiple(
        'common.api_health',
        check_database=lambda: db,
        check_cache=lambda: cache,
        check_celery=lambda: celery,
        check_disk_space=lambda: disk,
    )


@tag('TestCase')
class DetailedHealthAggregationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = USER_MODEL.objects.create_user(
            username='health_admin', password='test-secret-123',
            is_staff=True,
        )

    def assert_overall(self, response, status_code, overall):
        self.assertEqual(response.status_code, status_code)
        self.assertEqual(response.data['status'], overall)

    def test_all_components_healthy(self):
        with mock_components():
            response = call_detailed(self.admin)
        self.assert_overall(response, 200, 'healthy')

    def test_database_unhealthy_returns_503(self):
        with mock_components(db={'status': 'unhealthy', 'error': 'boom'}):
            response = call_detailed(self.admin)
        self.assert_overall(response, 503, 'unhealthy')

    def test_cache_unavailable_returns_503(self):
        with mock_components(cache={'status': 'unavailable', 'error': 'down'}):
            response = call_detailed(self.admin)
        self.assert_overall(response, 503, 'unhealthy')

    def test_celery_error_returns_503(self):
        with mock_components(celery={'status': 'error', 'error': 'broker'}):
            response = call_detailed(self.admin)
        self.assert_overall(response, 503, 'unhealthy')

    def test_celery_unavailable_returns_503(self):
        with mock_components(
                celery={'status': 'unavailable',
                        'message': 'Celery not installed'}):
            response = call_detailed(self.admin)
        self.assert_overall(response, 503, 'unhealthy')

    def test_celery_zero_workers_degraded_never_healthy(self):
        with mock_components(
                celery={'status': 'degraded', 'workers': 0,
                        'message': 'No active workers found'}):
            response = call_detailed(self.admin)
        self.assert_overall(response, 200, 'degraded')
        self.assertNotEqual(response.data['status'], 'healthy')

    def test_celery_unknown_is_degraded(self):
        with mock_components(
                celery={'status': 'unknown',
                        'message': 'Could not connect to workers'}):
            response = call_detailed(self.admin)
        self.assert_overall(response, 200, 'degraded')

    def test_disk_critical_returns_503(self):
        with mock_components(disk={'status': 'critical',
                                   'used_percent': 95.0}):
            response = call_detailed(self.admin)
        self.assert_overall(response, 503, 'unhealthy')

    def test_disk_warning_is_degraded(self):
        with mock_components(disk={'status': 'warning',
                                   'used_percent': 85.0}):
            response = call_detailed(self.admin)
        self.assert_overall(response, 200, 'degraded')

    def test_disk_unknown_is_degraded(self):
        with mock_components(disk={'status': 'unknown', 'error': 'no stat'}):
            response = call_detailed(self.admin)
        self.assert_overall(response, 200, 'degraded')

    def test_unhealthy_wins_over_degraded(self):
        """Critical κατάσταση υπερισχύει οποιουδήποτε degraded."""
        with mock_components(
                celery={'status': 'degraded', 'workers': 0},
                disk={'status': 'critical', 'used_percent': 95.0}):
            response = call_detailed(self.admin)
        self.assert_overall(response, 503, 'unhealthy')

    def test_response_contract_unchanged(self):
        """Τα υπάρχοντα response fields παραμένουν."""
        with mock_components():
            response = call_detailed(self.admin)
        for field in ('status', 'version', 'debug', 'check_duration_ms',
                      'components', 'settings'):
            self.assertIn(field, response.data)
        self.assertEqual(
            set(response.data['components']),
            {'database', 'cache', 'celery', 'disk'},
        )

    def test_detailed_endpoint_requires_admin(self):
        """Anonymous και non-staff χρήστες δεν έχουν πρόσβαση."""
        response = call_detailed(user=None)
        self.assertIn(response.status_code, (401, 403))

        non_staff = USER_MODEL.objects.create_user(
            username='health_plain', password='test-secret-123',
            is_staff=False,
        )
        response = call_detailed(non_staff)
        self.assertEqual(response.status_code, 403)
