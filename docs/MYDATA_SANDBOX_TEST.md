# myDATA sandbox — χειροκίνητο end-to-end test

Το τελευταίο βήμα του backlog πριν την παραγωγή: **πραγματική υποβολή σε
`mydataapidev.aade.gr` με αληθινά credentials**. Δεν αυτοματοποιείται και δεν
τρέχει στο CI — χρειάζεται λογαριασμό δοκιμών ΑΑΔΕ που δεν ζει στο repo.

Αυτό το runbook είναι για να το τρέξεις εσύ, μία φορά, και να καταγράψεις το
αποτέλεσμα στο τέλος.

---

## 0. Τι χρειάζεσαι

Από το [ΑΑΔΕ myDATA](https://www.aade.gr/mydata) (περιβάλλον δοκιμών):

- **User ID** — για το sandbox είναι το *username* του δοκιμαστικού
  λογαριασμού, **όχι** ΑΦΜ (στην παραγωγή είναι ΑΦΜ).
- **Subscription Key** — από το developer portal της ΑΑΔΕ.
- **ΑΦΜ εκδότη** για τα δοκιμαστικά παραστατικά.

⚠️ Τα credentials **ποτέ** σε commit, σε log, ή σε ticket. Μόνο στο τοπικό
`.env`, το οποίο είναι ήδη στο `.gitignore`.

---

## 1. Ρύθμιση περιβάλλοντος

Στο `.env`:

```bash
MYDATA_IS_SANDBOX=true          # ⚠️ ΚΡΙΣΙΜΟ — δες παρακάτω
MYDATA_USER_ID=<test username>
MYDATA_SUBSCRIPTION_KEY=<test key>
MYDATA_ISSUER_VAT=<ΑΦΜ εκδότη δοκιμών>
```

`MYDATA_IS_SANDBOX` έχει default `true` (`webcrm/settings.py`), δηλαδή
fail-safe: αν ξεχαστεί, πάει στο sandbox και όχι στην παραγωγή. **Μόνο** η
ρητή τιμή `false`/`0`/`no` ενεργοποιεί την παραγωγή.

Επιβεβαίωσε πριν κάνεις οτιδήποτε:

```bash
python manage.py shell -c "from django.conf import settings; \
print('SANDBOX' if settings.MYDATA_IS_SANDBOX else '⚠️ PRODUCTION')"
```

Αν δεν τυπώσει `SANDBOX`, **σταμάτα εδώ**.

---

## 2. Endpoints — μην τα «διορθώσεις»

Τα base URLs στο `mydata/client.py` είναι **ασύμμετρα εκ σχεδιασμού** και
αυτό είναι σωστό κατά την ΑΑΔΕ:

| Περιβάλλον | Base URL | Παράδειγμα |
|---|---|---|
| Παραγωγή | `https://mydatapi.aade.gr/myDATA` | `…/myDATA/SendInvoices` |
| Sandbox | `https://mydataapidev.aade.gr` | `…/SendInvoices` (**χωρίς** `/myDATA`) |

Επαληθεύτηκε στο επίσημο [test URLs PDF της ΑΑΔΕ](https://www.aade.gr/sites/default/files/2022-12/test_urls_0.pdf).
Το `/myDATAProvider/…` αφορά *παρόχους* ηλεκτρονικής τιμολόγησης — δεν μας αφορά.

---

## 3. Έλεγχος σύνδεσης (read-only, ακίνδυνο)

Ξεκίνα με ανάγνωση, όχι υποβολή:

```bash
python manage.py sync_mydata --days 7 --type both
```

Αναμενόμενο: σύνδεση χωρίς `MyDataAuthError`. Μηδέν παραστατικά σε καινούριο
δοκιμαστικό λογαριασμό είναι φυσιολογικό — σημασία έχει ότι δεν έσκασε στο 401/403.

**Αν πάρεις 401/403:** λάθος user_id (βάζεις ΑΦΜ αντί για username;) ή λάθος
subscription key, ή το key δεν έχει ενεργοποιηθεί για το περιβάλλον δοκιμών.

---

## 4. Υποβολή δοκιμαστικού τιμολογίου

Από το admin: Τιμολόγια → επίλεξε ένα → action αποστολής προς myDATA.
Ή από shell:

```bash
python manage.py shell
```
```python
from mydata.models import Invoice
from mydata.services import MyDataService
inv = Invoice.objects.get(pk=<ID>)
print(MyDataService().submit_invoice(inv))
```

Έλεγξε ότι:

- [ ] Επιστρέφεται **MARK** και αποθηκεύεται στο `Invoice`
- [ ] Το `VATSyncLog`/sync log δεν μένει `PENDING`
- [ ] Στα logs **δεν** εμφανίζεται user_id ή subscription key
- [ ] Ελληνικοί χαρακτήρες (επωνυμία, περιγραφή) περνούν σωστά — χωρίς `?` ή mojibake
- [ ] Το ίδιο τιμολόγιο δεύτερη φορά δεν δημιουργεί διπλό MARK

Μετά δοκίμασε **ανάκτηση**: `python manage.py fetch_invoices` και επιβεβαίωσε
ότι το παραστατικό επιστρέφει με το ίδιο MARK.

---

## 5. Ακύρωση

```python
MyDataService().client.cancel_invoice(mark='<MARK>')
```

- [ ] Επιστρέφεται `cancellationMark`

---

## 6. Επιστροφή σε ασφαλή κατάσταση

Μετά το τεστ, **καθάρισε τα δοκιμαστικά credentials από το `.env`** ώστε να
μη μείνουν σε μηχάνημα ανάπτυξης, και επιβεβαίωσε ότι το
`MYDATA_IS_SANDBOX` παραμένει `true` παντού εκτός παραγωγής.

---

## 7. Καταγραφή αποτελέσματος

| Πεδίο | Τιμή |
|---|---|
| Ημερομηνία | |
| Έκδοση/commit | |
| Sync (βήμα 3) | ☐ OK ☐ Απέτυχε |
| Υποβολή + MARK (βήμα 4) | ☐ OK ☐ Απέτυχε |
| Ανάκτηση | ☐ OK ☐ Απέτυχε |
| Ακύρωση (βήμα 5) | ☐ OK ☐ Απέτυχε |
| Παρατηρήσεις | |

Όταν όλα είναι OK, σημείωσε το backlog #5 στο `CLAUDE.md` ως ολοκληρωμένο.
