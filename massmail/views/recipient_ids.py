from django.urls import reverse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.contrib.contenttypes.models import ContentType

from massmail.models import MailingOut


def view_recipient_ids(_, object_id, method):
    data = {
        ContentType.objects.get(app_label="crm", model="contact").id: 'site:crm_contact_changelist',
        ContentType.objects.get(app_label="crm", model="company").id: 'site:crm_company_changelist',
        ContentType.objects.get(app_label="crm", model="lead").id: 'site:crm_lead_changelist',
    }
    mo = get_object_or_404(MailingOut, id=object_id)
    url_name = data.get(mo.content_type_id)
    if url_name is None:
        return HttpResponseBadRequest('Unsupported content type.')
    get_particular_ids = getattr(mo, method)
    l_ids = get_particular_ids()
    url = reverse(url_name) + '?id__in=' + '%s' % ",".join(map(str, l_ids))
    return HttpResponseRedirect(url)
