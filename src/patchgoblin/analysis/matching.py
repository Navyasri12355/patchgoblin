"""Contribution-fit heuristic — deterministic scoring with explainability."""

from __future__ import annotations

from dataclasses import dataclass, field

from patchgoblin.analysis.difficulty import Difficulty, estimate_difficulty
from patchgoblin.github.models import ContributorProfile, IssueInfo, RepositoryInfo

# ---------------------------------------------------------------------------
# Scoring constants (all values are documented here for transparency)
# ---------------------------------------------------------------------------
#
# Positive factors
_SCORE_LANGUAGE_MATCH = 20  # repo language in contributor's known languages
_SCORE_GOOD_FIRST_ISSUE = 30  # "good first issue" or "first-timers-only" label
_SCORE_HELP_WANTED = 15  # "help wanted" label
_SCORE_DOCUMENTATION = 10  # documentation / readme / typo issue
_SCORE_TEST = 8  # test-related issue
_SCORE_BEGINNER_DIFFICULTY = 15  # estimated difficulty is BEGINNER
_SCORE_CLEAR_DESCRIPTION = 10  # issue has a non-empty description

# Negative factors
_SCORE_ADVANCED_ISSUE = -25  # estimated difficulty is ADVANCED
_SCORE_UNCLEAR_ISSUE = -15  # no description at all
_SCORE_LARGE_FEATURE = -20  # labels suggest large feature / epic
_SCORE_SECURITY = -20  # security-sensitive label
_SCORE_MANY_COMMENTS = -10  # >20 comments (active / contested discussion)

# Score bounds
_MIN_RAW = -50
_MAX_RAW = 100


# ---------------------------------------------------------------------------
# Label checks (re-use difficulty label sets where appropriate)
# ---------------------------------------------------------------------------

_GOOD_FIRST_LABELS = frozenset(
    {"good first issue", "good-first-issue", "first-timers-only", "newcomer"}
)
_HELP_WANTED_LABELS = frozenset({"help wanted", "help-wanted"})
_DOCUMENTATION_LABELS = frozenset({"documentation", "docs", "doc", "typo", "readme"})
_TEST_LABELS = frozenset({"test", "tests", "testing"})
_LARGE_FEATURE_LABELS = frozenset({"epic", "major", "large", "big feature"})
_SECURITY_LABELS = frozenset({"security", "vulnerability", "cve"})


def _label_set(issue: IssueInfo) -> frozenset[str]:
    return frozenset(lbl.lower() for lbl in issue.labels)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class FitResult:
    """Heuristic fit score with human-readable explanations."""

    score: int  # 0–100
    reasons: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    difficulty: Difficulty = Difficulty.UNKNOWN


# ---------------------------------------------------------------------------
# Contributor language extraction
# ---------------------------------------------------------------------------


def extract_contributor_languages(profile: ContributorProfile) -> frozenset[str]:
    """
    Return the set of languages the contributor is known to use.

    Stage 2: languages come from the contributor's own starred/repo list
    held in ``ContributorProfile.known_languages`` (populated by the
    discovery service when it fetches per-user repos).  Falls back to
    an empty set if not available.
    """
    langs = getattr(profile, "known_languages", None) or set()
    return frozenset(lang.lower() for lang in langs)


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------


def calculate_fit(
    issue: IssueInfo,
    repo: RepositoryInfo,
    contributor: ContributorProfile,
) -> FitResult:
    """
    Return a deterministic :class:`FitResult` for a potential contribution.

    The score is normalised to 0–100 and accompanied by explicit reasons
    and concerns so the user can evaluate the heuristic themselves.
    """
    labels = _label_set(issue)
    difficulty = estimate_difficulty(issue)
    contributor_languages = extract_contributor_languages(contributor)

    raw = 0
    reasons: list[str] = []
    concerns: list[str] = []

    # --- Positive signals ---

    # Language match
    repo_lang = (repo.language or "").lower()
    if repo_lang and contributor_languages and repo_lang in contributor_languages:
        raw += _SCORE_LANGUAGE_MATCH
        reasons.append(f"Repository uses {repo.language} (language match)")

    # Good first issue
    if labels & _GOOD_FIRST_LABELS:
        raw += _SCORE_GOOD_FIRST_ISSUE
        matched = next(iter(labels & _GOOD_FIRST_LABELS))
        reasons.append(f'Labeled "{matched}"')

    # Help wanted
    if labels & _HELP_WANTED_LABELS:
        raw += _SCORE_HELP_WANTED
        reasons.append('Labeled "help wanted"')

    # Documentation / typo
    if labels & _DOCUMENTATION_LABELS:
        raw += _SCORE_DOCUMENTATION
        reasons.append("Documentation or typo issue (typically accessible)")

    # Test issue
    if labels & _TEST_LABELS:
        raw += _SCORE_TEST
        reasons.append("Test-related issue (good for learning the codebase)")

    # Beginner difficulty estimate
    if difficulty == Difficulty.BEGINNER:
        raw += _SCORE_BEGINNER_DIFFICULTY
        reasons.append("Heuristic difficulty estimate: beginner")

    # Clear issue description
    has_description = bool(issue.body and issue.body.strip())
    if has_description:
        raw += _SCORE_CLEAR_DESCRIPTION
        reasons.append("Issue has a description (requirements are visible)")

    # --- Negative signals ---

    # Advanced difficulty
    if difficulty == Difficulty.ADVANCED:
        raw += _SCORE_ADVANCED_ISSUE
        concerns.append("Heuristic difficulty estimate: advanced")

    # No description at all
    if not has_description:
        raw += _SCORE_UNCLEAR_ISSUE
        concerns.append("Issue has no description (requirements may be unclear)")

    # Large feature / epic
    if labels & _LARGE_FEATURE_LABELS:
        raw += _SCORE_LARGE_FEATURE
        concerns.append("Labeled as large feature or epic")

    # Security sensitive
    if labels & _SECURITY_LABELS:
        raw += _SCORE_SECURITY
        concerns.append("Security-sensitive issue (higher risk)")

    # Long discussion thread
    if issue.comments > 20:
        raw += _SCORE_MANY_COMMENTS
        concerns.append(f"{issue.comments} existing comments (active discussion)")

    # --- Normalise to 0–100 ---
    clamped = max(_MIN_RAW, min(_MAX_RAW, raw))
    # Map [_MIN_RAW, _MAX_RAW] → [0, 100]
    score = round((clamped - _MIN_RAW) / (_MAX_RAW - _MIN_RAW) * 100)

    return FitResult(score=score, reasons=reasons, concerns=concerns, difficulty=difficulty)
