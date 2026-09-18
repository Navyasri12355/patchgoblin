"""Contributor analysis — deterministic heuristics."""

from __future__ import annotations

from patchgoblin.github.models import ContributorProfile


def extract_languages(profile: ContributorProfile) -> list[str]:
    """Return the list of programming languages the contributor is known to use."""
    return list(profile.known_languages)


def analyze_contributor(profile: ContributorProfile) -> dict:
    """Return a structured analysis dict for a contributor profile."""
    return {
        "username": profile.username,
        "public_repos": profile.public_repositories,
        "followers": profile.followers,
        "has_bio": bool(profile.bio and profile.bio.strip()),
        "known_languages": extract_languages(profile),
    }
