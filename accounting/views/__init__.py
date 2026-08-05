# accounting/views/__init__.py
"""
Accounting Views Package

This package organizes the accounting views into separate modules for better maintainability.
"""

# Helper functions (internal use)
from .helpers import (
    _safe_int,
    _calculate_dashboard_stats,
    _build_filtered_query,
    _calculate_monthly_stats,
    _process_individual_obligations,
    _process_grouped_obligations,
    _match_client_by_phone_standalone,
    _format_voip_call,
    _get_status_color,
    _get_resolution_color,
    _calculate_success_rate,
    _log_voip_change,
    _calculate_send_time,
    _create_bulk_emails,
    _get_filters_from_request,
    _build_export_query,
    _apply_excel_styling,
    _write_excel_headers,
    _write_excel_data,
    _auto_adjust_excel_columns,
    _calculate_monthly_completion_stats,
    _calculate_client_performance,
    _calculate_time_stats,
    _calculate_revenue,
    _calculate_type_stats,
    _calculate_current_month_stats,
    _format_chart_data,
)

# VoIP views
from .voip import (
    # Function-based views
    voip_dashboard,
    fritz_webhook,
    voip_calls_api,
    voip_call_update,
    voip_statistics,
    voip_bulk_action,
    voip_export_csv,
    # Class-based views
    VoIPCallViewSet,
    VoIPCallLogViewSet,
)

# Dashboard views
from .dashboard import (
    dashboard_view,
    reports_view,
)

# Calendar views
from .calendar import (
    calendar_view,
    calendar_events_api,
)

# Email views
from .email_views import (
    api_email_templates,
    api_send_bulk_email,
    api_email_template_detail,
    api_send_bulk_email_direct,
    send_ticket_email,
)

# Obligation views
from .obligations import (
    quick_complete_obligation,
    bulk_complete_view,
    advanced_bulk_complete,
    check_obligation_duplicate,
    complete_with_file,
    bulk_complete_obligations,
    obligation_detail_view,
    api_obligations_wizard,
    wizard_bulk_process,
)

# Ticket views
from .tickets import (
    assign_ticket,
    update_ticket_status,
)

# Door control views (Tasmota IoT)
from .door import (
    door_status,
    open_door,
    door_control,
)

# Export views
from .export import (
    export_filtered_excel,
)

# Search views
from .search import (
    global_search_api,
)

# Report views (PDF generation)
from .reports import (
    client_report_pdf,
    monthly_report_pdf,
)

# Client views
from .clients import (
    client_detail_view,
    ClientDocumentViewSet,
)

# Notification views
from .notifications import (
    get_notifications,
)

__all__ = [
    # Helpers
    '_safe_int',
    '_calculate_dashboard_stats',
    '_build_filtered_query',
    '_calculate_monthly_stats',
    '_process_individual_obligations',
    '_process_grouped_obligations',
    '_match_client_by_phone_standalone',
    '_format_voip_call',
    '_get_status_color',
    '_get_resolution_color',
    '_calculate_success_rate',
    '_log_voip_change',
    '_calculate_send_time',
    '_create_bulk_emails',
    '_get_filters_from_request',
    '_build_export_query',
    '_apply_excel_styling',
    '_write_excel_headers',
    '_write_excel_data',
    '_auto_adjust_excel_columns',
    '_calculate_monthly_completion_stats',
    '_calculate_client_performance',
    '_calculate_time_stats',
    '_calculate_revenue',
    '_calculate_type_stats',
    '_calculate_current_month_stats',
    '_format_chart_data',
    # VoIP function-based views
    'voip_dashboard',
    'fritz_webhook',
    'voip_calls_api',
    'voip_call_update',
    'voip_statistics',
    'voip_bulk_action',
    'voip_export_csv',
    # VoIP class-based views
    'VoIPCallViewSet',
    'VoIPCallLogViewSet',
    # Dashboard views
    'dashboard_view',
    'reports_view',
    # Calendar views
    'calendar_view',
    'calendar_events_api',
    # Email views
    'api_email_templates',
    'api_send_bulk_email',
    'api_email_template_detail',
    'api_send_bulk_email_direct',
    'send_ticket_email',
    # Obligation views
    'quick_complete_obligation',
    'bulk_complete_view',
    'advanced_bulk_complete',
    'check_obligation_duplicate',
    'complete_with_file',
    'bulk_complete_obligations',
    'obligation_detail_view',
    'api_obligations_wizard',
    'wizard_bulk_process',
    # Ticket views
    'assign_ticket',
    'update_ticket_status',
    # Door control views
    'door_status',
    'open_door',
    'door_control',
    # Export views
    'export_filtered_excel',
    # Search views
    'global_search_api',
    # Report views
    'client_report_pdf',
    'monthly_report_pdf',
    # Client views
    'client_detail_view',
    'ClientDocumentViewSet',
    # Notification views
    'get_notifications',
]
