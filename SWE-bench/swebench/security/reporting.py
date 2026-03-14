"""
VulnAgentBench reporting — generates per-track and per-CWE summaries from result files.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def generate_report(
    results_dir: Path,
    run_id: str,
    output_dir: Path | None = None,
) -> dict:
    """
    Read per-instance result JSON files from results_dir, compute aggregate
    statistics, print a summary table, and save report.json.

    Returns the report dict.
    """
    result_files = sorted(results_dir.glob("*.json"))
    if not result_files:
        print("No result files found.")
        return {}

    results = []
    for f in result_files:
        try:
            results.append(json.loads(f.read_text()))
        except Exception:
            pass

    report = _build_report(results, run_id)

    if output_dir:
        report_path = output_dir / "logs" / run_id / "report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2))

    _print_report(report)
    return report


def _build_report(results: list[dict], run_id: str) -> dict:
    """Compute per-track scores and per-CWE detection rates."""
    by_track: dict[int, list[dict]] = defaultdict(list)
    for r in results:
        by_track[r.get("track", 0)].append(r)

    track_summaries = {}
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

    # Per-CWE detection rate
    cwe_stats: dict[str, dict] = defaultdict(lambda: {"found": 0, "total": 0})
    for r in results:
        project_id = r.get("project_id", "")
        raw_findings = r.get("raw_findings", [])
        found_cwes = {f.get("cwe_id", "").upper() for f in raw_findings}

        # Load ground truth to know which CWEs were present
        from swebench.security.dataset import PROJECTS_DIR
        gt_path = PROJECTS_DIR / project_id / "ground_truth.json"
        if gt_path.exists():
            gt = json.loads(gt_path.read_text())
            for entry in gt:
                cwe = entry.get("cwe_id", "").upper()
                cwe_stats[cwe]["total"] += 1
                if cwe in found_cwes:
                    cwe_stats[cwe]["found"] += 1

    cwe_detection_rates = {
        cwe: {
            "found": stats["found"],
            "total": stats["total"],
            "detection_rate": round(stats["found"] / stats["total"], 4) if stats["total"] else 0.0,
        }
        for cwe, stats in sorted(cwe_stats.items())
    }

    overall_n = len(results)
    overall_f1 = sum(r.get("f1", 0.0) for r in results) / overall_n if overall_n else 0.0
    overall_precision = sum(r.get("precision", 0.0) for r in results) / overall_n if overall_n else 0.0
    overall_recall = sum(r.get("recall", 0.0) for r in results) / overall_n if overall_n else 0.0

    return {
        "run_id": run_id,
        "num_instances": overall_n,
        "overall_avg_f1": round(overall_f1, 4),
        "overall_avg_precision": round(overall_precision, 4),
        "overall_avg_recall": round(overall_recall, 4),
        "by_track": track_summaries,
        "cwe_detection_rates": cwe_detection_rates,
    }


def _print_report(report: dict) -> None:
    """Print a human-readable summary table."""
    print("\n" + "=" * 60)
    print(f"VulnAgentBench Results — run_id: {report.get('run_id', '?')}")
    print("=" * 60)
    print(
        f"Overall  F1={report['overall_avg_f1']:.3f}  "
        f"P={report['overall_avg_precision']:.3f}  "
        f"R={report['overall_avg_recall']:.3f}  "
        f"({report['num_instances']} instances)"
    )

    print("\nPer-Track Scores:")
    print(f"  {'Track':<10} {'F1':>6} {'Precision':>10} {'Recall':>8} {'TP':>4} {'FP':>4} {'FN':>4}")
    print("  " + "-" * 50)
    for track_key, s in sorted(report.get("by_track", {}).items()):
        print(
            f"  {track_key:<10} {s['avg_f1']:>6.3f} {s['avg_precision']:>10.3f} "
            f"{s['avg_recall']:>8.3f} {s['total_true_positives']:>4} "
            f"{s['total_false_positives']:>4} {s['total_false_negatives']:>4}"
        )

    print("\nPer-CWE Detection Rates:")
    print(f"  {'CWE':<12} {'Found':>6} {'Total':>6} {'Rate':>8}")
    print("  " + "-" * 35)
    for cwe, stats in sorted(report.get("cwe_detection_rates", {}).items()):
        print(
            f"  {cwe:<12} {stats['found']:>6} {stats['total']:>6} "
            f"{stats['detection_rate']:>8.3f}"
        )
    print("=" * 60 + "\n")
