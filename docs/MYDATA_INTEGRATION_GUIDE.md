# myDATA Integration - Setup Guide

## 📋 Τι έχεις τώρα:

1. **mydata_client.py** - API Client για myDATA
2. **inventory_models.py** - Django models (Product, Invoice, Stock)
3. **mydata_services.py** - Service layer (sync logic)

---

## 🚀 Setup Instructions

### ΒΗΜΑ 1: Προσθήκη στο Django Project

```bash
# Στο root directory του Django project σου
cd /path/to/your/django/project

# Δημιούργησε τα νέα apps
python manage.py startapp inventory
python manage.py startapp mydata
```

### ΒΗΜΑ 2: Copy τα αρχεία

```bash
# Copy models
cp inventory_models.py inventory/models.py

# Copy myDATA client & service
cp mydata_client.py mydata/client.py
cp mydata_services.py mydata/services.py
```

### ΒΗΜΑ 3: Settings Configuration

Άνοιξε το `settings.py` και πρόσθεσε:

```python
# settings.py

# Installed Apps
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Your existing apps
    'accounting',
    
    # NEW APPS
    'inventory',      # ← ΠΡΟΣΘΗΚΗ
    'mydata',         # ← ΠΡΟΣΘΗΚΗ
]

# myDATA Configuration
MYDATA_USER_ID = "099999999"  # ← ΑΛΛΑΞΕ με το ΑΦΜ σου
MYDATA_SUBSCRIPTION_KEY = "your-subscription-key-here"  # ← ΑΛΛΑΞΕ
MYDATA_IS_SANDBOX = True  # True για testing, False για production

# Logging (optional αλλά χρήσιμο)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'mydata.log',
        },
    },
    'loggers': {
        'mydata': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
    },
}
```

### ΒΗΜΑ 4: URLs Configuration

Δημιούργησε `inventory/urls.py`:

```python
# inventory/urls.py
from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # TODO: Θα τα φτιάξουμε μετά
]
```

Και ενημέρωσε το `project/urls.py`:

```python
# project/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounting/', include('accounting.urls')),
    path('inventory/', include('inventory.urls')),  # ← ΠΡΟΣΘΗΚΗ
]
```

### ΒΗΜΑ 5: Database Migration

```bash
# Δημιουργία migrations
python manage.py makemigrations inventory
python manage.py makemigrations mydata

# Εφαρμογή migrations
python manage.py migrate
```

### ΒΗΜΑ 6: Django Admin Setup

Δημιούργησε `inventory/admin.py`:

