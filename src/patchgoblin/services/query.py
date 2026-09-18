"""Structured GitHub search query builder.

Constructs GitHub issue search queries from validated parameters.
User input is never concatenated verbatim — only whitelisted values
and properly quoted strings reach the API.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Allowed / validated values
# ---------------------------------------------------------------------------

_SAFE_LABEL_RE = re.compile(r"^[\w\s\-\.]+$")
_SAFE_LANGUAGE_RE = re.compile(r"^[\w\+\#]+$")
_SAFE_TOPIC_RE = re.compile(r"^[\w\-]+$")


def _safe_label(label: str) -> str:
    """Validate and return a label string safe for the GitHub query."""
    label = label.strip()
    if not _SAFE_LABEL_RE.match(label):
        raise ValueError(f"Invalid label: {label!r}")
    return label


def _safe_language(language: str) -> str:
    """Validate and return a language string safe for the GitHub query."""
    language = language.strip()
    if not _SAFE_LANGUAGE_RE.match(language):
        raise ValueError(f"Invalid language: {language!r}")
    return language


def _safe_topic(topic: str) -> str:
    """Validate and return a topic string safe for the GitHub query."""
    topic = topic.strip()
    if not _SAFE_TOPIC_RE.match(topic):
        raise ValueError(f"Invalid topic: {topic!r}")
    return topic


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------


def build_issue_search_query(
    *,
    language: str | None = None,
    label: str | None = None,
    topic: str | None = None,
    min_stars: int | None = None,
    max_stars: int | None = None,
    extra_labels: list[str] | None = None,
) -> str:
    """
    Build a GitHub issue search query string from structured parameters.

    Returns a query string ready to pass to the GitHub search API.
    Raises :class:`ValueError` if any parameter fails validation.

    Examples::

        build_issue_search_query(language="python", label="good first issue")
        # → 'is:issue is:open label:"good first issue" language:python'
    """
    parts: list[str] = ["is:issue", "is:open"]

    if label is not None:
        parts.append(f'label:"{_safe_label(label)}"')

    if extra_labels:
        for lbl in extra_labels:
            parts.append(f'label:"{_safe_label(lbl)}"')

    if language is not None:
        parts.append(f"language:{_safe_language(language)}")

    if topic is not None:
        parts.append(f"topic:{_safe_topic(topic)}")

    if min_stars is not None:
        if max_stars is not None:
            parts.append(f"stars:{min_stars}..{max_stars}")
        else:
            parts.append(f"stars:>={min_stars}")
    elif max_stars is not None:
        parts.append(f"stars:<={max_stars}")

    return " ".join(parts)
