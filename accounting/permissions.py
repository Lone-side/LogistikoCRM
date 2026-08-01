# -*- coding: utf-8 -*-
"""
accounting/permissions.py
Author: ddiplas
Description: Custom permissions for VoIP and internal services
"""
import hmac
import logging
from rest_framework.permissions import BasePermission
from django.conf import settings

logger = logging.getLogger(__name__)

# Το default του settings.py — δεν γίνεται ποτέ δεκτό ως έγκυρο credential
INSECURE_DEFAULT_TOKEN = 'change-this-token-in-production'


class IsVoIPMonitor(BasePermission):
    """
    Custom permission for VoIP monitor services (e.g., Fritz!Box monitor).

    Allows access if the request includes a valid X-API-Key header
    matching the FRITZ_API_TOKEN setting.

    Usage in ViewSet:
        permission_classes = [IsAuthenticated | IsVoIPMonitor]
    """

    def has_permission(self, request, view):
        # Μόνο header — token σε query string καταλήγει σε access logs/Referer
        api_key = request.headers.get('X-API-Key')

        if not api_key:
            logger.info(f"IsVoIPMonitor: No X-API-Key header (IP: {self._get_client_ip(request)})")
            return False

        # Get expected token from settings
        expected_token = getattr(settings, 'FRITZ_API_TOKEN', None)

        if not expected_token or expected_token == INSECURE_DEFAULT_TOKEN:
            logger.warning("IsVoIPMonitor: FRITZ_API_TOKEN not configured (or left at "
                           "the insecure default) — denying all requests")
            return False

        # Secure comparison to prevent timing attacks
        if hmac.compare_digest(api_key, expected_token):
            logger.info(f"IsVoIPMonitor: ✅ GRANTED - Valid API key (IP: {self._get_client_ip(request)})")
            return True
        else:
            # Log mismatch with masked tokens for debugging
            provided_masked = api_key[:4] + '...' if len(api_key) > 4 else '****'
            expected_masked = expected_token[:4] + '...' if len(expected_token) > 4 else '****'
            logger.warning(
                f"IsVoIPMonitor: ❌ DENIED - Token mismatch "
                f"(provided: {provided_masked}, expected: {expected_masked}, IP: {self._get_client_ip(request)})"
            )
            return False

    def _get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')


class IsLocalRequest(BasePermission):
    """
    Permission that allows requests from localhost/loopback addresses.

    Useful as a fallback for internal services running on the same machine.

    Allowed IPs:
    - 127.0.0.1 (IPv4 loopback)
    - localhost (resolved)
    - ::1 (IPv6 loopback)
    - 0.0.0.0 (some Windows configurations)

    Usage in ViewSet:
        permission_classes = [IsAuthenticated | IsVoIPMonitor | IsLocalRequest]
    """

    # Extended list to cover all localhost variants
    ALLOWED_IPS = {
        '127.0.0.1',      # IPv4 loopback
        'localhost',       # hostname
        '::1',            # IPv6 loopback
        '0.0.0.0',        # Some Windows configs
        '::ffff:127.0.0.1',  # IPv6-mapped IPv4 loopback
    }

    def has_permission(self, request, view):
        remote_addr = request.META.get('REMOTE_ADDR', 'unknown')
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

        # Log all relevant info for debugging
        logger.info(f"IsLocalRequest: Checking request - REMOTE_ADDR='{remote_addr}', X-Forwarded-For='{x_forwarded_for}'")

        # Use REMOTE_ADDR directly (don't trust X-Forwarded-For for security)
        client_ip = remote_addr

        if client_ip in self.ALLOWED_IPS:
            logger.info(f"IsLocalRequest: ✅ GRANTED - IP '{client_ip}' is in allowed list")
            return True

        # Also check if it starts with 127. (covers 127.0.0.0/8 subnet)
        if client_ip.startswith('127.'):
            logger.info(f"IsLocalRequest: ✅ GRANTED - IP '{client_ip}' is in 127.x.x.x range")
            return True

        logger.info(f"IsLocalRequest: ❌ DENIED - IP '{client_ip}' not in allowed list: {self.ALLOWED_IPS}")
        return False


class CanAccessClient(BasePermission):
    """
    Object-level permission: πρόσβαση μόνο σε ανατεθειμένους πελάτες.

    Ενεργό μόνο όταν settings.ENFORCE_CLIENT_ASSIGNMENT=True. Superusers
    και χρήστες με accounting.view_all_clients περνούν πάντα.
    Το object μπορεί να είναι ClientProfile ή οποιοδήποτε μοντέλο με .client.
    """

    def has_object_permission(self, request, view, obj):
        from accounting.mixins import user_sees_all_clients
        if user_sees_all_clients(request.user):
            return True
        client = obj if hasattr(obj, 'assigned_users') else getattr(obj, 'client', None)
        if client is None:
            return True
        return client.assigned_users.filter(pk=request.user.pk).exists()
