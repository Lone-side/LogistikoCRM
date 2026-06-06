from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import include, path
from django.conf.urls.static import static
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from common.views.favicon import FaviconRedirect
from crm.views.contact_form import contact_form
from massmail.views.get_oauth2_tokens import get_refresh_token

# OpenAPI/Swagger documentation
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

# Health check endpoints
from common.api_health import health_check, health_check_detailed, health_ready, health_live

# 2FA (SD-002): όταν είναι ενεργό, το default admin site απαιτεί verified OTP
# device (django-otp). Gated από το ENABLE_ADMIN_2FA ώστε να μην κλειδώνει
# κανέναν by default. Ο swap αλλάζει μόνο την κλάση του υπάρχοντος site, οπότε
# όλες οι @admin.register καταχωρήσεις παραμένουν.
if getattr(settings, 'ENABLE_ADMIN_2FA', False):
    from django_otp.admin import OTPAdminSite
    admin.site.__class__ = OTPAdminSite

# Main URL patterns (no language prefix)
urlpatterns = [
    path('accounting/', include('accounting.urls')),
    path('favicon.ico', FaviconRedirect.as_view()),
    path('voip/', include('voip.urls')),
    path('OAuth-2/authorize/', staff_member_required(get_refresh_token), name='get_refresh_token'),

    # ==================================================
    # HEALTH CHECKS (for monitoring & load balancers)
    # ==================================================
    path('api/health/', health_check, name='health-check'),
    path('api/health/detailed/', health_check_detailed, name='health-detailed'),
    path('api/health/ready/', health_ready, name='health-ready'),
    path('api/health/live/', health_live, name='health-live'),

    # ==================================================
    # API DOCUMENTATION (OpenAPI/Swagger)
    # ==================================================
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Media files (development only)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Rosetta (translations)
if 'rosetta' in settings.INSTALLED_APPS:
    urlpatterns += [
        path('rosetta/', include('rosetta.urls'))
    ]

# Internationalized patterns (with language prefix)
urlpatterns += i18n_patterns(
    path(settings.SECRET_CRM_PREFIX, include('common.urls')),
    path(settings.SECRET_CRM_PREFIX, include('crm.urls')),
    path(settings.SECRET_CRM_PREFIX, include('massmail.urls')),
    path(settings.SECRET_CRM_PREFIX, include('tasks.urls')),
    path(settings.SECRET_CRM_PREFIX, include('analytics.urls')),
    path(settings.SECRET_CRM_PREFIX, include('chat.urls')),
    path(settings.SECRET_CRM_PREFIX, include('help.urls')),
    path(settings.SECRET_CRM_PREFIX, include('settings.urls')),
    path(settings.SECRET_ADMIN_PREFIX, admin.site.urls),  # Admin URL with secret prefix
    path('contact_form/', contact_form, name='contact_form'),
)
