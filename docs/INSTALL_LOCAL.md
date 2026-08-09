# Τοπική εγκατάσταση LogistikoCRM

Οδηγίες για εγκατάσταση στο μηχάνημα του γραφείου (απλή dev εγκατάσταση:
Python venv + SQLite — χωρίς Docker/PostgreSQL).

## Προαπαιτούμενα

| Τι | Από πού | Σημείωση |
|---|---|---|
| Python 3.11+ | https://www.python.org/downloads/ | Στην εγκατάσταση τσέκαρε **"Add python.exe to PATH"** |
| Node.js LTS | https://nodejs.org/ | Μόνο για το React UI (προαιρετικό αλλά προτεινόμενο) |
| Git | https://git-scm.com/ | Ή κατέβασε το ZIP από το GitHub (Code → Download ZIP) |

## 0. Έλεγχος για παλιά εγκατάσταση (προαιρετικό)

Αν πιθανόν υπάρχει ήδη παλιότερη εγκατάσταση στον υπολογιστή, τρέξε με διπλό
κλικ το `scripts\check_local_install.bat` (wrapper — η δουλειά γίνεται στο
`check_local_install.ps1`, ώστε τα ελληνικά να εμφανίζονται σωστά). Θα σου
δείξει:

- σε ποιους φακέλους βρέθηκε εγκατάσταση (venv, db.sqlite3, media κλπ),
- αν τρέχει ήδη server στα ports 8000/5173,
- τα βήματα για ασφαλή διαγραφή.

> ⚠️ Τα `db.sqlite3` και `media\` της παλιάς εγκατάστασης μπορεί να περιέχουν
> **πραγματικά στοιχεία πελατών**. Κράτα πρώτα αντίγραφο πριν σβήσεις.
> Η διαγραφή είναι απλή: κλείσε τα παράθυρα του server και σβήσε τον φάκελο —
> η εγκατάσταση δεν αφήνει ίχνη στο μητρώο ή στα Program Files.

## 1. Λήψη του κώδικα

```bat
git clone https://github.com/Lone-side/LogistikoCRM
cd LogistikoCRM
```

(ή αποσυμπίεσε το ZIP και άνοιξε Command Prompt μέσα στον φάκελο)

## 2. Πρώτη εγκατάσταση — ΜΙΑ φορά

Ο πιο απλός δρόμος: **διπλό κλικ στο `LogistikoCRM.bat`**. Στο πρώτο τρέξιμο
δημιουργεί το venv, εγκαθιστά τα πακέτα, φτιάχνει το `.env`, τρέχει τα
migrations και το αρχικό setup (cache table, ρόλοι, χρήστης `IamSUPER`).

Χειροκίνητα (ισοδύναμο, αν προτιμάς τη γραμμή εντολών):

```bat
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt
copy .env.development .env
venv\Scripts\python manage.py migrate
venv\Scripts\python manage.py createcachetable
venv\Scripts\python manage.py setupdata
cd frontend && npm install && cd ..
```

> ⚠️ **Η σειρά έχει σημασία**: πρώτα `setupdata`, ΠΟΤΕ `createsuperuser`
> πριν από αυτό (χαλάει τα pk των groups). Το `setupdata` δημιουργεί τους
> ρόλους και τον superuser **IamSUPER**.

Για το React UI χρειάζεται και το `cd frontend && npm install` (μία φορά) —
το launcher το εντοπίζει αυτόματα στις επόμενες εκκινήσεις.

## 3. Καθημερινή χρήση

Διπλό κλικ στο **`LogistikoCRM.bat`**. Ανοίγει:

- **React UI:** http://localhost:5173/
- **Django admin:** http://localhost:8000/el/456-admin/ (χρήστης `IamSUPER`)

Για τερματισμό: κλείσε τα δύο παράθυρα "LogistikoCRM Backend" και
"LogistikoCRM Frontend".

## 4. Ενημέρωση σε νέα έκδοση

```bat
git pull
venv\Scripts\python -m pip install -r requirements.txt
venv\Scripts\python manage.py migrate
cd frontend && npm install && cd ..
```

## Linux / Mac

Ίδια βήματα χωρίς το `.bat`:

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.development .env
python manage.py migrate
python manage.py createcachetable
python manage.py setupdata
python manage.py runserver            # terminal 1
cd frontend && npm install && npm run dev   # terminal 2
```

## Συχνά προβλήματα

- **«python δεν αναγνωρίζεται»**: ξαναεγκατάσταση Python με "Add to PATH".
- **Port 8000/5173 κατειλημμένο**: τρέχει ήδη παλιά εγκατάσταση — δες το
  βήμα 0 / κλείσε τα παλιά παράθυρα.
- **Ελληνικά «σπασμένα» στο τερματικό**: το launcher θέτει `chcp 65001`
  αυτόματα· σε δικό σου terminal τρέξε το πρώτα.
- Το τοπικό dev setup στέλνει emails μόνο στην κονσόλα
  (`EMAIL_BACKEND_CONSOLE=true` στο `.env.development`) — καμία πραγματική
  αποστολή.
