"""goblin find command — Stage 2 issue discovery."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from patchgoblin.analysis.difficulty import Difficulty
from patchgoblin.config import Config
from patchgoblin.github.client import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubClient,
    GitHubRateLimitError,
)
from patchgoblin.models.candidate import ContributionCandidate
from patchgoblin.services.discovery import DiscoveryFilters, discover_candidates

console = Console()
app = typer.Typer()

_DIFFICULTY_STYLE = {
    Difficulty.BEGINNER: "green",
    Difficulty.INTERMEDIATE: "yellow",
    Difficulty.ADVANCED: "red",
    Difficulty.UNKNOWN: "dim",
}


def _fit_style(score: int) -> str:
    if score >= 70:
        return "bold green"
    if score >= 45:
        return "yellow"
    return "dim"


def _render_candidate(index: int, candidate: ContributionCandidate) -> Panel:
    """Render a single candidate as a Rich Panel."""
    issue = candidate.issue
    repo = candidate.repository

    diff_style = _DIFFICULTY_STYLE.get(candidate.estimated_difficulty, "dim")
    fit_style = _fit_style(candidate.fit_score)

    body = Text()
    body.append(f"{repo.full_name}", style="bold cyan")
    body.append(f"#{issue.number}  ", style="cyan")
    body.append(f"{issue.title}\n", style="bold")

    body.append("\n  Difficulty:    ", style="dim")
    body.append(candidate.estimated_difficulty.value, style=diff_style)
    body.append("\n  Heuristic fit: ", style="dim")
    body.append(f"{candidate.fit_score}/100", style=fit_style)

    if repo.language:
        body.append("\n  Language:      ", style="dim")
        body.append(repo.language)

    body.append("\n  Stars:         ", style="dim")
    body.append(f"{repo.stars:,}")

    if candidate.fit_reasons:
        body.append("\n\n  [bold]Signals:[/bold]")
        for reason in candidate.fit_reasons:
            body.append(f"\n  [green]✓[/green] {reason}")

    if candidate.concerns:
        body.append("\n\n  [bold]Concerns:[/bold]")
        for concern in candidate.concerns:
            body.append(f"\n  [yellow]•[/yellow] {concern}")

    body.append(f"\n\n  {issue.url}", style="dim underline")

    return Panel(body, title=f"[bold]#{index}[/bold]", expand=False)


def _render_table(candidates: list[ContributionCandidate]) -> Table:
    """Render candidates as a summary table."""
    table = Table(
        title="[bold]PatchGoblin — Top Heuristic Matches[/bold]",
        show_lines=False,
        header_style="bold",
        title_justify="left",
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Repository", style="cyan", no_wrap=True)
    table.add_column("Issue", no_wrap=False, max_width=50)
    table.add_column("Difficulty", no_wrap=True)
    table.add_column("Fit", no_wrap=True)

    for i, c in enumerate(candidates, 1):
        diff_style = _DIFFICULTY_STYLE.get(c.estimated_difficulty, "dim")
        fit_style = _fit_style(c.fit_score)
        table.add_row(
            str(i),
            f"{c.repository.full_name}#{c.issue.number}",
            c.issue.title,
            Text(c.estimated_difficulty.value, style=diff_style),
            Text(f"{c.fit_score}/100", style=fit_style),
        )

    return table


@app.callback(invoke_without_command=True)
def find(
    language: str | None = typer.Option(  # noqa: UP007
        None, "--language", "-l", help="Filter by programming language (e.g. python)."
    ),
    label: str | None = typer.Option(  # noqa: UP007
        None, "--label", help="Filter by GitHub label (e.g. good-first-issue)."
    ),
    topic: str | None = typer.Option(  # noqa: UP007
        None, "--topic", help="Filter by repository topic."
    ),
    min_stars: int | None = typer.Option(  # noqa: UP007
        None, "--min-stars", help="Minimum repository stars."
    ),
    max_stars: int | None = typer.Option(  # noqa: UP007
        None, "--max-stars", help="Maximum repository stars."
    ),
    limit: int = typer.Option(
        10, "--limit", "-n", help="Maximum number of results.", min=1, max=50
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed cards for each result."
    ),
) -> None:
    """Find open-source issues that match your contributor profile.

    Results are ordered by PatchGoblin's heuristic fit score — not by
    objective difficulty or guaranteed suitability. The score is explained
    for each result so you can make your own judgement.

    Use [bold cyan]goblin inspect OWNER/REPO#N[/bold cyan] to investigate any issue further.
    """
    token = Config.github_token()
    if not token:
        console.print("[red]Not authenticated.[/red] Run [bold]goblin auth login[/bold] first.")
        raise typer.Exit(code=1)

    filters = DiscoveryFilters(
        language=language,
        label=label,
        topic=topic,
        min_stars=min_stars,
        max_stars=max_stars,
        limit=limit,
    )

    console.print("[bold]PatchGoblin Issue Finder[/bold]")
    console.print("Searching GitHub for contribution opportunities...\n")

    try:
        with GitHubClient(token) as client:
            contributor = client.get_authenticated_user()
            candidates = discover_candidates(client, contributor, filters)
    except GitHubAuthError:
        console.print("[red]Invalid or expired GitHub token.[/red]")
        raise typer.Exit(code=1) from None
    except GitHubRateLimitError:
        console.print("[red]GitHub API rate limit exceeded.[/red] Try again later.")
        raise typer.Exit(code=1) from None
    except GitHubAPIError as exc:
        console.print(f"[red]GitHub API error:[/red] {exc}")
        raise typer.Exit(code=1) from None

    if not candidates:
        console.print("[yellow]No candidates found.[/yellow] Try adjusting your filters.")
        raise typer.Exit()

    console.print(f"Found [bold]{len(candidates)}[/bold] candidate(s).\n")

    if verbose:
        for i, candidate in enumerate(candidates, 1):
            console.print(_render_candidate(i, candidate))
            console.print()
    else:
        console.print(_render_table(candidates))
        console.print(
            "\n[dim]Use [bold]goblin inspect OWNER/REPO#N[/bold]"
            " to investigate an issue in detail.[/dim]"
        )
        console.print("[dim]Use [bold]--verbose[/bold] for per-issue signal breakdown.[/dim]")
