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
import logging
import os

logger = logging.getLogger(__name__)

from rest_framework.decorators import api_view, permission_classes, throttle_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.response import Response
from rest_framework import status

from django.conf import settings
from accounting.portal import is_client_user, get_client_profile
from accounting.models import MonthlyObligation, ClientDocument, VoIPCall, ClientLiability


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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_liabilities(request):
    """GET /api/client/me/liabilities/ — ενημερωτικές οφειλές ΑΑΔΕ/ΕΦΚΑ του πελάτη.

    Read-only: τις καταχωρεί ο λογιστής. Επιστρέφει και τα επίσημα deep-links
    (myAADE / ΚΕΑΟ) όπου ο πελάτης βλέπει τις ζωντανές οφειλές με το TaxisNet του.
    Δεν υπάρχει επίσημο API οφειλών — γι' αυτό είναι ενημερωτικά + link-out.
    """
    from decimal import Decimal

    profile, err = _require_client(request)
    if err:
        return err
    qs = (ClientLiability.objects
          .filter(client=profile)
          .order_by('-due_date', '-created_at'))
    results = [{
        'id': o.id,
        'source': o.source,
        'source_display': o.get_source_display(),
        'description': o.description,
        'amount': str(o.amount),
        'due_date': o.due_date,
        'payment_code': o.payment_code,
        'status': o.status,
        'status_display': o.get_status_display(),
    } for o in qs]
    # Σύνολα ανά φορέα — μόνο μη-εξοφλημένες.
    totals = {}
    for o in qs:
        if o.status != 'paid':
            totals[o.source] = totals.get(o.source, Decimal('0')) + (o.amount or Decimal('0'))
    return Response({
        'count': len(results),
        'results': results,
        'totals': {k: str(v) for k, v in totals.items()},
        'links': {
            'aade': getattr(settings, 'AADE_DEBTS_URL', ''),
            'efka': getattr(settings, 'EFKA_DEBTS_URL', ''),
        },
    })


