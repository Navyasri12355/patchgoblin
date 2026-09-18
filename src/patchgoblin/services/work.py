"""WorkService — orchestrates the Stage 4 ``goblin work`` workflow.

Flow:
  Fetch issue + repo → analyse → show plan → human approval
  → create workspace → clone → verify clean → coding agent
  → diff → show results
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchgoblin.coding.agent import CodingAgent
from patchgoblin.coding.models import ChangeResult
from patchgoblin.config import Config
from patchgoblin.github.client import GitHubClient
from patchgoblin.github.models import IssueInfo, RepositoryInfo
from patchgoblin.llm.client import LLMError, OpenAICompatibleClient
from patchgoblin.llm.models import LLMConfig
from patchgoblin.llm.provider import LLMProvider
from patchgoblin.models.analysis import ImplementationPlan, IssueAnalysis
from patchgoblin.repository.clone import CloneError, RepositoryClone
from patchgoblin.repository.git import GitHelper
from patchgoblin.repository.inspector import RepositoryEvidence, RepositoryInspector
from patchgoblin.services.explain import ExplainError, ExplainService
from patchgoblin.workspace.manager import WorkspaceError, WorkspaceManager
from patchgoblin.workspace.models import WorkspaceMetadata, WorkspaceStatus


class WorkError(Exception):
    """Raised when the work workflow cannot complete."""


@dataclass
class WorkResult:
    """Full result of a ``goblin work`` run."""

    issue: IssueInfo
    repo: RepositoryInfo
    analysis: IssueAnalysis
    plan: ImplementationPlan
    workspace: WorkspaceMetadata
    change_result: ChangeResult


class WorkService:
    """Orchestrates the full ``goblin work`` workflow.

    Dependencies are injected so they can be mocked in tests.
    """

    def __init__(
        self,
        github_client: GitHubClient,
        llm_provider: LLMProvider,
        workspace_manager: WorkspaceManager,
        model_name: str = "unknown",
    ) -> None:
        self._github = github_client
        self._llm = llm_provider
        self._ws_manager = workspace_manager
        self._model_name = model_name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def prepare(
        self,
        owner: str,
        repo_name: str,
        issue_number: int,
    ) -> tuple[IssueInfo, RepositoryInfo, IssueAnalysis, RepositoryEvidence | None]:
        """Fetch issue/repo and run analysis.  Returns materials for human review."""
        issue = self._github.get_issue(owner, repo_name, issue_number)
        repo = self._github.get_repository(owner, repo_name)

        evidence: RepositoryEvidence | None = None
        clone_url = f"https://github.com/{repo.full_name}.git"
        try:
            with RepositoryClone(clone_url) as clone:
                inspector = RepositoryInspector(clone.path)
                evidence = inspector.collect_evidence(issue.title, issue.body)
        except CloneError:
            pass  # proceed without evidence

        explain_service = ExplainService(
            github_client=self._github,
            llm_provider=self._llm,
            model_name=self._model_name,
        )
        try:
            result = explain_service.explain(owner, repo_name, issue_number)
            analysis = result.analysis
        except (ExplainError, LLMError) as exc:
            raise WorkError(f"Analysis failed: {exc}") from exc

        return issue, repo, analysis, evidence

    def execute(
        self,
        owner: str,
        repo_name: str,
        issue_number: int,
        issue: IssueInfo,
        repo: RepositoryInfo,
        analysis: IssueAnalysis,
        plan: ImplementationPlan,
        approved_files: list[str],
    ) -> WorkResult:
        """Create workspace, clone, run the coding agent, generate diff.

        Parameters
        ----------
        approved_files:
            Relative paths the human has approved for modification.
        """
        issue_ref = f"{owner}/{repo_name}#{issue_number}"
        clone_url = f"https://github.com/{repo.full_name}.git"

        # --- Create workspace ---
        try:
            meta = self._ws_manager.create(
                issue_reference=issue_ref,
                repository=repo.full_name,
                source_url=clone_url,
            )
        except WorkspaceError as exc:
            raise WorkError(f"Failed to create workspace: {exc}") from exc

        # --- Clone ---
        workspace_path = Path(meta.local_path)
        try:
            self._clone_into(clone_url, workspace_path, meta)
        except (CloneError, WorkError) as exc:
            self._ws_manager.update_status(meta, WorkspaceStatus.FAILED)
            raise WorkError(str(exc)) from exc

        # --- Verify clean ---
        git = GitHelper(workspace_path)
        if not git.is_clean():
            self._ws_manager.update_status(meta, WorkspaceStatus.FAILED)
            raise WorkError("Cloned workspace has an unexpected dirty working tree. Aborting.")

        # --- Update approved files in metadata ---
        meta.approved_files = approved_files
        self._ws_manager.update_status(meta, WorkspaceStatus.WORKING)

        # --- Run coding agent ---
        agent = CodingAgent(
            llm=self._llm,
            workspace_root=workspace_path,
            approved_files=approved_files,
        )
        change_result = agent.run(issue=issue, analysis=analysis, plan=plan)

        # --- Update status ---
        if change_result.success:
            meta.modified_files = change_result.modified_files
            self._ws_manager.update_status(meta, WorkspaceStatus.REVIEW)
        else:
            self._ws_manager.update_status(meta, WorkspaceStatus.FAILED)

        return WorkResult(
            issue=issue,
            repo=repo,
            analysis=analysis,
            plan=plan,
            workspace=meta,
            change_result=change_result,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _clone_into(
        self,
        clone_url: str,
        workspace_path: Path,
        meta: WorkspaceMetadata,
    ) -> None:
        """Clone *clone_url* directly into *workspace_path* (must be empty)."""
        from patchgoblin.repository.clone import RepositoryClone

        # We need to clone directly into the pre-created workspace_path.
        # RepositoryClone normally creates a "repo" sub-dir; here we re-use it
        # as the destination by invoking the static helper directly.
        workspace_path.mkdir(parents=True, exist_ok=True)

        # Remove the existing empty dir so git clone can populate it
        import shutil

        shutil.rmtree(workspace_path)
        workspace_path.mkdir(parents=True, exist_ok=True)

        RepositoryClone._run_clone(clone_url, workspace_path)

        # Record commit SHA
        git = GitHelper(workspace_path)
        meta.commit_sha = git.rev_parse_head()
        meta.status = WorkspaceStatus.READY
        self._ws_manager.save(meta)


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------


def create_work_service(
    github_token: str,
    llm_api_key: str,
    *,
    base_url: str | None = None,
    model: str | None = None,
    workspace_manager: WorkspaceManager | None = None,
) -> WorkService:
    """Build a :class:`WorkService` from raw config values."""
    llm_cfg = LLMConfig(
        api_key=llm_api_key,
        base_url=base_url or Config.llm_base_url(),
        model=model or Config.llm_model(),
    )
    llm_client = OpenAICompatibleClient(llm_cfg)
    github_client = GitHubClient(github_token)
    ws_manager = workspace_manager or WorkspaceManager()
    return WorkService(
        github_client=github_client,
        llm_provider=llm_client,
        workspace_manager=ws_manager,
        model_name=llm_cfg.model,
    )
