# 🚀 LogistikoCRM — Οδηγός Production Deployment

Ο προτεινόμενος τρόπος είναι **Docker Compose** σε έναν server (VPS ή μηχάνημα γραφείου): PostgreSQL + Redis + Django/gunicorn + Celery + nginx, όλα με μία εντολή.

## Α. Deployment με Docker Compose (προτεινόμενο)

### Προαπαιτούμενα

- Linux server (Ubuntu 22.04+ / Debian 12+) με Docker & Docker Compose plugin
- (Προαιρετικά) domain name που δείχνει στον server

### 1. Κλωνοποίηση & ρύθμιση

```bash
git clone <repo-url> LogistikoCRM
cd LogistikoCRM
cp .env.production.example .env
nano .env
```

Υποχρεωτικά στο `.env`:

| Μεταβλητή | Τι βάζεις |
|---|---|
| `DJANGO_ENV` | `production` — **δεν αντικαθίσταται από το `DEBUG=False`** (βλ. σημείωση παρακάτω) |
| `SECRET_KEY` | `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DB_PASSWORD` | Ισχυρός κωδικός PostgreSQL |
| `SITE_URL` | π.χ. `https://crm.example.gr` (μπαίνει σε emails/links) |
| `ALLOWED_HOSTS` | π.χ. `crm.example.gr` |
| `FRITZ_API_TOKEN` | `openssl rand -hex 32` — υποχρεωτικό ακόμη κι αν δεν χρησιμοποιείς Fritz!Box |

> Με `DEBUG=False` το app **αρνείται να ξεκινήσει** αν τα `SECRET_KEY`/`FRITZ_API_TOKEN` έχουν μείνει στα defaults — αυτό είναι σκόπιμο (security hard-fail).

> ### ⚠️ `DJANGO_ENV=production` — γιατί δεν αρκεί το `DEBUG=False`
>
> Το `manage.py` φορτώνει `webcrm.settings_local`, και εκείνο διαλέγει
> development ή production branch **αποκλειστικά από το `DJANGO_ENV`**.
> Στο development branch επιβάλλει `DEBUG = True` γράφοντας πάνω από ό,τι
> έχεις ορίσει στο `DEBUG`. Δηλαδή:
>
> ```bash
> DEBUG=False python manage.py migrate        # ❌ τρέχει με DEBUG=True
> DJANGO_ENV=production python manage.py migrate   # ✅
> ```
>
> Το `settings_local` δέχεται **μόνο** `production` ή `development` και
> αποτυγχάνει κλειστά σε οτιδήποτε άλλο:
>
> | `DJANGO_ENV` | `DEBUG` (env) | Αποτέλεσμα |
> |---|---|---|
> | `production` | οτιδήποτε | production· `DEBUG=False`, secure cookies, HSTS |
> | `development` | οτιδήποτε | development |
> | `  ProDuction  ` | — | production (γίνεται trim + lowercase) |
> | `prod`, `prodction`, `staging`, κενό | — | **`ImproperlyConfigured`** |
> | *απών* | `True` (ρητό) | development |
> | *απών* | `False` ή απών | **`ImproperlyConfigured`** |
> | *απών* | — (test runner) | development — τα tests τρέχουν χωρίς env setup |
>
> **Ιστορικό — γιατί υπάρχει αυτός ο έλεγχος.** Παλιότερα η προεπιλογή
> ήταν σιωπηλά `development`, οπότε απών ή λάθος γραμμένο `DJANGO_ENV`
> έδινε `DEBUG=True`, `ALLOWED_HOSTS=['*']`, χωρίς secure cookies/HSTS —
> και, το σοβαρότερο, τα `/media/` σερβίρονταν **ελεύθερα** από το
> `static()` αντί για το authenticated `serve_protected_media`, δηλαδή
> έγγραφα πελατών χωρίς login. Τα fail-closed guards
> (`FRITZ_API_TOKEN`, `DATA_ENCRYPTION_KEY_CURRENT`,
> `ENFORCE_CLIENT_ASSIGNMENT`) **δεν** έπιαναν το πρόβλημα: κρίνονται από
> το `DEBUG` env var μέσα στο `settings.py`. Η εφαρμογή ξεκινούσε
> κανονικά και έμοιαζε σωστά ρυθμισμένη — γι' αυτό πλέον σκάει αντί να
> μαντεύει.
>
> Έλεγχος:
>
> ```bash
> DJANGO_ENV=production python manage.py shell -c \
>   "from django.conf import settings; print(settings.DEBUG)"   # → False
> ```
>
> Το `docker-compose.prod.yml` το ορίζει ήδη, οπότε η προτεινόμενη Docker
> εγκατάσταση δεν επηρεάζεται. **Αφορά τη χειροκίνητη εγκατάσταση** και
> κάθε `manage.py` εντολή που τρέχεις με το χέρι στον server (migrate,
> collectstatic, createcachetable, backup_database, restore_database).

