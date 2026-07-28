"""
Tests for Task forms validation
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from tasks.models import Task, Project, Memo, TaskStage
from tasks.forms import TaskForm, ProjectForm, MemoForm
from common.utils.helpers import get_today


class TaskFormTest(TestCase):
    """Test TaskForm validation"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.stage = TaskStage.objects.create(name='In progress', active=True, default=True)

    def test_valid_task_form(self):
        """Test form with valid data"""
        form_data = {
            'name': 'Test Task',
            'description': 'Test description',
            'responsible': [self.user.id],
            'due_date': (get_today() + timedelta(days=7)).isoformat(),
            'stage': self.stage.id,
            'creation_date': get_today().isoformat(),
            'priority': '2',
            'next_step': 'next step',
            'next_step_date': (get_today() + timedelta(days=1)).isoformat(),
            'token': 'testtoken',
        }

        form = TaskForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_task_form_requires_name(self):
        """Test that name is required"""
        form_data = {
            'name': '',
            'responsible': [self.user.id],
        }

        form = TaskForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_task_form_requires_responsible(self):
        """Test that responsible is required"""
        form_data = {
            'name': 'Test Task',
            'responsible': [],
        }

        form = TaskForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('responsible', form.errors)

    def test_task_form_rejects_past_due_date(self):
        """Test that past due dates are rejected"""
        form_data = {
            'name': 'Test Task',
            'responsible': [self.user.id],
            'due_date': (get_today() - timedelta(days=1)).isoformat(),
        }

        form = TaskForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('due_date', form.errors)
        self.assertIn('past', str(form.errors['due_date']).lower())

    def test_task_form_accepts_future_due_date(self):
        """Test that future due dates are accepted"""
        form_data = {
            'name': 'Test Task',
            'responsible': [self.user.id],
            'due_date': (get_today() + timedelta(days=5)).isoformat(),
            'stage': self.stage.id,
            'creation_date': get_today().isoformat(),
            'priority': '2',
            'next_step': 'next step',
            'next_step_date': (get_today() + timedelta(days=1)).isoformat(),
            'token': 'testtoken',
        }

        form = TaskForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_subtask_must_have_single_responsible(self):
        """Test that subtasks can only have one responsible person"""
        # Create parent task
        parent_task = Task.objects.create(
            name="Parent Task",
            stage=self.stage
        )
        parent_task.responsible.add(self.user)

        # Create second user
        user2 = User.objects.create_user(
            username='user2',
            password='pass2'
        )

        # Try to create subtask with multiple responsibles
        form_data = {
            'name': 'Subtask',
            'task': parent_task.id,
            'responsible': [self.user.id, user2.id],  # Multiple responsibles
        }

        form = TaskForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('responsible', form.errors)

    def test_subtask_with_single_responsible_is_valid(self):
        """Test that subtasks with single responsible are valid"""
        # Create parent task
        parent_task = Task.objects.create(
            name="Parent Task",
            stage=self.stage
        )
        parent_task.responsible.add(self.user)

        form_data = {
            'name': 'Subtask',
            'task': parent_task.id,
            'responsible': [self.user.id],  # Single responsible
            'stage': self.stage.id,
            'creation_date': get_today().isoformat(),
            'priority': '2',
            'next_step': 'next step',
            'next_step_date': (get_today() + timedelta(days=1)).isoformat(),
            'token': 'testtoken',
        }

        form = TaskForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_task_form_next_step_date_validation(self):
        """Test next_step_date validation"""
        # Past next_step_date should be rejected
        form_data = {
            'name': 'Test Task',
            'responsible': [self.user.id],
            'next_step_date': (get_today() - timedelta(days=1)).isoformat(),
            'remind_me': True,
        }

        form = TaskForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('next_step_date', form.errors)


class ProjectFormTest(TestCase):
    """Test ProjectForm validation"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_valid_project_form(self):
        """Test form with valid data"""
        form_data = {
            'name': 'Test Project',
            'description': 'Project description',
            'responsible': [self.user.id],
            'creation_date': get_today().isoformat(),
            'priority': '2',
            'next_step': 'next step',
            'next_step_date': (get_today() + timedelta(days=1)).isoformat(),
            'token': 'testtoken',
        }

        form = ProjectForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_project_form_requires_name(self):
        """Test that name is required"""
        form_data = {
            'name': '',
            'responsible': [self.user.id],
        }

        form = ProjectForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_project_form_multiple_responsibles_allowed(self):
        """Test that projects can have multiple responsibles"""
        user2 = User.objects.create_user(
            username='user2',
            password='pass2'
        )

        form_data = {
            'name': 'Big Project',
            'description': 'Large project',
            'responsible': [self.user.id, user2.id],
            'creation_date': get_today().isoformat(),
            'priority': '2',
            'next_step': 'next step',
            'next_step_date': (get_today() + timedelta(days=1)).isoformat(),
            'token': 'testtoken',
        }

        form = ProjectForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)


class MemoFormTest(TestCase):
    """Test MemoForm validation"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='memouser',
            password='testpass123'
        )

    def test_valid_memo_form(self):
        """Test form with valid data"""
        form_data = {
            'name': 'Test Memo',
            'description': 'Memo description',
            'to': self.user.id,
            'stage': Memo.PENDING,
            'creation_date': get_today().isoformat(),
        }

        form = MemoForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_memo_form_with_minimal_data(self):
        """Test memo with minimal required data"""
        form_data = {
            'name': 'Simple Memo',
            'to': self.user.id,
            'stage': Memo.PENDING,
            'creation_date': get_today().isoformat(),
        }

        form = MemoForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)


class FormWidgetsTest(TestCase):
    """Test form widget configuration"""

    def test_task_form_widgets(self):
        """Test TaskForm has proper widgets configured"""
        form = TaskForm()

        # Check textarea widgets
        self.assertEqual(
            form.fields['name'].widget.__class__.__name__,
            'Textarea'
        )
        self.assertEqual(
            form.fields['description'].widget.__class__.__name__,
            'Textarea'
        )

    def test_project_form_widgets(self):
        """Test ProjectForm has proper widgets configured"""
        form = ProjectForm()

        # Check textarea widgets
        self.assertEqual(
            form.fields['name'].widget.__class__.__name__,
            'Textarea'
        )

    def test_memo_form_widgets(self):
        """Test MemoForm has proper widgets configured"""
        form = MemoForm()

        # Check textarea widgets
        self.assertEqual(
            form.fields['name'].widget.__class__.__name__,
            'Textarea'
        )
        self.assertEqual(
            form.fields['description'].widget.__class__.__name__,
            'Textarea'
        )
