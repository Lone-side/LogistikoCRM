# inventory/models.py
"""
Inventory & Invoicing Models για Django CRM
Συμβατά με myDATA integration
"""

from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone


# =====================================================
# ΒΑΣΙΚΕΣ ΕΠΙΛΟΓΕΣ
# =====================================================

UNIT_CHOICES = [
    ('piece', 'Τεμάχια'),
    ('m3', 'Κυβικά Μέτρα (m³)'),
    ('m2', 'Τετραγωνικά Μέτρα (m²)'),
    ('m', 'Μέτρα'),
    ('kg', 'Κιλά'),
    ('ton', 'Τόνοι'),
    ('liter', 'Λίτρα'),
]

INVOICE_TYPE_CHOICES = [
    ('1.1', 'Τιμολόγιο Πώλησης'),
    ('1.2', 'Τιμολόγιο Πώλησης / Ενδοκοινοτικές Παραδόσεις'),
    ('1.3', 'Τιμολόγιο Πώλησης / Παραδόσεις Τρίτων Χωρών'),
    ('2.1', 'Τιμολόγιο Παροχής Υπηρεσιών'),
    ('5.1', 'Πιστωτικό Τιμολόγιο / Συσχετιζόμενο'),
    ('5.2', 'Πιστωτικό Τιμολόγιο / Μη Συσχετιζόμενο'),
]

VAT_CATEGORY_CHOICES = [
    (1, 'ΦΠΑ 24%'),
    (2, 'ΦΠΑ 13%'),
    (3, 'ΦΠΑ 6%'),
    (4, 'ΦΠΑ 17%'),
    (5, 'ΦΠΑ 9%'),
    (6, 'ΦΠΑ 4%'),
    (7, 'Χωρίς ΦΠΑ'),
]

MOVEMENT_TYPE_CHOICES = [
    ('IN', 'Εισαγωγή'),
    ('OUT', 'Εξαγωγή'),
    ('ADJ', 'Διόρθωση'),
]


# =====================================================
# ΚΑΤΗΓΟΡΙΕΣ ΠΡΟΪΟΝΤΩΝ
# =====================================================

class ProductCategory(models.Model):
    """Κατηγορίες προϊόντων (π.χ. Ξυλεία Καστανιάς, Ξυλεία Ελάτης)"""
    name = models.CharField('Όνομα Κατηγορίας', max_length=100)
    description = models.TextField('Περιγραφή', blank=True)
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        verbose_name='Γονική Κατηγορία'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Κατηγορία Προϊόντος'
        verbose_name_plural = 'Κατηγορίες Προϊόντων'
        ordering = ['name']
    
    def __str__(self):
        return self.name


# =====================================================
# ΠΡΟΪΟΝΤΑ
# =====================================================

