"""Language and tooling detector for test execution."""

from __future__ import annotations

from pathlib import Path

from patchgoblin.testing.models import TestingLanguage


class DetectorError(Exception):
    """Raised when language detection fails."""


class LanguageDetector:
    """Detects the programming language and tooling of a repository."""

    # Language indicators (files that suggest a particular language)
    LANGUAGE_INDICATORS = {
        TestingLanguage.PYTHON: [
            "pyproject.toml",
            "setup.py",
            "requirements.txt",
            "setup.cfg",
            "Pipfile",
            "poetry.lock",
            ".python-version",
        ],
        TestingLanguage.NODE: [
            "package.json",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            "node_modules",
            ".nvmrc",
        ],
    }

    def __init__(self, workspace_path: Path):
        """Initialize with the workspace path."""
        self._workspace_path = Path(workspace_path).resolve()

    def detect(self) -> TestingLanguage:
        """Detect the programming language of the repository.

        Returns:
            TestingLanguage: The detected language, or UNKNOWN if not recognized.

        Raises:
            DetectorError: If the workspace path doesn't exist.
        """
        if not self._workspace_path.exists():
            raise DetectorError(f"Workspace path does not exist: {self._workspace_path}")

        # Check for language indicators
        for language, indicators in self.LANGUAGE_INDICATORS.items():
            for indicator in indicators:
                if (self._workspace_path / indicator).exists():
                    return language

        return TestingLanguage.UNKNOWN

    def is_supported(self) -> bool:
        """Check if the detected language is supported for sandboxed testing."""
        language = self.detect()
        return language != TestingLanguage.UNKNOWN
