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


def _require_locked_access(user, client):
    """
    Fail-closed access έλεγχος ΠΑΝΩ στο locked state (blocker «stale
    object authorization»): το view κάνει client scoping ΠΡΙΝ το lock,
    οπότε το instance που φτάνει εδώ μπορεί να έχει αλλάξει πελάτη στο
    μεταξύ. Καλείται ΜΟΝΟ αφού αποκτηθούν τα locks, με τον client του
    locked row — ποτέ του stale instance.

    - `user is None` (τεκμηριωμένο system automation): δεν περιορίζεται.
    - `client is None` (unassigned/triage): προσβάσιμο σε όλους με τα
      model permissions — υπάρχουσα triage policy.
    - Αλλιώς: ο locked πόρος πρέπει να είναι προσβάσιμος στον χρήστη,
      αλλιώς PermissionDenied ΧΩΡΙΣ καμία μετάλλαξη.
    """
    if user is None or client is None:
        return
    from django.core.exceptions import PermissionDenied
    from accounting.services.access import user_can_access_client
    if not user_can_access_client(user, client):
        raise PermissionDenied(
            'Ο πόρος ανήκει σε μη προσβάσιμο πελάτη.'
        )


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

        # Post-lock access revalidation: locked call (ΟΧΙ το stale
        # instance) + target client — stale κλήση που έγινε ξένη πριν
        # το lock δεν μεταβάλλεται από scoped χρήστη
        _require_locked_access(user, locked_call.client)
        _require_locked_access(user, new_client)

        if linked is not None:
            # Cross-side gap (τελικό εύρημα review): το linked Ticket
            # μπορεί να μεταβληθεί εδώ — σε legacy inconsistent state
            # (Call=A, Ticket=B) scoped χρήστης του Α δεν επιτρέπεται
            # να αγγίξει το ξένο ticket. Triage (client=None) και
            # user=None (system) μένουν ανεπηρέαστα.
            _require_locked_access(user, linked.client)
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
        # Post-lock access revalidation και στις δύο locked πλευρές
        _require_locked_access(user, locked_ticket.client)
        _require_locked_access(user, locked_call.client)
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


def delete_call(call, *, user=None):
    """
    Atomic διαγραφή κλήσης με σεβασμό του cross-model invariant.

    Η διαγραφή κλήσης με linked ticket κάνει `Ticket.call → NULL`
    (SET_NULL) — δηλαδή μεταβάλλει Ticket, άρα απαιτεί ΚΑΙ
    `accounting.change_ticket` (όπως ήδη επιβάλλει το Admin). Κλήση
    χωρίς ticket: αρκεί το `delete_voipcall` (ελέγχεται στο view layer).

    Ενιαία global σειρά κλειδώματος VoIPCall → Ticket, με revalidation
    στο locked state (όχι στο stale instance του caller): αν ticket
    συνδέθηκε ΜΕΤΑ το lookup του view, fail closed. Τα VoIPCallLog
    επιβιώνουν με τα snapshots τους (SET_NULL στο call FK).
    """
    from django.core.exceptions import PermissionDenied
    from accounting.models import Ticket, VoIPCall

    with transaction.atomic():
        locked_call = VoIPCall.objects.select_for_update().filter(
            pk=call.pk
        ).first()
        if locked_call is None:
            return  # ήδη διαγραμμένη — τίποτα να κάνουμε
        locked_ticket = Ticket.objects.select_for_update().filter(
            call=locked_call
        ).first()
        # Post-lock access revalidation στο ΙΔΙΟ το locked primary
        # object (stale-authorization blocker): κλήση που άλλαξε πελάτη
        # μεταξύ view lookup και lock δεν διαγράφεται από scoped χρήστη
        _require_locked_access(user, locked_call.client)
        if locked_ticket is not None:
            if user is not None and not user.has_perm(
                'accounting.change_ticket'
            ):
                raise PermissionDenied(
                    'Η διαγραφή της κλήσης αποσυνδέει το ticket της — '
                    'απαιτείται δικαίωμα αλλαγής ticket.'
                )
            _require_locked_access(user, locked_ticket.client)
        locked_call.delete()


