"""Analysis package for PatchGoblin."""

from patchgoblin.analysis.contributor import analyze_contributor
from patchgoblin.analysis.issue import analyze_issue, is_beginner_friendly
from patchgoblin.analysis.repository import analyze_repository

__all__ = [
    "analyze_issue",
    "is_beginner_friendly",
    "analyze_repository",
    "analyze_contributor",
]
