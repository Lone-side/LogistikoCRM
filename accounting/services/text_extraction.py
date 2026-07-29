# -*- coding: utf-8 -*-
"""
Εξαγωγή κειμένου από έγγραφα πελατών (OCR-lite).

- Ψηφιακά PDF: pypdf (pure-Python, χωρίς εξωτερικά binaries)
- Σκαναρισμένα: προαιρετικά Tesseract, ΜΟΝΟ αν DOCUMENT_OCR_ENABLED=True
  και υπάρχει το binary στο σύστημα (δεν είναι hard dependency)

Το κείμενο τροφοδοτεί: αναζήτηση περιεχομένου, πρόταση κατηγορίας,
έλεγχο αναντιστοιχίας ΑΦΜ και «έξυπνη» πρόταση ονόματος στο upload.
"""
import logging
import os
import shutil

from django.conf import settings as dj_settings
from django.utils import timezone

from common.utils.afm import find_afm_candidates

logger = logging.getLogger(__name__)

# Όριο αποθηκευμένου κειμένου (χαρακτήρες) και σελίδων ανάγνωσης
MAX_TEXT_CHARS = 100_000
MAX_PAGES = 30

# Λέξεις-κλειδιά → κατηγορία ClientDocument (ίδια λογική με
# MonthlyObligation._get_category_from_obligation, εδώ για περιεχόμενο)
CATEGORY_KEYWORDS = [
    ('vat', ['ΦΠΑ', 'Φ.Π.Α', 'ΠΕΡΙΟΔΙΚΗ ΔΗΛΩΣΗ', 'VAT']),
    ('apd', ['ΑΠΔ', 'Α.Π.Δ', 'ΕΦΚΑ', 'ΑΝΑΛΥΤΙΚΗ ΠΕΡΙΟΔΙΚΗ']),
    ('myf', ['ΜΥΦ', 'ΣΥΓΚΕΝΤΡΩΤΙΚ']),
    ('payroll', ['ΜΙΣΘΟΔΟΣ', 'ΑΠΟΔΟΧ', 'ΜΙΣΘΩΤ']),
    ('e1', ['Ε1', 'ΔΗΛΩΣΗ ΦΟΡΟΛΟΓΙΑΣ ΕΙΣΟΔΗΜΑΤΟΣ']),
    ('e3', ['Ε3', 'ΟΙΚΟΝΟΜΙΚΩΝ ΣΤΟΙΧΕΙΩΝ']),
    ('enfia', ['ΕΝΦΙΑ', 'ΕΝ.Φ.Ι.Α', 'ΦΟΡΟΣ ΙΔΙΟΚΤΗΣΙΑΣ']),
    ('balance', ['ΙΣΟΛΟΓΙΣΜ']),
    ('invoices_issued', ['ΤΙΜΟΛΟΓΙΟ', 'ΤΙΜΟΛΟΓΙΑ', 'INVOICE']),
    ('bank', ['ΤΡΑΠΕΖ', 'EXTRAIT', 'STATEMENT', 'IBAN']),
    ('contracts', ['ΣΥΜΒΑΣΗ', 'ΣΥΜΦΩΝΗΤΙΚΟ', 'ΜΙΣΘΩΤΗΡΙΟ']),
    ('registration', ['ΚΑΤΑΣΤΑΤΙΚΟ', 'ΓΕΜΗ', 'Γ.Ε.ΜΗ', 'ΕΝΑΡΞΗ ΕΡΓΑΣΙΩΝ']),
]


def extract_text_from_file(fileobj, filename, max_pages=MAX_PAGES):
    """
    Εξάγει κείμενο από file-like object.

    Returns: (text, status) όπου status in ('done', 'failed', 'skipped')
    """
    ext = os.path.splitext(filename or '')[1].lower()

    if ext == '.pdf':
        try:
            from pypdf import PdfReader
            reader = PdfReader(fileobj)
            parts = []
            total = 0
            for page in reader.pages[:max_pages]:
                text = page.extract_text() or ''
                parts.append(text)
                total += len(text)
                if total >= MAX_TEXT_CHARS:
                    break
            text = '\n'.join(parts)[:MAX_TEXT_CHARS].strip()
            if text:
                return text, 'done'
            # Άδειο κείμενο → πιθανώς σκαναρισμένο· δοκιμή OCR αν επιτρέπεται
            ocr_text = _try_tesseract_pdf(fileobj)
            if ocr_text:
                return ocr_text[:MAX_TEXT_CHARS], 'done'
            return '', 'done'  # ψηφιακά άδειο, όχι σφάλμα
        except Exception as e:
            logger.warning(f"Αποτυχία ανάγνωσης PDF '{filename}': {e}")
            return '', 'failed'

    if ext in ('.jpg', '.jpeg', '.png'):
        ocr_text = _try_tesseract_image(fileobj)
        if ocr_text is None:
            return '', 'skipped'
        return ocr_text[:MAX_TEXT_CHARS], 'done'

    if ext in ('.txt', '.csv', '.xml'):
        try:
            fileobj.seek(0)
            data = fileobj.read(MAX_TEXT_CHARS)
            if isinstance(data, bytes):
                data = data.decode('utf-8', errors='replace')
            return data.strip(), 'done'
        except Exception as e:
            logger.warning(f"Αποτυχία ανάγνωσης '{filename}': {e}")
            return '', 'failed'

    # doc/xls/zip κλπ — εκτός εμβέλειας αυτής της φάσης
    return '', 'skipped'


