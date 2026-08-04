# -*- coding: utf-8 -*-
"""Νέο custom permission mydata.sync_vatdata για το sync-first calculation."""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mydata', '0003_remove_vatrecord_unique_client_mark_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='vatperiodresult',
            options={
                'ordering': ['-year', '-period'],
                'permissions': [
                    ('sync_vatdata',
                     'Μπορεί να κάνει sync δεδομένων ΦΠΑ από myDATA'),
                ],
                'verbose_name': 'Αποτέλεσμα ΦΠΑ Περιόδου',
                'verbose_name_plural': 'Αποτελέσματα ΦΠΑ Περιόδων',
            },
        ),
    ]