class Product(models.Model):
    """Προϊόντα αποθήκης"""
    
    # Βασικά στοιχεία
    code = models.CharField('Κωδικός', max_length=50, unique=True)
    name = models.CharField('Όνομα Προϊόντος', max_length=200)
    description = models.TextField('Περιγραφή', blank=True)
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Κατηγορία'
    )
    
    # Μονάδα μέτρησης
    unit = models.CharField('Μονάδα Μέτρησης', max_length=20, choices=UNIT_CHOICES)
    
    # Stock
    current_stock = models.DecimalField(
        'Τρέχον Απόθεμα',
        max_digits=12,
        decimal_places=3,
        default=0,
        validators=[MinValueValidator(Decimal('0.000'))]
    )
    min_stock = models.DecimalField(
        'Ελάχιστο Απόθεμα (Alert)',
        max_digits=12,
        decimal_places=3,
        default=0,
        validators=[MinValueValidator(Decimal('0.000'))]
    )
    
    # Τιμές
    purchase_price = models.DecimalField(
        'Τιμή Αγοράς',
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    sale_price = models.DecimalField(
        'Τιμή Πώλησης',
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # ΦΠΑ
    vat_category = models.IntegerField(
        'Κατηγορία ΦΠΑ',
        choices=VAT_CATEGORY_CHOICES,
        default=1  # 24%
    )
    
    # Metadata
    active = models.BooleanField('Ενεργό', default=True)
    notes = models.TextField('Σημειώσεις', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Προϊόν'
        verbose_name_plural = 'Προϊόντα'
        ordering = ['code']
        # Ονόματα ίδια με το migration 9999_add_performance_indexes
        indexes = [
            models.Index(fields=['active', 'code'], name='prod_active_code_idx'),
            models.Index(fields=['category', 'active'], name='prod_cat_active_idx'),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def is_low_stock(self):
        """Έλεγχος αν το απόθεμα είναι χαμηλό"""
        return self.current_stock <= self.min_stock
    
    @property
    def stock_value(self):
        """Αξία τρέχοντος αποθέματος (σε τιμή αγοράς)"""
        return self.current_stock * self.purchase_price
    
    def get_vat_rate(self):
        """Επιστρέφει το ποσοστό ΦΠΑ"""
        vat_rates = {1: 24, 2: 13, 3: 6, 4: 17, 5: 9, 6: 4, 7: 0}
        return vat_rates.get(self.vat_category, 24)


# =====================================================
# ΚΙΝΗΣΕΙΣ ΑΠΟΘΗΚΗΣ
# =====================================================

class StockMovement(models.Model):
    """Κινήσεις αποθήκης (εισαγωγές/εξαγωγές)"""
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name='Προϊόν',
        related_name='movements'
    )
    
    # Τύπος κίνησης
    movement_type = models.CharField(
        'Τύπος Κίνησης',
        max_length=3,
        choices=MOVEMENT_TYPE_CHOICES
    )
    
    # Ποσότητα
    quantity = models.DecimalField(
        'Ποσότητα',
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))]
    )
    
    # Τιμή μονάδας (για εισαγωγές)
    unit_cost = models.DecimalField(
        'Κόστος Μονάδας',
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Ημερομηνία
    date = models.DateTimeField('Ημερομηνία', default=timezone.now)
    
    # Συσχέτιση με παραστατικό (αν υπάρχει)
    invoice = models.ForeignKey(
        'Invoice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Παραστατικό',
        related_name='stock_movements'
    )
    
    # Supplier ή Customer
    counterpart = models.ForeignKey(
        'accounting.ClientProfile',
        on_delete=models.PROTECT,
        null=True,                      # ← ΠΡΟΣΘΗΚΗ!
        blank=True,                     # ← ΠΡΟΣΘΗΚΗ!
        verbose_name='Πελάτης/Προμηθευτής',
        related_name='client_invoices'  # ← ΑΛΛΑΓΗ!
)    # Σημειώσεις
    notes = models.TextField('Σημειώσεις', blank=True)
    
    # Metadata
    created_by = models.CharField('Δημιουργήθηκε από', max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Κίνηση Αποθήκης'
        verbose_name_plural = 'Κινήσεις Αποθήκης'
        ordering = ['-date']
        # Ονόματα ίδια με το migration 9999_add_performance_indexes
        indexes = [
            models.Index(fields=['product', 'date'], name='stock_prod_date_idx'),
            models.Index(fields=['movement_type', 'date'], name='stock_type_date_idx'),
            models.Index(fields=['invoice'], name='stock_invoice_idx'),
        ]
    
    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.product.code} - {self.quantity} {self.product.unit}"
    
    def save(self, *args, **kwargs):
        """
        Override save για auto-update του stock
        SECURITY FIX: Use transaction and select_for_update to prevent race conditions
        """
        from django.db import transaction

        with transaction.atomic():
            is_new = self.pk is None
            old_movement = None if is_new else StockMovement.objects.get(pk=self.pk)

            # Lock the product row to prevent concurrent updates (RACE CONDITION FIX)
            product = Product.objects.select_for_update().get(pk=self.product.pk)

            super().save(*args, **kwargs)

            # Update product stock atomically
            if is_new:
                if self.movement_type == 'IN':
                    product.current_stock += self.quantity
                elif self.movement_type == 'OUT':
                    product.current_stock -= self.quantity
                elif self.movement_type == 'ADJ':
                    # Για adjustment, η quantity είναι η διαφορά
                    product.current_stock += self.quantity

                product.save()
            else:
                # Undo old movement
                if old_movement.movement_type == 'IN':
                    product.current_stock -= old_movement.quantity
                elif old_movement.movement_type == 'OUT':
                    product.current_stock += old_movement.quantity

                # Apply new movement
                if self.movement_type == 'IN':
                    product.current_stock += self.quantity
                elif self.movement_type == 'OUT':
                    product.current_stock -= self.quantity

                product.save()
    
    @property
    def total_value(self):
        """Συνολική αξία κίνησης"""
        if self.unit_cost:
            return self.quantity * self.unit_cost
        return Decimal('0.00')


# =====================================================
# ΤΙΜΟΛΟΓΙΑ
# =====================================================

class Invoice(models.Model):
    """Τιμολόγια (εισερχόμενα & εξερχόμενα)"""
    
    # Στοιχεία παραστατικού
    series = models.CharField('Σειρά', max_length=10)
    number = models.CharField('Αριθμός', max_length=50)
    invoice_type = models.CharField(
        'Τύπος Παραστατικού',
        max_length=10,
        choices=INVOICE_TYPE_CHOICES
    )
    
    # Ημερομηνίες
    issue_date = models.DateField('Ημερομηνία Έκδοσης', default=timezone.now)
    
    # Αντισυμβαλλόμενος
    counterpart = models.ForeignKey(
        'accounting.ClientProfile',
        on_delete=models.PROTECT,
        verbose_name='Πελάτης/Προμηθευτής',
        related_name='invoices'
    )
    counterpart_vat = models.CharField('ΑΦΜ Αντισυμβαλλόμενου', max_length=20)
    counterpart_name = models.CharField('Επωνυμία Αντισυμβαλλόμενου', max_length=200)
    
    # Κατεύθυνση (incoming/outgoing)
    is_outgoing = models.BooleanField('Εξερχόμενο', default=True)
    
    # Ποσά
    total_net = models.DecimalField(
        'Σύνολο Καθαρής Αξίας',
        max_digits=12,
        decimal_places=2,
        default=0
    )
    total_vat = models.DecimalField(
        'Σύνολο ΦΠΑ',
        max_digits=12,
        decimal_places=2,
        default=0
    )
    total_gross = models.DecimalField(
        'Σύνολο Τελικό',
        max_digits=12,
        decimal_places=2,
        default=0
    )
    
    # myDATA integration
    mydata_mark = models.BigIntegerField('MARK myDATA', null=True, blank=True, unique=True)
    mydata_uid = models.CharField('UID myDATA', max_length=100, blank=True)
    mydata_sent = models.BooleanField('Απεσταλμένο στο myDATA', default=False)
    mydata_sent_at = models.DateTimeField('Ημ/νία Αποστολής myDATA', null=True, blank=True)
    # Ακύρωση στο myDATA (δομημένα — όχι μόνο σημείωση)
    mydata_cancelled = models.BooleanField('Ακυρωμένο στο myDATA', default=False)
    mydata_cancellation_mark = models.BigIntegerField(
        'MARK Ακύρωσης', null=True, blank=True
    )
    mydata_cancelled_at = models.DateTimeField(
        'Ημ/νία Ακύρωσης myDATA', null=True, blank=True
    )
    # Για πιστωτικά 5.1: MARK του συσχετιζόμενου αρχικού παραστατικού
    correlated_mark = models.BigIntegerField(
        'MARK Συσχετιζόμενου', null=True, blank=True,
        help_text='Υποχρεωτικό για πιστωτικά τύπου 5.1'
    )
    
    # Metadata
    notes = models.TextField('Σημειώσεις', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Τιμολόγιο'
        verbose_name_plural = 'Τιμολόγια'
        ordering = ['-issue_date', '-number']
        unique_together = [['series', 'number']]
        # Ονόματα ίδια με το migration 9999_add_performance_indexes
        indexes = [
            models.Index(fields=['issue_date', 'counterpart'], name='inv_issue_cpty_idx'),
            models.Index(fields=['mydata_mark'], name='inv_mydata_idx'),
            models.Index(fields=['is_outgoing', 'issue_date'], name='inv_outgoing_date_idx'),
            models.Index(fields=['counterpart_vat'], name='inv_cpty_vat_idx'),
            models.Index(fields=['-issue_date'], name='inv_date_desc_idx'),
        ]
    
    def __str__(self):
        return f"{self.series}/{self.number} - {self.counterpart_name} - {self.total_gross}€"
    
    def calculate_totals(self):
        """Υπολογισμός συνόλων από τις γραμμές"""
        items = self.items.all()
        self.total_net = sum(item.net_value for item in items)
        self.total_vat = sum(item.vat_amount for item in items)
        self.total_gross = self.total_net + self.total_vat
        self.save()


class InvoiceItem(models.Model):
    """Γραμμές τιμολογίου"""
    
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        verbose_name='Τιμολόγιο',
        related_name='items'
    )
    
    line_number = models.IntegerField('Αριθμός Γραμμής')
    
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        verbose_name='Προϊόν',
        null=True,
        blank=True
    )
    
    description = models.CharField('Περιγραφή', max_length=300)
    quantity = models.DecimalField(
        'Ποσότητα',
        max_digits=12,
        decimal_places=3
    )
    unit = models.CharField('Μονάδα', max_length=20, choices=UNIT_CHOICES)
    
    unit_price = models.DecimalField(
        'Τιμή Μονάδας',
        max_digits=10,
        decimal_places=2
    )
    
    net_value = models.DecimalField(
        'Καθαρή Αξία',
        max_digits=12,
        decimal_places=2
    )
    
    vat_category = models.IntegerField(
        'Κατηγορία ΦΠΑ',
        choices=VAT_CATEGORY_CHOICES
    )
    vat_exemption_category = models.IntegerField(
        'Κατηγορία Εξαίρεσης ΦΠΑ',
        null=True, blank=True,
        help_text='Υποχρεωτικό όταν η κατηγορία ΦΠΑ είναι 7 (Χωρίς ΦΠΑ) — κωδικοί ΑΑΔΕ 1-31'
    )
    vat_amount = models.DecimalField(
        'Ποσό ΦΠΑ',
        max_digits=12,
        decimal_places=2
    )
    
    class Meta:
        verbose_name = 'Γραμμή Τιμολογίου'
        verbose_name_plural = 'Γραμμές Τιμολογίου'
        ordering = ['line_number']
    
    def __str__(self):
        return f"Γραμμή {self.line_number} - {self.description}"
    
    def save(self, *args, **kwargs):
        """Auto-calculate values"""
        self.net_value = self.quantity * self.unit_price
        
        # Calculate VAT
        vat_rates = {1: 24, 2: 13, 3: 6, 4: 17, 5: 9, 6: 4, 7: 0}
        vat_rate = vat_rates.get(self.vat_category, 24)
        self.vat_amount = (self.net_value * vat_rate) / 100
        
        super().save(*args, **kwargs)
        
        # Update invoice totals
        self.invoice.calculate_totals()


