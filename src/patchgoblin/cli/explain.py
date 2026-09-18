"""goblin explain command — AI-powered issue understanding and repository investigation."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from patchgoblin.cli.parse import parse_issue_reference
from patchgoblin.config import Config
from patchgoblin.llm.client import LLMError
from patchgoblin.models.analysis import ConfidenceLevel, IssueAnalysis
from patchgoblin.services.explain import ExplainError, ExplainResult, create_explain_service

console = Console()
app = typer.Typer()

_CONFIDENCE_STYLE = {
    ConfidenceLevel.HIGH: "green",
    ConfidenceLevel.MEDIUM: "yellow",
    ConfidenceLevel.LOW: "red",
}


@app.callback(invoke_without_command=True)
def explain(
    issue_ref: str = typer.Argument(
        ...,
        metavar="OWNER/REPO#NUMBER",
        help="Issue reference, e.g. pallets/flask#123",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Override the LLM model (default: LLM_MODEL env var or gpt-4o-mini).",
    ),
    skip_clone: bool = typer.Option(
        False,
        "--skip-clone",
        help="Skip repository cloning; analyze using GitHub metadata only.",
    ),
) -> None:
    """AI-powered analysis of a GitHub issue.

    Shows what the issue means, where to look, and how to approach it.
    """
    # --- Parse reference --------------------------------------------------
    try:
        ref = parse_issue_reference(issue_ref)
    except ValueError as exc:
        console.print(f"[red]Invalid issue reference:[/red] {exc}")
        raise typer.Exit(code=1) from None

    # --- Credentials check ------------------------------------------------
    github_token = Config.github_token()
    if not github_token:
        console.print("[red]Not authenticated.[/red] Run [bold]goblin auth login[/bold] first.")
        raise typer.Exit(code=1)

    llm_api_key = Config.llm_api_key()
    if not llm_api_key:
        console.print(
            "[red]LLM API key not set.[/red]\n"
            "Set the [bold]LLM_API_KEY[/bold] environment variable and retry.\n\n"
            "Tip: for deterministic issue inspection (no AI), use:\n"
            f"  goblin inspect {issue_ref}"
        )
        raise typer.Exit(code=1)

    # --- Run analysis -----------------------------------------------------
    console.print(
        f"\n[bold]PatchGoblin[/bold] — analyzing "
        f"[cyan]{ref.owner}/{ref.repo}#{ref.number}[/cyan]…\n"
    )

    try:
        service = create_explain_service(
            github_token=github_token,
            llm_api_key=llm_api_key,
            model=model,
            clone_repos=not skip_clone,
        )
        result = service.explain(ref.owner, ref.repo, ref.number)
    except ExplainError as exc:
        _print_explain_error(str(exc), issue_ref)
        raise typer.Exit(code=1) from None
    except LLMError as exc:
        _print_explain_error(str(exc), issue_ref)
        raise typer.Exit(code=1) from None
    except Exception as exc:
        console.print(f"[red]Unexpected error:[/red] {exc}")
        raise typer.Exit(code=1) from None

    _print_result(result)


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _print_result(result: ExplainResult) -> None:
    analysis = result.analysis
    issue = result.issue
    repo = result.repo
    confidence_style = _CONFIDENCE_STYLE.get(analysis.confidence, "yellow")

    console.print(Rule("[bold]PatchGoblin Analysis[/bold]"))
    console.print()

    # Header
    header = Text()
    header.append(f"Issue: #{issue.number}  {issue.title}\n", style="bold")
    header.append(f"Repository: {repo.full_name}\n", style="cyan")
    header.append(f"Model: {result.model_used}\n", style="dim")
    if result.commit_sha and result.commit_sha not in ("unknown", "not-cloned"):
        header.append(f"Commit: {result.commit_sha[:12]}\n", style="dim")
    header.append("Confidence: ", style="dim")
    header.append(analysis.confidence.value, style=confidence_style)
    console.print(Panel(header, title="[bold]Overview[/bold]"))

    # What the issue means
    _section("What this issue means", _format_meaning(analysis))

    # Likely area of the codebase
    if analysis.likely_files or analysis.likely_components:
        _section("Likely area of the codebase", _format_location(analysis))

    # Implementation approach
    if analysis.implementation_steps:
        _section("Implementation approach", _format_steps(analysis.implementation_steps))

    # Things to verify
    items: list[str] = []
    if analysis.potential_risks:
        items += [f"[yellow]Risk:[/yellow] {r}" for r in analysis.potential_risks]
    if analysis.unknowns:
        items += [f"[dim]Unknown:[/dim] {u}" for u in analysis.unknowns]
    if analysis.testing_strategy:
        items.append(f"[green]Testing:[/green] {analysis.testing_strategy}")
    if items:
        _section("Things to verify / unknowns", "\n".join(f"  • {i}" for i in items))

    console.print(Rule())
    console.print("[dim italic]AI-generated analysis — review before acting.[/dim italic]\n")


def _section(title: str, body: str) -> None:
    console.print(Rule(f"[bold]{title}[/bold]", style="dim"))
    console.print(body)
    console.print()


def _format_meaning(analysis: IssueAnalysis) -> str:
    lines = []
    if analysis.summary:
        lines.append(analysis.summary)
    if analysis.problem:
        lines.append(f"\n[bold]Problem:[/bold]\n  {analysis.problem}")
    if analysis.expected_behavior:
        lines.append(f"\n[bold]Expected behavior:[/bold]\n  {analysis.expected_behavior}")
    if analysis.current_behavior:
        lines.append(f"\n[bold]Current behavior:[/bold]\n  {analysis.current_behavior}")
    return "\n".join(lines)


def _format_location(analysis: IssueAnalysis) -> str:
    lines = []
    if analysis.likely_files:
        lines.append("[bold]Likely files:[/bold]")
        for f in analysis.likely_files:
            lines.append(f"  [cyan]{f.path}[/cyan]")
            if f.reason:
                lines.append(f"    [dim]{f.reason}[/dim]")
    if analysis.likely_components:
        lines.append("\n[bold]Relevant components:[/bold]")
        for c in analysis.likely_components:
            lines.append(f"  {c}")
    return "\n".join(lines)


def _format_steps(steps: list[str]) -> str:
    return "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(steps))


def _print_explain_error(reason: str, issue_ref: str) -> None:
    console.print(
        Panel(
            f"[red]PatchGoblin could not complete AI analysis.[/red]\n\n"
            f"[bold]Reason:[/bold]\n{reason}\n\n"
            f"The deterministic issue information is still available with:\n"
            f"  [bold]goblin inspect {issue_ref}[/bold]",
            title="[red]Analysis Failed[/red]",
        )
    )
