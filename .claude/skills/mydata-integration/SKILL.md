---
name: mydata-integration
description: Κανόνες για την ενσωμάτωση myDATA (ΑΑΔΕ) του LogistikoCRM — δομή, credentials, XML συμβόλαιο, environments. Χρήση σε κάθε αλλαγή στο mydata/ app ή στη ροή τιμολογίων.
---

# myDATA Integration

## Δομή (`mydata/` app)
- `client.py` — HTTP client προς ΑΑΔΕ (SendInvoices, RequestDocs, VAT info)
- `invoice_xml.py` — παραγωγή XML κατά το **επίσημο συμβόλαιο ΑΑΔΕ**
- `models.py` — `MyDataCredentials` (encrypted user_id/subscription_key), invoices, `VATSyncLog`
- `encryption.py` — Fernet/MultiFernet (κοινό για όλο το project — βλ. `credentials-and-secrets`)
- `management/commands/` — `sync_mydata`, `fetch_invoices`, `mydata_sync_vat`, `rotate_encryption_key`
- Tests: `tests/mydata/` (client parsing, XML, sync paths, encryption keys)

## Environments
- `MYDATA_ENVIRONMENT=test` → sandbox `mydataapidev.aade.gr` · `prod` → παραγωγή.
- Credentials ΜΟΝΟ μέσω `MyDataCredentials` (κρυπτογραφημένα στη βάση) ή env vars — ποτέ hardcoded, ποτέ σε logs/tests. Στα tests: mock responses, ψεύτικα κλειδιά.
- Εκκρεμεί το χειροκίνητο end-to-end sandbox βήμα με πραγματικά credentials (backlog #5 στο CLAUDE.md) — δεν αυτοματοποιείται από τον Claude.

## Απαράβατα
1. **Αλλαγές στο XML/πεδία μόνο με βάση την επίσημη τεκμηρίωση ΑΑΔΕ** (https://www.aade.gr/mydata) — με αναφορά πηγής/έκδοσης συμβολαίου στο PR, ποτέ «από μνήμη» (βλ. `greek-tax-domain`).
2. Κάθε αλλαγή στο `invoice_xml.py` θέλει test με αναμενόμενο XML στο `tests/mydata/test_invoice_xml.py`.
3. Σφάλματα ΑΑΔΕ API: log χωρίς credentials στο μήνυμα· retries με backoff υπάρχουν στο client — μην προσθέτεις δεύτερο layer.
4. Υποβολή σε myDATA = εξωτερική, μη αναστρέψιμη ενέργεια: σε παραγωγικό context απαιτεί ρητή επιβεβαίωση χρήστη.
