from django.conf import settings
from django.apps import apps as django_apps
from django.contrib.admin.models import LogEntry

PREFIX = settings.SECRET_CRM_PREFIX
ADMIN_PREFIX = settings.SECRET_ADMIN_PREFIX

reminder_iconed_name = 'Reminders <i class="material-icons" ' \
                       'style="font-size: 17px;vertical-align: middle;">alarm</i>'
userprofile_iconed_name = 'User profiles <i class="material-icons" ' \
                           'style="font-size: 17px;vertical-align: middle;">people</i>'


def get_perms(add: bool = True,
              change: bool = True,
              delete: bool = True,
              view: bool = True):
    return {'add': add, 'change': change, 'delete': delete, 'view': view}


# -- Data for Analytics Application Models -- #

def get_incomestat_model_data(prefix: str = '') -> dict:
    prefix = prefix or PREFIX
    return {
        'name': 'Income Summary',
        'object_name': 'IncomeStat',
        'perms': get_perms(add=False, change=False, delete=False),
        'admin_url': f'/en/{prefix}analytics/incomestat/',
        'add_url': None,
        'view_only': True
    }


# -- Data for CRM Application Models --

def get_company_model_data(prefix: str = '',
                            perms: dict = {},   # NOQA
                            view_only: bool = True,
                            is_add_url: bool = False,
                            ) -> dict:
    perms = get_perms(**perms)
    prefix = prefix or PREFIX
    add_url = f'/en/{prefix}crm/company/add/' if is_add_url else None
    return {
        'name': 'Companies',
        'object_name': 'Company',
        'perms': perms,
        'admin_url': f'/en/{prefix}crm/company/',
        'add_url': add_url,
        'view_only': view_only
    }


def get_contact_model_data(prefix: str = '',
                            perms: dict = {},   # NOQA
                            view_only: bool = True,
                            is_add_url: bool = False,
                            ) -> dict:
    perms = get_perms(**perms)
    prefix = prefix or PREFIX
    add_url = f'/en/{prefix}crm/contact/add/' if is_add_url else None
    return {
        'name': 'Contact persons',
        'object_name': 'Contact',
        'perms': perms,
        'admin_url': f'/en/{prefix}crm/contact/',
        'add_url': add_url,
        'view_only': view_only
    }


def get_deal_model_data(prefix: str = '',
                            perms: dict = {},   # NOQA
                            view_only: bool = True,
                            is_add_url: bool = False,
                            ) -> dict:
    perms = get_perms(**perms)
    prefix = prefix or PREFIX
    add_url = f'/en/{prefix}crm/deal/add/' if is_add_url else None
    return {
        'object_name': 'Deal',
        'perms': perms,
        'admin_url': f'/en/{prefix}crm/deal/',
        'add_url': add_url,
        'view_only': view_only
    }


def get_shipment_model_data(prefix: str = '',
                            perms: dict = {},   # NOQA
                            view_only: bool = True,
                            is_add_url: bool = False,
                            ) -> dict:
    perms = get_perms(**perms)
    prefix = prefix or PREFIX
    add_url = f'/en/{prefix}crm/shipment/add/' if is_add_url else None
    return {
        'object_name': 'Shipment',
        'perms': perms,
        'admin_url': f'/en/{prefix}crm/shipment/',
        'add_url': add_url,
        'view_only': view_only
    }


# -- Data for Common Application Models -- #

def get_department_model_data(prefix: str = '') -> dict:
    prefix = prefix or PREFIX
    return {
        'name': 'Departments',
        'object_name': 'Department',
        'perms': get_perms(),
        'admin_url': f'/en/{prefix}common/department/',
        'add_url': f'/en/{prefix}common/department/add/',
        'view_only': False
    }


def get_thefile_model_data(prefix: str = '') -> dict:
    prefix = prefix or PREFIX
    return {
        'name': 'Files',
        'object_name': 'TheFile',
        'perms': get_perms(),
        'admin_url': f'/en/{prefix}common/thefile/',
        'add_url': f'/en/{prefix}common/thefile/add/',
        'view_only': False
    }


def get_publicemaildomain_model_data(name: str = '', prefix: str = '') -> dict:
    prefix = prefix or PREFIX
    name = name or "Public email domains"
    return {
        'name': name,
        'object_name': 'PublicEmailDomain',
        'perms': get_perms(),
        'admin_url': f'/en/{prefix}settings/publicemaildomain/',
        'add_url': f'/en/{prefix}settings/publicemaildomain/add/',
        'view_only': False
    }


def get_reminder_model_data(name: str = '', prefix: str = '') -> dict:
    prefix = prefix or PREFIX
    name = name or "Reminders"
    return {
        'name': name,
        'object_name': 'Reminder',
        'perms': get_perms(),
        'admin_url': f'/en/{prefix}common/reminder/',
        'add_url': f'/en/{prefix}common/reminder/add/',
        'view_only': False
    }


def get_stopphrase_model_data(name: str = '', prefix: str = '') -> dict:
    prefix = prefix or PREFIX
    name = name or "Stop Phrases"
    return {
        'name': name,
        'object_name': 'StopPhrase',
        'perms': get_perms(),
        'admin_url': f'/en/{prefix}settings/stopphrase/',
        'add_url': f'/en/{prefix}settings/stopphrase/add/',
        'view_only': False
    }


def get_userprofile_model_data(name: str = '',
                               prefix: str = '',
                               perms: dict = {},
                               is_add_url: bool = False,
                               view_only: bool = True,) -> dict:
    perms = get_perms(**perms) if perms else get_perms(add=False, change=False, delete=False)
    prefix = prefix or PREFIX
    name = name or "User profiles"
    add_url = f'/en/{prefix}common/userprofile/add/' if is_add_url else None
    return {
        'name': name,
        'object_name': 'UserProfile',
        'perms': perms,
        'admin_url': f'/en/{prefix}common/userprofile/',
        'add_url': add_url,
        'view_only': view_only
    }


# -- Data for Tasks Application Models -- #

def get_memo_model_data(prefix: str = '',
                        perms: dict = {},   # NOQA
                        is_add_url: bool = False) -> dict:
    perms = get_perms(**perms)
    prefix = prefix or PREFIX
    add_url = f'/en/{prefix}tasks/memo/add/' if is_add_url else None
    return {
        'name': 'Memos',
        'object_name': 'Memo',
        'perms': perms,
        'admin_url': f'/en/{prefix}tasks/memo/',
        'add_url': add_url,
        'view_only': False
    }


def get_projectstage_model_data(prefix: str = '') -> dict:
    prefix = prefix or PREFIX
    return {
        'name': 'Project stages',
        'object_name': 'ProjectStage',
        'perms': get_perms(),
        'admin_url': f'/en/{prefix}tasks/projectstage/',
        'add_url': f'/en/{prefix}tasks/projectstage/add/',
        'view_only': False
    }


