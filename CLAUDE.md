# CLAUDE.md - Οδηγός LogistikoCRM για AI Assistants

## 📋 Επισκόπηση Project

**LogistikoCRM** είναι ένα production-ready Django CRM σύστημα ειδικά σχεδιασμένο για ελληνικά λογιστικά γραφεία. Βασίζεται στο open-source Django-CRM με εξειδικευμένες λειτουργίες για λογιστική και φορολογική συμμόρφωση.

**Βασικά χαρακτηριστικά:**
- Enterprise-grade CRM με ενσωμάτωση myDATA (ΑΑΔΕ)
- Django 5.x backend με επιλογή React.js frontend
- PostgreSQL/MySQL για παραγωγή, SQLite για ανάπτυξη
- Υποστήριξη 23 γλωσσών (ελληνικά default)
- Timezone: Europe/Athens

---

## 🚀 Προτεραιότητες Ανάπτυξης

### Φάση 1: Καθαρό Backend ✅
- [x] Διόρθωση όλων των migration θεμάτων (`makemigrations --check` καθαρό)
- [x] Όλα τα models να έχουν `__str__`, `get_absolute_url`
- [x] Καθαρισμός αχρησιμοποίητου κώδικα
- [x] Προσθήκη validation στα models

### Φάση 2: Διασύνδεση Αρχείων-Υποχρεώσεων ✅
- [x] Σύνδεση uploaded αρχείων με συγκεκριμένες υποχρεώσεις (ClientDocument.obligation)
- [x] Αυτόματη δημιουργία φακέλων κατά το upload (accounting/services/filing.py)
- [x] Προβολή όλων των εγγράφων ανά πελάτη (admin + React tab με ομαδοποίηση)
- [x] Κουμπί "Άνοιγμα φακέλου πελάτη" στο admin
- [x] Αυτόματη ονομασία αρχείων (FilingSystemSettings.file_naming_convention)
- [x] Εξαγωγή κειμένου PDF + αναζήτηση περιεχομένου + έλεγχος ΑΦΜ (text_extraction.py)

### Φάση 3: Email Αυτοματισμοί ✅
- [x] Celery tasks: υπενθυμίσεις προθεσμιών, ημερήσια σύνοψη, scheduled emails
- [x] Email templates στα ελληνικά (seeded, migration 0025)
- [x] Ρυθμίσεις ειδοποιήσεων ανά χρήστη (UserNotificationSettings)
- [ ] Email ειδοποίησης για νέα έγγραφα

### Φάση 4: Αναζήτηση & Φίλτρα ✅ (εκτός SearchVector)
- [x] Αναζήτηση πελάτη (ΑΦΜ, επωνυμία, τηλέφωνο) — global search
- [x] Φίλτρα υποχρεώσεων (μήνας, κατάσταση, τύπος)
- [x] Αναζήτηση στο περιεχόμενο εγγράφων (extracted_text)
- [ ] Full-text search με PostgreSQL SearchVector (προαιρετικό, σε παραγωγή)

### Φάση 5: Έτοιμο για Παραγωγή ✅
- [x] Docker configuration (multi-stage Dockerfile + docker-compose.prod.yml)
- [x] Redis/Celery configuration (beat: reminders, summary, backup, yearly folders)
- [x] Health checks (/api/health/, /detailed, /ready, /live)
- [x] Αυτόματο backup βάσης (Celery beat 02:00, SQLite copy ή pg_dump)
- [x] PostgreSQL setup σε παραγωγή (docker-compose.prod.yml + pg_dump backup)
- [x] Nginx configuration + React build στο Dockerfile (nginx/nginx.conf, stage `nginx`)
- [x] Protected media: signed URLs + X-Accel-Redirect (common/views/protected_media.py)

