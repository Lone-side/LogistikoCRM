# -*- coding: utf-8 -*-
"""
Γύρος 22 — κεντρικό invariant στόχου για τα SharedLink.

Πρόβλημα: ένα link μπορούσε να έχει ΚΑΙ document ΚΑΙ client, ή κανέναν
στόχο. Το public περιεχόμενο διαβάζει το `document`, ενώ το
`upload_target_client` προτιμά το `client` — άρα ένα link μπορούσε να
εμφανίζει έγγραφο του πελάτη Α και να αποθηκεύει uploads στον πελάτη Β.

Πολιτική καθαρισμού legacy δεδομένων (deterministic, χωρίς διαγραφές):

1. Link με ΚΑΙ document ΚΑΙ client:
   canonical θεωρείται το **document** (αυτό βλέπει ο παραλήπτης του
   συνδέσμου· το document ορίζει και τον πελάτη μέσω document.client).
   Το redundant `client` καθαρίζεται ΜΟΝΟ όταν είναι ο ίδιος πελάτης με
   το `document.client` ή όταν το link είναι ενεργό — σε κάθε περίπτωση
   δεν χάνεται δεδομένο: το document παραμένει.
   ΕΞΑΙΡΕΣΗ: αν ο client διαφέρει από τον document.client, το link είναι
   αμφίβολο (mismatch) → **απενεργοποιείται** και κρατά και τα δύο πεδία
   για χειροκίνητη εξέταση (το constraint επιτρέπει ό,τι είναι ανενεργό).

2. ΕΝΕΡΓΟ link χωρίς κανέναν στόχο (orphan):
   **απενεργοποιείται** (is_active=False). ΔΕΝ διαγράφεται — το row
   παραμένει για audit/ιστορικό.

Καμία σιωπηλή διαγραφή. Τα logs κρατούν ΜΟΝΟ internal IDs.
"""
import logging

from django.db import migrations, models

logger = logging.getLogger(__name__)


def _normalize_targets(apps, schema_editor):
    SharedLink = apps.get_model('accounting', 'SharedLink')

    # 1. Διπλός στόχος
    both = SharedLink.objects.filter(
        document__isnull=False, client__isnull=False)
    mismatched, cleaned = [], []
    for link in both.only('id', 'document_id', 'client_id', 'is_active'):
        doc_client_id = SharedLink.objects.filter(pk=link.id).values_list(
            'document__client_id', flat=True).first()
        if doc_client_id == link.client_id:
            # Redundant αλλά συνεπές → κρατάμε το document ως canonical
            SharedLink.objects.filter(pk=link.id).update(client=None)
            cleaned.append(link.id)
        else:
            # Ασυνέπεια πελάτη → fail closed: απενεργοποίηση, χωρίς
            # διαγραφή και χωρίς αυθαίρετη επιλογή στόχου
            SharedLink.objects.filter(pk=link.id).update(is_active=False)
            mismatched.append(link.id)

    # 2. Ενεργά orphan links (κανένας στόχος)
    orphan_ids = list(SharedLink.objects.filter(
        document__isnull=True, client__isnull=True, is_active=True
    ).values_list('id', flat=True))
    if orphan_ids:
        SharedLink.objects.filter(id__in=orphan_ids).update(is_active=False)

    # Μόνο internal IDs στα logs — ποτέ token/ΑΦΜ/filename
    if cleaned:
        logger.info('SharedLink: καθαρίστηκε redundant client σε ids=%s',
                    sorted(cleaned))
    if mismatched:
        logger.warning(
            'SharedLink: απενεργοποιήθηκαν λόγω ασυνέπειας στόχου ids=%s '
            '(απαιτείται χειροκίνητος έλεγχος)', sorted(mismatched))
    if orphan_ids:
        logger.warning(
            'SharedLink: απενεργοποιήθηκαν orphan links ids=%s',
            sorted(orphan_ids))


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '10021_fix_legacy_slot_chains'),
    ]

    operations = [
        migrations.RunPython(_normalize_targets, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='sharedlink',
            constraint=models.CheckConstraint(
                check=(
                    models.Q(is_active=False)
                    | models.Q(document__isnull=False, client__isnull=True)
                    | models.Q(document__isnull=True, client__isnull=False)
                ),
                name='sharedlink_active_exactly_one_target',
            ),
        ),
    ]
