from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

from common.models import UserProfile
from common.utils.helpers import USER_MODEL

logger = logging.getLogger(__name__)


@receiver(post_save, sender=USER_MODEL)
def user_creation_handler(sender, instance, created, **kwargs):
    """
    Signal handler που εκτελείται όταν δημιουργείται νέος user.

    Προσθέτει τον user στο group 'co-workers' και δημιουργεί UserProfile.
    Είναι robust - δεν αποτυγχάνει αν το group δεν υπάρχει.
    """
    if created:
        # Δημιουργία UserProfile
        UserProfile.objects.get_or_create(user=instance)

        # Προσθήκη στο co-workers group (αν υπάρχει)
        try:
            co_workers = Group.objects.get(name='co-workers')
            instance.groups.add(co_workers)
            logger.debug(f"Added user {instance.username} to co-workers group")
        except Group.DoesNotExist:
            logger.warning(
                f"Group 'co-workers' does not exist. "
                f"User {instance.username} was created without group assignment. "
                f"Run: python manage.py loaddata groups.json"
            )

