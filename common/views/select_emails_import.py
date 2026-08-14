from time import sleep
from typing import Optional
from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.main import PAGE_VAR
from django.core.handlers.wsgi import WSGIRequest
from django.core.mail import mail_admins
from django.http.response import HttpResponse
from django.http.response import HttpResponseBadRequest
from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.db.models import Q
from django.db.models.query import QuerySet
from django.views.decorators.csrf import csrf_protect
from django.utils.translation import gettext as _
from django.urls import reverse

from crm.models import Deal
from crm.models import CrmEmail
from crm.models import Request
from crm.utils.helpers import get_crmimap
from crm.utils.import_emails import get_email_headers_page
from crm.utils.import_emails import parse_message_bytes
from crm.utils.restore_imap_emails import process_imported_email
from crm.site.crmadminsite import crm_site
from massmail.models import EmailAccount
from common.utils.email_account_access import get_accessible_email_account_or_404


@csrf_protect
def select_emails_import(request: WSGIRequest):
    if request.method == 'POST':
        data = request.POST.copy()
        try:
            ea_id = int(data.pop('ea_id')[0])
        except (KeyError, ValueError):
            return HttpResponseBadRequest('Invalid "ea_id" parameter.')
        # Ίδια ευπάθεια ιδιοκτησίας με τα original-email views: το ea_id
        # έρχεται από τον client και ακολουθούν IMAP delete/spam/seen.
        # Έλεγχος ΠΡΙΝ από κάθε IMAP πρόσβαση, fail closed (404).
        ea = get_accessible_email_account_or_404(request.user, id=ea_id)
        data.pop('csrfmiddlewaretoken', None)
        action_list = data.pop('action', None)
        if not action_list:
            return HttpResponseBadRequest('The "action" parameter is required.')
        action = action_list[0]
        if action == 'import':
            return emails_import(data, request, ea)

        uids = [
            key for key in data.keys()
            if data[key] == 'False'
        ]
        if uids:
            uids_str = ','.join(uids)
            crmimap = get_crmimap(ea, 'INBOX')
            if crmimap:
                if action == 'delete':
                    crmimap.delete_emails(uids_str)
                elif action == 'spam':
                    crmimap.move_emails_to_spam(uids_str)
                elif action == 'seen':
                    crmimap.mark_emails_as_read(uids_str)
                crmimap.release()
        url = request.get_full_path()
        return HttpResponseRedirect(url)

    else:  # request.method == 'GET'
        deal_name = deal_url = inquiry_name = inquiry_url = ''
        next_url = request.GET.get('next')
        deal_id = request.GET.get('deal_id')
        request_id = request.GET.get('request_id')
        ticket = request.GET.get('ticket')
        ea_id = request.GET.get('ea')
        if ea_id and not ea_id.isdigit():
            return HttpResponseBadRequest('Invalid "ea" parameter.')
        ea = get_accessible_email_account_or_404(
            request.user, id=ea_id) if ea_id else None
        if not ea:
            q_params = Q(owner=request.user) | Q(co_owner=request.user)
            q_params = q_params & Q(do_import=True)
            if request.user.department_id:  # NOQA
                q_params = q_params & Q(department_id=request.user.department_id)   # NOQA
            eas = EmailAccount.objects.filter(q_params)

            if len(eas) > 1:
                return select_ea_view(
                    eas, next_url, ticket, deal_id, request_id)

            elif len(eas) == 1:
                ea = eas.get()

        if ea:
            if deal_id:
                if not deal_id.isdigit():
                    return HttpResponseBadRequest('Invalid "deal_id" parameter.')
                deal = get_object_or_404(Deal, id=deal_id)
                deal_name = deal.name
                deal_url = deal.get_absolute_url()
                opts = Deal._meta  # NOQA

            elif request_id:
                if not request_id.isdigit():
                    return HttpResponseBadRequest('Invalid "request_id" parameter.')
                inquiry = get_object_or_404(Request, id=request_id)
                inquiry_name = inquiry.request_for
                inquiry_url = inquiry.get_absolute_url()
                opts = Request._meta  # NOQA
            else:
                opts = Request._meta  # NOQA
            post_name = CrmEmail._meta.verbose_name_plural  # NOQA
            context = dict(
                crm_site.each_context(request),
                opts=opts,
                msg='',
                object_name=deal_name or inquiry_name,
                object_url=deal_url or inquiry_url,
                post_name=post_name
            )
            try:
                page_num = int(request.GET.get(PAGE_VAR, 0))
            except ValueError:
                return HttpResponseBadRequest('Invalid page number.')
            page, err = get_email_headers_page(ea, page_num)
            # if page and not err:
            if not err:
                page.params = dict(request.GET.items())
                page.page_num = page_num
                context['page'] = page
                context['page_range'] = page.paginator.page_range
                context['email_host_user'] = ea.email_host_user
                context['ea_id'] = ea.id
                context['url'] = next_url
            else:
                return HttpResponse(err)
        else:
            messages.warning(
                request,
                _('You do not have mail accounts marked for importing emails.'
                  ' Please contact your administrator.')
            )
            return HttpResponseRedirect(next_url)
        return TemplateResponse(
            request,
            "common/select_emails.html",
            context
        )


