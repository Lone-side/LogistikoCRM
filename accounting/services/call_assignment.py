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
