"""Issue discovery service — Stage 2 implementation."""

from __future__ import annotations

from dataclasses import dataclass

from patchgoblin.analysis.matching import calculate_fit
from patchgoblin.github.client import GitHubAPIError, GitHubClient
from patchgoblin.github.models import ContributorProfile, IssueInfo, RepositoryInfo
from patchgoblin.models.candidate import ContributionCandidate
from patchgoblin.services.query import build_issue_search_query

_DOCUMENTATION_LABELS = frozenset({"documentation", "docs", "doc", "typo", "readme"})
_GOOD_FIRST_LABELS = frozenset(
    {"good first issue", "good-first-issue", "first-timers-only", "newcomer"}
)
_HELP_WANTED_LABELS = frozenset({"help wanted", "help-wanted"})


@dataclass
class DiscoveryFilters:
    """Structured filters for :func:`discover_candidates`."""

    language: str | None = None
    label: str | None = None
    topic: str | None = None
    min_stars: int | None = None
    max_stars: int | None = None
    limit: int = 10


def _enrich_contributor(client: GitHubClient, profile: ContributorProfile) -> ContributorProfile:
    """
    Fetch the user's public repos and populate ``known_languages``.

    Returns a new ContributorProfile with ``known_languages`` set.
    Silently falls back to an empty list on API errors.
    """
    try:
        repos = client.list_user_repos(per_page=100)
    except GitHubAPIError:
        return profile

    langs = {r.get("language") for r in repos if isinstance(r, dict) and r.get("language")}
    return profile.model_copy(update={"known_languages": sorted(langs)})


def _fetch_repos_deduped(
    client: GitHubClient,
    issues: list[IssueInfo],
) -> dict[str, RepositoryInfo]:
    """
    Return a mapping of full_name → RepositoryInfo for all unique
    repositories referenced by *issues*.

    Each unique repo is fetched at most once.
    """
    seen: dict[str, RepositoryInfo] = {}
    for issue in issues:
        # The issue URL is like https://github.com/owner/repo/issues/N
        parts = issue.url.rstrip("/").split("/")
        # parts: ['https:', '', 'github.com', 'owner', 'repo', 'issues', 'N']
        if len(parts) >= 5:
            owner, repo_name = parts[3], parts[4]
            full_name = f"{owner}/{repo_name}"
            if full_name not in seen:
                try:
                    seen[full_name] = client.get_repository(owner, repo_name)
                except GitHubAPIError:
                    pass  # Skip repos we can't fetch; handled below
    return seen


def _label_set(issue: IssueInfo) -> frozenset[str]:
    return frozenset(lbl.lower() for lbl in issue.labels)


def _build_candidate(
    issue: IssueInfo,
    repo: RepositoryInfo,
    contributor: ContributorProfile,
) -> ContributionCandidate:
    """Assemble a fully-scored :class:`ContributionCandidate`."""
    labels = _label_set(issue)
    fit = calculate_fit(issue, repo, contributor)

    return ContributionCandidate(
        repository=repo,
        issue=issue,
        language=repo.language,
        good_first_issue=bool(labels & _GOOD_FIRST_LABELS),
        help_wanted=bool(labels & _HELP_WANTED_LABELS),
        documentation_related=bool(labels & _DOCUMENTATION_LABELS),
        estimated_difficulty=fit.difficulty,
        fit_score=fit.score,
        fit_reasons=fit.reasons,
        concerns=fit.concerns,
    )


def discover_candidates(
    client: GitHubClient,
    contributor: ContributorProfile,
    filters: DiscoveryFilters | None = None,
) -> list[ContributionCandidate]:
    """
    Search GitHub for open issues and return ranked :class:`ContributionCandidate` objects.

    Flow:
    1. Build a structured GitHub query from *filters*.
    2. Fetch issues (at most ``filters.limit * 3`` to give the ranker room).
    3. Enrich the contributor profile with language data.
    4. Fetch unique repositories (deduplicated).
    5. Score each issue against the contributor profile.
    6. Sort by fit score descending, truncate to *limit*.
    """
    if filters is None:
        filters = DiscoveryFilters()

    query = build_issue_search_query(
        language=filters.language,
        label=filters.label,
        topic=filters.topic,
        min_stars=filters.min_stars,
        max_stars=filters.max_stars,
    )

    fetch_count = min(filters.limit * 3, 100)
    issues = client.search_issues(query, per_page=fetch_count)

    if not issues:
        return []

    # Enrich contributor with language data
    enriched_contributor = _enrich_contributor(client, contributor)

    # Fetch unique repo metadata
    repo_map = _fetch_repos_deduped(client, issues)

    # Score and build candidates, skipping issues whose repo we couldn't fetch
    candidates: list[ContributionCandidate] = []
    for issue in issues:
        parts = issue.url.rstrip("/").split("/")
        if len(parts) >= 5:
            full_name = f"{parts[3]}/{parts[4]}"
            repo = repo_map.get(full_name)
            if repo is None:
                # Create a minimal RepositoryInfo from what we know
                repo = RepositoryInfo(
                    owner=parts[3],
                    name=parts[4],
                    full_name=full_name,
                    url=f"https://github.com/{full_name}",
                )
            candidates.append(_build_candidate(issue, repo, enriched_contributor))

    # Sort by fit score descending
    candidates.sort(key=lambda c: c.fit_score, reverse=True)

    return candidates[: filters.limit]
