# -*- coding: utf-8 -*-
"""
GIN full-text index στο ClientDocument.extracted_text (μόνο PostgreSQL).

Η έκφραση ταιριάζει με το SQL που παράγει το
SearchVector('extracted_text', config='greek') — βλ.
accounting/services/search.py — ώστε το φίλτρο αναζήτησης να
χρησιμοποιεί τον index. Σε SQLite (development) το migration είναι no-op.
"""
from django.db import migrations

INDEX_NAME = 'accounting_clientdoc_fts_idx'

CREATE_SQL = f"""
CREATE INDEX IF NOT EXISTS {INDEX_NAME}
ON accounting_clientdocument
USING GIN (to_tsvector('greek', COALESCE(extracted_text, '')))
"""

DROP_SQL = f"DROP INDEX IF EXISTS {INDEX_NAME}"


def create_index(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute(CREATE_SQL)


def drop_index(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute(DROP_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '10011_sharedlink_allow_upload_sharedlink_max_uploads_and_more'),
    ]

    operations = [
        migrations.RunPython(create_index, drop_index),
    ]
