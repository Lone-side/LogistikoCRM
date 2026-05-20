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
        from accounting.models import get_client_folder
        from datetime import datetime
        base_path = os.path.join(settings.MEDIA_ROOT, get_client_folder(client))

        # Permanent folder categories (under 00_ΜΟΝΙΜΑ/)
        permanent_categories = ['contracts', 'registration', 'licenses']
        for category in permanent_categories:
            category_path = os.path.join(base_path, '00_ΜΟΝΙΜΑ', category)
            self.assertTrue(
                os.path.exists(category_path),
                f"Permanent folder '00_ΜΟΝΙΜΑ/{category}' was not created"
            )

        # Monthly categories (under {year}/{month}/)
        current_year = datetime.now().year
        monthly_categories = ['vat', 'myf', 'payroll', 'general']
        month_path = os.path.join(base_path, str(current_year), '01')
        for category in monthly_categories:
            category_path = os.path.join(month_path, category)
            self.assertTrue(
                os.path.exists(category_path),
                f"Monthly folder '{current_year}/01/{category}' was not created"
            )

        # Check INFO.txt was created
        info_file = os.path.join(base_path, 'INFO.txt')
        self.assertTrue(os.path.exists(info_file))

        # Check INFO.txt content
        with open(info_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn(client.eponimia, content)
            self.assertIn(client.afm, content)