def get_tag_model_data(prefix: str = '') -> dict:
    prefix = prefix or PREFIX
    return {
        'name': 'Tags',
        'object_name': 'Tag',
        'perms': get_perms(),
        'admin_url': f'/en/{prefix}tasks/tag/',
        'add_url': f'/en/{prefix}tasks/tag/add/',
        'view_only': False
    }


def get_taskstage_model_data(prefix: str = '') -> dict:
    prefix = prefix or PREFIX
    return {
        'name': 'Task stages',
        'object_name': 'TaskStage',
        'perms': get_perms(),
        'admin_url': f'/en/{prefix}tasks/taskstage/',
        'add_url': f'/en/{prefix}tasks/taskstage/add/',
        'view_only': False
    }


def get_resolution_model_data(prefix: str = '') -> dict:
    prefix = prefix or PREFIX
    return {
        'name': 'Resolutions',
        'object_name': 'Resolution',
        'perms': get_perms(),
        'admin_url': f'/en/{prefix}tasks/resolution/',
        'add_url': f'/en/{prefix}tasks/resolution/add/',
        'view_only': False
    }


# -- APP Data -- #

def get_analytics_app_data(prefix: str = '') -> dict:
    prefix = prefix or PREFIX
    return {
        'name': 'Analytics',
        'app_label': 'analytics',
        'app_url': f'/en/{prefix}analytics/',
        'has_module_perms': True,
        'models': [
            {
                'name': 'Closing reason Summary',
                'object_name': 'ClosingReasonStat',
                'perms': get_perms(add=False, change=False, delete=False),
                'admin_url': f'/en/{prefix}analytics/closingreasonstat/',
                'add_url': None,
                'view_only': True
            },
            {
                'name': 'Conversion Summary',
                'object_name': 'ConversionStat',
                'perms': get_perms(add=False, change=False, delete=False),
                'admin_url': f'/en/{prefix}analytics/conversionstat/',
                'add_url': None,
                'view_only': True
            },
            {
                'name': 'Deal Summary',
                'object_name': 'DealStat',
                'perms': get_perms(add=False, change=False, delete=False),
                'admin_url': f'/en/{prefix}analytics/dealstat/',
                'add_url': None,
                'view_only': True
            },
            get_incomestat_model_data(prefix),
            {
                'name': 'Lead source Summary',
                'object_name': 'LeadSourceStat',
                'perms': get_perms(add=False, change=False, delete=False),
                'admin_url': f'/en/{prefix}analytics/leadsourcestat/',
                'add_url': None,
                'view_only': True
            },
            {
                'name': 'Requests Summary',
                'object_name': 'RequestStat',
                'perms': get_perms(add=False, change=False, delete=False),
                'admin_url': f'/en/{prefix}analytics/requeststat/',
                'add_url': None,
                'view_only': True
            },
            {
                'name': 'Sales Report',
                'object_name': 'OutputStat',
                'perms': get_perms(add=False, change=False, delete=False),
                'admin_url': f'/en/{prefix}analytics/outputstat/',
                'add_url': None,
                'view_only': True
            },
            {
                'name': 'Sales funnel',
                'object_name': 'SalesFunnel',
                'perms': get_perms(add=False, change=False, delete=False),
                'admin_url': f'/en/{prefix}analytics/salesfunnel/',
                'add_url': None,
                'view_only': True
            }
        ]
    }


def get_common_app_data(add_models: tuple = tuple(), prefix: str = '') -> dict:
    prefix = prefix or PREFIX
    if add_models:
        models = [*add_models]
    else:
        models = [
            get_reminder_model_data(name=reminder_iconed_name),
            get_userprofile_model_data(name=userprofile_iconed_name),
        ]
    return {
        'name': 'Common',
        'app_label': 'common',
        'app_url': f'/en/{prefix}common/',
        'has_module_perms': True,
        'models': models
    }


def get_task_app_data(add_models: tuple = tuple(), prefix: str = '') -> dict:
    prefix = prefix or PREFIX
    models = [
        {
            'name': 'Projects',
            'object_name': 'Project',
            'perms': get_perms(),
            'admin_url': f'/en/{prefix}tasks/project/',
            'add_url': f'/en/{prefix}tasks/project/add/',
            'view_only': False
        },
        {
            'name': 'Tasks',
            'object_name': 'Task',
            'perms': get_perms(),
            'admin_url': f'/en/{prefix}tasks/task/',
            'add_url': f'/en/{prefix}tasks/task/add/',
            'view_only': False
        }
    ]
    if add_models:
        models.extend([*add_models])
    return {
        'name': 'Tasks',
        'app_label': 'tasks',
        'app_url': f'/en/{prefix}tasks/',
        'has_module_perms': True,
        'models': models
    }


# -- Output Data -- #

