"""
Tests for Calendar View functionality
Tests for: calendar_view, calendar_events_api
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta
import json

from accounting.models import (
    ClientProfile, ObligationType, MonthlyObligation
)


class CalendarViewTestCase(TestCase):
    """Test cases for calendar view"""

    def setUp(self):
        """Set up test data"""
        # Create a staff user
        self.user = User.objects.create_user(
            username='testadmin',
            email='admin@test.com',
            password='testpass123',
            is_staff=True
        )
        # Γύρος 13: το ημερολόγιο απαιτεί πλέον view_monthlyobligation
        from django.contrib.auth.models import Permission
        self.user.user_permissions.add(Permission.objects.get(
            codename='view_monthlyobligation',
            content_type__app_label='accounting'))
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

        # Create a client profile
        self.client_profile = ClientProfile.objects.create(
            afm="123456789",
            eponimia="Test Company AE",
            eidos_ipoxreou="company",
            is_active=True
        )

        # Create obligation type
        self.obligation_type = ObligationType.objects.create(
            name="ΦΠΑ",
            code="VAT",
            frequency="monthly",
            is_active=True
        )

        # Create test obligations
        today = timezone.now().date()
        self.pending_obligation = MonthlyObligation.objects.create(
            client=self.client_profile,
            obligation_type=self.obligation_type,
            year=today.year,
            month=today.month,
            deadline=today + timedelta(days=5),
            status='pending'
        )

        self.completed_obligation = MonthlyObligation.objects.create(
            client=self.client_profile,
            obligation_type=self.obligation_type,
            year=today.year,
            month=today.month - 1 if today.month > 1 else 12,
            deadline=today - timedelta(days=10),
            status='completed',
            completed_date=today - timedelta(days=5)
        )

        # Διαφορετικός τύπος ώστε να μην παραβιάζεται το unique constraint
        # (client, obligation_type, year, month)
        self.overdue_obligation_type = ObligationType.objects.create(
            name="ΑΠΔ",
            code="APD",
            frequency="monthly",
            is_active=True
        )
        self.overdue_obligation = MonthlyObligation.objects.create(
            client=self.client_profile,
            obligation_type=self.overdue_obligation_type,
            year=today.year,
            month=today.month,
            deadline=today - timedelta(days=3),
            status='pending'  # Still pending but past deadline
        )

    def test_calendar_view_loads(self):
        """Test that calendar view loads successfully"""
        response = self.client.get(reverse('accounting:calendar'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ημερολόγιο Υποχρεώσεων')
        self.assertTemplateUsed(response, 'accounting/calendar.html')

    def test_calendar_view_requires_login(self):
        """Test that calendar view requires authentication"""
        self.client.logout()
        response = self.client.get(reverse('accounting:calendar'))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_calendar_view_requires_staff(self):
        """Test that calendar view requires staff status"""
        # Create non-staff user
        regular_user = User.objects.create_user(
            username='regularuser',
            password='testpass123',
            is_staff=False
        )
        self.client.login(username='regularuser', password='testpass123')
        response = self.client.get(reverse('accounting:calendar'))
        # Should redirect to admin login
        self.assertEqual(response.status_code, 302)

    def test_calendar_view_contains_filters(self):
        """Test that calendar view contains filter dropdowns"""
        response = self.client.get(reverse('accounting:calendar'))
        self.assertContains(response, 'filter-client')
        self.assertContains(response, 'filter-type')
        self.assertContains(response, 'filter-status')

    def test_calendar_view_contains_statistics(self):
        """Test that calendar view contains statistics"""
        response = self.client.get(reverse('accounting:calendar'))
        self.assertContains(response, 'Εκκρεμείς')
        self.assertContains(response, 'Εκπρόθεσμες')
        self.assertContains(response, 'Ολοκληρώθηκαν')

    def test_calendar_view_contains_legend(self):
        """Test that calendar view contains legend"""
        response = self.client.get(reverse('accounting:calendar'))
        self.assertContains(response, 'calendar-legend')

    def test_calendar_view_context_has_clients(self):
        """Test that context contains clients"""
        response = self.client.get(reverse('accounting:calendar'))
        self.assertIn('clients', response.context)
        self.assertIn(self.client_profile, response.context['clients'])

    def test_calendar_view_context_has_obligation_types(self):
        """Test that context contains obligation types"""
        response = self.client.get(reverse('accounting:calendar'))
        self.assertIn('obligation_types', response.context)
        self.assertIn(self.obligation_type, response.context['obligation_types'])


class CalendarEventsAPITestCase(TestCase):
    """Test cases for calendar events API endpoint"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testadmin',
            email='admin@test.com',
            password='testpass123',
            is_staff=True
        )
        # Γύρος 13: το ημερολόγιο απαιτεί πλέον view_monthlyobligation
        from django.contrib.auth.models import Permission
        self.user.user_permissions.add(Permission.objects.get(
            codename='view_monthlyobligation',
            content_type__app_label='accounting'))
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

        # Create client profiles
        self.client_profile1 = ClientProfile.objects.create(
            afm="111111111",
            eponimia="Company Alpha",
            eidos_ipoxreou="company",
            is_active=True
        )
        self.client_profile2 = ClientProfile.objects.create(
            afm="222222222",
            eponimia="Company Beta",
            eidos_ipoxreou="company",
            is_active=True
        )

        # Create obligation types
        self.vat_type = ObligationType.objects.create(
            name="ΦΠΑ",
            code="VAT",
            frequency="monthly",
            is_active=True
        )
        self.apd_type = ObligationType.objects.create(
            name="ΑΠΔ",
            code="APD",
            frequency="monthly",
            is_active=True
        )

        # Create obligations
        today = timezone.now().date()
        self.obligation1 = MonthlyObligation.objects.create(
            client=self.client_profile1,
            obligation_type=self.vat_type,
            year=today.year,
            month=today.month,
            deadline=today + timedelta(days=5),
            status='pending'
        )
        self.obligation2 = MonthlyObligation.objects.create(
            client=self.client_profile2,
            obligation_type=self.apd_type,
            year=today.year,
            month=today.month,
            deadline=today + timedelta(days=10),
            status='completed'
        )
        self.obligation3 = MonthlyObligation.objects.create(
            client=self.client_profile1,
            obligation_type=self.apd_type,
            year=today.year,
            month=today.month,
            deadline=today - timedelta(days=2),
            status='pending'  # Overdue
        )

    def test_api_returns_json(self):
        """Test that API returns valid JSON"""
        today = timezone.now().date()
        start = today.replace(day=1)
        end = start + timedelta(days=31)

        response = self.client.get(
            reverse('accounting:calendar_events_api'),
            {
                'start': start.isoformat(),
                'end': end.isoformat()
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

        data = json.loads(response.content)
        self.assertIn('events', data)

    def test_api_requires_login(self):
        """Test that API requires authentication"""
        self.client.logout()
        response = self.client.get(reverse('accounting:calendar_events_api'))
        self.assertEqual(response.status_code, 302)

    def test_api_returns_events_in_date_range(self):
        """Test that API returns only events in specified date range"""
        today = timezone.now().date()
        start = today.replace(day=1)
        end = start + timedelta(days=31)

        response = self.client.get(
            reverse('accounting:calendar_events_api'),
            {
                'start': start.isoformat(),
                'end': end.isoformat()
            }
        )
        data = json.loads(response.content)

        # Should return events for this month
        self.assertGreater(len(data['events']), 0)

    def test_api_event_structure(self):
        """Test that events have correct structure"""
        today = timezone.now().date()
        start = today.replace(day=1)
        end = start + timedelta(days=31)

        response = self.client.get(
            reverse('accounting:calendar_events_api'),
            {
                'start': start.isoformat(),
                'end': end.isoformat()
            }
        )
        data = json.loads(response.content)

        if data['events']:
            event = data['events'][0]
            self.assertIn('id', event)
            self.assertIn('title', event)
            self.assertIn('start', event)
            self.assertIn('color', event)
            self.assertIn('extendedProps', event)
            self.assertIn('status', event['extendedProps'])
            self.assertIn('client_name', event['extendedProps'])
            self.assertIn('obligation_type', event['extendedProps'])

    def test_api_filter_by_client(self):
        """Test filtering events by client"""
        today = timezone.now().date()
        start = today.replace(day=1)
        end = start + timedelta(days=31)

        response = self.client.get(
            reverse('accounting:calendar_events_api'),
            {
                'start': start.isoformat(),
                'end': end.isoformat(),
                'client': str(self.client_profile1.id)
            }
        )
        data = json.loads(response.content)

        # All events should be for client_profile1
        for event in data['events']:
            self.assertEqual(
                event['extendedProps']['client_id'],
                self.client_profile1.id
            )

    def test_api_filter_by_type(self):
        """Test filtering events by obligation type"""
        today = timezone.now().date()
        start = today.replace(day=1)
        end = start + timedelta(days=31)

        response = self.client.get(
            reverse('accounting:calendar_events_api'),
            {
                'start': start.isoformat(),
                'end': end.isoformat(),
                'type': str(self.vat_type.id)
            }
        )
        data = json.loads(response.content)

        # All events should be VAT type
        for event in data['events']:
            self.assertEqual(
                event['extendedProps']['obligation_type'],
                'ΦΠΑ'
            )

    def test_api_filter_by_status_pending(self):
        """Test filtering events by pending status"""
        today = timezone.now().date()
        start = today.replace(day=1)
        end = start + timedelta(days=31)

        response = self.client.get(
            reverse('accounting:calendar_events_api'),
            {
                'start': start.isoformat(),
                'end': end.isoformat(),
                'status': 'pending'
            }
        )
        data = json.loads(response.content)

        # All events should be pending (not overdue ones since filter is pending status)
        for event in data['events']:
            self.assertIn(
                event['extendedProps']['status'],
                ['pending', 'overdue']  # pending may become overdue based on deadline
            )

    def test_api_filter_by_status_completed(self):
        """Test filtering events by completed status"""
        today = timezone.now().date()
        start = today.replace(day=1)
        end = start + timedelta(days=31)

        response = self.client.get(
            reverse('accounting:calendar_events_api'),
            {
                'start': start.isoformat(),
                'end': end.isoformat(),
                'status': 'completed'
            }
        )
        data = json.loads(response.content)

        # All events should be completed
        for event in data['events']:
            self.assertEqual(event['extendedProps']['status'], 'completed')

    def test_api_colors_by_status(self):
        """Test that events have correct colors based on status"""
        today = timezone.now().date()
        start = today.replace(day=1)
        end = start + timedelta(days=31)

        response = self.client.get(
            reverse('accounting:calendar_events_api'),
            {
                'start': start.isoformat(),
                'end': end.isoformat()
            }
        )
        data = json.loads(response.content)

        expected_colors = {
            'pending': '#f59e0b',
            'completed': '#22c55e',
            'overdue': '#ef4444'
        }

        for event in data['events']:
            status = event['extendedProps']['status']
            if status in expected_colors:
                self.assertEqual(event['color'], expected_colors[status])

    def test_api_overdue_detection(self):
        """Test that pending obligations past deadline are marked as overdue"""
        today = timezone.now().date()
        start = today - timedelta(days=10)
        end = today + timedelta(days=10)

        response = self.client.get(
            reverse('accounting:calendar_events_api'),
            {
                'start': start.isoformat(),
                'end': end.isoformat()
            }
        )
        data = json.loads(response.content)

        # Find obligation3 which should be overdue
        overdue_events = [
            e for e in data['events']
            if e['id'] == self.obligation3.id
        ]

        if overdue_events:
            self.assertEqual(overdue_events[0]['extendedProps']['status'], 'overdue')
            self.assertEqual(overdue_events[0]['color'], '#ef4444')


class CalendarURLTestCase(TestCase):
    """Test URL configuration for calendar"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testadmin',
            password='testpass123',
            is_staff=True
        )
        self.client = Client()
        self.client.login(username='testadmin', password='testpass123')

    def test_calendar_url_resolves(self):
        """Test that calendar URL resolves correctly"""
        url = reverse('accounting:calendar')
        self.assertEqual(url, '/accounting/calendar/')

    def test_calendar_api_url_resolves(self):
        """Test that calendar API URL resolves correctly"""
        url = reverse('accounting:calendar_events_api')
        self.assertEqual(url, '/accounting/api/calendar-events/')
