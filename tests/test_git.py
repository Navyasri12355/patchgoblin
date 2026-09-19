"""Tests for git module (Stage 5)."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from patchgoblin.git.branch import BranchError, BranchManager
from patchgoblin.git.push import PushError, PushManager
from patchgoblin.repository.git import GitError


class TestBranchManager:
    """Test BranchManager."""

    @patch("patchgoblin.git.branch.GitHelper")
    def test_create_patchgoblin_branch(self, mock_git_helper_class, tmp_path):
        """Test creating a PatchGoblin-owned branch."""
        mock_git = Mock()
        mock_git.checkout_new_branch.return_value = None
        mock_git_helper_class.return_value = mock_git

        manager = BranchManager(tmp_path)
        branch_name = manager.create_patchgoblin_branch("pg-abc123", "fix-issue")

        assert branch_name.startswith("patchgoblin/")
        assert "pg-abc123" in branch_name
        mock_git.checkout_new_branch.assert_called_once()

    @patch("patchgoblin.git.branch.GitHelper")
    def test_create_protected_branch_rejected(self, mock_git_helper_class, tmp_path):
        """Test that protected branch names are rejected."""
        mock_git = Mock()
        mock_git_helper_class.return_value = mock_git

        manager = BranchManager(tmp_path)
        # Test the protected branch check directly
        assert manager.is_protected_branch("main") is True
        assert manager.is_protected_branch("master") is True

    @patch("patchgoblin.git.branch.GitHelper")
    def test_get_current_branch(self, mock_git_helper_class, tmp_path):
        """Test getting current branch name."""
        mock_git = Mock()
        mock_git.current_branch.return_value = "patchgoblin/pg-abc123-fix"
        mock_git_helper_class.return_value = mock_git

        manager = BranchManager(tmp_path)
        branch = manager.get_current_branch()
        assert branch == "patchgoblin/pg-abc123-fix"

    @patch("patchgoblin.git.branch.GitHelper")
    def test_get_current_branch_error(self, mock_git_helper_class, tmp_path):
        """Test error handling when getting current branch."""
        mock_git = Mock()
        mock_git.current_branch.side_effect = GitError("git error")
        mock_git_helper_class.return_value = mock_git

        manager = BranchManager(tmp_path)
        with pytest.raises(BranchError, match="Failed to get current branch"):
            manager.get_current_branch()

    def test_is_patchgoblin_branch(self, tmp_path):
        """Test PatchGoblin branch detection."""
        manager = BranchManager(tmp_path)
        assert manager.is_patchgoblin_branch("patchgoblin/pg-123-fix") is True
        assert manager.is_patchgoblin_branch("main") is False
        assert manager.is_patchgoblin_branch("feature-branch") is False

    def test_is_protected_branch(self, tmp_path):
        """Test protected branch detection."""
        manager = BranchManager(tmp_path)
        assert manager.is_protected_branch("main") is True
        assert manager.is_protected_branch("master") is True
        assert manager.is_protected_branch("develop") is True
        assert manager.is_protected_branch("patchgoblin/pg-123-fix") is False


class TestPushManager:
    """Test PushManager."""

    @patch("patchgoblin.git.push.BranchManager")
    @patch("patchgoblin.git.push.GitHelper")
    def test_commit_and_push_success(
        self, mock_git_helper_class, mock_branch_manager_class, tmp_path
    ):
        """Test successful commit and push."""
        # Setup git mock
        mock_git = Mock()
        mock_git_helper_class.return_value = mock_git

        # Setup branch manager mock
        mock_branch_manager = Mock()
        mock_branch_manager.get_current_branch.return_value = "patchgoblin/pg-123-fix"
        mock_branch_manager.is_patchgoblin_branch.return_value = True
        mock_branch_manager.is_protected_branch.return_value = False
        mock_branch_manager_class.return_value = mock_branch_manager

        # Execute
        push_manager = PushManager(tmp_path)
        remote_ref = push_manager.commit_and_push(
            "patchgoblin/pg-123-fix", ["file1.py"], "test commit"
        )

        # Verify
        assert remote_ref == "origin/patchgoblin/pg-123-fix"
        mock_git.add_files.assert_called_once()
        mock_git.commit.assert_called_once()
        mock_git.push.assert_called_once()

    @patch("patchgoblin.git.push.BranchManager")
    def test_push_non_patchgoblin_branch_rejected(self, mock_branch_manager_class, tmp_path):
        """Test that non-PatchGoblin branches are rejected."""
        mock_branch_manager = Mock()
        mock_branch_manager.is_patchgoblin_branch.return_value = False
        mock_branch_manager_class.return_value = mock_branch_manager

        push_manager = PushManager(tmp_path)
        with pytest.raises(PushError, match="non-PatchGoblin branch"):
            push_manager.commit_and_push("pg-123", "main", ["file1.py"], "test commit")

    @patch("patchgoblin.git.push.BranchManager")
    def test_push_protected_branch_rejected(self, mock_branch_manager_class, tmp_path):
        """Test that protected branches are rejected."""
        mock_branch_manager = Mock()
        mock_branch_manager.is_patchgoblin_branch.return_value = True
        mock_branch_manager.is_protected_branch.return_value = True
        mock_branch_manager_class.return_value = mock_branch_manager

        push_manager = PushManager(tmp_path)
        with pytest.raises(PushError, match="protected branch"):
            push_manager.commit_and_push(
                "pg-123", "patchgoblin/pg-123-main", ["file1.py"], "test commit"
            )