```python
# inventory/admin.py
from django.contrib import admin
from .models import (
    ProductCategory, Product, StockMovement,
    Invoice, InvoiceItem, MyDataSyncLog
)

@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'created_at']
    search_fields = ['name']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'name', 'category', 'current_stock',
        'unit', 'purchase_price', 'sale_price', 'active'
    ]
    list_filter = ['category', 'active', 'unit']
    search_fields = ['code', 'name']
    list_editable = ['active']
    
    fieldsets = (
        ('Βασικά Στοιχεία', {
            'fields': ('code', 'name', 'description', 'category', 'active')
        }),
        ('Απόθεμα', {
            'fields': ('unit', 'current_stock', 'min_stock')
        }),
        ('Τιμές', {
            'fields': ('purchase_price', 'sale_price', 'vat_category')
        }),
        ('Σημειώσεις', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = [
        'date', 'product', 'movement_type', 'quantity',
        'unit_cost', 'counterpart', 'invoice'
    ]
    list_filter = ['movement_type', 'date']
    search_fields = ['product__name', 'product__code']
    date_hierarchy = 'date'
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing
            return ['product', 'movement_type', 'quantity']
        return []

class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    fields = ['line_number', 'product', 'description', 'quantity', 'unit', 'unit_price', 'vat_category']

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        'series', 'number', 'issue_date', 'counterpart_name',
        'total_gross', 'is_outgoing', 'mydata_sent'
    ]
    list_filter = ['is_outgoing', 'mydata_sent', 'issue_date', 'invoice_type']
    search_fields = ['series', 'number', 'counterpart_name', 'counterpart_vat']
    date_hierarchy = 'issue_date'
    inlines = [InvoiceItemInline]
    
    fieldsets = (
        ('Στοιχεία Παραστατικού', {
            'fields': ('series', 'number', 'invoice_type', 'issue_date', 'is_outgoing')
        }),
        ('Αντισυμβαλλόμενος', {
            'fields': ('counterpart', 'counterpart_vat', 'counterpart_name')
        }),
        ('Ποσά', {
            'fields': ('total_net', 'total_vat', 'total_gross')
        }),
        ('myDATA', {
            'fields': ('mydata_mark', 'mydata_uid', 'mydata_sent', 'mydata_sent_at'),
            'classes': ('collapse',)
        }),
        ('Σημειώσεις', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['submit_to_mydata']
    
    def submit_to_mydata(self, request, queryset):
        """Action για αποστολή στο myDATA"""
        from mydata.services import MyDataService
        service = MyDataService()
        
        success = 0
        errors = 0
        
        for invoice in queryset:
            if not invoice.mydata_sent:
                try:
                    service.submit_invoice(invoice)
                    success += 1
                except Exception as e:
                    errors += 1
                    self.message_user(
                        request,
                        f"Σφάλμα στο {invoice}: {str(e)}",
                        level='ERROR'
                    )
        
        self.message_user(
            request,
            f"Απεστάλησαν {success} τιμολόγια. {errors} σφάλματα."
        )
    
    submit_to_mydata.short_description = "Αποστολή στο myDATA"

@admin.register(MyDataSyncLog)
class MyDataSyncLogAdmin(admin.ModelAdmin):
    list_display = [
        'started_at', 'sync_type', 'status',
        'records_processed', 'records_created',
        'records_updated', 'records_failed'
    ]
    list_filter = ['sync_type', 'status', 'started_at']
    readonly_fields = [
        'sync_type', 'status', 'started_at', 'completed_at',
        'records_processed', 'records_created', 'records_updated',
        'records_failed', 'error_message', 'details'
    ]
    
    def has_add_permission(self, request):
        return False
```

### ΒΗΜΑ 7: Management Command για Sync

Δημιούργησε το directory structure:

```bash
mkdir -p mydata/management/commands
touch mydata/management/__init__.py
touch mydata/management/commands/__init__.py
```

Φτιάξε `mydata/management/commands/sync_mydata.py`:

```python
# mydata/management/commands/sync_mydata.py
from django.core.management.base import BaseCommand
from mydata.services import MyDataService

class Command(BaseCommand):
    help = 'Sync invoices from myDATA'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to sync back'
        )
        parser.add_argument(
            '--type',
            type=str,
            choices=['received', 'transmitted', 'both'],
            default='both',
            help='Type of invoices to sync'
        )
    
    def handle(self, *args, **options):
        service = MyDataService()
        days = options['days']
        sync_type = options['type']
        
        self.stdout.write(f"Starting sync for last {days} days...")
        
        if sync_type in ['received', 'both']:
            self.stdout.write("Syncing received invoices...")
            created, updated, errors = service.sync_received_invoices(days)
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Received: {created} created, {updated} updated, {len(errors)} errors"
                )
            )
            if errors:
                for error in errors:
                    self.stdout.write(self.style.ERROR(f"  - {error}"))
        
        if sync_type in ['transmitted', 'both']:
            self.stdout.write("Syncing transmitted invoices...")
            created, updated, errors = service.sync_transmitted_invoices(days)
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Transmitted: {created} created, {updated} updated, {len(errors)} errors"
                )
            )
            if errors:
                for error in errors:
                    self.stdout.write(self.style.ERROR(f"  - {error}"))
        
        self.stdout.write(self.style.SUCCESS('✓ Sync completed!'))
```

---

## 🧪 Testing

### 1. Test myDATA Connection

Δημιούργησε `test_mydata.py` στο root:

