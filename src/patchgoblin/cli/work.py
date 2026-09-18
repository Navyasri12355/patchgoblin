"""goblin work command — repository-aware code generation in an isolated workspace."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from patchgoblin.cli.parse import parse_issue_reference
from patchgoblin.config import Config
from patchgoblin.models.analysis import ImplementationPlan
from patchgoblin.services.work import WorkError, WorkResult, create_work_service
from patchgoblin.workspace.manager import WorkspaceError, WorkspaceManager
from patchgoblin.workspace.models import WorkspaceMetadata, WorkspaceStatus

console = Console()
app = typer.Typer(no_args_is_help=True)

# Maximum lines of diff shown in the terminal before truncating
_MAX_DIFF_LINES = 80


# ---------------------------------------------------------------------------
# goblin work <issue-ref>
# ---------------------------------------------------------------------------


@app.command(name="start")
def work_start(
    issue_ref: str = typer.Argument(
        ...,
        metavar="OWNER/REPO#NUMBER",
        help="Issue reference, e.g. pallets/flask#123",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Override the LLM model.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip the human approval prompt (use in scripts).",
    ),
) -> None:
    """Start the work workflow for a GitHub issue.

    Analyses the issue, presents an implementation plan, asks for approval,
    then modifies a disposable workspace and shows the resulting diff.
    """
    # --- Parse reference ---
    try:
        ref = parse_issue_reference(issue_ref)
    except ValueError as exc:
        console.print(f"[red]Invalid issue reference:[/red] {exc}")
        raise typer.Exit(code=1) from None

    # --- Credentials ---
    github_token = Config.github_token()
    if not github_token:
        console.print("[red]Not authenticated.[/red] Run [bold]goblin auth login[/bold] first.")
        raise typer.Exit(code=1)

    llm_api_key = Config.llm_api_key()
    if not llm_api_key:
        console.print(
            "[red]LLM API key not set.[/red]\n"
            "Set the [bold]LLM_API_KEY[/bold] environment variable and retry."
        )
        raise typer.Exit(code=1)

    # --- Prepare (fetch + analyse) ---
    console.print(
        f"\n[bold]PatchGoblin[/bold] — preparing implementation for "
        f"[cyan]{ref.owner}/{ref.repo}#{ref.number}[/cyan]…\n"
    )

    service = create_work_service(
        github_token=github_token,
        llm_api_key=llm_api_key,
        model=model,
    )

    try:
        issue, repo, analysis, evidence = service.prepare(ref.owner, ref.repo, ref.number)
    except WorkError as exc:
        console.print(f"[red]Preparation failed:[/red] {exc}")
        raise typer.Exit(code=1) from None

    # Build a simple implementation plan from the analysis
    likely_files = [f.path for f in analysis.likely_files]
    plan = ImplementationPlan(
        objective=analysis.summary,
        steps=analysis.implementation_steps,
        files_to_modify=likely_files,
        files_to_add=[],
        tests_to_update=[f for f in likely_files if "test" in f.lower()],
        risks=analysis.potential_risks,
        unknowns=analysis.unknowns,
    )

    # Combine approved files (modify + new)
    approved_files = list(dict.fromkeys(plan.files_to_modify + plan.files_to_add))

    # --- Show plan + approval gate ---
    _print_approval_prompt(issue_ref, plan, approved_files, str(service._ws_manager.base_dir))

    if not yes:
        answer = typer.prompt("Proceed with implementation? [y/N]", default="N")
        if answer.strip().lower() != "y":
            console.print("\n[yellow]Implementation cancelled.[/yellow]")
            raise typer.Exit(code=0)

    # --- Execute ---
    console.print("\n[bold]PatchGoblin[/bold] — creating workspace and running coding agent…\n")

    try:
        result = service.execute(
            owner=ref.owner,
            repo_name=ref.repo,
            issue_number=ref.number,
            issue=issue,
            repo=repo,
            analysis=analysis,
            plan=plan,
            approved_files=approved_files,
        )
    except WorkError as exc:
        console.print(f"[red]Work failed:[/red] {exc}")
        raise typer.Exit(code=1) from None

    _print_result(result)


@app.callback(invoke_without_command=False)
def work_callback(ctx: typer.Context) -> None:
    """Workspace-based code modification commands."""


# The default command when called as ``goblin work owner/repo#123``
# Typer doesn't natively do positional dispatch to subcommands for single
# non-subcommand patterns, so we add a separate top-level callback that
# intercepts the positional argument pattern.

# ---------------------------------------------------------------------------
# goblin work status
# ---------------------------------------------------------------------------


@app.command(name="status")
def work_status() -> None:
    """Show status of all PatchGoblin workspaces."""
    ws_manager = WorkspaceManager()
    workspaces = ws_manager.list_all()

    if not workspaces:
        console.print("[dim]No PatchGoblin workspaces found.[/dim]")
        return

    console.print(Rule("[bold]PatchGoblin Workspaces[/bold]"))
    for meta in workspaces:
        _print_workspace_summary(meta)


# ---------------------------------------------------------------------------
# goblin work list
# ---------------------------------------------------------------------------


@app.command(name="list")
def work_list() -> None:
    """List all PatchGoblin workspaces."""
    work_status()


# ---------------------------------------------------------------------------
# goblin work inspect <task-id>
# ---------------------------------------------------------------------------


@app.command(name="inspect")
def work_inspect(
    task_id: str = typer.Argument(..., help="Task ID, e.g. pg-7f3a21"),
) -> None:
    """Inspect a specific PatchGoblin workspace."""
    ws_manager = WorkspaceManager()
    try:
        meta = ws_manager.load(task_id)
    except WorkspaceError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from None

    _print_workspace_detail(meta, ws_manager)


# ---------------------------------------------------------------------------
# goblin work diff <task-id>
# ---------------------------------------------------------------------------


@app.command(name="diff")
def work_diff(
    task_id: str = typer.Argument(..., help="Task ID, e.g. pg-7f3a21"),
) -> None:
    """Show the full git diff for a workspace."""
    from patchgoblin.repository.git import GitHelper

    ws_manager = WorkspaceManager()
    try:
        meta = ws_manager.load(task_id)
    except WorkspaceError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from None

    import os

    if not os.path.exists(meta.local_path):
        console.print(f"[red]Workspace path does not exist:[/red] {meta.local_path}")
        raise typer.Exit(code=1)

    git = GitHelper(meta.path)
    diff = git.diff()
    if not diff.strip():
        console.print("[dim]No changes in this workspace.[/dim]")
    else:
        console.print(diff)


# ---------------------------------------------------------------------------
# goblin work discard <task-id>
# ---------------------------------------------------------------------------


@app.command(name="discard")
def work_discard(
    task_id: str = typer.Argument(..., help="Task ID, e.g. pg-7f3a21"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Discard a PatchGoblin workspace (deletes the cloned repository)."""
    ws_manager = WorkspaceManager()
    try:
        meta = ws_manager.load(task_id)
    except WorkspaceError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from None

    console.print(
        Panel(
            f"[bold]Task:[/bold] {meta.task_id}\n"
            f"[bold]Issue:[/bold] {meta.issue_reference}\n"
            f"[bold]Workspace:[/bold] {meta.local_path}\n\n"
            "[yellow]This will permanently delete the workspace directory.[/yellow]\n"
            "PatchGoblin will NOT delete anything outside this workspace.",
            title="[red]Discard Workspace[/red]",
        )
    )

    if not yes:
        answer = typer.prompt("Confirm discard? [y/N]", default="N")
        if answer.strip().lower() != "y":
            console.print("[yellow]Discard cancelled.[/yellow]")
            raise typer.Exit(code=0)

    try:
        ws_manager.discard(task_id)
        console.print(f"[green]Workspace {task_id!r} discarded.[/green]")
    except WorkspaceError as exc:
        console.print(f"[red]Discard failed:[/red] {exc}")
        raise typer.Exit(code=1) from None


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _print_approval_prompt(
    issue_ref: str,
    plan: ImplementationPlan,
    approved_files: list[str],
    workspace_base: str,
) -> None:
    lines = [
        "[bold]PatchGoblin is ready to modify a disposable workspace.[/bold]\n",
        f"[bold]Issue:[/bold] {issue_ref}\n",
        "[bold]Planned changes:[/bold]",
    ]
    for i, step in enumerate(plan.steps, 1):
        lines.append(f"  {i}. {step}")
    if approved_files:
        lines.append("\n[bold]Likely files:[/bold]")
        for f in approved_files:
            lines.append(f"  - [cyan]{f}[/cyan]")
    lines.append(f"\n[bold]Workspace base:[/bold] {workspace_base}")
    lines.append("\n[green]PatchGoblin will NOT modify your original repository.[/green]")

    console.print(Panel("\n".join(lines), title="[bold]Implementation Plan[/bold]"))


