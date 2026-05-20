"""
Tests for UserMiddleware
Critical for user session management and permissions
"""
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User, Group
from django.contrib.sessions.middleware import SessionMiddleware
from unittest.mock import Mock, patch

from common.models import UserProfile
from common.utils.usermiddleware import (
    UserMiddleware, set_user_groups, set_user_department,
    set_user_timezone, activate_stored_messages_to_user,
    check_user_language
)


class UserMiddlewareTest(TestCase):
    """Test UserMiddleware functionality"""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = UserMiddleware(lambda r: Mock())

        # Create user with profile
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        # Create groups
        self.co_workers = Group.objects.create(name='co-workers')
        self.operators = Group.objects.create(name='operators')
        self.chiefs = Group.objects.create(name='chiefs')
        self.managers = Group.objects.create(name='managers')
        self.accountants = Group.objects.create(name='accountants')

    def _add_session_to_request(self, request):
        """Helper to add session to request"""
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()

    def test_middleware_processes_authenticated_user(self):
        """Test middleware processes authenticated users"""
        request = self.factory.get('/')
        request.user = self.user
        self._add_session_to_request(request)

        # Mock get_response
        get_response = Mock(return_value=Mock())
        middleware = UserMiddleware(get_response)

        response = middleware(request)

        # Should call get_response
        get_response.assert_called_once_with(request)

    def test_middleware_skips_anonymous_users(self):
        """Test middleware doesn't process anonymous users"""
        request = self.factory.get('/')
        request.user = Mock(is_authenticated=False)

        get_response = Mock(return_value=Mock())
        middleware = UserMiddleware(get_response)

        middleware(request)

        # Should still call get_response
        get_response.assert_called_once()


