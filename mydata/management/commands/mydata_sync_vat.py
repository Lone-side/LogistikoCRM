# mydata/management/commands/mydata_sync_vat.py
"""
Management command για sync VAT data από myDATA.

Usage:
    # Sync VAT για συγκεκριμένο πελάτη (τελευταίος μήνας)
    python manage.py mydata_sync_vat --client=123456789

    # Sync VAT για συγκεκριμένη περίοδο
    python manage.py mydata_sync_vat --client=123456789 --year=2025 --month=1

    # Sync VAT για εύρος ημερομηνιών
    python manage.py mydata_sync_vat --client=123456789 --from=01/01/2025 --to=31/01/2025

    # Sync VAT για ΟΛΟΥΣ τους πελάτες με credentials
    python manage.py mydata_sync_vat --all

    # Dry run (δεν αποθηκεύει τίποτα)
    python manage.py mydata_sync_vat --client=123456789 --dry-run
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from datetime import date, datetime, timedelta
from calendar import monthrange
import logging

from accounting.models import ClientProfile
from mydata.models import MyDataCredentials, VATRecord, VATSyncLog
from mydata.client import (
    MyDataClient,
    MyDataCredentialsNotFoundError,
    MyDataAuthError,
    MyDataAPIError,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync VAT data from myDATA for specified client(s)'

    def add_arguments(self, parser):
        # Client selection
        parser.add_argument(
            '--client',
            type=str,
            help='ΑΦΜ πελάτη για sync'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Sync όλους τους πελάτες με ενεργά credentials'
        )

        # Date range options
        parser.add_argument(
            '--year',
            type=int,
            help='Έτος περιόδου (π.χ. 2025)'
        )
        parser.add_argument(
            '--month',
            type=int,
            help='Μήνας περιόδου (1-12)'
        )
        parser.add_argument(
            '--from',
            dest='date_from',
            type=str,
            help='Από ημερομηνία (dd/mm/yyyy)'
        )
        parser.add_argument(
            '--to',
            dest='date_to',
            type=str,
            help='Έως ημερομηνία (dd/mm/yyyy)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Αριθμός ημερών πίσω (default: 30)'
        )

        # Options
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Εμφάνιση χωρίς αποθήκευση στη βάση'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Αναλυτική έξοδος'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            default=True,
            help='Διαγραφή παλιών records πριν το sync (default: True)'
        )
        parser.add_argument(
            '--no-clear',
            action='store_true',
            help='Να μην διαγράψει τα παλιά records'
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.verbose = options['verbose']
        self.clear_before_sync = options['clear'] and not options['no_clear']

        # Validate arguments
        if not options['client'] and not options['all']:
            raise CommandError(
                "Πρέπει να δώσεις --client=ΑΦΜ ή --all"
            )

        # Parse date range
        date_from, date_to = self._parse_date_range(options)

        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("myDATA VAT Sync"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Περίοδος: {date_from} - {date_to}")

        if self.dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - Δεν θα αποθηκευτούν δεδομένα"))

        self.stdout.write("")

        # Get clients to sync
        if options['all']:
            clients = self._get_all_clients_with_credentials()
        else:
            clients = self._get_client_by_afm(options['client'])

        if not clients:
            self.stdout.write(self.style.ERROR("Δεν βρέθηκαν πελάτες για sync"))
            return

        self.stdout.write(f"Πελάτες για sync: {len(clients)}")
        self.stdout.write("")

        # Sync each client
        total_created = 0
        total_updated = 0
        total_errors = 0

        for client in clients:
            created, updated, errors = self._sync_client_vat(
                client, date_from, date_to
            )
            total_created += created
            total_updated += updated
            total_errors += errors

        # Summary
        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("ΣΥΝΟΛΟ"))
        self.stdout.write(f"  Νέες εγγραφές: {total_created}")
        self.stdout.write(f"  Ενημερωμένες: {total_updated}")
        if total_errors:
            self.stdout.write(self.style.ERROR(f"  Σφάλματα: {total_errors}"))
        self.stdout.write("=" * 60)

    def _parse_date_range(self, options) -> tuple[date, date]:
        """Parse date range from command options."""
        today = date.today()

        # Explicit from/to dates
        if options['date_from'] and options['date_to']:
            try:
                date_from = datetime.strptime(options['date_from'], '%d/%m/%Y').date()
                date_to = datetime.strptime(options['date_to'], '%d/%m/%Y').date()
                return date_from, date_to
            except ValueError:
                raise CommandError("Λάθος format ημερομηνίας. Χρησιμοποίησε dd/mm/yyyy")

        # Year/month
        if options['year'] and options['month']:
            year = options['year']
            month = options['month']
            date_from = date(year, month, 1)
            last_day = monthrange(year, month)[1]
            date_to = date(year, month, last_day)
            return date_from, date_to

        # Only year (full year)
        if options['year']:
            year = options['year']
            date_from = date(year, 1, 1)
            date_to = min(date(year, 12, 31), today)
            return date_from, date_to

        # Default: last N days
        days = options['days']
        date_to = today
        date_from = today - timedelta(days=days)
        return date_from, date_to

    def _get_all_clients_with_credentials(self) -> list:
        """Get all clients with active myDATA credentials."""
        credentials = MyDataCredentials.objects.filter(
            is_active=True
        ).select_related('client')

        clients = []
        for cred in credentials:
            if cred.has_credentials:
                clients.append(cred.client)
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Παράλειψη {cred.client.afm} - δεν έχει credentials"
                    )
                )

        return clients

    def _get_client_by_afm(self, afm: str) -> list:
        """Get single client by AFM."""
        try:
            client = ClientProfile.objects.get(afm=afm)
            return [client]
        except ClientProfile.DoesNotExist:
            raise CommandError(f"Δεν βρέθηκε πελάτης με ΑΦΜ: {afm}")

    def _sync_client_vat(
        self,
        client: ClientProfile,
        date_from: date,
        date_to: date
    ) -> tuple[int, int, int]:
        """
        Sync VAT data για έναν πελάτη.

        Returns:
            Tuple (created, updated, errors)
        """
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Πελάτης: {client.eponimia} ({client.afm})")
        self.stdout.write(f"{'='*60}")

        # Check credentials
        try:
            credentials = client.mydata_credentials
        except MyDataCredentials.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    f"  Δεν υπάρχουν myDATA credentials για τον πελάτη {client.afm}"
                )
            )
            return 0, 0, 1

        if not credentials.has_credentials:
            self.stdout.write(
                self.style.ERROR(
                    f"  Τα credentials δεν έχουν συμπληρωθεί"
                )
            )
            return 0, 0, 1

        # Create sync log
        sync_log = None
        if not self.dry_run:
            sync_log = VATSyncLog.objects.create(
                client=client,
                sync_type='VAT_INFO',
                status='PENDING',
                date_from=date_from,
                date_to=date_to
            )

        created = 0
        updated = 0
        errors = 0
        deleted = 0

        try:
            # Clear existing records for this period if requested
            if self.clear_before_sync and not self.dry_run:
                deleted = VATRecord.objects.filter(
                    client=client,
                    issue_date__gte=date_from,
                    issue_date__lte=date_to
                ).delete()[0]
                if deleted > 0:
                    self.stdout.write(
                        self.style.WARNING(f"  Διαγράφηκαν {deleted} παλιά records")
                    )

            # Get API client
            api_client = credentials.get_api_client()

            env = "SANDBOX" if credentials.is_sandbox else "PRODUCTION"
            self.stdout.write(f"  Environment: {env}")
            self.stdout.write(f"  Fetching VAT info...")

            # Fetch VAT records
            records_fetched = 0

            for vat_record in api_client.request_vat_info(
                date_from=date_from,
                date_to=date_to
            ):
                records_fetched += 1

                if self.verbose:
                    self._print_vat_record(vat_record)

                if not self.dry_run:
                    try:
                        is_created = self._save_vat_record(client, vat_record)
                        if is_created:
                            created += 1
                        else:
                            updated += 1
                    except Exception as e:
                        logger.error(f"Error saving VAT record: {e}")
                        errors += 1

            self.stdout.write(f"  Fetched: {records_fetched} records")

            if not self.dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Created: {created}, Updated: {updated}, Errors: {errors}"
                    )
                )

                # Update sync log
                if sync_log:
                    sync_log.records_fetched = records_fetched
                    sync_log.records_created = created
                    sync_log.records_updated = updated
                    sync_log.records_failed = errors
                    sync_log.mark_completed(
                        'SUCCESS' if errors == 0 else 'PARTIAL'
                    )

                # Update credentials last sync
                credentials.mark_vat_sync_completed()

        except MyDataAuthError as e:
            self.stdout.write(
                self.style.ERROR(f"  Authentication failed: {e.message}")
            )
            if sync_log:
                sync_log.mark_failed(e.message)
            return 0, 0, 1

        except MyDataAPIError as e:
            self.stdout.write(
                self.style.ERROR(f"  API Error: {e.message}")
            )
            if sync_log:
                sync_log.mark_failed(e.message)
            return 0, 0, 1

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"  Unexpected error: {str(e)}")
            )
            logger.exception(f"Unexpected error syncing VAT for {client.afm}")
            if sync_log:
                sync_log.mark_failed(str(e))
            return 0, 0, 1

        return created, updated, errors

    def _save_vat_record(self, client: ClientProfile, vat_record) -> bool:
        """
        Save or update a VAT record.

        Returns:
            True if created, False if updated
        """
        with transaction.atomic():
            record, created = VATRecord.objects.update_or_create(
                client=client,
                mark=vat_record.mark,
                expense_category=vat_record.expense_category,
                income_code=vat_record.income_code,
                defaults={
                    'is_cancelled': vat_record.is_cancelled,
                    'issue_date': vat_record.issue_date,
                    'rec_type': vat_record.rec_type,
                    'inv_type': vat_record.inv_type,
                    'vat_category': vat_record.vat_category,
                    'vat_exemption_category': vat_record.vat_exemption_category or '',
                    'net_value': vat_record.net_value,
                    'vat_amount': vat_record.vat_amount,
                    'counter_vat_number': vat_record.counter_vat_number or '',
                    'vat_offset_amount': vat_record.vat_offset_amount,
                    'deductions_amount': vat_record.deductions_amount,
                }
            )

        return created

    def _print_vat_record(self, vat_record):
        """Print VAT record details (verbose mode)."""
        type_str = "Εκροή" if vat_record.rec_type == 1 else "Εισροή"
        self.stdout.write(
            f"    [{vat_record.mark}] {type_str} | "
            f"{vat_record.issue_date} | "
            f"Net: {vat_record.net_value} | "
            f"VAT: {vat_record.vat_amount} | "
            f"Cat: {vat_record.vat_rate_display}"
        )
