# GDPR / Διαχείριση Προσωπικών Δεδομένων — LogistikoCRM

> Πρακτικός οδηγός για τη συμμόρφωση του λογιστικού γραφείου (data controller)
> ως προς τα προσωπικά δεδομένα που τηρεί το CRM. Συνοδεύει το
> `docs/SECURITY_DECISIONS.md`. Δεν αποτελεί νομική συμβουλή.

## 1. Ποια προσωπικά δεδομένα τηρούνται

| Πηγή (model) | Δεδομένα | Κατηγορία |
|---|---|---|
| `accounting.ClientProfile` | ΑΦΜ, ΑΜΚΑ, αριθμός ταυτότητας, ονοματεπώνυμο/πατρώνυμο, ημ. γέννησης, διευθύνσεις, τηλέφωνα, email, IBAN | Ταυτοποίηση/επικοινωνία/οικονομικά |
| `accounting.ClientProfile` (credentials) | κωδικοί TaxisNet/ΕΦΚΑ/ΓΕΜΗ | **Ευαίσθητα διαπιστευτήρια** |
| `mydata.MyDataCredentials` | myDATA user_id / subscription key | Διαπιστευτήρια (**κρυπτογραφημένα**, Fernet) |
| `accounting.ClientDocument` | μεταφορτωμένα παραστατικά/έγγραφα πελάτη | Οικονομικά/φορολογικά |
| `mydata.VATRecord` / `VATPeriodResult` | οικονομικά στοιχεία ΦΠΑ ανά πελάτη | Οικονομικά |
| `accounting.VoIPCall` | αριθμοί τηλεφώνου, ώρες κλήσεων | Επικοινωνία |
| `common.AuditLog` | user, action, IP, user-agent, timestamp | Δεδομένα ασφαλείας/ελέγχου |
| `User` (portal) | username (=ΑΦΜ), email, password hash | Ταυτοποίηση |

## 2. Νομική βάση & σκοπός

Τα δεδομένα τηρούνται για την **εκτέλεση των λογιστικών/φορολογικών υποχρεώσεων**
(σύμβαση + έννομη υποχρέωση, Άρθρο 6(1)(b)/(c) GDPR). Φορολογικά παραστατικά
υπόκεινται σε **υποχρεωτική διατήρηση** κατά την ελληνική φορολογική νομοθεσία
(τυπικά ≥5 έτη) — η διαγραφή δεν μπορεί να προηγηθεί αυτής της περιόδου.

## 3. Υφιστάμενα τεχνικά μέτρα (στον κώδικα)

- **Απομόνωση πολυ-μισθωτών (tenant isolation):** ο πελάτης βλέπει ΜΟΝΟ τα δικά
  του δεδομένα — `accounting/portal_mixins.py::ClientScopedQuerysetMixin` (fail-closed),
  `IsStaffUser` σε όλα τα management endpoints (βλ. SECURITY_DECISIONS).
- **Κρυπτογράφηση διαπιστευτηρίων myDATA:** Fernet (`mydata/encryption.py`).
- **Audit trail:** `common.AuditLog.log()` — create/update/delete/view/export/login,
  με IP & user-agent. Χρησιμοποίησέ το για export/erase ενέργειες (βλ. §5).
- **Έλεγχος πρόσβασης staff:** secret admin prefix (SD-002) + **2FA** (`ENABLE_ADMIN_2FA`).
- **Throttling & no-enumeration** σε login/reset (SD-003).
- **CSP + short-lived JWT** (SD-001).

## 4. Δικαίωμα πρόσβασης (Άρθρο 15) — export

Ο πελάτης βλέπει τα δικά του δεδομένα μέσω του portal (`/api/client/me/...`).
Για επίσημο αίτημα πρόσβασης, ο λογιστής εξάγει: `ClientProfile`, οι σχετικές
`MonthlyObligation`, `ClientDocument`, `VATRecord`, `VoIPCall`. (Δες admin export
actions στο `accounting/admin/clients.py`.)

## 5. Δικαίωμα διαγραφής (Άρθρο 17) — διαδικασία & ΚΕΝΟ

> ⚠️ **Δεν υπάρχει αυτοματοποιημένος μηχανισμός erasure/anonymization.** Η
> διαγραφή γίνεται χειροκίνητα από staff και **περιορίζεται** από τη φορολογική
> υποχρέωση διατήρησης (§2).

Τρέχουσα διαδικασία (χειροκίνητη):
1. Επιβεβαίωσε ότι έχει λήξει η υποχρεωτική περίοδος διατήρησης για τα παραστατικά.
2. Διέγραψε το `ClientProfile` από το admin — οι σχετικές εγγραφές με
   `on_delete=CASCADE` αφαιρούνται· πρόσεξε FKs με `PROTECT` (π.χ. `Invoice.counterpart`).
3. Διέγραψε τον συνδεδεμένο `User` (portal) και τυχόν μεταφορτωμένα αρχεία στο media.
4. Κατέγραψε την ενέργεια στο `AuditLog` (action=`delete`, severity=`high`).

**Συνιστώμενη βελτίωση (μελλοντικά):** management command
`anonymize_client <afm>` που (α) ψευδωνυμοποιεί ταυτοποιητικά πεδία, (β) σβήνει
διαπιστευτήρια/αρχεία, (γ) διατηρεί τα φορολογικώς απαιτούμενα aggregates, και
(δ) γράφει `AuditLog`. Προτιμότερο από hard-delete λόγω των `PROTECT` FKs.

## 6. Παραβίαση δεδομένων (breach)

Σε υποψία διαρροής: ανάκληση/rotation `SECRET_KEY` (επηρεάζει το Fernet key των
myDATA credentials → re-encrypt), rotation JWT, έλεγχος `AuditLog` για ύποπτη
πρόσβαση, ειδοποίηση ΑΠΔΠΧ εντός 72h αν απαιτείται.

## 7. Εκκρεμότητες (checklist)

- [ ] Management command `anonymize_client` (§5).
- [ ] Πολιτική διατήρησης ανά τύπο δεδομένου (ρητοί χρόνοι).
- [ ] Επιβεβαίωση ότι τα media (έγγραφα) σβήνονται μαζί με το `ClientProfile`.
- [ ] DPA (σύμβαση επεξεργασίας) με τυχόν τρίτους (hosting, myDATA, Zadarma/Fritz).
