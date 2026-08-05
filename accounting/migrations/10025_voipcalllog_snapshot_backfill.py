# Βήμα 2/3 — Backfill των snapshot πεδίων ΠΡΙΝ αλλάξει το FK σε SET_NULL.
#
# Σε αυτό το σημείο το `call` είναι ακόμη CASCADE non-null, οπότε ΚΑΘΕ
# υπάρχον log έχει κλήση: όλα αποκτούν snapshot. Ακολουθεί validation ότι
# κανένα log με κλήση δεν έμεινε χωρίς `call_reference` snapshot — μόνο
# μετά επιτρέπεται (στο 10026) η αποδυνάμωση του FK.

from django.db import migrations

_CHUNK = 1000


def _backfill(apps, schema_editor):
    VoIPCallLog = apps.get_model('accounting', 'VoIPCallLog')

    qs = (VoIPCallLog.objects
          .filter(call__isnull=False)
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
    # Κάθε log με κλήση πρέπει πλέον να έχει call_reference snapshot.
    # Αν όχι, σταματάμε ΠΡΙΝ αλλάξει το FK — δεν υπάρχει επικίνδυνο window.
    missing = VoIPCallLog.objects.filter(
        call__isnull=False, call_reference='').count()
    if missing:
        raise RuntimeError(
            f'VoIPCallLog snapshot backfill incomplete: {missing} rows με '
            'κλήση αλλά χωρίς call_reference — abort πριν το SET_NULL.')


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '10024_voipcalllog_snapshot_fields'),
    ]

    operations = [
        migrations.RunPython(_backfill, migrations.RunPython.noop),
        migrations.RunPython(_validate, migrations.RunPython.noop),
    ]
