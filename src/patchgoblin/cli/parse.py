"""Issue reference parser for the inspect command."""

from __future__ import annotations

import re
from dataclasses import dataclass

_ISSUE_REF_RE = re.compile(r"^(?P<owner>[^/]+)/(?P<repo>[^#]+)#(?P<number>\d+)$")


@dataclass(frozen=True)
class IssueReference:
    """Parsed issue reference: owner/repo#number."""

    owner: str
    repo: str
    number: int


def parse_issue_reference(ref: str) -> IssueReference:
    """
    Parse a string like ``owner/repo#123`` into an :class:`IssueReference`.

    Raises :class:`ValueError` with a descriptive message on invalid input.
    """
    ref = ref.strip()
    match = _ISSUE_REF_RE.match(ref)
    if not match:
        raise ValueError(
            f"Invalid issue reference: {ref!r}\n"
            "Expected format: owner/repository#number  (e.g. pallets/flask#123)"
        )
    owner = match.group("owner").strip()
    repo = match.group("repo").strip()
    number = int(match.group("number"))

    if not owner:
        raise ValueError("Owner must not be empty.")
    if not repo:
        raise ValueError("Repository name must not be empty.")
    if number <= 0:
        raise ValueError("Issue number must be a positive integer.")

    return IssueReference(owner=owner, repo=repo, number=number)