### Επόμενα (backlog με σειρά αξίας)
1. **Portal πελάτη με upload** — ο πελάτης ανεβάζει έγγραφα μόνος του μέσω SharedLink (+ document requests με tracking)
2. **Dashboard αναβάθμιση** — φόρτος ανά υπάλληλο, κατανομή προθεσμιών ανά τύπο, τάσεις
3. **myDATA αποστολή τιμολογίων** — ο client υπάρχει (send_invoices), δεν εκτίθεται σε UI· tests για το mydata app
4. **Frontend tests** — μηδενική κάλυψη React σήμερα

---

## 🛠️ Τεχνολογίες

### Backend
- **Framework:** Django 5.0-5.2 (LTS)
- **Βάση Δεδομένων:** PostgreSQL 14+ (production), SQLite (development)
- **API:** Django REST Framework 3.14+ με JWT authentication
- **Task Queue:** Celery 5.3+ με Redis, Django-Q (database-backed εναλλακτικά)
- **Caching:** Redis ή database cache
- **Search:** PostgreSQL full-text search με SearchVector

### Frontend
- **React:** 19.2 με Create React App
- **Styling:** Tailwind CSS 4.x
- **Charts:** Recharts
- **HTTP Client:** Axios
- **Τοποθεσία:** `/frontend/` directory

### Ενσωματώσεις
- **VoIP:** Fritz!Box μέσω πρωτοκόλλου TR-064
- **IoT:** Tasmota για έλεγχο πόρτας
- **MyData:** API ΑΑΔΕ για φορολογικά

---

## 📁 Δομή Project

```
LogistikoCRM/
├── accounting/          # 🏦 Κύριο app - πελάτες, υποχρεώσεις, αρχεία
│   ├── models.py        # ClientProfile, MonthlyObligation, Ticket
│   ├── admin.py         # Προσαρμοσμένο admin interface
│   ├── views/           # Class-based views
│   └── migrations/      # Database migrations
├── crm/                 # 📊 Core CRM λειτουργικότητα
│   ├── models/          # Company, Contact, Deal, Lead, etc.
│   ├── views/           # CRUD operations
│   └── utils/           # Helper functions
├── tasks/               # ✅ Διαχείριση εργασιών & tickets
│   ├── models/          # Task, Memo models
│   └── views/           # Task management views
├── voip/                # 📞 VoIP ενσωμάτωση (Fritz!Box)
│   ├── models.py        # CallLog, VoIPSettings
│   └── services/        # Fritz!Box API integration
├── inventory/           # 📦 Διαχείριση αποθέματος
│   └── models.py        # Product, Stock models
├── analytics/           # 📈 Αναφορές & Dashboards
├── chat/                # 💬 Εσωτερικό messaging
├── common/              # 🔧 Shared utilities & base classes
│   ├── models.py        # Base models, mixins
│   └── utils/           # Common helper functions
├── help/                # ❓ Σύστημα βοήθειας
├── massmail/            # 📧 Μαζικά email
├── settings/            # ⚙️ App-specific settings models
├── docs/                # 📚 Τεκμηρίωση (MkDocs)
├── frontend/            # ⚛️ React frontend
│   ├── src/             # Source code
│   └── public/          # Static assets
├── scripts/             # 🔨 Utility scripts
│   └── backup_cron.sh   # Backup automation
├── templates/           # 🎨 Django templates
├── static/              # 📁 Static files
├── tests/               # 🧪 Test suite
│   ├── accounting/      # Accounting tests
│   ├── crm/             # CRM tests
│   └── utils/           # Test utilities
├── webcrm/              # ⚙️ Django project settings
│   ├── settings.py      # Main settings
│   ├── settings_local.py # Local overrides
│   ├── urls.py          # Root URL configuration
│   ├── celery.py        # Celery configuration
│   └── wsgi.py          # WSGI entry point
├── manage.py            # Django management
├── requirements.txt     # Production dependencies
├── requirements-dev.txt # Development dependencies
└── setup.cfg            # Linting/testing configuration
```

---

## 🇬🇷 Ελληνική Επιχειρηματική Λογική

