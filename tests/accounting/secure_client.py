# tests/accounting/secure_client.py
"""
HTTPS test client για τα RBAC smoke tests.

Το CI security-smoke job τρέχει με πραγματικό production config
(DJANGO_ENV=production), όπου το SECURE_SSL_REDIRECT μένει ενεργό και στο
test runner. Όλα τα requests εδώ γίνονται secure (https) ώστε να περνούν
από το redirect middleware και να ελέγχονται τα πραγματικά status codes
(200/400/401/403/404/500) αντί για 301.
"""

from django.test import Client
from rest_framework.test import APIClient


class SecureAPIClient(APIClient):
    """APIClient που μιλάει πάντα HTTPS."""

    def generic(self, method, path, data='',
                content_type='application/octet-stream', secure=True, **extra):
        return super().generic(method, path, data, content_type,
                               secure=True, **extra)


class SecureClient(Client):
    """Django test Client που μιλάει πάντα HTTPS (για legacy/admin views)."""

    def generic(self, method, path, data='',
                content_type='application/octet-stream', secure=True, **extra):
        return super().generic(method, path, data, content_type,
                               secure=True, **extra)
