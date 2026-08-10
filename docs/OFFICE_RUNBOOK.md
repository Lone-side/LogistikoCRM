# Office Runbook — Τοπική λειτουργία στο LAN του γραφείου

Οδηγός εγκατάστασης, αποδοχής (acceptance) και λειτουργίας του LogistikoCRM
σε server **μέσα στο LAN του λογιστικού γραφείου**, με πραγματικά δεδομένα,
εσωτερικό HTTPS και **καμία έκθεση στο Internet**.

Συμπληρώνει το [DEPLOYMENT.md](../DEPLOYMENT.md) — ό,τι δεν αναφέρεται εδώ
(migrations runbooks, restore λεπτομέρειες, χειροκίνητη εγκατάσταση) ισχύει
όπως εκεί.

> ⚠️ Τα `ΤΟΠΙΚΟ_ΔΙΚΤΥΟ.md` και `start_network.*` είναι ΜΟΝΟ για
> development (DEBUG=True, runserver, ανοιχτό CORS). **Ποτέ** με
> πραγματικά δεδομένα πελατών — γι' αυτά ισχύει αποκλειστικά ο παρών
> οδηγός.

---

## 1. Τοπολογία & απαιτήσεις

- Ένας server (Linux με Docker Engine + Docker Compose **≥ 2.24**) με
  **στατική LAN IP** (π.χ. `192.168.1.10`).
- Το CRM σερβίρεται ΜΟΝΟ στη LAN IP (`OFFICE_BIND_IP`) — το office
  compose profile αρνείται να ξεκινήσει χωρίς αυτήν και δεν δένει ποτέ
  σε `0.0.0.0`.
- Εσωτερικό hostname (default `crm.office.lan`) που αναλύεται από τους
  υπολογιστές του γραφείου:
  - είτε στο τοπικό DNS/router,
  - είτε με γραμμή στο hosts file κάθε υπολογιστή:
    `192.168.1.10  crm.office.lan`
    (Windows: `C:\Windows\System32\drivers\etc\hosts` ως Administrator,
    macOS/Linux: `/etc/hosts`).
- **Καμία** προώθηση πόρτας στο router, κανένα port forwarding, κανένα
  δημόσιο DNS record. Αν ο server έχει και δεύτερο interface προς
  Internet, βεβαιωθείτε ότι το `OFFICE_BIND_IP` είναι η LAN διεύθυνση.
- Το myDATA παραμένει **υποχρεωτικά σε sandbox** (`MYDATA_IS_SANDBOX=True`)
  — το preflight αποτυγχάνει διαφορετικά. Παραγωγική υποβολή μόνο μετά το
  [MYDATA_SANDBOX_TEST.md](MYDATA_SANDBOX_TEST.md) και συνειδητή απόφαση.

## 2. Πρώτη εγκατάσταση

```bash
git clone <repo> logistikocrm && cd logistikocrm

# 1. Environment
cp .env.office.example .env
nano .env    # OFFICE_BIND_IP, OFFICE_HOSTNAME, ALLOWED_HOSTS,
             # CSRF_TRUSTED_ORIGINS, SITE_URL + όλα τα secrets:
# SECRET_KEY:  python3 -c "import secrets; print(secrets.token_urlsafe(50))"
# DB_PASSWORD: openssl rand -hex 24
# FRITZ_API_TOKEN: openssl rand -hex 32
# DATA_ENCRYPTION_KEY_CURRENT: python3 scripts/generate_fernet_key.py

# 2. Εσωτερικό CA + server certificate (φάκελος ./certs, εκτός git)
./scripts/office_certs.sh crm.office.lan 192.168.1.10
# ⚠️ Το office-ca.key (CA private key) ΔΕΝ μπαίνει ποτέ σε container —
# το compose κάνει mount ΜΟΝΟ τα office.crt/office.key στο nginx.
# Φύλαξη του office-ca.key: μένει στον server με δικαιώματα 600 (το
# script τα ορίζει), και κρατήστε offline αντίγραφο (π.χ. κρυπτογραφημένο
# USB στο χρηματοκιβώτιο του γραφείου) — αν χαθεί, νέο CA σημαίνει
# επανεγκατάσταση σε ΟΛΟΥΣ τους υπολογιστές· αν διαρρεύσει, ο κάτοχος
# μπορεί να πλαστογραφήσει οποιοδήποτε site για τα μηχανήματα που το
# εμπιστεύονται (αμέσως αφαίρεση από όλα τα trust stores + νέο CA).

# 3. Build + εκκίνηση (πάντα και τα δύο -f, με αυτή τη σειρά)
docker compose -f docker-compose.prod.yml -f docker-compose.office.yml up -d --build
```

Η εκκίνηση του `web` τρέχει αυτόματα `migrate` + `createcachetable`.
Όλα τα services έχουν `restart: unless-stopped` — επανέρχονται μόνα τους
μετά από reboot (βλ. §5.7).

## 3. Εγκατάσταση του CA στους υπολογιστές του γραφείου

