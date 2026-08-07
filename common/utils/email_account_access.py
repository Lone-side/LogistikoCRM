# -*- coding: utf-8 -*-
"""
Κεντρικός έλεγχος πρόσβασης σε EmailAccount (mailbox ownership).

Η πολιτική ΔΕΝ επινοήθηκε εδώ — αντιγράφει την ήδη υπάρχουσα κανονική
πολιτική του project για την ΙΔΙΑ ακριβώς λειτουργία (ανάγνωση mailbox
μέσω IMAP), όπως εκφράζεται στο ``common/views/select_emails_import.py``::

    q_params = Q(owner=request.user) | Q(co_owner=request.user)
    q_params = q_params & Q(do_import=True)
    if request.user.department_id:
        q_params = q_params & Q(department_id=request.user.department_id)

Δηλαδή:

* ``owner`` — ο κάτοχος του account (``common.models.Base.owner``).
* ``co_owner`` — το πεδίο shared/team πρόσβασης του EmailAccount
  (``massmail/models/email_account.py``). Είναι το μοναδικό πεδίο
  «μοιραζόμενου» account στο μοντέλο.
* ``department`` — λειτουργεί **περιοριστικά** (AND), όπως στο
  select_emails_import: όταν ο χρήστης είναι κλειδωμένος σε department,
  βλέπει μόνο accounts του department του. Το department **ΠΟΤΕ δεν
  παραχωρεί** από μόνο του πρόσβαση — πουθενά στο codebase δεν δίνει
  department-only πρόσβαση σε EmailAccount, οπότε δεν το εισάγουμε.
* ``is_superuser`` — βλέπει τα πάντα (``massmail/site/emailaccountadmin.py``).

Το ``do_import`` ΔΕΝ περιλαμβάνεται: αφορά μόνο τη ροή μαζικού import,
όχι την προβολή ενός ήδη καταγεγραμμένου μηνύματος.
"""
from django.db.models import Q
from django.http import Http404

from massmail.models import EmailAccount


def accessible_email_accounts(user):
    """QuerySet των EmailAccount στα οποία ο ``user`` έχει νόμιμη πρόσβαση."""
    qs = EmailAccount.objects.all()
    if not user or not user.is_authenticated:
        return qs.none()
    if user.is_superuser:
        return qs
    q = Q(owner=user) | Q(co_owner=user)
    department_id = getattr(user, 'department_id', None)
    if department_id:
        q &= Q(department_id=department_id)
    return qs.filter(q)


def get_accessible_email_account_or_404(user, **lookup):
    """
    Επιστρέφει EmailAccount προσβάσιμο από τον ``user`` ή ρίχνει Http404.

    Fail closed: ξένο, ανύπαρκτο ή μη έγκυρο identifier δίνουν ΤΗΝ ΙΔΙΑ
    απόκριση (404), ώστε να μην αποκαλύπτεται η ύπαρξη του account.
    Χρησιμοποιεί ``.first()`` (όχι ``.get()``) ώστε διπλότυπα
    email_host_user να μη γίνονται 500.
    """
    try:
        ea = accessible_email_accounts(user).filter(**lookup).first()
    except (ValueError, TypeError):
        ea = None
    if ea is None:
        raise Http404('EmailAccount not found')
    return ea
