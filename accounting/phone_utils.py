# -*- coding: utf-8 -*-
"""
accounting/phone_utils.py
Author: ddiplas
Version: 1.0
Description: Phone number normalization and client matching utilities
"""
import re
import logging
from django.db.models import Q
from accounting.services.access import mask_pii_value

logger = logging.getLogger(__name__)


def normalize_phone(phone_number):
    """
    Normalize a phone number for comparison.

    Handles Greek phone formats:
    - 6947709311
    - +306947709311
    - 00306947709311
    - 0030 6947709311
    - 694 770 9311
    - 210-1234567

    Returns the last 10 digits (Greek mobile/landline format).
    For shorter numbers (internal extensions), returns as-is.

    Args:
        phone_number: Phone number string to normalize

    Returns:
        Normalized phone string (digits only, without country code)
    """
    if not phone_number:
        return ''

    # Remove all non-digit characters
    digits = re.sub(r'\D', '', str(phone_number))

    if not digits:
        return ''

    # Remove Greek country code (30) from the beginning
    # Handle: +30, 0030
    if digits.startswith('30') and len(digits) > 10:
        digits = digits[2:]
    elif digits.startswith('0030') and len(digits) > 12:
        digits = digits[4:]

    # Return last 10 digits for standard Greek numbers
    # Mobile: 69x xxx xxxx (10 digits)
    # Landline: 2xx xxx xxxx (10 digits)
    if len(digits) >= 10:
        return digits[-10:]

    # For shorter numbers (extensions, etc.), return as-is
    return digits


def phone_matches(phone1, phone2):
    """
    Check if two phone numbers match after normalization.

    Args:
        phone1: First phone number
        phone2: Second phone number

    Returns:
        True if phones match, False otherwise
    """
    norm1 = normalize_phone(phone1)
    norm2 = normalize_phone(phone2)

    if not norm1 or not norm2:
        return False

    return norm1 == norm2


def find_client_by_phone(phone_number, clients_qs=None):
    """
    Find a ClientProfile by phone number.

    Searches across all phone fields:
    - tilefono_oikias_1, tilefono_oikias_2 (home)
    - kinito_tilefono (mobile)
    - tilefono_epixeirisis_1, tilefono_epixeirisis_2 (business)

    Args:
        phone_number: Phone number to search for
        clients_qs: Optional queryset περιορισμού (π.χ. accessible_clients(user))
            — αν δεν δοθεί, ψάχνει σε όλους τους ενεργούς πελάτες

    Returns:
        ClientProfile instance if found, None otherwise
    """
    from .models import ClientProfile

    normalized = normalize_phone(phone_number)

    if not normalized or len(normalized) < 5:
        # Too short to be a valid phone number
        return None

    logger.debug(f"Searching for client with normalized phone: {mask_pii_value(normalized)}")

    base_qs = clients_qs if clients_qs is not None else ClientProfile.objects.all()
    clients = base_qs.filter(is_active=True)

    # Check each client's phone numbers
    for client in clients:
        phone_fields = [
            client.tilefono_oikias_1,
            client.tilefono_oikias_2,
            client.kinito_tilefono,
            client.tilefono_epixeirisis_1,
            client.tilefono_epixeirisis_2,
        ]

        for field_value in phone_fields:
            if field_value and phone_matches(field_value, phone_number):
                logger.info(f"Found client {client.id} for phone {mask_pii_value(phone_number)}")
                return client

    logger.debug(f"No client found for phone: {mask_pii_value(phone_number)}")
    return None


def find_clients_by_phone_query(phone_number):
    """
    Find ClientProfiles by phone number using database query.

    This is an optimized version that uses Q objects for database-level filtering.
    Note: This uses LIKE queries and may not be as accurate as find_client_by_phone
    for numbers stored in different formats.

    Args:
        phone_number: Phone number to search for

    Returns:
        QuerySet of matching ClientProfile instances
    """
    from .models import ClientProfile

    normalized = normalize_phone(phone_number)

    if not normalized or len(normalized) < 5:
        return ClientProfile.objects.none()

    # Search with the normalized number and partial matches
    # This catches cases where the database has numbers in various formats
    return ClientProfile.objects.filter(
        is_active=True
    ).filter(
        Q(tilefono_oikias_1__icontains=normalized[-7:]) |
        Q(tilefono_oikias_2__icontains=normalized[-7:]) |
        Q(kinito_tilefono__icontains=normalized[-7:]) |
        Q(tilefono_epixeirisis_1__icontains=normalized[-7:]) |
        Q(tilefono_epixeirisis_2__icontains=normalized[-7:])
    )


def auto_match_call(call, save=True, clients_qs=None):
    """
    Attempt to auto-match a VoIP call to a client by phone number.

    Args:
        call: VoIPCall instance
        save: If True, save the call after matching
        clients_qs: Optional queryset περιορισμού της αναζήτησης
            (π.χ. accessible_clients(user) για scoped χρήστες)

    Returns:
        ClientProfile if matched, None otherwise
    """
    if call.client is not None:
        # Already matched
        return call.client

    client = find_client_by_phone(call.phone_number, clients_qs=clients_qs)

    if client:
        # Κλήση με ticket ήδη αντιστοιχισμένο σε ΑΛΛΟΝ πελάτη: το
        # auto-match δεν την αγγίζει — μένει για χειροκίνητο triage
        from .models import Ticket
        linked_client_id = Ticket.objects.filter(call=call).values_list(
            'client_id', flat=True
        ).first()
        if linked_client_id and linked_client_id != client.pk:
            logger.warning(
                f"Auto-match skipped for call {call.id}: linked ticket "
                f"bound to different client"
            )
            return None
        if save:
            # Κεντρικό service: atomic + invariant κλήσης-ticket (το
            # auto-match ενημερώνει και τυχόν unassigned linked ticket)
            from accounting.services.call_assignment import change_call_client
            change_call_client(call, client, log_action='client_matched')
        else:
            call.client = client
            call.client_email = client.email or ''

        logger.info(f"Auto-matched call {call.id} to client {client.id}")
        return client

    return None


def batch_auto_match_calls(dry_run=False):
    """
    Auto-match all unmatched VoIP calls to clients.

    Args:
        dry_run: If True, don't save changes, just report what would be matched

    Returns:
        dict with statistics: {'matched': int, 'unmatched': int, 'details': list}
    """
    from .models import VoIPCall

    unmatched_calls = VoIPCall.objects.filter(client__isnull=True)

    stats = {
        'total': unmatched_calls.count(),
        'matched': 0,
        'unmatched': 0,
        'details': []
    }

    for call in unmatched_calls:
        client = find_client_by_phone(call.phone_number)

        if client:
            stats['matched'] += 1
            stats['details'].append({
                'call_id': call.id,
                'phone': call.phone_number,
                'matched_client': client.eponimia,
                'client_id': client.id
            })

            if not dry_run:
                auto_match_call(call, save=True)
        else:
            stats['unmatched'] += 1

    return stats
