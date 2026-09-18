"""auth sub-commands: login, status, logout."""

from __future__ import annotations

import typer
from rich.console import Console

from patchgoblin.config import Config
from patchgoblin.github.client import GitHubAuthError, GitHubClient

console = Console()
app = typer.Typer(help="Manage GitHub authentication.")


@app.command("login")
def auth_login() -> None:
    """Configure GitHub authentication.

    Set the GITHUB_TOKEN environment variable and run ``goblin auth status``
    to verify it.
    """
    console.print(
        "[bold]To authenticate PatchGoblin:[/bold]\n\n"
        "  1. Create a Personal Access Token at "
        "[link=https://github.com/settings/tokens]https://github.com/settings/tokens[/link]\n"
        "  2. Export it in your shell:\n\n"
        "       [bold cyan]export GITHUB_TOKEN=your_token_here[/bold cyan]\n\n"
        "  3. Run [bold cyan]goblin auth status[/bold cyan] to verify."
    )


@app.command("status")
def auth_status() -> None:
    """Check whether the GitHub token is configured and valid."""
    token = Config.github_token()
    if not token:
        console.print("[red]GitHub authentication: not configured[/red]")
        console.print("Set [bold]GITHUB_TOKEN[/bold] and try again.")
        raise typer.Exit(code=1)

    try:
        with GitHubClient(token) as client:
            profile = client.get_authenticated_user()
        console.print("[green]GitHub authentication: valid[/green]")
        console.print(f"Authenticated as: [bold]{profile.username}[/bold]")
    except GitHubAuthError:
        console.print("[red]GitHub authentication: invalid token[/red]")
        console.print("The provided GITHUB_TOKEN was rejected by GitHub.")
        raise typer.Exit(code=1) from None
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error checking authentication:[/red] {exc}")
        raise typer.Exit(code=1) from None


@app.command("logout")
def auth_logout() -> None:
    """Remove GitHub authentication.

    PatchGoblin reads the token from the GITHUB_TOKEN environment variable.
    To log out, unset it in your shell:

        unset GITHUB_TOKEN
    """
    console.print(
        "[yellow]PatchGoblin uses the GITHUB_TOKEN environment variable.[/yellow]\n\n"
        "To log out, unset it in your shell:\n\n"
        "    [bold cyan]unset GITHUB_TOKEN[/bold cyan]\n\n"
        "The variable is not stored on disk by PatchGoblin."
    )
