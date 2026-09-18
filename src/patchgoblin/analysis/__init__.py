"""Analysis package for PatchGoblin."""

from patchgoblin.analysis.contributor import analyze_contributor, extract_languages
from patchgoblin.analysis.difficulty import Difficulty, estimate_difficulty
from patchgoblin.analysis.issue import analyze_issue, is_beginner_friendly, is_newbie_friendly
from patchgoblin.analysis.matching import FitResult, calculate_fit
from patchgoblin.analysis.repository import analyze_repository

__all__ = [
    "Difficulty",
    "estimate_difficulty",
    "is_beginner_friendly",
    "is_newbie_friendly",
    "analyze_issue",
    "analyze_repository",
    "analyze_contributor",
    "extract_languages",
    "FitResult",
    "calculate_fit",
]