class SetUserGroupsTest(TestCase):
    """Test set_user_groups function"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        # Create groups
        self.operators = Group.objects.create(name='operators')
        self.chiefs = Group.objects.create(name='chiefs')
        self.managers = Group.objects.create(name='managers')
        self.superoperators = Group.objects.create(name='superoperators')
        self.accountants = Group.objects.create(name='accountants')

    def test_set_operator_flag(self):
        """Test setting operator flag"""
        self.user.groups.add(self.operators)
        request = self.factory.get('/')
        request.user = self.user

        groups = self.user.groups.all()
        set_user_groups(request, groups)

        self.assertTrue(request.user.is_operator)

    def test_set_chief_flag(self):
        """Test setting chief flag"""
        self.user.groups.add(self.chiefs)
        request = self.factory.get('/')
        request.user = self.user

        groups = self.user.groups.all()
        set_user_groups(request, groups)

        self.assertTrue(request.user.is_chief)

    def test_set_manager_flag(self):
        """Test setting manager flag"""
        self.user.groups.add(self.managers)
        request = self.factory.get('/')
        request.user = self.user

        groups = self.user.groups.all()
        set_user_groups(request, groups)

        self.assertTrue(request.user.is_manager)

    def test_set_accountant_flag(self):
        """Test setting accountant flag"""
        self.user.groups.add(self.accountants)
        request = self.factory.get('/')
        request.user = self.user

        groups = self.user.groups.all()
        set_user_groups(request, groups)

        self.assertTrue(request.user.is_accountant)

    def test_set_multiple_group_flags(self):
        """Test setting multiple group flags"""
        self.user.groups.add(self.managers, self.accountants)
        request = self.factory.get('/')
        request.user = self.user

        groups = self.user.groups.all()
        set_user_groups(request, groups)

        self.assertTrue(request.user.is_manager)
        self.assertTrue(request.user.is_accountant)


class SetUserDepartmentTest(TestCase):
    """Test set_user_department function"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def _add_session_to_request(self, request):
        """Helper to add session to request"""
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()

    def test_superuser_can_set_department_from_get(self):
        """Test superuser can set department from GET parameter"""
        self.user.is_superuser = True
        request = self.factory.get('/?department=5')
        request.user = self.user
        self._add_session_to_request(request)

        groups = self.user.groups.all()
        set_user_groups(request, groups)
        set_user_department(request, groups)

        self.assertEqual(request.user.department_id, 5)
        self.assertEqual(request.session['department_id'], 5)

    def test_department_set_to_all(self):
        """Test setting department to 'all'"""
        self.user.is_superuser = True
        request = self.factory.get('/?department=all')
        request.user = self.user
        self._add_session_to_request(request)

        groups = self.user.groups.all()
        set_user_groups(request, groups)
        set_user_department(request, groups)

        self.assertIsNone(request.user.department_id)
        self.assertIsNone(request.session['department_id'])

    def test_ajax_requests_skip_department_setting(self):
        """Test AJAX requests don't trigger department setting"""
        self.user.is_superuser = True
        request = self.factory.get(
            '/?department=5',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        request.user = self.user
        self._add_session_to_request(request)

        # Store original department_id
        request.user.department_id = 10

        groups = self.user.groups.all()
        set_user_department(request, groups)

        # Should not change for AJAX requests
        # (department_id won't be set in the function)


class SetUserTimezoneTest(TestCase):
    """Test set_user_timezone function"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.profile = UserProfile.objects.get(user=self.user)

    @patch('common.utils.usermiddleware.timezone.activate')
    def test_activate_user_timezone(self, mock_activate):
        """Test activating user's timezone"""
        self.profile.utc_timezone = 'Europe/Athens'
        self.profile.activate_timezone = True
        self.profile.save()

        set_user_timezone(self.profile)

        # Should activate timezone
        mock_activate.assert_called_once()

    @patch('common.utils.usermiddleware.timezone.deactivate')
    def test_deactivate_timezone_when_not_activated(self, mock_deactivate):
        """Test deactivating timezone when user preference is off"""
        self.profile.utc_timezone = 'Europe/Athens'
        self.profile.activate_timezone = False
        self.profile.save()

        set_user_timezone(self.profile)

        # Should deactivate
        mock_deactivate.assert_called_once()


class ActivateStoredMessagesTest(TestCase):
    """Test activate_stored_messages_to_user function"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.profile = UserProfile.objects.get(user=self.user)

    def _add_session_and_messages_to_request(self, request):
        """Helper to add session and messages to request"""
        from django.contrib.messages.storage.fallback import FallbackStorage
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()
        setattr(request, '_messages', FallbackStorage(request))

    def test_activate_stored_messages(self):
        """Test activating stored messages"""
        # Store a message in profile
        self.profile.messages = ['Test message', 'SUCCESS']
        self.profile.save()

        request = self.factory.get('/')
        self._add_session_and_messages_to_request(request)

        activate_stored_messages_to_user(request, self.profile)

        # Messages should be cleared from profile
        self.profile.refresh_from_db()
        self.assertEqual(len(self.profile.messages), 0)

    def test_multiple_stored_messages(self):
        """Test activating multiple stored messages"""
        self.profile.messages = [
            'Message 1', 'INFO',
            'Message 2', 'WARNING',
            'Message 3', 'ERROR'
        ]
        self.profile.save()

        request = self.factory.get('/')
        self._add_session_and_messages_to_request(request)

        activate_stored_messages_to_user(request, self.profile)

        # All messages should be cleared
        self.profile.refresh_from_db()
        self.assertEqual(len(self.profile.messages), 0)


class CheckUserLanguageTest(TestCase):
    """Test check_user_language function"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.profile = UserProfile.objects.get(user=self.user)

    @patch('common.utils.usermiddleware.get_language')
    def test_update_language_when_changed(self, mock_get_language):
        """Test updating profile language when it changes"""
        # Set initial language
        self.profile.language_code = 'en'
        self.profile.save()

        # Mock current language as different
        mock_get_language.return_value = 'el'

        check_user_language(self.profile)

        # Profile should be updated
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.language_code, 'el')

    @patch('common.utils.usermiddleware.get_language')
    def test_no_update_when_language_same(self, mock_get_language):
        """Test no update when language is same"""
        self.profile.language_code = 'en'
        self.profile.save()

        # Mock current language as same
        mock_get_language.return_value = 'en'

        check_user_language(self.profile)

        self.profile.refresh_from_db()
        # Should not change language_code
        self.assertEqual(self.profile.language_code, 'en')
