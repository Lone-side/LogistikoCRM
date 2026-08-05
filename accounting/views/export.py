"""
Export Views
Author: ddiplas
Description: Views for exporting data to Excel and other formats
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpResponse
from django.utils import timezone

import openpyxl
import logging

from .helpers import (
    _get_filters_from_request,
    _build_export_query,
    _apply_excel_styling,
    _write_excel_headers,
    _write_excel_data,
    _auto_adjust_excel_columns,
)

logger = logging.getLogger(__name__)


@staff_member_required
def export_filtered_excel(request):
    """
    Export filtered obligations to Excel with formatting
    """
    # Το export περιέχει ΑΦΜ/επωνυμίες — απαιτεί το ξεχωριστό export permission
    if not request.user.has_perm('accounting.export_clientprofile'):
        return JsonResponse(
            {'error': 'Δεν έχετε δικαίωμα εξαγωγής στοιχείων πελατών.'}, status=403
        )
    try:
        # Get filters from request
        filters = _get_filters_from_request(request)

        # Build query
        query = _build_export_query(filters, request.user)

        # Create Excel workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Υποχρεώσεις"

        # Apply styling
        _apply_excel_styling(ws)

        # Add headers and data
        _write_excel_headers(ws)
        _write_excel_data(ws, query)

        # Auto-adjust columns
        _auto_adjust_excel_columns(ws)

        # Prepare response
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f'Ypohrewseis_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        wb.save(response)
        logger.info(f"Excel exported by {request.user.username}: {query.count()} records")
        return response

    except Exception as e:
        logger.error(f"Error exporting Excel: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)
