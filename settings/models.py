from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
import os
import json


class FilingSystemSettings(models.Model):
    """
    Ρυθμίσεις Συστήματος Αρχειοθέτησης - Singleton model.

    Επιτρέπει την προσαρμογή της δομής φακέλων και των
    κανόνων αρχειοθέτησης για το λογιστικό γραφείο.
    """
    # Ρητά BigAutoField: το migration δημιούργησε bigint id ενώ το app default είναι AutoField
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')

    class Meta:
        verbose_name = _('Ρυθμίσεις Αρχειοθέτησης')
        verbose_name_plural = _('Ρυθμίσεις Αρχειοθέτησης')

    # === Βασικές Ρυθμίσεις ===
    archive_root = models.CharField(
        'Φάκελος Αρχειοθέτησης',
        max_length=500,
        default='',
        blank=True,
        help_text='Κοινόχρηστος φάκελος (π.χ. /mnt/nas/logistiko/ ή Z:\\Logistiko\\). '
                  'Κενό = χρήση MEDIA_ROOT'
    )

    use_network_storage = models.BooleanField(
        'Χρήση Δικτυακού Φακέλου',
        default=False,
        help_text='Ενεργοποίηση αποθήκευσης σε κοινόχρηστο φάκελο δικτύου'
    )

    # === Δομή Φακέλων ===
    FOLDER_STRUCTURE_CHOICES = [
        ('standard', 'Τυπική (ΑΦΜ_Επωνυμία/Έτος/Μήνας/Κατηγορία)'),
        ('year_first', 'Πρώτα Έτος (Έτος/ΑΦΜ_Επωνυμία/Μήνας/Κατηγορία)'),
        ('category_first', 'Πρώτα Κατηγορία (Κατηγορία/ΑΦΜ_Επωνυμία/Έτος/Μήνας)'),
        ('flat', 'Επίπεδη (ΑΦΜ_Επωνυμία/Κατηγορία)'),
        ('custom', 'Προσαρμοσμένη'),
    ]

    folder_structure = models.CharField(
        'Δομή Φακέλων',
        max_length=20,
        choices=FOLDER_STRUCTURE_CHOICES,
        default='standard',
        help_text='Επιλογή τρόπου οργάνωσης φακέλων'
    )

    custom_folder_template = models.CharField(
        'Προσαρμοσμένο Template',
        max_length=255,
        default='{afm}_{name}/{year}/{month:02d}/{category}',
        blank=True,
        help_text='Template φακέλου. Μεταβλητές: {afm}, {name}, {year}, {month}, {category}, {month_name}'
    )

    # === Μόνιμος Φάκελος ===
    enable_permanent_folder = models.BooleanField(
        'Μόνιμος Φάκελος (00_ΜΟΝΙΜΑ)',
        default=True,
        help_text='Δημιουργία φακέλου για μόνιμα έγγραφα (συμβάσεις, καταστατικό, κλπ)'
    )

    permanent_folder_name = models.CharField(
        'Όνομα Μόνιμου Φακέλου',
        max_length=50,
        default='00_ΜΟΝΙΜΑ',
        help_text='Χρήση 00_ για να εμφανίζεται πρώτος στη λίστα'
    )

    # === Ετήσιος Φάκελος ===
    enable_yearend_folder = models.BooleanField(
        'Φάκελος Ετήσιων Δηλώσεων',
        default=True,
        help_text='Δημιουργία φακέλου 13_ΕΤΗΣΙΑ για ετήσιες δηλώσεις (Ε1, Ε2, Ε3, ΕΝΦΙΑ)'
    )

    yearend_folder_name = models.CharField(
        'Όνομα Φακέλου Ετήσιων',
        max_length=50,
        default='13_ΕΤΗΣΙΑ',
        help_text='Χρήση 13_ για να εμφανίζεται μετά τους μήνες'
    )

    # === Κατηγορίες Εγγράφων ===
    document_categories = models.JSONField(
        'Κατηγορίες Εγγράφων',
        default=dict,
        blank=True,
        help_text='JSON με επιπλέον κατηγορίες {code: label}'
    )

    # === Ονοματολογία Αρχείων ===
    FILE_NAMING_CHOICES = [
        ('original', 'Αρχικό όνομα'),
        ('structured', 'Δομημένο (YYYYMMDD_ΑΦΜ_Κατηγορία_Όνομα)'),
        ('date_prefix', 'Ημ/νία + Αρχικό (YYYYMMDD_Όνομα)'),
        ('afm_prefix', 'ΑΦΜ + Αρχικό (ΑΦΜ_Όνομα)'),
    ]

    file_naming_convention = models.CharField(
        'Κανόνας Ονοματολογίας',
        max_length=20,
        choices=FILE_NAMING_CHOICES,
        default='original',
        help_text='Τρόπος μετονομασίας αρχείων κατά το upload'
    )

    # === Πολιτική Διατήρησης ===
    retention_years = models.PositiveIntegerField(
        'Έτη Διατήρησης',
        default=5,
        help_text='Ελάχιστα έτη διατήρησης εγγράφων (νόμος: 5 έτη, παράταση: 20 έτη)'
    )

    auto_archive_years = models.PositiveIntegerField(
        'Αυτόματη Αρχειοθέτηση (έτη)',
        default=0,
        help_text='Μετακίνηση σε Archive μετά από Χ έτη (0 = απενεργοποιημένο)'
    )

    enable_retention_warnings = models.BooleanField(
        'Προειδοποιήσεις Διατήρησης',
        default=True,
        help_text='Ειδοποίηση για έγγραφα που πλησιάζουν τη λήξη διατήρησης'
    )

    # === Ασφάλεια ===
    allowed_extensions = models.CharField(
        'Επιτρεπόμενες Καταλήξεις',
        max_length=500,
        default='.pdf,.xlsx,.xls,.docx,.doc,.jpg,.jpeg,.png,.gif,.zip,.txt,.csv,.xml',
        help_text='Καταλήξεις αρχείων διαχωρισμένες με κόμμα'
    )

    max_file_size_mb = models.PositiveIntegerField(
        'Μέγιστο Μέγεθος (MB)',
        default=10,
        help_text='Μέγιστο μέγεθος αρχείου σε MB'
    )

    # === Μήνες Ελληνικά ===
    use_greek_month_names = models.BooleanField(
        'Ελληνικά Ονόματα Μηνών',
        default=False,
        help_text='Χρήση 01_Ιανουάριος αντί για 01'
    )

    # === Metadata ===
    created_at = models.DateTimeField('Δημιουργήθηκε', auto_now_add=True)
    updated_at = models.DateTimeField('Ενημερώθηκε', auto_now=True)

    # === Greek Month Names ===
    GREEK_MONTHS = {
        1: 'Ιανουάριος',
        2: 'Φεβρουάριος',
        3: 'Μάρτιος',
        4: 'Απρίλιος',
        5: 'Μάιος',
        6: 'Ιούνιος',
        7: 'Ιούλιος',
        8: 'Αύγουστος',
        9: 'Σεπτέμβριος',
        10: 'Οκτώβριος',
        11: 'Νοέμβριος',
        12: 'Δεκέμβριος',
    }

    # === Default Categories ===
    DEFAULT_CATEGORIES = {
        # Μόνιμα
        'registration': 'Ιδρυτικά Έγγραφα',
        'contracts': 'Συμβάσεις',
        'licenses': 'Άδειες & Πιστοποιητικά',
        # Μηνιαία
        'vat': 'ΦΠΑ',
        'apd': 'ΑΠΔ/ΕΦΚΑ',
        'myf': 'ΜΥΦ',
        'payroll': 'Μισθοδοσία',
        'invoices_issued': 'Εκδοθέντα Τιμολόγια',
        'invoices_received': 'Ληφθέντα Τιμολόγια',
        'bank': 'Τραπεζικά',
        'receipts': 'Αποδείξεις',
        # Ετήσια
        'e1': 'Ε1 - Φόρος Εισοδήματος',
        'e2': 'Ε2 - Ακίνητα',
        'e3': 'Ε3 - Οικονομικά Στοιχεία',
        'enfia': 'ΕΝΦΙΑ',
        'balance': 'Ισολογισμός',
        'audit': 'Έλεγχοι',
        # Γενικά
        'correspondence': 'Αλληλογραφία',
        'general': 'Γενικά',
    }

    def save(self, *args, **kwargs):
        # Singleton pattern
        if not self.pk and FilingSystemSettings.objects.exists():
            existing = FilingSystemSettings.objects.first()
            self.pk = existing.pk
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        """Επιστρέφει τις ρυθμίσεις ή δημιουργεί default."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def get_archive_root(self):
        """Επιστρέφει το root path για αρχειοθέτηση."""
        if self.use_network_storage and self.archive_root:
            return self.archive_root
        return os.environ.get('ARCHIVE_ROOT', str(settings.MEDIA_ROOT))

    def get_allowed_extensions_list(self):
        """Επιστρέφει λίστα με επιτρεπόμενες καταλήξεις."""
        return [ext.strip().lower() for ext in self.allowed_extensions.split(',') if ext.strip()]

    def get_max_file_size_bytes(self):
        """Επιστρέφει μέγιστο μέγεθος σε bytes."""
        return self.max_file_size_mb * 1024 * 1024

    def get_all_categories(self):
        """Επιστρέφει όλες τις κατηγορίες (default + custom)."""
        categories = self.DEFAULT_CATEGORIES.copy()
        if self.document_categories:
            categories.update(self.document_categories)
        return categories

    def get_month_folder_name(self, month_number):
        """Επιστρέφει το όνομα φακέλου για τον μήνα."""
        if self.use_greek_month_names:
            return f"{month_number:02d}_{self.GREEK_MONTHS.get(month_number, '')}"
        return f"{month_number:02d}"

    def build_client_path(self, client, year=None, month=None, category=None):
        """
        Δημιουργεί το path για αρχεία πελάτη βάσει ρυθμίσεων.

        Args:
            client: ClientProfile instance
            year: Έτος (optional)
            month: Μήνας (optional)
            category: Κατηγορία (optional)

        Returns:
            Relative path string
        """
        import re

        # Καθαρισμός επωνυμίας
        safe_name = re.sub(r'[^\w\s-]', '', client.eponimia)[:30]
        safe_name = safe_name.replace(' ', '_').strip('_')

        # Βασικό path πελάτη
        if self.folder_structure == 'standard':
            base = f"{client.afm}_{safe_name}"
        elif self.folder_structure == 'year_first' and year:
            base = f"{year}/{client.afm}_{safe_name}"
        elif self.folder_structure == 'category_first' and category:
            base = f"{category}/{client.afm}_{safe_name}"
        elif self.folder_structure == 'custom':
            base = self.custom_folder_template.format(
                afm=client.afm,
                name=safe_name,
                year=year or '',
                month=month or '',
                month_name=self.GREEK_MONTHS.get(month, '') if month else '',
                category=category or ''
            )
        else:
            base = f"{client.afm}_{safe_name}"

        # Προσθήκη year/month/category
        parts = ['clients', base]

        if year and self.folder_structure not in ['year_first', 'flat', 'custom']:
            parts.append(str(year))

        if month and self.folder_structure not in ['flat', 'custom']:
            parts.append(self.get_month_folder_name(month))

        if category and self.folder_structure not in ['category_first', 'custom']:
            parts.append(category)

        return os.path.join(*parts)

    def generate_filename(self, original_filename, client=None, category=None, date=None):
        """
        Δημιουργεί το όνομα αρχείου βάσει κανόνα ονοματολογίας.
        """
        from datetime import datetime
        import re

        if self.file_naming_convention == 'original':
            return original_filename

        # Εξαγωγή βασικού ονόματος και κατάληξης
        name, ext = os.path.splitext(original_filename)
        safe_name = re.sub(r'[^\w\s-]', '', name)[:50]

        date_str = (date or datetime.now()).strftime('%Y%m%d')

        if self.file_naming_convention == 'structured':
            afm = client.afm if client else ''
            cat = category or ''
            return f"{date_str}_{afm}_{cat}_{safe_name}{ext}"

        elif self.file_naming_convention == 'date_prefix':
            return f"{date_str}_{safe_name}{ext}"

        elif self.file_naming_convention == 'afm_prefix':
            afm = client.afm if client else ''
            return f"{afm}_{safe_name}{ext}"

        return original_filename

    def get_permanent_folder_categories(self):
        """Κατηγορίες για τον μόνιμο φάκελο."""
        return ['registration', 'contracts', 'licenses', 'correspondence']

    def get_yearend_folder_categories(self):
        """Κατηγορίες για τον ετήσιο φάκελο."""
        return ['e1', 'e2', 'e3', 'enfia', 'balance', 'audit']

    def get_monthly_folder_categories(self):
        """Κατηγορίες για μηνιαίους φακέλους."""
        return ['vat', 'apd', 'myf', 'payroll', 'invoices_issued',
                'invoices_received', 'bank', 'receipts', 'general']

    def __str__(self):
        return f"Filing System Settings (Root: {self.get_archive_root()[:50]}...)"


class BackupSettings(models.Model):
    """
    Ρυθμίσεις Backup - Singleton model.
    """
    # Ρητά BigAutoField: το migration δημιούργησε bigint id ενώ το app default είναι AutoField
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')

    class Meta:
        verbose_name = _('Ρυθμίσεις Backup')
        verbose_name_plural = _('Ρυθμίσεις Backup')
        permissions = [
            ('can_create_backup', 'Δημιουργία backup'),
            ('can_restore_backup', 'Επαναφορά backup'),
            ('can_download_backup', 'Λήψη backup'),
        ]

    backup_path = models.CharField(
        'Φάκελος Backup',
        max_length=500,
        default='backups/',
        help_text='Σχετικό path από το MEDIA_ROOT ή απόλυτο path'
    )
    include_media = models.BooleanField(
        'Συμπερίληψη Media',
        default=True,
        help_text='Να συμπεριλαμβάνονται τα uploaded αρχεία'
    )
    max_backups = models.PositiveIntegerField(
        'Μέγιστος αριθμός Backups',
        default=10,
        help_text='Αυτόματη διαγραφή παλαιότερων (0 = χωρίς όριο)'
    )
    created_at = models.DateTimeField('Δημιουργήθηκε', auto_now_add=True)
    updated_at = models.DateTimeField('Ενημερώθηκε', auto_now=True)

    def save(self, *args, **kwargs):
        # Singleton pattern
        if not self.pk and BackupSettings.objects.exists():
            existing = BackupSettings.objects.first()
            self.pk = existing.pk
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        """Επιστρέφει τις ρυθμίσεις ή δημιουργεί default."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def get_backup_dir(self):
        """Επιστρέφει το πλήρες path του backup folder."""
        if os.path.isabs(self.backup_path):
            return self.backup_path
        return os.path.join(settings.MEDIA_ROOT, self.backup_path)

    def __str__(self):
        return f"Backup Settings ({self.backup_path})"


