"""
Backup βάσης δεδομένων + αρχείων media.

    python manage.py backup_database [--output-dir DIR] [--keep-days N] [--skip-media]

Παράγει ανά εκτέλεση:
    crm_db_{timestamp}.backup      (SQLite: αντίγραφο αρχείου)
    crm_db_{timestamp}.pgdump      (PostgreSQL: pg_dump custom format)
    crm_media_{timestamp}.tar.gz   (media files, εκτός αν --skip-media)

Η επαναφορά γίνεται με `python manage.py restore_database` — τα ονόματα
αρχείων εδώ και εκεί πρέπει να μένουν συγχρονισμένα (βλ. BACKUP_PREFIX /
MEDIA_PREFIX που μοιράζονται οι δύο εντολές).
"""
from django.core.management.base import BaseCommand, CommandError
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from django.conf import settings

# Κοινές σταθερές με το restore_database — μην τις αλλάξεις μονομερώς.
BACKUP_PREFIX = 'crm_db_'
MEDIA_PREFIX = 'crm_media_'
DB_SUFFIXES = ('.backup', '.pgdump')
MEDIA_SUFFIX = '.tar.gz'

# Ημιτελή backups (η βάση πάρθηκε, τα media όχι). Σκόπιμα ΔΕΝ ταιριάζουν με
# το BACKUP_PREFIX ώστε να μην επιλέγονται ποτέ από --latest/--list.
PARTIAL_PREFIX = 'partial_crm_db_'

# Πόσα ημιτελή backups κρατάμε. Επειδή δεν μετρούν στον κανονικό καθαρισμό
# (δεν ταιριάζουν με το BACKUP_PREFIX), μια επαναλαμβανόμενη αποτυχία media
# θα γέμιζε τον δίσκο με partial_* για πάντα. Κρατάμε τα 3 νεότερα: αρκετά
# για διάγνωση, όχι αρκετά για να γεμίσει ο δίσκος.
MAX_PARTIAL_BACKUPS = 3


def default_backup_dir():
    """Ο προεπιλεγμένος φάκελος backup (κοινός με το restore_database)."""
    return Path(settings.BASE_DIR) / 'backups'


