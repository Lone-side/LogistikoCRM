# crm/utils/public_rate_limit.py
"""
Cache-backed rate limiting για τα public CRM intake endpoints
(crm.views.contact_form, crm.views.add_request).

Τα endpoints αυτά είναι CSRF-exempt και δεν απαιτούν authentication,
οπότε χωρίς throttle μπορούν να δημιουργούν Request/CrmEmail records
απεριόριστα. Χρησιμοποιείται το SimpleRateThrottle του DRF (υπάρχουσα
dependency) πάνω στο default Django cache — καμία νέα dependency.

Το όριο ρυθμίζεται με το setting PUBLIC_FORM_THROTTLE_RATE
(default "30/hour") και μετράει ανά client IP και ανά endpoint.
"""
import logging
from functools import wraps

from django.conf import settings
from django.http import HttpResponse
from rest_framework.settings import api_settings
from rest_framework.throttling import SimpleRateThrottle

logger = logging.getLogger(__name__)

DEFAULT_PUBLIC_FORM_THROTTLE_RATE = '30/hour'


class PublicFormRateThrottle(SimpleRateThrottle):
    """Throttle ανά client IP + endpoint scope για public φόρμες."""

    def __init__(self, scope_suffix: str):
        self.scope_suffix = scope_suffix
        self.rate = getattr(
            settings,
            'PUBLIC_FORM_THROTTLE_RATE',
            DEFAULT_PUBLIC_FORM_THROTTLE_RATE,
        )
        super().__init__()

    def get_ident(self, request):
        # Χωρίς δηλωμένο NUM_PROXIES δεν εμπιστευόμαστε καθόλου το
        # X-Forwarded-For: το default του DRF θα χρησιμοποιούσε ολόκληρη
        # την (attacker-controlled) τιμή του header ως ident, οπότε ένας
        # spoofer θα έπαιρνε νέο counter σε κάθε request. Με configured
        # NUM_PROXIES ισχύει η υπάρχουσα proxy λογική του DRF.
        if api_settings.NUM_PROXIES is None:
            return request.META.get('REMOTE_ADDR') or 'unknown'
        return super().get_ident(request)

    def get_cache_key(self, request, view=None):
        return self.cache_format % {
            'scope': f'public_form_{self.scope_suffix}',
            'ident': self.get_ident(request),
        }


def throttle_public_form(scope_suffix: str):
    """
    Decorator για public intake views: εφαρμόζει το throttle στα POST
    requests πριν εκτελεστεί οτιδήποτε από το view (κανένα Request,
    CrmEmail, ticket ή notification πάνω από το όριο). Επιστρέφει
    generic 429 χωρίς εσωτερικές πληροφορίες.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.method == 'POST':
                throttle = PublicFormRateThrottle(scope_suffix)
                if not throttle.allow_request(request, None):
                    logger.warning(
                        "Throttled public form POST (scope=%s)", scope_suffix
                    )
                    return HttpResponse(status=429)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
