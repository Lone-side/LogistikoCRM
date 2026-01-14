# Generated manually for folder_creation_mode and folder_templates
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0007_backupsettings_backuphistory'),
    ]

    operations = [
        migrations.AddField(
            model_name='filingsystemsettings',
            name='folder_creation_mode',
            field=models.CharField(
                choices=[
                    ('none', 'Καμία αυτόματη δημιουργία'),
                    ('minimal', 'Μόνο φάκελος πελάτη'),
                    ('basic', 'Πελάτης + Έτος'),
                    ('full', 'Πλήρης δομή (μήνες, κατηγορίες)')
                ],
                default='minimal',
                help_text='Τι φακέλους να δημιουργεί αυτόματα για νέο πελάτη',
                max_length=20,
                verbose_name='Αυτόματη Δημιουργία Φακέλων'
            ),
        ),
        migrations.AddField(
            model_name='filingsystemsettings',
            name='folder_templates',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Αποθηκευμένα templates δομής φακέλων που μπορεί να εφαρμόσει ο χρήστης',
                verbose_name='Templates Φακέλων'
            ),
        ),
        migrations.AlterField(
            model_name='filingsystemsettings',
            name='enable_permanent_folder',
            field=models.BooleanField(
                default=False,
                help_text='Δημιουργία φακέλου για μόνιμα έγγραφα (συμβάσεις, καταστατικό, κλπ)',
                verbose_name='Μόνιμος Φάκελος (00_ΜΟΝΙΜΑ)'
            ),
        ),
        migrations.AlterField(
            model_name='filingsystemsettings',
            name='enable_yearend_folder',
            field=models.BooleanField(
                default=False,
                help_text='Δημιουργία φακέλου 13_ΕΤΗΣΙΑ για ετήσιες δηλώσεις (Ε1, Ε2, Ε3, ΕΝΦΙΑ)',
                verbose_name='Φάκελος Ετήσιων Δηλώσεων'
            ),
        ),
    ]
