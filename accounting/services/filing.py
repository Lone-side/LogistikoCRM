# -*- coding: utf-8 -*-
"""
Ενιαία υπηρεσία αρχειοθέτησης εγγράφων πελατών.

Μοναδική πηγή αλήθειας για:
- Διαδρομές φακέλων πελατών (βάσει FilingSystemSettings)
- Δημιουργία δέντρου φακέλων (idempotent, ανά έτος)
- Επικύρωση uploads (επιτρεπόμενες καταλήξεις/μέγεθος από ρυθμίσεις)
- Δημιουργία ClientDocument με versioning

Όλα τα upload endpoints και signals πρέπει να περνούν από εδώ ώστε
τα αρχεία και οι φάκελοι να καταλήγουν πάντα στην ίδια δομή:
clients/{ΑΦΜ}_{Επωνυμία}/{00_ΜΟΝΙΜΑ | ΕΤΟΣ/ΜΗΝΑΣ | ΕΤΟΣ/13_ΕΤΗΣΙΑ}/{κατηγορία}/
"""
import logging
import os
from datetime import datetime

from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


def _get_filing_settings():
    """FilingSystemSettings singleton — None αν η βάση δεν είναι διαθέσιμη."""
    try:
        from settings.models import FilingSystemSettings
        return FilingSystemSettings.get_settings()
    except Exception:
        return None


def get_archive_root():
    """Απόλυτο root αρχειοθέτησης: FilingSystemSettings → ARCHIVE_ROOT env → MEDIA_ROOT."""
    filing_settings = _get_filing_settings()
    if filing_settings:
        return filing_settings.get_archive_root()
    from django.conf import settings as dj_settings
    return os.environ.get('ARCHIVE_ROOT', str(dj_settings.MEDIA_ROOT))


def get_client_folder_path(client):
    """Απόλυτο path του βασικού φακέλου πελάτη: {archive_root}/clients/{ΑΦΜ}_{Επωνυμία}."""
    from accounting.models import get_client_folder
    return os.path.join(get_archive_root(), get_client_folder(client))


def get_document_dir(client, category, year=None, month=None):
    """
    Σχετικός φάκελος (χωρίς filename) για έγγραφο, βάσει τύπου κατηγορίας:
    - permanent: clients/{ΑΦΜ}_{Επων}/00_ΜΟΝΙΜΑ/{category}
    - monthly:   clients/{ΑΦΜ}_{Επων}/{YYYY}/{MM ή 01_Ιανουάριος}/{category}
    - yearend:   clients/{ΑΦΜ}_{Επων}/{YYYY}/13_ΕΤΗΣΙΑ/{category}
    """
    from accounting.models import ClientDocument, get_client_folder

    client_folder = get_client_folder(client)
    category = category or 'general'
    filing_settings = _get_filing_settings()
    folder_type = ClientDocument.CATEGORY_FOLDER_TYPE.get(category, 'monthly')

    if folder_type == 'permanent':
        permanent_name = '00_ΜΟΝΙΜΑ'
        if filing_settings and filing_settings.enable_permanent_folder:
            permanent_name = filing_settings.permanent_folder_name
        return os.path.join(client_folder, permanent_name, category)

    now = datetime.now()
    year = year or now.year
    month = month or now.month

    if folder_type == 'yearend':
        yearend_name = '13_ΕΤΗΣΙΑ'
        if filing_settings and filing_settings.enable_yearend_folder:
            yearend_name = filing_settings.yearend_folder_name
        return os.path.join(client_folder, str(year), yearend_name, category)

    if filing_settings:
        month_str = filing_settings.get_month_folder_name(month)
    else:
        month_str = f"{month:02d}"
    return os.path.join(client_folder, str(year), month_str, category)