DATA = [
    (
        'Olga.Co-worker.Global',  # 'username'
        [
            get_task_app_data(add_models=(get_memo_model_data(is_add_url=True),)),
            get_common_app_data()
        ]  # 'correct_app_list'
    ),
    (
        'Ekaterina.Task_operator',
        [
            get_task_app_data(add_models=(
                get_memo_model_data(is_add_url=True),
                get_resolution_model_data(),
                get_tag_model_data()
            )),
            {
                'name': 'Crm',
                'app_label': 'crm',
                'app_url': f'/en/{PREFIX}crm/',
                'has_module_perms': True,
                'models': [
                    get_shipment_model_data(perms={'add': False, 'change': False, 'delete': False}),
                ]
            },
            get_common_app_data()
        ]
    ),
    (
        'Garry.Chief',
        [
            get_task_app_data(add_models=(get_memo_model_data(is_add_url=True),)),
            {
                'name': 'Crm',
                'app_label': 'crm',
                'app_url': f'/en/{PREFIX}crm/',
                'has_module_perms': True,
                'models': [
                    get_company_model_data(perms={'add': False, 'change': False, 'delete': False}),
                    get_contact_model_data(perms={'add': False, 'change': False, 'delete': False}),
                    get_deal_model_data(perms={'add': False, 'delete': False}, view_only=False),
                    {
                        'name': 'Emails in CRM',
                        'object_name': 'CrmEmail',
                        'perms': get_perms(add=False, change=False, delete=False),
                        'admin_url': f'/en/{PREFIX}crm/crmemail/',
                        'add_url': None,
                        'view_only': True
                    },
                    {
                        'name': 'Leads',
                        'object_name': 'Lead',
                        'perms': get_perms(add=False, change=False, delete=False),
                        'admin_url': f'/en/{PREFIX}crm/lead/',
                        'add_url': None,
                        'view_only': True
                    },
                    {
                        'name': 'Payments',
                        'object_name': 'Payment',
                        'perms': get_perms(add=False, change=False, delete=False),
                        'admin_url': f'/en/{PREFIX}crm/payment/', 'add_url': None,
                        'view_only': True
                    },
                    {
                        'name': 'Products',
                        'object_name': 'Product',
                        'perms': get_perms(add=False, change=False, delete=False),
                        'admin_url': f'/en/{PREFIX}crm/product/',
                        'add_url': None,
                        'view_only': True
                    },
                    {
                        'name': 'Requests',
                        'object_name': 'Request',
                        'perms': get_perms(add=False, change=False, delete=False),
                        'admin_url': f'/en/{PREFIX}crm/request/',
                        'add_url': None,
                        'view_only': True
                    },
                    get_shipment_model_data(
                        perms={'add': False, 'change': False, 'delete': False}
                    ),
                ]
            },
            get_analytics_app_data(),
            {
                'name': 'Mass mail',
                'app_label': 'massmail',
                'app_url': f'/en/{PREFIX}massmail/',
                'has_module_perms': True,
                'models': [
                    {
                        'name': 'Email Messages',
                        'object_name': 'EmlMessage',
                        'perms': get_perms(add=False, change=False, delete=False),
                        'admin_url': f'/en/{PREFIX}massmail/emlmessage/',
                        'add_url': None,
                        'view_only': True
                    },
                    {
                        'name': 'Mailing Outs',
                        'object_name': 'MailingOut',
                        'perms': get_perms(add=False, change=False, delete=False),
                        'admin_url': f'/en/{PREFIX}massmail/mailingout/',
                        'add_url': None,
                        'view_only': True
                    }
                ]
            },
            get_common_app_data()
        ]
    ),
    (
        'Valeria.Operator.Global',
        [
            get_task_app_data(add_models=(get_memo_model_data(is_add_url=True),)),
            {
                'name': 'Crm',
                'app_label': 'crm',
                'app_url': f'/en/{PREFIX}crm/',
                'has_module_perms': True,
                'models': [
                    get_company_model_data(is_add_url=True, view_only=False),
                    get_contact_model_data(),
                    get_deal_model_data(perms={'add': False}, view_only=False),
                    {
                        'name': 'Emails in CRM',
                        'object_name': 'CrmEmail',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}crm/crmemail/',
                        'add_url': f'/en/{PREFIX}crm/crmemail/add/',
                        'view_only': False
                    },
                    {
                        'name': 'Leads',
                        'object_name': 'Lead',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}crm/lead/',
                        'add_url': f'/en/{PREFIX}crm/lead/add/',
                        'view_only': False
                    },
                    {
                        'name': 'Products',
                        'object_name': 'Product',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}crm/product/',
                        'add_url': f'/en/{PREFIX}crm/product/add/',
                        'view_only': False
                    },
                    {
                        'name': 'Requests',
                        'object_name': 'Request',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}crm/request/',
                        'add_url': f'/en/{PREFIX}crm/request/add/',
                        'view_only': False
                    }
                ]
            },
            get_common_app_data(),
            {
                'name': 'Settings',
                'app_label': 'settings',
                'app_url': f'/en/{PREFIX}settings/',
                'has_module_perms': True,
                'models': [
                    {
                        'name': 'Public email domains',
                        'object_name': 'PublicEmailDomain',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}settings/publicemaildomain/',
                        'add_url': f'/en/{PREFIX}settings/publicemaildomain/add/',
                        'view_only': False
                    },
                    {
                        'name': 'Stop Phrases', 'object_name': 'StopPhrase',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}settings/stopphrase/',
                        'add_url': f'/en/{PREFIX}settings/stopphrase/add/',
                        'view_only': False
                    }
                ]
            }
        ]
    ),
    (
        'Andrew.Manager.Global',
        [
            get_task_app_data(add_models=(
                get_memo_model_data(is_add_url=True),
                get_tag_model_data(),
            )),
            {
                'name': 'Crm',
                'app_label': 'crm',
                'app_url': f'/en/{PREFIX}crm/',
                'has_module_perms': True,
                'models': [
                    get_company_model_data(is_add_url=True, view_only=False),
                    get_contact_model_data(),
                    {
                        'name': 'Currencies',
                        'object_name': 'Currency',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}crm/currency/',
                        'add_url': f'/en/{PREFIX}crm/currency/add/',
                        'view_only': False
                    },
                    get_deal_model_data(perms={'add': False}, view_only=False),
                    {
                        'name': 'Emails in CRM',
                        'object_name': 'CrmEmail',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}crm/crmemail/',
                        'add_url': f'/en/{PREFIX}crm/crmemail/add/',
                        'view_only': False
                    },
                    {
                        'name': 'Leads',
                        'object_name': 'Lead',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}crm/lead/',
                        'add_url': f'/en/{PREFIX}crm/lead/add/',
                        'view_only': False
                    },
                    {
                        'name': 'Payments',
                        'object_name': 'Payment',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}crm/payment/',
                        'add_url': f'/en/{PREFIX}crm/payment/add/',
                        'view_only': False
                    },
                    {
                        'name': 'Products',
                        'object_name': 'Product',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}crm/product/',
                        'add_url': f'/en/{PREFIX}crm/product/add/',
                        'view_only': False
                    },
                    {
                        'name': 'Requests',
                        'object_name': 'Request',
                        'perms': get_perms(delete=False),
                        'admin_url': f'/en/{PREFIX}crm/request/',
                        'add_url': f'/en/{PREFIX}crm/request/add/',
                        'view_only': False
                    },
                    get_shipment_model_data(
                        perms={'add': False, 'delete': False}, view_only=False
                    ),
                    {
                        'name': 'Tags',
                        'object_name': 'Tag',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}crm/tag/',
                        'add_url': f'/en/{PREFIX}crm/tag/add/',
                        'view_only': False
                    }
                ]
            },
            get_analytics_app_data(),
            {
                'name': 'Mass mail',
                'app_label': 'massmail',
                'app_url': f'/en/{PREFIX}massmail/',
                'has_module_perms': True,
                'models': [
                    {
                        'name': 'Email Accounts',
                        'object_name': 'EmailAccount',
                        'perms': get_perms(add=False, change=False, delete=False),
                        'admin_url': f'/en/{PREFIX}massmail/emailaccount/',
                        'add_url': None,
                        'view_only': True
                    },
                    {
                        'name': 'Email Messages',
                        'object_name': 'EmlMessage',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}massmail/emlmessage/',
                        'add_url': f'/en/{PREFIX}massmail/emlmessage/add/',
                        'view_only': False
                    },
                    {
                        'name': 'Mailing Outs',
                        'object_name': 'MailingOut',
                        'perms': get_perms(add=False,),
                        'admin_url': f'/en/{PREFIX}massmail/mailingout/',
                        'add_url': None,
                        'view_only': False
                    },
                    {
                        'name': 'Signatures',
                        'object_name': 'Signature',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}massmail/signature/',
                        'add_url': f'/en/{PREFIX}massmail/signature/add/',
                        'view_only': False
                    }
                ]
            },
            get_common_app_data()
        ]
    ),
    (
        'Adam.Admin',
        [
            get_task_app_data(
                add_models=(
                    get_memo_model_data(is_add_url=True),
                    get_resolution_model_data(),
                    get_tag_model_data()
                )
            ),
            {
                'name': 'Crm',
                'app_label': 'crm',
                'app_url': f'/en/{PREFIX}crm/',
                'has_module_perms': True,
                'models': [
                    get_company_model_data(is_add_url=True, view_only=False),
                    get_contact_model_data(),
                    {
                        'name': 'Currencies',
                        'object_name': 'Currency',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}crm/currency/',
                        'add_url': f'/en/{PREFIX}crm/currency/add/',
                        'view_only': False
                    },
                    get_deal_model_data(is_add_url=True, view_only=False),
                    {
                        'name': 'Emails in CRM',
                        'object_name': 'CrmEmail',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}crm/crmemail/',
                        'add_url': f'/en/{PREFIX}crm/crmemail/add/',
                        'view_only': False
                    },
                    {
                        'name': 'Leads',
                        'object_name': 'Lead',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}crm/lead/',
                        'add_url': f'/en/{PREFIX}crm/lead/add/',
                        'view_only': False
                    },
                    {
                        'name': 'Payments',
                        'object_name': 'Payment',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}crm/payment/',
                        'add_url': f'/en/{PREFIX}crm/payment/add/',
                        'view_only': False
                    },
                    {
                        'name': 'Products',
                        'object_name': 'Product',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}crm/product/',
                        'add_url': f'/en/{PREFIX}crm/product/add/',
                        'view_only': False
                    },
                    {
                        'name': 'Requests',
                        'object_name': 'Request',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}crm/request/',
                        'add_url': f'/en/{PREFIX}crm/request/add/',
                        'view_only': False
                    },
                    get_shipment_model_data(
                        view_only=False, is_add_url=False,
                        perms={
                            'add': False, 'change': True,
                            'delete': True, 'view': True
                        }
                    ),
                    {
                        'name': 'Tags',
                        'object_name': 'Tag',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}crm/tag/',
                        'add_url': f'/en/{PREFIX}crm/tag/add/',
                        'view_only': False
                    }
                ]
            },
            get_analytics_app_data(),
            {
                'name': 'Mass mail',
                'app_label': 'massmail',
                'app_url': f'/en/{PREFIX}massmail/',
                'has_module_perms': True,
                'models': [
                    {
                        'name': 'Email Accounts',
                        'object_name': 'EmailAccount',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}massmail/emailaccount/',
                        'add_url': f'/en/{PREFIX}massmail/emailaccount/add/',
                        'view_only': False
                    },
                    {
                        'name': 'Email Messages',
                        'object_name': 'EmlMessage',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}massmail/emlmessage/',
                        'add_url': f'/en/{PREFIX}massmail/emlmessage/add/',
                        'view_only': False
                    },
                    {
                        'name': 'Mailing Outs',
                        'object_name': 'MailingOut',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}massmail/mailingout/',
                        'add_url': f'/en/{PREFIX}massmail/mailingout/add/',
                        'view_only': False
                    },
                    {
                        'name': 'Signatures',
                        'object_name': 'Signature',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}massmail/signature/',
                        'add_url': f'/en/{PREFIX}massmail/signature/add/',
                        'view_only': False
                    }
                ]
            },
            get_common_app_data(add_models=(
                get_reminder_model_data(name=reminder_iconed_name),
                get_userprofile_model_data(
                    name=userprofile_iconed_name,
                    perms={'add': True, 'change': True, 'delete': True, 'view': True},
                    view_only=False,
                    is_add_url=True
                ),                
            )),
            {
                'name': 'Settings',
                'app_label': 'settings',
                'app_url': f'/en/{PREFIX}settings/',
                'has_module_perms': True,
                'models': [
                    {
                        'name': 'Public email domains',
                        'object_name': 'PublicEmailDomain',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}settings/publicemaildomain/',
                        'add_url': f'/en/{PREFIX}settings/publicemaildomain/add/',
                        'view_only': False
                    },
                    {
                        'name': 'Stop Phrases', 'object_name': 'StopPhrase',
                        'perms': get_perms(),
                        'admin_url': f'/en/{PREFIX}settings/stopphrase/',
                        'add_url': f'/en/{PREFIX}settings/stopphrase/add/',
                        'view_only': False
                    }
                ]
            }
        ]
    ),
    (
        "Sergey.Co-worker.Head.Bookkeeping",
        [
            get_task_app_data(add_models=(get_memo_model_data(is_add_url=True),),),
            get_common_app_data()
        ]
    )
]

