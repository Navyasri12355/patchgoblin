"""goblin find command."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()
app = typer.Typer()


@app.callback(invoke_without_command=True)
def find() -> None:
    """Find beginner-friendly open-source issues to contribute to.

    [Stage 2] Full issue discovery with filtering, difficulty estimation,
    repository quality scoring, and contributor-fit matching will be
    implemented in Stage 2.
    """
    console.print(
        "[yellow]Issue discovery will be implemented in Stage 2.[/yellow]\n\n"
        "Coming soon:\n"
        "  • Filter by language, labels, and repository quality\n"
        "  • Difficulty estimation\n"
        "  • Contributor-fit matching"
    )
    raise typer.Exit()
