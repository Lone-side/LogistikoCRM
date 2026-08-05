---
name: logistiko-architecture
description: Χάρτης αρχιτεκτονικής του LogistikoCRM — πού ζει τι, βασικές συμβάσεις και τι ΔΕΝ πρέπει να αγγίξεις. Διάβασέ το στην αρχή κάθε session ή πριν δουλέψεις σε άγνωστη περιοχή του codebase.
---

# LogistikoCRM Architecture Map

## Apps και ρόλοι
| App | Ρόλος |
|-----|-------|
| `accounting/` | **Core**: ClientProfile, MonthlyObligation, ClientDocument, ClientCredential, tickets, emails, portal |
| `mydata/` | Ενσωμάτωση ΑΑΔΕ myDATA (client, XML, encrypted credentials) — βλ. skill `mydata-integration` |
| `voip/` | Zadarma cloud PBX· το Fritz!Box monitoring ζει στο `accounting/` + `fritz_monitor.py` |
| `common/` | Shared: `AuditLog` (common/models.py), protected media, base utils |
| `crm/`, `tasks/`, `inventory/`, `analytics/`, `chat/`, `massmail/`, `help/` | Κληρονομιά Django-CRM — άγγιξέ τα μόνο αν ζητηθεί |
| `webcrm/` | Settings, celery, urls |
| `frontend/` | React 19 + Vite 7 + TS + Tailwind 4 (tokens στο `src/index.css`, primitives στο `src/components/ui/`) |

## Κρίσιμα σημεία στο accounting/
- API ανά αρχείο: `api_clients.py`, `api_documents.py`, `api_obligations.py`, `api_credentials.py`, `api_file_manager.py`, κλπ.
- RBAC: `mixins.py` (`ClientScopedQuerysetMixin`) + `permissions.py` (`CanAccessClient`) — κάθε νέο viewset με δεδομένα πελάτη τα χρησιμοποιεί. Flag: `ENFORCE_CLIENT_ASSIGNMENT`.
- Αρχειοθέτηση αρχείων: ΠΑΝΤΑ μέσω `accounting/services/filing.py` (ενιαία πηγή αλήθειας για paths/ονομασία).
- Κωδικοί πελατών: ΜΟΝΟ `ClientCredential` (encrypted) — βλ. skill `credentials-and-secrets`.

## URLs
- Το `accounting/urls.py` είναι μεγάλο (~150 patterns)· το router είναι mounted ΚΑΙ σε `api/` ΚΑΙ σε `api/v1/` (γραμμές ~330) — νέα endpoints μπαίνουν στο κοινό router ή ρητά κάτω από `api/v1/`.
- Admin: `/el/456-admin/` · CRM: `/el/123/`.

## Setup (Η ΣΕΙΡΑ ΜΕΤΡΑΕΙ)
```
migrate → createcachetable → setupdata (ΟΧΙ createsuperuser πριν το setupdata)
```

## ΜΗΝ αγγίξεις χωρίς λόγο
- Migrations numbering: το accounting έχει `9999_*` και `10015+` — συνέχισε από το μεγαλύτερο υπάρχον νούμερο, μην «διορθώσεις» τη σειρά. Βλ. skill `django-migrations`.
- Τα encrypted πεδία (`_secret_encrypted`, `_encrypted_*`) — ποτέ απευθείας εγγραφή, μόνο μέσω properties.
- Το διπλό api/ + api/v1/ mount — η κατάργηση του legacy είναι σχεδιασμένο P1, όχι παρενέργεια άλλου PR.
