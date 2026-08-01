---
name: django-migrations
description: Κανόνες για Django migrations στο LogistikoCRM (ιδιαίτερο numbering, data migrations, staged removals). Χρήση πριν από ΚΑΘΕ αλλαγή σε models ή δημιουργία migration.
---

# Django Migrations — Κανόνες

## Numbering (ιδιαιτερότητα του repo)
Το `accounting/migrations/` περιέχει `0001..`, `9999_add_performance_indexes` και `10015+`. **Συνέχισε πάντα από το μεγαλύτερο υπάρχον νούμερο** (π.χ. 10018) — μην αναδιατάξεις, μην «διορθώσεις» τα παλιά.

## Πριν & μετά
```bash
python manage.py makemigrations --dry-run -v 2   # δες τι θα παραχθεί
python manage.py makemigrations --check          # καθαρό μετά τις αλλαγές
python manage.py migrate                          # δοκιμή σε ΑΝΤΙΓΡΑΦΟ του db.sqlite3
```
Κράτα backup του db.sqlite3 στο scratchpad πριν από destructive migrate.

## Απαράβατα
1. **Ποτέ edit σε applied migration** — νέο migration για κάθε διόρθωση.
2. **Data migrations**: μόνο `apps.get_model(...)` (historical models)· ΟΧΙ imports των πραγματικών models, ΟΧΙ model properties/custom methods — αν χρειάζεσαι helper (π.χ. `encrypt_value`), import από module, όχι από model.
3. **Μη αναστρέψιμες μεταφορές** (π.χ. plaintext → encrypted): reverse = no-op με σχόλιο γιατί. Ποτέ reverse που ξαναγράφει ευαίσθητα δεδομένα plaintext.
4. **Staged pattern για αφαίρεση πεδίων με δεδομένα** (όπως τα 10015-10017):
   - (α) schema: νέο μοντέλο/πεδία
   - (β) data: αντιγραφή/μετατροπή
   - (γ) schema: RemoveField των παλιών
   Τρία ξεχωριστά migrations, στο ίδιο PR.
5. **Custom permissions** σε `Meta.permissions` δημιουργούνται με το migration — commands που τα χρησιμοποιούν (π.χ. `setup_roles`) τρέχουν ΜΕΤΑ το migrate.
6. Πριν από μεγάλες αλλαγές σε models: ρώτα τον χρήστη (κανόνας CLAUDE.md).

## Tests
Κάθε data migration συνοδεύεται από test που επιβεβαιώνει τη μεταφορά (βλ. `tests/accounting/test_client_credentials.py` ως πρότυπο).
