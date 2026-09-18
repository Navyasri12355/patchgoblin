"""Tests for repository inspection utilities."""

from __future__ import annotations

from pathlib import Path

from patchgoblin.repository.relevance import (
    IGNORE_DIRS,
    extract_keywords,
    find_relevant_files,
    read_snippet,
    score_file,
)
from patchgoblin.repository.tree import build_tree

# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------


def test_extract_keywords_basic():
    kws = extract_keywords("Fix authentication timeout handling in the client")
    assert "authentication" in kws
    assert "timeout" in kws
    assert "handling" in kws
    # Stopwords removed
    assert "the" not in kws
    assert "in" not in kws


def test_extract_keywords_deduplicates():
    kws = extract_keywords("auth auth auth")
    assert kws.count("auth") == 1


def test_extract_keywords_returns_lowercase():
    kws = extract_keywords("ConfigurationError")
    assert "configurationerror" in kws or "configuration" in kws or "configurationerror" in kws


# ---------------------------------------------------------------------------
# Tree builder
# ---------------------------------------------------------------------------


def test_build_tree_simple(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("# main")
    (tmp_path / "README.md").write_text("# readme")

    tree = build_tree(tmp_path)
    assert "main.py" in tree
    assert "README.md" in tree


def test_build_tree_ignores_git_directory(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("fake")
    (tmp_path / "app.py").write_text("# app")

    tree = build_tree(tmp_path)
    assert ".git" not in tree
    assert "app.py" in tree


def test_build_tree_ignores_pycache(tmp_path: Path):
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    (pycache / "main.cpython-312.pyc").write_bytes(b"\x00\x01")
    (tmp_path / "main.py").write_text("# main")

    tree = build_tree(tmp_path)
    assert "__pycache__" not in tree


def test_build_tree_depth_limit(tmp_path: Path):
    # Create a deep nesting
    deep = tmp_path
    for _ in range(6):
        deep = deep / "subdir"
        deep.mkdir()
    (deep / "deep_file.py").write_text("# deep")

    tree = build_tree(tmp_path, max_depth=2)
    # deep_file.py is beyond max depth — should not appear
    assert "deep_file.py" not in tree


# ---------------------------------------------------------------------------
# Relevance scoring
# ---------------------------------------------------------------------------


def test_score_file_source_extension(tmp_path: Path):
    f = tmp_path / "config.py"
    f.write_text("# config")
    score = score_file(f, tmp_path, ["config"])
    assert score > 0


def test_score_file_test_directory_bonus(tmp_path: Path):
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    f = test_dir / "test_config.py"
    f.write_text("# tests")
    score = score_file(f, tmp_path, ["config"])
    # Should have source + test + keyword match
    assert score >= 10


def test_score_file_keyword_match_boosts_score(tmp_path: Path):
    f = tmp_path / "auth_handler.py"
    f.write_text("# auth")
    score_match = score_file(f, tmp_path, ["auth"])
    score_no_match = score_file(f, tmp_path, ["database"])
    assert score_match > score_no_match


# ---------------------------------------------------------------------------
# Relevant file discovery
# ---------------------------------------------------------------------------


def test_find_relevant_files_returns_matching_files(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.py").write_text("# auth module")
    (src / "database.py").write_text("# database module")
    (tmp_path / "README.md").write_text("# project readme")

    files = find_relevant_files(tmp_path, ["auth"])
    paths = [str(f.relative_to(tmp_path)).replace("\\", "/") for f in files]
    assert any("auth" in p for p in paths)


def test_find_relevant_files_respects_max(tmp_path: Path):
    for i in range(20):
        (tmp_path / f"module_{i}.py").write_text(f"# module {i} config auth")
    files = find_relevant_files(tmp_path, ["config", "auth"], max_files=5)
    assert len(files) <= 5


def test_find_relevant_files_ignores_node_modules(tmp_path: Path):
    nm = tmp_path / "node_modules"
    nm.mkdir()
    (nm / "package.js").write_text("// npm")
    (tmp_path / "app.py").write_text("# app auth")
    files = find_relevant_files(tmp_path, ["auth"])
    for f in files:
        assert "node_modules" not in str(f)


def test_find_relevant_files_ignores_binary_extensions(tmp_path: Path):
    (tmp_path / "image.png").write_bytes(b"\x89PNG")
    (tmp_path / "source.py").write_text("# auth")
    files = find_relevant_files(tmp_path, ["auth"])
    for f in files:
        assert f.suffix != ".png"


# ---------------------------------------------------------------------------
# Snippet reading
# ---------------------------------------------------------------------------


def test_read_snippet_returns_content(tmp_path: Path):
    f = tmp_path / "app.py"
    f.write_text("def hello(): pass")
    content = read_snippet(f)
    assert content is not None
    assert "hello" in content


def test_read_snippet_truncates_large_file(tmp_path: Path):
    f = tmp_path / "large.py"
    f.write_text("x" * 10_000)
    content = read_snippet(f, max_chars=100)
    assert content is not None
    assert len(content) <= 120  # 100 chars + truncation marker


def test_read_snippet_returns_none_for_oversized_file(tmp_path: Path):
    f = tmp_path / "huge.py"
    f.write_bytes(b"a" * 100_001)
    content = read_snippet(f)
    assert content is None


# ---------------------------------------------------------------------------
# IGNORE_DIRS sanity check
# ---------------------------------------------------------------------------


def test_ignore_dirs_contains_key_patterns():
    assert ".git" in IGNORE_DIRS
    assert "node_modules" in IGNORE_DIRS
    assert "__pycache__" in IGNORE_DIRS
    assert ".venv" in IGNORE_DIRS
