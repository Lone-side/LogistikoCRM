# Generated manually for EmailSettings model with encrypted password field
# This creates the EmailSettings singleton model for SMTP configuration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "10003_obligationtype_profile_to_profiles"),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('smtp_host', models.CharField(default='smtp.gmail.com', help_text='π.χ. smtp.gmail.com, mail.example.com', max_length=255, verbose_name='SMTP Server')),
                ('smtp_port', models.PositiveIntegerField(default=587, help_text='Συνήθως 587 (TLS), 465 (SSL), ή 25', verbose_name='SMTP Port')),
                ('smtp_username', models.CharField(blank=True, default='', help_text='Συνήθως το email σας', max_length=255, verbose_name='SMTP Username')),
                # Password stored encrypted using Fernet
                ('_encrypted_smtp_password', models.TextField(blank=True, default='', help_text='App Password για Gmail/Google Workspace (κρυπτογραφημένο)', verbose_name='SMTP Password (encrypted)')),
                ('smtp_security', models.CharField(choices=[('tls', 'TLS (port 587)'), ('ssl', 'SSL (port 465)'), ('none', 'Κανένα (port 25)')], default='tls', max_length=10, verbose_name='Ασφάλεια')),
                ('from_email', models.EmailField(help_text='Η διεύθυνση που θα εμφανίζεται ως αποστολέας', max_length=254, verbose_name='Email Αποστολέα')),
                ('from_name', models.CharField(blank=True, default='', help_text='π.χ. Λογιστικό Γραφείο Παπαδόπουλος', max_length=100, verbose_name='Όνομα Αποστολέα')),
                ('reply_to', models.EmailField(blank=True, default='', help_text='Αν διαφέρει από το email αποστολέα', max_length=254, verbose_name='Reply-To Email')),
                ('company_name', models.CharField(blank=True, default='', max_length=200, verbose_name='Όνομα Εταιρείας')),
                ('company_phone', models.CharField(blank=True, default='', max_length=50, verbose_name='Τηλέφωνο Εταιρείας')),
                ('company_website', models.URLField(blank=True, default='', verbose_name='Website Εταιρείας')),
                ('accountant_name', models.CharField(blank=True, default='', max_length=100, verbose_name='Όνομα Λογιστή')),
                ('accountant_title', models.CharField(blank=True, default='Λογιστής Α\' Τάξης', help_text='π.χ. Λογιστής Α\' Τάξης, Ορκωτός Ελεγκτής', max_length=100, verbose_name='Τίτλος Λογιστή')),
                ('email_signature', models.TextField(blank=True, default='', help_text='HTML υπογραφή που προστίθεται στα emails', verbose_name='Υπογραφή Email')),
                ('rate_limit', models.FloatField(default=2.0, help_text='Μέγιστα emails ανά δευτερόλεπτο', verbose_name='Rate Limit (emails/sec)')),
                ('burst_limit', models.PositiveIntegerField(default=5, help_text='Μέγιστα emails σε burst', verbose_name='Burst Limit')),
                ('is_active', models.BooleanField(default=True, help_text='Αν απενεργοποιηθεί, τα emails δεν θα στέλνονται', verbose_name='Ενεργό')),
                ('last_test_at', models.DateTimeField(blank=True, null=True, verbose_name='Τελευταίο Test')),
                ('last_test_success', models.BooleanField(blank=True, null=True, verbose_name='Επιτυχές Test')),
                ('last_test_error', models.TextField(blank=True, default='', verbose_name='Σφάλμα Test')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Ρυθμίσεις Email',
                'verbose_name_plural': 'Ρυθμίσεις Email',
            },
        ),
    ]