def _print_result(result: WorkResult) -> None:
    cr = result.change_result
    meta = result.workspace

    if not cr.success:
        console.print(
            Panel(
                f"[red]Coding agent failed.[/red]\n\n{cr.error}",
                title="[red]Work Failed[/red]",
            )
        )
        return

    # Success summary
    lines = [
        "[green]PatchGoblin finished the proposed changes.[/green]\n",
        "[bold]Files changed:[/bold]",
    ]
    for f in cr.modified_files:
        lines.append(f"  [cyan]{f}[/cyan]")
    if cr.diff_stat:
        lines.append(f"\n[bold]Diff stat:[/bold]\n{cr.diff_stat}")
    if cr.summary:
        lines.append(f"\n[bold]Summary:[/bold]\n{cr.summary}")
    if cr.concerns:
        lines.append("\n[bold yellow]Concerns:[/bold yellow]")
        for c in cr.concerns:
            lines.append(f"  [yellow]• {c}[/yellow]")
    lines.append(
        f"\n[dim]Task ID:[/dim] [bold]{meta.task_id}[/bold]\n"
        f"[dim]Workspace:[/dim] {meta.local_path}\n\n"
        "[bold red]PatchGoblin has NOT pushed or committed anything.[/bold red]\n"
        "Review the changes before proceeding.\n\n"
        f"[dim]View full diff:[/dim]  goblin work diff {meta.task_id}\n"
        f"[dim]Discard workspace:[/dim] goblin work discard {meta.task_id}"
    )

    console.print(Panel("\n".join(lines), title="[bold green]Work Complete[/bold green]"))

    # Show diff (truncated)
    if cr.diff and cr.diff.strip():
        diff_lines = cr.diff.splitlines()
        shown = diff_lines[:_MAX_DIFF_LINES]
        console.print(Rule("[bold]Diff Preview[/bold]"))
        console.print("\n".join(shown))
        if len(diff_lines) > _MAX_DIFF_LINES:
            console.print(
                f"\n[dim]… {len(diff_lines) - _MAX_DIFF_LINES} more lines. "
                f"Run [bold]goblin work diff {meta.task_id}[/bold] to view the full diff.[/dim]"
            )