### 2. Εκκίνηση

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Το build φτιάχνει και το React frontend (multi-stage) — δεν χρειάζεται Node στον server.

### 3. Αρχικοποίηση δεδομένων (μία φορά)

```bash
# Η ΣΕΙΡΑ ΕΧΕΙ ΣΗΜΑΣΙΑ — τα migrations τρέχουν αυτόματα στο πρώτο up
docker compose -f docker-compose.prod.yml exec web python manage.py createcachetable
docker compose -f docker-compose.prod.yml exec web python manage.py setupdata
# ⚠️ ΟΧΙ createsuperuser πριν το setupdata — δημιουργεί τον superuser IamSUPER
#    και τυπώνει τον κωδικό του στην κονσόλα
```

### 4. Έλεγχος

- React app: `http://<server>/`
- CRM: `http://<server>/el/123/` — Admin: `http://<server>/el/456-admin/`
- Health: `http://<server>/api/health/detailed/`

### 5. HTTPS

Βάλε certbot ή έναν HTTPS reverse proxy (Caddy/Traefik/Cloudflare) μπροστά από το nginx (port 80) και στο `.env`:

```bash
CSRF_TRUSTED_ORIGINS=https://crm.example.gr
USE_X_FORWARDED_PROTO=True
SITE_URL=https://crm.example.gr
```

Με `DEBUG=False` το Django ενεργοποιεί αυτόματα HSTS, secure cookies και SSL redirect.

## Ασφάλεια αρχείων (media)

Σε production **τα αρχεία πελατών ΔΕΝ σερβίρονται δημόσια**:

- Κάθε αίτημα `/media/...` περνά από authenticated Django view (συνδεδεμένος χρήστης **ή** signed URL με λήξη — `?mt=...`, default 4 ώρες, ρύθμιση `MEDIA_TOKEN_MAX_AGE`).
- Το nginx στέλνει το αρχείο μέσω `X-Accel-Redirect` από internal location (`MEDIA_ACCEL_REDIRECT=True` στο prod compose) — το Django κάνει μόνο τον έλεγχο, όχι το I/O.
- Τα SharedLink downloads του portal πελατών έχουν δικό τους έλεγχο (password/λήξη) και δεν επηρεάζονται.

## Backups

- Αυτόματο backup βάσης καθημερινά 02:00 (Celery beat → `backup_database`), στο volume `backups_volume` (`/app/backups`).
- Μαζί με τη βάση γίνεται backup και των media (`crm_media_<ts>.tar.gz`) — τα έγγραφα πελατών. Παράλειψη με `--skip-media`.
- PostgreSQL: χρησιμοποιείται `pg_dump --format=custom` (αρχεία `.pgdump`).
- Χειροκίνητο: `docker compose -f docker-compose.prod.yml exec web python manage.py backup_database`
- Επαναφορά (βάση + media, με αντίγραφο ασφαλείας του τρέχοντος πριν την αντικατάσταση).

  ⚠️ **Η επαναφορά γίνεται ΜΟΝΟ σε παράθυρο συντήρησης, με το web και τους Celery workers σταματημένους.**
  Η εντολή αντικαθιστά ολόκληρη τη βάση και ολόκληρο τον φάκελο media. Αν την ώρα της επαναφοράς τρέχει
  έστω ένα request ή ένα Celery task, τότε: γράφει σε βάση που αντικαθίσταται (οι εγγραφές χάνονται χωρίς
  ίχνος), κρατά ανοιχτά connections που εμποδίζουν το `pg_restore`, ή διαβάζει media από φάκελο που
  μετακινείται κάτω από τα πόδια του. Το αποτέλεσμα είναι βάση και αρχεία που δεν συμφωνούν — ακριβώς
  αυτό που η επαναφορά υποτίθεται ότι διορθώνει.

  ```bash
  cd /opt/logistikocrm
  # 1. Δες τι υπάρχει (δεν αλλάζει τίποτα — μπορεί να τρέξει και με το σύστημα ζωντανό)
  docker compose -f docker-compose.prod.yml exec web python manage.py restore_database --list

  # 2. Σταμάτα ό,τι γράφει: web + workers + beat. Η βάση μένει πάνω.
  docker compose -f docker-compose.prod.yml stop web celery celery-beat nginx

  # 3. Επαναφορά (χρειάζεται προσωρινά το web container μόνο για την εντολή)
  docker compose -f docker-compose.prod.yml run --rm web python manage.py restore_database --latest

  # 4. Ξανά πάνω
  docker compose -f docker-compose.prod.yml up -d
  ```