def validate_upload(uploaded_file):
    """
    Επικύρωση αρχείου βάσει FilingSystemSettings (καταλήξεις + μέγεθος).
    Raises ValidationError με ελληνικό μήνυμα.
    """
    if not uploaded_file:
        raise ValidationError('Δεν επιλέχθηκε αρχείο.')

    filing_settings = _get_filing_settings()
    if filing_settings:
        allowed = filing_settings.get_allowed_extensions_list()
        max_bytes = filing_settings.get_max_file_size_bytes()
        max_mb = filing_settings.max_file_size_mb
    else:
        allowed = ['.pdf', '.xlsx', '.xls', '.docx', '.doc',
                   '.jpg', '.jpeg', '.png', '.gif', '.zip', '.txt', '.csv', '.xml']
        max_bytes = 10 * 1024 * 1024
        max_mb = 10

    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in allowed:
        raise ValidationError(
            f'Η κατάληξη "{ext or "(χωρίς κατάληξη)"}" δεν επιτρέπεται. '
            f'Επιτρεπόμενες: {", ".join(allowed)}'
        )

    if uploaded_file.size > max_bytes:
        size_mb = uploaded_file.size / (1024 * 1024)
        raise ValidationError(
            f'Το αρχείο είναι πολύ μεγάλο ({size_mb:.1f}MB). '
            f'Μέγιστο επιτρεπόμενο: {max_mb}MB'
        )

    _reject_dangerous_content(uploaded_file)


# Περιεχόμενο που δεν δεχόμαστε ΠΟΤΕ ανεξαρτήτως κατάληξης — σημαντικό για
# τα ανώνυμα uploads του portal (π.χ. HTML με script μεταμφιεσμένο σε .pdf)
_DANGEROUS_MIME_TYPES = {
    'text/html', 'application/xhtml+xml', 'text/javascript',
    'application/javascript', 'application/x-dosexec', 'application/x-executable',
    'application/x-sharedlib', 'application/x-mach-binary', 'application/x-elf',
    'application/x-sh', 'application/x-msdownload',
}

# Επιτρεπτά detected MIME types — αντιστοιχούν στις επιτρεπόμενες
# καταλήξεις (pdf/office/εικόνες/zip/κείμενο). Το octet-stream επιτρέπεται
# συνειδητά: γενικό binary αποτέλεσμα του libmagic για αρκετά νόμιμα
# office formats — η άμυνα σε executables γίνεται από το blacklist πιο πάνω.
_ALLOWED_MIME_TYPES = {
    'application/pdf', 'image/jpeg', 'image/png', 'image/gif',
    'application/zip', 'text/plain', 'text/csv', 'text/xml',
    'application/xml', 'application/msword', 'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/CDFV2', 'application/octet-stream', 'application/x-empty',
    'image/webp', 'application/rtf', 'text/rtf',
}


def _libmagic_fail_closed():
    """Production mode: DEBUG=False Ή ρητό REQUIRE_LIBMAGIC=True."""
    from django.conf import settings as dj_settings
    return (not dj_settings.DEBUG) or getattr(
        dj_settings, 'REQUIRE_LIBMAGIC', False)


_MAGIC_MISSING_WARNED = False


def _reject_dangerous_content(uploaded_file):
    """
    Έλεγχος πραγματικού περιεχομένου με python-magic.

    Production mode (_libmagic_fail_closed): FAIL CLOSED —
    - ImportError του magic → reject upload
    - runtime exception από from_buffer → reject upload
    - κενό/άκυρο MIME αποτέλεσμα → reject upload
    - MIME εκτός _ALLOWED_MIME_TYPES → reject upload
    Development: μόνο warning σε απουσία magic (extension-only validation),
    αλλά το dangerous blacklist εφαρμόζεται πάντα όταν το magic λειτουργεί.
    """
    global _MAGIC_MISSING_WARNED
    fail_closed = _libmagic_fail_closed()
    try:
        import magic
    except ImportError:
        if fail_closed:
            raise ValidationError(
                'Ο έλεγχος περιεχομένου αρχείων δεν είναι διαθέσιμος — '
                'η μεταφόρτωση απορρίφθηκε.')
        if not _MAGIC_MISSING_WARNED:
            _MAGIC_MISSING_WARNED = True
            logger.warning(
                'python-magic/libmagic δεν είναι εγκατεστημένο — ο έλεγχος '
                'πραγματικού περιεχομένου των uploads ΔΕΝ εκτελείται. '
                'Εγκατάσταση: pip install python-magic (+ libmagic1).'
            )
        return
    try:
        uploaded_file.seek(0)
        detected = magic.from_buffer(uploaded_file.read(2048), mime=True)
        uploaded_file.seek(0)
    except Exception:
        if fail_closed:
            logger.exception('Αποτυχία libmagic detection (fail closed)')
            raise ValidationError(
                'Ο έλεγχος περιεχομένου του αρχείου απέτυχε — '
                'η μεταφόρτωση απορρίφθηκε.')
        return
    if detected in _DANGEROUS_MIME_TYPES:
        raise ValidationError(
            'Το περιεχόμενο του αρχείου δεν αντιστοιχεί σε αποδεκτό τύπο εγγράφου.'
        )
    if fail_closed:
        if not detected or not isinstance(detected, str):
            raise ValidationError(
                'Δεν αναγνωρίστηκε ο τύπος περιεχομένου του αρχείου — '
                'η μεταφόρτωση απορρίφθηκε.')
        if detected not in _ALLOWED_MIME_TYPES:
            raise ValidationError(
                'Ο τύπος περιεχομένου του αρχείου δεν επιτρέπεται.')


