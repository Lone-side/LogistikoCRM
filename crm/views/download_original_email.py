import email
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.utils.encoding import escape_uri_path
from django.utils.translation import gettext

from django.shortcuts import get_object_or_404

from crm.models import CrmEmail
from crm.utils.helpers import ensure_decoding
from crm.utils.helpers import get_crmimap
from common.utils.email_account_access import get_accessible_email_account_or_404

err_msg = gettext('Not enough data to identify the email or email has been deleted')


def download_original_email(request: WSGIRequest, object_id: int) -> HttpResponse:
    """Downloads original email from IMAP server by uid or message_id."""

    crm_email = get_object_or_404(CrmEmail, id=object_id)
    # Έλεγχος ιδιοκτησίας mailbox ΠΡΙΝ από κάθε IMAP σύνδεση/ανάκτηση.
    # Ξένο ή ανύπαρκτο account -> Http404 (fail closed, χωρίς αποκάλυψη).
    ea = get_accessible_email_account_or_404(
        request.user,
        imap_host=crm_email.imap_host,
        email_host_user=crm_email.email_host_user,
    )
    crmimap = get_crmimap(ea, 'INBOX')
    if crmimap is None:
        return HttpResponse(err_msg)
    if crmimap.error:
        crmimap.release()
        return HttpResponse(f"Error: {crmimap.error}")

    result, data, _ = crmimap.uid_fetch(str(crm_email.uid).encode('utf8'))
    if result != 'OK' or not data[0]:
        if not crm_email.message_id:
            crmimap.release()
            return HttpResponse(err_msg)
        result, data = crmimap.get_emails_by_message_id(crm_email.message_id)
        if result != 'OK' or not data[0]:
            crmimap.release()
            return HttpResponse(err_msg)

    crmimap.release()
    msg = email.message_from_bytes(
        data[0][1], policy=email.policy.default)
    filename = f"{ensure_decoding(msg['Subject'])}.eml"

    response = HttpResponse(data[0][1], content_type="message/rfc822")
    response['Content-Disposition'] = 'attachment; filename=%s' % escape_uri_path(filename)
    return response
