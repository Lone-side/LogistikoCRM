#!/usr/bin/env python
"""
Παραγωγή Fernet key για το DATA_ENCRYPTION_KEY_CURRENT.

Standalone — ΔΕΝ φορτώνει Django settings, οπότε δουλεύει και σε καθαρό
production bootstrap όπου τα settings κάνουν hard-fail επειδή το
DATA_ENCRYPTION_KEY_CURRENT λείπει ακόμη.

Χρήση:
    python scripts/generate_fernet_key.py

Ισοδύναμο one-liner:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""


def generate_key() -> str:
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode("utf-8")


if __name__ == "__main__":
    print(generate_key())
