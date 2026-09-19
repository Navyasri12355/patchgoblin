"""Test output parser for structured result extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass

from patchgoblin.testing.models import TestingLanguage


class ParseError(Exception):
    """Raised when test output parsing fails."""


@dataclass
class ParsedTestResults:
    """Parsed test results."""

    test_count: int | None = None
    failure_count: int | None = None
    error_count: int | None = None
    skipped_count: int | None = None


class TestParser:
    """Parses test output to extract structured results."""

    # Regex patterns for different test frameworks
    PATTERNS = {
        TestingLanguage.PYTHON: {
            "pytest": [
                r"(\d+) passed",
                r"(\d+) failed",
                r"(\d+) error",
                r"(\d+) skipped",
            ],
            "unittest": [
                r"Ran (\d+) test",
                r"FAILED \(failures=(\d+)\)",
                r"ERROR\(errors=(\d+)\)",
            ],
        },
        TestingLanguage.NODE: {
            "jest": [
                r"Tests:\s+(\d+)",
                r"Failed:\s+(\d+)",
            ],
            "mocha": [
                r"passing:\s+(\d+)",
                r"failing:\s+(\d+)",
            ],
        },
    }

    def parse(self, output: str, language: TestingLanguage) -> dict[str, int | None]:
        """Parse test output and extract structured results.

        Args:
            output: Combined stdout/stderr from test execution.
            language: Detected programming language.

        Returns:
            Dictionary with test_count, failure_count, error_count, skipped_count.
            Values are None if not found in output.
        """
        result = {
            "test_count": None,
            "failure_count": None,
            "error_count": None,
            "skipped_count": None,
        }

        if language == TestingLanguage.PYTHON:
            self._parse_python(output, result)
        elif language == TestingLanguage.NODE:
            self._parse_node(output, result)
        # For UNKNOWN, return all None

        return result

    def _parse_python(self, output: str, result: dict) -> None:
        """Parse Python test output (pytest, unittest)."""
        # Try pytest patterns first
        if "passed" in output.lower() or "failed" in output.lower():
            match = re.search(r"(\d+) passed", output)
            if match:
                result["test_count"] = int(match.group(1))

            match = re.search(r"(\d+) failed", output)
            if match:
                result["failure_count"] = int(match.group(1))

            match = re.search(r"(\d+) error", output, re.IGNORECASE)
            if match:
                result["error_count"] = int(match.group(1))

            match = re.search(r"(\d+) skipped", output, re.IGNORECASE)
            if match:
                result["skipped_count"] = int(match.group(1))

        # Try unittest patterns
        else:
            match = re.search(r"Ran (\d+) test", output)
            if match:
                result["test_count"] = int(match.group(1))

            match = re.search(r"FAILED \(failures=(\d+)\)", output)
            if match:
                result["failure_count"] = int(match.group(1))

            match = re.search(r"ERROR\(errors=(\d+)\)", output)
            if match:
                result["error_count"] = int(match.group(1))

    def _parse_node(self, output: str, result: dict) -> None:
        """Parse Node.js test output (jest, mocha)."""
        # Try jest patterns
        if "Tests:" in output or "tests:" in output.lower():
            match = re.search(r"Tests?:\s+(\d+)", output, re.IGNORECASE)
            if match:
                result["test_count"] = int(match.group(1))

            match = re.search(r"Failed:\s+(\d+)", output)
            if match:
                result["failure_count"] = int(match.group(1))

        # Try mocha patterns
        elif "passing:" in output or "failing:" in output:
            match = re.search(r"passing:\s+(\d+)", output)
            if match:
                result["test_count"] = int(match.group(1))

            match = re.search(r"failing:\s+(\d+)", output)
            if match:
                result["failure_count"] = int(match.group(1))
