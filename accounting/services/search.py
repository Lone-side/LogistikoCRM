# -*- coding: utf-8 -*-
"""
accounting/services/search.py

Ενιαία αναζήτηση εγγράφων (ClientDocument) με προαιρετικό PostgreSQL
full-text search στο περιεχόμενο.

- Σε PostgreSQL: επιπλέον SearchVector/SearchQuery (config 'greek') στο
  extracted_text — γρήγορα stemmed whole-word matches με GIN index
  (migration 10012). Τα icontains ΔΙΑΤΗΡΟΥΝΤΑΙ στο OR: το greek config
  δεν αφαιρεί τόνους, οπότε το FTS είναι πρόσθετο, όχι αντικατάσταση.
- Σε SQLite (development): ακριβώς η κλασική icontains συμπεριφορά.
"""
from django.db import connection
from django.db.models import F, Q, TextField, Value
from django.db.models.functions import Coalesce, Replace

# Το pypdf 6.15.0 (βλ. requirements.txt) εξήγαγε το ελληνικό κεφαλαίο Δ ως
# ∆ (U+2206 INCREMENT). Η έκδοση είναι πλέον καρφωμένη, αλλά **τα ήδη
# αποθηκευμένα extracted_text δεν ξαναγράφονται**: ό,τι επεξεργάστηκε η
# χαλασμένη έκδοση κουβαλά U+2206 για πάντα. Χωρίς κανονικοποίηση, τα
# ΔΗΛΩΣΗ / ΔΟΥ / ΑΔΕΙΑ γίνονται μη ευρέσιμα σε εκείνα τα έγγραφα.
#
# Αυτό είναι το μοναδικό ζεύγος με fail-before απόδειξη σε πραγματικά
# εξαγόμενο κείμενο. Σκόπιμα ΔΕΝ προστίθενται άλλα «παρόμοια» (∑→Σ, ∏→Π,
# µ→μ): είναι κανονικά μαθηματικά σύμβολα με δική τους σημασία, η
# μετατροπή τους θα παρήγαγε ψευδή αποτελέσματα αναζήτησης, και κάθε
# ζεύγος κοστίζει ένα ακόμη SQL REPLACE πάνω στη στήλη. Νέο ζεύγος μόνο
# με fail-before απόδειξη.
_BROKEN_DELTA = '∆'  # U+2206
_GREEK_DELTA = 'Δ'   # U+0394


def _to_greek(text):
    """Κανονικοποίηση του αλλοιωμένου ∆ (U+2206) προς το ελληνικό Δ."""
    return (text or '').replace(_BROKEN_DELTA, _GREEK_DELTA)


def _normalized_field(field_name):
    """
    Έκφραση SQL που κανονικοποιεί ένα text πεδίο προς τα ελληνικά.

    Η αλλοίωση είναι **ανά χαρακτήρα**: το «∆ΗΛΩΣΗ» έχει χαλασμένο μόνο το
    Δ, με το Σ σωστό. Γι' αυτό δεν αρκεί να μεταφράσουμε τον όρο — μια
    «όλα σύμβολα» εκδοχή θα έψαχνε «∆ΗΛΩ∑Η» και δεν θα έβρισκε τίποτα.
    Κανονικοποιούμε και τις δύο πλευρές προς τα ελληνικά.
    """
    # Ρητό output_field: το Value('') είναι CharField ενώ το extracted_text
    # TextField, και ο Coalesce αρνείται να μαντέψει.
    text = TextField()
    return Replace(
        Coalesce(F(field_name), Value(''), output_field=text),
        Value(_BROKEN_DELTA),
        Value(_GREEK_DELTA),
        output_field=text,
    )


def apply_document_search(queryset, term, include_client_fields=True):
    """
    Φιλτράρει queryset από ClientDocument με όρο αναζήτησης σε
    filename/original_filename/description/extracted_text
    (+ client eponimia/afm όταν include_client_fields=True).
    """
    if not term:
        return queryset

    greek_term = _to_greek(term)

    # Το extracted_text έρχεται από PDF/OCR — εκεί ζει η αλλοίωση, οπότε
    # συγκρίνεται κανονικοποιημένο. Τα υπόλοιπα πεδία τα γράφουν άνθρωποι.
    queryset = queryset.annotate(
        normalized_extracted_text=_normalized_field('extracted_text'),
    )

    filters = (
        Q(filename__icontains=term)
        | Q(original_filename__icontains=term)
        | Q(description__icontains=term)
        | Q(normalized_extracted_text__icontains=greek_term)
    )
    if greek_term != term:
        # Ο χρήστης επικόλλησε ∆: να βρίσκει και ό,τι έχει γραφτεί σωστά.
        filters |= (
            Q(filename__icontains=greek_term)
            | Q(original_filename__icontains=greek_term)
            | Q(description__icontains=greek_term)
        )
    if include_client_fields:
        filters |= Q(client__eponimia__icontains=term) | Q(client__afm__icontains=term)

    if connection.vendor == 'postgresql':
        from django.contrib.postgres.search import SearchQuery, SearchVector

        queryset = queryset.annotate(
            content_search=SearchVector(
                _normalized_field('extracted_text'), config='greek')
        )
        filters |= Q(content_search=SearchQuery(greek_term, config='greek'))

    return queryset.filter(filters)
