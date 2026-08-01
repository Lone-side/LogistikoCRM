---
name: credentials-and-secrets
description: Κανόνες χειρισμού κωδικών και secrets στο LogistikoCRM. Χρήση σε ΚΑΘΕ αλλαγή που αγγίζει credentials πελατών (Taxisnet/ΕΦΚΑ/ΓΕΜΗ), myDATA, SMTP, tokens, ή encryption.
---

# Credentials & Secrets — Κανόνες

## Απαγορεύεται ρητά
- **Plaintext credentials σε μοντέλα**: κάθε secret αποθηκεύεται μέσω Fernet
  (`mydata/encryption.py`). Οι κωδικοί πελατών ζουν ΜΟΝΟ στο
  `accounting.models.ClientCredential` (`_secret_encrypted`).
- **Secrets σε serializers/responses**: κανένα secret δεν μπαίνει σε
  `Meta.fields` serializer. Αποκάλυψη μόνο μέσω του `reveal` action
  (`accounting/api_credentials.py`) με permission
  `accounting.view_client_credential_secret` + AuditLog.
- **Logging κωδικών**: ποτέ log/print/exception message με τιμή secret.
  Στο AuditLog καταγράφονται μόνο flags (`secret_changed: true`), ποτέ τιμές.
- **Secrets σε Claude/AI**: μην διαβάζεις, εμφανίζεις ή στέλνεις πραγματικές
  τιμές credentials σε συνομιλία, commit, PR ή test fixture. Στα tests χρήση
  ψεύτικων τιμών (π.χ. "test-secret-123").
- **Django SECRET_KEY ως data-encryption key**: η κρυπτογράφηση χρησιμοποιεί
  `DATA_ENCRYPTION_KEY_CURRENT` (ανεξάρτητο Fernet key). Το legacy
  SHA-256(SECRET_KEY) υπάρχει μόνο για αποκρυπτογράφηση παλιών δεδομένων.
- **Credentials σε Git**: ποτέ πραγματικές τιμές σε .env committed αρχεία,
  fixtures, ή migrations.

## Υποχρεωτικά σε κάθε PR που αγγίζει secrets
1. Regression test ότι το API response ΔΕΝ περιέχει το secret.
2. AuditLog entry σε κάθε reveal/change/delete.
3. Νέα encrypted πεδία προστίθενται στο `rotate_encryption_key` command.

## Υποδομή
- Κρυπτογράφηση: `mydata/encryption.py` (MultiFernet: CURRENT → PREVIOUS → legacy)
- Rotation: `python manage.py rotate_encryption_key [--generate|--dry-run]`
- Ρόλοι/permissions: `python manage.py setup_roles`
