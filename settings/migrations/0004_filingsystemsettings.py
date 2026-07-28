# Generated manually for FilingSystemSettings

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0007_backupsettings_backuphistory'),
    ]

    operations = [
        migrations.CreateModel(
            name='FilingSystemSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('archive_root', models.CharField(blank=True, default='', help_text='Κοινόχρηστος φάκελος (π.χ. /mnt/nas/logistiko/ ή Z:\\Logistiko\\). Κενό = χρήση MEDIA_ROOT', max_length=500, verbose_name='Φάκελος Αρχειοθέτησης')),
                ('use_network_storage', models.BooleanField(default=False, help_text='Ενεργοποίηση αποθήκευσης σε κοινόχρηστο φάκελο δικτύου', verbose_name='Χρήση Δικτυακού Φακέλου')),
                ('folder_structure', models.CharField(choices=[('standard', 'Τυπική (ΑΦΜ_Επωνυμία/Έτος/Μήνας/Κατηγορία)'), ('year_first', 'Πρώτα Έτος (Έτος/ΑΦΜ_Επωνυμία/Μήνας/Κατηγορία)'), ('category_first', 'Πρώτα Κατηγορία (Κατηγορία/ΑΦΜ_Επωνυμία/Έτος/Μήνας)'), ('flat', 'Επίπεδη (ΑΦΜ_Επωνυμία/Κατηγορία)'), ('custom', 'Προσαρμοσμένη')], default='standard', help_text='Επιλογή τρόπου οργάνωσης φακέλων', max_length=20, verbose_name='Δομή Φακέλων')),
                ('custom_folder_template', models.CharField(blank=True, default='{afm}_{name}/{year}/{month:02d}/{category}', help_text='Template φακέλου. Μεταβλητές: {afm}, {name}, {year}, {month}, {category}, {month_name}', max_length=255, verbose_name='Προσαρμοσμένο Template')),
                ('enable_permanent_folder', models.BooleanField(default=True, help_text='Δημιουργία φακέλου για μόνιμα έγγραφα (συμβάσεις, καταστατικό, κλπ)', verbose_name='Μόνιμος Φάκελος (00_ΜΟΝΙΜΑ)')),
                ('permanent_folder_name', models.CharField(default='00_ΜΟΝΙΜΑ', help_text='Χρήση 00_ για να εμφανίζεται πρώτος στη λίστα', max_length=50, verbose_name='Όνομα Μόνιμου Φακέλου')),
                ('enable_yearend_folder', models.BooleanField(default=True, help_text='Δημιουργία φακέλου 13_ΕΤΗΣΙΑ για ετήσιες δηλώσεις (Ε1, Ε2, Ε3, ΕΝΦΙΑ)', verbose_name='Φάκελος Ετήσιων Δηλώσεων')),
                ('yearend_folder_name', models.CharField(default='13_ΕΤΗΣΙΑ', help_text='Χρήση 13_ για να εμφανίζεται μετά τους μήνες', max_length=50, verbose_name='Όνομα Φακέλου Ετήσιων')),
                ('document_categories', models.JSONField(blank=True, default=dict, help_text='JSON με επιπλέον κατηγορίες {code: label}', verbose_name='Κατηγορίες Εγγράφων')),
                ('file_naming_convention', models.CharField(choices=[('original', 'Αρχικό όνομα'), ('structured', 'Δομημένο (YYYYMMDD_ΑΦΜ_Κατηγορία_Όνομα)'), ('date_prefix', 'Ημ/νία + Αρχικό (YYYYMMDD_Όνομα)'), ('afm_prefix', 'ΑΦΜ + Αρχικό (ΑΦΜ_Όνομα)')], default='original', help_text='Τρόπος μετονομασίας αρχείων κατά το upload', max_length=20, verbose_name='Κανόνας Ονοματολογίας')),
                ('retention_years', models.PositiveIntegerField(default=5, help_text='Ελάχιστα έτη διατήρησης εγγράφων (νόμος: 5 έτη, παράταση: 20 έτη)', verbose_name='Έτη Διατήρησης')),
                ('auto_archive_years', models.PositiveIntegerField(default=0, help_text='Μετακίνηση σε Archive μετά από Χ έτη (0 = απενεργοποιημένο)', verbose_name='Αυτόματη Αρχειοθέτηση (έτη)')),
                ('enable_retention_warnings', models.BooleanField(default=True, help_text='Ειδοποίηση για έγγραφα που πλησιάζουν τη λήξη διατήρησης', verbose_name='Προειδοποιήσεις Διατήρησης')),
                ('allowed_extensions', models.CharField(default='.pdf,.xlsx,.xls,.docx,.doc,.jpg,.jpeg,.png,.gif,.zip,.txt,.csv,.xml', help_text='Καταλήξεις αρχείων διαχωρισμένες με κόμμα', max_length=500, verbose_name='Επιτρεπόμενες Καταλήξεις')),
                ('max_file_size_mb', models.PositiveIntegerField(default=10, help_text='Μέγιστο μέγεθος αρχείου σε MB', verbose_name='Μέγιστο Μέγεθος (MB)')),
                ('use_greek_month_names', models.BooleanField(default=False, help_text='Χρήση 01_Ιανουάριος αντί για 01', verbose_name='Ελληνικά Ονόματα Μηνών')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Δημιουργήθηκε')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Ενημερώθηκε')),
            ],
            options={
                'verbose_name': 'Ρυθμίσεις Αρχειοθέτησης',
                'verbose_name_plural': 'Ρυθμίσεις Αρχειοθέτησης',
            },
        ),
    ]
