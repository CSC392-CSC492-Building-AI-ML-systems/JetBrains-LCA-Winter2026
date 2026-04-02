#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


NUMERIC_INT_FIELDS = [
    "iterations",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "commands_executed",
    "commands_timed_out",
    "reasoning_steps",
    "lines_added",
    "lines_removed",
]

NUMERIC_FLOAT_FIELDS = [
    "wall_clock_seconds",
    "estimated_cost_usd",
]



def to_int(value) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return 0
    return 0



def to_float(value) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0



def build_summary(metrics_records: list[dict]) -> dict:
    if not metrics_records:
        return {}

    totals_int = {k: 0 for k in NUMERIC_INT_FIELDS}
    totals_float = {k: 0.0 for k in NUMERIC_FLOAT_FIELDS}

    patches_produced = 0
    exit_reasons: dict[str, int] = {}

    for record in metrics_records:
        for key in NUMERIC_INT_FIELDS:
            totals_int[key] += to_int(record.get(key, 0))
        for key in NUMERIC_FLOAT_FIELDS:
            totals_float[key] += to_float(record.get(key, 0.0))

        if bool(record.get("patch_produced", False)):
            patches_produced += 1

        reason = record.get("exit_reason", "")
        if not isinstance(reason, str) or not reason:
            reason = "unknown"
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

    n = len(metrics_records)

    total_input = totals_int["input_tokens"]
    total_output = totals_int["output_tokens"]
    total_tokens = totals_int["total_tokens"]
    if total_tokens == 0:
        total_tokens = total_input + total_output

    total_wall = totals_float["wall_clock_seconds"]
    total_cost = totals_float["estimated_cost_usd"]

    return {
        "num_instances": n,
        "patches_produced": patches_produced,
        "patch_rate": patches_produced / n,
        "total_wall_clock_seconds": total_wall,
        "avg_wall_clock_seconds": total_wall / n,
        "total_iterations": totals_int["iterations"],
        "avg_iterations": totals_int["iterations"] / n,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_tokens,
        "avg_tokens_per_instance": total_tokens / n,
        "total_commands_executed": totals_int["commands_executed"],
        "total_commands_timed_out": totals_int["commands_timed_out"],
        "total_reasoning_steps": totals_int["reasoning_steps"],
        "avg_reasoning_steps_per_instance": totals_int["reasoning_steps"] / n,
        "total_lines_added": totals_int["lines_added"],
        "total_lines_removed": totals_int["lines_removed"],
        "total_estimated_cost_usd": total_cost,
        "avg_cost_per_instance_usd": total_cost / n,
        "exit_reasons": exit_reasons,
    }



def collect_metrics(run_logs_dir: Path) -> list[dict]:
    records: list[dict] = []

    for instance_dir in sorted(run_logs_dir.iterdir()):
        if not instance_dir.is_dir():
            continue
        metrics_path = instance_dir / "metrics.json"
        if not metrics_path.exists():
            continue
        try:
            record = json.loads(metrics_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(record, dict):
            records.append(record)

    return records



def recompute_summary(run_logs_dir: Path, summary_path: Path, dry_run: bool) -> int:
    if not run_logs_dir.exists():
        raise FileNotFoundError(f"Run logs directory not found: {run_logs_dir}")

    metrics_records = collect_metrics(run_logs_dir)
    summary = build_summary(metrics_records)

    if not summary:
        raise RuntimeError("No valid metrics.json files found.")

    if dry_run:
        print(json.dumps(summary, indent=2))
        return 0

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"Summary updated: {summary_path}")
    print(f"Instances: {summary['num_instances']}")
    print(f"Patches produced: {summary['patches_produced']}")
    print(f"Total estimated cost (USD): {summary['total_estimated_cost_usd']:.8f}")

    return 0



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recompute summary.json from per-instance metrics.json files."
    )
    parser.add_argument(
        "--run-logs-dir",
        type=Path,
        default=Path(
            "/home/rafay/Documents/github_csc398/JetBrains-LCA-Winter2026/"
            "SWE-bench/predictions/logs/my-claude-run/claude-sonnet-4-6"
        ),
        help="Directory containing per-instance folders with metrics.json.",
    )
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=Path(
            "/home/rafay/Documents/github_csc398/JetBrains-LCA-Winter2026/"
            "SWE-bench/predictions/logs/my-claude-run/summary.json"
        ),
        help="Output summary.json path.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print recomputed summary without writing file.",
    )
    return parser



def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    return recompute_summary(
        run_logs_dir=args.run_logs_dir,
        summary_path=args.summary_path,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
