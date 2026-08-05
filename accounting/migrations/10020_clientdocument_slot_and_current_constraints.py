# -*- coding: utf-8 -*-
"""
Γύρος 19 — DB-level enforcement του «ένα current ανά exact logical key».

1. Νέο πεδίο `slot` (μέρος του exact key): '' για τα «κύρια» έγγραφα του
   γραφείου, μοναδικό hex για portal uploads (on_existing='keep') ώστε τα
   πολλαπλά ανεξάρτητα έγγραφα πελάτη να μην παραβιάζουν το invariant.
2. Data migration: υπάρχοντα rows που παραβιάζουν το invariant (πολλαπλά
   current στο ίδιο key — ιστορικά δεδομένα ή portal uploads της παλιάς
   'keep' σημασιολογίας) παίρνουν ΝΤΕΤΕΡΜΙΝΙΣΤΙΚΑ μοναδικό slot ώστε να
   παραμείνουν ΟΛΑ προσβάσιμα/current χωρίς να χαθεί κανένα έγγραφο —
   ΔΕΝ γίνεται demote/διαγραφή δεδομένων.
3. Δύο partial UniqueConstraints (nullable obligation → NULL != NULL στην
   PostgreSQL, γι' αυτό ξεχωριστό constraint με obligation__isnull=True).
"""
from django.db import migrations, models


def assign_slots_to_duplicates(apps, schema_editor):
    ClientDocument = apps.get_model('accounting', 'ClientDocument')
    from collections import defaultdict
    groups = defaultdict(list)
    for row in ClientDocument.objects.filter(is_current=True).values(
            'id', 'client_id', 'document_category', 'year', 'month',
            'obligation_id').order_by('id'):
        key = (row['client_id'], row['document_category'], row['year'],
               row['month'], row['obligation_id'])
        groups[key].append(row['id'])
    for key, ids in groups.items():
        if len(ids) <= 1:
            continue
        # Ντετερμινιστικά: το ΠΑΛΑΙΟΤΕΡΟ (μικρότερο id) κρατά το κύριο
        # slot ''· τα υπόλοιπα παίρνουν μοναδικό slot ανά id
        for doc_id in ids[1:]:
            ClientDocument.objects.filter(pk=doc_id).update(
                slot=f'legacy-{doc_id}')


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '10019_export_clientprofile_permission'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientdocument',
            name='slot',
            field=models.CharField(
                blank=True, default='',
                help_text='Λογική θέση εγγράφου — μέρος του exact conflict key',
                max_length=64, verbose_name='Slot'),
        ),
        migrations.RunPython(
            assign_slots_to_duplicates, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='clientdocument',
            constraint=models.UniqueConstraint(
                condition=models.Q(is_current=True, obligation__isnull=True),
                fields=['client', 'document_category', 'year', 'month',
                        'slot'],
                name='uniq_current_doc_no_obligation'),
        ),
        migrations.AddConstraint(
            model_name='clientdocument',
            constraint=models.UniqueConstraint(
                condition=models.Q(is_current=True, obligation__isnull=False),
                fields=['client', 'document_category', 'year', 'month',
                        'obligation', 'slot'],
                name='uniq_current_doc_with_obligation'),
        ),
    ]
