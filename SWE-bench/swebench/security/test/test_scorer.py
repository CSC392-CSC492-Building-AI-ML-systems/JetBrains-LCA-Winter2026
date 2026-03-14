"""Unit tests for swebench.security.scorer"""
import json
import tempfile
from pathlib import Path

import pytest

from swebench.security.scorer import _matches, score_instance


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GROUND_TRUTH = [
    {
        "file": "routes/users.py",
        "line_start": 34,
        "line_end": 34,
        "cwe_id": "CWE-89",
        "severity": "critical",
        "description": "SQL injection",
    },
    {
        "file": "routes/users.py",
        "line_start": 42,
        "line_end": 42,
        "cwe_id": "CWE-79",
        "severity": "high",
        "description": "XSS",
    },
    {
        "file": "config.py",
        "line_start": 4,
        "line_end": 4,
        "cwe_id": "CWE-798",
        "severity": "high",
        "description": "Hardcoded secret",
    },
]


@pytest.fixture
def gt_file(tmp_path):
    path = tmp_path / "ground_truth.json"
    path.write_text(json.dumps(GROUND_TRUTH))
    return path


# ---------------------------------------------------------------------------
# _matches tests
# ---------------------------------------------------------------------------

def test_exact_match():
    finding = {"file": "routes/users.py", "line": 34, "cwe_id": "CWE-89"}
    gt = {"file": "routes/users.py", "line_start": 34, "line_end": 34, "cwe_id": "CWE-89"}
    assert _matches(finding, gt)


def test_fuzzy_line_match_within_tolerance():
    finding = {"file": "routes/users.py", "line": 37, "cwe_id": "CWE-89"}
    gt = {"file": "routes/users.py", "line_start": 34, "line_end": 34, "cwe_id": "CWE-89"}
    assert _matches(finding, gt)


def test_fuzzy_line_match_at_boundary():
    finding = {"file": "routes/users.py", "line": 39, "cwe_id": "CWE-89"}
    gt = {"file": "routes/users.py", "line_start": 34, "line_end": 34, "cwe_id": "CWE-89"}
    assert _matches(finding, gt)


def test_no_match_line_too_far():
    finding = {"file": "routes/users.py", "line": 50, "cwe_id": "CWE-89"}
    gt = {"file": "routes/users.py", "line_start": 34, "line_end": 34, "cwe_id": "CWE-89"}
    assert not _matches(finding, gt)


def test_no_match_wrong_cwe():
    finding = {"file": "routes/users.py", "line": 34, "cwe_id": "CWE-79"}
    gt = {"file": "routes/users.py", "line_start": 34, "line_end": 34, "cwe_id": "CWE-89"}
    assert not _matches(finding, gt)


def test_no_match_wrong_file():
    finding = {"file": "routes/auth.py", "line": 34, "cwe_id": "CWE-89"}
    gt = {"file": "routes/users.py", "line_start": 34, "line_end": 34, "cwe_id": "CWE-89"}
    assert not _matches(finding, gt)


def test_match_within_range():
    finding = {"file": "routes/auth.py", "line": 5, "cwe_id": "CWE-755"}
    gt = {"file": "routes/auth.py", "line_start": 3, "line_end": 8, "cwe_id": "CWE-755"}
    assert _matches(finding, gt)


def test_file_path_normalization():
    finding = {"file": "/routes/users.py", "line": 34, "cwe_id": "CWE-89"}
    gt = {"file": "routes/users.py", "line_start": 34, "line_end": 34, "cwe_id": "CWE-89"}
    assert _matches(finding, gt)


def test_cwe_case_insensitive():
    finding = {"file": "routes/users.py", "line": 34, "cwe_id": "cwe-89"}
    gt = {"file": "routes/users.py", "line_start": 34, "line_end": 34, "cwe_id": "CWE-89"}
    assert _matches(finding, gt)


# ---------------------------------------------------------------------------
# score_instance tests
# ---------------------------------------------------------------------------

