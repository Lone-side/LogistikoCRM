"""
Tests for signal handlers
"""
from django.test import TestCase
from django.contrib.auth.models import User, Group

from common.models import UserProfile


class UserCreationSignalTest(TestCase):
    """Test user creation signal handler"""

    def setUp(self):
        # Create co-workers group (required by signal)
        self.co_workers_group = Group.objects.create(name='co-workers')

    def test_user_profile_created_on_user_creation(self):
        """Test that UserProfile is auto-created when user is created"""
        # Create user
        user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )

        # Check that UserProfile was auto-created
        self.assertTrue(
            UserProfile.objects.filter(user=user).exists()
        )

        user_profile = UserProfile.objects.get(user=user)
        self.assertEqual(user_profile.user, user)

    def test_user_added_to_co_workers_group(self):
        """Test that new users are automatically added to co-workers group"""
        # Create user
        user = User.objects.create_user(
            username='newuser',
            password='testpass123'
        )

        # Check that user is in co-workers group
        self.assertIn(
            self.co_workers_group,
            user.groups.all()
        )

    def test_signal_only_fires_on_creation(self):
        """Test that signal only fires when user is created, not updated"""
        # Create user
        user = User.objects.create_user(
            username='testuser2',
            password='testpass123'
        )

        # Count initial profiles
        initial_profile_count = UserProfile.objects.count()

        # Update user
        user.email = 'updated@example.com'
        user.save()

        # Profile count should not change
        self.assertEqual(
            UserProfile.objects.count(),
            initial_profile_count
        )

    def test_multiple_users_creation(self):
        """Test signal works for multiple users"""
        users_data = [
            ('user1', 'pass1'),
            ('user2', 'pass2'),
            ('user3', 'pass3'),
        ]

        for username, password in users_data:
            user = User.objects.create_user(
                username=username,
                password=password
            )

            # Each should have a profile
            self.assertTrue(
                UserProfile.objects.filter(user=user).exists()
            )

            # Each should be in co-workers group
            self.assertIn(
                self.co_workers_group,
                user.groups.all()
            )


class ClientProfileFolderCreationSignalTest(TestCase):
    """Test client profile folder creation signal"""

    def test_client_folders_created_on_profile_creation(self):
        """Test that folders are created when ClientProfile is created"""
        from accounting.models import ClientProfile
        from django.conf import settings
        import os

        client = ClientProfile.objects.create(
            afm="123456789",
            eponimia="Test Client",
            eidos_ipoxreou="company"
        )

        # Check that folder structure was created
        # Η δομή είναι ιεραρχική: 00_ΜΟΝΙΜΑ/, {έτος}/{μήνας}/{κατηγορία}/
        # βάσει FilingSystemSettings
        from datetime import datetime
        from accounting.models import get_client_folder
        from settings.models import FilingSystemSettings

        filing_settings = FilingSystemSettings.get_settings()
        base_path = os.path.join(
            filing_settings.get_archive_root(), get_client_folder(client)
        )

        # Μόνιμος φάκελος με τις κατηγορίες του
        permanent_path = os.path.join(
            base_path, filing_settings.permanent_folder_name
        )
        for category in filing_settings.get_permanent_folder_categories():
            self.assertTrue(
                os.path.exists(os.path.join(permanent_path, category)),
                f"Permanent category folder '{category}' was not created"
            )

        # Μηνιαίοι φάκελοι τρέχοντος έτους
        year_path = os.path.join(base_path, str(datetime.now().year))
        month_name = (
            filing_settings.get_month_folder_name(1)
            if filing_settings.use_greek_month_names else '01'
        )
        for category in filing_settings.get_monthly_folder_categories():
            self.assertTrue(
                os.path.exists(os.path.join(year_path, month_name, category)),
                f"Monthly category folder '{category}' was not created"
            )

        # Check INFO.txt was created
        info_file = os.path.join(base_path, 'INFO.txt')
        self.assertTrue(os.path.exists(info_file))

        # Check INFO.txt content
        with open(info_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn(client.eponimia, content)
            self.assertIn(client.afm, content)
