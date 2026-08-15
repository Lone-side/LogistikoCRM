#!/bin/bash
#
# Off-host backup του LogistikoCRM — μία εντολή, επαληθευμένο αντίγραφο.
#
# ΓΙΑΤΙ ΥΠΑΡΧΕΙ: το καθημερινό backup (Celery beat, 02:00) γράφει στον ΙΔΙΟ
# δίσκο με τη βάση. Βλάβη ή κλοπή του μηχανήματος τα παίρνει όλα μαζί. Το
# docs/GO_LIVE_2026-08-17.md §3 απαιτεί ρητά αντίγραφο σε ΔΕΥΤΕΡΟ φυσικό μέσο
# ή host — αντιγραφή σε άλλο φάκελο του ίδιου δίσκου ΔΕΝ μετράει.
#
# ΧΡΗΣΗ:
#   ./scripts/backup_offhost.sh /d/logistiko-backup
#   ./scripts/backup_offhost.sh //nas/backups/logistiko
#
# Τι κάνει, με τη σειρά:
#   1. Παίρνει ΦΡΕΣΚΟ backup μέσα στο web container
#   2. Το εξάγει από το named volume σε τοπικό staging
#   3. Υπολογίζει SHA-256 και τα επαληθεύει στο staging
#   4. Αντιγράφει στον προορισμό
#   5. Επαληθεύει ΞΑΝΑ τα checksums ΣΤΟΝ ΠΡΟΟΡΙΣΜΟ (εδώ πιάνονται τα
#      σιωπηλά σφάλματα αντιγραφής — το βήμα που παραλείπεται συνήθως)
#
# ΔΕΝ κρυπτογραφεί: το κλειδί είναι δική σου ευθύνη και δεν πρέπει να ζει σε
# script. Αν ο προορισμός δεν είναι ήδη κρυπτογραφημένος (BitLocker/VeraCrypt),
# κρυπτογράφησέ τον πριν τον αποσυνδέσεις.

set -euo pipefail

DEST="${1:-}"
if [ -z "$DEST" ]; then
    echo "ΧΡΗΣΗ: $0 <φάκελος-προορισμού>" >&2
    echo "π.χ.  $0 /d/logistiko-backup" >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(dirname "$SCRIPT_DIR")}"
STAGING="${STAGING:-$PROJECT_DIR/../logistikocrm-backup}"
PROJECT_NAME="${COMPOSE_PROJECT:-logistikocrm_office}"
ENV_FILE="${ENV_FILE:-certs/.env.office}"

COMPOSE=(docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE"
         -f docker-compose.prod.yml -f docker-compose.office.yml)

cd "$PROJECT_DIR"

step() { printf '\n=== %s ===\n' "$1"; }
fail() { printf '\n!!! %s\n' "$1" >&2; exit 1; }

# Ο προορισμός πρέπει να είναι ΑΛΛΟ μέσο. Δεν μπορούμε να το αποδείξουμε
# φορητά, αλλά πιάνουμε το προφανές λάθος: προορισμό μέσα στο ίδιο repo.
case "$(cd "$(dirname "$DEST")" 2>/dev/null && pwd || echo "$DEST")" in
    "$PROJECT_DIR"*)
        fail "Ο προορισμός είναι μέσα στο project. Αυτό ΔΕΝ είναι off-host backup." ;;
esac

step "1/5  Φρέσκο backup μέσα στο container"
"${COMPOSE[@]}" exec -T web python manage.py backup_database

step "2/5  Εξαγωγή από το volume -> $STAGING"
mkdir -p "$STAGING"
"${COMPOSE[@]}" cp web:/app/backups/. "$STAGING/"

step "3/5  Checksums στο staging"
cd "$STAGING"
sha256sum crm_db_* crm_media_* > SHA256SUMS
sha256sum -c SHA256SUMS || fail "Τα checksums δεν επαληθεύονται ΣΤΟ STAGING."

LATEST_DB=$(ls -1t crm_db_*.pgdump | head -1)
LATEST_MEDIA=$(ls -1t crm_media_*.tar.gz | head -1)
echo "Τελευταίο: $LATEST_DB + $LATEST_MEDIA"

step "4/5  Αντιγραφή -> $DEST"
mkdir -p "$DEST"
cp -v crm_db_* crm_media_* SHA256SUMS "$DEST/"

step "5/5  Επαλήθευση ΣΤΟΝ ΠΡΟΟΡΙΣΜΟ"
cd "$DEST"
sha256sum -c SHA256SUMS || fail "Τα checksums ΔΕΝ επαληθεύονται στον προορισμό — η αντιγραφή αλλοίωσε δεδομένα. ΜΗΝ αποσυνδέσεις το μέσο· ξανατρέξε."

cat <<EOF

========================================
 OK — επαληθευμένο αντίγραφο στον προορισμό
========================================
Προορισμός : $DEST
Database   : $LATEST_DB
Media      : $LATEST_MEDIA
Ημερομηνία : $(date -Iseconds)

ΕΠΟΜΕΝΑ ΒΗΜΑΤΑ (χειροκίνητα, go-live §3):
  [ ] Κρυπτογράφησε τον προορισμό αν δεν είναι ήδη
  [ ] ΑΠΟΣΥΝΔΕΣΕ το μέσο — backup που μένει συνδεδεμένο πέφτει μαζί με
      το μηχάνημα σε ransomware
  [ ] Σημείωσε ημερομηνία/θέση στο docs/GO_LIVE_2026-08-17.md §3
EOF
