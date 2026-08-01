---
name: django-security
description: Checklist ασφάλειας για κάθε PR στο LogistikoCRM που προσθέτει ή αλλάζει Django views, API endpoints, serializers, uploads ή permissions.
---

# Django Security — Checklist ανά PR

Έλεγξε ΚΑΘΕ νέο ή τροποποιημένο endpoint για τα εξής:

1. **Permissions**: κανένα endpoint με σκέτο `IsAuthenticated` αν σερβίρει
   δεδομένα πελατών — πρόσθεσε `CanAccessClient` + `ClientScopedQuerysetMixin`
   (`accounting/permissions.py`, `accounting/mixins.py`) με σωστό `client_field`.
2. **Object-level access / IDOR**: κάθε detail view με `<pk>` πρέπει να
   φιλτράρει queryset ή να ελέγχει object permission — όχι μόνο κρυμμένα
   κουμπιά στο React. Το φιλτράρισμα γίνεται ΠΑΝΤΑ στο backend.
3. **Mass assignment**: serializers με explicit `fields` λίστα, ποτέ
   `fields = '__all__'` σε μοντέλα με ευαίσθητα πεδία.
4. **PII exposure**: πριν προσθέσεις πεδίο σε serializer, ρώτα: χρειάζεται
   ο καλών αυτό το πεδίο; (ΑΦΜ, ΑΜΚΑ, IBAN, διευθύνσεις = PII).
5. **Uploads**: επέκταση + μέγεθος validation, αποθήκευση μέσω
   `accounting/services/filing.py`, ποτέ user-controlled paths (traversal).
6. **CSRF/JWT**: μην απενεργοποιείς CSRF· τα public endpoints (AllowAny)
   χρειάζονται δικό τους rate limiting + password/token gate.
7. **Audit logging**: reveal/αλλαγές PII/διαγραφές → `common.models.AuditLog.log()`.
8. **Secrets**: δες το skill `credentials-and-secrets`.
9. **Errors**: άκυρα inputs → 400/404, όχι 500· ποτέ stack trace ή secret
   σε response.
10. **Tests**: κάθε νέο permission θέλει αρνητικό test (403/404 για χρήστη
    χωρίς δικαίωμα), όχι μόνο θετικό.