class BackupHistory(models.Model):
    """
    Ιστορικό Backups.
    """
    # Ρητά BigAutoField: το migration δημιούργησε bigint id ενώ το app default είναι AutoField
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')

    class Meta:
        verbose_name = _('Backup')
        verbose_name_plural = _('Ιστορικό Backups')
        ordering = ['-created_at']

    RESTORE_MODE_CHOICES = [
        ('replace', 'Αντικατάσταση'),
        ('merge', 'Συγχώνευση'),
    ]

    filename = models.CharField('Αρχείο', max_length=255)
    file_path = models.CharField('Πλήρες Path', max_length=500)
    file_size = models.BigIntegerField('Μέγεθος (bytes)', default=0)
    includes_db = models.BooleanField('Περιέχει DB', default=True)
    includes_media = models.BooleanField('Περιέχει Media', default=False)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='backups_created',
        verbose_name='Δημιουργήθηκε από'
    )
    created_at = models.DateTimeField('Δημιουργήθηκε', auto_now_add=True)
    notes = models.TextField('Σημειώσεις', blank=True)

    # Restore tracking
    restored_at = models.DateTimeField('Επαναφέρθηκε', null=True, blank=True)
    restored_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='backups_restored',
        verbose_name='Επαναφέρθηκε από'
    )
    restore_mode = models.CharField(
        'Τρόπος επαναφοράς',
        max_length=10,
        choices=RESTORE_MODE_CHOICES,
        null=True,
        blank=True
    )

    def file_size_display(self):
        """Εμφάνιση μεγέθους σε human-readable format."""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def file_exists(self):
        """Έλεγχος αν το αρχείο υπάρχει."""
        return os.path.exists(self.file_path)

    def __str__(self):
        return f"{self.filename} ({self.created_at.strftime('%d/%m/%Y %H:%M')})"


