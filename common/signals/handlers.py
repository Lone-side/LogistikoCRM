from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

from common.models import UserProfile
from common.utils.helpers import USER_MODEL


@receiver(post_save, sender=USER_MODEL)
def user_creation_handler(sender, instance, created, **kwargs):
    if created:
        # get_or_create ώστε η δημιουργία χρήστη να μην σκάει αν λείπει το group
        # (π.χ. σε φρέσκια βάση ή σε test χωρίς το groups fixture).
        co_workers, _ = Group.objects.get_or_create(name='co-workers')
        instance.groups.add(co_workers)
        UserProfile.objects.get_or_create(user=instance)
