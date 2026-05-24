# mydata/models.py
"""
Models για myDATA Integration (ΑΑΔΕ Ηλεκτρονικά Βιβλία)

Περιλαμβάνει:
- MyDataCredentials: Per-client encrypted credentials
- VATRecord: Αναλυτικά VAT records από RequestVatInfo
- MyDataSyncLog: Logging για sync operations
"""

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
import logging

from .encryption import encrypt_value, decrypt_value, safe_decrypt, is_encrypted

logger = logging.getLogger(__name__)


# =============================================================================
# MYDATA CREDENTIALS
# =============================================================================

class MyDataCredentials(models.Model):
    """
    myDATA API credentials για κάθε πελάτη.

    SECURITY:
    - user_id και subscription_key αποθηκεύονται encrypted
    - Χρησιμοποιεί Fernet symmetric encryption
    - Το encryption key προέρχεται από Django SECRET_KEY

    USAGE:
        # Get credentials
        creds = client_profile.mydata_credentials
        print(creds.user_id)  # Decrypted automatically

        # Set credentials
        creds.user_id = "my_user_id"  # Encrypted automatically
        creds.subscription_key = "my_key"
        creds.save()
    """

    # Link to ClientProfile (OneToOne)
    client = models.OneToOneField(
        'accounting.ClientProfile',
        on_delete=models.CASCADE,
        related_name='mydata_credentials',
        verbose_name='Πελάτης'
    )

    # Encrypted credentials (stored as encrypted text)
    _encrypted_user_id = models.TextField(
        verbose_name='User ID (encrypted)',
        blank=True,
        default='',
        help_text='AADE User ID - κρυπτογραφημένο'
    )

    _encrypted_subscription_key = models.TextField(
        verbose_name='Subscription Key (encrypted)',
        blank=True,
        default='',
        help_text='AADE Subscription Key - κρυπτογραφημένο'
    )

    # Environment setting
    is_sandbox = models.BooleanField(
        verbose_name='Sandbox Mode',
        default=False,
        help_text='True για testing environment (mydataapidev.aade.gr)'
    )

    # Sync tracking
    last_sync_at = models.DateTimeField(
        verbose_name='Τελευταίο Sync',
        null=True,
        blank=True
    )

    last_vat_sync_at = models.DateTimeField(
        verbose_name='Τελευταίο VAT Sync',
        null=True,
        blank=True
    )

    # Track last marks for incremental sync
    last_income_mark = models.BigIntegerField(
        verbose_name='Τελευταίο Income Mark',
        default=0,
        help_text='Για incremental sync εσόδων'
    )

    last_expense_mark = models.BigIntegerField(
        verbose_name='Τελευταίο Expense Mark',
        default=0,
        help_text='Για incremental sync εξόδων'
    )

    # Status
    is_active = models.BooleanField(
        verbose_name='Ενεργό',
        default=True,
        help_text='Αν είναι False, δεν θα γίνεται sync'
    )

    is_verified = models.BooleanField(
        verbose_name='Επιβεβαιωμένο',
        default=False,
        help_text='True αν τα credentials έχουν επιβεβαιωθεί'
    )

    verification_error = models.TextField(
        verbose_name='Σφάλμα Επιβεβαίωσης',
        blank=True,
        default='',
        help_text='Τελευταίο error message κατά την επιβεβαίωση'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Δημιουργία')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Ενημέρωση')

    # Notes
    notes = models.TextField(
        verbose_name='Σημειώσεις',
        blank=True,
        default='',
        help_text='Εσωτερικές σημειώσεις'
    )

    # Initial credit balance (one-time setup)
    initial_credit_balance = models.DecimalField(
        verbose_name='Αρχικό Πιστωτικό Υπόλοιπο',
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Πιστωτικό υπόλοιπο κατά την έναρξη χρήσης του συστήματος'
    )

    # Date when initial credit was set (to know which period to apply it)
    initial_credit_period_year = models.IntegerField(
        verbose_name='Έτος Αρχικού Πιστωτικού',
        null=True,
        blank=True,
        help_text='Από ποιο έτος εφαρμόζεται το αρχικό πιστωτικό'
    )

    initial_credit_period = models.IntegerField(
        verbose_name='Περίοδος Αρχικού Πιστωτικού',
        null=True,
        blank=True,
        help_text='Από ποια περίοδο εφαρμόζεται (μήνας ή τρίμηνο)'
    )

    class Meta:
        verbose_name = 'myDATA Credentials'
        verbose_name_plural = 'myDATA Credentials'
        ordering = ['client__eponimia']

    def __str__(self):
        status = "✓" if self.is_verified else "?"
        env = "SANDBOX" if self.is_sandbox else "PROD"
        return f"{self.client.eponimia} [{env}] {status}"

    # =========================================================================
    # ENCRYPTED PROPERTY: user_id
    # =========================================================================

    @property
    def user_id(self) -> str:
        """Get decrypted user_id."""
        if not self._encrypted_user_id:
            return ''
        return safe_decrypt(self._encrypted_user_id) or ''

    @user_id.setter
    def user_id(self, value: str):
        """Set encrypted user_id."""
        if value:
            # Don't re-encrypt if already encrypted
            if not is_encrypted(value):
                self._encrypted_user_id = encrypt_value(value)
            else:
                self._encrypted_user_id = value
        else:
            self._encrypted_user_id = ''
        # Reset verification when credentials change
        self.is_verified = False

    # =========================================================================
    # ENCRYPTED PROPERTY: subscription_key
    # =========================================================================

    @property
    def subscription_key(self) -> str:
        """Get decrypted subscription_key."""
        if not self._encrypted_subscription_key:
            return ''
        return safe_decrypt(self._encrypted_subscription_key) or ''

    @subscription_key.setter
    def subscription_key(self, value: str):
        """Set encrypted subscription_key."""
        if value:
            if not is_encrypted(value):
                self._encrypted_subscription_key = encrypt_value(value)
            else:
                self._encrypted_subscription_key = value
        else:
            self._encrypted_subscription_key = ''
        # Reset verification when credentials change
        self.is_verified = False

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    @property
    def has_credentials(self) -> bool:
        """Check if both credentials are set."""
        return bool(self._encrypted_user_id and self._encrypted_subscription_key)

    @property
    def client_afm(self) -> str:
        """Shortcut to client's AFM."""
        return self.client.afm if self.client else ''

    def get_api_client(self):
        """
        Δημιουργεί MyDataClient instance με τα credentials αυτού του πελάτη.

        Returns:
            MyDataClient instance

        Raises:
            ValueError: Αν δεν υπάρχουν credentials
        """
        from .client import MyDataClient, MyDataCredentialsNotFoundError

        if not self.has_credentials:
            raise MyDataCredentialsNotFoundError(self.client_afm)

        return MyDataClient(
            user_id=self.user_id,
            subscription_key=self.subscription_key,
            is_sandbox=self.is_sandbox
        )

    def verify_credentials(self) -> bool:
        """
        Επαληθεύει τα credentials κάνοντας ένα test API call.

        Returns:
            True αν τα credentials είναι valid

        Updates:
            is_verified, verification_error fields
        """
        from .client import MyDataAuthError, MyDataAPIError
        from datetime import date, timedelta

        if not self.has_credentials:
            self.is_verified = False
            self.verification_error = "Δεν έχουν οριστεί credentials"
            self.save(update_fields=['is_verified', 'verification_error'])
            return False

        try:
            client = self.get_api_client()

            # Try to fetch last 7 days VAT info (minimal request)
            today = date.today()
            week_ago = today - timedelta(days=7)

            # Just try the request - we don't care about results
            list(client.request_vat_info(
                date_from=week_ago,
                date_to=today
            ))

            self.is_verified = True
            self.verification_error = ''
            self.save(update_fields=['is_verified', 'verification_error'])
            return True

        except MyDataAuthError as e:
            self.is_verified = False
            self.verification_error = f"Authentication failed: {e.message}"
            self.save(update_fields=['is_verified', 'verification_error'])
            return False

        except MyDataAPIError as e:
            # Other API errors might not mean bad credentials
            self.is_verified = False
            self.verification_error = f"API Error: {e.message}"
            self.save(update_fields=['is_verified', 'verification_error'])
            return False

        except Exception as e:
            self.is_verified = False
            self.verification_error = f"Unexpected error: {str(e)}"
            self.save(update_fields=['is_verified', 'verification_error'])
            return False

    def mark_sync_completed(self):
        """Update last_sync_at timestamp."""
        self.last_sync_at = timezone.now()
        self.save(update_fields=['last_sync_at'])

    def mark_vat_sync_completed(self):
        """Update last_vat_sync_at timestamp."""
        self.last_vat_sync_at = timezone.now()
        self.save(update_fields=['last_vat_sync_at'])


