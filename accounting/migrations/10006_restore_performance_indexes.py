# Generated manually to restore performance indexes
# These indexes were accidentally removed in migration 10001
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Restore performance indexes that were removed in migration 10001.

    SAFE: Adding indexes does NOT affect existing data or functionality.
    It only improves query performance.
    """

    dependencies = [
        ('accounting', '10004_document_sharing_system'),
        ('accounting', '10005_emailsettings'),
    ]

    operations = [
        # ============================================
        # ClientProfile Indexes
        # ============================================
        migrations.AddIndex(
            model_name='clientprofile',
            index=models.Index(fields=['afm'], name='client_afm_idx'),
        ),
        migrations.AddIndex(
            model_name='clientprofile',
            index=models.Index(fields=['is_active', 'eponimia'], name='client_active_name_idx'),
        ),
        migrations.AddIndex(
            model_name='clientprofile',
            index=models.Index(fields=['company'], name='client_company_idx'),
        ),

        # ============================================
        # MonthlyObligation Indexes (CRITICAL for dashboard)
        # ============================================
        migrations.AddIndex(
            model_name='monthlyobligation',
            index=models.Index(fields=['status', 'deadline'], name='mo_status_deadline_idx'),
        ),
        migrations.AddIndex(
            model_name='monthlyobligation',
            index=models.Index(fields=['client', 'year', 'month'], name='mo_client_ym_idx'),
        ),
        migrations.AddIndex(
            model_name='monthlyobligation',
            index=models.Index(fields=['deadline', 'status'], name='mo_deadline_status_idx'),
        ),
        migrations.AddIndex(
            model_name='monthlyobligation',
            index=models.Index(fields=['-deadline'], name='mo_deadline_desc_idx'),
        ),
        migrations.AddIndex(
            model_name='monthlyobligation',
            index=models.Index(fields=['completed_by', 'completed_date'], name='mo_completed_idx'),
        ),
        migrations.AddIndex(
            model_name='monthlyobligation',
            index=models.Index(fields=['assigned_to', 'status'], name='mo_assigned_status_idx'),
        ),

        # ============================================
        # ScheduledEmail Indexes
        # ============================================
        migrations.AddIndex(
            model_name='scheduledemail',
            index=models.Index(fields=['status', 'send_at'], name='email_status_send_idx'),
        ),
        migrations.AddIndex(
            model_name='scheduledemail',
            index=models.Index(fields=['client', 'status'], name='email_client_status_idx'),
        ),
    ]
