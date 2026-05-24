# Generated manually for backup system

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('settings', '0005_gsissettings_afm'),
    ]

    operations = [
        migrations.CreateModel(
            name='BackupSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('backup_path', models.CharField(default='backups/', help_text='Σχετικό path από το MEDIA_ROOT ή απόλυτο path', max_length=500, verbose_name='Φάκελος Backup')),
                ('include_media', models.BooleanField(default=True, help_text='Να συμπεριλαμβάνονται τα uploaded αρχεία', verbose_name='Συμπερίληψη Media')),
                ('max_backups', models.PositiveIntegerField(default=10, help_text='Αυτόματη διαγραφή παλαιότερων (0 = χωρίς όριο)', verbose_name='Μέγιστος αριθμός Backups')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Δημιουργήθηκε')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Ενημερώθηκε')),
            ],
            options={
                'verbose_name': 'Ρυθμίσεις Backup',
                'verbose_name_plural': 'Ρυθμίσεις Backup',
                'permissions': [
                    ('can_create_backup', 'Δημιουργία backup'),
                    ('can_restore_backup', 'Επαναφορά backup'),
                    ('can_download_backup', 'Λήψη backup'),
                ],
            },
        ),
        migrations.CreateModel(
            name='BackupHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('filename', models.CharField(max_length=255, verbose_name='Αρχείο')),
                ('file_path', models.CharField(max_length=500, verbose_name='Πλήρες Path')),
                ('file_size', models.BigIntegerField(default=0, verbose_name='Μέγεθος (bytes)')),
                ('includes_db', models.BooleanField(default=True, verbose_name='Περιέχει DB')),
                ('includes_media', models.BooleanField(default=False, verbose_name='Περιέχει Media')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Δημιουργήθηκε')),
                ('notes', models.TextField(blank=True, verbose_name='Σημειώσεις')),
                ('restored_at', models.DateTimeField(blank=True, null=True, verbose_name='Επαναφέρθηκε')),
                ('restore_mode', models.CharField(blank=True, choices=[('replace', 'Αντικατάσταση'), ('merge', 'Συγχώνευση')], max_length=10, null=True, verbose_name='Τρόπος επαναφοράς')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='backups_created', to=settings.AUTH_USER_MODEL, verbose_name='Δημιουργήθηκε από')),
                ('restored_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='backups_restored', to=settings.AUTH_USER_MODEL, verbose_name='Επαναφέρθηκε από')),
            ],
            options={
                'verbose_name': 'Backup',
                'verbose_name_plural': 'Ιστορικό Backups',
                'ordering': ['-created_at'],
            },
        ),
    ]
