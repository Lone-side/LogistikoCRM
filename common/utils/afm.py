# -*- coding: utf-8 -*-
"""
Βοηθητικά για ελληνικό ΑΦΜ.
"""
import re

AFM_CANDIDATE_RE = re.compile(r'(?<!\d)\d{9}(?!\d)')


def validate_afm(afm):
    """
    Επικυρώνει ελληνικό ΑΦΜ (9 ψηφία + checksum).
    Returns: bool
    """
    if not afm or len(afm) != 9 or not afm.isdigit():
        return False
    total = sum(int(afm[i]) * (2 ** (8 - i)) for i in range(8))
    check_digit = (total % 11) % 10
    return check_digit == int(afm[8])


def find_afm_candidates(text):
    """
    Βρίσκει όλα τα έγκυρα (checksum) ΑΦΜ μέσα σε κείμενο.
    Returns: λίστα μοναδικών ΑΦΜ με τη σειρά εμφάνισης.
    """
    seen = []
    for match in AFM_CANDIDATE_RE.findall(text or ''):
        if match not in seen and validate_afm(match):
            seen.append(match)
    return seen