Μοιράστε το `certs/office-ca.crt` (ΜΟΝΟ το .crt — **ποτέ** τα .key
αρχεία) σε κάθε υπολογιστή:

**Windows** (Command Prompt ως Administrator):
```
certutil -addstore -f Root office-ca.crt
```
ή διπλό κλικ στο αρχείο → Install Certificate → Local Machine →
"Trusted Root Certification Authorities". Chrome/Edge το βλέπουν αμέσως.

**macOS**:
```
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain office-ca.crt
```
ή Keychain Access → System → εισαγωγή → Always Trust.

**Firefox** (δικό του store): Ρυθμίσεις → Απόρρητο & Ασφάλεια →
Πιστοποιητικά → Προβολή → Αρχές → Εισαγωγή του `office-ca.crt`
(✓ "Εμπιστοσύνη για ιστοσελίδες"). Εναλλακτικά, στο `about:config`:
`security.enterprise_roots.enabled = true` ώστε να διαβάζει το OS store.

Έλεγχος: `https://crm.office.lan/` ανοίγει **χωρίς** προειδοποίηση.

## 4. Αρχικοποίηση δεδομένων (μία φορά — Η ΣΕΙΡΑ ΕΧΕΙ ΣΗΜΑΣΙΑ)

Όπως στο DEPLOYMENT.md §Α.3, με το πλήρες compose prefix:

```bash
COMPOSE="docker compose -f docker-compose.prod.yml -f docker-compose.office.yml"

# 1. Fixtures + superuser IamSUPER (τυπώνει τον κωδικό του — ΦΥΛΑΞΤΕ τον)
$COMPOSE exec web python manage.py setupdata
# ⚠️ ΟΧΙ createsuperuser πριν το setupdata — χαλάει τα pk των groups.

# 2. RBAC role groups (Διαχειριστής / Λογιστής / Βοηθός)
$COMPOSE exec web python manage.py setup_roles

# 3. Ομάδες/προφίλ/τύποι υποχρεώσεων
$COMPOSE exec web python manage.py setup_obligations
```

Το `setup_obligations` είναι idempotent — επανεκτέλεση δεν δημιουργεί
διπλοεγγραφές. Δημιουργεί 1 ομάδα ΦΠΑ, 2 profiles (Μισθοδοσία,
Ενδοκοινοτικές) και 74 τύπους υποχρεώσεων: 23 πλήρως ρυθμισμένους και
51 του default catalog **χωρίς** προσυμπληρωμένη περιοδικότητα/προθεσμία
— αυτά τα ρυθμίζει ο λογιστής πριν την αυτόματη δημιουργία υποχρεώσεων
(μέχρι τότε είναι διαθέσιμα μόνο για χειροκίνητη επιλογή ανά πελάτη).

Μετά, από το admin (`https://crm.office.lan/el/456-admin/`):
1. **Αλλάξτε αμέσως τον κωδικό του IamSUPER.**
2. Δημιουργήστε προσωπικό λογαριασμό για κάθε χρήστη (ποτέ κοινόχρηστος).
3. Βάλτε κάθε χρήστη στο σωστό role group.
4. Αναθέστε πελάτες (Προφίλ Πελάτη → Ανάθεση) — με
   `ENFORCE_CLIENT_ASSIGNMENT=True` οι χρήστες βλέπουν ΜΟΝΟ
   ανατεθειμένους πελάτες (οι superusers τα πάντα).

## 5. Acceptance checklist

Εκτελέστε με τη σειρά· κάθε βήμα έχει αναμενόμενο αποτέλεσμα. Στο τέλος
όλα πρέπει να είναι ✅ πριν μπουν πραγματικά δεδομένα.

Ορίστε πρώτα: `COMPOSE="docker compose -f docker-compose.prod.yml -f docker-compose.office.yml"`

| # | Δοκιμή | Εντολή / ενέργεια | Αναμενόμενο |
|---|--------|--------------------|-------------|
| 5.1 | Preflight | `./scripts/office_preflight.sh` | «όλα πράσινα» (το backup-age είναι WARN μέχρι το πρώτο backup) |
| 5.2 | HTTPS χωρίς loop | Άνοιγμα `http://crm.office.lan/` | 301 σε `https://` και φόρτωση χωρίς προειδοποίηση cert |
| 5.3 | SMTP (ελεγχόμενο) | `$COMPOSE exec web python manage.py sendtestemail <δικό-σας-inbox>` | Το email φτάνει· ο αποστολέας είναι το `DEFAULT_FROM_EMAIL` |
| 5.4 | Upload/Download | UI: ανέβασμα δοκιμαστικού PDF σε δοκιμαστικό πελάτη → κατέβασμα → διαγραφή | Και τα δύο επιτυχή μέσω HTTPS (X-Accel-Redirect path) |
| 5.5 | Scheduled tasks | `$COMPOSE exec web celery -A webcrm call accounting.tasks.backup_database_task` και μετά `$COMPOSE exec web python manage.py restore_database --list` | Εμφανίζεται φρέσκο `crm_db_*` (αποδεικνύει broker→worker→volume)· το κανονικό backup τρέχει αυτόματα 02:00 |
| 5.6 | Restore σε trial | Βλ. §6 — ΠΟΤΕ restore δοκιμής στην κανονική εγκατάσταση | Η trial εγκατάσταση δείχνει τα δεδομένα του backup |
| 5.7 | Reboot | `sudo systemctl is-enabled docker` (πρέπει `enabled`) → `sudo reboot` → μετά την επανεκκίνηση `./scripts/office_preflight.sh` | Όλα τα services επανήλθαν μόνα τους, preflight πράσινο |

