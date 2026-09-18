"""File editor — applies structured edits inside a workspace.

All paths are validated.  Binary files and oversized writes are rejected.
Only approved extensions may be written.
"""

from __future__ import annotations

from pathlib import Path

from patchgoblin.coding.models import EditOperation, FileEdit
from patchgoblin.workspace.safety import (
    MAX_WRITE_BYTES,
    PathTraversalError,
    is_allowed_extension,
    validate_workspace_path,
)


class EditError(Exception):
    """Raised when an edit cannot be applied safely."""


class FileEditor:
    """Applies :class:`~patchgoblin.coding.models.FileEdit` objects inside a workspace.

    The editor enforces:
    - Path-traversal protection
    - Allowed file extensions
    - File-size limits
    - Scope restrictions (approved files only)
    """

    def __init__(
        self,
        workspace_root: Path,
        approved_files: list[str],
    ) -> None:
        self._root = workspace_root.resolve()
        # Normalise to forward-slash relative paths for consistent comparison
        self._approved = {f.replace("\\", "/") for f in approved_files}

    def apply(self, edit: FileEdit) -> None:
        """Apply a single :class:`~patchgoblin.coding.models.FileEdit`.

        Raises
        ------
        EditError
            For any policy violation or I/O failure.
        """
        # --- Scope check ---
        norm_path = edit.path.replace("\\", "/")
        if norm_path not in self._approved:
            raise EditError(
                f"File {edit.path!r} is not in the approved scope. "
                f"Approved files: {sorted(self._approved)}"
            )

        # --- Extension check ---
        if not is_allowed_extension(edit.path):
            raise EditError(
                f"File extension {Path(edit.path).suffix!r} is not allowed for writing."
            )

        # --- Path safety ---
        try:
            abs_path = validate_workspace_path(edit.path, self._root)
        except PathTraversalError as exc:
            raise EditError(str(exc)) from exc

        # --- Dispatch ---
        if edit.operation == EditOperation.WRITE_FILE:
            self._write_file(abs_path, edit.content)
        elif edit.operation == EditOperation.REPLACE_LINES:
            self._replace_lines(abs_path, edit.start_line, edit.end_line, edit.content)
        elif edit.operation == EditOperation.INSERT_AFTER:
            self._insert_after(abs_path, edit.start_line, edit.content)
        else:
            raise EditError(f"Unknown edit operation: {edit.operation!r}")

    def apply_all(self, edits: list[FileEdit]) -> list[str]:
        """Apply a list of edits in order.  Returns relative paths of modified files.

        Raises :class:`EditError` on the first failure.
        """
        modified: list[str] = []
        for edit in edits:
            self.apply(edit)
            rel = edit.path.replace("\\", "/")
            if rel not in modified:
                modified.append(rel)
        return modified

    # ------------------------------------------------------------------
    # Internal edit implementations
    # ------------------------------------------------------------------

    def _write_file(self, abs_path: Path, content: str) -> None:
        """Write *content* to *abs_path*, creating parent directories as needed."""
        if len(content.encode("utf-8")) > MAX_WRITE_BYTES:
            raise EditError(
                f"Content for {abs_path.name!r} exceeds the {MAX_WRITE_BYTES:,}-byte write limit."
            )
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content, encoding="utf-8")

    def _replace_lines(self, abs_path: Path, start: int, end: int, replacement: str) -> None:
        """Replace lines *start*–*end* (1-based inclusive) with *replacement*."""
        if start < 1 or end < start:
            raise EditError(
                f"Invalid line range [{start}, {end}] for replace_lines on {abs_path.name!r}. "
                "start_line must be >= 1 and <= end_line."
            )
        if not abs_path.exists():
            raise EditError(f"File not found for replace_lines: {abs_path}")

        lines = abs_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        total = len(lines)

        if start > total:
            raise EditError(
                f"start_line {start} exceeds file length {total} for {abs_path.name!r}."
            )
        end = min(end, total)

        new_content_lines = replacement.splitlines(keepends=True)
        # Ensure last replacement line ends with newline
        if new_content_lines and not new_content_lines[-1].endswith("\n"):
            new_content_lines[-1] += "\n"

        new_lines = lines[: start - 1] + new_content_lines + lines[end:]
        new_text = "".join(new_lines)
        self._check_write_size(abs_path, new_text)
        abs_path.write_text(new_text, encoding="utf-8")

    def _insert_after(self, abs_path: Path, after_line: int, content: str) -> None:
        """Insert *content* after line *after_line* (0 = prepend before line 1)."""
        if after_line < 0:
            raise EditError(
                f"insert_after line must be >= 0, got {after_line} for {abs_path.name!r}."
            )

        if abs_path.exists():
            lines = abs_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        else:
            lines = []

        insert_lines = content.splitlines(keepends=True)
        if insert_lines and not insert_lines[-1].endswith("\n"):
            insert_lines[-1] += "\n"

        pos = min(after_line, len(lines))
        new_lines = lines[:pos] + insert_lines + lines[pos:]
        new_text = "".join(new_lines)
        self._check_write_size(abs_path, new_text)
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(new_text, encoding="utf-8")

    @staticmethod
    def _check_write_size(abs_path: Path, text: str) -> None:
        if len(text.encode("utf-8")) > MAX_WRITE_BYTES:
            raise EditError(
                f"Resulting file {abs_path.name!r} would exceed the "
                f"{MAX_WRITE_BYTES:,}-byte write limit."
            )
