# -*- coding: utf-8 -*-
"""
SECURITY (SD-001): every response carries a Content-Security-Policy that blocks
inline/injected scripts (defense-in-depth against XSS token theft) without
breaking the Django admin.
"""
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from common.utils.csp_middleware import ContentSecurityPolicyMiddleware, DEFAULT_CSP


class CspMiddlewareUnitTest(TestCase):
    def test_adds_csp_header(self):
        from django.http import HttpResponse
        mw = ContentSecurityPolicyMiddleware(lambda r: HttpResponse('ok'))
        resp = mw(APIRequestFactory().get('/'))
        self.assertIn('Content-Security-Policy', resp)

    def test_policy_blocks_inline_scripts(self):
        # script-src must be 'self' only — no 'unsafe-inline' for scripts.
        self.assertIn("script-src 'self'", DEFAULT_CSP)
        self.assertNotIn("script-src 'self' 'unsafe-inline'", DEFAULT_CSP)
        self.assertIn("object-src 'none'", DEFAULT_CSP)

    def test_does_not_override_existing_header(self):
        from django.http import HttpResponse

        def view(_):
            r = HttpResponse('ok')
            r['Content-Security-Policy'] = "default-src 'none'"
            return r

        mw = ContentSecurityPolicyMiddleware(view)
        resp = mw(APIRequestFactory().get('/'))
        self.assertEqual(resp['Content-Security-Policy'], "default-src 'none'")


class CspIntegrationTest(TestCase):
    def test_health_endpoint_has_csp_header(self):
        resp = self.client.get('/api/health/')
        self.assertIn('Content-Security-Policy', resp)
        self.assertIn("script-src 'self'", resp['Content-Security-Policy'])
