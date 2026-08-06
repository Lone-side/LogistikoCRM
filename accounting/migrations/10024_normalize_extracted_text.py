# -*- coding: utf-8 -*-
"""
Backfill: κανονικοποίηση του υπάρχοντος ClientDocument.extracted_text.

Το πεδίο είναι αποκλειστικά search index (δεν εκτίθεται σε UI/API).
Από εδώ και πέρα γράφεται κανονικοποιημένο από το text_extraction·
αυτή η migration φέρνει τα ήδη αποθηκευμένα έγγραφα στην ίδια μορφή,
ώστε η αναζήτηση «ΔΟΚΙΜΩΝ» να βρίσκει και το «∆ΟΚΙΜΩΝ» των παλιών PDF.

Μη αντιστρέψιμη ως προς τα δεδομένα (η αρχική μορφή δεν φυλάσσεται),
αλλά πλήρως ανακτήσιμη με `manage.py extract_document_text` από τα αρχεία.
"""
from django.db import migrations

BATCH = 500


def normalize_existing(apps, schema_editor):
    from accounting.services.text_normalization import normalize_search_text

    ClientDocument = apps.get_model('accounting', 'ClientDocument')
    qs = ClientDocument.objects.exclude(extracted_text='').exclude(
        extracted_text__isnull=True
    ).only('id', 'extracted_text')

    batch = []
    for doc in qs.iterator(chunk_size=BATCH):
        normalized = normalize_search_text(doc.extracted_text)
        if normalized == doc.extracted_text:
            continue
        doc.extracted_text = normalized
        batch.append(doc)
        if len(batch) >= BATCH:
            ClientDocument.objects.bulk_update(batch, ['extracted_text'])
            batch = []
    if batch:
        ClientDocument.objects.bulk_update(batch, ['extracted_text'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '10023_repair_legacy_slot_chains'),
    ]

    operations = [
        migrations.RunPython(normalize_existing, migrations.RunPython.noop),
    ]
