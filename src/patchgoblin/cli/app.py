"""Root Typer application — wires together all sub-commands."""

from __future__ import annotations

import typer

from patchgoblin.cli import auth, find, inspect, profile

app = typer.Typer(
    name="goblin",
    help=(
        "PatchGoblin — your open-source contribution copilot.\n\n"
        "Summon the goblin, find the right issue, ship the patch."
    ),
    no_args_is_help=True,
)

# auth sub-commands (goblin auth login / status / logout)
app.add_typer(auth.app, name="auth", help="Manage GitHub authentication.")

# top-level commands
app.add_typer(profile.app, name="profile", help="Display your GitHub profile.")
app.add_typer(find.app, name="find", help="Find beginner-friendly issues.")
app.add_typer(inspect.app, name="inspect", help="Inspect a GitHub issue.")
