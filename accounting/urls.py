"""
Accounting URLs Configuration
Author: ddiplas
Version: 2.3
Description: Unified and optimized URL routing for the Accounting app.
             Includes JWT auth endpoints and API documentation.
"""

from django.urls import path, include

from settings.api import NotificationSettingsView
from rest_framework.routers import DefaultRouter
from . import views_main as views
from . import api_auth
from .api_clients import ClientViewSet
from .api_obligations import ObligationViewSet, ObligationTypeViewSet
from .api_dashboard import (
    dashboard_stats,
    dashboard_calendar,
    dashboard_recent_activity,
    dashboard_client_stats
)
from .api_obligation_profiles import (
    clients_obligation_status,
    client_obligation_profile,
    obligation_types_grouped,
    obligation_profiles_list,
    generate_month_obligations,
    bulk_assign_obligations,
)
from .api_obligation_settings import (
    ObligationTypeSettingsViewSet,
    ObligationProfileSettingsViewSet,
    ObligationGroupSettingsViewSet,
)
from .api_voip import (
    VoIPCallViewSet as VoIPCallViewSetV2,
    TicketViewSet,
    calls_stats,
    tickets_stats,
    search_clients_for_match,
)
from .api_search import global_search
from .api_documents import (
    DocumentViewSet,
    attach_document_to_obligation,
    obligation_documents,
)
from .api_email import (
    email_templates,
    email_template_detail,
    preview_email,
    send_email,
    send_obligation_notice,
    complete_and_notify,
    bulk_complete_with_notify,
    bulk_complete_with_documents,
    email_history,
    email_settings,
    email_settings_test,
    email_settings_send_test,
)
from .api_door import (
    door_status as api_door_status,
    door_open as api_door_open,
    door_pulse as api_door_pulse,
    door_access_logs as api_door_logs,
)
from .api_gsis import (
    afm_lookup,
    gsis_settings_status,
    gsis_settings_update,
    gsis_test_connection,
)
from .api_notifications import notifications_list
from .api_users import (
    user_list,
    user_create,
    user_detail,
    user_update,
    user_delete,
    user_toggle_active,
)
from .api_export_import import (
    export_clients_csv,
    export_clients_template,
    import_clients_csv,
    export_obligation_types_csv,
    export_obligation_profiles_csv,
    export_client_obligations_csv,
    import_client_obligations_csv,
)
from .api_reports import (
    reports_stats,
    reports_export,
    reports_export_download,
    client_statement,
    vat_summary,
)

# New Completion Views
from .completion.completion_views import (
    obligation_list_view,
    obligation_list_api,
    obligation_complete_single,
    obligation_complete_bulk,
    obligation_upload_file,
    email_compose_view,
    email_send_view,
    email_send_bulk_view,
    client_files_view,
    file_download,
    file_delete,
    archive_settings_view,
    archive_config_create,
    open_document_folder,
    open_client_folder,
)
from .api_document_upload import (
    check_existing_document,
    upload_document_with_version,
    document_preview,
    suggest_document_metadata,
)
from .api_file_manager import (
    DocumentViewSet as FileManagerDocumentViewSet,
    TagViewSet,
    SharedLinkViewSet,
    FavoriteViewSet,
    CollectionViewSet,
    PublicSharedLinkView,
    PublicSharedLinkDownloadView,
    FileManagerStatsView,
    RecentDocumentsView,
    BrowseFoldersView,
)


app_name = "accounting"

# ============================================
# REST API ROUTER SETUP
# ============================================
router = DefaultRouter()
router.register(r"voip-calls", views.VoIPCallViewSet, basename="voip-call")
router.register(r"voip-call-logs", views.VoIPCallLogViewSet, basename="voip-call-log")

# New enhanced VoIP/Tickets router (v2)
router_v2 = DefaultRouter()
router_v2.register(r'calls', VoIPCallViewSetV2, basename='calls')
router_v2.register(r'tickets', TicketViewSet, basename='tickets')

# Enhanced Documents API (replaces old ViewSet)
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'obligations', ObligationViewSet, basename='obligation')
router.register(r'obligation-types', ObligationTypeViewSet, basename='obligation-type')

