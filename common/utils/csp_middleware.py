# -*- coding: utf-8 -*-
"""
Content-Security-Policy middleware (SD-001 defense-in-depth vs XSS).

Self-contained (no external dependency). The policy is intentionally
admin-compatible: the Django admin relies on inline styles, so style-src allows
'unsafe-inline'. Script execution is restricted to same-origin ('self'), which
blocks the primary XSS → token-theft vector (inline/injected <script>).

The policy can be overridden via the CSP_POLICY setting. For the React SPA served
separately (nginx/Vite), set the CSP at that server too; this header protects
Django-rendered responses (admin, error pages, DRF browsable API).
"""
from django.conf import settings

DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "      # admin inline styles
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'self'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none'"
)


class ContentSecurityPolicyMiddleware:
    """Adds a Content-Security-Policy header to every response."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.policy = getattr(settings, 'CSP_POLICY', DEFAULT_CSP)

    def __call__(self, request):
        response = self.get_response(request)
        # Don't override if something upstream already set it.
        response.setdefault('Content-Security-Policy', self.policy)
        return response