def _ocr_enabled():
    return bool(getattr(dj_settings, 'DOCUMENT_OCR_ENABLED', False)) and shutil.which('tesseract')


def _try_tesseract_pdf(fileobj):
    """OCR σε σκαναρισμένο PDF — απαιτεί tesseract + pdf2image/poppler. Best effort."""
    if not _ocr_enabled():
        return None
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
        fileobj.seek(0)
        pages = convert_from_bytes(fileobj.read(), first_page=1, last_page=5)
        return '\n'.join(
            pytesseract.image_to_string(page, lang='ell+eng') for page in pages
        ).strip()
    except Exception as e:
        logger.info(f"OCR PDF μη διαθέσιμο/απέτυχε: {e}")
        return None


def _try_tesseract_image(fileobj):
    """OCR σε εικόνα. Επιστρέφει None αν το OCR δεν είναι διαθέσιμο."""
    if not _ocr_enabled():
        return None
    try:
        import pytesseract
        from PIL import Image
        fileobj.seek(0)
        return pytesseract.image_to_string(Image.open(fileobj), lang='ell+eng').strip()
    except Exception as e:
        logger.info(f"OCR εικόνας απέτυχε: {e}")
        return None


def _normalize(text):
    """Κεφαλαία χωρίς τόνους — για accent-insensitive matching ελληνικών."""
    import unicodedata
    decomposed = unicodedata.normalize('NFD', text or '')
    return ''.join(c for c in decomposed if not unicodedata.combining(c)).upper()


def suggest_category(text, filename=''):
    """
    Προτείνει κατηγορία ClientDocument από το περιεχόμενο (+ όνομα αρχείου).
    Accent-insensitive (π.χ. «τιμολόγιο» ↔ ΤΙΜΟΛΟΓΙΟ). Returns: code ή None.
    """
    haystack = _normalize(f"{filename}\n{text or ''}")
    for category, keywords in CATEGORY_KEYWORDS:
        for keyword in keywords:
            if _normalize(keyword) in haystack:
                return category
    return None


def process_document(document):
    """
    Εξάγει κείμενο για ένα ClientDocument και ενημερώνει
    extracted_text / ocr_status / ocr_processed_at / afm_mismatch.

    Δεν σηκώνει exceptions — ποτέ δεν πρέπει να σπάσει ένα upload.
    Returns: το status ('done'/'failed'/'skipped').
    """
    try:
        with document.file.open('rb') as f:
            text, status = extract_text_from_file(f, document.filename)
    except Exception as e:
        logger.warning(f"Αποτυχία εξαγωγής για έγγραφο {document.pk}: {e}")
        text, status = '', 'failed'

    mismatch = False
    if text and document.client_id:
        client_afm = document.client.afm or ''
        candidates = find_afm_candidates(text)
        # Mismatch μόνο αν βρέθηκαν έγκυρα ΑΦΜ και το ΑΦΜ του πελάτη δεν
        # εμφανίζεται πουθενά στο κείμενο (ούτε ως σκέτο string — κάποια
        # πραγματικά ΑΦΜ αποτυγχάνουν στο checksum)
        if candidates and client_afm not in candidates and client_afm not in text:
            mismatch = True

    document.extracted_text = text
    document.ocr_status = status
    document.ocr_processed_at = timezone.now()
    document.afm_mismatch = mismatch
    document.save(update_fields=[
        'extracted_text', 'ocr_status', 'ocr_processed_at', 'afm_mismatch'
    ])
    return status


def queue_extraction(document):
    """
    Δρομολογεί την εξαγωγή κειμένου μετά το commit.

    Σε DEBUG (ή DOCUMENT_OCR_SYNC=True) τρέχει συγχρονισμένα ώστε να
    δουλεύει και χωρίς Celery worker· αλλιώς μέσω Celery με fallback.
    """
    from django.db import transaction

    def _dispatch():
        sync = getattr(dj_settings, 'DOCUMENT_OCR_SYNC', dj_settings.DEBUG)
        if not sync:
            try:
                from accounting.tasks import extract_document_text
                extract_document_text.delay(document.pk)
                return
            except Exception as e:
                logger.info(f"Celery μη διαθέσιμο, sync εξαγωγή: {e}")
        try:
            process_document(document)
        except Exception as e:
            logger.warning(f"Sync εξαγωγή απέτυχε για {document.pk}: {e}")

    transaction.on_commit(_dispatch)
