# Backfill των snapshot πεδίων του VoIPCallLog από τις υπάρχουσες κλήσεις.
#
# Logs των οποίων η κλήση έχει ήδη διαγραφεί (call=None από το 10024)
# δεν μπορούν να αποκτήσουν snapshot — μένουν legacy orphans και το
# admin scoping τα δείχνει fail-closed μόνο σε see-all χρήστες.

from django.db import migrations
from django.db.models import F

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


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '10025_voipcalllog_snapshot_fields'),
    ]

    operations = [
        migrations.RunPython(_backfill, migrations.RunPython.noop),
    ]
