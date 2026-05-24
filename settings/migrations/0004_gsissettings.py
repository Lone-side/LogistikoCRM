# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0004_filingsystemsettings'),
    ]

    operations = [
        migrations.CreateModel(
            name='GSISSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(help_text='Ειδικός κωδικός λήψης στοιχείων - Username', max_length=100, verbose_name='Όνομα Χρήστη')),
                ('password', models.CharField(help_text='Ειδικός κωδικός λήψης στοιχείων - Password', max_length=100, verbose_name='Κωδικός')),
                ('is_active', models.BooleanField(default=True, help_text='Αν είναι απενεργοποιημένο, η λήψη στοιχείων δεν θα είναι διαθέσιμη', verbose_name='Ενεργό')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Δημιουργήθηκε')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Ενημερώθηκε')),
            ],
            options={
                'verbose_name': 'Ρυθμίσεις GSIS',
                'verbose_name_plural': 'Ρυθμίσεις GSIS',
            },
        ),
    ]