def apply_naming(uploaded_file, client, category=None, year=None, month=None):
    """
    Εφαρμόζει τον Κανόνα Ονοματολογίας των ρυθμίσεων στο όνομα του αρχείου
    (original/structured/date_prefix/afm_prefix) και το καθαρίζει (sanitize).

    Η ημερομηνία αναφοράς προκύπτει από year/month (1η του μήνα) ώστε το
    όνομα να συμφωνεί με τον φάκελο περιόδου, όχι με την ημέρα του upload.
    """
    from common.utils.file_validation import sanitize_filename

    filing_settings = _get_filing_settings()
    new_name = uploaded_file.name
    if filing_settings:
        try:
            ref_date = None
            if year and month:
                ref_date = datetime(int(year), int(month), 1)
            elif year:
                ref_date = datetime(int(year), 1, 1)
            new_name = filing_settings.generate_filename(
                uploaded_file.name,
                client=client,
                category=category,
                date=ref_date,
            )
        except Exception as e:
            logger.warning(f"Αποτυχία εφαρμογής κανόνα ονοματολογίας: {e}")
            new_name = uploaded_file.name
    uploaded_file.name = sanitize_filename(new_name)
    return uploaded_file.name


def ensure_folders(client, year=None):
    """
    Δημιουργεί (idempotent) το πλήρες δέντρο φακέλων του πελάτη για το
    δεδομένο έτος (default: τρέχον) + INFO.txt στη ρίζα του πελάτη.
    Επιστρέφει το απόλυτο base path του πελάτη, ή None σε αποτυχία I/O.
    """
    filing_settings = _get_filing_settings()
    base_path = get_client_folder_path(client)
    year = year or datetime.now().year

    try:
        # === ΜΟΝΙΜΟΣ ΦΑΚΕΛΟΣ ===
        if filing_settings and not filing_settings.enable_permanent_folder:
            pass
        else:
            permanent_name = (
                filing_settings.permanent_folder_name if filing_settings else '00_ΜΟΝΙΜΑ'
            )
            permanent_categories = (
                filing_settings.get_permanent_folder_categories()
                if filing_settings else
                ['registration', 'contracts', 'licenses', 'correspondence']
            )
            for category in permanent_categories:
                os.makedirs(os.path.join(base_path, permanent_name, category), exist_ok=True)

        # === ΜΗΝΙΑΙΟΙ ΦΑΚΕΛΟΙ ΕΤΟΥΣ ===
        year_path = os.path.join(base_path, str(year))
        monthly_categories = (
            filing_settings.get_monthly_folder_categories()
            if filing_settings else
            ['vat', 'apd', 'myf', 'payroll', 'invoices_issued',
             'invoices_received', 'bank', 'receipts', 'general']
        )
        for month in range(1, 13):
            month_name = (
                filing_settings.get_month_folder_name(month)
                if filing_settings else f"{month:02d}"
            )
            for category in monthly_categories:
                os.makedirs(os.path.join(year_path, month_name, category), exist_ok=True)

        # === ΕΤΗΣΙΟΣ ΦΑΚΕΛΟΣ ===
        if filing_settings and not filing_settings.enable_yearend_folder:
            pass
        else:
            yearend_name = (
                filing_settings.yearend_folder_name if filing_settings else '13_ΕΤΗΣΙΑ'
            )
            yearend_categories = (
                filing_settings.get_yearend_folder_categories()
                if filing_settings else
                ['e1', 'e2', 'e3', 'enfia', 'balance', 'audit']
            )
            for category in yearend_categories:
                os.makedirs(os.path.join(year_path, yearend_name, category), exist_ok=True)

        _write_info_file(client, base_path)
        return base_path

    except OSError as e:
        logger.error(f"Αποτυχία δημιουργίας φακέλων πελάτη id={client.pk}: {e}")
        return None