# =============================================================================
# VAT RECORD
# =============================================================================

class VATRecord(models.Model):
    """
    Αναλυτική εγγραφή ΦΠΑ από myDATA RequestVatInfo.

    Κάθε record αντιστοιχεί σε μία VatInfo εγγραφή από το API.
    Τα summaries υπολογίζονται on-the-fly από αυτά τα records.
    """

    REC_TYPE_CHOICES = [
        (1, 'Εκροές (Έσοδα)'),
        (2, 'Εισροές (Έξοδα)'),
    ]

    VAT_CATEGORY_CHOICES = [
        (1, 'ΦΠΑ 24%'),
        (2, 'ΦΠΑ 13%'),
        (3, 'ΦΠΑ 6%'),
        (4, 'ΦΠΑ 17%'),
        (5, 'ΦΠΑ 9%'),
        (6, 'ΦΠΑ 4%'),
        (7, 'ΦΠΑ 0%'),
        (8, 'Χωρίς ΦΠΑ'),
    ]

    # Link to client
    client = models.ForeignKey(
        'accounting.ClientProfile',
        on_delete=models.CASCADE,
        related_name='vat_records',
        verbose_name='Πελάτης'
    )

    # myDATA unique identifier
    mark = models.BigIntegerField(
        verbose_name='MARK',
        db_index=True,
        help_text='Μοναδικός αριθμός καταχώρησης myDATA'
    )

    # Basic info
    is_cancelled = models.BooleanField(
        verbose_name='Ακυρωμένο',
        default=False
    )

    issue_date = models.DateField(
        verbose_name='Ημερομηνία Έκδοσης',
        db_index=True
    )

    # Type of record
    rec_type = models.IntegerField(
        verbose_name='Τύπος',
        choices=REC_TYPE_CHOICES,
        db_index=True,
        help_text='1=Εκροές (έσοδα), 2=Εισροές (έξοδα)'
    )

    # Invoice type
    inv_type = models.CharField(
        verbose_name='Τύπος Παραστατικού',
        max_length=20,
        db_index=True,
        help_text='π.χ. 1.1, 2.1, 5.1, ΕΙΣΡΟΕΣ_362'
    )

    EXPENSE_CATEGORY_CHOICES = [
        ('', '-'),
        ('361', 'Εμπορεύματα & Α\' Ύλες'),
        ('362', 'Πάγια'),
        ('363', 'Λοιπές Δαπάνες'),
        ('364', 'Ενδοκοιν. Εμπορεύματα'),
        ('365', 'Ενδοκοιν. Πάγια'),
        ('366', 'Ενδοκοιν. Λοιπές Δαπάνες'),
    ]

    expense_category = models.CharField(
        verbose_name='Κατηγορία Δαπάνης',
        max_length=3,
        choices=EXPENSE_CATEGORY_CHOICES,
        blank=True,
        default='',
        db_index=True,
        help_text='Κωδικός εισροών ΑΑΔΕ (361-364)'
    )

    # VAT category
    vat_category = models.IntegerField(
        verbose_name='Κατηγορία ΦΠΑ',
        choices=VAT_CATEGORY_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(8)],
        db_index=True
    )

    vat_exemption_category = models.CharField(
        verbose_name='Κατηγορία Εξαίρεσης ΦΠΑ',
        max_length=50,
        blank=True,
        default=''
    )

    # Amounts
    net_value = models.DecimalField(
        verbose_name='Καθαρή Αξία',
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )

    vat_amount = models.DecimalField(
        verbose_name='Ποσό ΦΠΑ',
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )

    # Counterpart
    counter_vat_number = models.CharField(
        verbose_name='ΑΦΜ Αντισυμβαλλόμενου',
        max_length=20,
        blank=True,
        default='',
        db_index=True
    )

    # Optional amounts
    vat_offset_amount = models.DecimalField(
        verbose_name='Ποσό Συμψηφισμού ΦΠΑ',
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )

    deductions_amount = models.DecimalField(
        verbose_name='Ποσό Παρακρατήσεων',
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Metadata
    fetched_at = models.DateTimeField(
        verbose_name='Ημ/νία Λήψης',
        auto_now_add=True,
        help_text='Πότε τραβήχτηκε από το myDATA'
    )

    updated_at = models.DateTimeField(
        verbose_name='Ημ/νία Ενημέρωσης',
        auto_now=True
    )

    class Meta:
        verbose_name = 'Εγγραφή ΦΠΑ'
        verbose_name_plural = 'Εγγραφές ΦΠΑ'
        ordering = ['-issue_date', '-mark']
        unique_together = [['client', 'mark', 'expense_category']]
        indexes = [
            models.Index(fields=['client', 'issue_date']),
            models.Index(fields=['client', 'rec_type', 'issue_date']),
            models.Index(fields=['client', 'vat_category', 'issue_date']),
            models.Index(fields=['issue_date', 'rec_type']),
        ]

    def __str__(self):
        type_str = "Εκροή" if self.rec_type == 1 else "Εισροή"
        return f"{self.client.afm} | {type_str} | {self.issue_date} | {self.net_value}+{self.vat_amount}"

    # =========================================================================
    # PROPERTIES
    # =========================================================================

    @property
    def is_income(self) -> bool:
        """True αν είναι εκροή (έσοδο)."""
        return self.rec_type == 1

    @property
    def is_expense(self) -> bool:
        """True αν είναι εισροή (έξοδο)."""
        return self.rec_type == 2

    @property
    def gross_value(self) -> Decimal:
        """Συνολική αξία (καθαρή + ΦΠΑ)."""
        return self.net_value + self.vat_amount

    @property
    def vat_rate(self) -> int:
        """VAT rate as percentage."""
        rates = {1: 24, 2: 13, 3: 6, 4: 17, 5: 9, 6: 4, 7: 0, 8: 0}
        return rates.get(self.vat_category, 0)

    @property
    def vat_rate_display(self) -> str:
        """Human-readable VAT rate."""
        return f"{self.vat_rate}%" if self.vat_category < 8 else "Χωρίς ΦΠΑ"

    @property
    def period_year(self) -> int:
        """Year of issue_date."""
        return self.issue_date.year if self.issue_date else 0

    @property
    def period_month(self) -> int:
        """Month of issue_date."""
        return self.issue_date.month if self.issue_date else 0

    # =========================================================================
    # CLASS METHODS FOR QUERIES
    # =========================================================================

    @classmethod
    def get_period_summary(
        cls,
        client,
        year: int,
        month: int,
        rec_type: int = None
    ) -> dict:
        """
        Υπολογίζει summary για συγκεκριμένη περίοδο.

        Args:
            client: ClientProfile instance
            year: Έτος
            month: Μήνας
            rec_type: 1=Εκροές, 2=Εισροές, None=Όλα

        Returns:
            Dict με net_value, vat_amount, gross_value, count
        """
        from django.db.models import Sum, Count

        qs = cls.objects.filter(
            client=client,
            issue_date__year=year,
            issue_date__month=month,
            is_cancelled=False
        )

        if rec_type:
            qs = qs.filter(rec_type=rec_type)

        result = qs.aggregate(
            total_net=Sum('net_value'),
            total_vat=Sum('vat_amount'),
            record_count=Count('id')
        )

        return {
            'net_value': result['total_net'] or Decimal('0.00'),
            'vat_amount': result['total_vat'] or Decimal('0.00'),
            'gross_value': (result['total_net'] or Decimal('0.00')) +
                          (result['total_vat'] or Decimal('0.00')),
            'count': result['record_count'] or 0
        }

    @classmethod
    def get_period_by_category(
        cls,
        client,
        year: int,
        month: int,
        rec_type: int = None
    ) -> list:
        """
        Breakdown ανά κατηγορία ΦΠΑ για συγκεκριμένη περίοδο.

        Returns:
            List of dicts με vat_category, net_value, vat_amount, count
        """
        from django.db.models import Sum, Count

        qs = cls.objects.filter(
            client=client,
            issue_date__year=year,
            issue_date__month=month,
            is_cancelled=False
        )

        if rec_type:
            qs = qs.filter(rec_type=rec_type)

        return list(
            qs.values('vat_category')
            .annotate(
                total_net=Sum('net_value'),
                total_vat=Sum('vat_amount'),
                record_count=Count('id')
            )
            .order_by('vat_category')
        )

    @classmethod
    def get_date_range_summary(
        cls,
        client,
        date_from,
        date_to,
        rec_type: int = None
    ) -> dict:
        """
        Υπολογίζει summary για εύρος ημερομηνιών.

        Args:
            client: ClientProfile instance
            date_from: Από ημερομηνία
            date_to: Έως ημερομηνία
            rec_type: 1=Εκροές, 2=Εισροές, None=Όλα

        Returns:
            Dict με net_value, vat_amount, gross_value, count
        """
        from django.db.models import Sum, Count

        qs = cls.objects.filter(
            client=client,
            issue_date__gte=date_from,
            issue_date__lte=date_to,
            is_cancelled=False
        )

        if rec_type:
            qs = qs.filter(rec_type=rec_type)

        result = qs.aggregate(
            total_net=Sum('net_value'),
            total_vat=Sum('vat_amount'),
            record_count=Count('id')
        )

        return {
            'net_value': result['total_net'] or Decimal('0.00'),
            'vat_amount': result['total_vat'] or Decimal('0.00'),
            'gross_value': (result['total_net'] or Decimal('0.00')) +
                          (result['total_vat'] or Decimal('0.00')),
            'count': result['record_count'] or 0
        }

    @classmethod
    def get_date_range_by_category(
        cls,
        client,
        date_from,
        date_to,
        rec_type: int = None
    ) -> list:
        """
        Breakdown ανά κατηγορία ΦΠΑ για εύρος ημερομηνιών.

        Returns:
            List of dicts με vat_category, net_value, vat_amount, count
        """
        from django.db.models import Sum, Count

        qs = cls.objects.filter(
            client=client,
            issue_date__gte=date_from,
            issue_date__lte=date_to,
            is_cancelled=False
        )

        if rec_type:
            qs = qs.filter(rec_type=rec_type)

        return list(
            qs.values('vat_category')
            .annotate(
                total_net=Sum('net_value'),
                total_vat=Sum('vat_amount'),
                record_count=Count('id')
            )
            .order_by('vat_category')
        )


# =============================================================================
# VAT SYNC LOG
# =============================================================================

class VATSyncLog(models.Model):
    """
    Log για VAT synchronization operations.

    Καταγράφει κάθε VAT sync operation με αποτελέσματα.
    Ξεχωριστό από inventory.MyDataSyncLog που είναι για invoices.
    """

    SYNC_TYPE_CHOICES = [
        ('VAT_INFO', 'VAT Info Sync'),
        ('INCOME', 'Income Sync'),
        ('EXPENSES', 'Expenses Sync'),
        ('VERIFY', 'Credentials Verification'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Σε εξέλιξη'),
        ('SUCCESS', 'Επιτυχία'),
        ('PARTIAL', 'Μερική επιτυχία'),
        ('ERROR', 'Σφάλμα'),
    ]

    # Link to client (optional - for client-specific syncs)
    client = models.ForeignKey(
        'accounting.ClientProfile',
        on_delete=models.CASCADE,
        related_name='mydata_sync_logs',
        verbose_name='Πελάτης',
        null=True,
        blank=True
    )

    # Sync details
    sync_type = models.CharField(
        verbose_name='Τύπος Sync',
        max_length=20,
        choices=SYNC_TYPE_CHOICES
    )

    status = models.CharField(
        verbose_name='Κατάσταση',
        max_length=10,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    # Date range that was synced
    date_from = models.DateField(
        verbose_name='Από Ημερομηνία',
        null=True,
        blank=True
    )

    date_to = models.DateField(
        verbose_name='Έως Ημερομηνία',
        null=True,
        blank=True
    )

    # Timestamps
    started_at = models.DateTimeField(
        verbose_name='Έναρξη',
        auto_now_add=True
    )

    completed_at = models.DateTimeField(
        verbose_name='Ολοκλήρωση',
        null=True,
        blank=True
    )

    # Statistics
    records_fetched = models.IntegerField(
        verbose_name='Εγγραφές που τραβήχτηκαν',
        default=0
    )

    records_created = models.IntegerField(
        verbose_name='Νέες εγγραφές',
        default=0
    )

    records_updated = models.IntegerField(
        verbose_name='Ενημερωμένες εγγραφές',
        default=0
    )

    records_skipped = models.IntegerField(
        verbose_name='Παραλειφθείσες',
        default=0
    )

    records_failed = models.IntegerField(
        verbose_name='Αποτυχίες',
        default=0
    )

    # Error details
    error_message = models.TextField(
        verbose_name='Μήνυμα Σφάλματος',
        blank=True,
        default=''
    )

    # Additional data (JSON)
    details = models.JSONField(
        verbose_name='Λεπτομέρειες',
        null=True,
        blank=True,
        help_text='Extra details σε JSON format'
    )

    class Meta:
        verbose_name = 'VAT Sync Log'
        verbose_name_plural = 'VAT Sync Logs'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['client', '-started_at']),
            models.Index(fields=['sync_type', '-started_at']),
            models.Index(fields=['status', '-started_at']),
        ]

    def __str__(self):
        client_str = self.client.afm if self.client else 'Global'
        return f"{client_str} | {self.get_sync_type_display()} | {self.status} | {self.started_at}"

    @property
    def duration_seconds(self) -> int:
        """Duration in seconds."""
        if self.completed_at and self.started_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return 0

    @property
    def duration_display(self) -> str:
        """Human-readable duration."""
        seconds = self.duration_seconds
        if seconds < 60:
            return f"{seconds}s"
        minutes = seconds // 60
        remaining = seconds % 60
        return f"{minutes}m {remaining}s"

    def mark_completed(self, status: str = 'SUCCESS'):
        """Mark sync as completed."""
        self.status = status
        self.completed_at = timezone.now()
        self.save()

    def mark_failed(self, error: str):
        """Mark sync as failed."""
        self.status = 'ERROR'
        self.error_message = error[:2000]  # Limit error length
        self.completed_at = timezone.now()
        self.save()

    def increment_stats(
        self,
        fetched: int = 0,
        created: int = 0,
        updated: int = 0,
        skipped: int = 0,
        failed: int = 0
    ):
        """Increment statistics."""
        self.records_fetched += fetched
        self.records_created += created
        self.records_updated += updated
        self.records_skipped += skipped
        self.records_failed += failed
        self.save(update_fields=[
            'records_fetched', 'records_created', 'records_updated',
            'records_skipped', 'records_failed'
        ])


# =============================================================================
# VAT PERIOD RESULT - Υπολογισμός ΦΠΑ ανά περίοδο
# =============================================================================

class VATPeriodResult(models.Model):
    """
    Αποτέλεσμα ΦΠΑ για συγκεκριμένη περίοδο (μήνα ή τρίμηνο).

    Παρακολουθεί:
    - ΦΠΑ Εκροών/Εισροών από τα VATRecord
    - Πιστωτικό υπόλοιπο από προηγούμενη περίοδο
    - Τελικό αποτέλεσμα (απόδοση ή μεταφορά πιστωτικού)
    - Κλείδωμα περιόδου μετά την υποβολή
    """

    PERIOD_TYPE_CHOICES = [
        ('monthly', 'Μηνιαίο'),
        ('quarterly', 'Τριμηνιαίο'),
    ]

    # Link to client
    client = models.ForeignKey(
        'accounting.ClientProfile',
        on_delete=models.CASCADE,
        related_name='vat_period_results',
        verbose_name='Πελάτης'
    )

    # Period definition
    period_type = models.CharField(
        verbose_name='Τύπος Περιόδου',
        max_length=10,
        choices=PERIOD_TYPE_CHOICES,
        default='monthly'
    )

    year = models.IntegerField(
        verbose_name='Έτος',
        validators=[MinValueValidator(2020), MaxValueValidator(2100)]
    )

    # For monthly: 1-12, for quarterly: 1-4
    period = models.IntegerField(
        verbose_name='Περίοδος',
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text='Μήνας (1-12) ή Τρίμηνο (1-4)'
    )

    # Calculated VAT values (from VATRecords)
    vat_output = models.DecimalField(
        verbose_name='ΦΠΑ Εκροών',
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Σύνολο ΦΠΑ από πωλήσεις'
    )

    vat_input = models.DecimalField(
        verbose_name='ΦΠΑ Εισροών',
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Σύνολο ΦΠΑ από αγορές'
    )

    # Difference before credit adjustment
    vat_difference = models.DecimalField(
        verbose_name='Διαφορά ΦΠΑ',
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Εκροές - Εισροές'
    )

    # Credit handling
    previous_credit = models.DecimalField(
        verbose_name='Πιστωτικό Προηγούμενης',
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Πιστωτικό υπόλοιπο από προηγούμενη περίοδο'
    )

    # Final result (positive = pay, negative = credit to next)
    final_result = models.DecimalField(
        verbose_name='Τελικό Αποτέλεσμα',
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Θετικό = προς απόδοση, Αρνητικό = πιστωτικό'
    )

    # Credit to carry forward
    credit_to_next = models.DecimalField(
        verbose_name='Πιστωτικό προς Μεταφορά',
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Πιστωτικό που μεταφέρεται στην επόμενη περίοδο'
    )

    # Lock status
    is_locked = models.BooleanField(
        verbose_name='Κλειδωμένο',
        default=False,
        help_text='True αν η περίοδος έχει υποβληθεί/κλειδωθεί'
    )

    locked_at = models.DateTimeField(
        verbose_name='Ημ/νία Κλειδώματος',
        null=True,
        blank=True
    )

    locked_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='locked_vat_periods',
        verbose_name='Κλειδώθηκε από'
    )

    # Sync tracking
    last_calculated_at = models.DateTimeField(
        verbose_name='Τελευταίος Υπολογισμός',
        null=True,
        blank=True
    )

    months_synced = models.JSONField(
        verbose_name='Συγχρονισμένοι Μήνες',
        default=list,
        blank=True,
        help_text='Λίστα μηνών που έχουν synced data'
    )

    # Notes
    notes = models.TextField(
        verbose_name='Σημειώσεις',
        blank=True,
        default=''
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Δημιουργία')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Ενημέρωση')

    class Meta:
        verbose_name = 'Αποτέλεσμα ΦΠΑ Περιόδου'
        verbose_name_plural = 'Αποτελέσματα ΦΠΑ Περιόδων'
        ordering = ['-year', '-period']
        unique_together = [['client', 'period_type', 'year', 'period']]
        indexes = [
            models.Index(fields=['client', 'year', 'period']),
            models.Index(fields=['client', 'period_type', '-year', '-period']),
            models.Index(fields=['is_locked', '-year', '-period']),
        ]

    def __str__(self):
        period_str = self.get_period_display()
        status = "🔒" if self.is_locked else "📝"
        return f"{self.client.eponimia} | {period_str} | {self.final_result}€ {status}"

    # =========================================================================
    # PROPERTIES
    # =========================================================================

    def get_period_display(self) -> str:
        """Human-readable period string."""
        if self.period_type == 'monthly':
            months = ['', 'Ιαν', 'Φεβ', 'Μαρ', 'Απρ', 'Μαι', 'Ιουν',
                     'Ιουλ', 'Αυγ', 'Σεπ', 'Οκτ', 'Νοε', 'Δεκ']
            return f"{months[self.period]} {self.year}"
        else:
            return f"Q{self.period} {self.year}"

    @property
    def is_payable(self) -> bool:
        """True αν το τελικό αποτέλεσμα είναι προς απόδοση."""
        return self.final_result > 0

    @property
    def is_credit(self) -> bool:
        """True αν το τελικό αποτέλεσμα είναι πιστωτικό."""
        return self.final_result < 0 or self.credit_to_next > 0

    @property
    def months_in_period(self) -> list:
        """Επιστρέφει τους μήνες που ανήκουν σε αυτή την περίοδο."""
        if self.period_type == 'monthly':
            return [self.period]
        else:
            # Quarterly: Q1=1,2,3  Q2=4,5,6  Q3=7,8,9  Q4=10,11,12
            start_month = (self.period - 1) * 3 + 1
            return [start_month, start_month + 1, start_month + 2]

    @property
    def period_start_date(self):
        """First day of the period."""
        from datetime import date
        first_month = self.months_in_period[0]
        return date(self.year, first_month, 1)

    @property
    def period_end_date(self):
        """Last day of the period."""
        from datetime import date
        import calendar
        last_month = self.months_in_period[-1]
        last_day = calendar.monthrange(self.year, last_month)[1]
        return date(self.year, last_month, last_day)

    # =========================================================================
    # CALCULATION METHODS
    # =========================================================================

    def calculate_from_records(self, save: bool = True) -> dict:
        """
        Υπολογίζει τα ποσά ΦΠΑ από τα VATRecords.

        Returns:
            Dict με τα υπολογισμένα ποσά
        """
        from django.db.models import Sum

        if self.is_locked:
            raise ValidationError("Δεν μπορείτε να επανυπολογίσετε κλειδωμένη περίοδο")

        months = self.months_in_period

        # Query VATRecords for this period
        records = VATRecord.objects.filter(
            client=self.client,
            issue_date__year=self.year,
            issue_date__month__in=months,
            is_cancelled=False
        )

        # Calculate output VAT (εκροές = rec_type 1)
        output_result = records.filter(rec_type=1).aggregate(
            total=Sum('vat_amount')
        )
        self.vat_output = output_result['total'] or Decimal('0.00')

        # Calculate input VAT (εισροές = rec_type 2)
        input_result = records.filter(rec_type=2).aggregate(
            total=Sum('vat_amount')
        )
        self.vat_input = input_result['total'] or Decimal('0.00')

        # Calculate difference
        self.vat_difference = self.vat_output - self.vat_input

        # Calculate final result with previous credit
        result_with_credit = self.vat_difference - self.previous_credit

        if result_with_credit >= 0:
            # Χρωστάμε
            self.final_result = result_with_credit
            self.credit_to_next = Decimal('0.00')
        else:
            # Πιστωτικό - μεταφέρεται
            self.final_result = Decimal('0.00')
            self.credit_to_next = abs(result_with_credit)

        self.last_calculated_at = timezone.now()

        if save:
            self.save()

        return {
            'vat_output': self.vat_output,
            'vat_input': self.vat_input,
            'vat_difference': self.vat_difference,
            'previous_credit': self.previous_credit,
            'final_result': self.final_result,
            'credit_to_next': self.credit_to_next,
        }

    def get_previous_period(self):
        """Βρίσκει την προηγούμενη περίοδο (αν υπάρχει)."""
        if self.period_type == 'monthly':
            if self.period == 1:
                prev_year = self.year - 1
                prev_period = 12
            else:
                prev_year = self.year
                prev_period = self.period - 1
        else:  # quarterly
            if self.period == 1:
                prev_year = self.year - 1
                prev_period = 4
            else:
                prev_year = self.year
                prev_period = self.period - 1

        return VATPeriodResult.objects.filter(
            client=self.client,
            period_type=self.period_type,
            year=prev_year,
            period=prev_period
        ).first()

    def inherit_credit_from_previous(self, save: bool = True):
        """
        Παίρνει το πιστωτικό από την προηγούμενη περίοδο.

        Αν δεν υπάρχει προηγούμενη περίοδος, ελέγχει αν υπάρχει
        αρχικό πιστωτικό στα credentials του πελάτη.
        """
        if self.is_locked:
            raise ValidationError("Δεν μπορείτε να τροποποιήσετε κλειδωμένη περίοδο")

        previous = self.get_previous_period()
        if previous and previous.credit_to_next > 0:
            self.previous_credit = previous.credit_to_next
        else:
            # Check for initial credit from client credentials
            try:
                creds = self.client.mydata_credentials
                if creds.initial_credit_balance > 0:
                    # Check if this is the first period or the designated period
                    should_apply = False

                    if creds.initial_credit_period_year and creds.initial_credit_period:
                        # Apply only to specific period
                        if (self.year == creds.initial_credit_period_year and
                            self.period == creds.initial_credit_period):
                            should_apply = True
                    else:
                        # Apply to first period (no previous exists)
                        if previous is None:
                            should_apply = True

                    if should_apply:
                        self.previous_credit = creds.initial_credit_balance
            except MyDataCredentials.DoesNotExist:
                pass

        if save and self.previous_credit > 0:
            self.save(update_fields=['previous_credit', 'updated_at'])

        return self.previous_credit

    def lock(self, user=None):
        """Κλειδώνει την περίοδο."""
        if self.is_locked:
            return False

        self.is_locked = True
        self.locked_at = timezone.now()
        self.locked_by = user
        self.save(update_fields=['is_locked', 'locked_at', 'locked_by', 'updated_at'])
        return True

    def unlock(self, user=None):
        """Ξεκλειδώνει την περίοδο (μόνο για admin)."""
        if not self.is_locked:
            return False

        self.is_locked = False
        self.locked_at = None
        self.locked_by = None
        self.save(update_fields=['is_locked', 'locked_at', 'locked_by', 'updated_at'])
        return True

    @classmethod
    def get_or_create_for_period(
        cls,
        client,
        period_type: str,
        year: int,
        period: int
    ):
        """
        Δημιουργεί ή επιστρέφει VATPeriodResult για συγκεκριμένη περίοδο.
        Αυτόματα παίρνει το πιστωτικό από την προηγούμενη.
        """
        obj, created = cls.objects.get_or_create(
            client=client,
            period_type=period_type,
            year=year,
            period=period
        )

        if created:
            # Inherit credit from previous period
            obj.inherit_credit_from_previous(save=True)

        return obj, created
