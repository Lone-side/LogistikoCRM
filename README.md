# LogistikoCRM

**Σύστημα Διαχείρισης Πελατειακών Σχέσεων για Λογιστικά Γραφεία**

---

## Περιγραφή

Το **LogistikoCRM** είναι ένα ολοκληρωμένο CRM σύστημα σχεδιασμένο ειδικά για τις ανάγκες των ελληνικών λογιστικών γραφείων. Προσφέρει διαχείριση πελατών, παρακολούθηση φορολογικών υποχρεώσεων, ενσωμάτωση με myDATA (ΑΑΔΕ) και αυτοματοποίηση εργασιών.

### Βασικά Χαρακτηριστικά

| Λειτουργία | Περιγραφή |
|------------|-----------|
| **Διαχείριση Πελατών** | Πλήρες προφίλ με ΑΦΜ, ΔΟΥ, στοιχεία επικοινωνίας |
| **Φορολογικές Υποχρεώσεις** | Παρακολούθηση ΦΠΑ, ΑΠΔ, ΕΝΦΙΑ, Ε1, Ε3, ΜΥΦ |
| **Ενσωμάτωση myDATA** | Σύνδεση με ΑΑΔΕ για τιμολόγια |
| **VoIP Τηλεφωνία** | Fritz!Box & Zadarma integration |
| **Αρχειοθέτηση** | Οργανωμένη αποθήκευση εγγράφων ανά πελάτη |
| **Email Marketing** | Μαζική αποστολή newsletters |
| **Αναφορές & Analytics** | Dashboards και στατιστικά |
| **Task Management** | Διαχείριση εργασιών και υπενθυμίσεις |

---

## Τεχνολογίες

- **Backend:** Django 5.x (Python)
- **Frontend:** React 19 με Tailwind CSS
- **Database:** PostgreSQL (production) / SQLite (development)
- **Task Queue:** Celery με Redis
- **API:** Django REST Framework με JWT

---

## Εγκατάσταση

### Προαπαιτούμενα

- Python 3.10+
- Node.js 18+ (για το frontend)
- PostgreSQL 14+ (για production)
- Redis (για Celery)

### Βήματα Εγκατάστασης

```bash
# 1. Clone του repository
git clone https://github.com/your-username/LogistikoCRM.git
cd LogistikoCRM

# 2. Δημιουργία virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Εγκατάσταση dependencies
pip install -r requirements.txt

# 4. Ρύθμιση environment variables
cp .env.example .env
# Επεξεργασία του .env με τις ρυθμίσεις σας

# 5. Εκτέλεση migrations
python manage.py migrate

# 6. Δημιουργία superuser
python manage.py createsuperuser

# 7. Εκκίνηση server
python manage.py runserver
```

### Frontend (προαιρετικά)

```bash
cd frontend
npm install
npm start  # Development server στο port 3000
```

---

## Ρυθμίσεις

### Environment Variables (.env)

```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (production)
DATABASE_URL=postgres://user:pass@localhost:5432/logistikocrm

# Email
EMAIL_HOST=smtp.example.com
EMAIL_HOST_USER=your-email@example.com
EMAIL_HOST_PASSWORD=your-password

# MyData ΑΑΔΕ
MYDATA_USER_ID=your-user-id
MYDATA_SUBSCRIPTION_KEY=your-key
MYDATA_ENVIRONMENT=test

# VoIP
FRITZ_API_TOKEN=your-token
ZADARMA_KEY=your-key
ZADARMA_SECRET=your-secret
```

---

## Δομή Φακέλων

```
LogistikoCRM/
├── accounting/      # Κύριο app - πελάτες, υποχρεώσεις
├── crm/             # Core CRM λειτουργικότητα
├── tasks/           # Διαχείριση εργασιών
├── voip/            # VoIP ενσωμάτωση
├── analytics/       # Αναφορές & Dashboards
├── frontend/        # React frontend
├── webcrm/          # Django settings
└── docs/            # Τεκμηρίωση
```

---

## Φορολογικές Υποχρεώσεις

Το σύστημα υποστηρίζει παρακολούθηση των εξής υποχρεώσεων:

| Κωδικός | Περιγραφή | Συχνότητα |
|---------|-----------|-----------|
| ΦΠΑ | Φόρος Προστιθέμενης Αξίας | Μηνιαία/Τριμηνιαία |
| ΑΠΔ | Αναλυτική Περιοδική Δήλωση ΕΦΚΑ | Μηνιαία |
| ΕΝΦΙΑ | Ενιαίος Φόρος Ιδιοκτησίας | Ετήσια |
| Ε1 | Δήλωση Φορολογίας Εισοδήματος | Ετήσια |
| Ε3 | Κατάσταση Οικονομικών Στοιχείων | Ετήσια |
| ΜΥΦ | Συγκεντρωτικές Καταστάσεις | Μηνιαία |

---

## API Endpoints

```
POST /api/token/          # Authentication
GET  /api/clients/        # Λίστα πελατών
GET  /api/obligations/    # Υποχρεώσεις
GET  /api/tickets/        # Tickets
GET  /api/calls/          # Call logs
```

---

## Ανάπτυξη

### Tests

```bash
python manage.py test
python manage.py test accounting  # Συγκεκριμένο app
```

### Celery Workers

```bash
celery -A webcrm worker -l info
celery -A webcrm beat -l info
```

---

## Συνεισφορά

Οι συνεισφορές είναι ευπρόσδεκτες! Δείτε το [CONTRIBUTING.md](CONTRIBUTING.md) για οδηγίες.

---

## Άδεια Χρήσης

Το LogistikoCRM διανέμεται υπό την άδεια **AGPL-3.0**. Δείτε το αρχείο [LICENSE](LICENSE) για λεπτομέρειες.

Βασίζεται στο [Django-CRM](https://github.com/DjangoCRM/django-crm) (AGPL-3.0).

---

## Επικοινωνία

- **Issues:** [GitHub Issues](https://github.com/jimmi21/LogistikoCRM/issues)
- **Email:** support@example.com

---

*Developed for Greek Accounting Offices*
