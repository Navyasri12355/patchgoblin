"""Tests for the IssueAnalysis and ImplementationPlan models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from patchgoblin.models.analysis import ConfidenceLevel, FileEvidence, IssueAnalysis


def test_valid_issue_analysis():
    data = {
        "summary": "Fix the thing",
        "problem": "It breaks",
        "expected_behavior": "Works",
        "current_behavior": "Does not work",
        "likely_components": ["auth", "config"],
        "likely_files": [{"path": "src/auth.py", "reason": "handles auth"}],
        "implementation_steps": ["step 1", "step 2"],
        "testing_strategy": "Add a unit test",
        "potential_risks": ["backward compat"],
        "unknowns": ["whether this is intentional"],
        "confidence": "high",
    }
    analysis = IssueAnalysis.model_validate(data)
    assert analysis.summary == "Fix the thing"
    assert analysis.confidence == ConfidenceLevel.HIGH
    assert len(analysis.likely_files) == 1
    assert analysis.likely_files[0].path == "src/auth.py"


def test_confidence_case_insensitive():
    analysis = IssueAnalysis(summary="test", confidence="HIGH")  # type: ignore[arg-type]
    assert analysis.confidence == ConfidenceLevel.HIGH


def test_confidence_medium_default():
    analysis = IssueAnalysis(summary="test")
    assert analysis.confidence == ConfidenceLevel.MEDIUM


def test_invalid_confidence_raises():
    with pytest.raises(ValidationError):
        IssueAnalysis(summary="test", confidence="very-high")  # type: ignore[arg-type]


def test_missing_summary_raises():
    with pytest.raises(ValidationError):
        IssueAnalysis.model_validate({})


def test_all_optional_fields_default_to_empty():
    analysis = IssueAnalysis(summary="minimal")
    assert analysis.problem == ""
    assert analysis.likely_components == []
    assert analysis.likely_files == []
    assert analysis.implementation_steps == []
    assert analysis.unknowns == []


def test_file_evidence_model():
    f = FileEvidence(path="src/config.py", reason="handles config")
    assert f.path == "src/config.py"
    assert f.reason == "handles config"
