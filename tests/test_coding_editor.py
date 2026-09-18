"""Tests for the FileEditor (applies structured edits inside a workspace)."""

from __future__ import annotations

from pathlib import Path

import pytest

from patchgoblin.coding.editor import EditError, FileEditor
from patchgoblin.coding.models import EditOperation, FileEdit


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    return root


@pytest.fixture()
def editor(workspace: Path) -> FileEditor:
    return FileEditor(workspace, approved_files=["src/main.py", "README.md", "src/new.py"])


class TestWriteFile:
    def test_write_new_file(self, editor: FileEditor, workspace: Path) -> None:
        edit = FileEdit(
            path="src/new.py",
            operation=EditOperation.WRITE_FILE,
            content="print('hello')\n",
        )
        editor.apply(edit)
        assert (workspace / "src" / "new.py").read_text() == "print('hello')\n"

    def test_write_creates_parent_dirs(self, editor: FileEditor, workspace: Path) -> None:
        edit = FileEdit(
            path="src/new.py",
            operation=EditOperation.WRITE_FILE,
            content="x = 1\n",
        )
        editor.apply(edit)
        assert (workspace / "src" / "new.py").exists()

    def test_write_unapproved_file_raises(self, editor: FileEditor) -> None:
        edit = FileEdit(
            path="secret.py",
            operation=EditOperation.WRITE_FILE,
            content="x = 1\n",
        )
        with pytest.raises(EditError, match="not in the approved scope"):
            editor.apply(edit)

    def test_write_disallowed_extension_raises(self, workspace: Path) -> None:
        ed = FileEditor(workspace, approved_files=["image.png"])
        edit = FileEdit(
            path="image.png",
            operation=EditOperation.WRITE_FILE,
            content="binary",
        )
        with pytest.raises(EditError, match="not allowed"):
            ed.apply(edit)

    def test_write_path_traversal_raises(self, editor: FileEditor) -> None:
        edit = FileEdit(
            path="../../etc/passwd",
            operation=EditOperation.WRITE_FILE,
            content="data",
        )
        with pytest.raises(EditError):
            editor.apply(edit)


class TestReplaceLines:
    def test_replace_single_line(self, editor: FileEditor, workspace: Path) -> None:
        src = workspace / "src" / "main.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("line1\nline2\nline3\n")
        edit = FileEdit(
            path="src/main.py",
            operation=EditOperation.REPLACE_LINES,
            start_line=2,
            end_line=2,
            content="REPLACED\n",
        )
        editor.apply(edit)
        assert src.read_text() == "line1\nREPLACED\nline3\n"

    def test_replace_multiple_lines(self, editor: FileEditor, workspace: Path) -> None:
        src = workspace / "src" / "main.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("a\nb\nc\nd\n")
        edit = FileEdit(
            path="src/main.py",
            operation=EditOperation.REPLACE_LINES,
            start_line=2,
            end_line=3,
            content="X\nY\n",
        )
        editor.apply(edit)
        assert src.read_text() == "a\nX\nY\nd\n"

    def test_replace_missing_file_raises(self, editor: FileEditor, workspace: Path) -> None:
        edit = FileEdit(
            path="src/main.py",
            operation=EditOperation.REPLACE_LINES,
            start_line=1,
            end_line=1,
            content="x\n",
        )
        with pytest.raises(EditError, match="not found"):
            editor.apply(edit)

    def test_replace_invalid_line_range_raises(self, editor: FileEditor, workspace: Path) -> None:
        src = workspace / "src" / "main.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("a\nb\n")
        edit = FileEdit(
            path="src/main.py",
            operation=EditOperation.REPLACE_LINES,
            start_line=0,  # invalid: must be >= 1
            end_line=1,
            content="x\n",
        )
        with pytest.raises(EditError, match="Invalid line range"):
            editor.apply(edit)

    def test_replace_start_exceeds_file_raises(self, editor: FileEditor, workspace: Path) -> None:
        src = workspace / "src" / "main.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("one line\n")
        edit = FileEdit(
            path="src/main.py",
            operation=EditOperation.REPLACE_LINES,
            start_line=99,
            end_line=100,
            content="x\n",
        )
        with pytest.raises(EditError, match="exceeds file length"):
            editor.apply(edit)


class TestInsertAfter:
    def test_insert_in_middle(self, editor: FileEditor, workspace: Path) -> None:
        src = workspace / "src" / "main.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("a\nb\nc\n")
        edit = FileEdit(
            path="src/main.py",
            operation=EditOperation.INSERT_AFTER,
            start_line=1,
            content="INSERTED\n",
        )
        editor.apply(edit)
        assert src.read_text() == "a\nINSERTED\nb\nc\n"

    def test_insert_at_top(self, editor: FileEditor, workspace: Path) -> None:
        src = workspace / "src" / "main.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("a\nb\n")
        edit = FileEdit(
            path="src/main.py",
            operation=EditOperation.INSERT_AFTER,
            start_line=0,
            content="TOP\n",
        )
        editor.apply(edit)
        assert src.read_text() == "TOP\na\nb\n"


class TestApplyAll:
    def test_multiple_edits_returns_modified_paths(
        self, editor: FileEditor, workspace: Path
    ) -> None:
        src = workspace / "src" / "main.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("line1\nline2\n")

        edits = [
            FileEdit(
                path="src/main.py",
                operation=EditOperation.REPLACE_LINES,
                start_line=1,
                end_line=1,
                content="UPDATED\n",
            ),
            FileEdit(
                path="README.md",
                operation=EditOperation.WRITE_FILE,
                content="# Title\n",
            ),
        ]
        modified = editor.apply_all(edits)
        assert "src/main.py" in modified
        assert "README.md" in modified

    def test_unapproved_file_in_batch_raises(self, editor: FileEditor) -> None:
        edits = [
            FileEdit(
                path="unauthorized.py",
                operation=EditOperation.WRITE_FILE,
                content="x\n",
            )
        ]
        with pytest.raises(EditError, match="not in the approved scope"):
            editor.apply_all(edits)
