# mydata/services.py
"""
Service Layer για myDATA Integration
Συνδέει το myDATA API Client με τα Django models
"""

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Tuple, Optional
import logging

from django.db import transaction
from django.db.models import Sum, QuerySet
from django.conf import settings
from django.utils import timezone

from .client import MyDataClient
from inventory.models import (
    Invoice, InvoiceItem, Product, StockMovement,
    MyDataSyncLog
)

logger = logging.getLogger(__name__)

# Currency quantization: όλα τα ποσά ΦΠΑ στρογγυλοποιούνται σε 2 δεκαδικά.
_CENTS = Decimal('0.01')
_ZERO = Decimal('0.00')


def _q(value) -> Decimal:
    """Quantize a Decimal/None to 2 decimal places (default 0.00)."""
    if value is None:
        return _ZERO
    return Decimal(value).quantize(_CENTS, rounding=ROUND_HALF_UP)


class VATPortalService:
    """
    Read-only VAT domain logic for the client portal.

    ΣΗΜΑΝΤΙΚΟ: όλες οι μέθοδοι δέχονται έναν ΗΔΗ επιλυμένο `client`
    (ClientProfile), ΠΟΤΕ request/user. Η απομόνωση (isolation) παραμένει
    αποκλειστικά στο view (_require_client). Έτσι το service είναι καθαρό
    domain layer και testable χωρίς HTTP.

    rec_type: 1 = εκροές (output / έσοδα), 2 = εισροές (input / έξοδα).
    """

    @staticmethod
    def get_summary(client) -> Dict[str, Dict[str, Decimal]]:
        """
        Σύνολα net/vat ανά κατεύθυνση (output/input) για ΟΛΗ την ιστορία του
        πελάτη, εξαιρώντας ακυρωμένα. Επιστρέφει quantized Decimals (2dp).
        """
        from mydata.models import VATRecord

        summary = {
            'output': {'net': _ZERO, 'vat': _ZERO},
            'input': {'net': _ZERO, 'vat': _ZERO},
        }
        agg = (VATRecord.objects
               .filter(client=client, is_cancelled=False)
               .values('rec_type')
               .annotate(total_net=Sum('net_value'), total_vat=Sum('vat_amount')))
        for row in agg:
            key = 'output' if row['rec_type'] == 1 else 'input'
            summary[key] = {
                'net': _q(row['total_net']),
                'vat': _q(row['total_vat']),
            }
        return summary

    @staticmethod
    def get_periods(client, *, period_type: Optional[str] = None,
                    year: Optional[int] = None) -> QuerySet:
        """
        VATPeriodResult του πελάτη, νεότερα πρώτα. Προαιρετικά φίλτρα
        period_type ('monthly'|'quarterly') και year.
        """
        from mydata.models import VATPeriodResult

        qs = VATPeriodResult.objects.filter(client=client)
        if period_type:
            qs = qs.filter(period_type=period_type)
        if year is not None:
            qs = qs.filter(year=year)
        return qs.order_by('-year', '-period')

    @staticmethod
    def get_recent_records(client, *, limit: int = 50,
                           year: Optional[int] = None) -> QuerySet:
        """
        Τα πιο πρόσφατα μη-ακυρωμένα VATRecord του πελάτη (έως `limit`).
        Προαιρετικό φίλτρο year (στο issue_date).
        """
        from mydata.models import VATRecord

        qs = VATRecord.objects.filter(client=client, is_cancelled=False)
        if year is not None:
            qs = qs.filter(issue_date__year=year)
        return qs.order_by('-issue_date')[:limit]