def delete_ticket(ticket, *, user=None):
    """
    Atomic διαγραφή ticket με σεβασμό του cross-model invariant.

    Το pre_delete signal μεταβάλλει το linked VoIPCall
    (`ticket_created=False`, `ticket_id=None`) — άρα ticket με κλήση
    απαιτεί ΚΑΙ `accounting.change_voipcall`. Ticket χωρίς κλήση: αρκεί
    το `delete_ticket` (view layer).

    Σειρά κλειδώματος VoIPCall → Ticket με revalidation· αποτυχία του
    signal ή οποιουδήποτε update κάνει rollback ολόκληρη τη διαγραφή.
    """
    from django.core.exceptions import PermissionDenied
    from accounting.models import Ticket, VoIPCall

    with transaction.atomic():
        # Global σειρά: πρώτα η κλήση (από το άφρακτο instance), μετά το
        # ticket, και revalidation της σχέσης στο locked state.
        locked_call = None
        if ticket.call_id:
            locked_call = VoIPCall.objects.select_for_update().filter(
                pk=ticket.call_id
            ).first()
        locked_ticket = Ticket.objects.select_for_update().filter(
            pk=ticket.pk
        ).first()
        if locked_ticket is None:
            return
        if locked_ticket.call_id and (
            locked_call is None or locked_ticket.call_id != locked_call.pk
        ):
            # Η σχέση άλλαξε μεταξύ lookup και lock — fail closed
            raise ValidationError({
                'call': 'Η σύνδεση κλήσης-ticket άλλαξε κατά τη διάρκεια '
                        'της ενέργειας — δοκιμάστε ξανά.'
            })
        # Post-lock access revalidation στο ΙΔΙΟ το locked primary
        # object: ticket που άλλαξε πελάτη μεταξύ lookup και lock δεν
        # διαγράφεται από scoped χρήστη
        _require_locked_access(user, locked_ticket.client)
        if locked_ticket.call_id:
            if user is not None and not user.has_perm(
                'accounting.change_voipcall'
            ):
                raise PermissionDenied(
                    'Η διαγραφή του ticket ενημερώνει τη συνδεδεμένη '
                    'κλήση — απαιτείται δικαίωμα αλλαγής κλήσης.'
                )
            _require_locked_access(user, locked_call.client)
        # Το pre_delete signal τρέχει εδώ, μέσα στο atomic — αποτυχία
        # του update της κλήσης κάνει rollback και τη διαγραφή.
        locked_ticket.delete()


def create_ticket_for_call(call, *, user=None, title=None, description='',
                           priority='medium'):
    """
    Atomic δημιουργία Ticket από κλήση: Ticket create + Call flags
    (`ticket_created`, `ticket_id`) + VoIPCallLog σε ΜΙΑ συναλλαγή.

    Απαιτεί `add_ticket` ΚΑΙ `change_voipcall` όταν δίνεται user (η
    ενέργεια μεταβάλλει και την κλήση). Κλειδώνει την κλήση και
    επανελέγχει ότι δεν υπάρχει ήδη ticket — ταυτόχρονο διπλό
    create σειριοποιείται και ο δεύτερος παίρνει ValidationError,
    ποτέ δύο tickets ή μερικά flags.
    """
    from django.core.exceptions import PermissionDenied
    from accounting.models import Ticket, VoIPCall, VoIPCallLog

    if user is not None and not user.has_perms(
        ('accounting.add_ticket', 'accounting.change_voipcall')
    ):
        raise PermissionDenied(
            'Η δημιουργία ticket από κλήση απαιτεί δικαιώματα προσθήκης '
            'ticket και αλλαγής κλήσης.'
        )
    with transaction.atomic():
        locked_call = VoIPCall.objects.select_for_update().get(pk=call.pk)
        # Post-lock access revalidation ΠΡΙΝ δημιουργηθεί οτιδήποτε:
        # κλήση που έγινε ξένη μεταξύ lookup και lock δεν παίρνει ticket
        _require_locked_access(user, locked_call.client)
        if Ticket.objects.filter(call=locked_call).exists():
            raise ValidationError({
                'call': 'Υπάρχει ήδη ticket για αυτή την κλήση.'
            })
        ticket = Ticket.objects.create(
            call=locked_call,
            client=locked_call.client,
            title=title or f'Κλήση από {locked_call.phone_number}',
            description=description,
            priority=priority,
            status='open',
        )
        locked_call.ticket_created = True
        locked_call.ticket_id = str(ticket.id)
        locked_call.save(update_fields=['ticket_created', 'ticket_id'])
        VoIPCallLog.objects.create(
            call=locked_call,
            action='ticket_created',
            description=f'Ticket #{ticket.id} created: {ticket.title}',
        )
    call.ticket_created = True
    call.ticket_id = str(ticket.id)
    return ticket
