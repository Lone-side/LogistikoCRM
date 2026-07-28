# 🚀 Οδηγός Τοπικής Εγκατάστασης LogistikoCRM

Πλήρης, δοκιμασμένος οδηγός για να τρέξει το LogistikoCRM σε τοπικό υπολογιστή
(development). Δεν χρειάζεται PostgreSQL/MySQL, Redis ή άλλα εξωτερικά services —
το default είναι SQLite και database cache.

> Για τον παλιό οδηγό ενσωμάτωσης myDATA βλ. `docs/MYDATA_INTEGRATION_GUIDE.md`.
> Για production deployment βλ. `DEPLOYMENT.md`.

---

## Προαπαιτούμενα

- **Python 3.10+** (δοκιμασμένο με 3.11)
- **Node.js 18+** (μόνο αν θες το React frontend)
- Linux / macOS / Windows (WSL προτείνεται)

---

## Βήματα Εγκατάστασης

Η **σειρά έχει σημασία** — ειδικά το `setupdata` πρέπει να τρέξει
**πριν** δημιουργηθεί οποιοσδήποτε χρήστης.

```bash
# 1. Virtual environment
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

# 2. Dependencies
pip install -r requirements.txt
# Σημείωση: το mysqlclient είναι προαιρετικό (σχολιασμένο στο requirements.txt).
# Τοπικά ΔΕΝ χρειάζεται — το default database είναι SQLite.

# 3. Ρυθμίσεις περιβάλλοντος
cp .env.development .env
# Το .env.development είναι το σωστό template για development
# (DEBUG=True, SQLite, console email backend)

# 4. Βάση δεδομένων
python manage.py migrate

# 5. Πίνακας cache (ΑΠΑΡΑΙΤΗΤΟ - χρησιμοποιείται database cache)
python manage.py createcachetable

# 6. Αρχικά δεδομένα: groups, departments, stages, sites + superuser
#    ⚠️ Τρέξε το ΠΡΙΝ δημιουργήσεις οποιονδήποτε χρήστη!
#    Δημιουργεί τον superuser "IamSUPER" και τυπώνει τον κωδικό του.
python manage.py setupdata

# 7. Εκκίνηση server
python manage.py runserver
```

---

## 🌐 URLs — ΠΡΟΣΟΧΗ: δεν υπάρχει `/admin/`!

Το CRM χρησιμοποιεί «κρυφά» URL prefixes (ορίζονται στο `webcrm/settings.py`
ως `SECRET_ADMIN_PREFIX` και `SECRET_CRM_PREFIX`):

| Σελίδα | URL |
|--------|-----|
| **Django Admin** | http://localhost:8000/el/456-admin/ |
| **CRM (κύρια εφαρμογή)** | http://localhost:8000/el/123/ |
| **Dashboard Λογιστηρίου** | http://localhost:8000/accounting/dashboard/ |
| **Ημερολόγιο Υποχρεώσεων** | http://localhost:8000/accounting/calendar/ |
| **API Docs (Swagger)** | http://localhost:8000/api/docs/ |
| **Health Check** | http://localhost:8000/api/health/ |

Σύνδεση με τα στοιχεία του superuser που τύπωσε το `setupdata` (βήμα 6).
**Άλλαξε τον κωδικό** από το admin μετά την πρώτη σύνδεση.

---

## Frontend (προαιρετικό)

Το React frontend είναι **Vite** app:

```bash
cd frontend
npm install
npm run dev        # ΟΧΙ "npm start" - δεν υπάρχει τέτοιο script
# Ανοίγει στο http://localhost:5173
```

Εναλλακτικά, το `./start_dev.sh` σηκώνει backend + frontend μαζί.

---

## Συχνά Προβλήματα

**`pip install` σκάει στο mysqlclient**
Δεν το χρειάζεσαι τοπικά — είναι πλέον σχολιασμένο στο `requirements.txt`.
Αν το θες για MySQL: `sudo apt install default-libmysqlclient-dev build-essential`

**500 error `no such table: django_cache_table`**
Ξέχασες το βήμα 5: `python manage.py createcachetable`

**404 στο `/admin/`**
Δεν υπάρχει — το admin είναι στο `/el/456-admin/` (βλ. πίνακα URLs).

**Δημιούργησα χρήστη πριν το `setupdata` και τα groups μπερδεύτηκαν**
Το `setupdata` φορτώνει τα groups με συγκεκριμένα pk. Αν προηγήθηκε χρήστης,
σβήσε τη βάση (`rm db.sqlite3`) και ξεκίνα από το βήμα 4 με τη σωστή σειρά.

**Τα emails «στέλνονται» αλλά δεν φαίνονται πουθενά**
Σε development (DEBUG=True) το default backend είναι console — τα emails
τυπώνονται στο terminal του runserver. Για πραγματικό SMTP όρισε
`EMAIL_BACKEND_CONSOLE=false` και τα EMAIL_* στο `.env`.

**Upload αρχείων σκάει με libmagic error**
`sudo apt install libmagic1`

---

## Προαιρετικά Services

Τίποτα από τα παρακάτω δεν χρειάζεται για τοπική χρήση — όλα υποβαθμίζονται
ομαλά όταν λείπουν:

| Service | Τι δίνει | Ρύθμιση |
|---------|----------|---------|
| Redis + Celery | Αυτοματοποιημένα emails/υπενθυμίσεις | `CELERY_BROKER_URL` στο `.env` |
| PostgreSQL | Production database | `DB_ENGINE`, `DB_NAME`, κλπ. στο `.env` |
| Fritz!Box | Παρακολούθηση κλήσεων γραφείου | `fritz_monitor.py` + `FRITZ_API_TOKEN` |
| Zadarma | Cloud PBX / click-to-call | `ZADARMA_KEY`, `ZADARMA_SECRET` |
| myDATA (ΑΑΔΕ) | Συγχρονισμός παραστατικών | βλ. `docs/MYDATA_INTEGRATION_GUIDE.md` |

---

## Tests

```bash
python manage.py test tests          # πλήρες suite (~2 λεπτά)
python manage.py test tests.accounting   # μόνο accounting
```
