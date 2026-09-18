"""goblin inspect command."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from patchgoblin.cli.parse import parse_issue_reference
from patchgoblin.config import Config
from patchgoblin.github.client import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubClient,
    GitHubNotFoundError,
)

console = Console()
app = typer.Typer()


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
    header.append(f"URL: {issue.url}")

    console.print(Panel(header, title="[bold]PatchGoblin — Issue Inspection[/bold]"))

    if issue.body and issue.body.strip():
        console.print("\n[bold]Description:[/bold]")
        console.print(issue.body.strip())
