# CLAUDE.md - Οδηγός LogistikoCRM για AI Assistants

## 📋 Επισκόπηση Project

**LogistikoCRM** είναι ένα Django CRM σύστημα ειδικά σχεδιασμένο για ελληνικά λογιστικά γραφεία. Βασίζεται στο open-source Django-CRM με εξειδικευμένες λειτουργίες για λογιστική και φορολογική συμμόρφωση. Έχει production υποδομή (Docker, nginx, backups), αλλά **δεν θεωρείται πλήρως production-ready πριν ολοκληρωθεί το security hardening** (credentials, RBAC — βλ. skills).

> ⚠️ **Φορολογική γνώση**: Ό,τι φορολογικό αναφέρεται σε αυτό το αρχείο
> (προθεσμίες, τύποι υποχρεώσεων) είναι ενδεικτικό για κατανόηση του domain,
> ΟΧΙ authoritative. Πριν από κάθε αλλαγή φορολογικής λογικής διάβασε το skill
> `.claude/skills/greek-tax-domain/`. Για secrets/κωδικούς: `credentials-and-secrets`.
> Για κάθε νέο endpoint: `django-security`.

### 📚 Project Skills (`.claude/skills/`)
| Skill | Πότε |
|-------|------|
| `logistiko-architecture` | Αρχή session / άγνωστη περιοχή codebase |
| `django-security` | Κάθε νέο/αλλαγμένο endpoint, serializer, permission |
| `credentials-and-secrets` | Ό,τι αγγίζει κωδικούς, secrets, encryption |
| `greek-tax-domain` | Κάθε φορολογική λογική/προθεσμία |
| `obligation-engine` | Αλλαγές στον μηχανισμό υποχρεώσεων |
| `mydata-integration` | Αλλαγές στο mydata/ app ή ροή τιμολογίων |
| `django-migrations` | Κάθε αλλαγή σε models/migrations |
| `testing-and-release` | Κάθε PR, bugfix, push |

Backlog skills (θα γραφτούν όταν αγγίξουμε τα αντίστοιχα κομμάτια):
`client-data-model`, `document-filing`, `api-contracts`, `react-design-system`, `gdpr-audit`.

**Βασικά χαρακτηριστικά:**
- Enterprise-grade CRM με ενσωμάτωση myDATA (ΑΑΔΕ)
- Django 5.x backend με επιλογή React.js frontend
- PostgreSQL/MySQL για παραγωγή, SQLite για ανάπτυξη
- Υποστήριξη 23 γλωσσών (ελληνικά default)
- Timezone: Europe/Athens

---

## 🚀 Ανοιχτά θέματα

Οι Φάσεις 1–5 (backend cleanup, διασύνδεση αρχείων-υποχρεώσεων, email αυτοματισμοί,
αναζήτηση/φίλτρα, production infra) έχουν ολοκληρωθεί — βλ. git history.
(⚠️ Το `CHANGELOG.md` είναι στάσιμο από 10/2025 — μην το εμπιστεύεσαι ως πηγή.)

Εκκρεμούν:
- [ ] Email ειδοποίησης για νέα έγγραφα
- [ ] Full-text search με PostgreSQL SearchVector (προαιρετικό, σε παραγωγή)
- [ ] **myDATA sandbox δοκιμή** — end-to-end υποβολή σε mydataapidev με πραγματικά credentials (χειροκίνητο βήμα· runbook: `docs/MYDATA_SANDBOX_TEST.md`)

---

## 🇬🇷 Ελληνική Επιχειρηματική Λογική

- **ΑΦΜ**: επικύρωση 9 ψηφίων με checksum — η υλοποίηση είναι η μοναδική πηγή αλήθειας, μην την ξαναγράψεις inline.
- **~~ΜΥΦ~~ (Συγκεντρωτικές Καταστάσεις)**: **παρωχημένο, αντικαταστάθηκε από myDATA· ΜΗΝ προστίθεται νέα λογική.**
- Τύποι υποχρεώσεων, συχνότητες και προθεσμίες: η αλήθεια ζει στα μοντέλα
  `ObligationType`/`ClientObligation` και στις πηγές του skill `greek-tax-domain`.
  Μη γράφεις προθεσμίες από μνήμη.

### Δομή Αρχειοθέτησης
```
Μοτίβο:  clients/{ΑΦΜ}_{Επωνυμία}/{έτος}/{μήνας}/{τύπος_υποχρέωσης}/
Παράδειγμα: clients/123456789_ΕΤΑΙΡΕΙΑ_ΑΕ/2025/01/ΦΠΑ/
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

## 🔧 Setup βάσης — Η ΣΕΙΡΑ ΕΧΕΙ ΣΗΜΑΣΙΑ

```bash
python manage.py migrate
python manage.py createcachetable   # απαραίτητο (database cache)
python manage.py setupdata          # groups/fixtures + superuser IamSUPER
# ⚠️ ΟΧΙ createsuperuser πριν το setupdata — χαλάει τα pk των groups

python manage.py runserver
# Admin: http://localhost:8000/el/456-admin/  |  CRM: http://localhost:8000/el/123/
```

Το `.env.development` είναι το σωστό template για `.env` (ΟΧΙ το `.env.example`).
Το `mysqlclient` στο `requirements.txt` είναι προαιρετικό/σχολιασμένο.

---

## 📞 VoIP — δύο ξεχωριστά συστήματα (μην τα μπερδεύεις)

| Σύστημα | App | Σκοπός |
|---------|-----|--------|
| **Zadarma** | `/voip/` | Cloud PBX, click-to-call, webhook notifications |
| **Fritz!Box** | `/accounting/` + `fritz_monitor.py` | Παρακολούθηση τηλεφώνου γραφείου (CallMonitor port 1012, auto-ticket για αναπάντητες) |

---

## 💡 Συμβουλές για Claude Code

1. **Ρώτα πριν από μεγάλες αλλαγές** - Αν αναδιαρθρώνεις models ή migrations, επιβεβαίωσε πρώτα
2. **Admin πρώτα** - Οι περισσότερες λειτουργίες χρησιμοποιούνται μέσω Django Admin
3. **Μην υποθέτεις** - Αν δεν είσαι σίγουρος, ρώτα τον χρήστη

---

## 📋 Αρχεία Αναφοράς (μη προφανή)

| Αρχείο | Περιγραφή |
|--------|-----------|
| `PRODUCTION_CHECKLIST.md` | Pre-deployment checklist |
| `SECURITY_EXCEPTIONS.md` | Γνωστά advisories που παραμένουν ανοιχτά + σκεπτικό |

---

*Τελευταία Ενημέρωση: Αύγουστος 2026*
*Project Owner: ddiplas*
