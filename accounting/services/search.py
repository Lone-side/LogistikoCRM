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
from django.db.models import Q


def apply_document_search(queryset, term, include_client_fields=True):
    """
    Φιλτράρει queryset από ClientDocument με όρο αναζήτησης σε
    filename/original_filename/description/extracted_text
    (+ client eponimia/afm όταν include_client_fields=True).
    """
    if not term:
        return queryset

    filters = (
        Q(filename__icontains=term)
        | Q(original_filename__icontains=term)
        | Q(description__icontains=term)
        | Q(extracted_text__icontains=term)
    )
    if include_client_fields:
        filters |= Q(client__eponimia__icontains=term) | Q(client__afm__icontains=term)

    if connection.vendor == 'postgresql':
        from django.contrib.postgres.search import SearchQuery, SearchVector

        queryset = queryset.annotate(
            content_search=SearchVector('extracted_text', config='greek')
        )
        filters |= Q(content_search=SearchQuery(term, config='greek'))

    return queryset.filter(filters)