def emails_import(data: dict, request: WSGIRequest,
                  ea: EmailAccount) -> HttpResponseRedirect:
    uids = [str.encode(key) for key in data.keys()
            if data[key] == 'False']
    url = data.pop('url')[0]
    if uids:
        t = 'inquiry'
        ticket = request.GET.get('ticket')
        if ticket:
            t = 'incoming'
        if not settings.TESTING:
            _get_emails_by_uid(request, ea, t, uids, ticket)
            sleep(0.7)

    return HttpResponseRedirect(url)


def select_ea_view(eas: QuerySet, next_url: str, ticket: str,
                   deal_id, request_id) -> HttpResponseRedirect:
    ids = eas.values_list('id', flat=True)
    url = reverse(
        'select_email_account'
    ) + '?eas=%s' % ",".join(map(str, ids))
    if next_url:
        url += f"&next={next_url}"
    if deal_id:
        url += f"&deal_id={deal_id}"
        url += f"&ticket={ticket}"
    elif request_id:
        url += f"&request_id={request_id}"
        url += f"&ticket={ticket}"

    return HttpResponseRedirect(url)


def _get_emails_by_uid(request: WSGIRequest, ea: EmailAccount, t: str, uids: list,
                       ticket: Optional[str] = None) -> None:
    crmimap = get_crmimap(ea, 'INBOX')
    if crmimap:
        if not crmimap.error:
            for uid in uids:
                result, data, err = crmimap.uid_fetch(uid)
                if result == 'OK' and data[0] and not err:
                    b_msg = parse_message_bytes(uid, data)
                    if not b_msg:
                        result, data, err = crmimap.uid_fetch(uid)
                        b_msg = parse_message_bytes(uid, data)
                    if b_msg:
                        crm_conf = apps.get_app_config('crm')
                        if getattr(crm_conf, 'eml_queue', None) is not None:
                            # Legacy consumer thread path (legacy threads on).
                            crm_conf.eml_queue.put(
                                (b_msg, ea, t, uid, ticket, request))
                        else:
                            # Production fail-safe: process synchronously so a
                            # manual import never crashes on a missing queue.
                            process_imported_email(
                                (b_msg, ea, t, uid, ticket, request))
                if result != 'OK' or not data[0] or err:
                    mail_admins(
                        f"The result is {result} at get_emails_by_uid",
                        f'''
                        \nResult: {result}
                        \nData: {data}
                        \nEmail account: {ea}
                        \nError:         {err}
                        ''',
                        fail_silently=True,
                    )
        crmimap.release()
