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
| `SECRET_KEY` | `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DB_PASSWORD` | Ισχυρός κωδικός PostgreSQL |
| `SITE_URL` | π.χ. `https://crm.example.gr` (μπαίνει σε emails/links) |
| `ALLOWED_HOSTS` | π.χ. `crm.example.gr` |
| `FRITZ_API_TOKEN` | `openssl rand -hex 32` — υποχρεωτικό ακόμη κι αν δεν χρησιμοποιείς Fritz!Box |

> Με `DEBUG=False` το app **αρνείται να ξεκινήσει** αν τα `SECRET_KEY`/`FRITZ_API_TOKEN` έχουν μείνει στα defaults — αυτό είναι σκόπιμο (security hard-fail).

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
- PostgreSQL: χρησιμοποιείται `pg_dump --format=custom` (αρχεία `.pgdump`). Επαναφορά: `pg_restore -d logistikocrm crm_db_<ts>.pgdump`
- Χειροκίνητο: `docker compose -f docker-compose.prod.yml exec web python manage.py backup_database`
- ⚠️ Κράτα αντίγραφα των volumes `media_volume` και `backups_volume` και **εκτός** server (rsync/rclone).

## Ενημέρωση σε νέα έκδοση

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build   # τρέχει migrations αυτόματα
```

## Β. Χειροκίνητη εγκατάσταση (χωρίς Docker)

<details>
<summary>Οδηγίες για systemd + nginx στον host</summary>

1. Σύστημα: `sudo apt install -y python3.11 python3-venv postgresql redis-server nginx libpq-dev libmagic1`
2. Κώδικας σε `/var/www/LogistikoCRM`, venv, `pip install -r requirements.txt gunicorn`
3. Frontend: `cd frontend && npm ci && npm run build` (θέλει Node 20) — σέρβιρε το `frontend/dist` από το nginx
4. `.env` όπως παραπάνω + `DB_ENGINE=django.db.backends.postgresql`, `DB_HOST=localhost`, `MEDIA_ACCEL_REDIRECT=True`
5. `python manage.py migrate && python manage.py createcachetable && python manage.py setupdata && python manage.py collectstatic --noinput`
6. nginx: προσάρμοσε το `nginx/nginx.conf` (άλλαξε το `upstream django` σε `127.0.0.1:8000`, τα alias σε πραγματικά paths, το `/protected-media/` alias στο MEDIA_ROOT)
7. systemd units για gunicorn, `celery -A webcrm worker` και `celery -A webcrm beat`

</details>

## Production Checklist

- [ ] `SECRET_KEY` μοναδικό, εκτός git
- [ ] `DEBUG=False` (default στο prod compose)
- [ ] `ALLOWED_HOSTS` + `CSRF_TRUSTED_ORIGINS` με το domain
- [ ] HTTPS ενεργό + `USE_X_FORWARDED_PROTO=True`
- [ ] `setupdata` έτρεξε & αποθηκεύτηκε ο κωδικός του IamSUPER
- [ ] Email SMTP ρυθμισμένο (δοκιμή: υπενθυμίσεις προθεσμιών)
- [ ] Backups εκτός server
- [ ] `/api/health/detailed/` πράσινο