```python
# test_mydata.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yourproject.settings')
django.setup()

from mydata.client import MyDataClient
from datetime import datetime, timedelta

# Initialize client
client = MyDataClient(
    user_id="YOUR_AFM",
    subscription_key="YOUR_KEY",
    is_sandbox=True
)

# Test 1: Fetch transmitted docs
print("Test 1: Fetching transmitted invoices...")
try:
    response = client.request_transmitted_docs(
        date_from=datetime.now() - timedelta(days=7)
    )
    invoices = client.parse_invoice_response(response)
    print(f"✓ Success! Found {len(invoices)} invoices")
    for inv in invoices[:3]:
        print(f"  - {inv['series']}/{inv['aa']} - {inv['total_gross']}€")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 2: Fetch received docs
print("\nTest 2: Fetching received invoices...")
try:
    response = client.request_docs(
        date_from=datetime.now() - timedelta(days=7)
    )
    invoices = client.parse_invoice_response(response)
    print(f"✓ Success! Found {len(invoices)} invoices")
except Exception as e:
    print(f"✗ Error: {e}")
```

Τρέξε:
```bash
python test_mydata.py
```

### 2. Test Django Integration

```bash
# Δημιουργία test data
python manage.py shell

>>> from inventory.models import ProductCategory, Product
>>> cat = ProductCategory.objects.create(name="Ξυλεία")
>>> product = Product.objects.create(
...     code="KAST-001",
...     name="Καστανιά 5x10cm",
...     category=cat,
...     unit="m3",
...     purchase_price=150.00,
...     sale_price=200.00
... )
>>> print(product)
```

### 3. Test myDATA Sync

```bash
# Sync τιμολογίων (τελευταίες 7 μέρες)
python manage.py sync_mydata --days=7 --type=both

# Sync μόνο received
python manage.py sync_mydata --days=30 --type=received
```

---

## 📊 Usage Examples

### Παράδειγμα 1: Manual Sync

```python
from mydata.services import MyDataService

service = MyDataService()

# Sync received invoices (last 30 days)
created, updated, errors = service.sync_received_invoices(days_back=30)
print(f"Created: {created}, Updated: {updated}, Errors: {len(errors)}")
```

### Παράδειγμα 2: Submit Invoice

```python
from inventory.models import Invoice
from mydata.services import MyDataService

# Get an invoice
invoice = Invoice.objects.get(pk=1)

# Submit to myDATA
service = MyDataService()
response = service.submit_invoice(invoice)

print(f"MARK: {invoice.mydata_mark}")
```

### Παράδειγμα 3: Check Sync Status

```python
from inventory.models import MyDataSyncLog

# Τελευταία sync
last_sync = MyDataSyncLog.objects.first()
print(f"Last sync: {last_sync.started_at}")
print(f"Status: {last_sync.status}")
print(f"Processed: {last_sync.records_processed}")
```

---

## 🔄 Automated Sync (Optional)

### Option A: Cron Job

```bash
# Άνοιξε crontab
crontab -e

# Πρόσθεσε (sync κάθε ώρα)
0 * * * * cd /path/to/project && python manage.py sync_mydata --days=1 --type=both
```

### Option B: Celery (Advanced)

Αν θέλεις async processing με Celery, πες μου να σου φτιάξω το setup!

---

## ⚠️ Important Notes

1. **Credentials:** ΜΗΝ commit τα credentials στο Git!
   ```python
   # Χρησιμοποίησε environment variables
   import os
   MYDATA_USER_ID = os.getenv('MYDATA_USER_ID')
   ```

2. **Testing:** ΠΑΝΤΑ δοκίμασε πρώτα με `is_sandbox=True`

3. **Rate Limits:** Το myDATA API έχει limits - μην κάνεις spam requests

4. **Backups:** Κάνε backup πριν κάνεις bulk sync

---

## 📝 Next Steps

1. ✅ Setup και test connection
2. ✅ Import existing invoices (one-time)
3. ✅ Test με 1-2 τιμολόγια manually
4. ✅ Setup automated sync
5. ✅ Train χρήστες στο admin panel
6. ⏳ React frontend (αργότερα)

---

## 🆘 Troubleshooting

### "Authentication failed"
- Έλεγξε το MYDATA_USER_ID (πρέπει να είναι το ΑΦΜ σου)
- Έλεγξε το MYDATA_SUBSCRIPTION_KEY

### "Invoice already exists"
- Το myDATA δεν επιτρέπει διπλότυπα
- Χρησιμοποίησε διαφορετικό series/aa

### "Stock movements not created"
- Έλεγξε ότι το Invoice.is_outgoing = False (για αγορές)
- Έλεγξε ότι τα InvoiceItems έχουν product assigned

---

Έτοιμος να ξεκινήσεις; 🚀
