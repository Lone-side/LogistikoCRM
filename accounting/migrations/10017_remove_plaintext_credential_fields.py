# Αφαίρεση των plaintext credential πεδίων από το ClientProfile.
# Τα δεδομένα έχουν ήδη μεταφερθεί στο ClientCredential (migration 10016).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "10016_migrate_plaintext_credentials"),
    ]

    operations = [
        migrations.RemoveField(model_name="clientprofile", name="kodikos_gemi"),
        migrations.RemoveField(model_name="clientprofile", name="kodikos_ika_ergodoti"),
        migrations.RemoveField(model_name="clientprofile", name="kodikos_taxisnet"),
        migrations.RemoveField(model_name="clientprofile", name="onoma_xristi_gemi"),
        migrations.RemoveField(model_name="clientprofile", name="onoma_xristi_ika_ergodoti"),
        migrations.RemoveField(model_name="clientprofile", name="onoma_xristi_taxisnet"),
    ]
