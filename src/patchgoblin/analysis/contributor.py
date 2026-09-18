"""Contributor analysis — deterministic heuristics for Stage 1."""

from __future__ import annotations

from patchgoblin.github.models import ContributorProfile


def analyze_contributor(profile: ContributorProfile) -> dict:
    """
    Return a simple analysis dict for a contributor profile.

    This is a deterministic Stage 1 placeholder.
    LLM-based matching will be introduced in a later stage.
    """
    return {
        "username": profile.username,
        "public_repos": profile.public_repositories,
        "followers": profile.followers,
        "has_bio": bool(profile.bio and profile.bio.strip()),
    }