# =====================================================
# MYDATA SYNC LOG
# =====================================================

class MyDataSyncLog(models.Model):
    """Log για myDATA synchronization"""
    
    SYNC_TYPE_CHOICES = [
        ('PULL_TRANSMITTED', 'Λήψη Εκδοθέντων'),
        ('PULL_RECEIVED', 'Λήψη Ληφθέντων'),
        ('PUSH_INVOICE', 'Αποστολή Παραστατικού'),
        ('CANCEL_INVOICE', 'Ακύρωση Παραστατικού'),
    ]
    
    STATUS_CHOICES = [
        ('SUCCESS', 'Επιτυχία'),
        ('ERROR', 'Σφάλμα'),
        ('PENDING', 'Σε εκκρεμότητα'),
    ]
    
    sync_type = models.CharField('Τύπος Sync', max_length=20, choices=SYNC_TYPE_CHOICES)
    status = models.CharField('Κατάσταση', max_length=10, choices=STATUS_CHOICES)
    
    started_at = models.DateTimeField('Έναρξη', auto_now_add=True)
    completed_at = models.DateTimeField('Ολοκλήρωση', null=True, blank=True)
    
    records_processed = models.IntegerField('Εγγραφές που επεξεργάστηκαν', default=0)
    records_created = models.IntegerField('Νέες Εγγραφές', default=0)
    records_updated = models.IntegerField('Ενημερωμένες Εγγραφές', default=0)
    records_failed = models.IntegerField('Αποτυχίες', default=0)
    
    error_message = models.TextField('Μήνυμα Σφάλματος', blank=True)
    details = models.JSONField('Λεπτομέρειες', null=True, blank=True)
    
    class Meta:
        verbose_name = 'myDATA Sync Log'
        verbose_name_plural = 'myDATA Sync Logs'
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.get_sync_type_display()} - {self.status} - {self.started_at}"
