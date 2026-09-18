"""Context builder — reads workspace files to feed to the coding agent.

All file I/O is validated through the workspace safety layer.
Credentials are never included.
"""

from __future__ import annotations

from pathlib import Path

from patchgoblin.workspace.safety import (
    MAX_READ_BYTES,
    validate_workspace_path,
)

_MAX_PROMPT_CHARS = 4_000  # per-file truncation for prompt context


class ContextBuilder:
    """Reads files from a workspace for use in coding-agent prompts.

    All paths are resolved and validated against *workspace_root* before any
    I/O is performed.
    """

    def __init__(self, workspace_root: Path) -> None:
        self._root = workspace_root.resolve()

    def read_files(self, relative_paths: list[str]) -> list[tuple[str, str]]:
        """Read a list of files and return ``(relative_path, content)`` pairs.

        Files that cannot be read, are too large, or are binary are skipped
        with a placeholder message in the content.
        """
        results: list[tuple[str, str]] = []
        for rel in relative_paths:
            content = self._read_one(rel)
            results.append((rel, content))
        return results

    def _read_one(self, rel_path: str) -> str:
        try:
            abs_path = validate_workspace_path(rel_path, self._root)
        except ValueError as exc:
            return f"[PatchGoblin: path rejected — {exc}]"

        if not abs_path.exists():
            return "[PatchGoblin: file does not exist]"

        if not abs_path.is_file():
            return "[PatchGoblin: path is not a regular file]"

        try:
            size = abs_path.stat().st_size
        except OSError:
            return "[PatchGoblin: could not stat file]"

        if size > MAX_READ_BYTES:
            return (
                f"[PatchGoblin: file is {size:,} bytes which exceeds the "
                f"{MAX_READ_BYTES:,}-byte read limit. "
                "Provide a more targeted path or split the investigation.]"
            )

        try:
            text = abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"[PatchGoblin: could not read file — {exc}]"

        if len(text) > _MAX_PROMPT_CHARS:
            text = text[:_MAX_PROMPT_CHARS] + "\n... (truncated by PatchGoblin)"
        return text
