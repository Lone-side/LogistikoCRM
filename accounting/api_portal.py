# -*- coding: utf-8 -*-
"""
Client Portal API — /api/client/me/ endpoints
=============================================
Read-mostly endpoints για τον συνδεδεμένο πελάτη. Όλα επιστρέφουν ΜΟΝΟ τα
δεδομένα του δικού του ClientProfile (μέσω get_client_profile).

Endpoints:
    GET /accounting/api/client/me/profile/     - Το προφίλ του πελάτη
    GET /accounting/api/client/me/obligations/ - Οι υποχρεώσεις του
    GET /accounting/api/client/me/documents/   - Τα έγγραφά του
    GET /accounting/api/client/me/calls/       - Οι κλήσεις του
"""
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from accounting.portal import is_client_user, get_client_profile
from accounting.models import MonthlyObligation, ClientDocument, VoIPCall


def _require_client(request):
    """
    Επιστρέφει (profile, error_response). Αν ο χρήστης δεν είναι client ή δεν
    έχει συνδεδεμένο προφίλ, το error_response είναι έτοιμο Response 403.
    """
    if not is_client_user(request.user):
        return None, Response(
            {'detail': 'Διαθέσιμο μόνο για λογαριασμούς πελατών.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    profile = get_client_profile(request.user)
    if profile is None:
        return None, Response(
            {'detail': 'Δεν υπάρχει συνδεδεμένο προφίλ πελάτη.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    return profile, None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_profile(request):
    """GET /api/client/me/profile/ — βασικά στοιχεία του πελάτη."""
    profile, err = _require_client(request)
    if err:
        return err
    return Response({
        'id': profile.id,
        'afm': profile.afm,
        'eponimia': profile.eponimia,
        'onoma': profile.onoma,
        'doy': profile.doy,
        'email': profile.email,
        'kinito_tilefono': profile.kinito_tilefono,
        'eidos_ipoxreou': profile.eidos_ipoxreou,
        'is_active': profile.is_active,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_obligations(request):
    """GET /api/client/me/obligations/ — υποχρεώσεις του πελάτη (newest first)."""
    profile, err = _require_client(request)
    if err:
        return err
    qs = (MonthlyObligation.objects
          .filter(client=profile)
          .select_related('obligation_type')
          .order_by('-year', '-month'))
    data = [{
        'id': o.id,
        'obligation_type': o.obligation_type.name if o.obligation_type else None,
        'obligation_type_code': o.obligation_type.code if o.obligation_type else None,
        'year': o.year,
        'month': o.month,
        'deadline': o.deadline,
        'status': o.status,
        'deadline_status': o.deadline_status,
        'completed_date': o.completed_date,
    } for o in qs]
    return Response({'count': len(data), 'results': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_documents(request):
    """GET /api/client/me/documents/ — έγγραφα του πελάτη (current versions)."""
    profile, err = _require_client(request)
    if err:
        return err
    qs = (ClientDocument.objects
          .filter(client=profile)
          .select_related('obligation', 'obligation__obligation_type')
          .order_by('-uploaded_at'))
    # Μόνο τρέχουσες εκδόσεις αν το model το υποστηρίζει.
    if hasattr(ClientDocument, 'is_current'):
        qs = qs.filter(is_current=True)
    data = [{
        'id': d.id,
        'filename': d.filename,
        'file_type': getattr(d, 'file_type', ''),
        'document_category': getattr(d, 'document_category', ''),
        'uploaded_at': d.uploaded_at,
        'obligation': (d.obligation.obligation_type.name
                       if d.obligation and d.obligation.obligation_type else None),
        'download_url': d.file.url if getattr(d, 'file', None) else None,
    } for d in qs]
    return Response({'count': len(data), 'results': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_calls(request):
    """GET /api/client/me/calls/ — κλήσεις που αντιστοιχίστηκαν στον πελάτη."""
    profile, err = _require_client(request)
    if err:
        return err
    qs = (VoIPCall.objects
          .filter(client=profile)
          .order_by('-started_at')[:100])
    data = [{
        'id': c.id,
        'phone_number': c.phone_number,
        'direction': c.direction,
        'status': c.status,
        'started_at': c.started_at,
        'duration_seconds': getattr(c, 'duration_seconds', 0),
    } for c in qs]
    return Response({'count': len(data), 'results': data})


# =============================================================================
# PASSWORD SET / RESET — για clients που δημιουργήθηκαν χωρίς usable password
# =============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def set_password(request):
    """
    POST /api/client/me/set-password/

    Ορισμός κωδικού μέσω one-time token (Django default_token_generator).
    Το staff δημιουργεί τον λογαριασμό· ο πελάτης λαμβάνει uid+token (μέσω
    email/SMS) και ορίζει κωδικό εδώ. Δεν απαιτεί authentication.

    Body: { "uid": "<base64 user id>", "token": "<token>", "password": "<new>" }
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    uid = request.data.get('uid')
    token = request.data.get('token')
    password = request.data.get('password')

    if not all([uid, token, password]):
        return Response(
            {'detail': 'Απαιτούνται uid, token και password.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(password) < 8:
        return Response(
            {'detail': 'Ο κωδικός πρέπει να έχει τουλάχιστον 8 χαρακτήρες.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user_id = urlsafe_base64_decode(uid).decode()
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return Response(
            {'detail': 'Μη έγκυρος σύνδεσμος.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Ασφάλεια: μόνο client users μπορούν να ορίσουν κωδικό από αυτό το endpoint.
    if not is_client_user(user):
        return Response(
            {'detail': 'Μη έγκυρος σύνδεσμος.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not default_token_generator.check_token(user, token):
        return Response(
            {'detail': 'Ο σύνδεσμος έληξε ή είναι άκυρος. Ζητήστε νέο.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(password)
    user.save(update_fields=['password'])
    return Response({'detail': 'Ο κωδικός ορίστηκε επιτυχώς.'})
