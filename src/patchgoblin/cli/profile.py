"""goblin profile command."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from patchgoblin.config import Config
from patchgoblin.github.client import GitHubAPIError, GitHubAuthError, GitHubClient

console = Console()
app = typer.Typer()


@app.callback(invoke_without_command=True)
def profile() -> None:
    """Display your GitHub profile."""
    token = Config.github_token()
    if not token:
        console.print("[red]Not authenticated.[/red] Run [bold]goblin auth login[/bold] first.")
        raise typer.Exit(code=1)

    try:
        with GitHubClient(token) as client:
            p = client.get_authenticated_user()
    except GitHubAuthError:
        console.print("[red]Invalid or expired GitHub token.[/red]")
        raise typer.Exit(code=1) from None
    except GitHubAPIError as exc:
        console.print(f"[red]GitHub API error:[/red] {exc}")
        raise typer.Exit(code=1) from None

    table = Table(title="PatchGoblin Profile", show_header=False, box=None)
    table.add_column("Field", style="bold cyan", no_wrap=True)
    table.add_column("Value")

    table.add_row("Username", p.username)
    table.add_row("Name", p.name or "—")
    table.add_row("Bio", p.bio or "—")
    table.add_row("Public repositories", str(p.public_repositories))
    table.add_row("Followers", str(p.followers))
    table.add_row("Following", str(p.following))
    table.add_row("Profile URL", p.profile_url)

    console.print(table)