### Επικύρωση ΑΦΜ
```python
def validate_afm(afm):
    """
    Επικυρώνει ελληνικό ΑΦΜ (9 ψηφία, έλεγχος checksum)
    """
    if len(afm) != 9 or not afm.isdigit():
        return False
    # Αλγόριθμος checksum
    total = sum(int(afm[i]) * (2 ** (8 - i)) for i in range(8))
    check_digit = (total % 11) % 10
    return check_digit == int(afm[8])
```

### Τύποι Υποχρεώσεων
| Κωδικός | Περιγραφή | Συχνότητα | Προθεσμία |
|---------|-----------|-----------|-----------|
| ΦΠΑ | Φόρος Προστιθέμενης Αξίας | Μηνιαία/Τριμηνιαία | 20η μήνα |
| ΑΠΔ | Αναλυτική Περιοδική Δήλωση ΕΦΚΑ | Μηνιαία | Τελευταία εργάσιμη |
| ΕΝΦΙΑ | Ενιαίος Φόρος Ιδιοκτησίας | Ετήσια | Σεπτέμβριος |
| Ε1 | Δήλωση Φορολογίας Εισοδήματος | Ετήσια | Ιούλιος |
| Ε3 | Κατάσταση Οικονομικών Στοιχείων | Ετήσια | Ιούλιος |
| ΜΥΦ | Συγκεντρωτικές Καταστάσεις | Μηνιαία | 20η μήνα |

### Δομή Αρχειοθέτησης
```
Μοτίβο:  clients/{ΑΦΜ}_{Επωνυμία}/{έτος}/{μήνας}/{τύπος_υποχρέωσης}/
Παράδειγμα: clients/123456789_ΕΤΑΙΡΕΙΑ_ΑΕ/2025/01/ΦΠΑ/
```

### Καταστάσεις Υποχρεώσεων
```python
OBLIGATION_STATUS = [
    ('pending', 'Εκκρεμεί'),
    ('in_progress', 'Σε εξέλιξη'),
    ('completed', 'Ολοκληρώθηκε'),
    ('overdue', 'Εκπρόθεσμη'),
    ('cancelled', 'Ακυρώθηκε'),
]
```

---

## ⚠️ Σημαντικοί Κανόνες

### ❌ ΜΗΝ ΚΑΝΕΙΣ
- Χρήση πολύπλοκων JavaScript frameworks (React μόνο στο /frontend/)
- Δημιουργία διπλών migrations
- Αποθήκευση ευαίσθητων δεδομένων στο settings.py
- Παράλειψη μεθόδων `__str__` στα models
- Hardcode ελληνικού κειμένου χωρίς translations
- Αλλαγές στα models χωρίς dry-run
- Απενεργοποίηση CSRF protection

### ✅ ΠΑΝΤΑ ΝΑ ΚΑΝΕΙΣ
- Τρέξε `python manage.py makemigrations --dry-run` πριν δημιουργήσεις migrations
- Δοκίμασε με ελληνικούς χαρακτήρες (UTF-8)
- Πρόσθεσε logging για σημαντικές λειτουργίες
- Χρησιμοποίησε timezone-aware datetimes
- Επικύρωσε το ΑΦΜ πριν την αποθήκευση
- Ρώτα πριν κάνεις μεγάλες αλλαγές σε models/migrations
- Ακολούθα PEP 8 με Black formatting

---

## 🔧 Εντολές Ανάπτυξης

### Αρχική Εγκατάσταση
```bash
# Δημιουργία virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Εγκατάσταση dependencies (το mysqlclient είναι προαιρετικό/σχολιασμένο)
pip install -r requirements.txt
pip install -r requirements-dev.txt  # για development

# Ρυθμίσεις (το .env.development είναι το σωστό template)
cp .env.development .env

# Ρύθμιση βάσης — Η ΣΕΙΡΑ ΕΧΕΙ ΣΗΜΑΣΙΑ
python manage.py migrate
python manage.py createcachetable   # απαραίτητο (database cache)
python manage.py setupdata          # groups/fixtures + superuser IamSUPER
# ⚠️ ΟΧΙ createsuperuser πριν το setupdata — χαλάει τα pk των groups

# Εκκίνηση server
python manage.py runserver
# Admin: http://localhost:8000/el/456-admin/  |  CRM: http://localhost:8000/el/123/
```