class GSISSettings(models.Model):
    """
    Ρυθμίσεις για GSIS API (Λήψη στοιχείων με ΑΦΜ).

    Χρησιμοποιεί τους "Ειδικούς Κωδικούς Λήψης Στοιχείων" της ΑΑΔΕ.
    Singleton model - μόνο μία εγγραφή επιτρέπεται.
    """
    # Ρητά BigAutoField: το migration δημιούργησε bigint id ενώ το app default είναι AutoField
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')

    class Meta:
        verbose_name = _('Ρυθμίσεις GSIS')
        verbose_name_plural = _('Ρυθμίσεις GSIS')

    afm = models.CharField(
        'ΑΦΜ',
        max_length=9,
        help_text='Το ΑΦΜ του λογιστή (για την παράμετρο afm_called_by)'
    )
    username = models.CharField(
        'Όνομα Χρήστη',
        max_length=100,
        help_text='Ειδικός κωδικός λήψης στοιχείων - Username'
    )
    password = models.CharField(
        'Κωδικός',
        max_length=100,
        help_text='Ειδικός κωδικός λήψης στοιχείων - Password'
    )
    is_active = models.BooleanField(
        'Ενεργό',
        default=True,
        help_text='Αν είναι απενεργοποιημένο, η λήψη στοιχείων δεν θα είναι διαθέσιμη'
    )
    created_at = models.DateTimeField('Δημιουργήθηκε', auto_now_add=True)
    updated_at = models.DateTimeField('Ενημερώθηκε', auto_now=True)

    def save(self, *args, **kwargs):
        # Singleton pattern - only one instance allowed
        if not self.pk and GSISSettings.objects.exists():
            # Update existing instead of creating new
            existing = GSISSettings.objects.first()
            self.pk = existing.pk
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        """Επιστρέφει τις ρυθμίσεις GSIS ή None αν δεν υπάρχουν."""
        return cls.objects.first()

    def __str__(self):
        return f"GSIS Settings ({self.username})"


