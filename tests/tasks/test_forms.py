"""
Tests for Task forms validation
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from common.utils.helpers import get_today
from tasks.forms import MemoForm, ProjectForm, TaskForm
from tasks.models import Memo, Project, Task, TaskStage


class TaskFormTest(TestCase):
    """Test TaskForm validation"""
    fixtures = ('taskstage.json',)

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.stage = TaskStage.objects.filter(default=True).first()

    def _valid_task_data(self, **overrides):
        data = {
            'name': 'Test Task',
            'description': 'Test description',
            'responsible': [self.user.id],
            'due_date': (get_today() + timedelta(days=7)).isoformat(),
            'next_step': 'Review',
            'next_step_date': (get_today() + timedelta(days=3)).isoformat(),
            'priority': '2',
            'stage': self.stage.pk,
        }
        data.update(overrides)
        return data

    def test_valid_task_form(self):
        """Test form with valid data"""
        form = TaskForm(data=self._valid_task_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_task_form_requires_name(self):
        """Test that name is required"""
        form = TaskForm(data={'name': '', 'responsible': [self.user.id]})
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_task_form_requires_responsible(self):
        """Test that responsible is required"""
        form = TaskForm(data={'name': 'Test Task', 'responsible': []})
        self.assertFalse(form.is_valid())
        self.assertIn('responsible', form.errors)

    def test_task_form_rejects_past_due_date(self):
        """Test that past due dates are rejected"""
        data = self._valid_task_data(due_date=(get_today() - timedelta(days=1)).isoformat())
        form = TaskForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('due_date', form.errors)

    def test_task_form_accepts_future_due_date(self):
        """Test that future due dates are accepted"""
        form = TaskForm(data=self._valid_task_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_subtask_must_have_single_responsible(self):
        """Test that subtasks can only have one responsible person"""
        parent_task = Task.objects.create(name="Parent Task", stage=self.stage)
        parent_task.responsible.add(self.user)

        user2 = User.objects.create_user(username='user2', password='pass2')
        data = self._valid_task_data(
            name='Subtask',
            task=parent_task.id,
            responsible=[self.user.id, user2.id],
        )
        form = TaskForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('responsible', form.errors)

    def test_subtask_with_single_responsible_is_valid(self):
        """Test that subtasks with single responsible are valid"""
        parent_task = Task.objects.create(name="Parent Task", stage=self.stage)
        parent_task.responsible.add(self.user)

        data = self._valid_task_data(name='Subtask', task=parent_task.id)
        form = TaskForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_task_form_next_step_date_validation(self):
        """Test next_step_date validation"""
        data = self._valid_task_data(
            next_step_date=(get_today() - timedelta(days=1)).isoformat(),
            remind_me=True,
        )
        form = TaskForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('next_step_date', form.errors)


class ProjectFormTest(TestCase):
    """Test ProjectForm validation"""
    fixtures = ('projectstage.json',)

    def setUp(self):
        from tasks.models import ProjectStage
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.stage = ProjectStage.objects.filter(default=True).first() or ProjectStage.objects.first()

    def _valid_project_data(self, **overrides):
        data = {
            'name': 'Test Project',
            'description': 'Project description',
            'responsible': [self.user.id],
            'next_step': 'Review',
            'next_step_date': (get_today() + timedelta(days=3)).isoformat(),
            'priority': '2',
            'stage': self.stage.pk,
        }
        data.update(overrides)
        return data

    def test_valid_project_form(self):
        """Test form with valid data"""
        form = ProjectForm(data=self._valid_project_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_project_form_requires_name(self):
        """Test that name is required"""
        form = ProjectForm(data={'name': '', 'responsible': [self.user.id]})
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_project_form_multiple_responsibles_allowed(self):
        """Test that projects can have multiple responsibles"""
        user2 = User.objects.create_user(username='user2', password='pass2')
        data = self._valid_project_data(responsible=[self.user.id, user2.id])
        form = ProjectForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)


class MemoFormTest(TestCase):
    """Test MemoForm validation"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_valid_memo_form(self):
        """Test form with valid data"""
        form = MemoForm(data={'name': 'Test Memo', 'description': 'Memo description', 'to': self.user.id})
        self.assertTrue(form.is_valid(), form.errors)

    def test_memo_form_with_minimal_data(self):
        """Test memo with minimal required data"""
        form = MemoForm(data={'name': 'Simple Memo', 'to': self.user.id})
        self.assertTrue(form.is_valid(), form.errors)


class FormWidgetsTest(TestCase):
    """Test form widget configuration"""

    def test_task_form_widgets(self):
        """Test TaskForm has proper widgets configured"""
        form = TaskForm()
        self.assertEqual(form.fields['name'].widget.__class__.__name__, 'Textarea')
        self.assertEqual(form.fields['description'].widget.__class__.__name__, 'Textarea')

    def test_project_form_widgets(self):
        """Test ProjectForm has proper widgets configured"""
        form = ProjectForm()
        self.assertEqual(form.fields['name'].widget.__class__.__name__, 'Textarea')

    def test_memo_form_widgets(self):
        """Test MemoForm has proper widgets configured"""
        form = MemoForm()
        self.assertEqual(form.fields['name'].widget.__class__.__name__, 'Textarea')
        self.assertEqual(form.fields['description'].widget.__class__.__name__, 'Textarea')
