"""
File Upload Security Validation
SECURITY FIX: Prevent malware uploads, verify file types
"""
import os
from django.core.exceptions import ValidationError
from django.conf import settings


# Allowed file extensions for accounting office
ALLOWED_EXTENSIONS = {
    '.pdf',   # Documents
    '.xlsx', '.xls',  # Excel
    '.docx', '.doc',  # Word
    '.jpg', '.jpeg', '.png', '.gif',  # Images
    '.zip',  # Archives
    '.txt', '.csv',  # Text files
}

# Maximum file size (10MB default)
MAX_FILE_SIZE = getattr(settings, 'MAX_UPLOAD_SIZE', 10 * 1024 * 1024)


# Magic-byte υπογραφές ανά επέκταση — dependency-free content check.
#
# SECURITY/PORTABILITY: ΔΕΝ χρησιμοποιούμε python-magic/libmagic. Η native
# libmagic μπορεί να κάνει hard **segfault** τη διεργασία (exit 139), κάτι που
# ΔΕΝ πιάνεται από try/except — οπότε ένα απλό `import magic` ρίσκαρε να ρίξει
# τον worker σε κάθε upload. Αντ' αυτού ελέγχουμε τα leading bytes του αρχείου.
# Επεκτάσεις χωρίς αξιόπιστη υπογραφή (π.χ. .txt/.csv) δεν ελέγχονται εδώ.
FILE_SIGNATURES = {
    '.pdf': (b'%PDF',),
    '.png': (b'\x89PNG\r\n\x1a\n',),
    '.gif': (b'GIF87a', b'GIF89a'),
    '.jpg': (b'\xff\xd8\xff',),
    '.jpeg': (b'\xff\xd8\xff',),
    '.zip': (b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08'),  # zip (incl. empty/spanned)
    '.docx': (b'PK\x03\x04',),   # OOXML = zip container
    '.xlsx': (b'PK\x03\x04',),
    '.doc': (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1',),   # legacy OLE compound file
    '.xls': (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1',),
}


def content_matches_extension(uploaded_file, ext):
    """True αν τα leading bytes του αρχείου ταιριάζουν με την επέκταση `ext`.

    Επεκτάσεις χωρίς γνωστή υπογραφή επιστρέφουν True (το extension allowlist
    έχει ήδη τρέξει). Σε σφάλμα ανάγνωσης δίνουμε το benefit of the doubt
    (True) ώστε ο έλεγχος να μη σπάει legitimate uploads — η επέκταση + το
    μέγεθος έχουν ήδη ελεγχθεί από τον caller.
    """
    signatures = FILE_SIGNATURES.get(ext)
    if not signatures:
        return True
    try:
        uploaded_file.seek(0)
        header = uploaded_file.read(8)
        uploaded_file.seek(0)
    except Exception:
        return True
    return any(header.startswith(sig) for sig in signatures)


def validate_file_upload(uploaded_file):
    """
    Validate uploaded file for security
    
    Checks:
    1. File extension
    2. File size
    3. Content signature (magic bytes) matches the extension

    Raises ValidationError if file is invalid
    """
    # Check if file exists
    if not uploaded_file:
        raise ValidationError('No file provided')
    
    # Check extension
    filename = uploaded_file.name
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f'File type "{ext}" not allowed. '
            f'Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'
        )
    
    # Check file size
    if uploaded_file.size > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        raise ValidationError(
            f'File too large ({uploaded_file.size} bytes). '
            f'Maximum size: {max_mb:.1f}MB'
        )
    
    # SECURITY (defense-in-depth): magic-bytes έλεγχος περιεχομένου ώστε ένα
    # εκτελέσιμο μετονομασμένο σε .pdf (ή άλλη επιτρεπτή επέκταση) να μην περνά
    # μόνο με βάση το extension. Dependency-free — δεν χρησιμοποιεί
    # python-magic/libmagic (που μπορεί να κάνει segfault τη διεργασία).
    if not content_matches_extension(uploaded_file, ext):
        raise ValidationError(
            f'Το περιεχόμενο του αρχείου δεν ταιριάζει με τον τύπο του ({ext}). '
            f'Το αρχείο μπορεί να είναι κατεστραμμένο ή επικίνδυνο.'
        )

    return True


def sanitize_filename(filename):
    """
    Sanitize filename to prevent directory traversal attacks
    
    Removes:
    - Path separators (/, \)
    - Special characters that could cause issues
    - Leading dots
    """
    # Get just the filename, no path
    filename = os.path.basename(filename)
    
    # Remove dangerous characters
    dangerous_chars = ['/', '\\', '..', '\x00', '\n', '\r']
    for char in dangerous_chars:
        filename = filename.replace(char, '_')
    
    # Remove leading dots (hidden files)
    filename = filename.lstrip('.')
    
    # Ensure filename is not empty
    if not filename:
        filename = 'unnamed_file'
    
    return filename


def validate_image_file(uploaded_file):
    """
    Validate image files specifically
    Additional checks for image files
    """
    validate_file_upload(uploaded_file)
    
    # Check if it's actually an image
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in {'.jpg', '.jpeg', '.png', '.gif'}:
        raise ValidationError('File must be an image (jpg, png, gif)')
    
    # Check image dimensions if Pillow available
    try:
        from PIL import Image
        uploaded_file.seek(0)
        img = Image.open(uploaded_file)
        img.verify()
        uploaded_file.seek(0)
        
        # Max dimensions
        max_width = 4000
        max_height = 4000
        
        if img.width > max_width or img.height > max_height:
            raise ValidationError(
                f'Image too large ({img.width}x{img.height}). '
                f'Maximum: {max_width}x{max_height}'
            )
    except ImportError:
        pass  # Pillow not installed
    except Exception as e:
        raise ValidationError(f'Invalid image file: {str(e)}')
    
    return True