class BannedCompanyName(models.Model):
    """
    Model representing a banned company name.

    This model is used to store company names that block the automatic generation
    of commercial requests from spam messages.
    Each name is unique and cannot be null or blank.

    Attributes:
        name (str): The name of the banned company, stored as a unique string
            with a maximum length of 50 characters.
    """
    class Meta:
        verbose_name = _("Banned company name")
        verbose_name_plural = _("Banned company names")

    name = models.CharField(
        max_length=50, unique=True,
        null=False, blank=False,
        verbose_name=_("Name")
    )

    def __str__(self):
        """
        Returns the string representation of the banned company name.
        """
        return self.name


class MassmailSettings(models.Model):
    """
    Model for mass mailing settings.
    """

    class Meta:
        verbose_name = _("Massmail Settings")
        verbose_name_plural = _("Massmail Settings")

    emails_per_day = models.PositiveIntegerField(
        default=94,
        help_text="Daily message limit for email accounts."
    )
    use_business_time = models.BooleanField(
        default=False,
        help_text="Send only during business hours."
    )
    business_time_start = models.TimeField(
        default="08:30",
        help_text="Start of working hours."
    )
    business_time_end = models.TimeField(
        default="17:30",
        help_text="End of working hours."
    )
    unsubscribe_url = models.URLField(
        default="https://www.example.com/unsubscribe",
        help_text='"Unsubscribed successfully" page."'
    )

    def __str__(self):
        return "Settings"


