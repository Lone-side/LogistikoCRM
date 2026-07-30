# inventory/admin.py
"""
Admin configuration για Inventory models
"""

from django.contrib import admin
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import path
from django.http import HttpResponseRedirect
from django.conf import settings
from .models import (
    ProductCategory, Product, StockMovement, 
    Invoice, InvoiceItem, MyDataSyncLog
)
from mydata.client import MyDataClient
from accounting.models import ClientProfile
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone


# =====================================================
# INLINE ADMINS
# =====================================================

class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    fields = ['line_number', 'description', 'quantity', 'unit', 'unit_price', 'vat_category']


# =====================================================
# INVOICE ADMIN
# =====================================================

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['series', 'number', 'issue_date', 'counterpart_name', 'total_gross', 'is_outgoing', 'mydata_sent', 'view_mydata_link']
    list_filter = ['is_outgoing', 'mydata_sent', 'issue_date', 'invoice_type']
    search_fields = ['number', 'series', 'counterpart_name', 'counterpart_vat']
    date_hierarchy = 'issue_date'
    inlines = [InvoiceItemInline]
    
    def view_mydata_link(self, obj):
        """Link to view full myDATA invoice"""
        if obj.mydata_mark:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse('admin:inventory_invoice_view_mydata', args=[obj.pk])
            return format_html('<a href="{}" target="_blank">👁️ Προβολή</a>', url)
        return '-'
    view_mydata_link.short_description = 'myDATA'
    
    fieldsets = (
        ('Στοιχεία Παραστατικού', {
            'fields': ('series', 'number', 'invoice_type', 'issue_date')
        }),
        ('Αντισυμβαλλόμενος', {
            'fields': ('counterpart', 'counterpart_vat', 'counterpart_name', 'is_outgoing')
        }),
        ('Ποσά', {
            'fields': ('total_net', 'total_vat', 'total_gross')
        }),
        ('myDATA', {
            'fields': ('mydata_mark', 'mydata_uid', 'mydata_sent', 'mydata_sent_at'),
            'classes': ('collapse',)
        }),
        ('Άλλα', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['fetch_from_mydata', 'register_to_stock', 'send_to_mydata']

    @admin.action(description='📤 Αποστολή στο myDATA')
    def send_to_mydata(self, request, queryset):
        """Αποστολή επιλεγμένων εξερχόμενων τιμολογίων στο myDATA."""
        from mydata.services import MyDataService

        service = MyDataService()
        sent = 0
        for invoice in queryset:
            try:
                result = service.submit_invoice(invoice)
                sent += 1
                self.message_user(
                    request,
                    f'✅ {invoice.series}/{invoice.number} → MARK {result["mark"]}',
                    messages.SUCCESS,
                )
            except Exception as e:
                self.message_user(
                    request,
                    f'❌ {invoice.series}/{invoice.number}: {e}',
                    messages.ERROR,
                )
        if sent:
            self.message_user(
                request, f'Εστάλησαν {sent} παραστατικά στο myDATA', messages.INFO
            )

    def register_to_stock(self, request, queryset):
        """Custom action: Καταχώρηση τιμολογίων στην αποθήκη"""
        
        registered = 0
        skipped = 0
        errors = 0
        
        for invoice in queryset:
            # Μόνο εισερχόμενα (is_outgoing=False)
            if invoice.is_outgoing:
                skipped += 1
                continue
            
            # Έλεγχος αν έχει ήδη καταχωρηθεί
            if invoice.stock_movements.exists():
                skipped += 1
                continue
            
            try:
                # Για κάθε γραμμή τιμολογίου
                for item in invoice.items.all():
                    # Βρες ή δημιούργησε προϊόν
                    product_code = f"IMP-{invoice.counterpart_vat}-{item.line_number}"
                    
                    product, created = Product.objects.get_or_create(
                        code=product_code,
                        defaults={
                            'name': item.description[:200],
                            'unit': item.unit,
                            'purchase_price': item.unit_price,  # ← ΧΩΡΙΣ ΦΠΑ!
                            'vat_category': item.vat_category,
                            'current_stock': 0
                        }
                    )
                    
                    # Δημιουργία StockMovement
                    StockMovement.objects.create(
                        product=product,
                        movement_type='IN',
                        quantity=item.quantity,
                        unit_cost=item.unit_price,  # ← ΚΑΘΑΡΗ ΤΙΜΗ!
                        date=invoice.issue_date,
                        invoice=invoice,
                        counterpart=invoice.counterpart,
                        notes=f"Εισαγωγή από {invoice.series}/{invoice.number}"
                    )
                    
                    # Stock ενημερώνεται αυτόματα από το StockMovement.save()
                
                registered += 1
                
            except Exception as e:
                errors += 1
                self.message_user(request, f'❌ Σφάλμα σε {invoice}: {e}', messages.ERROR)
        
        # Success message
        msg = f'✅ Καταχωρήθηκαν {registered} τιμολόγια στην αποθήκη'
        if skipped > 0:
            msg += f' ({skipped} παραλείφθηκαν)'
        if errors > 0:
            msg += f' - {errors} σφάλματα'
        
        self.message_user(request, msg, messages.SUCCESS if errors == 0 else messages.WARNING)
    
    register_to_stock.short_description = "📦 Καταχώρηση στην Αποθήκη (χωρίς ΦΠΑ)"
    
    def fetch_from_mydata(self, request, queryset):
        """Custom action: Λήψη τιμολογίων από myDATA"""
        
        # Initialize client
        client = MyDataClient(
            user_id=settings.MYDATA_USER_ID,
            subscription_key=settings.MYDATA_SUBSCRIPTION_KEY,
            is_sandbox=settings.MYDATA_IS_SANDBOX
        )
        
        # Fetch last 90 days
        date_from = datetime.now() - timedelta(days=90)
        date_to = datetime.now()
        
        try:
            response = client.request_docs(date_from=date_from, date_to=date_to)
            invoices_data = client.parse_invoice_response(response)
            
            imported = 0
            skipped = 0
            
            for inv_data in invoices_data:
                supplier_vat = inv_data.get('issuer_vat')
                if not supplier_vat:
                    continue
                
                series = inv_data.get('series', 'A')
                number = inv_data.get('aa', '')
                
                # Check if exists
                if Invoice.objects.filter(series=series, number=number).exists():
                    skipped += 1
                    continue
                
                # Get or create supplier
                try:
                    counterpart = ClientProfile.objects.get(afm=supplier_vat)
                except ClientProfile.DoesNotExist:
                    counterpart = ClientProfile.objects.create(
                        afm=supplier_vat,
                        eponimia=f'Συναλλασσόμενος ΑΦΜ: {supplier_vat}',
                        doy='ΑΘΗΝΩΝ'
                    )
                except ClientProfile.MultipleObjectsReturned:
                    counterpart = ClientProfile.objects.filter(afm=supplier_vat).first()
                
                # Parse date
                issue_date_str = inv_data.get('issue_date', '')
                try:
                    issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d').date()
                except Exception:
                    issue_date = timezone.now().date()
                
                # Create invoice
                invoice = Invoice.objects.create(
                    series=series,
                    number=number,
                    invoice_type=inv_data.get('invoice_type', '2.1'),
                    issue_date=issue_date,
                    counterpart=counterpart,
                    counterpart_vat=supplier_vat,
                    counterpart_name=counterpart.eponimia,
                    is_outgoing=False,
                    total_net=Decimal(str(inv_data.get('total_net', 0))),
                    total_vat=Decimal(str(inv_data.get('total_vat', 0))),
                    total_gross=Decimal(str(inv_data.get('total_gross', 0))),
                    mydata_mark=inv_data.get('mark') or None,
                    mydata_uid=inv_data.get('uid') or '',
                    mydata_sent=True,
                    mydata_sent_at=timezone.now(),
                    notes=f"Εισαγωγή από myDATA"
                )
                
                # Create invoice item
                InvoiceItem.objects.create(
                    invoice=invoice,
                    line_number=1,
                    description="Εισαγωγή από myDATA",
                    quantity=Decimal('1'),
                    unit='piece',
                    unit_price=invoice.total_net,
                    net_value=invoice.total_net,
                    vat_category=1,
                    vat_amount=invoice.total_vat
                )
                
                imported += 1
            
            # Success message
            msg = f'✅ Εισήχθησαν {imported} τιμολόγια'
            if skipped > 0:
                msg += f' ({skipped} υπήρχαν ήδη)'
            self.message_user(request, msg, messages.SUCCESS)
            
        except Exception as e:
            self.message_user(request, f'❌ Σφάλμα: {e}', messages.ERROR)
    
    fetch_from_mydata.short_description = "🔄 Λήψη από myDATA (τελευταίες 90 μέρες)"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('fetch-mydata/', self.admin_site.admin_view(self.fetch_mydata_view), name='inventory_invoice_fetch_mydata'),
            path('<int:invoice_id>/view-mydata/', self.admin_site.admin_view(self.view_mydata_detail), name='inventory_invoice_view_mydata'),
        ]
        return custom_urls + urls
    
    def fetch_mydata_view(self, request):
        """Custom view for fetching from myDATA"""
        # Trigger the action
        self.fetch_from_mydata(request, Invoice.objects.none())
        return HttpResponseRedirect("../")
    
    def view_mydata_detail(self, request, invoice_id):
        """View full myDATA invoice details"""
        from django.template.response import TemplateResponse
        import xml.etree.ElementTree as ET
        
        invoice = Invoice.objects.get(pk=invoice_id)
        
        # Fetch full invoice from myDATA
        client = MyDataClient(
            user_id=settings.MYDATA_USER_ID,
            subscription_key=settings.MYDATA_SUBSCRIPTION_KEY,
            is_sandbox=settings.MYDATA_IS_SANDBOX
        )
        
        invoice_data = None
        xml_content = None
        
        try:
            # Fetch by mark
            if invoice.mydata_mark:
                response = client.request_docs(mark=invoice.mydata_mark)
                
                if isinstance(response, str):
                    xml_content = response
                    # Parse XML
                    ns = {'ns': 'http://www.aade.gr/myDATA/invoice/v1.0',
                          'ecls': 'https://www.aade.gr/myDATA/expensesClassificaton/v1.0'}
                    root = ET.fromstring(response)
                    
                    inv_elem = root.find('.//ns:invoice', ns)
                    if inv_elem:
                        invoice_data = {
                            'issuer_vat': inv_elem.find('.//ns:issuer/ns:vatNumber', ns).text if inv_elem.find('.//ns:issuer/ns:vatNumber', ns) is not None else '',
                            'counterpart_vat': inv_elem.find('.//ns:counterpart/ns:vatNumber', ns).text if inv_elem.find('.//ns:counterpart/ns:vatNumber', ns) is not None else '',
                            'series': inv_elem.find('.//ns:invoiceHeader/ns:series', ns).text if inv_elem.find('.//ns:invoiceHeader/ns:series', ns) is not None else '',
                            'aa': inv_elem.find('.//ns:invoiceHeader/ns:aa', ns).text if inv_elem.find('.//ns:invoiceHeader/ns:aa', ns) is not None else '',
                            'issue_date': inv_elem.find('.//ns:invoiceHeader/ns:issueDate', ns).text if inv_elem.find('.//ns:invoiceHeader/ns:issueDate', ns) is not None else '',
                            'invoice_type': inv_elem.find('.//ns:invoiceHeader/ns:invoiceType', ns).text if inv_elem.find('.//ns:invoiceHeader/ns:invoiceType', ns) is not None else '',
                        }
                        
                        # Get invoice details (lines)
                        details = []
                        for detail in inv_elem.findall('.//ns:invoiceDetails', ns):
                            line = {
                                'line_number': detail.find('ns:lineNumber', ns).text if detail.find('ns:lineNumber', ns) is not None else '',
                                'net_value': detail.find('ns:netValue', ns).text if detail.find('ns:netValue', ns) is not None else '0',
                                'vat_category': detail.find('ns:vatCategory', ns).text if detail.find('ns:vatCategory', ns) is not None else '',
                                'vat_amount': detail.find('ns:vatAmount', ns).text if detail.find('ns:vatAmount', ns) is not None else '0',
                            }
                            
                            # Get classifications
                            classifications = []
                            for cls in detail.findall('.//ecls:expensesClassification', ns):
                                classifications.append({
                                    'type': cls.find('ecls:classificationType', ns).text if cls.find('ecls:classificationType', ns) is not None else '',
                                    'category': cls.find('ecls:classificationCategory', ns).text if cls.find('ecls:classificationCategory', ns) is not None else '',
                                    'amount': cls.find('ecls:amount', ns).text if cls.find('ecls:amount', ns) is not None else '0',
                                })
                            line['classifications'] = classifications
                            details.append(line)
                        
                        invoice_data['details'] = details
                        
                        # Get summary
                        summary = inv_elem.find('.//ns:invoiceSummary', ns)
                        if summary:
                            invoice_data['summary'] = {
                                'total_net': summary.find('ns:totalNetValue', ns).text if summary.find('ns:totalNetValue', ns) is not None else '0',
                                'total_vat': summary.find('ns:totalVatAmount', ns).text if summary.find('ns:totalVatAmount', ns) is not None else '0',
                                'total_gross': summary.find('ns:totalGrossValue', ns).text if summary.find('ns:totalGrossValue', ns) is not None else '0',
                            }
        except Exception as e:
            messages.error(request, f'Σφάλμα λήψης από myDATA: {e}')
        
        context = {
            **self.admin_site.each_context(request),
            'invoice': invoice,
            'invoice_data': invoice_data,
            'xml_content': xml_content,
            'title': f'myDATA Λεπτομέρειες - {invoice.series}/{invoice.number}',
        }
        
        return TemplateResponse(request, 'admin/inventory/invoice_mydata_detail.html', context)


# =====================================================
# OTHER ADMINS
# =====================================================

@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'created_at']
    search_fields = ['name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'category', 'current_stock', 'unit', 'purchase_price', 'sale_price', 'active']
    list_filter = ['active', 'category', 'unit']
    search_fields = ['code', 'name']
    fieldsets = (
        ('Βασικά Στοιχεία', {
            'fields': ('code', 'name', 'description', 'category', 'unit', 'active')
        }),
        ('Απόθεμα', {
            'fields': ('current_stock', 'min_stock')
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
    list_display = ['product', 'movement_type', 'quantity', 'date', 'counterpart', 'invoice']
    list_filter = ['movement_type', 'date']
    search_fields = ['product__code', 'product__name']
    date_hierarchy = 'date'


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'line_number', 'description', 'quantity', 'unit_price', 'net_value']
    list_filter = ['invoice__issue_date']
    search_fields = ['description', 'invoice__number']


@admin.register(MyDataSyncLog)
class MyDataSyncLogAdmin(admin.ModelAdmin):
    list_display = ['sync_type', 'status', 'started_at', 'completed_at', 'records_processed', 'records_created']
    list_filter = ['sync_type', 'status', 'started_at']
    readonly_fields = ['started_at', 'completed_at']
