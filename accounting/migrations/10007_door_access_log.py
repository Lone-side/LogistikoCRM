# Generated migration for DoorAccessLog model
# accounting/migrations/10006_door_access_log.py

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounting', '10006_restore_performance_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='DoorAccessLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('status', 'Έλεγχος Κατάστασης'), ('open', 'Άνοιγμα'), ('toggle', 'Toggle'), ('pulse', 'Pulse')], max_length=20, verbose_name='Ενέργεια')),
                ('result', models.CharField(choices=[('success', 'Επιτυχία'), ('failed', 'Αποτυχία'), ('timeout', 'Timeout'), ('offline', 'Εκτός Σύνδεσης')], max_length=20, verbose_name='Αποτέλεσμα')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP Διεύθυνση')),
                ('user_agent', models.CharField(blank=True, default='', max_length=500, verbose_name='User Agent')),
                ('response_data', models.JSONField(blank=True, null=True, verbose_name='Απάντηση')),
                ('timestamp', models.DateTimeField(auto_now_add=True, verbose_name='Χρονική Στιγμή')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='door_access_logs', to=settings.AUTH_USER_MODEL, verbose_name='Χρήστης')),
            ],
            options={
                'verbose_name': 'Log Πρόσβασης Πόρτας',
                'verbose_name_plural': 'Logs Πρόσβασης Πόρτας',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='dooraccesslog',
            index=models.Index(fields=['-timestamp'], name='door_log_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='dooraccesslog',
            index=models.Index(fields=['user', '-timestamp'], name='door_log_user_idx'),
        ),
        migrations.AddIndex(
            model_name='dooraccesslog',
            index=models.Index(fields=['action', 'result'], name='door_log_action_idx'),
        ),
    ]