class VatReadThrottle(SimpleRateThrottle):
    # NOTE: ScopedRateThrottle no-ops on function views (it reads throttle_scope
    # off the view, which @api_view functions lack). SimpleRateThrottle with a
    # fixed scope actually enforces. Keyed per authenticated user (fallback IP).
    scope = 'vat_read'

    def get_cache_key(self, request, view):
        ident = (request.user.pk if request.user and request.user.is_authenticated
                 else self.get_ident(request))
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class VatSyncThrottle(SimpleRateThrottle):
    # Client self-sync ΦΠΑ: αυστηρό (κόστος/όρια myDATA + anti-abuse). Keyed per
    # authenticated user. Ίδιο μοτίβο με VatReadThrottle (SimpleRateThrottle, όχι
    # ScopedRateThrottle που κάνει no-op σε @api_view function views).
    scope = 'vat_sync'

    def get_cache_key(self, request, view):
        ident = (request.user.pk if request.user and request.user.is_authenticated
                 else self.get_ident(request))
        return self.cache_format % {'scope': self.scope, 'ident': ident}


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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([VatSyncThrottle])
def me_sync_vat(request):
    """
    POST /api/client/me/vat/sync/

    Ο πελάτης τραβάει ΜΟΝΟΣ του τα δεδομένα ΦΠΑ του από το myDATA (self-service).
    Scoped: συγχρονίζει ΜΟΝΟ τον συνδεδεμένο πελάτη (αγνοεί τυχόν client_id στο
    body — όχι spoofing). Αυστηρά guardrails:
      - throttle 3/hour ανά πελάτη (VatSyncThrottle)
      - μόνο τρέχων ή προηγούμενος μήνας (όχι αυθαίρετα/παλιά εύρη)
      - σέβεται κλειδωμένες (υποβληθείσες) περιόδους μέσω του locked-period guard
        του mydata_sync_vat — επιστρέφει καθαρό skipped/locked αντί για ψεύτικη
        επιτυχία.

    Optional body: {year, month} — αν δοθούν, πρέπει να ανήκουν στο επιτρεπτό
    σύνολο {τρέχων μήνας, προηγούμενος μήνας}· αλλιώς 400.
    """
    from django.core.management import call_command
    from django.db.models import Max
    from django.utils import timezone
    from io import StringIO
    from mydata.models import MyDataCredentials, VATSyncLog
    from mydata.services import summarize_vat_sync

    profile, err = _require_client(request)
    if err:
        return err

    # Credentials ορισμένα από το λογιστήριο — απαραίτητα.
    try:
        creds = profile.mydata_credentials
    except MyDataCredentials.DoesNotExist:
        creds = None
    if creds is None or not creds.has_credentials or not creds.is_active:
        return Response(
            {'detail': 'Δεν έχουν ρυθμιστεί στοιχεία myDATA. '
                       'Επικοινωνήστε με το λογιστήριο.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Period restriction (STRICT): μόνο τρέχων ή προηγούμενος μήνας.
    today = timezone.localdate()
    current = (today.year, today.month)
    previous = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
    allowed = {current, previous}

    raw_year = request.data.get('year')
    raw_month = request.data.get('month')
    if raw_year is not None or raw_month is not None:
        try:
            year, month = int(raw_year), int(raw_month)
        except (TypeError, ValueError):
            return Response(
                {'detail': 'Μη έγκυρα year/month.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if (year, month) not in allowed:
            return Response(
                {'detail': 'Επιτρέπεται συγχρονισμός μόνο για τον τρέχοντα ή '
                           'τον προηγούμενο μήνα.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        year, month = current

    before_id = (VATSyncLog.objects.filter(client=profile)
                 .aggregate(m=Max('id'))['m'] or 0)

    out = StringIO()
    try:
        call_command('mydata_sync_vat', '--client', profile.afm,
                     '--year', str(year), '--month', str(month), stdout=out)
    except Exception:
        logger.exception('Client self-sync VAT failed for %s', profile.afm)
        return Response(
            {'detail': 'Σφάλμα συγχρονισμού. Δοκιμάστε ξανά αργότερα.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(summarize_vat_sync(profile, before_id, out))


# =============================================================================
# DOCUMENT UPLOAD — ο πελάτης ανεβάζει αρχείο, ΠΑΝΤΑ αποδίδεται στον εαυτό του
# =============================================================================

_ALLOWED_EXTS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png'}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
_ALLOWED_CATEGORIES = {'contracts', 'invoices', 'tax', 'myf', 'vat', 'payroll', 'general'}

# Magic-byte content check — κοινός helper με το staff path, χωρίς εξάρτηση από
# python-magic/libmagic (το οποίο είναι native/αναξιόπιστο και μπορεί να κάνει
# segfault τη διεργασία). Βλ. common/utils/file_validation.py.
from common.utils.file_validation import content_matches_extension as _content_matches_extension


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

    # SECURITY (defense-in-depth): magic-bytes έλεγχος περιεχομένου ώστε ένα
    # εκτελέσιμο μετονομασμένο σε .pdf να μην περνά μόνο με το extension.
    # Χωρίς εξάρτηση από python-magic/libmagic (που είναι αναξιόπιστο/native).
    if not _content_matches_extension(uploaded, ext):
        return Response(
            {'detail': 'Το περιεχόμενο του αρχείου δεν ταιριάζει με τον τύπο του.'},
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

class SetPasswordThrottle(SimpleRateThrottle):
    # SimpleRateThrottle (not ScopedRateThrottle) so it actually enforces on this
    # function view. Unauthenticated endpoint → key by client IP.
    scope = 'set_password'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


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
    κωδικό εδώ. Rate-limited (3/hour) κατά brute-force.

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

    # Resolve user με ΕΝΙΑΙΟ generic error (no enumeration oracle).
    user = None
    try:
        user_id = urlsafe_base64_decode(uid).decode()
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    # Constant-time: ΠΑΝΤΑ τρέχουμε token check (ακόμη κι αν λείπει ο user ή δεν
    # είναι client), ώστε ο χρόνος απόκρισης να μην προδίδει αν το uid υπάρχει.
    token_user = user if (user is not None and is_client_user(user)) else None
    token_ok = default_token_generator.check_token(token_user, token)

    if token_user is None or not token_ok:
        return Response(
            {'detail': _INVALID_LINK},
            status=status.HTTP_400_BAD_REQUEST,
        )
    user = token_user

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


class PasswordResetThrottle(SimpleRateThrottle):
    # Self-service αίτημα reset: keyed by IP (ο χρήστης δεν είναι authenticated).
    scope = 'password_reset'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetThrottle])
def request_password_reset(request):
    """
    POST /api/client/request-password-reset/

    Self-service «ξέχασα τον κωδικό»: ο πελάτης δίνει email ή ΑΦΜ και λαμβάνει
    σύνδεσμο ορισμού κωδικού (το ίδιο email με την πρόσκληση).

    ΠΑΝΤΑ επιστρέφει το ίδιο γενικό μήνυμα (no enumeration oracle — δεν προδίδει
    αν υπάρχει λογαριασμός). Απαιτεί ρυθμισμένο SMTP για να παραδοθεί το email·
    αλλιώς ο λογιστής μπορεί να ορίσει κωδικό απευθείας από την κάρτα Portal.

    Body: { "identifier": "<email ή ΑΦΜ>" }
    """
    from django.db.models import Q
    from accounting.models import ClientProfile
    from accounting.services.email_service import EmailService

    generic = Response({
        'detail': 'Αν υπάρχει λογαριασμός, στάλθηκε σύνδεσμος ορισμού κωδικού στο '
                  'email του πελάτη.'
    })

    identifier = (request.data.get('identifier') or '').strip()
    if not identifier:
        return generic

    # Πελάτης με αυτό το email ή ΑΦΜ που ΕΧΕΙ portal user.
    profile = (ClientProfile.objects
               .filter(Q(email__iexact=identifier) | Q(afm=identifier))
               .exclude(user__isnull=True)
               .first())
    if profile is not None:
        try:
            EmailService.send_portal_invite(profile)
        except Exception:
            logger.exception('Self-service password reset email failed for %s',
                             getattr(profile, 'afm', '?'))
    return generic
