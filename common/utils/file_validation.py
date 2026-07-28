"""
File Upload Security Validation
SECURITY FIX: Prevent malware uploads, verify file types
"""
import os
import mimetypes
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

# Allowed MIME types
ALLOWED_MIMES = {
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # xlsx
    'application/vnd.ms-excel',  # xls
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # docx
    'application/msword',  # doc
    'image/jpeg',
    'image/png',
    'image/gif',
    'application/zip',
    'text/plain',
    'text/csv',
}

# Maximum file size (10MB default)
MAX_FILE_SIZE = getattr(settings, 'MAX_UPLOAD_SIZE', 10 * 1024 * 1024)


def validate_file_upload(uploaded_file):
    """
    Validate uploaded file for security
    
    Checks:
    1. File extension
    2. File size
    3. MIME type (if python-magic available)
    
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
    
    # Check MIME type (best effort)
    try:
        import magic
        uploaded_file.seek(0)
        file_type = magic.from_buffer(uploaded_file.read(2048), mime=True)
        uploaded_file.seek(0)
        
        if file_type not in ALLOWED_MIMES:
            raise ValidationError(
                f'Invalid file type detected: {file_type}. '
                f'File may be corrupted or dangerous.'
            )
    except ImportError:
        # python-magic not installed, skip MIME check
        # Use mimetypes as fallback
        guessed_type, _ = mimetypes.guess_type(filename)
        if guessed_type and guessed_type not in ALLOWED_MIMES:
            raise ValidationError(f'File type {guessed_type} not allowed')
    
    return True


def sanitize_filename(filename):
    """
    Sanitize filename to prevent directory traversal attacks
    
    Removes:
    - Path separators (/, \)
    - Special characters that could cause issues
    - Leading dots
    """
    # Remove parent-directory references entirely, then neutralize
    # path separators and control characters
    filename = filename.replace('..', '')
    for char in ['/', '\\', '\x00', '\n', '\r']:
        filename = filename.replace(char, '_')

    # Remove leading dots (hidden files) and leftover separators
    filename = filename.lstrip('._')
    
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
