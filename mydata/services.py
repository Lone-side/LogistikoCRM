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
        mark = inv_data.get('mark')
        if not mark:
            # Χωρίς MARK δεν υπάρχει κλειδί αντιστοίχισης: θα δημιουργούσαμε
            # διπλοεγγραφή σε κάθε sync ή θα ενημερώναμε άσχετο τιμολόγιο
            raise ValueError(
                'Το παραστατικό από το myDATA δεν έχει MARK — παραλείπεται '
                f'(series/aa: {inv_data.get("series")}/{inv_data.get("aa")})'
            )

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
            ValueError: για guard αποτυχίες (λάθος κατεύθυνση, ήδη απεσταλμένο,
                        χωρίς γραμμές, μη ρυθμισμένο MYDATA_ISSUER_VAT)
            MyDataValidationError: όταν η ΑΑΔΕ απορρίψει το παραστατικό
            MyDataServerError: για μη αναγνώσιμη/κενή απάντηση ΑΑΔΕ
        """
        from .client import MyDataServerError, MyDataValidationError
        from .invoice_xml import build_invoices_doc, parse_response_doc

        # --- Guards πριν από οποιοδήποτε API call (η κατεύθυνση πρώτη,
        # ώστε τα pulled εισερχόμενα να μην παίρνουν μήνυμα «ήδη απεσταλμένο») ---
        if not invoice.is_outgoing:
            raise ValueError('Μόνο εξερχόμενα παραστατικά αποστέλλονται στο myDATA')
        issuer_vat = getattr(settings, 'MYDATA_ISSUER_VAT', '')
        if not issuer_vat:
            raise ValueError(
                'Δεν έχει ρυθμιστεί το ΑΦΜ εκδότη (MYDATA_ISSUER_VAT στο .env)'
            )
        aa = str(invoice.number).strip()
        if not aa.isdigit() or int(aa) <= 0:
            raise ValueError(
                f'Ο αριθμός παραστατικού «{invoice.number}» πρέπει να είναι '
                f'θετικός ακέραιος για αποστολή στο myDATA'
            )
        items = list(invoice.items.all())
        if not items:
            raise ValueError('Το παραστατικό δεν έχει γραμμές')

        # --- Atomic claim: μόνο ένας νικητής σε ταυτόχρονα κλικ.
        # Το UPDATE ... WHERE mydata_sent=False είναι test-and-set στη βάση —
        # δεν κρατάμε row lock κατά τη διάρκεια του HTTP call στην ΑΑΔΕ. ---
        claimed = Invoice.objects.filter(
            pk=invoice.pk, mydata_sent=False
        ).update(mydata_sent=True)
        if not claimed:
            invoice.refresh_from_db()
            raise ValueError(
                f'Το παραστατικό {invoice} έχει ήδη σταλεί ή αποστέλλεται '
                f'στο myDATA (MARK: {invoice.mydata_mark})'
            )

        log = MyDataSyncLog.objects.create(
            sync_type='PUSH_INVOICE',
            status='PENDING',
            details={'invoice_id': invoice.pk,
                     'invoice': f'{invoice.series}/{invoice.number}'},
        )

        try:
            # Το build γίνεται πριν το API call — validation errors (π.χ.
            # κατηγορία ΦΠΑ 7 χωρίς εξαίρεση) σκάνε τοπικά, όχι στην ΑΑΔΕ
            xml_doc = build_invoices_doc(
                [self._invoice_to_mydata_format(invoice, issuer_vat)]
            )
            raw_response = self.client.send_invoices(xml_doc)

            try:
                result = parse_response_doc(raw_response)[0]
            except (ValueError, IndexError) as exc:
                # Η υποβολή ΜΠΟΡΕΙ να έχει γίνει — κράτα το raw response στο
                # log για χειροκίνητο έλεγχο (RequestTransmittedDocs)
                log.details = {**(log.details or {}), 'raw_response': str(raw_response)[:2000]}
                raise MyDataServerError(
                    f'Μη έγκυρη απάντηση από το myDATA: {exc} — ΕΛΕΓΞΕ στα '
                    f'εκδοθέντα (RequestTransmittedDocs) πριν ξαναστείλεις'
                ) from exc

            if result['status_code'] == 'Success':
                if not result['invoice_mark']:
                    raise MyDataValidationError(
                        'Το myDATA επέστρεψε Success χωρίς MARK — το παραστατικό '
                        'δεν σημειώθηκε ως απεσταλμένο'
                    )
                # Πρώτα το MARK στο log (αν αποτύχει το invoice.save, το MARK
                # δεν χάνεται), μετά το invoice
                log.status = 'SUCCESS'
                log.records_processed = 1
                log.records_created = 1
                log.details = {**(log.details or {}), **result}
                log.completed_at = timezone.now()
                log.save()

                invoice.mydata_mark = result['invoice_mark']
                invoice.mydata_uid = result['invoice_uid'] or ''
                invoice.mydata_sent = True
                invoice.mydata_sent_at = timezone.now()
                invoice.save(update_fields=[
                    'mydata_mark', 'mydata_uid', 'mydata_sent', 'mydata_sent_at',
                    'updated_at',
                ])

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
            log.details = {**(log.details or {}), **result}
            raise MyDataValidationError(
                f'Το myDATA απέρριψε το παραστατικό: {error_messages}'
            )

        except Exception as e:
            # Αποδέσμευση του claim ώστε να επιτρέπεται retry — μόνο αν δεν
            # έχει γραφτεί MARK (αν γράφτηκε, η υποβολή πέτυχε)
            Invoice.objects.filter(
                pk=invoice.pk, mydata_mark__isnull=True
            ).update(mydata_sent=False)
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
        from .client import MyDataServerError, MyDataValidationError
        from .invoice_xml import parse_response_doc

        if not invoice.is_outgoing:
            raise ValueError('Μόνο εξερχόμενα παραστατικά μπορούν να ακυρωθούν στο myDATA')
        if not invoice.mydata_sent or not invoice.mydata_mark:
            raise ValueError('Το παραστατικό δεν έχει σταλεί στο myDATA')
        if invoice.mydata_cancelled:
            raise ValueError(
                f'Το παραστατικό είναι ήδη ακυρωμένο στο myDATA '
                f'(cancellationMark: {invoice.mydata_cancellation_mark})'
            )

        log = MyDataSyncLog.objects.create(
            sync_type='CANCEL_INVOICE',
            status='PENDING',
            details={'invoice_id': invoice.pk,
                     'invoice': f'{invoice.series}/{invoice.number}',
                     'mark': invoice.mydata_mark},
        )

        try:
            raw_response = self.client.cancel_invoice(invoice.mydata_mark)
            try:
                result = parse_response_doc(raw_response)[0]
            except (ValueError, IndexError) as exc:
                log.details = {**(log.details or {}), 'raw_response': str(raw_response)[:2000]}
                raise MyDataServerError(
                    f'Μη έγκυρη απάντηση από το myDATA: {exc}'
                ) from exc

            already_cancelled = any(
                (e.get('code') or '') == '251' for e in result['errors']
            )
            if result['status_code'] == 'Success' or already_cancelled:
                cancellation_mark = result['cancellation_mark']
                self._mark_cancelled(invoice, cancellation_mark)

                log.status = 'SUCCESS'
                log.records_processed = 1
                log.details = {**(log.details or {}), **result}
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
            log.details = {**(log.details or {}), **result}
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

    def _mark_cancelled(self, invoice: Invoice, cancellation_mark):
        """Δομημένη καταγραφή ακύρωσης + σημείωση για τον χρήστη."""
        stamp = timezone.now().strftime('%d/%m/%Y %H:%M')
        note = (
            f'Ακυρώθηκε στο myDATA {stamp} '
            f'(cancellationMark: {cancellation_mark or "—"})'
        )
        invoice.mydata_cancelled = True
        invoice.mydata_cancellation_mark = cancellation_mark
        invoice.mydata_cancelled_at = timezone.now()
        invoice.notes = f'{invoice.notes}\n{note}'.strip()
        invoice.save(update_fields=[
            'mydata_cancelled', 'mydata_cancellation_mark', 'mydata_cancelled_at',
            'notes', 'updated_at',
        ])

    def _invoice_to_mydata_format(self, invoice: Invoice, issuer_vat: str) -> Dict:
        """
        Μετατροπή Invoice στο dict format του invoice_xml.build_invoices_doc.
        Οι χαρακτηρισμοί εσόδων (incomeClassification) συμπληρώνονται με
        defaults ανά τύπο παραστατικού μέσα στο invoice_xml.
        """
        return {
            'issuer_vat': issuer_vat,
            'counterpart_vat': invoice.counterpart_vat,
            'series': invoice.series,
            'aa': str(invoice.number).strip(),
            'issue_date': invoice.issue_date,
            'invoice_type': invoice.invoice_type,
            'currency': 'EUR',
            'correlated_marks': (
                [invoice.correlated_mark] if invoice.correlated_mark else []
            ),
            'lines': [
                {
                    'line_number': item.line_number,
                    'net_value': item.net_value,
                    'vat_category': item.vat_category,
                    'vat_amount': item.vat_amount,
                    'vat_exemption_category': item.vat_exemption_category,
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
