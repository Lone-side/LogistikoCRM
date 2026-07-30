# mydata/services.py
"""
Service Layer για myDATA Integration
Συνδέει το myDATA API Client με τα Django models
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Tuple
import logging

from django.db import transaction
from django.conf import settings
from django.utils import timezone

from .client import MyDataClient
from inventory.models import (
    Invoice, InvoiceItem, Product, StockMovement,
    MyDataSyncLog
)

logger = logging.getLogger(__name__)


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
        Αποστολή τιμολογίου στο myDATA (επίσημο XML συμβόλαιο ΑΑΔΕ).

        Returns:
            Dict: {'success': True, 'mark': ..., 'uid': ...}

        Raises:
            ValueError: για guard αποτυχίες (ήδη απεσταλμένο, χωρίς γραμμές,
                        μη ρυθμισμένο MYDATA_ISSUER_VAT)
            MyDataValidationError: όταν η ΑΑΔΕ απορρίψει το παραστατικό
        """
        from .client import MyDataValidationError
        from .invoice_xml import build_invoices_doc, parse_response_doc

        # --- Guards πριν από οποιοδήποτε API call ---
        if invoice.mydata_sent and invoice.mydata_mark:
            raise ValueError(
                f'Το παραστατικό {invoice} έχει ήδη σταλεί στο myDATA '
                f'(MARK: {invoice.mydata_mark})'
            )
        if not invoice.is_outgoing:
            raise ValueError('Μόνο εξερχόμενα παραστατικά αποστέλλονται στο myDATA')
        issuer_vat = getattr(settings, 'MYDATA_ISSUER_VAT', '')
        if not issuer_vat:
            raise ValueError(
                'Δεν έχει ρυθμιστεί το ΑΦΜ εκδότη (MYDATA_ISSUER_VAT στο .env)'
            )
        items = list(invoice.items.all())
        if not items:
            raise ValueError('Το παραστατικό δεν έχει γραμμές')

        log = MyDataSyncLog.objects.create(
            sync_type='PUSH_INVOICE',
            status='PENDING'
        )

        try:
            xml_doc = build_invoices_doc([self._invoice_to_mydata_format(invoice, issuer_vat)])
            raw_response = self.client.send_invoices(xml_doc)
            result = parse_response_doc(raw_response)[0]

            if result['status_code'] == 'Success':
                invoice.mydata_mark = result['invoice_mark']
                invoice.mydata_uid = result['invoice_uid'] or ''
                invoice.mydata_sent = True
                invoice.mydata_sent_at = timezone.now()
                invoice.save(update_fields=[
                    'mydata_mark', 'mydata_uid', 'mydata_sent', 'mydata_sent_at',
                    'updated_at',
                ])

                log.status = 'SUCCESS'
                log.records_processed = 1
                log.records_created = 1
                log.details = result
                log.completed_at = timezone.now()
                log.save()

                logger.info(
                    f'myDATA: Εστάλη {invoice.series}/{invoice.number} '
                    f'- MARK {result["invoice_mark"]}'
                )
                return {
                    'success': True,
                    'mark': result['invoice_mark'],
                    'uid': result['invoice_uid'],
                }

            # ΑΑΔΕ επέστρεψε ValidationError/XMLSyntaxError κλπ
            error_messages = '; '.join(
                f"[{e['code']}] {e['message']}" for e in result['errors']
            ) or f"statusCode: {result['status_code']}"
            log.status = 'ERROR'
            log.error_message = error_messages
            log.details = result
            log.completed_at = timezone.now()
            log.save()
            raise MyDataValidationError(
                f'Το myDATA απέρριψε το παραστατικό: {error_messages}'
            )

        except Exception as e:
            if log.status == 'PENDING':
                log.status = 'ERROR'
                log.error_message = str(e)
                log.completed_at = timezone.now()
                log.save()
            raise

    def cancel_invoice(self, invoice: Invoice) -> Dict:
        """
        Ακύρωση απεσταλμένου παραστατικού στο myDATA.

        Returns:
            Dict: {'success': True, 'cancellation_mark': ...}
        """
        from .client import MyDataValidationError
        from .invoice_xml import parse_response_doc

        if not invoice.mydata_sent or not invoice.mydata_mark:
            raise ValueError('Το παραστατικό δεν έχει σταλεί στο myDATA')

        log = MyDataSyncLog.objects.create(
            sync_type='CANCEL_INVOICE',
            status='PENDING'
        )

        try:
            raw_response = self.client.cancel_invoice(invoice.mydata_mark)
            result = parse_response_doc(raw_response)[0]

            if result['status_code'] == 'Success':
                cancellation_mark = result['cancellation_mark']
                stamp = timezone.now().strftime('%d/%m/%Y %H:%M')
                note = (
                    f'Ακυρώθηκε στο myDATA {stamp} '
                    f'(cancellationMark: {cancellation_mark})'
                )
                invoice.notes = f'{invoice.notes}\n{note}'.strip()
                invoice.save(update_fields=['notes', 'updated_at'])

                log.status = 'SUCCESS'
                log.records_processed = 1
                log.details = result
                log.completed_at = timezone.now()
                log.save()

                logger.info(
                    f'myDATA: Ακυρώθηκε {invoice.series}/{invoice.number} '
                    f'- cancellationMark {cancellation_mark}'
                )
                return {'success': True, 'cancellation_mark': cancellation_mark}

            error_messages = '; '.join(
                f"[{e['code']}] {e['message']}" for e in result['errors']
            ) or f"statusCode: {result['status_code']}"
            log.status = 'ERROR'
            log.error_message = error_messages
            log.details = result
            log.completed_at = timezone.now()
            log.save()
            raise MyDataValidationError(
                f'Το myDATA απέρριψε την ακύρωση: {error_messages}'
            )

        except Exception as e:
            if log.status == 'PENDING':
                log.status = 'ERROR'
                log.error_message = str(e)
                log.completed_at = timezone.now()
                log.save()
            raise

    def _invoice_to_mydata_format(self, invoice: Invoice, issuer_vat: str) -> Dict:
        """
        Μετατροπή Invoice στο dict format του invoice_xml.build_invoices_doc.
        """
        return {
            'issuer_vat': issuer_vat,
            'counterpart_vat': invoice.counterpart_vat,
            'series': invoice.series,
            'aa': invoice.number,
            'issue_date': invoice.issue_date,
            'invoice_type': invoice.invoice_type,
            'currency': 'EUR',
            'lines': [
                {
                    'line_number': item.line_number,
                    'net_value': item.net_value,
                    'vat_category': item.vat_category,
                    'vat_amount': item.vat_amount,
                }
                for item in invoice.items.all()
            ],
            'total_net': invoice.total_net,
            'total_vat': invoice.total_vat,
            'total_gross': invoice.total_gross,
        }

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
