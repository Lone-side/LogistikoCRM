#!/usr/bin/env bash
# LogistikoCRM — Δημιουργία εσωτερικού CA + server certificate για το
# office/LAN HTTPS profile (nginx/office.conf).
#
# Χρήση:
#   ./scripts/office_certs.sh <hostname> <ip> [επιπλέον DNS ή IP ...]
#   π.χ. ./scripts/office_certs.sh crm.office.lan 192.168.1.10
#
# Παράγει στο ./certs/ (ο φάκελος είναι στο .gitignore — ΠΟΤΕ commit):
#   office-ca.key / office-ca.crt   — το CA του γραφείου (5 χρόνια).
#                                     Το .crt εγκαθίσταται στους
#                                     υπολογιστές του γραφείου
#                                     (βλ. docs/OFFICE_RUNBOOK.md).
#   office.key / office.crt         — το server certificate (820 μέρες,
#                                     κάτω από το όριο των 825 που
#                                     δέχονται τα Apple/σύγχρονα browsers)
#                                     με SAN για όλα τα ορίσματα.
#
# Υπάρχον CA ΔΕΝ ξαναγράφεται (τα εγκατεστημένα certs στους clients θα
# αχρηστεύονταν) — μόνο με --force-ca. Το server cert ξαναγράφεται πάντα
# (renewal με το ίδιο CA δεν χρειάζεται αλλαγή στους clients).
set -euo pipefail

FORCE_CA=0
if [ "${1:-}" = "--force-ca" ]; then
    FORCE_CA=1
    shift
fi

if [ "$#" -lt 2 ]; then
    echo "Χρήση: $0 [--force-ca] <hostname> <ip> [επιπλέον DNS ή IP ...]" >&2
    echo "  π.χ. $0 crm.office.lan 192.168.1.10" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CERT_DIR="$(dirname "$SCRIPT_DIR")/certs"
HOSTNAME_MAIN="$1"

mkdir -p "$CERT_DIR"
chmod 700 "$CERT_DIR"

# SAN list: DNS για ονόματα, IP για διευθύνσεις
SAN=""
for entry in "$@"; do
    if printf '%s' "$entry" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
        SAN="${SAN},IP:${entry}"
    else
        SAN="${SAN},DNS:${entry}"
    fi
done
SAN="${SAN#,}"

CA_KEY="$CERT_DIR/office-ca.key"
CA_CRT="$CERT_DIR/office-ca.crt"

if [ -f "$CA_CRT" ] && [ "$FORCE_CA" -ne 1 ]; then
    echo "==> Υπάρχον CA ($CA_CRT) — διατηρείται (χρήση --force-ca για αντικατάσταση)"
else
    echo "==> Δημιουργία CA γραφείου (5 χρόνια)"
    openssl genrsa -out "$CA_KEY" 4096
    chmod 600 "$CA_KEY"
    openssl req -x509 -new -nodes -key "$CA_KEY" -sha256 -days 1825 \
        -subj "/CN=LogistikoCRM Office CA/O=Logistiko Office" \
        -out "$CA_CRT"
fi

echo "==> Δημιουργία server certificate για: $SAN (820 μέρες)"
SRV_KEY="$CERT_DIR/office.key"
SRV_CSR="$CERT_DIR/office.csr"
SRV_CRT="$CERT_DIR/office.crt"

openssl genrsa -out "$SRV_KEY" 2048
chmod 600 "$SRV_KEY"
openssl req -new -key "$SRV_KEY" \
    -subj "/CN=${HOSTNAME_MAIN}/O=Logistiko Office" \
    -out "$SRV_CSR"
openssl x509 -req -in "$SRV_CSR" -CA "$CA_CRT" -CAkey "$CA_KEY" \
    -CAcreateserial -days 820 -sha256 \
    -extfile <(printf 'subjectAltName=%s\nextendedKeyUsage=serverAuth\n' "$SAN") \
    -out "$SRV_CRT"
rm -f "$SRV_CSR"

echo ""
echo "Έτοιμα στο $CERT_DIR:"
echo "  - office-ca.crt  → εγκατάσταση στους υπολογιστές του γραφείου"
echo "                     (Windows: certutil -addstore -f Root office-ca.crt)"
echo "                     (βλ. docs/OFFICE_RUNBOOK.md για macOS/Firefox)"
echo "  - office.crt/key → τα διαβάζει το nginx (docker-compose.office.yml)"
echo ""
echo "Επόμενο βήμα: docker compose -f docker-compose.prod.yml -f docker-compose.office.yml up -d"
