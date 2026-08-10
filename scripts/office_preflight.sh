#!/usr/bin/env bash
# LogistikoCRM — Host-level office preflight wrapper.
#
# Τρέχει από τον φάκελο του project στον office server:
#   ./scripts/office_preflight.sh [--max-backup-age-hours N]
#
# Ελέγχει (read-only):
#   1. Έκδοση Docker Compose (>= 2.24 για το !override του overlay)
#   2. Ότι και τα 6 services τρέχουν και τα health-checked είναι healthy
#   3. Ελεύθερο χώρο δίσκου στον host
#   4. End-to-end HTTPS: TLS chain + κανένα redirect loop
#   5. Τους in-container ελέγχους (manage.py office_preflight)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

COMPOSE="docker compose -f docker-compose.prod.yml -f docker-compose.office.yml"
FAILURES=0

fail() { echo "[FAIL] $1"; FAILURES=$((FAILURES + 1)); }
ok()   { echo "[OK]   $1"; }
warn() { echo "[WARN] $1"; }

# ---- 1. Compose version (>= 2.24 για !override) ----
COMPOSE_VERSION="$(docker compose version --short 2>/dev/null || echo 0)"
MAJOR="${COMPOSE_VERSION%%.*}"
MINOR="$(echo "$COMPOSE_VERSION" | cut -d. -f2)"
if [ "${MAJOR:-0}" -gt 2 ] || { [ "${MAJOR:-0}" -eq 2 ] && [ "${MINOR:-0}" -ge 24 ]; }; then
    ok "docker compose $COMPOSE_VERSION (>= 2.24)"
else
    fail "docker compose $COMPOSE_VERSION — απαιτείται >= 2.24 (YAML !override)"
fi

# ---- 2. Κατάσταση containers ----
PS_OUTPUT="$($COMPOSE ps 2>/dev/null || true)"
for service in db redis web celery celery-beat nginx; do
    line="$(echo "$PS_OUTPUT" | grep -E "(^|[-_ ])${service}([-_ ]|\s)" | head -1 || true)"
    if [ -z "$line" ]; then
        fail "service ${service}: δεν τρέχει"
        continue
    fi
    case "$line" in
        *"(healthy)"*)   ok "service ${service}: running (healthy)" ;;
        *"(unhealthy)"*) fail "service ${service}: UNHEALTHY" ;;
        *"(health"*)     warn "service ${service}: health check σε εξέλιξη" ;;
        *Up*|*running*)  ok "service ${service}: running" ;;
        *)               fail "service ${service}: $line" ;;
    esac
done

# ---- 3. Host disk ----
DISK_USED="$(df -P "$PROJECT_DIR" | awk 'NR==2 {gsub("%",""); print $5}')"
if [ "${DISK_USED:-100}" -ge 90 ]; then
    fail "host disk: ${DISK_USED}% σε χρήση"
elif [ "${DISK_USED:-100}" -ge 80 ]; then
    warn "host disk: ${DISK_USED}% σε χρήση"
else
    ok "host disk: ${DISK_USED}% σε χρήση"
fi

# ---- 4. End-to-end HTTPS (TLS chain + όχι redirect loop) ----
OFFICE_HOSTNAME="$(grep -E '^OFFICE_HOSTNAME=' .env 2>/dev/null | cut -d= -f2- || true)"
OFFICE_BIND_IP="$(grep -E '^OFFICE_BIND_IP=' .env 2>/dev/null | cut -d= -f2- || true)"
if [ -n "$OFFICE_HOSTNAME" ] && [ -n "$OFFICE_BIND_IP" ] && [ -f certs/office-ca.crt ]; then
    # --noproxy: ο έλεγχος αφορά την εσωτερική LAN διεύθυνση — δεν πρέπει
    # ποτέ να δρομολογηθεί μέσω system/corporate proxy (θα αποτύγχανε
    # ψευδώς αφού το hostname δεν υπάρχει έξω από το LAN).
    HTTP_CODE="$(curl -s -o /dev/null -w '%{http_code}' \
        --noproxy '*' \
        --cacert certs/office-ca.crt \
        --resolve "${OFFICE_HOSTNAME}:443:${OFFICE_BIND_IP}" \
        --max-time 10 \
        "https://${OFFICE_HOSTNAME}/api/health/" || echo 000)"
    if [ "$HTTP_CODE" = "200" ]; then
        ok "https://${OFFICE_HOSTNAME}/api/health/ → 200 (TLS chain OK)"
    else
        fail "https://${OFFICE_HOSTNAME}/api/health/ → HTTP ${HTTP_CODE}"
    fi
else
    warn "παράλειψη HTTPS ελέγχου (λείπει OFFICE_HOSTNAME/OFFICE_BIND_IP στο .env ή certs/office-ca.crt)"
fi

# ---- 5. In-container preflight ----
if $COMPOSE exec -T web python manage.py office_preflight --fail-on-findings "$@"; then
    ok "in-container office_preflight"
else
    fail "in-container office_preflight (βλ. παραπάνω)"
fi

echo ""
if [ "$FAILURES" -gt 0 ]; then
    echo "Αποτέλεσμα: $FAILURES αποτυχίες."
    exit 1
fi
echo "Αποτέλεσμα: όλα πράσινα."
