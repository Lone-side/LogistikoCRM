# -*- coding: utf-8 -*-
"""
Regression test: εξαγωγή ΕΛΛΗΝΙΚΟΥ κειμένου από PDF.

Ιστορικό — γιατί υπάρχει αυτό το αρχείο:

Το `pypdf` 6.15.0 εξάγει το ελληνικό κεφαλαίο «Δ» (U+0394 GREEK CAPITAL
LETTER DELTA) ως «∆» (U+2206 INCREMENT — μαθηματικό σύμβολο). Οπτικά είναι
σχεδόν ίδια, αλλά είναι διαφορετικοί χαρακτήρες, οπότε κάθε αναζήτηση σε
έγγραφο που περιέχει Δ γυρίζει **κενή**. Στα ελληνικά λογιστικά αυτό αγγίζει
τα πάντα: ΔΗΛΩΣΗ, ΔΟΥ, ΑΔΕΙΑ, ΠΑΡΑΔΟΣΗ, ΔΑΠΑΝΕΣ.

Το bug μπήκε αθόρυβα, χωρίς καμία αλλαγή κώδικα: τα requirements είχαν
`pypdf>=4.0`, το CI εγκατέστησε 6.15.0 μόλις κυκλοφόρησε και η σουίτα
κοκκίνισε. Γι' αυτό οι εκδόσεις είναι πλέον καρφωμένες.

Το test ελέγχει τη **συμπεριφορά**, όχι τον αριθμό έκδοσης — αν κάποια
μελλοντική έκδοση διορθώσει το πρόβλημα, το ξεκάρφωμα θα περάσει καθαρά.
"""
import io
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from accounting.services.text_extraction import MAX_TEXT_CHARS, extract_text_from_file

# Το «Δ» εμφανίζεται δύο φορές — μία σε κάθε λέξη-κλειδί
GREEK_SAMPLE = 'ΜΟΝΑΔΙΚΗΛΕΞΗ ΞΕΝΟΔΟΧΕΙΟ ΑΚΡΟΠΟΛΙΣ'
INCREMENT = '∆'   # ∆ — ΛΑΘΟΣ
DELTA = 'Δ'       # Δ — ΣΩΣΤΟ


def make_pdf(text):
    """PDF bytes με το δοσμένο κείμενο (ίδια διαδρομή με τα υπόλοιπα tests)."""
    from xhtml2pdf import pisa
    buf = io.BytesIO()
    pisa.CreatePDF(f"<html><body><p>{text}</p></body></html>", dest=buf)
    return buf.getvalue()