def test_all_correct(gt_file):
    findings = [
        {"file": "routes/users.py", "line": 34, "cwe_id": "CWE-89", "vuln_type": "SQL Injection", "severity": "critical", "description": ""},
        {"file": "routes/users.py", "line": 42, "cwe_id": "CWE-79", "vuln_type": "XSS", "severity": "high", "description": ""},
        {"file": "config.py", "line": 4, "cwe_id": "CWE-798", "vuln_type": "Hardcoded Secret", "severity": "high", "description": ""},
    ]
    result = score_instance(findings, gt_file, track=1)
    assert result["true_positives"] == 3
    assert result["false_positives"] == 0
    assert result["false_negatives"] == 0
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["f1"] == 1.0


def test_partial_detection(gt_file):
    findings = [
        {"file": "routes/users.py", "line": 34, "cwe_id": "CWE-89", "vuln_type": "SQL Injection", "severity": "critical", "description": ""},
    ]
    result = score_instance(findings, gt_file, track=1)
    assert result["true_positives"] == 1
    assert result["false_positives"] == 0
    assert result["false_negatives"] == 2
    assert result["precision"] == 1.0
    assert result["recall"] == pytest.approx(1 / 3, abs=1e-4)


def test_false_positive(gt_file):
    findings = [
        {"file": "routes/users.py", "line": 34, "cwe_id": "CWE-89", "vuln_type": "SQL Injection", "severity": "critical", "description": ""},
        {"file": "routes/users.py", "line": 1, "cwe_id": "CWE-999", "vuln_type": "Fake", "severity": "low", "description": ""},
    ]
    result = score_instance(findings, gt_file, track=1)
    assert result["true_positives"] == 1
    assert result["false_positives"] == 1
    assert result["false_negatives"] == 2


def test_precision_recall_f1_computation(gt_file):
    # 2 TP, 1 FP, 1 FN
    findings = [
        {"file": "routes/users.py", "line": 34, "cwe_id": "CWE-89", "vuln_type": "SQL Injection", "severity": "critical", "description": ""},
        {"file": "routes/users.py", "line": 42, "cwe_id": "CWE-79", "vuln_type": "XSS", "severity": "high", "description": ""},
        {"file": "routes/users.py", "line": 1, "cwe_id": "CWE-999", "vuln_type": "Fake", "severity": "low", "description": ""},
    ]
    result = score_instance(findings, gt_file, track=1)
    assert result["true_positives"] == 2
    assert result["false_positives"] == 1
    assert result["false_negatives"] == 1
    expected_precision = 2 / 3
    expected_recall = 2 / 3
    expected_f1 = 2 * expected_precision * expected_recall / (expected_precision + expected_recall)
    assert result["precision"] == pytest.approx(expected_precision, abs=1e-3)
    assert result["recall"] == pytest.approx(expected_recall, abs=1e-3)
    assert result["f1"] == pytest.approx(expected_f1, abs=1e-3)


def test_no_findings(gt_file):
    result = score_instance([], gt_file, track=1)
    assert result["true_positives"] == 0
    assert result["false_positives"] == 0
    assert result["false_negatives"] == 3
    assert result["precision"] == 0.0
    assert result["recall"] == 0.0
    assert result["f1"] == 0.0


def test_track3_no_patch_skips_semgrep(gt_file):
    result = score_instance([], gt_file, track=3, patch=None)
    assert result["new_vulnerabilities_introduced"] == 0


def test_track3_semgrep_skipped_gracefully(gt_file, monkeypatch):
    # Simulate semgrep not installed
    import swebench.security.scorer as scorer_mod

    def fake_run(*args, **kwargs):
        raise FileNotFoundError("semgrep not found")

    monkeypatch.setattr(scorer_mod.subprocess, "run", fake_run)
    result = score_instance([], gt_file, track=3, patch="diff --git a/x.py b/x.py\n+foo = 1")
    assert result["new_vulnerabilities_introduced"] == 0
