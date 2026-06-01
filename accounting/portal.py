# -*- coding: utf-8 -*-
"""
Client Portal helpers
=====================
Utilities για τη διάκριση staff vs client χρηστών και την ασφαλή απομόνωση
δεδομένων στο client portal.

Σχεδιαστική αρχή: 1 πελάτης = 1 login. Ο ρόλος "client" προσδιορίζεται μέσω
membership στο Django Group 'client' (ίδιο pattern με το 'co-workers').
"""

CLIENT_GROUP_NAME = 'client'


def is_client_user(user) -> bool:
    """
    True αν ο χρήστης είναι πελάτης portal (όχι staff).

    Ένας χρήστης θεωρείται client όταν:
      - είναι authenticated, ΚΑΙ
      - δεν είναι staff/superuser, ΚΑΙ
      - ανήκει στο group 'client' Ή έχει συνδεδεμένο ClientProfile.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return False
    if user.groups.filter(name=CLIENT_GROUP_NAME).exists():
        return True
    # Fallback: αν υπάρχει συνδεδεμένο ClientProfile, είναι client.
    return hasattr(user, 'client_profile') and user.client_profile is not None


def get_client_profile(user):
    """
    Επιστρέφει το ClientProfile που ανήκει στον χρήστη, ή None.
    Ασφαλές: δεν ρίχνει exception αν δεν υπάρχει σύνδεση.
    """
    if not user or not user.is_authenticated:
        return None
    profile = getattr(user, 'client_profile', None)
    return profile
