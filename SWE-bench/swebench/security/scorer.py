from __future__ import annotations

import json
import os
import subprocess
import tempfile
import warnings
from pathlib import Path

LINE_TOLERANCE = 5


def score_instance(
    findings: list[dict],
    ground_truth_path: Path,
    track: int,
    patch: str | None = None,
) -> dict:
    """
    Score agent findings against ground truth for a single instance.

    Returns a dict with TP, FP, FN, precision, recall, F1, and for track 3
    the count of new vulnerabilities introduced.
    """
    ground_truth = json.loads(ground_truth_path.read_text())

    matched_gt: set[int] = set()
    matched_findings: set[int] = set()

    for fi, finding in enumerate(findings):
        for gi, gt in enumerate(ground_truth):
            if gi in matched_gt:
                continue
            if _matches(finding, gt):
                matched_gt.add(gi)
                matched_findings.add(fi)
                break

    tp = len(matched_gt)
    fp = len(findings) - len(matched_findings)
    fn = len(ground_truth) - tp

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    result = {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "vulnerabilities_found": len(findings),
        "ground_truth_total": len(ground_truth),
    }

    if track == 3 and patch:
        result["new_vulnerabilities_introduced"] = _run_semgrep_on_patch(patch)
    else:
        result["new_vulnerabilities_introduced"] = 0

    return result


def _matches(finding: dict, gt: dict) -> bool:
    """Check if a finding matches a ground truth entry (file + CWE + fuzzy line)."""
    finding_file = finding.get("file", "").lstrip("/").lstrip("./")
    gt_file = gt.get("file", "").lstrip("/").lstrip("./")
    if finding_file != gt_file:
        return False

    finding_cwe = finding.get("cwe_id", "").strip().upper()
    gt_cwe = gt.get("cwe_id", "").strip().upper()
    if finding_cwe != gt_cwe:
        return False

    finding_line = finding.get("line", 0)
    gt_line_start = gt.get("line_start", gt.get("line", 0))
    gt_line_end = gt.get("line_end", gt_line_start)

    return (
        abs(finding_line - gt_line_start) <= LINE_TOLERANCE
        or abs(finding_line - gt_line_end) <= LINE_TOLERANCE
        or (gt_line_start <= finding_line <= gt_line_end)
    )


def _run_semgrep_on_patch(patch: str) -> int:
    """
    Run semgrep on added lines from a patch to count newly introduced vulnerabilities.
    Returns 0 if semgrep is not installed or an error occurs.
    """
    try:
        check = subprocess.run(
            ["semgrep", "--version"],
            capture_output=True,
            timeout=10,
        )
        if check.returncode != 0:
            warnings.warn("semgrep check failed; skipping new-vuln detection.")
            return 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        warnings.warn("semgrep not found; skipping new-vulnerability detection for Track 3.")
        return 0

    # Extract added lines, track the last file extension seen
    added_lines: list[str] = []
    current_ext = ".py"
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            current_ext = Path(line[6:]).suffix or ".py"
        elif line.startswith("+") and not line.startswith("+++"):
            added_lines.append(line[1:])

    if not added_lines:
        return 0

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=current_ext, delete=False
    ) as tmp:
        tmp.write("\n".join(added_lines))
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["semgrep", "--config=auto", "--json", tmp_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # semgrep exits 1 when findings are found, 0 when clean
        if result.returncode not in (0, 1):
            return 0
        data = json.loads(result.stdout)
        return len(data.get("results", []))
    except Exception:
        return 0
    finally:
        os.unlink(tmp_path)


def score_run(results: list[dict]) -> dict:
    """Aggregate scores across all instances, broken down by track."""
    if not results:
        return {}

    by_track: dict[int, list[dict]] = {}
    for r in results:
        track = r.get("track", 0)
        by_track.setdefault(track, []).append(r)

    track_summaries = {}
    all_f1: list[float] = []
    all_precision: list[float] = []
    all_recall: list[float] = []

    for track, track_results in sorted(by_track.items()):
        n = len(track_results)
        avg_f1 = sum(r.get("f1", 0.0) for r in track_results) / n
        avg_precision = sum(r.get("precision", 0.0) for r in track_results) / n
        avg_recall = sum(r.get("recall", 0.0) for r in track_results) / n
        total_tp = sum(r.get("true_positives", 0) for r in track_results)
        total_fp = sum(r.get("false_positives", 0) for r in track_results)
        total_fn = sum(r.get("false_negatives", 0) for r in track_results)
        track_summaries[f"track_{track}"] = {
            "num_instances": n,
            "avg_f1": round(avg_f1, 4),
            "avg_precision": round(avg_precision, 4),
            "avg_recall": round(avg_recall, 4),
            "total_true_positives": total_tp,
            "total_false_positives": total_fp,
            "total_false_negatives": total_fn,
        }
        all_f1.extend(r.get("f1", 0.0) for r in track_results)
        all_precision.extend(r.get("precision", 0.0) for r in track_results)
        all_recall.extend(r.get("recall", 0.0) for r in track_results)

    overall_n = len(results)
    return {
        "num_instances": overall_n,
        "overall_avg_f1": round(sum(all_f1) / overall_n, 4),
        "overall_avg_precision": round(sum(all_precision) / overall_n, 4),
        "overall_avg_recall": round(sum(all_recall) / overall_n, 4),
        "by_track": track_summaries,
    }
