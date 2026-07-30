# mydata/urls.py
"""
URL Configuration για myDATA module.

API Endpoints:
    /api/mydata/credentials/          - MyDataCredentials CRUD
    /api/mydata/credentials/{id}/verify/  - Verify credentials
    /api/mydata/credentials/{id}/sync/    - Trigger sync

    /api/mydata/records/              - VATRecord list
    /api/mydata/records/{id}/         - VATRecord detail
    /api/mydata/records/summary/      - Period summary
    /api/mydata/records/by_category/  - Category breakdown

    /api/mydata/logs/                 - VATSyncLog list
    /api/mydata/logs/{id}/            - VATSyncLog detail

    /api/mydata/periods/              - VATPeriodResult CRUD
    /api/mydata/periods/{id}/calculate/  - Υπολογισμός ΦΠΑ
    /api/mydata/periods/{id}/lock/       - Κλείδωμα περιόδου
    /api/mydata/periods/{id}/unlock/     - Ξεκλείδωμα περιόδου
    /api/mydata/periods/{id}/set_credit/ - Ορισμός πιστωτικού

    /api/mydata/dashboard/            - Dashboard overview
    /api/mydata/client/{afm}/         - Client detail
    /api/mydata/trend/                - Monthly trend data
    /api/mydata/calculator/           - Quick VAT period calculator
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    MyDataCredentialsViewSet,
    VATRecordViewSet,
    VATSyncLogViewSet,
    MyDataDashboardView,
    ClientVATDetailView,
    MonthlyTrendView,
    VATPeriodResultViewSet,
    VATPeriodCalculatorView,
    InvoiceViewSet,
)

app_name = 'mydata'

# Router for ViewSets
router = DefaultRouter()
router.register(r'credentials', MyDataCredentialsViewSet, basename='credentials')
router.register(r'records', VATRecordViewSet, basename='records')
router.register(r'logs', VATSyncLogViewSet, basename='logs')
router.register(r'periods', VATPeriodResultViewSet, basename='periods')
router.register(r'invoices', InvoiceViewSet, basename='invoices')

# URL patterns
urlpatterns = [
    # ViewSet routes
    path('', include(router.urls)),

    # Custom API views
    path('dashboard/', MyDataDashboardView.as_view(), name='dashboard'),
    path('client/<str:afm>/', ClientVATDetailView.as_view(), name='client-detail'),
    path('trend/', MonthlyTrendView.as_view(), name='trend'),
    path('calculator/', VATPeriodCalculatorView.as_view(), name='calculator'),
]
