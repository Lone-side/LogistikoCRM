from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from massmail.models import EmlMessage, Signature


def copy_message(request, object_id):
    msg = get_object_or_404(EmlMessage, id=object_id)
    try:
        signature = Signature.objects.get(
            owner=request.user,
            default=True
        )
        msg.signature = signature
    except Signature.DoesNotExist:
        msg.signature = None
    msg.id = None
    msg.owner = request.user
    msg.save()
    url = reverse(
        'site:massmail_emlmessage_change',
        args=(msg.id,)
    )
    return HttpResponseRedirect(url) 