def _print_workspace_summary(meta: WorkspaceMetadata) -> None:
    status_style = {
        WorkspaceStatus.REVIEW: "green",
        WorkspaceStatus.MODIFIED: "cyan",
        WorkspaceStatus.WORKING: "yellow",
        WorkspaceStatus.FAILED: "red",
        WorkspaceStatus.DISCARDED: "dim",
    }.get(meta.status, "white")

    text = Text()
    text.append(f"{meta.task_id}  ", style="bold")
    text.append(f"{meta.issue_reference}  ", style="cyan")
    text.append(meta.status.value, style=status_style)
    if meta.modified_files:
        text.append(f"  ({len(meta.modified_files)} file(s) modified)", style="dim")
    console.print(text)


def _print_workspace_detail(meta: WorkspaceMetadata, ws_manager: WorkspaceManager) -> None:
    from patchgoblin.repository.git import GitError, GitHelper  # noqa: F401

    short_sha = meta.commit_sha[:12] if meta.commit_sha != "unknown" else "unknown"
    lines = [
        f"[bold]Task:[/bold] {meta.task_id}",
        f"[bold]Issue:[/bold] {meta.issue_reference}",
        f"[bold]Repository:[/bold] {meta.repository}",
        f"[bold]Status:[/bold] {meta.status.value}",
        f"[bold]Commit:[/bold] {short_sha}",
        f"[bold]Created:[/bold] {meta.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"[bold]Workspace:[/bold] {meta.local_path}",
    ]
    if meta.approved_files:
        lines.append("\n[bold]Approved files:[/bold]")
        for f in meta.approved_files:
            lines.append(f"  - {f}")
    if meta.modified_files:
        lines.append("\n[bold]Modified files:[/bold]")
        for f in meta.modified_files:
            lines.append(f"  - [cyan]{f}[/cyan]")

    import os

    if os.path.exists(meta.local_path):
        try:
            git = GitHelper(meta.path)
            diff_stat = git.diff_stat()
            if diff_stat:
                lines.append(f"\n[bold]Diff stat:[/bold]\n{diff_stat}")
        except GitError:
            pass

    lines.append(
        f"\n[dim]View diff:[/dim]  goblin work diff {meta.task_id}\n"
        f"[dim]Discard:[/dim]    goblin work discard {meta.task_id}"
    )

    console.print(Panel("\n".join(lines), title=f"[bold]Workspace {meta.task_id}[/bold]"))
