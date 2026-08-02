"""
Accounting Views - Re-export Module
Author: ddiplas
Version: 3.0

This module re-exports all views from the accounting/views/ package.
All view implementations have been moved to separate modules for better maintainability.

Module structure:
- views/helpers.py      - Helper functions for views
- views/voip.py         - VoIP call management views
- views/dashboard.py    - Dashboard and reports views
- views/calendar.py     - Calendar views
- views/email_views.py  - Email management views
- views/obligations.py  - Obligation management views
- views/tickets.py      - Ticket management views
- views/door.py         - Door control views (Tasmota IoT)
- views/export.py       - Excel export views
- views/search.py       - Global search API
- views/reports.py      - PDF report generation
- views/clients.py      - Client detail and document views
- views/notifications.py - Notification system views
"""

import logging

# Re-export all views from the views package
from .views import (
    # Helper functions
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
    # VoIP views
    voip_dashboard,
    fritz_webhook,
    voip_calls_api,
    voip_call_update,
    voip_statistics,
    voip_bulk_action,
    voip_export_csv,
    VoIPCallViewSet,
    VoIPCallLogViewSet,
    # Dashboard views
    dashboard_view,
    reports_view,
    # Calendar views
    calendar_view,
    calendar_events_api,
    # Email views
    api_email_templates,
    api_send_bulk_email,
    api_email_template_detail,
    api_send_bulk_email_direct,
    send_ticket_email,
    # Obligation views
    quick_complete_obligation,
    bulk_complete_view,
    advanced_bulk_complete,
    check_obligation_duplicate,
    complete_with_file,
    bulk_complete_obligations,
    obligation_detail_view,
    api_obligations_wizard,
    wizard_bulk_process,
    # Ticket views
    assign_ticket,
    update_ticket_status,
    # Door control views
    door_status,
    open_door,
    door_control,
    # Export views
    export_filtered_excel,
    # Search views
    global_search_api,
    # Report views
    client_report_pdf,
    monthly_report_pdf,
    # Client views
    client_detail_view,
    ClientDocumentViewSet,
    # Notification views
    get_notifications,
)

logger = logging.getLogger(__name__)

logger.info("Accounting views module loaded successfully (re-exports from views/ package)")
