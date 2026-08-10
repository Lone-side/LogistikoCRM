"""
Επαναφορά βάσης δεδομένων + media από backup που παρήγαγε το
`python manage.py backup_database`.

    python manage.py restore_database --latest
    python manage.py restore_database 20260807_134442
    python manage.py restore_database crm_db_20260807_134442.backup
    python manage.py restore_database --list

ΣΕΙΡΑ ΕΚΤΕΛΕΣΗΣ (σχεδιασμένη ώστε βάση και media να μη διαφωνήσουν ποτέ)
-----------------------------------------------------------------------
1. Επιλογή backup + έλεγχος μηχανής βάσης.
2. **Media πρώτα, χωρίς να αγγιχτεί τίποτα**: το tarball πρέπει να υπάρχει,
   να είναι ασφαλές (χωρίς absolute paths / «..» / symlinks που γράφουν
   εκτός MEDIA_ROOT) και να αποσυμπιέζεται επιτυχώς σε προσωρινό φάκελο.
   Οποιοδήποτε πρόβλημα εδώ σταματά την εντολή με τη ΒΑΣΗ ΑΝΕΠΑΦΗ.
3. Αντίγραφο ασφαλείας της τρέχουσας βάσης (`pre_restore_*`). Αν αποτύχει,
   η επαναφορά ματαιώνεται.
4. Transactional restore της βάσης.
5. Ατομικό swap του φακέλου media (rename, όχι αντιγραφή).
6. Αν αποτύχει ΟΤΙΔΗΠΟΤΕ μετά το βήμα 4, γίνεται **αυτόματο rollback** και
   της βάσης (από το safety dump) και των media. Αν αποτύχει και το
   rollback, η εντολή τερματίζει με σφάλμα και ρητές διαδρομές — ποτέ με
   μήνυμα επιτυχίας.
"""
import os
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from accounting.management.commands.backup_database import (
    BACKUP_PREFIX, DB_SUFFIXES, MEDIA_PREFIX, MEDIA_SUFFIX, default_backup_dir,
)

# Πρόθεμα των αντιγράφων ασφαλείας που παίρνονται ΠΡΙΝ από κάθε επαναφορά.
# Σκόπιμα διαφορετικό από το BACKUP_PREFIX ώστε ένα safety dump να μη
# γίνεται ποτέ υποψήφιο για --latest ή για τον καθαρισμό του backup_database.
SAFETY_PREFIX = 'pre_restore_'


def tar_path_parts(name):
    """Τα components ενός tar member name (πάντα POSIX μέσα σε tar)."""
    return [p for p in name.replace('\\', '/').split('/') if p]


class MediaArchiveError(Exception):
    """Το media archive λείπει, είναι κατεστραμμένο ή μη ασφαλές."""


class _NoPreviousMedia:
    """
    Sentinel: το swap έγινε, αλλά ΔΕΝ υπήρχαν προηγούμενα media.

    Χρειάζεται ξεχωριστή τιμή από το `None` γιατί τα δύο σενάρια θέλουν
    αντίθετο rollback:
      * `None`  → το swap δεν έτρεξε ποτέ· μην αγγίξεις τα media.
      * sentinel → το swap έβαλε ΝΕΑ media εκεί που δεν υπήρχε τίποτα· το
        rollback πρέπει να τα **αφαιρέσει**, αλλιώς μένουν πίσω media που
        δεν αντιστοιχούν στη βάση μετά το rollback.
    """

    def __repr__(self):  # pragma: no cover — μόνο για διαγνωστικά
        return '<NO_PREVIOUS_MEDIA>'


NO_PREVIOUS_MEDIA = _NoPreviousMedia()


