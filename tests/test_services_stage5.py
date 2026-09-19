"""Tests for Stage 5 services."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from patchgoblin.services.feedback_service import FeedbackService, PRFeedback
from patchgoblin.services.pr_service import PRService
from patchgoblin.services.push_service import PushService
from patchgoblin.services.test_service import TestService, TestServiceError
from patchgoblin.testing.models import TestingLanguage, TestRunResult
from patchgoblin.workspace.models import WorkspaceMetadata, WorkspaceStatus


class TestTestService:
    """Test TestService."""

    @patch("patchgoblin.services.test_service.TestExecutor")
    @patch("patchgoblin.services.test_service.WorkspaceManager")
    def test_run_tests_success(self, mock_ws_manager_class, mock_executor_class):
        """Test successful test execution."""
        # Setup workspace metadata
        mock_meta = Mock(spec=WorkspaceMetadata)
        mock_meta.status = WorkspaceStatus.REVIEW
        mock_meta.local_path = "/tmp/workspace"

        mock_ws_manager = Mock()
        mock_ws_manager.load.return_value = mock_meta
        mock_ws_manager_class.return_value = mock_ws_manager

        # Setup executor mock
        mock_executor = Mock()
        test_result = TestRunResult(
            task_id="test-task",
            command="pytest",
            exit_code=0,
            passed=True,
            duration_seconds=5.0,
            truncated_output="",
            language=TestingLanguage.PYTHON,
        )
        mock_executor.execute.return_value = test_result
        mock_executor_class.return_value = mock_executor

        # Execute
        service = TestService()
        result = service.run_tests("test-task")

        # Verify
        assert result.task_id == "test-task"
        assert result.passed is True
        mock_ws_manager.save.assert_called_once()

    @patch("patchgoblin.services.test_service.WorkspaceManager")
    def test_run_tests_invalid_status(self, mock_ws_manager_class):
        """Test error handling for invalid workspace status."""
        mock_meta = Mock()
        mock_meta.status = Mock()
        mock_meta.status.value = "working"

        mock_ws_manager = Mock()
        mock_ws_manager.load.return_value = mock_meta
        mock_ws_manager_class.return_value = mock_ws_manager

        service = TestService()
        with pytest.raises(TestServiceError, match="status"):
            service.run_tests("test-task")


class TestPushService:
    """Test PushService."""

    @patch("patchgoblin.services.push_service.PushManager")
    @patch("patchgoblin.services.push_service.BranchManager")
    @patch("patchgoblin.services.push_service.WorkspaceManager")
    def test_push_branch_success(
        self, mock_ws_manager_class, mock_branch_manager_class, mock_push_manager_class
    ):
        """Test successful branch push."""
        # Setup workspace metadata
        mock_meta = Mock()
        mock_meta.status = WorkspaceStatus.REVIEW
        mock_meta.local_path = "/tmp/workspace"
        mock_meta.issue_reference = "owner/repo#123"
        mock_meta.approved_files = ["file1.py"]

        mock_ws_manager = Mock()
        mock_ws_manager.load.return_value = mock_meta
        mock_ws_manager_class.return_value = mock_ws_manager

        # Setup mocks
        mock_branch_manager = Mock()
        mock_branch_manager.create_patchgoblin_branch.return_value = "patchgoblin/pg-123-fix"
        mock_branch_manager_class.return_value = mock_branch_manager

        mock_push_manager = Mock()
        mock_push_manager.commit_and_push.return_value = "origin/patchgoblin/pg-123-fix"
        mock_push_manager_class.return_value = mock_push_manager

        # Execute
        service = PushService()
        branch_name, remote_ref = service.push_branch("pg-123", "test commit")

        # Verify
        assert branch_name == "patchgoblin/pg-123-fix"
        assert remote_ref == "origin/patchgoblin/pg-123-fix"
        mock_ws_manager.save.assert_called_once()


class TestPRService:
    """Test PRService."""

    @patch("patchgoblin.services.pr_service.GitHubClient")
    @patch("patchgoblin.services.pr_service.BranchManager")
    @patch("patchgoblin.services.pr_service.WorkspaceManager")
    def test_create_pr_success(
        self, mock_ws_manager_class, mock_branch_manager_class, mock_github_client_class
    ):
        """Test successful PR creation."""
        # Setup workspace metadata
        mock_meta = Mock(spec=WorkspaceMetadata)
        mock_meta.local_path = "/tmp/workspace"
        mock_meta.repository = "owner/repo"

        mock_ws_manager = Mock()
        mock_ws_manager.load.return_value = mock_meta
        mock_ws_manager_class.return_value = mock_ws_manager

        # Setup branch manager mock
        mock_branch_manager = Mock()
        mock_branch_manager.get_current_branch.return_value = "patchgoblin/pg-123-fix"
        mock_branch_manager.is_patchgoblin_branch.return_value = True
        mock_branch_manager_class.return_value = mock_branch_manager

        # Setup GitHub client mock
        mock_github = Mock()
        mock_user = Mock()
        mock_user.username = "testuser"
        mock_github.get_authenticated_user.return_value = mock_user

        mock_repo = Mock()
        mock_repo.default_branch = "main"
        mock_github.get_repository.return_value = mock_repo

        mock_pr = Mock()
        mock_pr.url = "https://github.com/owner/repo/pull/1"
        mock_pr.number = 1
        mock_github.create_pull_request.return_value = mock_pr
        mock_github_client_class.return_value = mock_github

        # Execute
        service = PRService(mock_github)
        pr = service.create_pull_request("pg-123", "Test PR", "PR body")

        # Verify
        assert pr.url == "https://github.com/owner/repo/pull/1"
        assert pr.number == 1
        mock_ws_manager.save.assert_called_once()


class TestFeedbackService:
    """Test FeedbackService."""

    @patch("patchgoblin.services.feedback_service.GitHubClient")
    def test_get_feedback_success(self, mock_github_client_class):
        """Test successful feedback retrieval."""
        # Setup GitHub client mock
        mock_github = Mock()
        mock_pr = Mock()
        mock_pr.url = "https://github.com/owner/repo/pull/1"
        mock_github.get_pull_request.return_value = mock_pr
        mock_github.list_pull_request_reviews.return_value = []
        mock_github.list_pull_request_comments.return_value = []
        mock_github.list_pull_request_check_runs.return_value = []
        mock_github_client_class.return_value = mock_github

        # Execute
        service = FeedbackService(mock_github)
        feedback = service.get_feedback("owner", "repo", 1)

        # Verify
        assert feedback.pr.url == "https://github.com/owner/repo/pull/1"
        assert len(feedback.reviews) == 0
        assert len(feedback.comments) == 0
        assert len(feedback.check_runs) == 0

    def test_feedback_has_approval(self):
        """Test feedback approval detection."""
        mock_pr = Mock()
        mock_pr.url = "https://github.com/owner/repo/pull/1"

        mock_review = Mock()
        mock_review.state.value = "APPROVED"

        feedback = PRFeedback(
            pr=mock_pr,
            reviews=[mock_review],
            comments=[],
            check_runs=[],
        )

        assert feedback.has_approval is True
        assert feedback.has_changes_requested is False
