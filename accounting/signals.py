# -*- coding: utf-8 -*-
"""
Signals for accounting app.

Handles:
- Ticket-call relationship cleanup
- Auto-creation of ClientObligation for new clients
"""
import logging

from django.db.models.signals import pre_delete, post_save
from django.dispatch import receiver
from django.conf import settings

logger = logging.getLogger(__name__)


# ============================================
# AUTO-CREATE CLIENT OBLIGATION
# ============================================

@receiver(post_save, sender='accounting.ClientProfile')
def auto_create_client_obligation(sender, instance, created, **kwargs):
    """
    Αυτόματη δημιουργία ClientObligation για νέους πελάτες.

    Ενεργοποιείται μόνο αν:
    1. Είναι νέος πελάτης (created=True)
    2. Υπάρχει το setting AUTO_CREATE_CLIENT_OBLIGATION = True
    3. Υπάρχει default profile (AUTO_CLIENT_OBLIGATION_PROFILE)
    """
    if not created:
        return

    # Έλεγχος αν είναι ενεργοποιημένο
    auto_create = getattr(settings, 'AUTO_CREATE_CLIENT_OBLIGATION', True)
    if not auto_create:
        return

    # Δημιουργία ClientObligation χωρίς profiles (ο χρήστης θα τα προσθέσει)
    from accounting.models import ClientObligation, ObligationProfile

    try:
        # Δημιούργησε ClientObligation (χωρίς profiles αρχικά)
        client_obl, obl_created = ClientObligation.objects.get_or_create(
            client=instance,
            defaults={'is_active': True}
        )

        if obl_created:
            # Αν υπάρχει default profile, πρόσθεσέ το
            default_profile_name = getattr(settings, 'AUTO_CLIENT_OBLIGATION_PROFILE', None)
            if default_profile_name:
                try:
                    default_profile = ObligationProfile.objects.get(name=default_profile_name)
                    client_obl.obligation_profiles.add(default_profile)
                    logger.info(
                        f"ClientObligation created for {instance.eponimia} "
                        f"with default profile: {default_profile_name}"
                    )
                except ObligationProfile.DoesNotExist:
                    logger.warning(
                        f"Default profile '{default_profile_name}' not found. "
                        f"ClientObligation created without profile."
                    )
            else:
                logger.info(
                    f"ClientObligation created for {instance.eponimia} (no default profile)"
                )
    except Exception as e:
        logger.error(f"Error creating ClientObligation for {instance.eponimia}: {e}")


@receiver(pre_delete, sender='accounting.Ticket')
def cleanup_orphan_call_on_ticket_delete(sender, instance, **kwargs):
    """
    Όταν διαγράφεται Ticket, ενημέρωσε το VoIPCall ότι δεν έχει πλέον ticket.

    Χρησιμοποιούμε pre_delete γιατί στο post_delete το call μπορεί να έχει ήδη
    διαγραφεί (CASCADE).
    """
    if instance.call_id:
        try:
            # Ενημέρωση μόνο αν δεν διαγράφεται και η κλήση
            from accounting.models import VoIPCall
            call = VoIPCall.objects.filter(pk=instance.call_id).first()
            if call:
                # Σημειώνουμε για μετά (αποφυγή infinite loops)
                call._ticket_being_deleted = True
                call.ticket_created = False
                call.ticket_id = None
                call.save(update_fields=['ticket_created', 'ticket_id'])
                logger.info(f"Call {call.call_id}: ticket_created reset to False")
        except Exception:
            # Fail closed: το signal προστατεύει data invariant — ΚΑΘΕ
            # αποτυχία ενημέρωσης της κλήσης πρέπει να ακυρώνει ολόκληρη
            # τη διαγραφή του ticket (rollback στο atomic του caller),
            # όχι σιωπηλά ticket_created=True προς ανύπαρκτο ticket.
            # (Η απουσία κλήσης καλύπτεται ήδη ρητά από το .first().)
            logger.exception(
                'Αποτυχία ενημέρωσης κλήσης κατά τη διαγραφή ticket')
            raise
