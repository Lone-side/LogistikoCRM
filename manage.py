#!/usr/bin/env python
import os
import sys


def _force_utf8_console():
    """Γράψε πάντα UTF-8 στο stdout/stderr.

    Οι εντολές του project τυπώνουν ελληνικά (ρόλοι, υποχρεώσεις, πελάτες).
    Η ελληνική κονσόλα των Windows είναι cp1253 και ΔΕΝ τα κωδικοποιεί, οπότε
    ένα απλό `self.stdout.write('Δημιουργήθηκε ρόλος…')` έριχνε ολόκληρη την
    εντολή με UnicodeEncodeError — αρκετό ώστε το τοπικό backend suite να
    βγάζει 127 errors που δεν υπήρχαν στο CI (Linux/UTF-8).

    Το errors='replace' εγγυάται ότι καμία εντολή δεν θα πέσει ποτέ επειδή
    ένας χαρακτήρας δεν χωρά στην κονσόλα.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, 'reconfigure', None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding='utf-8', errors='replace')
        except (OSError, ValueError):
            # Ανακατευθυνόμενο ή κλειστό stream — δεν είναι λόγος αποτυχίας.
            pass


if __name__ == '__main__':
    _force_utf8_console()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webcrm.settings_local')
    os.environ.setdefault('DJANGO_RUNSERVER_HIDE_WARNING', 'true')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