def summarize_vat_sync(client, before_id, out) -> Dict:
    """
    Εξετάζει τα VATSyncLog που δημιούργησε ένα sync run (id > before_id) για τον
    client και επιστρέφει ένα Response-ready dict.

    Όταν ο locked-period guard παρέκαμψε ΟΛΟΚΛΗΡΟ τον sync (skipped>0 και τίποτα
    fetched/created/updated), δίνει καθαρό σήμα skipped/locked αντί για ψεύτικη
    «επιτυχία», ώστε το frontend να ενημερώσει σωστά τον χρήστη.

    Args:
        client: ClientProfile
        before_id: το max VATSyncLog.id πριν τρέξει το command (0 αν κανένα)
        out: StringIO με το stdout του command (fallback message)
    Returns:
        dict έτοιμο για Response(...).
    """
    from mydata.models import VATSyncLog

    new_logs = list(VATSyncLog.objects.filter(client=client, id__gt=before_id))
    fetched = sum((l.records_fetched or 0) for l in new_logs)
    created = sum((l.records_created or 0) for l in new_logs)
    updated = sum((l.records_updated or 0) for l in new_logs)
    skipped = sum((l.records_skipped or 0) for l in new_logs)

    if skipped and not (fetched or created or updated):
        detail = ' · '.join(
            (l.error_message or '').strip()
            for l in new_logs
            if (l.records_skipped or 0) > 0 and l.error_message
        )
        return {
            'success': False,
            'skipped': True,
            'locked': True,
            'message': (
                'Ο συγχρονισμός παραλείφθηκε: η περίοδος είναι κλειδωμένη. '
                'Ξεκλειδώστε την για επανασυγχρονισμό.'
            ),
            'detail': detail or out.getvalue(),
        }
    return {
        'success': True,
        'skipped': False,
        'records_created': created,
        'records_updated': updated,
        'records_fetched': fetched,
        'message': out.getvalue(),
    }