class PublicEmailDomain(models.Model):
    """
    Model representing a public email domain list.

    This model is used to store public domains to identify them in messages
    and prevent company identification by email domain.
    Each domain is unique and stored in the lowercase.

    Attributes:
        domain (str): The email domain, stored as a unique string with a
            maximum length of 20 characters.
    """
    class Meta:
        verbose_name = _('Public email domain')
        verbose_name_plural = _('Public email domains')

    domain = models.CharField(
        max_length=20, unique=True,
        null=False, blank=False,
        verbose_name=_("Domain")
    )

    def save(self, *args, **kwargs):
        """
        Overrides the save method to ensure the domain is stored in lowercase.
        """
        self.domain = self.domain.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        """
        Returns the string representation of the public email domain.
        """
        return self.domain


class Reminders(models.Model):
    """
    Model for storing reminder settings.

    This model is used to configure the interval at which reminders are checked.

    Attributes:
        check_interval (int): The interval in seconds to check for reminders,
            stored as a positive integer. Defaults to 300 seconds.
    """
    class Meta:
        verbose_name = _('Reminder settings')
        verbose_name_plural = _('Reminder settings')

    check_interval = models.PositiveBigIntegerField(
        null=False, blank=False,
        default='300',
        verbose_name=_("Check interval"),
        help_text=_(
            "Specify the interval in seconds to check if it's time for a reminder."
        )
    )

    def __str__(self):
        """
        Returns a string representation of the reminder settings.
        """
        return "Settings"