# data for admin site
# ΑΝΑΓΕΝΝΗΜΕΝΟ snapshot: πραγματικό app_list του default admin (superuser)
# Περιλαμβάνει και τα apps του fork (accounting, voip, mydata, settings κ.λπ.)
ADMIN_DATA = [
    {
        'name': 'Accounting',
        'app_label': 'accounting',
        'app_url': '/en/456-admin/accounting/',
        'has_module_perms': True,
        'models': [
            {
                'model': django_apps.get_model('accounting', 'ObligationProfile'),
                'name': 'Profiles Υποχρεώσεων',
                'object_name': 'ObligationProfile',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/accounting/obligationprofile/',
                'view_only': False,
                'add_url': '/en/456-admin/accounting/obligationprofile/add/',
            },
            {
                'model': django_apps.get_model('accounting', 'Ticket'),
                'name': 'Tickets (Missed Calls)',
                'object_name': 'Ticket',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/accounting/ticket/',
                'view_only': False,
                'add_url': '/en/456-admin/accounting/ticket/add/',
            },
            {
                'model': django_apps.get_model('accounting', 'ClientDocument'),
                'name': 'Έγγραφα Πελατών',
                'object_name': 'ClientDocument',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/accounting/clientdocument/',
                'view_only': False,
                'add_url': '/en/456-admin/accounting/clientdocument/add/',
            },
            {
                'model': django_apps.get_model('accounting', 'DocumentRequest'),
                'name': 'Αιτήματα Εγγράφων',
                'object_name': 'DocumentRequest',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/accounting/documentrequest/',
                'view_only': False,
                'add_url': '/en/456-admin/accounting/documentrequest/add/',
            },
            {
                'model': django_apps.get_model('accounting', 'EmailLog'),
                'name': 'Ιστορικό Email',
                'object_name': 'EmailLog',
                'perms': {'add': False, 'change': False, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/accounting/emaillog/',
                'view_only': True,
            },
            {
                'model': django_apps.get_model('accounting', 'EmailAutomationRule'),
                'name': 'Κανόνες Αυτοματοποίησης',
                'object_name': 'EmailAutomationRule',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/accounting/emailautomationrule/',
                'view_only': False,
                'add_url': '/en/456-admin/accounting/emailautomationrule/add/',
            },
            {
                'model': django_apps.get_model('accounting', 'VoIPCallLog'),
                'name': 'Καταγραφές Κλήσεων',
                'object_name': 'VoIPCallLog',
                'perms': {'add': False, 'change': True, 'delete': False, 'view': True},
                'admin_url': '/en/456-admin/accounting/voipcalllog/',
                'view_only': False,
            },
            {
                'model': django_apps.get_model('accounting', 'VoIPCall'),
                'name': 'Κλήσεις VoIP',
                'object_name': 'VoIPCall',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/accounting/voipcall/',
                'view_only': False,
                'add_url': '/en/456-admin/accounting/voipcall/add/',
            },
            {
                'model': django_apps.get_model('accounting', 'ClientCredential'),
                'name': 'Κωδικοί Πελατών',
                'object_name': 'ClientCredential',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/accounting/clientcredential/',
                'view_only': False,
                'add_url': '/en/456-admin/accounting/clientcredential/add/',
            },
            {
                'model': django_apps.get_model('accounting', 'MonthlyObligation'),
                'name': 'Μηνιαίες Υποχρεώσεις',
                'object_name': 'MonthlyObligation',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/accounting/monthlyobligation/',
                'view_only': False,
                'add_url': '/en/456-admin/accounting/monthlyobligation/add/',
            },
            {
                'model': django_apps.get_model('accounting', 'ObligationGroup'),
                'name': 'Ομάδες Υποχρεώσεων',
                'object_name': 'ObligationGroup',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/accounting/obligationgroup/',
                'view_only': False,
                'add_url': '/en/456-admin/accounting/obligationgroup/add/',
            },
            {
                'model': django_apps.get_model('accounting', 'ScheduledEmail'),
                'name': 'Προγραμματισμένα Email',
                'object_name': 'ScheduledEmail',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/accounting/scheduledemail/',
                'view_only': False,
                'add_url': '/en/456-admin/accounting/scheduledemail/add/',
            },
            {
                'model': django_apps.get_model('accounting', 'ClientProfile'),
                'name': 'Προφίλ Πελατών',
                'object_name': 'ClientProfile',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/accounting/clientprofile/',
                'view_only': False,
                'add_url': '/en/456-admin/accounting/clientprofile/add/',
            },
            {
                'model': django_apps.get_model('accounting', 'EmailTemplate'),
                'name': 'Πρότυπα Email',
                'object_name': 'EmailTemplate',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/accounting/emailtemplate/',
                'view_only': False,
                'add_url': '/en/456-admin/accounting/emailtemplate/add/',
            },
            {
                'model': django_apps.get_model('accounting', 'ArchiveConfiguration'),
                'name': 'Ρυθμίσεις Αρχειοθέτησης',
                'object_name': 'ArchiveConfiguration',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/accounting/archiveconfiguration/',
                'view_only': False,
                'add_url': '/en/456-admin/accounting/archiveconfiguration/add/',
            },
            {
                'model': django_apps.get_model('accounting', 'ObligationType'),
                'name': 'Τύποι Υποχρεώσεων',
                'object_name': 'ObligationType',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/accounting/obligationtype/',
                'view_only': False,
                'add_url': '/en/456-admin/accounting/obligationtype/add/',
            },
            {
                'model': django_apps.get_model('accounting', 'ClientObligation'),
                'name': 'Υποχρεώσεις Πελατών',
                'object_name': 'ClientObligation',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/accounting/clientobligation/',
                'view_only': False,
                'add_url': '/en/456-admin/accounting/clientobligation/add/',
            },
        ],
    },
    {
        'name': 'Administration',
        'app_label': 'admin',
        'app_url': '/en/456-admin/admin/',
        'has_module_perms': True,
        'models': [
            {
                'model': django_apps.get_model('admin', 'LogEntry'),
                'name': 'Log entries',
                'object_name': 'LogEntry',
                'perms': {'add': False, 'change': False, 'delete': False, 'view': True},
                'admin_url': '/en/456-admin/admin/logentry/',
                'view_only': True,
            },
        ],
    },
    {
        'name': 'Analytics',
        'app_label': 'analytics',
        'app_url': '/en/456-admin/analytics/',
        'has_module_perms': True,
        'models': [
            {
                'model': django_apps.get_model('analytics', 'IncomeStat'),
                'name': 'Income Summary',
                'object_name': 'IncomeStat',
                'perms': {'add': False, 'change': False, 'delete': False, 'view': True},
                'admin_url': '/en/456-admin/analytics/incomestat/',
                'view_only': True,
            },
            {
                'model': django_apps.get_model('analytics', 'IncomeStatSnapshot'),
                'name': 'IncomeStat Snapshots',
                'object_name': 'IncomeStatSnapshot',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/analytics/incomestatsnapshot/',
                'view_only': False,
                'add_url': '/en/456-admin/analytics/incomestatsnapshot/add/',
            },
        ],
    },
    {
        'name': 'Auth Token',
        'app_label': 'authtoken',
        'app_url': '/en/456-admin/authtoken/',
        'has_module_perms': True,
        'models': [
            {
                'model': django_apps.get_model('authtoken', 'TokenProxy'),
                'name': 'Tokens',
                'object_name': 'TokenProxy',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/authtoken/tokenproxy/',
                'view_only': False,
                'add_url': '/en/456-admin/authtoken/tokenproxy/add/',
            },
        ],
    },
    {
        'name': 'Authentication and Authorization',
        'app_label': 'auth',
        'app_url': '/en/456-admin/auth/',
        'has_module_perms': True,
        'models': [
            {
                'model': django_apps.get_model('auth', 'Group'),
                'name': 'Groups',
                'object_name': 'Group',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/auth/group/',
                'view_only': False,
                'add_url': '/en/456-admin/auth/group/add/',
            },
            {
                'model': django_apps.get_model('auth', 'Permission'),
                'name': 'Permissions',
                'object_name': 'Permission',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/auth/permission/',
                'view_only': False,
                'add_url': '/en/456-admin/auth/permission/add/',
            },
            {
                'model': django_apps.get_model('auth', 'User'),
                'name': 'Users',
                'object_name': 'User',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/auth/user/',
                'view_only': False,
                'add_url': '/en/456-admin/auth/user/add/',
            },
        ],
    },
    {
        'name': 'Chat',
        'app_label': 'chat',
        'app_url': '/en/456-admin/chat/',
        'has_module_perms': True,
        'models': [
            {
                'model': django_apps.get_model('chat', 'ChatMessage'),
                'name': 'Messages',
                'object_name': 'ChatMessage',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/chat/chatmessage/',
                'view_only': False,
                'add_url': '/en/456-admin/chat/chatmessage/add/',
            },
        ],
    },
    {
        'name': 'Common',
        'app_label': 'common',
        'app_url': '/en/456-admin/common/',
        'has_module_perms': True,
        'models': [
            {
                'model': django_apps.get_model('common', 'AuditLog'),
                'name': 'Audit Log',
                'object_name': 'AuditLog',
                'perms': {'add': False, 'change': False, 'delete': False, 'view': True},
                'admin_url': '/en/456-admin/common/auditlog/',
                'view_only': True,
            },
            {
                'model': django_apps.get_model('common', 'Department'),
                'name': 'Departments',
                'object_name': 'Department',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/common/department/',
                'view_only': False,
                'add_url': '/en/456-admin/common/department/add/',
            },
            {
                'model': django_apps.get_model('common', 'TheFile'),
                'name': 'Files',
                'object_name': 'TheFile',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/common/thefile/',
                'view_only': False,
                'add_url': '/en/456-admin/common/thefile/add/',
            },
            {
                'model': django_apps.get_model('common', 'Reminder'),
                'name': 'Reminders',
                'object_name': 'Reminder',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/common/reminder/',
                'view_only': False,
                'add_url': '/en/456-admin/common/reminder/add/',
            },
            {
                'model': django_apps.get_model('common', 'UserProfile'),
                'name': 'User profiles',
                'object_name': 'UserProfile',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/common/userprofile/',
                'view_only': False,
                'add_url': '/en/456-admin/common/userprofile/add/',
            },
        ],
    },
    {
        'name': 'Crm',
        'app_label': 'crm',
        'app_url': '/en/456-admin/crm/',
        'has_module_perms': True,
        'models': [
            {
                'model': django_apps.get_model('crm', 'City'),
                'name': 'Cities',
                'object_name': 'City',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/city/',
                'view_only': False,
                'add_url': '/en/456-admin/crm/city/add/',
            },
            {
                'model': django_apps.get_model('crm', 'ClosingReason'),
                'name': 'Closing reasons',
                'object_name': 'ClosingReason',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/closingreason/',
                'view_only': False,
                'add_url': '/en/456-admin/crm/closingreason/add/',
            },
            {
                'model': django_apps.get_model('crm', 'Company'),
                'name': 'Companies',
                'object_name': 'Company',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/company/',
                'view_only': False,
                'add_url': '/en/456-admin/crm/company/add/',
            },
            {
                'model': django_apps.get_model('crm', 'Contact'),
                'name': 'Contact persons',
                'object_name': 'Contact',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/contact/',
                'view_only': False,
                'add_url': '/en/456-admin/crm/contact/add/',
            },
            {
                'model': django_apps.get_model('crm', 'Country'),
                'name': 'Countries',
                'object_name': 'Country',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/country/',
                'view_only': False,
                'add_url': '/en/456-admin/crm/country/add/',
            },
            {
                'model': django_apps.get_model('crm', 'Currency'),
                'name': 'Currencies',
                'object_name': 'Currency',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/currency/',
                'view_only': False,
                'add_url': '/en/456-admin/crm/currency/add/',
            },
            {
                'model': django_apps.get_model('crm', 'Rate'),
                'name': 'Currency rates',
                'object_name': 'Rate',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/rate/',
                'view_only': False,
                'add_url': '/en/456-admin/crm/rate/add/',
            },
            {
                'model': django_apps.get_model('crm', 'Deal'),
                'name': 'Deals',
                'object_name': 'Deal',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/deal/',
                'view_only': False,
                'add_url': '/en/456-admin/crm/deal/add/',
            },
            {
                'model': django_apps.get_model('crm', 'CrmEmail'),
                'name': 'Emails in CRM',
                'object_name': 'CrmEmail',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/crmemail/',
                'view_only': False,
                'add_url': '/en/456-admin/crm/crmemail/add/',
            },
            {
                'model': django_apps.get_model('crm', 'Industry'),
                'name': 'Industries of Clients',
                'object_name': 'Industry',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/industry/',
                'view_only': False,
                'add_url': '/en/456-admin/crm/industry/add/',
            },
            {
                'model': django_apps.get_model('crm', 'LeadSource'),
                'name': 'Lead Sources',
                'object_name': 'LeadSource',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/leadsource/',
                'view_only': False,
                'add_url': '/en/456-admin/crm/leadsource/add/',
            },
            {
                'model': django_apps.get_model('crm', 'Lead'),
                'name': 'Leads',
                'object_name': 'Lead',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/lead/',
                'view_only': False,
                'add_url': '/en/456-admin/crm/lead/add/',
            },
            {
                'model': django_apps.get_model('crm', 'Payment'),
                'name': 'Payments',
                'object_name': 'Payment',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/payment/',
                'view_only': False,
                'add_url': '/en/456-admin/crm/payment/add/',
            },
            {
                'model': django_apps.get_model('crm', 'ProductCategory'),
                'name': 'Product categories',
                'object_name': 'ProductCategory',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/productcategory/',
                'view_only': False,
                'add_url': '/en/456-admin/crm/productcategory/add/',
            },
            {
                'model': django_apps.get_model('crm', 'Product'),
                'name': 'Products',
                'object_name': 'Product',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/product/',
                'view_only': False,
                'add_url': '/en/456-admin/crm/product/add/',
            },
            {
                'model': django_apps.get_model('crm', 'Request'),
                'name': 'Requests',
                'object_name': 'Request',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/request/',
                'view_only': False,
                'add_url': '/en/456-admin/crm/request/add/',
            },
            {
                'model': django_apps.get_model('crm', 'Shipment'),
                'name': 'Shipments',
                'object_name': 'Shipment',
                'perms': {'add': False, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/shipment/',
                'view_only': False,
            },
            {
                'model': django_apps.get_model('crm', 'Stage'),
                'name': 'Stages',
                'object_name': 'Stage',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/stage/',
                'view_only': False,
                'add_url': '/en/456-admin/crm/stage/add/',
            },
            {
                'model': django_apps.get_model('crm', 'Tag'),
                'name': 'Tags',
                'object_name': 'Tag',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/tag/',
                'view_only': False,
                'add_url': '/en/456-admin/crm/tag/add/',
            },
            {
                'model': django_apps.get_model('crm', 'ClientType'),
                'name': 'Types of Clients',
                'object_name': 'ClientType',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/crm/clienttype/',
                'view_only': False,
                'add_url': '/en/456-admin/crm/clienttype/add/',
            },
        ],
    },
    {
        'name': 'Help',
        'app_label': 'help',
        'app_url': '/en/456-admin/help/',
        'has_module_perms': True,
        'models': [
            {
                'model': django_apps.get_model('help', 'Page'),
                'name': 'Help pages',
                'object_name': 'Page',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/help/page/',
                'view_only': False,
                'add_url': '/en/456-admin/help/page/add/',
            },
            {
                'model': django_apps.get_model('help', 'Paragraph'),
                'name': 'Paragraphs',
                'object_name': 'Paragraph',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/help/paragraph/',
                'view_only': False,
                'add_url': '/en/456-admin/help/paragraph/add/',
            },
        ],
    },
    {
        'name': 'Inventory',
        'app_label': 'inventory',
        'app_url': '/en/456-admin/inventory/',
        'has_module_perms': True,
        'models': [
            {
                'model': django_apps.get_model('inventory', 'MyDataSyncLog'),
                'name': 'MyDATA Sync Logs',
                'object_name': 'MyDataSyncLog',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/inventory/mydatasynclog/',
                'view_only': False,
                'add_url': '/en/456-admin/inventory/mydatasynclog/add/',
            },
            {
                'model': django_apps.get_model('inventory', 'InvoiceItem'),
                'name': 'Γραμμές Τιμολογίου',
                'object_name': 'InvoiceItem',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/inventory/invoiceitem/',
                'view_only': False,
                'add_url': '/en/456-admin/inventory/invoiceitem/add/',
            },
            {
                'model': django_apps.get_model('inventory', 'ProductCategory'),
                'name': 'Κατηγορίες Προϊόντων',
                'object_name': 'ProductCategory',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/inventory/productcategory/',
                'view_only': False,
                'add_url': '/en/456-admin/inventory/productcategory/add/',
            },
            {
                'model': django_apps.get_model('inventory', 'StockMovement'),
                'name': 'Κινήσεις Αποθήκης',
                'object_name': 'StockMovement',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/inventory/stockmovement/',
                'view_only': False,
                'add_url': '/en/456-admin/inventory/stockmovement/add/',
            },
            {
                'model': django_apps.get_model('inventory', 'Product'),
                'name': 'Προϊόντα',
                'object_name': 'Product',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/inventory/product/',
                'view_only': False,
                'add_url': '/en/456-admin/inventory/product/add/',
            },
            {
                'model': django_apps.get_model('inventory', 'Invoice'),
                'name': 'Τιμολόγια',
                'object_name': 'Invoice',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/inventory/invoice/',
                'view_only': False,
                'add_url': '/en/456-admin/inventory/invoice/add/',
            },
        ],
    },
    {
        'name': 'Mass mail',
        'app_label': 'massmail',
        'app_url': '/en/456-admin/massmail/',
        'has_module_perms': True,
        'models': [
            {
                'model': django_apps.get_model('massmail', 'EmailAccount'),
                'name': 'Email Accounts',
                'object_name': 'EmailAccount',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/massmail/emailaccount/',
                'view_only': False,
                'add_url': '/en/456-admin/massmail/emailaccount/add/',
            },
            {
                'model': django_apps.get_model('massmail', 'EmlMessage'),
                'name': 'Email Messages',
                'object_name': 'EmlMessage',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/massmail/emlmessage/',
                'view_only': False,
                'add_url': '/en/456-admin/massmail/emlmessage/add/',
            },
            {
                'model': django_apps.get_model('massmail', 'EmlAccountsQueue'),
                'name': 'Eml accounts queues',
                'object_name': 'EmlAccountsQueue',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/massmail/emlaccountsqueue/',
                'view_only': False,
                'add_url': '/en/456-admin/massmail/emlaccountsqueue/add/',
            },
            {
                'model': django_apps.get_model('massmail', 'MailingOut'),
                'name': 'Mailing Outs',
                'object_name': 'MailingOut',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/massmail/mailingout/',
                'view_only': False,
                'add_url': '/en/456-admin/massmail/mailingout/add/',
            },
            {
                'model': django_apps.get_model('massmail', 'MassContact'),
                'name': 'Mass contacts',
                'object_name': 'MassContact',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/massmail/masscontact/',
                'view_only': False,
                'add_url': '/en/456-admin/massmail/masscontact/add/',
            },
            {
                'model': django_apps.get_model('massmail', 'Signature'),
                'name': 'Signatures',
                'object_name': 'Signature',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/massmail/signature/',
                'view_only': False,
                'add_url': '/en/456-admin/massmail/signature/add/',
            },
        ],
    },
    {
        'name': 'Mydata',
        'app_label': 'mydata',
        'app_url': '/en/456-admin/mydata/',
        'has_module_perms': True,
        'models': [
            {
                'model': django_apps.get_model('mydata', 'MyDataCredentials'),
                'name': 'MyDATA Credentials',
                'object_name': 'MyDataCredentials',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/mydata/mydatacredentials/',
                'view_only': False,
                'add_url': '/en/456-admin/mydata/mydatacredentials/add/',
            },
            {
                'model': django_apps.get_model('mydata', 'VATSyncLog'),
                'name': 'VAT Sync Logs',
                'object_name': 'VATSyncLog',
                'perms': {'add': False, 'change': False, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/mydata/vatsynclog/',
                'view_only': True,
            },
            {
                'model': django_apps.get_model('mydata', 'VATRecord'),
                'name': 'Εγγραφές ΦΠΑ',
                'object_name': 'VATRecord',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/mydata/vatrecord/',
                'view_only': False,
                'add_url': '/en/456-admin/mydata/vatrecord/add/',
            },
        ],
    },
    {
        'name': 'Settings',
        'app_label': 'settings',
        'app_url': '/en/456-admin/settings/',
        'has_module_perms': True,
        'models': [
            {
                'model': django_apps.get_model('settings', 'BannedCompanyName'),
                'name': 'Banned company names',
                'object_name': 'BannedCompanyName',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/settings/bannedcompanyname/',
                'view_only': False,
                'add_url': '/en/456-admin/settings/bannedcompanyname/add/',
            },
            {
                'model': django_apps.get_model('settings', 'MassmailSettings'),
                'name': 'Massmail Settings',
                'object_name': 'MassmailSettings',
                'perms': {'add': False, 'change': True, 'delete': False, 'view': True},
                'admin_url': '/en/456-admin/settings/massmailsettings/',
                'view_only': False,
            },
            {
                'model': django_apps.get_model('settings', 'PublicEmailDomain'),
                'name': 'Public email domains',
                'object_name': 'PublicEmailDomain',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/settings/publicemaildomain/',
                'view_only': False,
                'add_url': '/en/456-admin/settings/publicemaildomain/add/',
            },
            {
                'model': django_apps.get_model('settings', 'Reminders'),
                'name': 'Reminder settings',
                'object_name': 'Reminders',
                'perms': {'add': False, 'change': True, 'delete': False, 'view': True},
                'admin_url': '/en/456-admin/settings/reminders/',
                'view_only': False,
            },
            {
                'model': django_apps.get_model('settings', 'StopPhrase'),
                'name': 'Stop Phrases',
                'object_name': 'StopPhrase',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/settings/stopphrase/',
                'view_only': False,
                'add_url': '/en/456-admin/settings/stopphrase/add/',
            },
            {
                'model': django_apps.get_model('settings', 'BackupHistory'),
                'name': 'Ιστορικό Backups',
                'object_name': 'BackupHistory',
                'perms': {'add': False, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/settings/backuphistory/',
                'view_only': False,
            },
            {
                'model': django_apps.get_model('settings', 'BackupSettings'),
                'name': 'Ρυθμίσεις Backup',
                'object_name': 'BackupSettings',
                'perms': {'add': False, 'change': True, 'delete': False, 'view': True},
                'admin_url': '/en/456-admin/settings/backupsettings/',
                'view_only': False,
            },
            {
                'model': django_apps.get_model('settings', 'FilingSystemSettings'),
                'name': 'Ρυθμίσεις Αρχειοθέτησης',
                'object_name': 'FilingSystemSettings',
                'perms': {'add': False, 'change': True, 'delete': False, 'view': True},
                'admin_url': '/en/456-admin/settings/filingsystemsettings/',
                'view_only': False,
            },
        ],
    },
    {
        'name': 'Sites',
        'app_label': 'sites',
        'app_url': '/en/456-admin/sites/',
        'has_module_perms': True,
        'models': [
            {
                'model': django_apps.get_model('sites', 'Site'),
                'name': 'Sites',
                'object_name': 'Site',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/sites/site/',
                'view_only': False,
                'add_url': '/en/456-admin/sites/site/add/',
            },
        ],
    },
    {
        'name': 'Tasks',
        'app_label': 'tasks',
        'app_url': '/en/456-admin/tasks/',
        'has_module_perms': True,
        'models': [
            {
                'model': django_apps.get_model('tasks', 'Memo'),
                'name': 'Memos',
                'object_name': 'Memo',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/tasks/memo/',
                'view_only': False,
                'add_url': '/en/456-admin/tasks/memo/add/',
            },
            {
                'model': django_apps.get_model('tasks', 'ProjectStage'),
                'name': 'Project stages',
                'object_name': 'ProjectStage',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/tasks/projectstage/',
                'view_only': False,
                'add_url': '/en/456-admin/tasks/projectstage/add/',
            },
            {
                'model': django_apps.get_model('tasks', 'Project'),
                'name': 'Projects',
                'object_name': 'Project',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/tasks/project/',
                'view_only': False,
                'add_url': '/en/456-admin/tasks/project/add/',
            },
            {
                'model': django_apps.get_model('tasks', 'Resolution'),
                'name': 'Resolutions',
                'object_name': 'Resolution',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/tasks/resolution/',
                'view_only': False,
                'add_url': '/en/456-admin/tasks/resolution/add/',
            },
            {
                'model': django_apps.get_model('tasks', 'Tag'),
                'name': 'Tags',
                'object_name': 'Tag',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/tasks/tag/',
                'view_only': False,
                'add_url': '/en/456-admin/tasks/tag/add/',
            },
            {
                'model': django_apps.get_model('tasks', 'TaskStage'),
                'name': 'Task stages',
                'object_name': 'TaskStage',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/tasks/taskstage/',
                'view_only': False,
                'add_url': '/en/456-admin/tasks/taskstage/add/',
            },
            {
                'model': django_apps.get_model('tasks', 'Task'),
                'name': 'Tasks',
                'object_name': 'Task',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/tasks/task/',
                'view_only': False,
                'add_url': '/en/456-admin/tasks/task/add/',
            },
        ],
    },
    {
        'name': 'Token Blacklist',
        'app_label': 'token_blacklist',
        'app_url': '/en/456-admin/token_blacklist/',
        'has_module_perms': True,
        'models': [
            {
                'model': django_apps.get_model('token_blacklist', 'BlacklistedToken'),
                'name': 'Blacklisted Tokens',
                'object_name': 'BlacklistedToken',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/token_blacklist/blacklistedtoken/',
                'view_only': False,
                'add_url': '/en/456-admin/token_blacklist/blacklistedtoken/add/',
            },
            {
                'model': django_apps.get_model('token_blacklist', 'OutstandingToken'),
                'name': 'Outstanding Tokens',
                'object_name': 'OutstandingToken',
                'perms': {'add': False, 'change': True, 'delete': False, 'view': True},
                'admin_url': '/en/456-admin/token_blacklist/outstandingtoken/',
                'view_only': False,
            },
        ],
    },
    {
        'name': 'Voip',
        'app_label': 'voip',
        'app_url': '/en/456-admin/voip/',
        'has_module_perms': True,
        'models': [
            {
                'model': django_apps.get_model('voip', 'Connection'),
                'name': 'Connections',
                'object_name': 'Connection',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/voip/connection/',
                'view_only': False,
                'add_url': '/en/456-admin/voip/connection/add/',
            },
        ],
    },
    {
        'name': 'Λογιστικό CRM',
        'app_label': 'django_q',
        'app_url': '/en/456-admin/django_q/',
        'has_module_perms': True,
        'models': [
            {
                'model': django_apps.get_model('django_q', 'Failure'),
                'name': 'Failed tasks',
                'object_name': 'Failure',
                'perms': {'add': False, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/django_q/failure/',
                'view_only': False,
            },
            {
                'model': django_apps.get_model('django_q', 'OrmQ'),
                'name': 'Queued tasks',
                'object_name': 'OrmQ',
                'perms': {'add': False, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/django_q/ormq/',
                'view_only': False,
            },
            {
                'model': django_apps.get_model('django_q', 'Schedule'),
                'name': 'Scheduled tasks',
                'object_name': 'Schedule',
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/django_q/schedule/',
                'view_only': False,
                'add_url': '/en/456-admin/django_q/schedule/add/',
            },
            {
                'model': django_apps.get_model('django_q', 'Success'),
                'name': 'Successful tasks',
                'object_name': 'Success',
                'perms': {'add': False, 'change': True, 'delete': True, 'view': True},
                'admin_url': '/en/456-admin/django_q/success/',
                'view_only': False,
            },
        ],
    },
]
