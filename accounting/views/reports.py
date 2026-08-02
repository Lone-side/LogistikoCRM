"""
PDF Report Generation Views
Author: ddiplas
Description: Views for generating PDF reports for clients and monthly summaries
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.template.loader import render_to_string

from ..models import ClientProfile, MonthlyObligation
from ..utils.report_constants import GREEK_MONTHS_FULL

import logging
from accounting.services.access import (
    accessible_clients, accessible_documents, accessible_obligations,
)

logger = logging.getLogger(__name__)


@staff_member_required
def client_report_pdf(request, client_id):
    """
    Generate PDF report for a specific client.
    Includes client info and obligation history.
    """
    from io import BytesIO
    try:
        from xhtml2pdf import pisa
    except ImportError:
        return HttpResponse(
            'xhtml2pdf δεν είναι εγκατεστημένο. Εγκαταστήστε το με: pip install xhtml2pdf',
            status=500
        )

    client = get_object_or_404(accessible_clients(request.user), id=client_id)

    # Get all obligations for stats calculation (before slicing)
    all_obligations = accessible_obligations(request.user).filter(client=client)

    # Calculate statistics from unsliced queryset
    stats = {
        'total': all_obligations.count(),
        'completed': all_obligations.filter(status='completed').count(),
        'pending': all_obligations.filter(status='pending').count(),
        'overdue': all_obligations.filter(status='overdue').count(),
    }

    # Get limited obligations for the table (after stats calculation)
    obligations = all_obligations.select_related('obligation_type').order_by('-deadline')[:50]

    # Completion rate
    if stats['total'] > 0:
        stats['completion_rate'] = round((stats['completed'] / stats['total']) * 100, 1)
    else:
        stats['completion_rate'] = 0

    html_content = render_to_string('reports/client_report.html', {
        'client': client,
        'obligations': obligations,
        'stats': stats,
        'generated_at': timezone.now()
    })

    try:
        result = BytesIO()
        pisa_status = pisa.CreatePDF(html_content, dest=result)
        if pisa_status.err:
            return HttpResponse("Error generating PDF", status=500)
        pdf = result.getvalue()
        response = HttpResponse(pdf, content_type='application/pdf')
        safe_name = client.afm.replace(' ', '_')
        response['Content-Disposition'] = f'filename="client_{safe_name}.pdf"'
        logger.info(f"PDF report generated for client {client.afm} by {request.user.username}")
        return response
    except Exception as e:
        logger.error(f"Error generating PDF for client {client_id}: {e}", exc_info=True)
        return HttpResponse(f'Σφάλμα δημιουργίας PDF: {str(e)}', status=500)


@staff_member_required
def monthly_report_pdf(request, year, month):
    """
    Generate PDF report for a specific month.
    Includes all obligations for that period.
    """
    from io import BytesIO
    try:
        from xhtml2pdf import pisa
    except ImportError:
        return HttpResponse(
            'xhtml2pdf δεν είναι εγκατεστημένο. Εγκαταστήστε το με: pip install xhtml2pdf',
            status=500
        )

    # Get all obligations for stats calculation (before any slicing)
    all_obligations = accessible_obligations(request.user).filter(
        year=year,
        month=month
    )

    # Calculate statistics from base queryset
    stats = {
        'total': all_obligations.count(),
        'completed': all_obligations.filter(status='completed').count(),
        'pending': all_obligations.filter(status='pending').count(),
        'overdue': all_obligations.filter(status='overdue').count(),
    }

    # Completion rate
    if stats['total'] > 0:
        stats['completion_rate'] = round((stats['completed'] / stats['total']) * 100, 1)
    else:
        stats['completion_rate'] = 0

    # Group by status (from base queryset)
    by_status = {
        'pending': all_obligations.filter(status='pending').select_related('client', 'obligation_type'),
        'completed': all_obligations.filter(status='completed').select_related('client', 'obligation_type'),
        'overdue': all_obligations.filter(status='overdue').select_related('client', 'obligation_type'),
    }

    # Get obligations for the table
    obligations = all_obligations.select_related('client', 'obligation_type').order_by('deadline', 'client__eponimia')

    # Month name in Greek (using centralized constants)
    month_name = GREEK_MONTHS_FULL.get(month, str(month))

    html_content = render_to_string('reports/monthly_report.html', {
        'year': year,
        'month': month,
        'month_name': month_name,
        'obligations': obligations,
        'stats': stats,
        'by_status': by_status,
        'generated_at': timezone.now()
    })

    try:
        result = BytesIO()
        pisa_status = pisa.CreatePDF(html_content, dest=result)
        if pisa_status.err:
            return HttpResponse("Error generating PDF", status=500)
        pdf = result.getvalue()
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'filename="report_{year}_{month:02d}.pdf"'
        logger.info(f"Monthly PDF report generated for {month}/{year} by {request.user.username}")
        return response
    except Exception as e:
        logger.error(f"Error generating monthly PDF for {month}/{year}: {e}", exc_info=True)
        return HttpResponse(f'Σφάλμα δημιουργίας PDF: {str(e)}', status=500)
