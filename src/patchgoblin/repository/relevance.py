"""Deterministic relevance scoring for repository files.

Before calling the LLM, PatchGoblin performs keyword-based file discovery
to select a small, high-signal subset of source files.
"""

from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Directories and extensions to ignore
# ---------------------------------------------------------------------------

IGNORE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".env",
        "dist",
        "build",
        "coverage",
        ".coverage",
        "htmlcov",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "eggs",
        ".eggs",
        "*.egg-info",
        "site-packages",
        ".tox",
        ".nox",
    }
)

IGNORE_EXTENSIONS: frozenset[str] = frozenset(
    {
        # Compiled / binary
        ".pyc",
        ".pyo",
        ".so",
        ".dylib",
        ".dll",
        ".exe",
        ".o",
        ".a",
        ".lib",
        # Images
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".ico",
        ".webp",
        ".bmp",
        ".tiff",
        # Video / audio
        ".mp4",
        ".mp3",
        ".wav",
        ".avi",
        ".mov",
        # Archives
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".7z",
        ".whl",
        ".egg",
        # Fonts
        ".ttf",
        ".otf",
        ".woff",
        ".woff2",
        # Data / DB
        ".db",
        ".sqlite",
        ".sqlite3",
        ".pkl",
        ".parquet",
        ".bin",
        # Lock files (large, not useful for analysis)
        ".lock",
    }
)

# Extensions we consider "source" (higher priority)
SOURCE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".kt",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".swift",
        ".scala",
        ".clj",
        ".ex",
        ".exs",
        ".sh",
        ".bash",
    }
)

# Directories that typically contain tests
TEST_DIR_PATTERNS: tuple[str, ...] = ("test", "tests", "spec", "specs", "__tests__")

# Limits
MAX_FILE_SIZE_BYTES = 50_000  # 50 KB per file
MAX_SNIPPET_CHARS = 2_000  # Characters per snippet sent to LLM
MAX_RELEVANT_FILES = 10  # Maximum files to pass to LLM


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_keywords(text: str) -> list[str]:
    """Extract meaningful lowercase keywords from *text*.

    Splits on whitespace and punctuation, removes short/common tokens.
    """
    words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", text.lower())
    stopwords = {
        "the",
        "and",
        "for",
        "are",
        "this",
        "that",
        "with",
        "from",
        "have",
        "has",
        "was",
        "not",
        "but",
        "can",
        "will",
        "should",
        "when",
        "which",
        "they",
        "you",
        "its",
        "use",
        "used",
        "also",
        "been",
        "may",
        "all",
        "any",
        "there",
    }
    seen: set[str] = set()
    result = []
    for w in words:
        if w not in stopwords and w not in seen:
            seen.add(w)
            result.append(w)
    return result


def score_file(path: Path, root: Path, keywords: list[str]) -> int:
    """Assign a relevance score to *path* based on *keywords*.

    Higher score → more relevant.
    """
    score = 0
    rel = path.relative_to(root)
    rel_str = str(rel).lower().replace("\\", "/")
    name = path.name.lower()
    suffix = path.suffix.lower()

    # Source files score higher
    if suffix in SOURCE_EXTENSIONS:
        score += 5

    # Test files get a bonus — they are almost always relevant
    if any(pat in rel_str for pat in TEST_DIR_PATTERNS) or name.startswith("test_"):
        score += 3

    # Keyword matches in path
    for kw in keywords:
        if kw in rel_str:
            score += 4

    # README / changelog are useful context
    if name in ("readme.md", "readme.rst", "readme.txt", "changelog.md", "changes.md"):
        score += 2

    # Package config files
    if name in ("pyproject.toml", "setup.py", "setup.cfg", "package.json", "cargo.toml"):
        score += 1

    return score


def find_relevant_files(
    root: Path,
    keywords: list[str],
    *,
    max_files: int = MAX_RELEVANT_FILES,
) -> list[Path]:
    """Return up to *max_files* files most relevant to *keywords*.

    Walks the directory tree, ignores generated/binary content, scores each
    candidate, and returns the top-N sorted by descending score.
    """
    candidates: list[tuple[int, Path]] = []

    for path in _iter_source_files(root):
        score = score_file(path, root, keywords)
        if score > 0:
            candidates.append((score, path))

    candidates.sort(key=lambda x: x[0], reverse=True)
    # Deduplicate (shouldn't happen but guard against symlinks)
    seen: set[Path] = set()
    result: list[Path] = []
    for _, p in candidates:
        if p not in seen:
            seen.add(p)
            result.append(p)
            if len(result) >= max_files:
                break
    return result


def read_snippet(path: Path, *, max_chars: int = MAX_SNIPPET_CHARS) -> str | None:
    """Read a text snippet from *path*, respecting size limits.

    Returns ``None`` if the file is binary or too large.
    """
    try:
        size = path.stat().st_size
    except OSError:
        return None

    if size > MAX_FILE_SIZE_BYTES:
        return None

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    if len(text) > max_chars:
        text = text[:max_chars] + "\n... (truncated)"
    return text


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _iter_source_files(root: Path):
    """Yield all non-ignored files under *root* recursively."""
    for entry in root.rglob("*"):
        if not entry.is_file():
            continue
        # Skip ignored directories anywhere in the path
        parts = set(entry.relative_to(root).parts)
        if parts & IGNORE_DIRS:
            continue
        # Skip if any parent starts with a dot
        rel_parts = entry.relative_to(root).parts
        if any(p.startswith(".") for p in rel_parts[:-1]):
            continue
        if entry.suffix.lower() in IGNORE_EXTENSIONS:
            continue
        yield entry
