# CLAUDE.md - Οδηγός LogistikoCRM για AI Assistants

## 📋 Επισκόπηση Project

**LogistikoCRM** είναι ένα production-ready Django CRM σύστημα ειδικά σχεδιασμένο για ελληνικά λογιστικά γραφεία. Βασίζεται στο open-source Django-CRM με εξειδικευμένες λειτουργίες για λογιστική και φορολογική συμμόρφωση.

**Βασικά χαρακτηριστικά:**
- Enterprise-grade CRM με ενσωμάτωση myDATA (ΑΑΔΕ)
- Django 5.x backend με επιλογή React.js frontend
- PostgreSQL/MySQL για παραγωγή, SQLite για ανάπτυξη
- Υποστήριξη 23 γλωσσών (ελληνικά default)
- Timezone: Europe/Athens
- **Client Portal**: πελάτες συνδέονται και βλέπουν ΜΟΝΟ τα δικά τους δεδομένα

---

## 🏛️ Αρχιτεκτονικές Αποφάσεις (Client Portal — ΣΗΜΑΝΤΙΚΟ)

> Πλήρης τεκμηρίωση: `docs/SECURITY_DECISIONS.md` · Πριν παραγωγή: `GOLIVE.md`

### Ρόλοι & απομόνωση (multi-tenant)
- **1 πελάτης = 1 login.** `ClientProfile.user` (OneToOne → User). Δημιουργία μέσω
  `ClientProfile.create_portal_user()` (βάζει τον χρήστη στο group `'client'`,
  τον βγάζει από το `'co-workers'`).
- Ρόλος client: `accounting/portal.py::is_client_user()` (group `'client'` ή
  συνδεδεμένο profile, ΚΑΙ όχι staff).
- **Isolation — fail-closed:** `accounting/portal_mixins.py::ClientScopedQuerysetMixin`
  φιλτράρει το queryset ώστε ο client να βλέπει μόνο τα δικά του· read-only
  (POST/PUT/PATCH/DELETE → 403). Άγνωστος authenticated → άδειο queryset.
- **Permission `IsStaffUser`** (`accounting/permissions.py`): default-deny για
  πελάτες. **ΚΑΝΟΝΑΣ:** κάθε νέο staff/management endpoint (π.χ. στο `mydata`,
  search, dashboard, reports, email, export) ΠΡΕΠΕΙ να έχει `IsStaffUser`. Οι
  πελάτες χρησιμοποιούν ΜΟΝΟ τα `/api/client/me/...`.

### Endpoints πελάτη (read-mostly, scoped)
`accounting/api_portal.py`: `/api/client/me/{profile,obligations,documents,vat,calls}/`
(GET, μέσω `_require_client`), `/api/client/me/documents/upload/` (forced στον
δικό του πελάτη), `/api/client/set-password/`. Domain logic ΦΠΑ: `mydata/services.py::VATPortalService`.

### Auth & ασφάλεια
- JWT (SimpleJWT): **access 15min**, refresh 7d με rotation+blacklist.
- **Throttling** (`SimpleRateThrottle`, ΟΧΙ `ScopedRateThrottle` — η τελευταία
  κάνει no-op σε function/JWT views): `login 5/min`, `set_password 3/hour`,
  `vat_read 120/hour`. Keyed by IP.
- `set_password`: constant-time token check (no enumeration oracle).
- **Production guards** (`webcrm/settings.py`, όταν `DEBUG=False`): raise
  `ImproperlyConfigured` αν λείπει `SECRET_KEY`/`FRITZ_API_TOKEN`.
- **CSP**: `common/utils/csp_middleware.py` (`script-src 'self'`).
- **JWT σε localStorage**: αποδεκτό ρίσκο με mitigations — βλ. SD-001.

### Email προσκλήσεις
`EmailService.send_portal_invite(client)` στέλνει set-password link στο
`PORTAL_URL`. Admin actions: «Δημιουργία λογαριασμού Portal + αποστολή πρόσκλησης»
και «Επαναποστολή πρόσκλησης». `seed_demo` command για demo δεδομένα.

### Frontend
- **Tests:** Vitest + React Testing Library (`npm test`), Playwright E2E
  (`npm run test:e2e`, χρειάζεται backend με `seed_demo`). Όλα στο CI.
- **Routing:** `src/routes/guards.tsx` (`ProtectedRoute` staff, `ClientRoute`
  πελάτης) με per-route `ErrorBoundary` (compact, resetKeys=path).
- Portal: mobile-responsive (scrollable tabs/tables) + a11y (role="tab"/tablist).

---

## 🚀 Προτεραιότητες Ανάπτυξης

### Φάση 1: Καθαρό Backend (ΤΡΕΧΟΥΣΑ)
- [ ] Διόρθωση όλων των migration θεμάτων
- [ ] Όλα τα models να έχουν `__str__`, `get_absolute_url`
- [ ] Καθαρισμός αχρησιμοποίητου κώδικα
- [ ] Προσθήκη validation στα models

### Φάση 2: Διασύνδεση Αρχείων-Υποχρεώσεων
- [ ] Σύνδεση uploaded αρχείων με συγκεκριμένες υποχρεώσεις
- [ ] Αυτόματη δημιουργία φακέλων κατά το upload
- [ ] Προβολή όλων των εγγράφων ανά πελάτη στο admin
- [ ] Κουμπί "Άνοιγμα φακέλου πελάτη" στο admin

### Φάση 3: Email Αυτοματισμοί
- [ ] Celery task για μηνιαίες υπενθυμίσεις
- [ ] Email ειδοποίησης για νέα έγγραφα
- [ ] Email templates (στα ελληνικά)

### Φάση 4: Αναζήτηση & Φίλτρα
- [ ] Αναζήτηση πελάτη (ΑΦΜ, επωνυμία, τηλέφωνο)
- [ ] Φίλτρα υποχρεώσεων (μήνας, κατάσταση, τύπος)
- [ ] Full-text search με PostgreSQL SearchVector

### Φάση 5: Έτοιμο για Παραγωγή
- [ ] Docker configuration
- [ ] PostgreSQL setup
- [ ] Redis/Celery configuration
- [ ] Nginx configuration
- [ ] Health checks

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

# Εγκατάσταση dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # για development

# Ρύθμιση βάσης
python manage.py migrate
python manage.py createsuperuser

# Εκκίνηση server
python manage.py runserver
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
# --- Backend (Django) ---
python manage.py test                          # όλα
python manage.py test tests.accounting tests.mydata   # κύρια apps
python manage.py test tests.test_production_guards     # prod guards
# Σημ.: ΑΠΑΙΤΕΙΤΑΙ Python 3.11 (prod/CI). Σε 3.13/3.14 ο Django test client σπάει.

# --- Frontend (Vitest + React Testing Library) ---
cd frontend
npm test            # unit/component tests (vitest run)
npx tsc -b          # typecheck (πρέπει 0 errors)

# --- E2E (Playwright) ---
# 1) Σήκωσε backend με demo δεδομένα:
python manage.py seed_demo --reset
python manage.py runserver 8000 --noreload
# 2) Σε άλλο terminal:
cd frontend && npm run test:e2e
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
