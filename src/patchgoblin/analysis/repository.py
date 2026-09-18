"""Repository analysis — deterministic heuristics for Stage 1."""

from __future__ import annotations

from patchgoblin.github.models import RepositoryInfo


def analyze_repository(repo: RepositoryInfo) -> dict:
    """
    Return a simple analysis dict for a repository.

    This is a deterministic Stage 1 placeholder.
    LLM-based analysis will be introduced in a later stage.
    """
    return {
        "full_name": repo.full_name,
        "language": repo.language,
        "stars": repo.stars,
        "forks": repo.forks,
        "open_issues": repo.open_issues,
        "has_description": bool(repo.description and repo.description.strip()),
    }