class StopPhrase(models.Model):
    """
    Model representing a stop phrase.

    This model is used to store phrases that block the automatic generation
    of commercial requests from spam messages. It also tracks the last
    occurrence date of each phrase.

    Attributes:
        phrase (str): The stop phrase, stored as a unique string with a
            maximum length of 100 characters.
        last_occurrence_date (date): The date when the phrase was most recently
            encountered, updated automatically whenever the record is saved.
    """
    class Meta:
        verbose_name = _('Stop Phrase')
        verbose_name_plural = _('Stop Phrases')

    phrase = models.CharField(
        max_length=100, unique=True,
        null=False, blank=False,
        verbose_name=_("Phrase")
    )
    last_occurrence_date = models.DateField(
        auto_now=True,
        verbose_name=_("Last occurrence date"),
        help_text=_("Date of last occurrence of the phrase")
    )

    def hit(self):
        """
        Updates the last occurrence date of the stop phrase to the current date.
        """
        self.save()

    def __str__(self):
        """
        Returns the string representation of the stop phrase.
        """
        return self.phrase


class UserNotificationSettings(models.Model):
    """
    Προτιμήσεις ειδοποιήσεων ανά χρήστη (σελίδα Ρυθμίσεις του React UI).
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_settings',
        verbose_name='Χρήστης',
    )
    email_reminders = models.BooleanField(
        'Email υπενθυμίσεις προθεσμιών', default=True)
    email_overdue = models.BooleanField(
        'Email για εκπρόθεσμες υποχρεώσεις', default=True)
    new_files = models.BooleanField(
        'Ειδοποίηση για νέα αρχεία', default=False)
    missed_calls = models.BooleanField(
        'Ειδοποίηση για αναπάντητες κλήσεις', default=True)
    weekly_summary = models.BooleanField(
        'Εβδομαδιαία σύνοψη', default=False)

    updated_at = models.DateTimeField('Ενημερώθηκε', auto_now=True)

    class Meta:
        verbose_name = 'Ρυθμίσεις Ειδοποιήσεων Χρήστη'
        verbose_name_plural = 'Ρυθμίσεις Ειδοποιήσεων Χρηστών'

    def __str__(self):
        return f"Ειδοποιήσεις: {self.user.username}"

    @classmethod
    def get_for_user(cls, user):
        obj, _ = cls.objects.get_or_create(user=user)
        return obj
