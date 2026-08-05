# -*- coding: utf-8 -*-
"""
accounting/api_gsis.py
Author: Claude
Description: REST API endpoints για GSIS (αναζήτηση στοιχείων με ΑΦΜ).
"""

import logging
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.throttling import UserRateThrottle

from .gsis_client import lookup_afm, get_gsis_client, GSISError
from accounting.services.access import mask_pii_value, require_model_perms

logger = logging.getLogger(__name__)


class AfmLookupThrottle(UserRateThrottle):
    """Όριο στα GSIS lookups — μοιραζόμαστε τα credentials του γραφείου."""
    scope = 'afm_lookup'


def _require_settings_admin(request):
    """Οι ρυθμίσεις GSIS (ΑΦΜ/username/password γραφείου) είναι μόνο για
    Διαχειριστή (superuser ή view_all_clients) — όχι για κάθε logged-in χρήστη."""
    user = request.user
    if user.is_superuser or user.has_perm('accounting.view_all_clients'):
        return None
    from accounting.services.access import _audit_deny
    _audit_deny(user, request, f'{request.method} {request.path}: ρυθμίσεις GSIS χωρίς ρόλο Διαχειριστή')
    return Response(
        {'error': 'Μόνο διαχειριστές μπορούν να δουν/αλλάξουν τις ρυθμίσεις GSIS.'},
        status=status.HTTP_403_FORBIDDEN,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([AfmLookupThrottle])
@require_model_perms('accounting.view_clientprofile')
def afm_lookup(request):
    """
    POST /api/v1/afm-lookup/

    Αναζήτηση στοιχείων επιχείρησης με ΑΦΜ.

    Request body:
        {
            "afm": "123456789"
        }

    Response (success):
        {
            "success": true,
            "data": {
                "afm": "123456789",
                "onomasia": "ΕΠΩΝΥΜΙΑ ΑΕ",
                "doy": "1234",
                "doy_descr": "Δ.Ο.Υ. ΑΘΗΝΩΝ",
                "legal_form_descr": "ΑΝΩΝΥΜΗ ΕΤΑΙΡΕΙΑ",
                "postal_address": "ΟΔΟΣ",
                "postal_address_no": "10",
                "postal_zip_code": "12345",
                "postal_area": "ΑΘΗΝΑ",
                "registration_date": "2020-01-01",
                "deactivation_flag": false,
                "firm_flag": true,
                "activities": [...]
            }
        }

    Response (error):
        {
            "success": false,
            "error": "Μήνυμα σφάλματος"
        }
    """
    afm = request.data.get('afm', '').strip()

    if not afm:
        return Response({
            'success': False,
            'error': 'Το ΑΦΜ είναι υποχρεωτικό.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Basic validation
    if len(afm) != 9 or not afm.isdigit():
        return Response({
            'success': False,
            'error': 'Το ΑΦΜ πρέπει να αποτελείται από 9 ψηφία.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Check if GSIS is configured
    client = get_gsis_client()
    if not client:
        return Response({
            'success': False,
            'error': 'Δεν έχουν ρυθμιστεί τα credentials GSIS. Παρακαλώ ρυθμίστε τα στις Ρυθμίσεις.'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    try:
        logger.info(f"AFM lookup requested for: {mask_pii_value(afm)} by user: {request.user}")
        info = lookup_afm(afm)

        return Response({
            'success': True,
            'data': info.to_dict()
        })

    except GSISError as e:
        logger.warning(f"GSIS lookup failed for AFM {mask_pii_value(afm)}: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Unexpected error during AFM lookup for {mask_pii_value(afm)}: {e}")
        return Response({
            'success': False,
            'error': 'Απρόσμενο σφάλμα κατά την αναζήτηση.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gsis_settings_status(request):
    """
    GET /api/v1/gsis/status/

    Επιστρέφει την κατάσταση ρύθμισης του GSIS.

    Response:
        {
            "configured": true/false,
            "active": true/false,
            "username": "..." (μόνο αν configured)
        }
    """
    denied = _require_settings_admin(request)
    if denied is not None:
        return denied
    from settings.models import GSISSettings

    settings = GSISSettings.get_settings()

    if not settings:
        return Response({
            'configured': False,
            'active': False,
        })

    return Response({
        'configured': True,
        'active': settings.is_active,
        'afm': settings.afm,
        'username': settings.username,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def gsis_settings_update(request):
    """
    POST /api/v1/gsis/settings/

    Ενημέρωση ρυθμίσεων GSIS.

    Request body:
        {
            "afm": "123456789",
            "username": "...",
            "password": "...",
            "is_active": true
        }

    Response:
        {
            "success": true,
            "message": "Οι ρυθμίσεις αποθηκεύτηκαν."
        }
    """
    denied = _require_settings_admin(request)
    if denied is not None:
        return denied
    from settings.models import GSISSettings

    afm = request.data.get('afm', '').strip()
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '').strip()
    is_active = request.data.get('is_active', True)

    # Validate AFM
    if not afm or len(afm) != 9 or not afm.isdigit():
        return Response({
            'success': False,
            'error': 'Το ΑΦΜ πρέπει να αποτελείται από 9 ψηφία.'
        }, status=status.HTTP_400_BAD_REQUEST)

    if not username:
        return Response({
            'success': False,
            'error': 'Το όνομα χρήστη είναι υποχρεωτικό.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Get or create settings
    settings = GSISSettings.get_settings()

    if settings:
        settings.afm = afm
        settings.username = username
        # Only update password if provided (allow keeping existing)
        if password:
            settings.password = password
        settings.is_active = is_active
        settings.save()
    else:
        if not password:
            return Response({
                'success': False,
                'error': 'Ο κωδικός είναι υποχρεωτικός για νέα ρύθμιση.'
            }, status=status.HTTP_400_BAD_REQUEST)

        settings = GSISSettings.objects.create(
            afm=afm,
            username=username,
            password=password,
            is_active=is_active,
        )

    logger.info(f"GSIS settings updated by user: {request.user}")

    return Response({
        'success': True,
        'message': 'Οι ρυθμίσεις αποθηκεύτηκαν επιτυχώς.'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def gsis_test_connection(request):
    """
    POST /api/v1/gsis/test/

    Δοκιμή σύνδεσης με το GSIS.

    Response:
        {
            "success": true/false,
            "message": "..."
        }
    """
    denied = _require_settings_admin(request)
    if denied is not None:
        return denied
    client = get_gsis_client()

    if not client:
        return Response({
            'success': False,
            'message': 'Δεν έχουν ρυθμιστεί τα credentials GSIS.'
        })

    try:
        if client.test_connection():
            return Response({
                'success': True,
                'message': 'Η σύνδεση με το GSIS είναι επιτυχής!'
            })
        else:
            return Response({
                'success': False,
                'message': 'Αποτυχία σύνδεσης. Ελέγξτε τα credentials.'
            })
    except Exception as e:
        logger.error(f"GSIS connection test failed: {e}")
        return Response({
            'success': False,
            'message': f'Σφάλμα: {str(e)}'
        })
