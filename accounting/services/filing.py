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


VALID_ON_EXISTING = ('version', 'replace', 'keep')


def _exact_conflict_qs(ClientDocument, client, category, year, month, obligation):
    """
    Το ΠΛΗΡΕΣ logical conflict key — όλα τα φίλτρα ΠΡΙΝ από κάθε select:
    client, document_category ΑΚΡΙΒΩΣ (και το 'general'), year, month,
    obligation ΑΚΡΙΒΩΣ (obligation__isnull=True όταν δεν υπάρχει).
    Δεν αφήνουμε ordering/uploaded_at να διαλέξει «κάποιο» row.
    """
    qs = ClientDocument.objects.select_for_update().filter(
        client=client,
        is_current=True,
        document_category=category or 'general',
        year=year,
        month=month,
    )
    if obligation is not None:
        qs = qs.filter(obligation=obligation)
    else:
        qs = qs.filter(obligation__isnull=True)
    return qs


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
    year = int(year or now.year)
    month = int(month or now.month)

    new_file_ref = {'storage': None, 'name': None, 'pk': None}
    try:
        with transaction.atomic():
            # === 2. Parent serialization lock (βλ. docstring) ===
            if obligation is not None:
                MonthlyObligation.objects.select_for_update().get(
                    pk=obligation.pk)
            else:
                ClientProfile.objects.select_for_update().get(pk=client.pk)

            # === 3. Exact conflict lookup ===
            existing = None
            mutation = 'create'
            if on_existing != 'keep':
                matches = list(_exact_conflict_qs(
                    ClientDocument, client, category, year, month, obligation))
                if len(matches) > 1:
                    logger.error(
                        'Πολλαπλά current documents στο ίδιο conflict key: '
                        'client id=%s, ids=%s',
                        client.pk, sorted(d.pk for d in matches))
                    raise ValidationError(
                        'Υπάρχουν πολλαπλά τρέχοντα έγγραφα για αυτόν τον '
                        'συνδυασμό — απαιτείται χειροκίνητη διόρθωση '
                        '(audit_clientdocument_invariants).')
                existing = matches[0] if matches else None
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
