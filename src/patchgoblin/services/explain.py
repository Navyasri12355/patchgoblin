"""ExplainService — orchestrates GitHub fetching, repo investigation, and LLM analysis."""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import ValidationError

from patchgoblin.config import Config
from patchgoblin.github.client import GitHubClient
from patchgoblin.github.models import IssueInfo, RepositoryInfo
from patchgoblin.llm.client import LLMError, LLMResponseError, OpenAICompatibleClient
from patchgoblin.llm.models import LLMConfig
from patchgoblin.llm.prompts.issue_analysis import build_issue_analysis_prompt
from patchgoblin.llm.prompts.safety import SAFETY_SYSTEM_PROMPT
from patchgoblin.llm.provider import LLMProvider
from patchgoblin.models.analysis import IssueAnalysis
from patchgoblin.repository.clone import CloneError, RepositoryClone
from patchgoblin.repository.inspector import RepositoryEvidence, RepositoryInspector


class ExplainError(Exception):
    """Raised when the explain workflow cannot complete."""


@dataclass
class ExplainResult:
    """Full result of a ``goblin explain`` run."""

    issue: IssueInfo
    repo: RepositoryInfo
    analysis: IssueAnalysis
    commit_sha: str = "unknown"
    model_used: str = "unknown"


class ExplainService:
    """Orchestrates the full explain workflow.

    Dependencies are injected so they can be mocked in tests.
    """

    def __init__(
        self,
        github_client: GitHubClient,
        llm_provider: LLMProvider,
        model_name: str = "unknown",
        clone_repos: bool = True,
    ) -> None:
        self._github = github_client
        self._llm = llm_provider
        self._model_name = model_name
        self._clone_repos = clone_repos

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def explain(self, owner: str, repo_name: str, issue_number: int) -> ExplainResult:
        """Run the full explain workflow for *owner/repo_name#issue_number*."""
        issue = self._github.get_issue(owner, repo_name, issue_number)
        repo = self._github.get_repository(owner, repo_name)

        evidence: RepositoryEvidence | None = None
        if self._clone_repos:
            evidence = self._investigate_repo(repo, issue)

        analysis = self._run_llm_analysis(issue, repo, evidence)

        return ExplainResult(
            issue=issue,
            repo=repo,
            analysis=analysis,
            commit_sha=evidence.commit_sha if evidence else "not-cloned",
            model_used=self._model_name,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _investigate_repo(
        self, repo: RepositoryInfo, issue: IssueInfo
    ) -> RepositoryEvidence | None:
        """Clone the repository and collect static evidence."""
        clone_url = f"https://github.com/{repo.full_name}.git"
        try:
            with RepositoryClone(clone_url) as clone:
                inspector = RepositoryInspector(clone.path)
                return inspector.collect_evidence(issue.title, issue.body)
        except CloneError:
            # Non-fatal: continue without repository evidence
            return None

    def _run_llm_analysis(
        self,
        issue: IssueInfo,
        repo: RepositoryInfo,
        evidence: RepositoryEvidence | None,
    ) -> IssueAnalysis:
        """Build the prompt, call the LLM, and parse the structured response."""
        repo_tree = evidence.tree if evidence else None
        snippets = evidence.snippets if evidence else None

        prompt = build_issue_analysis_prompt(
            issue=issue,
            repo=repo,
            repo_tree=repo_tree,
            relevant_snippets=snippets,
        )

        try:
            raw_response = self._llm.generate(prompt, system=SAFETY_SYSTEM_PROMPT)
        except LLMError as exc:
            raise ExplainError(str(exc)) from exc

        return self._parse_analysis(raw_response)

    @staticmethod
    def _parse_analysis(raw: str) -> IssueAnalysis:
        """Parse and validate the LLM response as an :class:`IssueAnalysis`."""
        # Strip possible markdown code fences
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            # Remove opening fence (```json or ```)
            lines = lines[1:]
            # Remove closing fence
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMResponseError(
                f"LLM provider returned non-JSON response: {exc}\n\nRaw response:\n{raw[:500]}"
            ) from exc

        try:
            return IssueAnalysis.model_validate(data)
        except ValidationError as exc:
            raise LLMResponseError(f"LLM response did not match expected schema: {exc}") from exc


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------


def create_explain_service(
    github_token: str,
    llm_api_key: str,
    *,
    base_url: str | None = None,
    model: str | None = None,
    clone_repos: bool = True,
) -> ExplainService:
    """Build an :class:`ExplainService` from raw config values."""
    llm_cfg = LLMConfig(
        api_key=llm_api_key,
        base_url=base_url or Config.llm_base_url(),
        model=model or Config.llm_model(),
    )
    llm_client = OpenAICompatibleClient(llm_cfg)
    github_client = GitHubClient(github_token)
    return ExplainService(
        github_client=github_client,
        llm_provider=llm_client,
        model_name=llm_cfg.model,
        clone_repos=clone_repos,
    )