class MyDataService:
    """
    Service για myDATA operations
    """
    
    def __init__(self):
        """Initialize με credentials από settings"""
        self.client = MyDataClient(
            user_id=settings.MYDATA_USER_ID,
            subscription_key=settings.MYDATA_SUBSCRIPTION_KEY,
            is_sandbox=settings.MYDATA_IS_SANDBOX
        )
    
    # =====================================================
    # SYNC ΠΑΡΑΣΤΑΤΙΚΩΝ ΑΠΟ myDATA
    # =====================================================
    
    def sync_received_invoices(
        self,
        days_back: int = 7
    ) -> Tuple[int, int, List[str]]:
        """
        Sync τιμολογίων που έχουμε ΛΑΒΕΙ (από προμηθευτές)
        
        Args:
            days_back: Πόσες μέρες πίσω να τραβήξει
            
        Returns:
            Tuple (created, updated, errors)
        """
        log = MyDataSyncLog.objects.create(
            sync_type='PULL_RECEIVED',
            status='PENDING'
        )
        
        try:
            # Pull data από myDATA
            date_from = datetime.now() - timedelta(days=days_back)
            response = self.client.request_docs(
                date_from=date_from,
                date_to=datetime.now()
            )
            
            invoices = self.client.parse_invoice_response(response)
            
            created = 0
            updated = 0
            errors = []
            
            for inv_data in invoices:
                try:
                    with transaction.atomic():
                        created_count, updated_count = self._process_invoice(
                            inv_data,
                            is_outgoing=False
                        )
                        created += created_count
                        updated += updated_count
                        
                except Exception as e:
                    error_msg = f"Error processing invoice {inv_data.get('mark')}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Update log
            log.status = 'SUCCESS' if not errors else 'ERROR'
            log.completed_at = timezone.now()
            log.records_processed = len(invoices)
            log.records_created = created
            log.records_updated = updated
            log.records_failed = len(errors)
            log.error_message = '\n'.join(errors) if errors else ''
            log.save()
            
            return created, updated, errors
            
        except Exception as e:
            log.status = 'ERROR'
            log.completed_at = timezone.now()
            log.error_message = str(e)
            log.save()
            raise
    
    def sync_transmitted_invoices(
        self,
        days_back: int = 7
    ) -> Tuple[int, int, List[str]]:
        """
        Sync τιμολογίων που έχουμε ΕΚΔΩΣΕΙ (σε πελάτες)
        
        Args:
            days_back: Πόσες μέρες πίσω να τραβήξει
            
        Returns:
            Tuple (created, updated, errors)
        """
        log = MyDataSyncLog.objects.create(
            sync_type='PULL_TRANSMITTED',
            status='PENDING'
        )
        
        try:
            # Pull data από myDATA
            date_from = datetime.now() - timedelta(days=days_back)
            response = self.client.request_transmitted_docs(
                date_from=date_from,
                date_to=datetime.now()
            )
            
            invoices = self.client.parse_invoice_response(response)
            
            created = 0
            updated = 0
            errors = []
            
            for inv_data in invoices:
                try:
                    with transaction.atomic():
                        created_count, updated_count = self._process_invoice(
                            inv_data,
                            is_outgoing=True
                        )
                        created += created_count
                        updated += updated_count
                        
                except Exception as e:
                    error_msg = f"Error processing invoice {inv_data.get('mark')}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Update log
            log.status = 'SUCCESS' if not errors else 'ERROR'
            log.completed_at = timezone.now()
            log.records_processed = len(invoices)
            log.records_created = created
            log.records_updated = updated
            log.records_failed = len(errors)
            log.error_message = '\n'.join(errors) if errors else ''
            log.save()
            
            return created, updated, errors
            
        except Exception as e:
            log.status = 'ERROR'
            log.completed_at = timezone.now()
            log.error_message = str(e)
            log.save()
            raise
    
    def _process_invoice(
        self,
        inv_data: Dict,
        is_outgoing: bool
    ) -> Tuple[int, int]:
        """
        Επεξεργασία ενός τιμολογίου από myDATA
        
        Returns:
            Tuple (created, updated) - 1 ή 0 για κάθε
        """
        mark = inv_data['mark']
        
        # Check if exists
        invoice = Invoice.objects.filter(mydata_mark=mark).first()
        
        if invoice:
            # Update existing
            invoice.total_net = Decimal(str(inv_data['total_net']))
            invoice.total_vat = Decimal(str(inv_data['total_vat']))
            invoice.total_gross = Decimal(str(inv_data['total_gross']))
            invoice.save()
            
            # TODO: Update items if needed
            
            return 0, 1
        else:
            # Create new
            from accounting.models import ClientProfile
            
            # Try to find counterpart
            counterpart_vat = inv_data['counterpart_vat'] if is_outgoing else inv_data['issuer_vat']
            counterpart = ClientProfile.objects.filter(afm=counterpart_vat).first()
            
            invoice = Invoice.objects.create(
                series=inv_data['series'] or 'A',
                number=inv_data['aa'],
                invoice_type=inv_data['invoice_type'],
                issue_date=datetime.strptime(inv_data['issue_date'], '%Y-%m-%d').date(),
                counterpart=counterpart,
                counterpart_vat=counterpart_vat,
                counterpart_name=counterpart.eponimia if counterpart else 'Άγνωστος',
                is_outgoing=is_outgoing,
                total_net=Decimal(str(inv_data['total_net'])),
                total_vat=Decimal(str(inv_data['total_vat'])),
                total_gross=Decimal(str(inv_data['total_gross'])),
                mydata_mark=mark,
                mydata_uid=inv_data['uid'],
                mydata_sent=True,
                mydata_sent_at=timezone.now()
            )
            
            # Create items
            for idx, detail in enumerate(inv_data['details'], start=1):
                InvoiceItem.objects.create(
                    invoice=invoice,
                    line_number=idx,
                    description=detail.get('itemDescr', 'Προϊόν'),
                    quantity=Decimal(str(detail.get('quantity', 1))),
                    unit='piece',  # TODO: Parse από detail
                    unit_price=Decimal(str(detail.get('netValue', 0))),
                    net_value=Decimal(str(detail.get('netValue', 0))),
                    vat_category=detail.get('vatCategory', 1),
                    vat_amount=Decimal(str(detail.get('vatAmount', 0)))
                )
            
            # Create stock movement για εισαγωγές
            if not is_outgoing:
                self._create_stock_movements_from_invoice(invoice)
            
            return 1, 0
    
    def _create_stock_movements_from_invoice(self, invoice: Invoice):
        """
        Δημιουργία stock movements από τιμολόγιο αγοράς
        """
        for item in invoice.items.all():
            if item.product:
                StockMovement.objects.create(
                    product=item.product,
                    movement_type='IN',
                    quantity=item.quantity,
                    unit_cost=item.unit_price,
                    date=invoice.issue_date,
                    invoice=invoice,
                    counterpart=invoice.counterpart,
                    notes=f"Auto από τιμολόγιο {invoice.series}/{invoice.number}"
                )
    
    # =====================================================
    # ΑΠΟΣΤΟΛΗ ΠΑΡΑΣΤΑΤΙΚΩΝ ΣΤΟ myDATA
    # =====================================================
    
    def submit_invoice(self, invoice: Invoice) -> Dict:
        """
        Αποστολή τιμολογίου στο myDATA
        
        Args:
            invoice: To Invoice object
            
        Returns:
            Dict με response (περιέχει MARK)
        """
        log = MyDataSyncLog.objects.create(
            sync_type='PUSH_INVOICE',
            status='PENDING'
        )
        
        try:
            # Convert invoice to myDATA format
            invoice_data = self._invoice_to_mydata_format(invoice)
            
            # Submit
            response = self.client.send_invoices([invoice_data])
            
            # Parse response
            if 'response' in response and len(response['response']) > 0:
                result = response['response'][0]
                
                if result.get('statusCode') == 'Success':
                    # Update invoice
                    invoice.mydata_mark = result.get('mark')
                    invoice.mydata_uid = result.get('uid')
                    invoice.mydata_sent = True
                    invoice.mydata_sent_at = timezone.now()
                    invoice.save()
                    
                    log.status = 'SUCCESS'
                    log.records_processed = 1
                    log.records_created = 1
                    log.details = result
                else:
                    error_msg = result.get('errors', 'Unknown error')
                    log.status = 'ERROR'
                    log.error_message = str(error_msg)
                    raise Exception(error_msg)
            
            log.completed_at = timezone.now()
            log.save()
            
            return response
            
        except Exception as e:
            log.status = 'ERROR'
            log.completed_at = timezone.now()
            log.error_message = str(e)
            log.save()
            raise
    
    def _invoice_to_mydata_format(self, invoice: Invoice) -> Dict:
        """
        Μετατροπή Invoice σε myDATA format
        """
        # Company info (από settings)
        my_vat = settings.MYDATA_USER_ID
        
        invoice_data = {
            "issuer": {
                "vatNumber": my_vat,
                "country": "GR",
                "branch": 0
            },
            "counterpart": {
                "vatNumber": invoice.counterpart_vat,
                "country": "GR",
                "branch": 0
            },
            "invoiceHeader": {
                "series": invoice.series,
                "aa": invoice.number,
                "issueDate": invoice.issue_date.strftime('%Y-%m-%d'),
                "invoiceType": invoice.invoice_type,
                "currency": "EUR"
            },
            "invoiceDetails": [],
            "invoiceSummary": {
                "totalNetValue": float(invoice.total_net),
                "totalVatAmount": float(invoice.total_vat),
                "totalWithheldAmount": 0.00,
                "totalFeesAmount": 0.00,
                "totalStampDutyAmount": 0.00,
                "totalOtherTaxesAmount": 0.00,
                "totalDeductionsAmount": 0.00,
                "totalGrossValue": float(invoice.total_gross)
            }
        }
        
        # Add items
        for item in invoice.items.all():
            invoice_data["invoiceDetails"].append({
                "lineNumber": item.line_number,
                "netValue": float(item.net_value),
                "vatCategory": item.vat_category,
                "vatAmount": float(item.vat_amount),
                "itemDescr": item.description[:300]  # Max 300 chars
            })
        
        return invoice_data
    
    # =====================================================
    # HELPER METHODS
    # =====================================================
    
    def get_latest_sync_status(self, sync_type: str = None) -> MyDataSyncLog:
        """Επιστρέφει το τελευταίο sync log"""
        qs = MyDataSyncLog.objects.all()
        if sync_type:
            qs = qs.filter(sync_type=sync_type)
        return qs.first()


# =====================================================
# DJANGO MANAGEMENT COMMANDS
# =====================================================

"""
Δημιούργησε αυτό το αρχείο:
mydata/management/commands/sync_mydata.py

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
                    f"Received: {created} created, {updated} updated, {len(errors)} errors"
                )
            )
        
        if sync_type in ['transmitted', 'both']:
            self.stdout.write("Syncing transmitted invoices...")
            created, updated, errors = service.sync_transmitted_invoices(days)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Transmitted: {created} created, {updated} updated, {len(errors)} errors"
                )
            )
        
        self.stdout.write(self.style.SUCCESS('Sync completed!'))

# Usage:
# python manage.py sync_mydata --days=30 --type=both
"""