### Frontend Development
```bash
cd frontend
npm install
npm start          # Development server (port 3000)
npm run build      # Production build
npm test           # Εκτέλεση tests
```

### Testing
```bash
# Django tests
python manage.py test

# Συγκεκριμένο app
python manage.py test accounting
python manage.py test accounting.tests.test_models

# Με pytest (αν είναι εγκατεστημένο)
pytest
pytest tests/accounting/ -v
pytest --cov=accounting  # Με coverage
```

### Celery Workers
```bash
# Εκκίνηση worker
celery -A webcrm worker -l info

# Εκκίνηση beat scheduler
celery -A webcrm beat -l info

# Flower monitoring (αν είναι εγκατεστημένο)
celery -A webcrm flower
```

### Στατικά Αρχεία & Μεταφράσεις
```bash
# Collect static files
python manage.py collectstatic

# Μεταφράσεις
python manage.py makemessages -l el
python manage.py compilemessages
```

---

## 📊 Βασικά Models

### ClientProfile (accounting/models.py)
```python
# Κύρια πεδία
- afm (CharField, unique, 9 χαρακτήρες)  # ΑΦΜ
- onoma (CharField)                       # Επωνυμία
- email (EmailField)
- phone (CharField)
- doy (CharField)                         # ΔΟΥ
- is_active (BooleanField)
- created, modified (timestamps)
```

### MonthlyObligation (accounting/models.py)
```python
# Μηνιαίες υποχρεώσεις πελάτη
- client (ForeignKey → ClientProfile)
- obligation_type (CharField)             # Τύπος (ΦΠΑ, ΑΠΔ, κλπ)
- period_month, period_year               # Περίοδος
- due_date (DateField)                    # Προθεσμία
- status (CharField)                      # Κατάσταση
- completed_date (DateField, null)
- notes (TextField)
```

### Ticket (accounting/models.py)
```python
# Tickets για follow-up
- client (ForeignKey → ClientProfile)
- subject (CharField)
- description (TextField)
- status (CharField)
- priority (CharField)
- assigned_to (ForeignKey → User)
- created_at, updated_at
```

---

## 🌐 API Structure

### Authentication
```python
# JWT tokens
POST /api/token/           # Λήψη token
POST /api/token/refresh/   # Ανανέωση token
POST /api/token/verify/    # Επαλήθευση token
```

### Κύρια Endpoints
```
/api/clients/              # ClientProfile CRUD
/api/obligations/          # MonthlyObligation CRUD
/api/tickets/              # Ticket management
/api/calls/                # VoIP call logs
```

### CORS Configuration
```python
# Επιτρεπόμενα origins (από settings.py)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
```

---

## 📞 Ενσωματώσεις

### VoIP Systems (δύο ξεχωριστά συστήματα)

| Σύστημα | App | Σκοπός |
|---------|-----|--------|
| **Zadarma** | `/voip/` | Cloud PBX, click-to-call, webhook notifications |
| **Fritz!Box** | `/accounting/` + `fritz_monitor.py` | Παρακολούθηση τηλεφώνου γραφείου |

**Zadarma VoIP** (`voip/` app):
```python
# Cloud PBX με click-to-call
# Webhook notifications για κλήσεις
# Auto-match με Contacts/Leads/Deals

# Ρυθμίσεις στο .env
ZADARMA_KEY=your-api-key
ZADARMA_SECRET=your-api-secret
```

**Fritz!Box VoIP** (`accounting/` app + `fritz_monitor.py`):
```python
# Παρακολούθηση κλήσεων μέσω CallMonitor port 1012
# Αυτόματη δημιουργία ticket για αναπάντητες (Celery)
# Αντιστοίχιση caller ID με ClientProfile

# Ρυθμίσεις στο .env
FRITZ_API_TOKEN=your-secure-token
```

