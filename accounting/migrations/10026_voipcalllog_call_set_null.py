# Βήμα 3/3 — ΜΟΝΟ μετά το backfill+validation αλλάζει το FK `call` από
# CASCADE σε SET_NULL. Πλέον η διαγραφή μιας κλήσης διατηρεί το log
# (audit trail) και τα snapshots (client/call_reference/phone_number)
# υπάρχουν ήδη, οπότε δεν χάνεται ποτέ η προέλευση/ο πελάτης.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "10025_voipcalllog_snapshot_backfill"),
    ]

    operations = [
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
