# tests/common/test_github_workflows.py
"""
Regression tests για το .github/workflows/claude.yml (P1-01).

Επικυρώνουν ότι το Claude workflow δεν μπορεί να ενεργοποιηθεί με σκέτο
label event (χωρίς @claude mention και author-association gate) και ότι
τα υπάρχοντα mention-based triggers/permissions παραμένουν ως έχουν.
"""
from pathlib import Path

import yaml
from django.test import SimpleTestCase

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "claude.yml"
)

# Τα τρία mention-based event paths που πρέπει να διατηρηθούν.
EXPECTED_EVENTS = {
    "issue_comment",
    "pull_request_review_comment",
    "pull_request_review",
}


class ClaudeWorkflowTriggerGateTest(SimpleTestCase):
    """Το claude.yml δεν πρέπει να έχει label-based trigger path."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # yaml.safe_load κάνει και syntax validation — αν το YAML είναι
        # άκυρο, όλα τα tests της κλάσης αποτυγχάνουν εδώ.
        with open(WORKFLOW_PATH, encoding="utf-8") as f:
            cls.workflow = yaml.safe_load(f)
        # Στο YAML 1.1 το κλειδί "on" διαβάζεται ως boolean True.
        cls.triggers = cls.workflow.get("on", cls.workflow.get(True))
        cls.job = cls.workflow["jobs"]["claude"]
        cls.condition = cls.job["if"]

    def test_workflow_parses_and_has_expected_structure(self):
        self.assertIsInstance(self.workflow, dict)
        self.assertIsInstance(self.triggers, dict)
        self.assertIn("claude", self.workflow["jobs"])

    def test_no_issues_labeled_event_trigger(self):
        """Label event μόνο του δεν μπορεί να ξεκινήσει το job."""
        self.assertNotIn("issues", self.triggers)

    def test_mention_based_events_remain(self):
        self.assertEqual(set(self.triggers), EXPECTED_EVENTS)
        self.assertEqual(self.triggers["issue_comment"]["types"], ["created"])
        self.assertEqual(
            self.triggers["pull_request_review_comment"]["types"], ["created"]
        )
        self.assertEqual(
            self.triggers["pull_request_review"]["types"], ["submitted"]
        )

    def test_no_label_based_condition(self):
        """Δεν υπάρχει condition branch για issues/labeled events."""
        self.assertNotIn("github.event_name == 'issues'", self.condition)
        self.assertNotIn("label", self.condition)

    def test_every_condition_branch_requires_mention_and_association(self):
        """
        Comment/review χωρίς @claude δεν περνά: κάθε OR branch του `if`
        απαιτεί το trigger phrase ΚΑΙ το author-association gate.
        """
        branches = [b.strip() for b in self.condition.split("||") if b.strip()]
        self.assertEqual(len(branches), len(EXPECTED_EVENTS))
        for branch in branches:
            self.assertIn("@claude", branch, msg=branch)
            self.assertIn(
                'contains(fromJSON(\'["OWNER","MEMBER"]\')', branch, msg=branch
            )
            self.assertIn("author_association", branch, msg=branch)

    def test_condition_covers_exactly_the_expected_events(self):
        for event in EXPECTED_EVENTS:
            self.assertIn(f"github.event_name == '{event}'", self.condition)

    def test_no_label_trigger_action_input(self):
        """Το claude-code-action δεν έχει πλέον label_trigger input."""
        for step in self.job["steps"]:
            self.assertNotIn("label_trigger", step.get("with", {}))

    def test_trigger_phrase_and_oauth_token_remain(self):
        action_steps = [
            s for s in self.job["steps"]
            if "claude-code-action" in s.get("uses", "")
        ]
        self.assertEqual(len(action_steps), 1)
        with_block = action_steps[0]["with"]
        self.assertEqual(with_block["trigger_phrase"], "@claude")
        self.assertEqual(
            with_block["claude_code_oauth_token"],
            "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}",
        )

    def test_permissions_unchanged(self):
        """Τα permissions του job παραμένουν ακριβώς ως έχουν."""
        self.assertEqual(
            self.job["permissions"],
            {
                "contents": "write",
                "pull-requests": "write",
                "issues": "write",
                "actions": "read",
                "checks": "read",
                "id-token": "write",
            },
        )