class Command(BaseCommand):
    help = 'Επαναφορά βάσης δεδομένων και media από backup.'

    def add_arguments(self, parser):
        parser.add_argument(
            'backup', type=str, nargs='?', default='',
            help='Timestamp (π.χ. 20260807_134442) ή όνομα αρχείου backup.'
        )
        parser.add_argument(
            '--backup-dir', type=str, default='',
            help='Φάκελος backups (default: BASE_DIR/backups)'
        )
        parser.add_argument(
            '--latest', action='store_true',
            help='Επαναφορά του πιο πρόσφατου backup.'
        )
        parser.add_argument(
            '--list', action='store_true', dest='list_backups',
            help='Εμφάνιση των διαθέσιμων backups και έξοδος.'
        )
        parser.add_argument(
            '--skip-media', action='store_true',
            help='Επαναφορά ΜΟΝΟ της βάσης, ρητά χωρίς media.'
        )
        parser.add_argument(
            '--yes', action='store_true',
            help='Χωρίς ερώτηση επιβεβαίωσης (ΕΠΙΚΙΝΔΥΝΟ).'
        )

    # ------------------------------------------------------------------ #

    def handle(self, *args, **options):
        backup_dir = (
            Path(options['backup_dir']) if options['backup_dir']
            else default_backup_dir()
        )
        if not backup_dir.exists():
            raise CommandError(f'Δεν βρέθηκε ο φάκελος backups: {backup_dir}')

        available = self._available(backup_dir)

        if options['list_backups']:
            self._print_list(backup_dir, available)
            return

        if not available:
            raise CommandError(f'Δεν υπάρχουν backups στο {backup_dir}')

        db_file = self._select(available, options)
        timestamp = db_file.name[len(BACKUP_PREFIX):-len(db_file.suffix)]

        self._check_engine_matches(db_file)

        if not options['yes']:
            self.stdout.write(self.style.WARNING(
                f'\n⚠️ Θα αντικατασταθεί η τρέχουσα βάση από το {db_file.name}.\n'
            ))
            if input('Γράψε "YES" για συνέχεια: ') != 'YES':
                self.stdout.write('Η επαναφορά ακυρώθηκε.')
                return

        staging_root = None
        staged_media = None
        try:
            # --- 1. Media: ό,τι μπορεί να αποτύχει, αποτυγχάνει ΕΔΩ, πριν
            #        αγγιχτεί η βάση.
            if not options['skip_media']:
                media_file = (
                    backup_dir / f'{MEDIA_PREFIX}{timestamp}{MEDIA_SUFFIX}')
                staging_root, staged_media = self._prepare_media(
                    media_file, timestamp)

            self.stdout.write(self.style.SUCCESS(f'🔄 Επαναφορά: {db_file.name}'))

            # --- 2. Δίχτυ ασφαλείας + restore βάσης.
            safety = self._safety_backup(db_file)
            self._restore_database(db_file)
            self.stdout.write(self.style.SUCCESS('✅ Η βάση επαναφέρθηκε'))

            # --- 3. Ό,τι αποτύχει από εδώ και πέρα → rollback ΚΑΙ των δύο.
            #
            # Το media_state γεμίζει ΜΕΣΑ στο _swap_media, όχι από την τιμή
            # επιστροφής: αν το swap σκάσει στη μέση, η επιστροφή δεν γίνεται
            # ποτέ και το rollback πρέπει παρ' όλα αυτά να ξέρει τι είχε ήδη
            # μετακινηθεί.
            media_state = {}
            try:
                if staged_media is not None:
                    self._swap_media(staged_media, media_state)
                    self.stdout.write(
                        self.style.SUCCESS('✅ Τα media επαναφέρθηκαν'))
            except Exception as exc:  # noqa: BLE001
                self._rollback_all(safety, media_state.get('previous'), exc)
        finally:
            if staging_root is not None:
                shutil.rmtree(staging_root, ignore_errors=True)

        if options['skip_media']:
            self.stdout.write(
                'ℹ️ Ρητή επαναφορά μόνο βάσης (--skip-media) — τα media δεν '
                'άλλαξαν.'
            )
        self.stdout.write(self.style.SUCCESS('\n✅ Ολοκληρώθηκε.'))

    # ------------------------------------------------------------------ #
    # Επιλογή backup
    # ------------------------------------------------------------------ #

    def _available(self, backup_dir):
        """Τα διαθέσιμα backups βάσης, από το παλαιότερο στο νεότερο."""
        return sorted(
            [p for p in backup_dir.iterdir()
             if p.name.startswith(BACKUP_PREFIX) and p.suffix in DB_SUFFIXES],
            key=lambda p: p.name,
        )

    def _print_list(self, backup_dir, available):
        if not available:
            self.stdout.write(f'Δεν υπάρχουν backups στο {backup_dir}')
            return
        self.stdout.write(f'Διαθέσιμα backups στο {backup_dir}:')
        for path in available:
            timestamp = path.name[len(BACKUP_PREFIX):-len(path.suffix)]
            media = backup_dir / f'{MEDIA_PREFIX}{timestamp}{MEDIA_SUFFIX}'
            size = path.stat().st_size / (1024 * 1024)
            flag = ' + media' if media.exists() else '  ⚠️ ΧΩΡΙΣ media'
            self.stdout.write(f'  {path.name}  ({size:.1f} MB){flag}')

    def _select(self, available, options):
        """Επιλογή του backup προς επαναφορά από τα ορίσματα."""
        if options['latest']:
            return available[-1]

        wanted = options['backup']
        if not wanted:
            raise CommandError(
                'Δώσε timestamp/όνομα αρχείου, ή --latest. '
                'Δες τα διαθέσιμα με --list.'
            )

        for path in available:
            timestamp = path.name[len(BACKUP_PREFIX):-len(path.suffix)]
            if wanted in (path.name, path.stem, timestamp):
                return path

        raise CommandError(
            f'Δεν βρέθηκε backup «{wanted}». Δες τα διαθέσιμα με --list.'
        )

    def _check_engine_matches(self, db_file):
        """
        Ένα .backup (SQLite) δεν επαναφέρεται σε PostgreSQL και αντίστροφα —
        απόρριψε το νωρίς αντί να αφήσεις μισοεπαναφερμένη βάση.
        """
        engine = settings.DATABASES['default']['ENGINE']
        is_sqlite = engine == 'django.db.backends.sqlite3'
        if is_sqlite and db_file.suffix != '.backup':
            raise CommandError(
                f'Το {db_file.name} είναι PostgreSQL dump, αλλά η τρέχουσα '
                f'βάση είναι SQLite.'
            )
        if not is_sqlite and db_file.suffix != '.pgdump':
            raise CommandError(
                f'Το {db_file.name} είναι SQLite backup, αλλά η τρέχουσα '
                f'βάση είναι PostgreSQL.'
            )

    # ------------------------------------------------------------------ #
    # Media: επικύρωση + staging ΠΡΙΝ αγγιχτεί η βάση
    # ------------------------------------------------------------------ #

    def _prepare_media(self, media_file, timestamp):
        """
        Επικυρώνει και αποσυμπιέζει το media archive σε προσωρινό φάκελο.

        Επιστρέφει (staging_root, staged_media_dir). Κάθε αποτυχία εδώ
        συμβαίνει ΠΡΙΝ αγγιχτεί η βάση — άρα η βάση μένει ανέπαφη.
        """
        if not media_file.exists():
            raise CommandError(
                f'❌ Λείπει το media backup {media_file.name} για το '
                f'{timestamp}.\nΗ βάση ΔΕΝ άλλαξε. Αν θέλεις επαναφορά μόνο '
                f'της βάσης, δώσε ρητά --skip-media.'
            )

        media_root = Path(settings.MEDIA_ROOT)
        media_root.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._validate_media_archive(media_file)
        except MediaArchiveError as exc:
            raise CommandError(
                f'❌ Μη έγκυρο ή μη ασφαλές media archive: {exc}\n'
                f'Η βάση ΔΕΝ άλλαξε.'
            ) from exc

        # Staging δίπλα στο MEDIA_ROOT ώστε το τελικό rename να είναι ατομικό
        # (ίδιο filesystem) και να μη μείνει ποτέ μισοαντιγραμμένος φάκελος.
        staging_root = Path(tempfile.mkdtemp(
            prefix='.restore_staging_', dir=str(media_root.parent)))
        try:
            with tarfile.open(media_file, 'r:gz') as tar:
                # filter='data' (Python 3.11.4+): δεύτερη γραμμή άμυνας πάνω
                # από τη ρητή επικύρωση — αγνοεί devices/symlinks και
                # απορρίπτει paths εκτός προορισμού.
                #
                # ΧΩΡΙΣ fallback σε unfiltered extractall: σε παλιά Python το
                # σωστό είναι να αποτύχει η εντολή (fail closed), όχι να
                # αποσυμπιέσει χωρίς προστασία. Ένα backup που δεν έγινε
                # restore είναι πρόβλημα· ένα archive που γράφει έξω από το
                # MEDIA_ROOT είναι παραβίαση.
                tar.extractall(path=staging_root, filter='data')
        except Exception as exc:  # noqa: BLE001
            shutil.rmtree(staging_root, ignore_errors=True)
            raise CommandError(
                f'❌ Η αποσυμπίεση του media archive απέτυχε: {exc}\n'
                f'Η βάση ΔΕΝ άλλαξε.'
            ) from exc

        staged_media = self._staged_media_dir(staging_root)
        if staged_media is None:
            shutil.rmtree(staging_root, ignore_errors=True)
            raise CommandError(
                f'❌ Το media archive {media_file.name} δεν περιέχει φάκελο '
                f'media. Η βάση ΔΕΝ άλλαξε.'
            )
        self.stdout.write(
            '📦 Τα media επικυρώθηκαν και αποσυμπιέστηκαν προσωρινά.')
        return staging_root, staged_media

    def _validate_media_archive(self, media_file):
        """
        Απορρίπτει archives που θα έγραφαν εκτός MEDIA_ROOT.

        Ένα backup μπορεί να προέρχεται από άλλο μηχάνημα ή να έχει πειραχθεί:
        absolute paths, «..» traversal και symlinks/hardlinks προς τα έξω
        είναι όλα τρόποι να γραφτούν αρχεία οπουδήποτε στον server με τα
        δικαιώματα της εφαρμογής.
        """
        try:
            with tarfile.open(media_file, 'r:gz') as tar:
                members = tar.getmembers()
        except tarfile.TarError as exc:
            raise MediaArchiveError(f'μη αναγνώσιμο tar: {exc}') from exc
        except OSError as exc:
            raise MediaArchiveError(f'σφάλμα ανάγνωσης: {exc}') from exc

        if not members:
            raise MediaArchiveError('το archive είναι κενό')

        for member in members:
            name = member.name
            if name.startswith('/') or (len(name) > 1 and name[1] == ':'):
                raise MediaArchiveError(f'absolute path: {name!r}')
            if '..' in tar_path_parts(name):
                raise MediaArchiveError(f'path traversal («..»): {name!r}')
            if member.issym() or member.islnk():
                target = member.linkname
                if target.startswith('/') or '..' in tar_path_parts(target):
                    raise MediaArchiveError(
                        f'σύνδεσμος εκτός MEDIA_ROOT: {name!r} -> {target!r}')
            if member.isdev():
                raise MediaArchiveError(f'device node: {name!r}')

    def _staged_media_dir(self, staging_root):
        """
        Ο φάκελος μέσα στο staging που αντιστοιχεί στο MEDIA_ROOT.

        Το backup γράφει `tar -C <parent> <media_dir_name>`, οπότε το archive
        έχει έναν φάκελο κορυφής. Το όνομά του μπορεί να διαφέρει από το
        τρέχον MEDIA_ROOT (άλλο μηχάνημα), γι' αυτό δεν το υποθέτουμε.
        """
        entries = list(staging_root.iterdir())
        dirs = [p for p in entries if p.is_dir()]
        if len(entries) == 1 and len(dirs) == 1:
            return dirs[0]
        if entries:
            # Archive χωρίς φάκελο κορυφής: το ίδιο το staging είναι το media.
            return staging_root
        return None

    # ------------------------------------------------------------------ #
    # Δίχτυ ασφαλείας + restore βάσης
    # ------------------------------------------------------------------ #

    def _safety_backup(self, db_file):
        db = settings.DATABASES['default']
        if db['ENGINE'] == 'django.db.backends.sqlite3':
            return ('sqlite', self._safety_copy_sqlite(db))
        return ('postgres', self._safety_dump_postgres(db, db_file))

    def _safety_copy_sqlite(self, db):
        db_path = Path(db['NAME'])
        connections.close_all()
        if not db_path.exists():
            return None
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safety = db_path.with_name(f'{db_path.name}.before_restore_{stamp}')
        shutil.copy2(db_path, safety)
        self.stdout.write(f'📋 Η τρέχουσα βάση φυλάχθηκε στο: {safety}')
        return safety

    def _pg_conn_args(self, db):
        """Κοινά ορίσματα σύνδεσης για pg_dump/pg_restore."""
        args = []
        if db.get('HOST'):
            args.append(f"--host={db['HOST']}")
        if db.get('PORT'):
            args.append(f"--port={db['PORT']}")
        if db.get('USER'):
            args.append(f"--username={db['USER']}")
        return args

    def _pg_env(self, db):
        env = os.environ.copy()
        if db.get('PASSWORD'):
            env['PGPASSWORD'] = db['PASSWORD']
        return env

    def _safety_dump_postgres(self, db, db_file):
        """
        ΠΡΑΓΜΑΤΙΚΟ pg_dump της τρέχουσας βάσης πριν την επαναφορά.

        Χωρίς αυτό, ένα αποτυχημένο `pg_restore --clean` αφήνει τη βάση άδεια
        ΚΑΙ χωρίς επιστροφή. Αν το dump αποτύχει, η επαναφορά ΔΕΝ ξεκινά.
        """
        pg_dump = shutil.which('pg_dump')
        if not pg_dump:
            raise CommandError(
                'Δεν βρέθηκε το pg_dump — δεν μπορεί να ληφθεί αντίγραφο '
                'ασφαλείας της τρέχουσας βάσης. Η επαναφορά ματαιώνεται.'
            )
        connections.close_all()
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safety = db_file.parent / f'{SAFETY_PREFIX}{stamp}.pgdump'
        cmd = [pg_dump, '--format=custom', f'--file={safety}']
        cmd += self._pg_conn_args(db)
        cmd.append(db['NAME'])

        result = subprocess.run(
            cmd, env=self._pg_env(db), capture_output=True, text=True,
            timeout=1800,
        )
        if result.returncode != 0:
            safety.unlink(missing_ok=True)
            raise CommandError(
                'Το αντίγραφο ασφαλείας της τρέχουσας βάσης απέτυχε — η '
                f'επαναφορά ΜΑΤΑΙΩΘΗΚΕ, η βάση δεν άλλαξε.\n'
                f'{result.stderr.strip()}'
            )
        self.stdout.write(f'📋 Αντίγραφο ασφαλείας τρέχουσας βάσης: {safety}')
        return safety

    def _restore_database(self, db_file):
        db = settings.DATABASES['default']
        if db['ENGINE'] == 'django.db.backends.sqlite3':
            self._restore_sqlite(db, db_file)
        else:
            self._restore_postgres(db, db_file)

    def _restore_sqlite(self, db, db_file):
        connections.close_all()
        try:
            self._atomic_copy(db_file, Path(db['NAME']))
        except OSError as exc:
            # Χάρη στο temp file + os.replace, η υπάρχουσα βάση δεν έχει
            # αγγιχτεί καθόλου — το μήνυμα το λέει ρητά αντί να αφήσει
            # γυμνό OSError στον χειριστή.
            raise CommandError(
                f'Η επαναφορά της βάσης απέτυχε: {exc}\n'
                f'Η υπάρχουσα βάση ΔΕΝ άλλαξε (ατομική αντικατάσταση).'
            ) from exc

    def _atomic_copy(self, source, target):
        """
        Αντιγραφή αρχείου βάσης χωρίς ενδιάμεση «μισή» κατάσταση.

        Το `shutil.copy2` απευθείας πάνω στη ζωντανή βάση την τρυπάει: αν ο
        δίσκος γεμίσει ή το backup είναι κομμένο, το αρχείο έχει ήδη
        αντικατασταθεί μερικώς και η προηγούμενη βάση έχει χαθεί. Γράφουμε
        πρώτα σε προσωρινό αρχείο **στον ίδιο φάκελο** (άρα ίδιο filesystem)
        και μετά `os.replace`, που είναι ατομικό: ή βλέπεις την παλιά βάση ή
        την καινούργια, ποτέ κάτι ενδιάμεσο.
        """
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f'.{target.name}.restore_', dir=str(target.parent))
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            shutil.copy2(source, tmp_path)
            os.replace(tmp_path, target)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    def _restore_postgres(self, db, db_file):
        pg_restore = shutil.which('pg_restore')
        if not pg_restore:
            raise CommandError(
                'Δεν βρέθηκε το pg_restore. Εγκατάστησε το postgresql-client.'
            )
        connections.close_all()

        # --single-transaction: ή περνούν όλα, ή τίποτα. Χωρίς αυτό ένα
        # σφάλμα στη μέση αφήνει τη βάση μισοεπαναφερμένη. Συνεπάγεται
        # --exit-on-error, οπότε δεν «προσπερνά» σιωπηλά σφάλματα.
        cmd = [pg_restore, '--clean', '--if-exists', '--single-transaction',
               '--format=custom', f"--dbname={db['NAME']}"]
        cmd += self._pg_conn_args(db)
        cmd.append(str(db_file))

        result = subprocess.run(
            cmd, env=self._pg_env(db), capture_output=True, text=True,
            timeout=3600,
        )
        if result.returncode != 0:
            raise CommandError(
                'Το pg_restore απέτυχε — λόγω --single-transaction η βάση '
                'έμεινε στην προηγούμενη κατάστασή της (rollback).\n'
                f'{result.stderr.strip()}'
            )

    # ------------------------------------------------------------------ #
    # Media swap + rollback
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_contents_mode(previous):
        """True αν το safety αντίγραφο ζει ΜΕΣΑ στο MEDIA_ROOT (mountpoint mode)."""
        return (
            previous is not None
            and previous is not NO_PREVIOUS_MEDIA
            and Path(previous).parent == Path(settings.MEDIA_ROOT)
        )

    @staticmethod
    def _move_children(src, dst, skip=None):
        """Μετακίνηση όλων των παιδιών του src στο dst (εκτός του skip)."""
        for child in Path(src).iterdir():
            if skip is not None and child.name == skip:
                continue
            shutil.move(str(child), str(Path(dst) / child.name))

    def _swap_media(self, staged_media, state):
        """
        Ατομική αντικατάσταση του MEDIA_ROOT από τον staged φάκελο.

        Καταγράφει στο `state['previous']` τι βρέθηκε πριν το swap:
        διαδρομή των παλιών media, ή `NO_PREVIOUS_MEDIA` αν δεν υπήρχαν.
        Το state ενημερώνεται **πριν** από κάθε επικίνδυνη κίνηση, ώστε το
        rollback να ξέρει την πραγματική κατάσταση ακόμη κι αν σκάσουμε στη μέση.

        Σε Docker εγκατάσταση το MEDIA_ROOT είναι volume mountpoint και δεν
        μπορεί να μετονομαστεί (EBUSY). Τότε το swap γίνεται σε επίπεδο
        ΠΕΡΙΕΧΟΜΕΝΩΝ, με το safety αντίγραφο ΜΕΣΑ στο volume
        (.before_restore_<stamp>) ώστε να επιβιώνει ακόμη κι από θάνατο
        του container στη μέση της επαναφοράς.
        """
        media_root = Path(settings.MEDIA_ROOT)
        contents_mode = False
        if media_root.exists():
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Ο έλεγχος mountpoint γίνεται ΠΡΟΛΗΠΤΙΚΑ: το shutil.move σε
            # cross-device αποτυχία κάνει copy+rmtree — το rmtree του
            # mountpoint θα άδειαζε τα παλιά media ΠΡΙΝ αποτύχει.
            if os.path.ismount(str(media_root)):
                contents_mode = True
                previous = media_root / f'.before_restore_{stamp}'
                previous.mkdir()
                state['previous'] = previous
                self._move_children(media_root, previous, skip=previous.name)
            else:
                previous = (
                    media_root.parent
                    / f'{media_root.name}_before_restore_{stamp}')
                shutil.move(str(media_root), str(previous))
            # ΑΜΕΣΩΣ μετά το move, πριν από οτιδήποτε άλλο: από αυτό το
            # σημείο και μετά τα παλιά media ΔΕΝ είναι στη θέση τους. Αν
            # σκάσει το επόμενο stdout.write (κλειστό stream, σπασμένο pipe),
            # το rollback πρέπει να ξέρει πού βρίσκονται.
            state['previous'] = previous
            self.stdout.write(f'📋 Τα τρέχοντα media φυλάχθηκαν στο: {previous}')
        else:
            # Γράφεται ΠΡΙΝ το move των staged media: μόλις μπουν στη θέση
            # τους, το rollback πρέπει να ξέρει ότι πρέπει να τα αφαιρέσει.
            previous = NO_PREVIOUS_MEDIA
            state['previous'] = previous
        try:
            if contents_mode:
                self._move_children(staged_media, media_root)
            else:
                shutil.move(str(staged_media), str(media_root))
        except Exception:
            # Το move απέτυχε: γύρνα αμέσως τα προηγούμενα στη θέση τους
            # ώστε ο φάκελος media να μη μείνει ανύπαρκτος/μισός.
            if contents_mode:
                self._move_children(previous, media_root, skip=None)
                previous.rmdir()
                state['previous'] = None
            elif previous is not NO_PREVIOUS_MEDIA and not media_root.exists():
                shutil.move(str(previous), str(media_root))
                state['previous'] = None
            raise

    def _rollback_all(self, safety, previous_media, original_exc):
        """
        Αυτόματο rollback βάσης ΚΑΙ media μετά από αποτυχία post-restore.

        Ποτέ δεν βγαίνει μήνυμα επιτυχίας από εδώ: είτε γίνεται πλήρες
        rollback και η εντολή αποτυγχάνει, είτε αποτυγχάνει και το rollback
        και το μήνυμα δίνει τις ακριβείς διαδρομές για χειροκίνητη ενέργεια.
        """
        problems = []

        media_root = Path(settings.MEDIA_ROOT)
        if previous_media is NO_PREVIOUS_MEDIA:
            # Δεν υπήρχαν media πριν την επαναφορά: το rollback σημαίνει
            # «ξαναφτιάξε το τίποτα». Αν αφήναμε τα νέα media, η βάση θα
            # γύριζε πίσω αλλά τα αρχεία όχι — ακριβώς η ασυμφωνία που
            # προσπαθούμε να αποτρέψουμε.
            try:
                if media_root.exists():
                    try:
                        shutil.rmtree(media_root)
                    except OSError:
                        # Mountpoint: καθάρισε μόνο τα περιεχόμενα.
                        for child in media_root.iterdir():
                            shutil.rmtree(child, ignore_errors=True) \
                                if child.is_dir() else child.unlink()
            except Exception as exc:  # noqa: BLE001
                problems.append(
                    f'τα νέα media δεν αφαιρέθηκαν από το {media_root} ({exc})')
        elif previous_media is not None:
            try:
                if self._is_contents_mode(previous_media):
                    # Mountpoint mode: αφαίρεσε τα νέα περιεχόμενα και
                    # γύρνα πίσω τα παλιά από το .before_restore_ dir.
                    previous_media = Path(previous_media)
                    for child in media_root.iterdir():
                        if child.name == previous_media.name:
                            continue
                        shutil.rmtree(child, ignore_errors=True) \
                            if child.is_dir() else child.unlink()
                    self._move_children(previous_media, media_root)
                    previous_media.rmdir()
                else:
                    if media_root.exists():
                        shutil.rmtree(media_root, ignore_errors=True)
                    shutil.move(str(previous_media), str(media_root))
            except Exception as exc:  # noqa: BLE001
                problems.append(
                    f'τα προηγούμενα media παρέμειναν στο {previous_media} '
                    f'({exc})')

        kind, safety_path = safety
        if safety_path is None:
            problems.append('δεν υπήρχε αντίγραφο ασφαλείας βάσης')
        else:
            try:
                self._rollback_database(kind, safety_path)
            except Exception as exc:  # noqa: BLE001
                problems.append(
                    f'η βάση ΔΕΝ επαναφέρθηκε από το {safety_path} ({exc})')

        if problems:
            raise CommandError(
                f'❌ Η επαναφορά απέτυχε ({original_exc}) ΚΑΙ το αυτόματο '
                'rollback δεν ολοκληρώθηκε:\n  - ' + '\n  - '.join(problems)
                + '\nΑπαιτείται χειροκίνητη ενέργεια.'
            ) from original_exc

        raise CommandError(
            f'❌ Η επαναφορά απέτυχε: {original_exc}\n'
            '✅ Έγινε αυτόματο rollback: βάση και media επανήλθαν στην '
            'κατάσταση πριν την επαναφορά.'
        ) from original_exc

    def _rollback_database(self, kind, safety_path):
        db = settings.DATABASES['default']
        connections.close_all()
        if kind == 'sqlite':
            self._atomic_copy(safety_path, Path(db['NAME']))
            return
        pg_restore = shutil.which('pg_restore')
        if not pg_restore:
            raise RuntimeError('δεν βρέθηκε pg_restore')
        cmd = [pg_restore, '--clean', '--if-exists', '--single-transaction',
               '--format=custom', f"--dbname={db['NAME']}"]
        cmd += self._pg_conn_args(db)
        cmd.append(str(safety_path))
        result = subprocess.run(
            cmd, env=self._pg_env(db), capture_output=True, text=True,
            timeout=3600,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
