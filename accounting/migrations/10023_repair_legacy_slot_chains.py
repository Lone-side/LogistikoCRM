# -*- coding: utf-8 -*-
"""
Γύρος 22 — repair pass για βάσεις όπου το 10021 έχει ΗΔΗ εφαρμοστεί.

Γιατί χρειάζεται:
Το `10021_fix_legacy_slot_chains` διορθώθηκε (component με >1 current row
δεν αγγίζεται πλέον — αλλιώς παραβίαζε το `uniq_current_doc_*` και
τερμάτιζε το `migrate` με IntegrityError). Επειδή όμως το 10021 είναι
`RunPython`, μια βάση που το έχει ΗΔΗ μαρκάρει ως applied **δεν θα
ξανατρέξει** τη διορθωμένη λογική. Αυτό το migration εκτελεί την
**ίδια, διορθωμένη** συνάρτηση ακόμη μία φορά, ώστε:

- βάσεις που πρόλαβαν το παλιό (buggy) 10021 να περάσουν από τη
  διορθωμένη λογική,
- βάσεις που το τρέχουν πρώτη φορά (10021 ήδη διορθωμένο) να μην
  αλλάξουν τίποτα — η συνάρτηση είναι **idempotent**,
- βάσεις όπου το παλιό 10021 απέτυχε στη μέση να είναι ήδη σε συνεπή
  κατάσταση (το migrate τρέχει σε transaction → πλήρες rollback) και
  εδώ απλώς να επιβεβαιώνεται.

Καμία διαγραφή, κανένα demote, καμία επιλογή «σωστού» branch: τα
αμφίβολα components παραμένουν ως έχουν και αναφέρονται από το
`audit_clientdocument_invariants` ως `legacy-branching-chain-needs-review`.

ΣΗΜΕΙΩΣΗ: δεν αντικαθιστά backup. Βλ. DEPLOYMENT.md για το runbook.
"""
from django.db import migrations


def _repair(apps, schema_editor):
    """Εκτελεί τη ΔΙΟΡΘΩΜΕΝΗ λογική του 10021 (idempotent)."""
    import importlib
    mod = importlib.import_module(
        'accounting.migrations.10021_fix_legacy_slot_chains')
    mod._fix_legacy_chains(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '10022_sharedlink_target_invariant'),
    ]

    operations = [
        migrations.RunPython(_repair, migrations.RunPython.noop),
    ]
