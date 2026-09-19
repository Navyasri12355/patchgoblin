"""Feedback service for Stage 5 PR feedback polling."""

from __future__ import annotations

from dataclasses import dataclass

from patchgoblin.github.client import GitHubClient
from patchgoblin.github.models import PRCheckRun, PRComment, PRReview, PullRequestInfo


class FeedbackServiceError(Exception):
    """Raised when feedback service operations fail."""


@dataclass
class PRFeedback:
    """Aggregated feedback for a pull request."""

    pr: PullRequestInfo
    reviews: list[PRReview]
    comments: list[PRComment]
    check_runs: list[PRCheckRun]

    @property
    def has_approval(self) -> bool:
        """Check if any review is an approval."""
        return any(review.state.value == "APPROVED" for review in self.reviews)

    @property
    def has_changes_requested(self) -> bool:
        """Check if any review requests changes."""
        return any(review.state.value == "CHANGES_REQUESTED" for review in self.reviews)

    @property
    def has_failing_checks(self) -> bool:
        """Check if any check runs have failed."""
        return any(check.conclusion == "failure" for check in self.check_runs if check.conclusion)


class FeedbackService:
    """Service for polling PR feedback (read-only)."""

    def __init__(self, github_client: GitHubClient) -> None:
        """Initialize with GitHub client."""
        self._github = github_client

    def get_feedback(self, owner: str, repo: str, pr_number: int) -> PRFeedback:
        """Get feedback for a pull request.

        This is a read-only operation that fetches reviews, comments, and CI status.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            PRFeedback with aggregated feedback.

        Raises:
            FeedbackServiceError: If feedback retrieval fails.
        """
        try:
            # Get PR details
            pr = self._github.get_pull_request(owner, repo, pr_number)

            # Get reviews
            reviews = self._github.list_pull_request_reviews(owner, repo, pr_number)

            # Get comments
            comments = self._github.list_pull_request_comments(owner, repo, pr_number)

            # Get check runs
            check_runs = self._github.list_pull_request_check_runs(owner, repo, pr_number)

            return PRFeedback(
                pr=pr,
                reviews=reviews,
                comments=comments,
                check_runs=check_runs,
            )

        except Exception as exc:
            raise FeedbackServiceError(f"Failed to get feedback: {exc}") from exc