class GreekPdfExtractionTest(SimpleTestCase):
    """Δεν χρειάζεται βάση — ελέγχει καθαρά την εξαγωγή κειμένου."""

    def _extract(self):
        pdf = make_pdf(GREEK_SAMPLE)
        text, status = extract_text_from_file(io.BytesIO(pdf), 'greek.pdf')
        self.assertEqual(status, 'done', f'Η εξαγωγή δεν ολοκληρώθηκε: {status}')
        return text

    def _pypdf_version(self):
        import pypdf
        return getattr(pypdf, '__version__', 'άγνωστη')

    def test_greek_text_extracted_intact(self):
        """Ολόκληρη η ελληνική φράση πρέπει να επιβιώνει της εξαγωγής."""
        text = self._extract()
        self.assertIn(
            GREEK_SAMPLE, text,
            f'Το ελληνικό κείμενο αλλοιώθηκε κατά την εξαγωγή.\n'
            f'  αναμενόταν: {GREEK_SAMPLE!r}\n'
            f'  βρέθηκε   : {text!r}\n'
            f'  pypdf     : {self._pypdf_version()}'
        )

    def test_delta_not_mangled_into_increment(self):
        """
        Ο συγκεκριμένος τρόπος αποτυχίας: Δ (U+0394) → ∆ (U+2206).
        Ξεχωριστό test ώστε η αιτία να φαίνεται αμέσως στο CI.
        """
        text = self._extract()
        self.assertNotIn(
            INCREMENT, text,
            f'Το «Δ» εξήχθη ως «∆» (U+2206 INCREMENT) αντί για U+0394. '
            f'Γνωστό regression του pypdf 6.15.0 — έλεγξε το pin στο '
            f'requirements.txt. Εγκατεστημένη pypdf: {self._pypdf_version()}\n'
            f'  βρέθηκε: {text!r}'
        )
        self.assertIn(
            DELTA, text,
            f'Λείπει τελείως το ελληνικό «Δ» (U+0394) από το εξαγόμενο '
            f'κείμενο. pypdf: {self._pypdf_version()}\n  βρέθηκε: {text!r}'
        )

    def test_delta_variants_normalize_at_pdf_extraction_boundary(self):
        """Both parser variants are stored as searchable Greek capital delta."""
        for parser_text in (f'{DELTA}ΗΛΩΣΗ', f'{INCREMENT}ΗΛΩΣΗ'):
            with self.subTest(parser_text=parser_text), patch(
                'pypdf.PdfReader'
            ) as reader:
                page = MagicMock()
                page.extract_text.return_value = parser_text
                reader.return_value.pages = [page]

                text, status = extract_text_from_file(
                    io.BytesIO(b'%PDF-1.4'), 'greek.pdf'
                )

                self.assertEqual(status, 'done')
                self.assertEqual(text, f'{DELTA}ΗΛΩΣΗ')
                self.assertNotIn(INCREMENT, text)

    def test_legitimate_mathematical_increment_is_preserved(self):
        with patch('pypdf.PdfReader') as reader:
            page = MagicMock()
            page.extract_text.return_value = f'{INCREMENT}ΗΛΩΣΗ | 5 {INCREMENT} 3 | {INCREMENT}x'
            reader.return_value.pages = [page]

            text, status = extract_text_from_file(
                io.BytesIO(b'%PDF-1.4'), 'mixed-content.pdf'
            )

        self.assertEqual(status, 'done')
        self.assertEqual(text, f'{DELTA}ΗΛΩΣΗ | 5 {INCREMENT} 3 | {INCREMENT}x')

    def test_page_is_bounded_before_normalization_allocation(self):
        with patch('pypdf.PdfReader') as reader, patch(
            'accounting.services.text_extraction._normalize_pdf_text',
            side_effect=lambda text: text,
        ) as normalize:
            page = MagicMock()
            page.extract_text.return_value = 'Α' * (MAX_TEXT_CHARS * 2)
            reader.return_value.pages = [page]

            text, status = extract_text_from_file(
                io.BytesIO(b'%PDF-1.4'), 'oversized-page.pdf'
            )

        self.assertEqual(status, 'done')
        self.assertEqual(len(text), MAX_TEXT_CHARS)
        self.assertEqual(len(normalize.call_args.args[0]), MAX_TEXT_CHARS)

    def test_no_unexpected_non_greek_symbols(self):
        """
        Ευρύτερο δίχτυ: κανένας χαρακτήρας από τα μαθηματικά/τεχνικά μπλοκ
        Unicode δεν έχει θέση σε ελληνικό κείμενο. Πιάνει και αντίστοιχες
        αλλοιώσεις άλλων γραμμάτων σε μελλοντικές εκδόσεις.
        """
        text = self._extract()
        suspicious = sorted({
            c for c in text
            if 0x2000 <= ord(c) <= 0x2BFF and not c.isspace()
        })
        self.assertEqual(
            suspicious, [],
            f'Βρέθηκαν μη-ελληνικά σύμβολα στο εξαγόμενο κείμενο: '
            f'{[(c, hex(ord(c))) for c in suspicious]}. '
            f'pypdf: {self._pypdf_version()}\n  βρέθηκε: {text!r}'
        )
