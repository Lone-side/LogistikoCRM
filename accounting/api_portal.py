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
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.http import urlsafe_base64_decode
import os

from rest_framework.decorators import api_view, permission_classes, throttle_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import ScopedRateThrottle
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

    def _download_url(doc):
        # d.file είναι πάντα FieldFile· truthy μόνο αν υπάρχει αρχείο.
        # .url ρίχνει ValueError σε κενό FieldFile — το πιάνουμε.
        if not doc.file:
            return None
        try:
            return request.build_absolute_uri(doc.file.url)
        except ValueError:
            return None

    data = [{
        'id': d.id,
        'filename': d.filename,
        'file_type': getattr(d, 'file_type', ''),
        'document_category': getattr(d, 'document_category', ''),
        'uploaded_at': d.uploaded_at,
        'obligation': (d.obligation.obligation_type.name
                       if d.obligation and d.obligation.obligation_type else None),
        'download_url': _download_url(d),
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


class VatReadThrottle(ScopedRateThrottle):
    scope = 'vat_read'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([VatReadThrottle])
def me_vat(request):
    """
    GET /api/client/me/vat/

    Επιστρέφει την κατάσταση ΦΠΑ του πελάτη:
      - periods: VATPeriodResult ανά περίοδο (output/input/difference/final)
      - records: τα πιο πρόσφατα VATRecord (50 max) με net/vat ανά παραστατικό
      - summary: σύνολο εκροών/εισροών για ταχεία επισκόπηση
    """
    profile, err = _require_client(request)
    if err:
        return err

    # Late import για να μην έχουμε circular dependency στο app startup.
    from mydata.services import VATPortalService

    # Προαιρετικά φίλτρα. period_type: κλειστό σύνολο → 400 αν άκυρο.
    # year: lenient — αν δεν είναι ακέραιος, αγνοείται.
    period_type = request.query_params.get('period_type')
    if period_type and period_type not in ('monthly', 'quarterly'):
        return Response(
            {'detail': "Μη έγκυρο period_type (επιτρέπονται: monthly, quarterly)."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    year = None
    raw_year = request.query_params.get('year')
    if raw_year:
        try:
            year = int(raw_year)
        except (ValueError, TypeError):
            year = None

    # Το domain logic (split/aggregation/quantization) ζει στο service· εδώ
    # μένει μόνο η σειριοποίηση (Decimals → strings) στο HTTP edge.
    RECORD_LIMIT = 50

    summary_d = VATPortalService.get_summary(profile)
    summary = {
        'output': {'net': str(summary_d['output']['net']),
                   'vat': str(summary_d['output']['vat'])},
        'input': {'net': str(summary_d['input']['net']),
                  'vat': str(summary_d['input']['vat'])},
    }

    periods = [{
        'id': p.id,
        'period_type': p.period_type,
        'year': p.year,
        'period': p.period,
        'vat_output': str(p.vat_output),
        'vat_input': str(p.vat_input),
        'vat_difference': str(p.vat_difference),
        'previous_credit': str(p.previous_credit),
        'final_result': str(p.final_result),
        'credit_to_next': str(p.credit_to_next),
        'is_locked': p.is_locked,
        'last_calculated_at': p.last_calculated_at,
    } for p in VATPortalService.get_periods(profile, period_type=period_type, year=year)]

    records_qs = VATPortalService.get_recent_records(profile, limit=RECORD_LIMIT, year=year)
    records = [{
        'id': r.id,
        'mark': r.mark,
        'issue_date': r.issue_date,
        # rec_type 1 = εκροές (έσοδα), 2 = εισροές (έξοδα)
        'rec_type': r.rec_type,
        'kind': 'output' if r.rec_type == 1 else 'input',
        'inv_type': r.inv_type,
        'net_value': str(r.net_value),
        'vat_amount': str(r.vat_amount),
    } for r in records_qs]

    return Response({
        'summary': summary,
        'periods': periods,
        'records': records,
        'records_truncated': len(records) == RECORD_LIMIT,
    })


# =============================================================================
# DOCUMENT UPLOAD — ο πελάτης ανεβάζει αρχείο, ΠΑΝΤΑ αποδίδεται στον εαυτό του
# =============================================================================

_ALLOWED_EXTS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png'}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
_ALLOWED_CATEGORIES = {'contracts', 'invoices', 'tax', 'myf', 'vat', 'payroll', 'general'}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def me_upload_document(request):
    """
    POST /api/client/me/documents/  (multipart/form-data)

    Ο πελάτης ανεβάζει αρχείο. Το `client` ΠΑΝΤΑ ορίζεται από τον
    συνδεδεμένο user (αγνοούμε τυχόν client_id στο body — όχι spoofing).

    Form fields:
      - file: το αρχείο (απαραίτητο)
      - document_category: contracts|invoices|tax|myf|vat|payroll|general
      - description: προαιρετική περιγραφή
    """
    profile, err = _require_client(request)
    if err:
        return err

    uploaded = request.FILES.get('file')
    if uploaded is None:
        return Response({'detail': 'Δεν δόθηκε αρχείο (πεδίο: file).'},
                        status=status.HTTP_400_BAD_REQUEST)

    # Έλεγχος επέκτασης
    ext = os.path.splitext(uploaded.name)[1].lower()
    if ext not in _ALLOWED_EXTS:
        return Response(
            {'detail': f'Μη επιτρεπτός τύπος αρχείου. Επιτρέπονται: '
                       f'{", ".join(sorted(_ALLOWED_EXTS))}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Έλεγχος μεγέθους
    if uploaded.size > _MAX_UPLOAD_BYTES:
        return Response(
            {'detail': 'Το αρχείο είναι μεγαλύτερο από 10MB.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    category = (request.data.get('document_category') or 'general').strip()
    if category not in _ALLOWED_CATEGORIES:
        category = 'general'
    description = (request.data.get('description') or '').strip()[:500]

    # SECURITY (defense-in-depth): καθάρισε το όνομα αρχείου ώστε να μην περιέχει
    # path traversal / separators / control chars — ακόμη κι αν ο parser αλλάξει.
    from common.utils.file_validation import sanitize_filename
    safe_name = sanitize_filename(uploaded.name)
    uploaded.name = safe_name

    doc = ClientDocument.objects.create(
        client=profile,                # ← forced, NEVER from body
        file=uploaded,
        original_filename=safe_name,
        filename=safe_name,
        file_size=uploaded.size,
        document_category=category,
        description=description,
        uploaded_by=request.user,
    )

    return Response({
        'id': doc.id,
        'filename': doc.filename,
        'document_category': doc.document_category,
        'file_size': doc.file_size,
        'uploaded_at': doc.uploaded_at,
        'detail': 'Το αρχείο ανέβηκε επιτυχώς.',
    }, status=status.HTTP_201_CREATED)


# =============================================================================
# PASSWORD SET / RESET — για clients που δημιουργήθηκαν χωρίς usable password
# =============================================================================

class SetPasswordThrottle(ScopedRateThrottle):
    scope = 'set_password'


# Ενιαίο γενικό μήνυμα για ΟΛΕΣ τις αποτυχίες uid/token/client, ώστε να μην
# υπάρχει enumeration oracle (ίδια απάντηση είτε το uid είναι έγκυρο/client
# είτε όχι).
_INVALID_LINK = 'Ο σύνδεσμος είναι άκυρος ή έληξε. Ζητήστε νέο.'


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([SetPasswordThrottle])
def set_password(request):
    """
    POST /api/client/set-password/

    Ορισμός κωδικού μέσω one-time token (Django default_token_generator).
    Το staff δημιουργεί τον λογαριασμό· ο πελάτης λαμβάνει uid+token και ορίζει
    κωδικό εδώ. Rate-limited (10/hour) κατά brute-force.

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

    # Resolve user + token + client-status με ΕΝΙΑΙΟ generic error (no oracle).
    user = None
    try:
        user_id = urlsafe_base64_decode(uid).decode()
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if (
        user is None
        or not is_client_user(user)
        or not default_token_generator.check_token(user, token)
    ):
        return Response(
            {'detail': _INVALID_LINK},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Έλεγχος ισχύος κωδικού με τους validators του Django (μήκος, κοινοί,
    # αριθμητικοί κ.λπ.).
    try:
        validate_password(password, user=user)
    except DjangoValidationError as e:
        return Response(
            {'detail': ' '.join(e.messages)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(password)
    user.save(update_fields=['password'])
    return Response({'detail': 'Ο κωδικός ορίστηκε επιτυχώς.'})
