# Βήμα 3/3 — τελικό catch-up backfill + validation ΚΑΙ ΜΕΤΑ CASCADE→SET_NULL,
# μέσα στην ΙΔΙΑ atomic migration (PostgreSQL transactional DDL).
#
# Deployment safety — όρια προστασίας:
#   * Το catch-up εδώ πιάνει logs που δημιουργήθηκαν από παλιό application
#     code ΜΕΤΑ το backfill του 10025 και ΠΡΙΝ αυτή τη migration (window
#     μεταξύ των δύο migrations).
#   * Το validation αποτυγχάνει (rollback ΟΛΗΣ της migration) αν μείνει
#     οποιοδήποτε log-με-κλήση χωρίς call_reference snapshot.
#   * ΔΕΝ εγγυάται zero-downtime αν παλιό code/worker γράφει ΤΑΥΤΟΧΡΟΝΑ:
#     ένα INSERT ανάμεσα στο catch-up και το ACCESS EXCLUSIVE lock του
#     AlterField μπορεί να αφήσει snapshot-less log. Γι' αυτό υπάρχει το
#     post-migration audit command `audit_voipcalllog_snapshots`
#     (fail-closed) + re-backfill· βλ. DEPLOYMENT runbook. Για πλήρη
#     ασφάλεια απαιτείται maintenance window (πάγωμα web/Celery/VoIP
#     writers) γύρω από αυτή τη migration.

import django.db.models.deletion
from django.db import migrations, models

_CHUNK = 1000


def _catch_up_backfill(apps, schema_editor):
    VoIPCallLog = apps.get_model('accounting', 'VoIPCallLog')
    qs = (VoIPCallLog.objects
          .filter(call__isnull=False, call_reference='')
          .select_related('call')
          .only('id', 'client_id', 'call_reference', 'phone_number',
                'call__client_id', 'call__call_id', 'call__phone_number'))
    batch = []
    for log in qs.iterator(chunk_size=_CHUNK):
        log.client_id = log.call.client_id
        log.call_reference = str(log.call.call_id or log.call_id)
        log.phone_number = log.call.phone_number or ''
        batch.append(log)
        if len(batch) >= _CHUNK:
            VoIPCallLog.objects.bulk_update(
                batch, ['client_id', 'call_reference', 'phone_number'])
            batch = []
    if batch:
        VoIPCallLog.objects.bulk_update(
            batch, ['client_id', 'call_reference', 'phone_number'])


def _validate(apps, schema_editor):
    VoIPCallLog = apps.get_model('accounting', 'VoIPCallLog')
    missing = VoIPCallLog.objects.filter(
        call__isnull=False, call_reference='').count()
    if missing:
        raise RuntimeError(
            f'VoIPCallLog snapshot incomplete: {missing} rows με κλήση αλλά '
            'χωρίς call_reference — abort πριν το SET_NULL (rollback).')


def _flush_deferred_constraints(apps, schema_editor):
    """
    Εύρημα του migration rehearsal σε PostgreSQL 14 με πραγματικά window
    rows: το catch-up backfill ενημερώνει FK στήλη (client_id) της οποίας
    το constraint είναι DEFERRABLE INITIALLY DEFERRED, οπότε μένουν
    pending constraint triggers μέχρι το COMMIT. Το AlterField (DDL) στο
    ΙΔΙΟ transaction αποτυγχάνει τότε με:

        cannot ALTER TABLE "accounting_voipcalllog"
        because it has pending trigger events

    Σε άδεια βάση το catch-up δεν αγγίζει τίποτα και το πρόβλημα δεν
    εμφανίζεται — γι' αυτό το CI (φρέσκια βάση) περνούσε. Το SET
    CONSTRAINTS ALL IMMEDIATE εκτελεί τους εκκρεμείς ελέγχους ΕΔΩ (μια
    παραβίαση FK κάνει rollback όλη τη migration, όπως πρέπει) ώστε το
    AlterField να τρέξει καθαρά, πάντα μέσα στην ίδια atomic transaction.
    """
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('SET CONSTRAINTS ALL IMMEDIATE')


class Migration(migrations.Migration):

    # Ρητά atomic: το catch-up + validation + AlterField πρέπει να είναι
    # μία transaction ώστε αποτυχία validation να κάνει rollback τα πάντα.
    atomic = True

    dependencies = [
        ("accounting", "10025_voipcalllog_snapshot_backfill"),
    ]

    operations = [
        migrations.RunPython(_catch_up_backfill, migrations.RunPython.noop),
        migrations.RunPython(_validate, migrations.RunPython.noop),
        migrations.RunPython(
            _flush_deferred_constraints, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="voipcalllog",
            name="call",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="logs",
                to="accounting.voipcall",
                verbose_name="Κλήση",
            ),
        ),
    ]
