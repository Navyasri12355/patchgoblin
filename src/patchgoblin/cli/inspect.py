"""goblin inspect command."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from patchgoblin.analysis.difficulty import Difficulty, estimate_difficulty
from patchgoblin.analysis.matching import calculate_fit
from patchgoblin.cli.parse import parse_issue_reference
from patchgoblin.config import Config
from patchgoblin.github.client import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubClient,
    GitHubNotFoundError,
)
from patchgoblin.github.models import ContributorProfile, RepositoryInfo

console = Console()
app = typer.Typer()

_DIFFICULTY_STYLE = {
    Difficulty.BEGINNER: "green",
    Difficulty.INTERMEDIATE: "yellow",
    Difficulty.ADVANCED: "red",
    Difficulty.UNKNOWN: "dim",
}


@app.callback(invoke_without_command=True)
def inspect(
    issue_ref: str = typer.Argument(
        ...,
        metavar="OWNER/REPO#NUMBER",
        help="Issue reference, e.g. pallets/flask#123",
    ),
) -> None:
    """Inspect a GitHub issue."""
    try:
        ref = parse_issue_reference(issue_ref)
    except ValueError as exc:
        console.print(f"[red]Invalid issue reference:[/red] {exc}")
        raise typer.Exit(code=1) from None

    token = Config.github_token()
    if not token:
        console.print("[red]Not authenticated.[/red] Run [bold]goblin auth login[/bold] first.")
        raise typer.Exit(code=1)

    try:
        with GitHubClient(token) as client:
            issue = client.get_issue(ref.owner, ref.repo, ref.number)
            # Best-effort: fetch repo and contributor for analysis
            try:
                repo = client.get_repository(ref.owner, ref.repo)
            except GitHubAPIError:
                repo = RepositoryInfo(
                    owner=ref.owner,
                    name=ref.repo,
                    full_name=f"{ref.owner}/{ref.repo}",
                    url=f"https://github.com/{ref.owner}/{ref.repo}",
                )
            try:
                contributor: ContributorProfile | None = client.get_authenticated_user()
            except GitHubAPIError:
                contributor = None
    except GitHubAuthError:
        console.print("[red]Invalid or expired GitHub token.[/red]")
        raise typer.Exit(code=1) from None
    except GitHubNotFoundError:
        console.print(
            f"[red]Issue not found:[/red] {ref.owner}/{ref.repo}#{ref.number}\n"
            "Check that the owner, repository, and issue number are correct."
        )
        raise typer.Exit(code=1) from None
    except GitHubAPIError as exc:
        console.print(f"[red]GitHub API error:[/red] {exc}")
        raise typer.Exit(code=1) from None

    labels_str = ", ".join(issue.labels) if issue.labels else "none"
    difficulty = estimate_difficulty(issue)
    diff_style = _DIFFICULTY_STYLE.get(difficulty, "dim")

    header = Text()
    header.append(f"Issue #{issue.number}\n", style="bold")
    header.append(f"Title: {issue.title}\n\n")
    header.append(f"Repository: {ref.owner}/{ref.repo}\n", style="cyan")
    header.append(f"State: {issue.state}\n", style="green" if issue.state == "open" else "red")
    header.append(f"Labels: {labels_str}\n")
    header.append(f"Author: {issue.author}\n")
    header.append(f"Comments: {issue.comments}\n")
    header.append(f"Created: {issue.created_at.strftime('%Y-%m-%d')}\n")
    header.append(f"Updated: {issue.updated_at.strftime('%Y-%m-%d')}\n\n")
    header.append("Difficulty: ", style="dim")
    header.append(difficulty.value, style=diff_style)
    header.append(f"\n\nURL: {issue.url}")

    console.print(Panel(header, title="[bold]PatchGoblin — Issue Inspection[/bold]"))

    # Heuristic fit (only if we have contributor context)
    if contributor is not None:
        fit = calculate_fit(issue, repo, contributor)
        fit_panel = Text()
        fit_panel.append(f"Heuristic fit: {fit.score}/100\n", style="bold")
        fit_panel.append(
            "[dim](Deterministic estimate — not an objective measure of suitability)[/dim]\n"
        )
        if fit.reasons:
            fit_panel.append("\n[bold]Signals:[/bold]")
            for r in fit.reasons:
                fit_panel.append(f"\n[green]✓[/green] {r}")
        if fit.concerns:
            fit_panel.append("\n\n[bold]Concerns:[/bold]")
            for c in fit.concerns:
                fit_panel.append(f"\n[yellow]•[/yellow] {c}")
        console.print(Panel(fit_panel, title="[bold]Contribution Fit[/bold]"))

    if issue.body and issue.body.strip():
        console.print("\n[bold]Description:[/bold]")
        console.print(issue.body.strip())