## 6. Δοκιμή restore σε ξεχωριστή trial εγκατάσταση

Η πρόβα restore γίνεται σε **δεύτερη, ανεξάρτητη** εγκατάσταση — ποτέ
στην παραγωγική:

```bash
# Ξεχωριστός φάκελος + project name ⇒ ξεχωριστά volumes/δίκτυο
git clone <repo> logistiko-trial && cd logistiko-trial
cp ../logistikocrm/.env .env
echo "COMPOSE_PROJECT_NAME=logistiko_trial" >> .env
echo "HTTP_PORT=127.0.0.1:8080" >> .env   # loopback μόνο, χωρίς office overlay

# Trial με ΣΚΕΤΟ το prod compose (χωρίς -f office — δεν χρειάζεται TLS/LAN)
docker compose -f docker-compose.prod.yml up -d --build

# Αντιγραφή του backup από την παραγωγική στο trial backups volume
docker compose -f docker-compose.prod.yml cp \
  ../logistikocrm-backup/crm_db_<timestamp>.pgdump web:/app/backups/

# Restore με τη σειρά του DEPLOYMENT.md (maintenance window της trial)
docker compose -f docker-compose.prod.yml stop web celery celery-beat nginx
docker compose -f docker-compose.prod.yml run --rm web \
  python manage.py restore_database --latest
docker compose -f docker-compose.prod.yml up -d

# Έλεγχος: http://127.0.0.1:8080 → τα δεδομένα του backup υπάρχουν
# Καθάρισμα: docker compose -f docker-compose.prod.yml down -v
```

Το αρχείο backup της παραγωγικής βρίσκεται στο named volume
`backups_volume` — εξαγωγή π.χ.:
`docker compose -f docker-compose.prod.yml -f docker-compose.office.yml cp web:/app/backups/. ../logistikocrm-backup/`

Κρατάτε αντίγραφα των backups ΚΑΙ εκτός server (βλ. DEPLOYMENT.md §Backups).

## 7. Περιοδική λειτουργία

- **Μετά από κάθε αλλαγή** (update, .env, certs): `./scripts/office_preflight.sh`.
- **Ενημέρωση έκδοσης**: όπως DEPLOYMENT.md §Ενημέρωση, με το πλήρες
  compose prefix (`-f docker-compose.prod.yml -f docker-compose.office.yml`).
- **Certificate renewal**: το server cert λήγει σε ~820 μέρες. Πριν τη
  λήξη: `./scripts/office_certs.sh crm.office.lan 192.168.1.10` (το CA
  διατηρείται — οι υπολογιστές του γραφείου ΔΕΝ χρειάζονται τίποτα) και
  restart του nginx service. ⚠️ Με ληγμένο cert οι browsers μπλοκάρουν
  σκληρά λόγω HSTS.
- **Πρόβα restore** στην trial εγκατάσταση: τουλάχιστον 2 φορές τον χρόνο.
- **CA private key**: παραμένει ΜΟΝΟ στον server (0600) + offline
  αντίγραφο — ποτέ σε container, email ή shared φάκελο (βλ. §2).

## 8. Troubleshooting

| Σύμπτωμα | Πιθανή αιτία / λύση |
|----------|---------------------|
| Ατέρμονο redirect (`ERR_TOO_MANY_REDIRECTS`) | `USE_X_FORWARDED_PROTO` δεν είναι `True` στο `.env` — το overlay το επιβάλλει, ελέγξτε ότι τρέχετε ΚΑΙ με το `-f docker-compose.office.yml` |
| CSRF 403 στο login/φόρμες | `CSRF_TRUSTED_ORIGINS` χωρίς το `https://` origin που χρησιμοποιείτε (hostname ΚΑΙ IP) |
| Προειδοποίηση certificate στον browser | Το `office-ca.crt` δεν έχει εγκατασταθεί σε αυτόν τον υπολογιστή (Firefox: δικό του store — βλ. §3) |
| `web` container unhealthy | `$COMPOSE exec web python manage.py office_preflight` για τη ρίζα· αν `local-health` δείχνει redirect → regression του `SECURE_REDIRECT_EXEMPT` |
| Compose error για `!override` | Docker Compose < 2.24 — αναβάθμιση |
| `DisallowedHost` | Το hostname/IP λείπει από `ALLOWED_HOSTS` στο `.env` |