class Command(BaseCommand):
    help = (
        'Backup της βάσης δεδομένων και των media με timestamp + καθαρισμός παλιών. '
        'SQLite: αντίγραφο αρχείου. PostgreSQL: pg_dump (custom format).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir', type=str, default='',
            help='Φάκελος αποθήκευσης (default: BASE_DIR/backups)'
        )
        parser.add_argument(
            '--keep-days', type=int, default=0,
            help='Διαγραφή backups παλαιότερων από Χ ημέρες (default: κράτα τα 30 τελευταία)'
        )
        parser.add_argument(
            '--skip-media', action='store_true',
            help='Παράλειψη του backup των media αρχείων'
        )

    def handle(self, *args, **options):
        # Backup directory
        if options['output_dir']:
            backup_dir = Path(options['output_dir'])
        else:
            backup_dir = default_backup_dir()
        backup_dir.mkdir(parents=True, exist_ok=True)

        db = settings.DATABASES['default']
        engine = db['ENGINE']
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if engine == 'django.db.backends.sqlite3':
            backup_path = self._backup_sqlite(db, backup_dir, timestamp)
        elif engine in ('django.db.backends.postgresql',
                        'django.db.backends.postgresql_psycopg2'):
            backup_path = self._backup_postgres(db, backup_dir, timestamp)
        else:
            raise CommandError(
                f'Μη υποστηριζόμενη μηχανή βάσης για backup: {engine}'
            )

        self.stdout.write(self.style.SUCCESS(
            f'✅ Backup βάσης ολοκληρώθηκε: {backup_path}'
        ))

        # Media: αποτυχία = αποτυχία ΟΛΟΥ του backup.
        #
        # Παλαιότερα έβγαινε warning και exit 0, αφήνοντας πίσω ένα κανονικά
        # ονομασμένο crm_db_* που έμοιαζε πλήρες. Το restore --latest θα το
        # επέλεγε και το γραφείο θα ανακάλυπτε την απουσία των εγγράφων τη
        # μέρα που θα τα χρειαζόταν. Πλέον το ημιτελές backup μετονομάζεται
        # σε partial_* ώστε να ΜΗΝ είναι υποψήφιο, και η εντολή αποτυγχάνει.
        if not options['skip_media']:
            try:
                media_path = self._backup_media(backup_dir, timestamp)
            except Exception as exc:  # noqa: BLE001
                partial = self._demote_to_partial(backup_path)
                raise CommandError(
                    f'❌ Το backup των media απέτυχε: {exc}\n'
                    f'Το backup της βάσης ΔΕΝ είναι πλήρες και μετονομάστηκε '
                    f'σε {partial.name} ώστε να μην επιλεγεί από --latest.'
                ) from exc
            self.stdout.write(self.style.SUCCESS(
                f'✅ Backup media ολοκληρώθηκε: {media_path}'
            ))

        self._cleanup(backup_dir, options['keep_days'])

    def _demote_to_partial(self, backup_path):
        """
        Υποβιβάζει ένα ημιτελές backup ώστε να μη μοιάζει πλήρες.

        Το `PARTIAL_PREFIX` δεν ταιριάζει με το `BACKUP_PREFIX`, οπότε το
        αρχείο δεν εμφανίζεται στο `--list`, δεν επιλέγεται από `--latest`
        και δεν μετράει στον καθαρισμό των 30 τελευταίων.
        """
        partial = backup_path.with_name(
            f'{PARTIAL_PREFIX}{backup_path.name[len(BACKUP_PREFIX):]}'
        )
        try:
            backup_path.rename(partial)
        except OSError:
            backup_path.unlink(missing_ok=True)
            self._prune_partials(backup_path.parent)
            return backup_path
        self._prune_partials(partial.parent)
        return partial

    def _prune_partials(self, backup_dir):
        """
        Κρατά μόνο τα MAX_PARTIAL_BACKUPS νεότερα partial_*.

        Τα ημιτελή backups δεν περνούν από τον κανονικό καθαρισμό (σκόπιμα —
        δεν πρέπει να μετρούν στα «30 τελευταία» καλά backups), οπότε χωρίς
        αυτό μια μόνιμη αποτυχία των media θα γέμιζε τον δίσκο.
        """
        partials = sorted(
            [p for p in backup_dir.iterdir()
             if p.name.startswith(PARTIAL_PREFIX)],
            key=lambda p: p.stat().st_mtime,
        )
        for old in partials[:-MAX_PARTIAL_BACKUPS] if MAX_PARTIAL_BACKUPS else partials:
            old.unlink(missing_ok=True)
            self.stdout.write(f'🗑️ Διαγράφηκε παλιό ημιτελές backup: {old.name}')

    def _backup_sqlite(self, db, backup_dir, timestamp):
        db_path = Path(db['NAME'])
        if not db_path.exists():
            raise CommandError(f'Δεν βρέθηκε η βάση: {db_path}')
        backup_path = backup_dir / f'{BACKUP_PREFIX}{timestamp}.backup'
        shutil.copy2(db_path, backup_path)
        return backup_path

    def _backup_postgres(self, db, backup_dir, timestamp):
        pg_dump = shutil.which('pg_dump')
        if not pg_dump:
            raise CommandError(
                'Δεν βρέθηκε το pg_dump. Εγκατάστησε το postgresql-client '
                '(περιλαμβάνεται στο production Docker image).'
            )
        backup_path = backup_dir / f'{BACKUP_PREFIX}{timestamp}.pgdump'
        cmd = [pg_dump, '--format=custom', f'--file={backup_path}']
        if db.get('HOST'):
            cmd.append(f"--host={db['HOST']}")
        if db.get('PORT'):
            cmd.append(f"--port={db['PORT']}")
        if db.get('USER'):
            cmd.append(f"--username={db['USER']}")
        cmd.append(db['NAME'])

        env = os.environ.copy()
        if db.get('PASSWORD'):
            env['PGPASSWORD'] = db['PASSWORD']

        result = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=1800
        )
        if result.returncode != 0:
            backup_path.unlink(missing_ok=True)
            raise CommandError(f'Το pg_dump απέτυχε: {result.stderr.strip()}')
        return backup_path

    def _backup_media(self, backup_dir, timestamp):
        """Συμπίεση του MEDIA_ROOT σε tar.gz δίπλα στο backup της βάσης."""
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            # ΟΧΙ σιωπηλή παράλειψη: αν ο χρήστης δεν ζήτησε --skip-media,
            # η απουσία του MEDIA_ROOT σημαίνει ότι το backup δεν μπορεί να
            # είναι πλήρες. Λάθος ρύθμιση MEDIA_ROOT δεν πρέπει να περνά ως
            # «επιτυχία χωρίς media».
            raise RuntimeError(
                f'Δεν υπάρχει φάκελος media ({media_root}). Αν το backup '
                f'προορίζεται να είναι μόνο βάσης, δώσε ρητά --skip-media.'
            )

        backup_path = backup_dir / f'{MEDIA_PREFIX}{timestamp}{MEDIA_SUFFIX}'
        cmd = [
            'tar', '-czf', str(backup_path),
            '-C', str(media_root.parent), media_root.name,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=3600
        )
        if result.returncode != 0:
            backup_path.unlink(missing_ok=True)
            raise RuntimeError(f'Το tar απέτυχε: {result.stderr.strip()}')
        return backup_path

    def _cleanup(self, backup_dir, keep_days):
        """
        Καθαρισμός παλιών backups. Τα media tarballs διαγράφονται μαζί με το
        αντίστοιχο backup βάσης (ίδιο timestamp), ώστε να μη μένουν ορφανά.
        """
        db_backups = sorted(
            [p for p in backup_dir.iterdir()
             if p.name.startswith(BACKUP_PREFIX) and p.suffix in DB_SUFFIXES],
            key=lambda p: p.stat().st_mtime,
        )

        if keep_days > 0:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=keep_days)
            doomed = [
                p for p in db_backups
                if datetime.fromtimestamp(p.stat().st_mtime) < cutoff
            ]
        elif len(db_backups) > 30:
            doomed = db_backups[:-30]
        else:
            doomed = []

        for old_backup in doomed:
            timestamp = old_backup.name[len(BACKUP_PREFIX):-len(old_backup.suffix)]
            old_backup.unlink()
            self.stdout.write(f'🗑️ Διαγράφηκε παλιό backup: {old_backup.name}')
            media_file = backup_dir / f'{MEDIA_PREFIX}{timestamp}{MEDIA_SUFFIX}'
            if media_file.exists():
                media_file.unlink()
                self.stdout.write(f'🗑️ Διαγράφηκε παλιό media backup: {media_file.name}')