# Settings management ViewSets
router.register(r'settings/obligation-types', ObligationTypeSettingsViewSet, basename='settings-obligation-type')
router.register(r'settings/obligation-profiles', ObligationProfileSettingsViewSet, basename='settings-obligation-profile')
router.register(r'settings/obligation-groups', ObligationGroupSettingsViewSet, basename='settings-obligation-group')
# ============================================
# URL PATTERNS
# ============================================
urlpatterns = [
    # MAIN VIEWS
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("reports/", views.reports_view, name="reports"),
    path("client/<int:client_id>/", views.client_detail_view, name="client_detail"),

    # CALENDAR
    path("calendar/", views.calendar_view, name="calendar"),
    path("api/calendar-events/", views.calendar_events_api, name="calendar_events_api"),

    path('door-status/', views.door_status, name='door_status'),
    path('open-door/', views.open_door, name='open_door'),
    path('door-control/', views.door_control, name='door_control'),   
    
    # NOTIFICATIONS (Django admin views)
    path("notifications/", views.get_notifications, name="notifications"),
    # REST API notifications (JWT authenticated - for React frontend)
    path("api/notifications/", notifications_list, name="api_notifications"),

    # OBLIGATION ACTIONS
    path("obligation/<int:obligation_id>/", views.obligation_detail_view, name="obligation_detail"),
    path("obligation/<int:obligation_id>/complete/", views.quick_complete_obligation, name="obligation_complete"),
    path("obligation/<int:obligation_id>/complete-with-file/", views.complete_with_file, name="obligation_complete_file"),
    path("quick-complete/<int:obligation_id>/", views.quick_complete_obligation, name="quick_complete"),  # Legacy
    path("bulk-complete/", views.bulk_complete_obligations, name="bulk_complete"),  # Enhanced bulk complete with email & file
    path("advanced-bulk-complete/", views.advanced_bulk_complete, name="advanced_bulk_complete"),

    # EXPORT
    path("export-excel/", views.export_filtered_excel, name="export_excel"),

    # VOIP MANAGEMENT
    path("voip/dashboard/", views.voip_dashboard, name="voip_dashboard"),
    path("voip/list/", views.VoIPCallsListView.as_view(), name="voip_list"),

    # Fritz!Box Webhook (Token authenticated, no session required)
    path("api/fritz-webhook/", views.fritz_webhook, name="fritz_webhook"),

    # AJAX / API Endpoints
    path("voip/api/calls/", views.voip_calls_api, name="voip_calls_api"),
    path("voip/api/update/<int:call_id>/", views.voip_call_update, name="voip_call_update"),
    path("voip/api/statistics/", views.voip_statistics, name="voip_statistics"),
    path("voip/api/bulk-action/", views.voip_bulk_action, name="voip_bulk_action"),

    # Export
    path("voip/export/csv/", views.voip_export_csv, name="voip_export_csv"),

    # EMAIL AUTOMATION API
    path("api/email-templates/", views.api_email_templates, name="api_email_templates"),
    path("api/email-template/<int:template_id>/", views.api_email_template_detail, name="api_email_template_detail"),
    path("api/send-bulk-email/", views.api_send_bulk_email, name="api_send_bulk_email"),
    path("api/send-bulk-email-direct/", views.api_send_bulk_email_direct, name="api_send_bulk_email_direct"),

    # OBLIGATION API
    path("api/obligation-check/", views.check_obligation_duplicate, name="check_obligation"),

    # WIZARD API
    path("api/obligations-wizard/", views.api_obligations_wizard, name="api_obligations_wizard"),
    path("wizard-bulk-process/", views.wizard_bulk_process, name="wizard_bulk_process"),

    # GLOBAL SEARCH API
    path("api/search/", views.global_search_api, name="global_search_api"),
    path("api/v1/search/", global_search, name="api_v1_global_search"),

    # PDF REPORTS
    path("reports/client/<int:client_id>/pdf/", views.client_report_pdf, name="client_report_pdf"),
    path("reports/monthly/<int:year>/<int:month>/pdf/", views.monthly_report_pdf, name="monthly_report_pdf"),

    # TICKET MANAGEMENT
    path("ticket/<int:ticket_id>/assign/", views.assign_ticket, name="assign_ticket"),
    path("ticket/<int:ticket_id>/update/", views.update_ticket_status, name="update_ticket_status"),
    path("ticket/send-email/", views.send_ticket_email, name="send_ticket_email"),

    # DASHBOARD API
    path("api/dashboard/stats/", dashboard_stats, name="api_dashboard_stats"),
    path("api/dashboard/calendar/", dashboard_calendar, name="api_dashboard_calendar"),
    path("api/dashboard/recent-activity/", dashboard_recent_activity, name="api_dashboard_recent_activity"),
    path("api/dashboard/client-stats/", dashboard_client_stats, name="api_dashboard_client_stats"),

    # REPORTS API
    path("api/reports/stats/", reports_stats, name="api_reports_stats"),
    path("api/reports/export/", reports_export, name="api_reports_export"),
    path("api/reports/export/download/", reports_export_download, name="api_reports_export_download"),
    path("api/reports/client-statement/<int:client_id>/", client_statement, name="api_client_statement"),
    path("api/reports/vat-summary/", vat_summary, name="api_vat_summary"),

    # ============================================
    # OBLIGATION PROFILE APIs
    # ============================================
    path("api/v1/clients/obligation-status/", clients_obligation_status, name="clients_obligation_status"),
    path("api/v1/clients/<int:client_id>/obligation-profile/", client_obligation_profile, name="client_obligation_profile"),
    path("api/v1/obligation-types/grouped/", obligation_types_grouped, name="obligation_types_grouped"),
    path("api/v1/obligation-profiles/", obligation_profiles_list, name="obligation_profiles_list"),
    path("api/v1/obligations/generate-month/", generate_month_obligations, name="generate_month_obligations"),
    path("api/v1/obligations/bulk-assign/", bulk_assign_obligations, name="bulk_assign_obligations"),

    # ============================================
    # DOOR CONTROL API (v1) - JWT authenticated
    # ============================================
    path("api/v1/door/status/", api_door_status, name="api_v1_door_status"),
    path("api/v1/door/open/", api_door_open, name="api_v1_door_open"),
    path("api/v1/door/pulse/", api_door_pulse, name="api_v1_door_pulse"),
    path("api/v1/door/logs/", api_door_logs, name="api_v1_door_logs"),

    # ============================================
    # NOTIFICATIONS API (v1) - JWT authenticated
    # ============================================
    path("api/v1/notifications/", notifications_list, name="api_v1_notifications"),

    # ============================================
    # GSIS API (v1) - Αναζήτηση στοιχείων με ΑΦΜ
    # ============================================
    path("api/v1/afm-lookup/", afm_lookup, name="api_v1_afm_lookup"),
    path("api/v1/gsis/status/", gsis_settings_status, name="api_v1_gsis_status"),
    path("api/v1/gsis/settings/", gsis_settings_update, name="api_v1_gsis_settings"),
    path("api/v1/gsis/test/", gsis_test_connection, name="api_v1_gsis_test"),

    # ============================================
    # EMAIL API (v1)
    # ============================================
    path("api/v1/email/templates/", email_templates, name="api_v1_email_templates"),
    path("api/v1/email/templates/<int:template_id>/", email_template_detail, name="api_v1_email_template_detail"),
    path("api/v1/email/preview/", preview_email, name="api_v1_email_preview"),
    path("api/v1/email/send/", send_email, name="api_v1_email_send"),
    path("api/v1/email/send-obligation-notice/", send_obligation_notice, name="api_v1_send_obligation_notice"),
    path("api/v1/email/history/", email_history, name="api_v1_email_history"),
    path("api/v1/email/settings/", email_settings, name="api_v1_email_settings"),
    path("api/v1/email/settings/test/", email_settings_test, name="api_v1_email_settings_test"),
    path("api/v1/email/settings/send-test/", email_settings_send_test, name="api_v1_email_settings_send_test"),

    # ============================================
    # OBLIGATION DOCUMENT & NOTIFICATION ENDPOINTS
    # ============================================
    path("api/v1/obligations/<int:obligation_id>/documents/", obligation_documents, name="api_v1_obligation_documents"),
    path("api/v1/obligations/<int:obligation_id>/attach-document/", attach_document_to_obligation, name="api_v1_attach_document"),
    path("api/v1/obligations/<int:obligation_id>/complete-and-notify/", complete_and_notify, name="api_v1_complete_and_notify"),
    path("api/v1/obligations/bulk-complete-notify/", bulk_complete_with_notify, name="api_v1_bulk_complete_notify"),
    path("api/v1/obligations/bulk-complete-with-documents/", bulk_complete_with_documents, name="api_v1_bulk_complete_with_documents"),

    # Πριν το router ώστε να μην το «πιάνει» το detail route documents/<pk>/
    path("api/documents/suggest/", suggest_document_metadata, name="api_suggest_document_metadata_legacy"),
    path("api/v1/documents/suggest/", suggest_document_metadata, name="api_suggest_document_metadata"),

    # REST ROUTER
    path("api/", include(router.urls)),
    path("api/v1/", include(router.urls)),  # Versioned API endpoint

    # ============================================
    # ENHANCED VOIP/TICKETS API (v2)
    # ============================================
    path("api/v1/", include(router_v2.urls)),  # New calls/tickets endpoints
    path("api/v1/calls/stats/", calls_stats, name="api_calls_stats"),
    path("api/v1/tickets/stats/", tickets_stats, name="api_tickets_stats"),
    path("api/v1/clients/search-for-match/", search_clients_for_match, name="search_clients_for_match"),

    # ==================================================
    # JWT AUTHENTICATION ENDPOINTS
    # ==================================================
    path("api/auth/login/", api_auth.CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh/", api_auth.CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/verify/", api_auth.CustomTokenVerifyView.as_view(), name="token_verify"),
    path("api/auth/logout/", api_auth.logout_view, name="auth_logout"),
    path("api/auth/me/", api_auth.current_user_view, name="auth_me"),

    # ==================================================
    # UTILITY ENDPOINTS
    # ==================================================
    path("api/health/", api_auth.health_check, name="api_health"),
    path("api/test/", api_auth.api_test, name="api_test"),

    # ==================================================
    # USER MANAGEMENT ENDPOINTS (Admin only)
    # ==================================================
    path("api/v1/users/", user_list, name="api_user_list"),
    path("api/v1/users/create/", user_create, name="api_user_create"),
    path("api/v1/users/<int:user_id>/", user_detail, name="api_user_detail"),
    path("api/v1/users/<int:user_id>/update/", user_update, name="api_user_update"),
    path("api/v1/users/<int:user_id>/delete/", user_delete, name="api_user_delete"),
    path("api/v1/users/<int:user_id>/toggle-active/", user_toggle_active, name="api_user_toggle_active"),

    # ==================================================
    # OBLIGATION COMPLETION & FILE MANAGEMENT VIEWS
    # ==================================================
    # Obligation List & Management
    path("obligations/", obligation_list_view, name="obligation_list"),
    path("obligations/api/", obligation_list_api, name="obligation_list_api"),
    path("obligations/<int:obligation_id>/complete/", obligation_complete_single, name="obligation_complete_single"),
    path("obligations/<int:obligation_id>/upload/", obligation_upload_file, name="obligation_upload_file"),
    path("obligations/complete-bulk/", obligation_complete_bulk, name="obligation_complete_bulk"),

    # Email Composition & Sending
    path("obligations/email/", email_compose_view, name="email_compose"),
    path("obligations/email/send/", email_send_view, name="email_send"),
    path("obligations/email/send-bulk/", email_send_bulk_view, name="email_send_bulk"),

    # Client Files Browser
    path("client/<int:client_id>/files/", client_files_view, name="client_files"),
    path("client/<int:client_id>/files/download/<path:file_path>", file_download, name="file_download"),
    path("client/<int:client_id>/files/delete/", file_delete, name="file_delete"),

    # Open Folder (local file browser)
    path("document/<int:document_id>/open-folder/", open_document_folder, name="open_document_folder"),
    path("client/<int:client_id>/open-folder/", open_client_folder, name="open_client_folder"),

    # Archive Settings
    path("settings/archive/", archive_settings_view, name="archive_settings"),
    path("settings/archive/create/", archive_config_create, name="archive_config_create"),

    # ==================================================
    # DOCUMENT UPLOAD API WITH VERSIONING
    # ==================================================
    path("api/v1/documents/check-existing/", check_existing_document, name="api_check_existing_document"),
    path("api/v1/documents/upload-with-version/", upload_document_with_version, name="api_upload_document_with_version"),
    path("api/v1/documents/<int:document_id>/preview/", document_preview, name="api_document_preview"),

    # ==================================================
    # EXPORT/IMPORT ENDPOINTS
    # ==================================================
    # Client Export/Import
    path("api/v1/export/clients/csv/", export_clients_csv, name="api_export_clients_csv"),
    path("api/v1/export/clients/template/", export_clients_template, name="api_export_clients_template"),
    path("api/v1/import/clients/csv/", import_clients_csv, name="api_import_clients_csv"),

    # Obligation Types & Profiles Export
    path("api/v1/export/obligation-types/csv/", export_obligation_types_csv, name="api_export_obligation_types_csv"),
    path("api/v1/export/obligation-profiles/csv/", export_obligation_profiles_csv, name="api_export_obligation_profiles_csv"),

    # Client-Obligation Assignment Export/Import
    path("api/v1/export/client-obligations/csv/", export_client_obligations_csv, name="api_export_client_obligations_csv"),
    path("api/v1/import/client-obligations/csv/", import_client_obligations_csv, name="api_import_client_obligations_csv"),

    # ==================================================
    # myDATA API (ΦΠΑ/ΑΑΔΕ)
    # ==================================================
    path("api/mydata/", include("mydata.urls")),

    # ==================================================
    # BACKUP & RESTORE API
    # ==================================================
    path("api/settings/backup/", include("settings.backup_urls")),
    path("api/v1/notifications/settings/", NotificationSettingsView.as_view(),
         name="api_v1_notification_settings"),

    # ==================================================
    # FILE MANAGER API (v1)
    # ==================================================
    # Documents
    path("api/v1/file-manager/documents/", FileManagerDocumentViewSet.as_view({
        'get': 'list',
    }), name="file_manager_documents"),
    path("api/v1/file-manager/documents/<int:pk>/", FileManagerDocumentViewSet.as_view({
        'get': 'retrieve',
        'delete': 'destroy',
    }), name="file_manager_document_detail"),
    path("api/v1/file-manager/documents/upload/", FileManagerDocumentViewSet.as_view({
        'post': 'upload',
    }), name="file_manager_upload"),
    path("api/v1/file-manager/documents/bulk-delete/", FileManagerDocumentViewSet.as_view({
        'post': 'bulk_delete',
    }), name="file_manager_bulk_delete"),
    path("api/v1/file-manager/documents/<int:pk>/preview/", FileManagerDocumentViewSet.as_view({
        'get': 'preview',
    }), name="file_manager_preview"),
    path("api/v1/file-manager/documents/<int:pk>/download/", FileManagerDocumentViewSet.as_view({
        'get': 'download',
    }), name="file_manager_download"),
    path("api/v1/file-manager/documents/<int:pk>/versions/", FileManagerDocumentViewSet.as_view({
        'get': 'versions',
    }), name="file_manager_versions"),
    path("api/v1/file-manager/documents/<int:pk>/tags/", FileManagerDocumentViewSet.as_view({
        'post': 'add_tags',
    }), name="file_manager_add_tags"),
    path("api/v1/file-manager/documents/<int:pk>/tags/<int:tag_id>/", FileManagerDocumentViewSet.as_view({
        'delete': 'remove_tag',
    }), name="file_manager_remove_tag"),

    # Tags
    path("api/v1/file-manager/tags/", TagViewSet.as_view({
        'get': 'list',
        'post': 'create',
    }), name="file_manager_tags"),
    path("api/v1/file-manager/tags/<int:pk>/", TagViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy',
    }), name="file_manager_tag_detail"),

    # Shared Links
    path("api/v1/file-manager/shared-links/", SharedLinkViewSet.as_view({
        'get': 'list',
        'post': 'create',
    }), name="file_manager_shared_links"),
    path("api/v1/file-manager/shared-links/<int:pk>/", SharedLinkViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy',
    }), name="file_manager_shared_link_detail"),
    path("api/v1/file-manager/shared-links/<int:pk>/regenerate-token/", SharedLinkViewSet.as_view({
        'post': 'regenerate_token',
    }), name="file_manager_regenerate_token"),
    path("api/v1/file-manager/shared-links/<int:pk>/access-logs/", SharedLinkViewSet.as_view({
        'get': 'access_logs',
    }), name="file_manager_access_logs"),

    # Favorites
    path("api/v1/file-manager/favorites/", FavoriteViewSet.as_view({
        'get': 'list',
        'post': 'create',
    }), name="file_manager_favorites"),
    path("api/v1/file-manager/favorites/<int:pk>/", FavoriteViewSet.as_view({
        'delete': 'destroy',
    }), name="file_manager_favorite_detail"),

    # Collections
    path("api/v1/file-manager/collections/", CollectionViewSet.as_view({
        'get': 'list',
        'post': 'create',
    }), name="file_manager_collections"),
    path("api/v1/file-manager/collections/<int:pk>/", CollectionViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy',
    }), name="file_manager_collection_detail"),
    path("api/v1/file-manager/collections/<int:pk>/documents/", CollectionViewSet.as_view({
        'post': 'add_documents',
    }), name="file_manager_collection_add_docs"),
    path("api/v1/file-manager/collections/<int:pk>/documents/<int:doc_id>/", CollectionViewSet.as_view({
        'delete': 'remove_document',
    }), name="file_manager_collection_remove_doc"),

    # Dashboard & Stats
    path("api/v1/file-manager/stats/", FileManagerStatsView.as_view(), name="file_manager_stats"),
    path("api/v1/file-manager/recent/", RecentDocumentsView.as_view(), name="file_manager_recent"),
    path("api/v1/file-manager/browse/", BrowseFoldersView.as_view(), name="file_manager_browse"),

    # Public Shared Link Access (NO AUTH REQUIRED)
    path("share/<str:token>/", PublicSharedLinkView.as_view(), name="shared_link_access"),
    path("share/<str:token>/download/", PublicSharedLinkDownloadView.as_view(), name="shared_link_download"),
]