### Tasmota IoT
```python
# Έλεγχος πόρτας γραφείου
# HTTP API: ON/OFF toggle
# Endpoint: http://{ip}/cm?cmnd=Power%20Toggle

TASMOTA_DOOR_IP=192.168.1.100
```

### MyData ΑΑΔΕ
```python
# Ενσωμάτωση με εφορία
# Υποβολή/ανάκτηση τιμολογίων
# Απαιτεί πιστοποιητικό

MYDATA_USER_ID=xxx
MYDATA_SUBSCRIPTION_KEY=xxx
MYDATA_ENVIRONMENT=test  # ή prod
```

---

## 🔐 Ασφάλεια

### Environment Variables (.env)
```bash
# Απαραίτητες μεταβλητές
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com

# Database
DATABASE_URL=postgres://user:pass@host:5432/dbname

# Email
EMAIL_HOST=smtp.example.com
EMAIL_HOST_USER=user@example.com
EMAIL_HOST_PASSWORD=xxx
```

### File Upload Validation
```python
# Επιτρεπόμενοι τύποι αρχείων
ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.png']
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
```

### Production Checklist
```
[ ] DEBUG = False
[ ] SECRET_KEY από environment
[ ] ALLOWED_HOSTS ρυθμισμένο
[ ] HTTPS enabled
[ ] CSRF protection ενεργό
[ ] Database backups configured
[ ] Logging σε αρχεία
[ ] Static files served by nginx
```

---

## 🐛 Troubleshooting

### Συνηθισμένα Προβλήματα

**Migration conflicts:**
```bash
python manage.py showmigrations
python manage.py migrate --fake app_name migration_name
```

**Static files not loading:**
```bash
python manage.py collectstatic --clear
```

**Celery tasks not running:**
```bash
# Έλεγχος Redis
redis-cli ping

# Restart worker
celery -A webcrm control shutdown
celery -A webcrm worker -l info
```

**Greek characters encoding:**
```python
# Βεβαιώσου ότι υπάρχει στην αρχή του αρχείου
# -*- coding: utf-8 -*-
```

---

## 💡 Συμβουλές για Claude Code

1. **Ρώτα πριν από μεγάλες αλλαγές** - Αν αναδιαρθρώνεις models ή migrations, επιβεβαίωσε πρώτα
2. **Δοκίμασε ελληνικούς χαρακτήρες** - Πάντα δοκιμή με πραγματικό ελληνικό κείμενο
3. **Κράτα το απλό** - Προτίμησε Django built-ins αντί για third-party packages
4. **Τεκμηρίωσε τη business logic** - Χρήση ελληνικών σχολίων για domain-specific κώδικα
5. **Σταδιακές αλλαγές** - Μικρά commits, δοκιμή μετά από κάθε αλλαγή
6. **Admin πρώτα** - Οι περισσότερες λειτουργίες χρησιμοποιούνται μέσω Django Admin
7. **Μην υποθέτεις** - Αν δεν είσαι σίγουρος, ρώτα τον χρήστη

---

## 📚 Χρήσιμοι Σύνδεσμοι

- Django Docs: https://docs.djangoproject.com/
- DRF Docs: https://www.django-rest-framework.org/
- MyData API: https://www.aade.gr/mydata
- MkDocs (project docs): http://localhost:8000 (με `mkdocs serve`)

---

## 📋 Αρχεία Αναφοράς

| Αρχείο | Περιγραφή |
|--------|-----------|
| `README.md` | Project overview |
| `CONTRIBUTING.md` | Οδηγίες συνεισφοράς |
| `DEPLOYMENT.md` | Οδηγίες deployment |
| `PRODUCTION_READY.md` | Production features |
| `PRODUCTION_CHECKLIST.md` | Pre-deployment checklist |
| `CHANGELOG.md` | Ιστορικό αλλαγών |
| `setup.cfg` | Linting/testing config |
| `.env.example` | Παράδειγμα environment |

---

*Τελευταία Ενημέρωση: Δεκέμβριος 2025*
*Project Owner: ddiplas*
