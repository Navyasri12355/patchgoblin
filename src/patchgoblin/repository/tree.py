"""Repository file-tree builder with depth and entry limits."""

from __future__ import annotations

from pathlib import Path

from patchgoblin.repository.relevance import IGNORE_DIRS, IGNORE_EXTENSIONS

# Limits that prevent giant trees from overwhelming prompts
MAX_DEPTH = 4
MAX_ENTRIES_PER_DIR = 40
MAX_TOTAL_ENTRIES = 300


def build_tree(root: Path, *, max_depth: int = MAX_DEPTH) -> str:
    """Return a human-readable directory tree rooted at *root*.

    Ignores generated/vendored directories and binary file types.
    Limits total entries to avoid extremely large strings.
    """
    lines: list[str] = []
    _walk(root, root, depth=0, max_depth=max_depth, lines=lines, total=[0])
    return "\n".join(lines)


def _walk(
    root: Path,
    current: Path,
    *,
    depth: int,
    max_depth: int,
    lines: list[str],
    total: list[int],
) -> None:
    if total[0] >= MAX_TOTAL_ENTRIES:
        return
    if depth >= max_depth:
        return

    try:
        entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return

    entry_count = 0
    for entry in entries:
        if total[0] >= MAX_TOTAL_ENTRIES:
            lines.append("  " * depth + "... (truncated)")
            break
        if entry_count >= MAX_ENTRIES_PER_DIR:
            lines.append("  " * depth + f"... ({len(list(current.iterdir())) - entry_count} more)")
            break

        rel = entry.relative_to(root)
        indent = "  " * depth

        if entry.is_dir():
            if entry.name in IGNORE_DIRS or entry.name.startswith("."):
                continue
            lines.append(f"{indent}{entry.name}/")
            total[0] += 1
            entry_count += 1
            _walk(root, entry, depth=depth + 1, max_depth=max_depth, lines=lines, total=total)
        elif entry.is_file():
            if entry.suffix.lower() in IGNORE_EXTENSIONS:
                continue
            lines.append(f"{indent}{rel.name}")
            total[0] += 1
            entry_count += 1