def _write_info_file(client, base_path):
    """Γράφει/ανανεώνει το INFO.txt στη ρίζα του φακέλου πελάτη."""
    info_path = os.path.join(base_path, 'INFO.txt')
    with open(info_path, 'w', encoding='utf-8') as f:
        f.write("ΦΑΚΕΛΟΣ ΠΕΛΑΤΗ\n")
        f.write(f"{'=' * 50}\n\n")
        f.write(f"Επωνυμία: {client.eponimia}\n")
        f.write(f"ΑΦΜ: {client.afm}\n")
        f.write(f"ΔΟΥ: {client.doy or '-'}\n")
        f.write(f"Email: {client.email or '-'}\n")
        f.write(f"Τηλέφωνο: {client.kinito_tilefono or client.tilefono_epixeirisis_1 or '-'}\n")
        f.write(f"\nΕνημέρωση: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
        f.write(f"\n{'=' * 50}\n")
        f.write("ΔΟΜΗ ΦΑΚΕΛΩΝ\n")
        f.write(f"{'=' * 50}\n\n")
        f.write("00_ΜΟΝΙΜΑ/      → Μόνιμα έγγραφα (συμβάσεις, καταστατικό)\n")
        f.write("YYYY/           → Φάκελος έτους\n")
        f.write("  ├─ 01-12/         → Μηνιαίοι φάκελοι (ΦΠΑ, ΑΠΔ, ΜΥΦ, μισθοδοσία...)\n")
        f.write("  └─ 13_ΕΤΗΣΙΑ/     → Ετήσιες δηλώσεις (Ε1, Ε3, ΕΝΦΙΑ, ισολογισμός)\n")


# ---------------------------------------------------------------------------
# Permission matrix για document mutations (κεντρική πολιτική — ισχύει για
# ΟΛΟΥΣ τους callers του filing service):
#   create (νέο ανεξάρτητο / keep):  add_clientdocument
#   version (νέα έκδοση):            add_clientdocument + change_clientdocument
#   replace (αντικατάσταση):         add + change + delete_clientdocument
# ---------------------------------------------------------------------------
MUTATION_PERMS = {
    'create': ('accounting.add_clientdocument',),
    'version': ('accounting.add_clientdocument',
                'accounting.change_clientdocument'),
    'replace': ('accounting.add_clientdocument',
                'accounting.change_clientdocument',
                'accounting.delete_clientdocument'),
}


def require_document_mutation_perms(user, mutation):
    """
    Fail-closed έλεγχος του permission matrix. user=None (ανώνυμα portal
    uploads) επιτρέπεται ΜΟΝΟ για 'create' — ποτέ version/replace.
    Raises django PermissionDenied (→ 403 σε DRF και Django views).
    """
    from django.core.exceptions import PermissionDenied
    required = MUTATION_PERMS[mutation]
    if user is None:
        if mutation != 'create':
            raise PermissionDenied(
                'Δεν επιτρέπεται αντικατάσταση/νέα έκδοση χωρίς χρήστη.')
        return
    if not all(user.has_perm(p) for p in required):
        raise PermissionDenied(
            'Δεν έχετε δικαίωμα για αυτή την ενέργεια στο έγγραφο.')


def _delete_stored_file(doc):
    """Best-effort διαγραφή του φυσικού αρχείου ενός (μη-committed) doc."""
    try:
        if doc.file and doc.file.name:
            doc.file.storage.delete(doc.file.name)
    except Exception as e:
        logger.warning(f"Δεν καθαρίστηκε orphan αρχείο: {e}")


VALID_ON_EXISTING = ('version', 'replace', 'keep')

# Λογικό εύρος ετών για document metadata
MIN_DOCUMENT_YEAR = 2000
MAX_DOCUMENT_YEAR = 2100


class MultipleCurrentDocumentsError(ValidationError):
    """Corrupted κατάσταση: >1 current rows στο ίδιο exact logical key."""


class DocumentKeyConflict(Exception):
    """Ελεγχόμενο conflict (409): το target exact key είναι κατειλημμένο."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message
        self.status_code = 409


def validate_document_key_inputs(category, year, month):
    """
    Κοινό validation layer για τα key inputs ΠΡΙΝ από lock/storage mutation.
    Raises ValidationError (→ 400 στα endpoints), ποτέ 500.
    """
    from accounting.models import ClientDocument
    valid_categories = {c[0] for c in ClientDocument.CATEGORY_CHOICES}
    if (category or 'general') not in valid_categories:
        raise ValidationError('Μη έγκυρη κατηγορία εγγράφου.')
    try:
        year = int(year)
        month = int(month)
    except (TypeError, ValueError):
        raise ValidationError('Μη έγκυρο έτος ή μήνας.')
    if not (MIN_DOCUMENT_YEAR <= year <= MAX_DOCUMENT_YEAR):
        raise ValidationError('Μη έγκυρο έτος.')
    if not (1 <= month <= 12):
        raise ValidationError('Μη έγκυρος μήνας.')
    return year, month


def find_current_for_key(client, category, year, month, obligation=None,
                         slot='', for_update=False):
    """
    Ο ΜΟΝΑΔΙΚΟΣ exact-conflict helper — τον χρησιμοποιούν filing service,
    ClientDocument.check_existing, check-existing API, upload-with-version
    pre-check, admin flows και attach/detach.

    Πλήρες logical key: client + document_category ΑΚΡΙΒΩΣ (και το
    'general') + year + month + obligation ΑΚΡΙΒΩΣ (obligation__isnull=True
    όταν λείπει) + slot. Πάντα is_current=True. Όλα τα φίλτρα μπαίνουν
    ΠΡΙΝ από κάθε select — κανένα .first() πριν ελεγχθεί το πλήθος.

    Returns: None (κανένα match) ή ακριβώς ένα ClientDocument.
    Raises: MultipleCurrentDocumentsError (fail closed, internal-ID log)
            για >1 matches — ΔΕΝ επιλέγεται αυθαίρετα ένα.
    """
    from accounting.models import ClientDocument
    qs = ClientDocument.objects.filter(
        client=client,
        is_current=True,
        document_category=category or 'general',
        year=year,
        month=month,
        slot=slot or '',
    )
    if obligation is not None:
        qs = qs.filter(obligation=obligation)
    else:
        qs = qs.filter(obligation__isnull=True)
    if for_update:
        qs = qs.select_for_update()
    matches = list(qs)
    if len(matches) > 1:
        logger.error(
            'Πολλαπλά current documents στο ίδιο conflict key: '
            'client id=%s, ids=%s',
            client.pk, sorted(d.pk for d in matches))
        raise MultipleCurrentDocumentsError(
            'Υπάρχουν πολλαπλά τρέχοντα έγγραφα για αυτόν τον συνδυασμό — '
            'απαιτείται χειροκίνητη διόρθωση '
            '(audit_clientdocument_invariants).')
    return matches[0] if matches else None


def create_client_document(client, uploaded_file, category='general', obligation=None,
                           year=None, month=None, user=None, description='',
                           on_existing='version'):
    """
    Το μοναδικό σημείο δημιουργίας ClientDocument από upload.

    Σειρά (καμία μόνιμη αλλαγή storage πριν από τα permissions):
    1. Input validation (on_existing, validate_upload, cross-client invariant)
       — χωρίς μόνιμα side effects
    2. Parent serialization lock: select_for_update στο MonthlyObligation
       (όταν υπάρχει obligation) αλλιώς στο ClientProfile row — αυτό
       σειριοποιεί και τα ταυτόχρονα ΠΡΩΤΑ uploads του ίδιου key, όπου
       δεν υπάρχει ακόμη conflict row για να κλειδωθεί
    3. Exact conflict lookup στο πλήρες logical key (_exact_conflict_qs)·
       πολλαπλά matching current rows → fail closed (ValidationError +
       internal-ID log), ΔΕΝ επιλέγεται αυθαίρετα ένα
    4. Mutation determination (create/version/replace)
    5. require_document_mutation_perms — permission matrix
    6. ΜΟΝΟ μετά: apply_naming, ensure_folders, storage write, DB mutation

    on_existing: 'version' (νέα έκδοση), 'replace' (αντικατάσταση),
    'keep' (νέο ανεξάρτητο — υποχρεωτικό για ανώνυμα portal uploads).

    Lifecycle (DB + storage ΔΕΝ είναι atomic — compensating cleanup):
    - Outer compensation: σε ΚΑΘΕ αποτυχία μετά τη δημιουργία του νέου
      φυσικού αρχείου (row save, μεταγενέστερο βήμα, commit) το νέο αρχείο
      διαγράφεται ΜΟΝΟ αφού επιβεβαιωθεί ότι το row ΔΕΝ υπάρχει στη βάση —
      σε ambiguous commit outcome (row τελικά committed) το αρχείο
      ΔΕΝ διαγράφεται, ώστε να μη μείνει committed row χωρίς αρχείο.
    - Replace: το παλιό φυσικό αρχείο διαγράφεται ΑΠΟΚΛΕΙΣΤΙΚΑ με
      transaction.on_commit — σε failure μένουν παλιό row ΚΑΙ παλιό αρχείο.
    - Version failure: το παλιό document παραμένει is_current=True (rollback).

    Returns: ClientDocument
    Raises: ValidationError (μη αποδεκτό αρχείο/ασυνέπεια/άκυρο on_existing),
            PermissionDenied (permission matrix)
    """
    from django.core.exceptions import ValidationError
    from django.db import transaction
    from accounting.models import ClientDocument, ClientProfile, MonthlyObligation

    # === 1. Input validation — κανένα μόνιμο side effect ===
    if on_existing not in VALID_ON_EXISTING:
        raise ValidationError(
            f"Μη έγκυρη τιμή on_existing — επιτρέπονται: "
            f"{', '.join(VALID_ON_EXISTING)}")
    validate_upload(uploaded_file)
    original_name = os.path.basename(uploaded_file.name or '') or 'unnamed_file'

    if obligation is not None and client is not None \
            and obligation.client_id != client.id:
        raise ValidationError(
            'Η υποχρέωση ανήκει σε διαφορετικό πελάτη από το έγγραφο.')

    if obligation:
        year = year or obligation.year
        month = month or obligation.month
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    # Κοινό key-input validation (category/year/month) — 400, ποτέ 500
    year, month = validate_document_key_inputs(category, year, month)

    # on_existing='keep' (portal): μοναδικό slot ώστε το νέο ανεξάρτητο
    # έγγραφο να ζει σε ΔΙΚΟ του exact key — ΠΟΤΕ δεύτερο current στο ίδιο
    # key, ΠΟΤΕ εκτοπισμός εγγράφων του γραφείου (βλ. ClientDocument.slot).
    slot = ''
    if on_existing == 'keep':
        import uuid
        slot = uuid.uuid4().hex[:32]

    new_file_ref = {'storage': None, 'name': None, 'pk': None}
    try:
        with transaction.atomic():
            # === 2. Parent serialization locks — deterministic ordering:
            # ΠΑΝΤΑ πρώτα το ClientProfile row και μετά το MonthlyObligation
            # (ίδια σειρά και στα attach/detach services → όχι deadlocks) ===
            ClientProfile.objects.select_for_update().get(pk=client.pk)
            if obligation is not None:
                MonthlyObligation.objects.select_for_update().get(
                    pk=obligation.pk)

            # === 3. Exact conflict lookup (κοινός helper, fail closed) ===
            existing = None
            mutation = 'create'
            if on_existing != 'keep':
                existing = find_current_for_key(
                    client, category, year, month, obligation,
                    slot=slot, for_update=True)
                if existing is not None:
                    mutation = 'replace' if on_existing == 'replace' else 'version'

            # === 4-5. Permission matrix ΠΡΙΝ από κάθε αλλαγή/file I/O ===
            require_document_mutation_perms(user, mutation)

            # === 6. Naming/folders/storage — μόνο μετά τα permissions ===
            apply_naming(uploaded_file, client, category=category,
                         year=year, month=month)
            ensure_folders(client, year=year)

            if mutation == 'version':
                doc = existing.create_new_version(
                    new_file=uploaded_file, user=user,
                    original_filename=original_name,
                    description=description or None,
                )
                new_file_ref.update(storage=doc.file.storage,
                                    name=doc.file.name, pk=doc.pk)
            else:
                old_file_name = None
                if mutation == 'replace':
                    # Το παλιό row φεύγει μέσα στο transaction· το παλιό
                    # ΦΥΣΙΚΟ αρχείο διαγράφεται μόνο on_commit.
                    old_file_name = existing.file.name if existing.file else None
                    existing.delete()

                doc = ClientDocument(
                    client=client,
                    obligation=obligation,
                    file=uploaded_file,
                    original_filename=original_name,
                    document_category=category or 'general',
                    year=year,
                    month=month,
                    slot=slot,
                    version=1,
                    is_current=True,
                    description=description,
                    uploaded_by=user,
                )
                try:
                    doc.save()
                except Exception:
                    # Το save μπορεί να αποτύχει ΜΕΤΑ το storage write
                    # (insert/signal) — καθάρισε το γραμμένο αρχείο
                    _delete_stored_file(doc)
                    raise
                new_file_ref.update(storage=doc.file.storage,
                                    name=doc.file.name, pk=doc.pk)

                if old_file_name:
                    storage = doc.file.storage
                    transaction.on_commit(
                        lambda: _safe_storage_delete(storage, old_file_name))
    except Exception:
        # Outer compensation: καλύπτει ΚΑΘΕ αποτυχία μετά το storage write
        # (row save, μεταγενέστερα βήματα, commit). Διαγραφή ΜΟΝΟ αν το row
        # δεν υπάρχει στη βάση — προστασία σε ambiguous commit outcome.
        if new_file_ref['name']:
            try:
                committed = new_file_ref['pk'] is not None and \
                    ClientDocument.objects.filter(
                        pk=new_file_ref['pk']).exists()
                if not committed:
                    new_file_ref['storage'].delete(new_file_ref['name'])
            except Exception as cleanup_err:
                logger.warning(f"Δεν καθαρίστηκε orphan αρχείο: {cleanup_err}")
        raise

    _queue_text_extraction(doc)
    return doc



def _safe_storage_delete(storage, name):
    """Διαγραφή παλιού αρχείου μετά το commit — ποτέ δεν ρίχνει."""
    try:
        storage.delete(name)
    except Exception as e:
        logger.warning(f"Δεν διαγράφηκε το παλιό αρχείο {os.path.basename(name)!r}: {e}")


def _queue_text_extraction(doc):
    """Δρομολόγηση εξαγωγής κειμένου — δεν πρέπει ποτέ να σπάσει το upload."""
    try:
        from accounting.services import text_extraction
        text_extraction.queue_extraction(doc)
    except Exception as e:
        logger.warning(f"Αποτυχία δρομολόγησης εξαγωγής κειμένου: {e}")


# ===========================================================================
# Transactional services για structural μεταβολές ClientDocument
# (attach/detach obligation, delete) — ΟΛΕΣ οι διαδρομές API/admin
# περνούν από εδώ. Deterministic lock ordering: ΠΑΝΤΑ ClientProfile
# πρώτα, μετά MonthlyObligation (ίδιο και στο create_client_document).
# ===========================================================================

def _audit_document_event(user, document, event):
    """Audit χωρίς PII/filesystem paths — μόνο internal IDs."""
    try:
        from common.models import AuditLog
        AuditLog.objects.create(
            user=user if getattr(user, 'is_authenticated', False) else None,
            action='update',
            model_name='ClientDocument',
            object_id=str(document.pk),
            description=(
                f'{event}: document id={document.pk}, '
                f'client id={document.client_id}, '
                f'obligation id={document.obligation_id}'
            ),
            severity='low',
        )
    except Exception:
        logger.warning('Δεν γράφτηκε document audit event', exc_info=True)


def attach_document_service(user, document, obligation):
    """
    Attach document ↔ obligation (structural: το obligation είναι μέρος
    του exact logical key).

    Σειρά: input validation → permission validation → locks (client →
    obligation) → exact target-key conflict lookup (fail closed σε
    πολλαπλά) → controlled conflict (DocumentKeyConflict/409) αν το target
    key είναι κατειλημμένο → mutation → audit (χωρίς PII/paths).

    Raises: ValidationError (400), DocumentKeyConflict (409),
            PermissionDenied (403), MultipleCurrentDocumentsError (409).
    """
    from django.core.exceptions import PermissionDenied
    from django.db import transaction
    from accounting.models import ClientProfile, MonthlyObligation

    # 1. Input validation
    if obligation is None:
        raise ValidationError('Απαιτείται υποχρέωση.')
    if document.client_id != obligation.client_id:
        raise ValidationError('Η υποχρέωση ανήκει σε διαφορετικό πελάτη.')
    if document.year != obligation.year or document.month != obligation.month:
        raise ValidationError(
            'Η περίοδος του εγγράφου δεν συμφωνεί με την υποχρέωση.')
    if document.obligation_id == obligation.pk:
        return document  # no-op

    # 2. Permission validation
    if user is None or not user.has_perm('accounting.change_clientdocument'):
        raise PermissionDenied(
            'Δεν έχετε δικαίωμα για αυτή την ενέργεια στο έγγραφο.')

    with transaction.atomic():
        # 3. Locks: client πρώτα, μετά obligation (deterministic)
        ClientProfile.objects.select_for_update().get(pk=document.client_id)
        MonthlyObligation.objects.select_for_update().get(pk=obligation.pk)

        # 4-6. Exact target-key conflict (μόνο για current docs — τα
        # historical δεν συμμετέχουν στο invariant)
        if document.is_current:
            occupied = find_current_for_key(
                document.client, document.document_category,
                document.year, document.month, obligation,
                slot=document.slot, for_update=True)
            if occupied is not None and occupied.pk != document.pk:
                raise DocumentKeyConflict(
                    'Υπάρχει ήδη τρέχον έγγραφο συνδεδεμένο με αυτή την '
                    'υποχρέωση για την ίδια κατηγορία/περίοδο.')

        # 7. Mutation
        document.obligation = obligation
        document.full_clean()
        document.save()

    # 8. Audit
    _audit_document_event(user, document, 'attach-obligation')
    return document


def detach_document_service(user, document):
    """
    Detach document από obligation — συμμετρικό του attach: locks (client),
    exact null-obligation target-key conflict, controlled 409, audit.
    """
    from django.core.exceptions import PermissionDenied
    from django.db import transaction
    from accounting.models import ClientProfile

    if document.obligation_id is None:
        return document  # no-op

    if user is None or not user.has_perm('accounting.change_clientdocument'):
        raise PermissionDenied(
            'Δεν έχετε δικαίωμα για αυτή την ενέργεια στο έγγραφο.')

    with transaction.atomic():
        ClientProfile.objects.select_for_update().get(pk=document.client_id)

        if document.is_current:
            occupied = find_current_for_key(
                document.client, document.document_category,
                document.year, document.month, None,
                slot=document.slot, for_update=True)
            if occupied is not None and occupied.pk != document.pk:
                raise DocumentKeyConflict(
                    'Υπάρχει ήδη ανεξάρτητο τρέχον έγγραφο στην ίδια '
                    'κατηγορία/περίοδο — η αποσύνδεση θα δημιουργούσε '
                    'διπλό τρέχον έγγραφο.')

        document.obligation = None
        document.full_clean()
        document.save()

    _audit_document_event(user, document, 'detach-obligation')
    return document


def delete_document_service(user, document):
    """
    Πολιτική διαγραφής versioned documents:
    - Root/ενδιάμεση version με descendants → ΑΠΑΓΟΡΕΥΕΤΑΙ (ValidationError)·
      διαγράφεται πρώτα ολόκληρη η ουρά (νεότερες εκδόσεις).
    - Current version με previous_version → atomic: διαγραφή row +
      προαγωγή της αμέσως προηγούμενης σε current (δεν μένει chain
      χωρίς current).
    - Current version χωρίς previous (μοναδική) → απλή διαγραφή.
    DB mutation πρώτα· το φυσικό αρχείο διαγράφεται ΜΟΝΟ με
    transaction.on_commit· αποτυχία storage → generic warning χωρίς
    path/PII. Καμία διαγραφή δεν αφήνει invariant violation.
    """
    from django.core.exceptions import PermissionDenied
    from django.db import transaction
    from accounting.models import ClientDocument, ClientProfile

    if user is None or not user.has_perm('accounting.delete_clientdocument'):
        raise PermissionDenied(
            'Δεν έχετε δικαίωμα διαγραφής εγγράφου.')

    with transaction.atomic():
        ClientProfile.objects.select_for_update().get(pk=document.client_id)
        locked = ClientDocument.objects.select_for_update().get(
            pk=document.pk)

        if locked.next_versions.exists():
            raise ValidationError(
                'Το έγγραφο έχει νεότερες εκδόσεις — διαγράψτε πρώτα '
                'τις νεότερες εκδόσεις.')

        storage = locked.file.storage if locked.file else None
        file_name = locked.file.name if locked.file else None
        promote_pk = (locked.previous_version_id
                      if locked.is_current else None)

        locked.delete()

        if promote_pk:
            # Ατομική προαγωγή της αμέσως προηγούμενης — η chain δεν
            # μένει ποτέ χωρίς current
            ClientDocument.objects.filter(pk=promote_pk).update(
                is_current=True)

        if file_name:
            transaction.on_commit(
                lambda: _safe_storage_delete(storage, file_name))

    _audit_document_event(user, document, 'delete-document')
