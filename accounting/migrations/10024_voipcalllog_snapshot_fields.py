# Βήμα 1/3 — VoIPCallLog audit trail retention (ασφαλής σειρά):
# προσθήκη nullable snapshot πεδίων. Το FK `call` παραμένει CASCADE σε
# αυτό το βήμα — δεν υπάρχει ενδιάμεσο schema όπου η διαγραφή μιας κλήσης
# αφήνει log χωρίς call ΚΑΙ χωρίς snapshot.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "10023_repair_legacy_slot_chains"),
    ]

    operations = [
        migrations.AddField(
            model_name="voipcalllog",
            name="call_reference",
            field=models.CharField(
                blank=True, default="", max_length=100,
                verbose_name="Αναφορά Κλήσης (snapshot)"),
        ),
        migrations.AddField(
            model_name="voipcalllog",
            name="client",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="voip_call_logs",
                to="accounting.clientprofile",
                verbose_name="Πελάτης (snapshot)",
            ),
        ),
        migrations.AddField(
            model_name="voipcalllog",
            name="phone_number",
            field=models.CharField(
                blank=True, default="", max_length=30,
                verbose_name="Τηλέφωνο (snapshot)"),
        ),
    ]
