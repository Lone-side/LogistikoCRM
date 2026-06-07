from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import path

from common.views.copy_department import copy_department
from common.views.debugs import debug
from common.views.reload_field import reload_field
from common.views.select_email_account import select_email_account
from common.views.select_emails_import import select_emails_import
from common.views.toggle_default_sorting import toggle_default_sorting
from common.views.user_transfer import user_transfer

urlpatterns = [
    path(
        'select-emails-import/request/',
        staff_member_required(select_emails_import),
        name='select_emails_import_request'
    ),
    path(
        'select-email-account/',
        staff_member_required(select_email_account),
        name='select_email_account'
    ),
    path(
        'user-transfer/',
        staff_member_required(user_transfer),  # destructive bulk re-assignment → staff only
        name='user_transfer'
    ),
    path(
        'copy-department/',
        staff_member_required(copy_department),  # creates departments/config → staff only
        name='copy_department'
    ),
    path(
        'debug/',
        staff_member_required(debug),  # debug endpoint must not be client-reachable
        name='debug'
    ),
    path(
        "toggle-default-sorting",
        staff_member_required(toggle_default_sorting),  # CRM-only helper (was unauthenticated)
        name="toggle_default_sorting"
    ),
    path(
        'reload-field/',
        login_required(reload_field),
        name='reload_field'
    ),
]