- ⚠️ **Δοκίμασε την επαναφορά σε staging πριν τη χρειαστείς στα αλήθεια** — ένα backup που δεν έχει επαναφερθεί ποτέ δεν είναι backup.
- ⚠️ Κράτα αντίγραφα των volumes `media_volume` και `backups_volume` και **εκτός** server (rsync/rclone).

## Ενημέρωση σε νέα έκδοση

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build   # τρέχει migrations αυτόματα
```

## Migrations 10020/10021 (slot + document invariants) — runbook

Τα migrations `10020_clientdocument_slot_and_current_constraints` και
`10021_fix_legacy_slot_chains` αγγίζουν ιστορικά `ClientDocument` rows.

**1. Backup πριν από οτιδήποτε**

```bash
pg_dump -Fc -f pre_10020_$(date +%F_%H%M).dump "$DATABASE_URL"
tar czf archive_root_$(date +%F).tar.gz "$ARCHIVE_ROOT"
```

**2. Rehearsal σε αντίγραφο της πραγματικής βάσης** (μέγεθος + χρόνος)

```bash
psql "$STAGING_URL" -c "SELECT COUNT(*) FROM accounting_clientdocument;"
time python manage.py migrate --noinput
python manage.py audit_clientdocument_invariants > audit_after.txt
```

**3. Ερμηνεία του audit**

| Περιβάλλον | Εντολή | Blocking; |
|---|---|---|
| CI (φρέσκια/κενή βάση) | `audit_clientdocument_invariants --fail-on-findings` | **ΝΑΙ** |
| Production rehearsal / deploy | `audit_clientdocument_invariants` (**χωρίς** flag) | **ΟΧΙ** — αποθήκευση output + χειροκίνητη αξιολόγηση |

Τα findings `legacy-slot-needs-review` είναι **αναμενόμενα** μετά τα
10020/10021 σε βάση με ιστορικά duplicates: το migration μετέφερε τις
αμφίβολες chains σε legacy slot και άφησε το κύριο slot (`''`) ελεύθερο.
Απαιτούν χειροκίνητη επιβεβαίωση, **δεν** μπλοκάρουν το deployment.

Blocking είναι μόνο: αποτυχία του ίδιου του `migrate`, ή **απρόσμενες**
κατηγορίες findings — `cross-client-obligation`,
`cross-client-previous-version`, `version-graph-cycle`,
`duplicate-current-for-key`, `missing-storage-file`.

**4. Components με πολλαπλά current**

Το `10021` **δεν αγγίζει** connected component που περιέχει πάνω από ένα
`is_current=True` row (branching chain): διατηρεί την constraint-safe
κατάσταση του `10020` και το αναφέρει ως `branching-chain` /
`multiple-current-in-chain`. Ποιο branch είναι το «σωστό» δεν μπορεί να
προκύψει αυτόματα — απαιτείται χειροκίνητη απόφαση από το γραφείο.

**4β. Βάσεις όπου το 10021 έχει ΗΔΗ εφαρμοστεί**

Το `10021` είναι `RunPython`: μια βάση που το έχει ήδη applied **δεν
ξανατρέχει** τη διορθωμένη λογική. Γι' αυτό υπάρχει το
`10023_repair_legacy_slot_chains`, που εκτελεί ακόμη μία φορά την ίδια
(idempotent) διορθωμένη συνάρτηση. Σε βάση που τρέχει πρώτη φορά την
αλυσίδα, το 10023 είναι no-op.

**4γ. `10022_sharedlink_target_invariant` — data mutation**

Κανονικοποιεί legacy `SharedLink` rows **χωρίς διαγραφές**:

| Κατάσταση | Ενέργεια |
|---|---|
| document + client, **ίδιος** πελάτης | canonical το document, καθαρίζεται το `client` |
| document + client, **διαφορετικοί** πελάτες | **απενεργοποίηση**, κρατά και τα δύο για χειροκίνητο έλεγχο |
| ενεργό link χωρίς στόχο (orphan) | **απενεργοποίηση** |

Μετά το deploy, έλεγξε τα warnings του migration (μόνο internal IDs) και
επιβεβαίωσε ποια links απενεργοποιήθηκαν:

```bash
python manage.py shell -c "
from accounting.models import SharedLink
qs = SharedLink.objects.filter(is_active=False)
print('ανενεργά links:', list(qs.values_list('id', flat=True)))"
```

**5. Rollback criteria**

* `migrate` exit ≠ 0 → επαναφορά από το dump, **όχι** χειροκίνητο fix-forward.
* Νέα κατηγορία findings στο `audit_after.txt` πέρα από τα legacy.
* Οποιοδήποτε 500 στα document endpoints κατά το smoke test.

## Β. Χειροκίνητη εγκατάσταση (χωρίς Docker)

<details>
<summary>Οδηγίες για systemd + nginx στον host</summary>

1. Σύστημα: `sudo apt install -y python3.11 python3-venv postgresql redis-server nginx libpq-dev libmagic1`
2. Κώδικας σε `/var/www/LogistikoCRM`, venv, `pip install -r requirements.txt gunicorn`
3. Frontend: `cd frontend && npm ci && npm run build` (θέλει Node 20) — σέρβιρε το `frontend/dist` από το nginx
4. `.env` όπως παραπάνω + `DJANGO_ENV=production`, `DB_ENGINE=django.db.backends.postgresql`, `DB_HOST=localhost`, `MEDIA_ACCEL_REDIRECT=True`
   - ⚠️ Το `DJANGO_ENV=production` είναι **υποχρεωτικό εδώ**. Χωρίς αυτό κάθε `manage.py` εντολή τρέχει σε development mode με `DEBUG=True`, ακόμη κι αν το `.env` λέει `DEBUG=False` — βλ. τη σημείωση στην ενότητα Α.
   - Οι systemd units (βήμα 7) πρέπει επίσης να το εξάγουν, π.χ. μέσω `EnvironmentFile=/var/www/LogistikoCRM/.env`, ώστε να το βλέπουν gunicorn, worker και beat.
5. `export DJANGO_ENV=production` και μετά `python manage.py migrate && python manage.py createcachetable && python manage.py setupdata && python manage.py collectstatic --noinput`
   - Επαλήθευση πριν προχωρήσεις: `python manage.py shell -c "from django.conf import settings; print(settings.DEBUG)"` πρέπει να τυπώνει `False`.
6. nginx: προσάρμοσε το `nginx/nginx.conf` (άλλαξε το `upstream django` σε `127.0.0.1:8000`, τα alias σε πραγματικά paths, το `/protected-media/` alias στο MEDIA_ROOT)
7. systemd units για gunicorn, `celery -A webcrm worker` και `celery -A webcrm beat`

</details>

## Production Checklist

- [ ] `SECRET_KEY` μοναδικό, εκτός git
- [ ] `DJANGO_ENV=production` στο περιβάλλον **και** στα systemd units — όχι μόνο `DEBUG=False` (το `settings_local` αποφασίζει από το `DJANGO_ENV`)
- [ ] `DEBUG=False` (default στο prod compose)
- [ ] `ALLOWED_HOSTS` + `CSRF_TRUSTED_ORIGINS` με το domain
- [ ] HTTPS ενεργό + `USE_X_FORWARDED_PROTO=True`
- [ ] `setupdata` έτρεξε & αποθηκεύτηκε ο κωδικός του IamSUPER
- [ ] Email SMTP ρυθμισμένο (δοκιμή: υπενθυμίσεις προθεσμιών)
- [ ] Backups εκτός server
- [ ] `/api/health/detailed/` πράσινο
