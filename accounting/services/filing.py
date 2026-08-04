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


_MAGIC_MISSING_WARNED = False


def _reject_dangerous_content(uploaded_file):
    """Best-effort έλεγχος πραγματικού περιεχομένου με python-magic (αν υπάρχει)."""
    global _MAGIC_MISSING_WARNED
    try:
        import magic
    except ImportError:
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
        return
    if detected in _DANGEROUS_MIME_TYPES:
        raise ValidationError(
            'Το περιεχόμενο του αρχείου δεν αντιστοιχεί σε αποδεκτό τύπο εγγράφου.'
        )


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


def create_client_document(client, uploaded_file, category='general', obligation=None,
                           year=None, month=None, user=None, description='',
                           on_existing='version'):
    """
    Το μοναδικό σημείο δημιουργίας ClientDocument από upload.

    - Επικυρώνει το αρχείο βάσει ρυθμίσεων (validate_upload)
    - Κρατά το ΠΡΑΓΜΑΤΙΚΟ αρχικό όνομα και μετά εφαρμόζει τον Κανόνα
      Ονοματολογίας των ρυθμίσεων + sanitize (apply_naming)
    - Παίρνει κατηγορία/έτος/μήνα από την υποχρέωση αν δεν δόθηκαν
    - Αν υπάρχει ήδη τρέχον έγγραφο για τον ίδιο συνδυασμό:
      on_existing='version' → νέα έκδοση, 'replace' → αντικατάσταση (v1),
      'keep' → νέο ανεξάρτητο έγγραφο ΧΩΡΙΣ να πειραχτεί το υπάρχον
      (υποχρεωτικό για ανώνυμα uploads πελατών — δεν επιτρέπεται να
      εκτοπίζουν έγγραφα του γραφείου)
    - Επιβάλλει το κεντρικό permission matrix (require_document_mutation_perms)
      ΑΦΟΥ προσδιοριστεί race-safe (select_for_update) αν υπάρχει conflict,
      αλλά ΠΡΙΝ από κάθε DB αλλαγή ή file I/O
    - Δημιουργεί on-demand τους φακέλους για το έτος του εγγράφου

    Lifecycle εγγύηση (DB + storage ΔΕΝ είναι atomic από μόνα τους — υπάρχει
    compensating cleanup):
    - Σε αποτυχία DB save το νέο φυσικό αρχείο διαγράφεται (όχι orphans).
    - Το παλιό φυσικό αρχείο (replace) διαγράφεται ΜΟΝΟ μετά το commit
      (transaction.on_commit) — σε failure μένουν παλιό row ΚΑΙ παλιό αρχείο.
    - Σε version failure το παλιό document παραμένει is_current=True
      (rollback του conditional update).

    Returns: ClientDocument
    Raises: ValidationError (μη αποδεκτό αρχείο/ασυνέπεια),
            PermissionDenied (permission matrix)
    """
    from django.core.exceptions import ValidationError
    from django.db import transaction
    from accounting.models import ClientDocument

    validate_upload(uploaded_file)
    original_name = os.path.basename(uploaded_file.name or '') or 'unnamed_file'

    # Data-integrity invariant ΠΡΙΝ από κάθε file I/O ή row: η υποχρέωση
    # (αν δόθηκε) πρέπει να ανήκει στον ίδιο πελάτη
    if obligation is not None and client is not None \
            and obligation.client_id != client.id:
        raise ValidationError(
            'Η υποχρέωση ανήκει σε διαφορετικό πελάτη από το έγγραφο.')

    if obligation:
        year = year or obligation.year
        month = month or obligation.month
    now = datetime.now()
    year = int(year or now.year)
    month = int(month or now.month)

    apply_naming(uploaded_file, client, category=category, year=year, month=month)

    # Φάκελοι για το έτος του εγγράφου (idempotent, καλύπτει νέα χρονιά)
    ensure_folders(client, year=year)

    with transaction.atomic():
        # Race-safe conflict detection: κλειδώνουμε το υποψήφιο υπάρχον row
        # ώστε δύο ταυτόχρονα requests να μη δουν και τα δύο «δεν υπάρχει».
        existing = None
        if on_existing != 'keep':
            conflict_qs = ClientDocument.objects.select_for_update().filter(
                client=client, is_current=True)
            if obligation:
                conflict_qs = conflict_qs.filter(obligation=obligation)
            if category and category != 'general':
                conflict_qs = conflict_qs.filter(document_category=category)
            existing = conflict_qs.first()

        has_conflict = bool(
            existing and existing.year == year and existing.month == month)
        if has_conflict:
            mutation = 'replace' if on_existing == 'replace' else 'version'
        else:
            mutation = 'create'

        # Permission matrix ΜΕΤΑ τον race-safe προσδιορισμό του conflict,
        # ΠΡΙΝ από οποιαδήποτε αλλαγή ή file I/O
        require_document_mutation_perms(user, mutation)

        if mutation == 'version':
            doc = existing.create_new_version(
                new_file=uploaded_file, user=user,
                original_filename=original_name,
            )
            if description:
                doc.description = description
                doc.save(update_fields=['description'])
            _queue_text_extraction(doc)
            return doc

        old_file_name = None
        if mutation == 'replace':
            # Το παλιό row φεύγει μέσα στο transaction· το παλιό ΦΥΣΙΚΟ αρχείο
            # διαγράφεται μόνο μετά το commit — σε failure μένουν και τα δύο.
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
            version=1,
            is_current=True,
            description=description,
            uploaded_by=user,
        )
        # Το save() γράφει πρώτα το φυσικό αρχείο και μετά το row· σε αποτυχία
        # του row το αρχείο καθαρίζεται (compensating cleanup) και το
        # transaction κάνει rollback κάθε DB αλλαγή (και το delete του replace).
        try:
            doc.save()
        except Exception:
            _delete_stored_file(doc)
            raise

        if old_file_name:
            storage = doc.file.storage
            transaction.on_commit(
                lambda: _safe_storage_delete(storage, old_file_name))

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
