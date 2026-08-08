# -*- coding: utf-8 -*-
"""
Κεντρικό, transactional service για αλλαγή πελάτη VoIP κλήσης.

Όλα τα paths που αλλάζουν το VoIPCall.client (API update, match_client,
auto_match, auto_match_all/batch, admin) περνούν από εδώ, ώστε το
invariant κλήσης-ticket να επιβάλλεται ΠΑΝΤΑ:
- κλήση και linked ticket καταλήγουν στον ίδιο πελάτη (atomic, με
  select_for_update και στα δύο rows),
- δεν επιτρέπεται unassign της μίας πλευράς όσο η άλλη μένει bound,
- σε αποτυχία δεν μεταβάλλεται καμία πλευρά (transaction rollback),
- το client_email ενημερώνεται/καθαρίζεται συνεπώς.

ΔΕΝ βασιζόμαστε στο model.clean() — το save() δεν το καλεί αυτόματα.
"""
from django.core.exceptions import ValidationError
from django.db import transaction


def change_call_client(call, new_client, *, user=None, log_action=None):
    """
    Αλλάζει τον πελάτη μιας κλήσης atomic, μαζί με το linked ticket.

    - `user`: όταν δίνεται, η προώθηση σε bound ticket άλλου πελάτη
      απαιτεί το permission `accounting.change_ticket`.
    - `log_action`: προαιρετικό VoIPCallLog action ('client_matched' κλπ)
      που γράφεται μόνο αν η αλλαγή ολοκληρωθεί.

    Raises django ValidationError σε παραβίαση του invariant — ο caller
    τη μεταφράζει σε 400/DRF ValidationError όπου χρειάζεται.
    """
    from accounting.models import Ticket, VoIPCall, VoIPCallLog

    new_client_id = new_client.pk if new_client is not None else None

    with transaction.atomic():
        locked_call = VoIPCall.objects.select_for_update().get(pk=call.pk)
        linked = Ticket.objects.select_for_update().filter(
            call=locked_call
        ).first()

        if linked is not None:
            if linked.client_id is not None:
                if new_client_id is None:
                    raise ValidationError({
                        'client': 'Η κλήση έχει ticket αντιστοιχισμένο σε '
                                  'πελάτη — η αφαίρεση πελάτη πρέπει να '
                                  'γίνει και στα δύο μαζί.'
                    })
                if new_client_id != linked.client_id:
                    if user is not None and not user.has_perm(
                        'accounting.change_ticket'
                    ):
                        raise ValidationError({
                            'client': 'Η αλλαγή πελάτη ενημερώνει και το '
                                      'συνδεδεμένο ticket — απαιτείται '
                                      'δικαίωμα αλλαγής ticket.'
                        })
                    linked.client_id = new_client_id
                    linked.save(update_fields=['client'])
            elif new_client_id is not None:
                # Unassigned (triage) linked ticket: παίρνει τον ίδιο
                # πελάτη — atomic ενημέρωση και των δύο πλευρών
                linked.client_id = new_client_id
                linked.save(update_fields=['client'])

        locked_call.client_id = new_client_id
        locked_call.client_email = (
            (new_client.email or '') if new_client is not None else ''
        )
        locked_call.save(update_fields=['client', 'client_email'])

        # Current-attribution contract (audit finding client-mismatch):
        # όσο υπάρχει η κλήση, ΚΑΘΕ log της έχει snapshot client ίδιο με
        # την κλήση — αλλιώς ο (νέος) scoped owner δεν βλέπει το πλήρες
        # ιστορικό και το audit gate σκάει. Μέσα στο ίδιο transaction:
        # αποτυχία εδώ κάνει rollback ΚΑΙ την αλλαγή πελάτη.
        VoIPCallLog.objects.filter(call=locked_call).update(
            client=new_client_id)

        if log_action and new_client is not None:
            VoIPCallLog.objects.create(
                call=locked_call,
                action=log_action,
                description=f'Client set: id={new_client_id}',
            )

    # Συγχρονισμός του in-memory instance του caller
    call.client = new_client
    call.client_id = new_client_id
    call.client_email = locked_call.client_email
    return locked_call


def sync_ticket_call_client(ticket, *, user=None):
    """
    Επιβολή του invariant ΑΠΟ την πλευρά του ticket, atomic.

    Μετά τη δημιουργία/ενημέρωση ενός ticket με πελάτη που είναι
    συνδεδεμένο σε unassigned κλήση, αντιστοιχίζει και την κλήση στον ίδιο
    πελάτη (policy A) — ώστε να μην υπάρξει ποτέ ticket(client=X) +
    call(client=None). Αν η κλήση είναι ήδη bound σε άλλον πελάτη, ρίχνει
    ValidationError (ο caller το έχει ήδη μπλοκάρει, εδώ είναι backstop).

    Απαιτεί `change_voipcall` όταν πράγματι αλλάζει την κλήση.
    """
    from django.core.exceptions import ValidationError
    from accounting.models import Ticket, VoIPCall

    if not ticket.call_id or not ticket.client_id:
        return
    with transaction.atomic():
        # Ενιαία global σειρά κλειδώματος: ΠΡΩΤΑ VoIPCall, ΜΕΤΑ Ticket —
        # ίδια με το change_call_client και τα VoIPCall admin paths. Η
        # αντίστροφη σειρά (ticket → call) αναπαρήχθη ως deadlock σε
        # PostgreSQL 14 με ταυτόχρονο call-side κλείδωμα. Το call_id
        # διαβάζεται από το (άφρακτο) instance του caller και
        # επανεπιβεβαιώνεται στο locked ticket — αν η σχέση άλλαξε στο
        # μεταξύ, fail closed (backstop, καμία μεταβολή).
        locked_call = VoIPCall.objects.select_for_update().filter(
            pk=ticket.call_id
        ).first()
        locked_ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
        if not locked_ticket.call_id or not locked_ticket.client_id:
            return
        if locked_call is None or locked_ticket.call_id != locked_call.pk:
            raise ValidationError({
                'call': 'Η σύνδεση κλήσης-ticket άλλαξε κατά τη διάρκεια '
                        'της ενέργειας — δοκιμάστε ξανά.'
            })
        if locked_call.client_id == locked_ticket.client_id:
            return
        if locked_call.client_id is not None:
            raise ValidationError({
                'call': 'Η κλήση ανήκει σε διαφορετικό πελάτη από το ticket.'
            })
        if user is not None and not user.has_perm('accounting.change_voipcall'):
            raise ValidationError({
                'call': 'Η αντιστοίχιση της κλήσης στον πελάτη του ticket '
                        'απαιτεί δικαίωμα αλλαγής κλήσης.'
            })
        client = locked_ticket.client
        locked_call.client_id = locked_ticket.client_id
        locked_call.client_email = (client.email or '') if client else ''
        locked_call.save(update_fields=['client', 'client_email'])

        # Current-attribution contract: τα υπάρχοντα logs της κλήσης
        # ακολουθούν τον νέο πελάτη, atomic με την ίδια την αλλαγή.
        from accounting.models import VoIPCallLog
        VoIPCallLog.objects.filter(call=locked_call).update(
            client=locked_ticket.client_id)
