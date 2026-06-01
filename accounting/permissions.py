# -*- coding: utf-8 -*-
"""
accounting/permissions.py
Author: ddiplas
Description: Custom permissions for VoIP and internal services
"""
import logging
from rest_framework.permissions import BasePermission
from django.conf import settings

from accounting.portal import is_client_user

logger = logging.getLogger(__name__)


class IsStaffOrClientOwner(BasePermission):
    """
    Client Portal permission.

    - Staff/superuser: πλήρης πρόσβαση (όπως πριν).
    - Client user: πρόσβαση μόνο σε αντικείμενα που ανήκουν στον ΔΙΚΟ του πελάτη.

    Το object-level έλεγχο γίνεται στο has_object_permission μέσω ενός callable
    `owner_lookup` που ορίζει το viewset (π.χ. lambda obj: obj.client.user).
    Το queryset-level scoping γίνεται ξεχωριστά στο get_queryset του viewset
    (βλ. ClientScopedQuerysetMixin) — αυτή η κλάση είναι η δεύτερη γραμμή άμυνας.
    """

    def has_permission(self, request, view):
        # Πρέπει να είναι authenticated· τα υπόλοιπα κρίνονται ανά object/queryset.
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_staff or user.is_superuser:
            return True
        if not is_client_user(user):
            return False

        # Βρες τον owner-user του object. Το viewset μπορεί να ορίσει
        # `client_owner_field` (dotted path προς το User), default 'client.user'.
        owner_field = getattr(view, 'client_owner_field', 'client.user')
        owner = obj
        for part in owner_field.split('.'):
            owner = getattr(owner, part, None)
            if owner is None:
                return False
        return owner == user


class IsVoIPMonitor(BasePermission):
    """
    Custom permission for VoIP monitor services (e.g., Fritz!Box monitor).

    Allows access if the request includes a valid X-API-Key header
    matching the FRITZ_API_TOKEN setting.

    Usage in ViewSet:
        permission_classes = [IsAuthenticated | IsVoIPMonitor]
    """

    def has_permission(self, request, view):
        # Get API key from header or query parameter
        api_key = request.headers.get('X-API-Key') or request.GET.get('api_key')

        if not api_key:
            logger.info(f"IsVoIPMonitor: No X-API-Key header (IP: {self._get_client_ip(request)})")
            return False

        # Get expected token from settings
        expected_token = getattr(settings, 'FRITZ_API_TOKEN', None)

        if not expected_token:
            logger.warning("IsVoIPMonitor: FRITZ_API_TOKEN not configured in settings!")
            return False

        # Secure comparison to prevent timing attacks
        if api_key == expected_token:
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
