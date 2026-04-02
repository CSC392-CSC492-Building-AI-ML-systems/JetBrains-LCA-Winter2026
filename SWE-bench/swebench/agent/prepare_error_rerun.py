#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class MetricsRecord:
    instance_id: str
    model_name_or_path: str
    exit_reason: str


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _collect_metrics(run_dir: Path) -> tuple[list[MetricsRecord], list[str]]:
    records: list[MetricsRecord] = []
    model_dirs: list[str] = []

    for candidate in sorted(run_dir.iterdir()):
        if not candidate.is_dir():
            continue
        if candidate.name.startswith("."):
            continue
        model_dirs.append(candidate.name)

        for instance_dir in sorted(candidate.iterdir()):
            if not instance_dir.is_dir():
                continue
            metrics_path = instance_dir / "metrics.json"
            if not metrics_path.exists():
                continue
            payload = _read_json(metrics_path)
            instance_id = str(payload.get("instance_id", instance_dir.name))
            model_name_or_path = str(
                payload.get("model_name_or_path", candidate.name)
            )
            exit_reason = str(payload.get("exit_reason", ""))
            records.append(
                MetricsRecord(
                    instance_id=instance_id,
                    model_name_or_path=model_name_or_path,
                    exit_reason=exit_reason,
                )
            )
    return records, model_dirs


def _default_run_id(base_name: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    return f"{base_name}-linux-rerun-{stamp}"


def _build_rerun_command(
    *,
    dataset_name: str,
    split: str,
    agent: str,
    model_name_or_path: str,
    output_dir: str,
    run_id: str,
    max_workers: int,
    max_iterations: int,
    instance_ids_file: Path,
    command_workdir: Path,
) -> str:
    return (
        f"cd {json.dumps(str(command_workdir))} && "
        "python3 -m swebench.agent.run_agent "
        f"--dataset_name {json.dumps(dataset_name)} "
        f"--split {json.dumps(split)} "
        f"--agent {json.dumps(agent)} "
        f"--model_name_or_path {json.dumps(model_name_or_path)} "
        f"--output_dir {json.dumps(output_dir)} "
        f"--run_id {json.dumps(run_id)} "
        f"--max_workers {max_workers} "
        f"--max_iterations {max_iterations} "
        "--instance_ids $(tr '\\n' ' ' < "
        f"{json.dumps(str(instance_ids_file))})"
    )


def prepare(args: argparse.Namespace) -> int:
    run_dir = args.run_dir.resolve()
    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    summary_path = run_dir / "summary.json"
    predictions_path = run_dir / "predictions.jsonl"
    if not summary_path.exists():
        raise FileNotFoundError(f"Missing summary.json at: {summary_path}")
    if not predictions_path.exists():
        raise FileNotFoundError(f"Missing predictions.jsonl at: {predictions_path}")

    summary = _read_json(summary_path)
    metrics_records, model_dirs = _collect_metrics(run_dir)
    if not metrics_records:
        raise RuntimeError("No metrics.json files found under model folders.")

    target_reason = args.exit_reason
    error_records = [m for m in metrics_records if m.exit_reason == target_reason]
    error_ids = sorted({m.instance_id for m in error_records})

    expected_errors = (
        summary.get("exit_reasons", {}).get(target_reason)
        if isinstance(summary.get("exit_reasons"), dict)
        else None
    )

    predictions = _read_jsonl(predictions_path)
    by_instance = {str(row.get("instance_id", "")): row for row in predictions}
    filtered_predictions = [by_instance[iid] for iid in error_ids if iid in by_instance]

    model_name_or_path = args.model_name_or_path
    if not model_name_or_path:
        if filtered_predictions:
            model_name_or_path = str(
                filtered_predictions[0].get("model_name_or_path", "")
            )
        else:
            model_name_or_path = metrics_records[0].model_name_or_path

    output_dir = args.output_dir.resolve()
    prep_dir = output_dir / args.prep_name
    prep_dir.mkdir(parents=True, exist_ok=True)

    ids_file = prep_dir / "error_instance_ids.txt"
    ids_file.write_text("\n".join(error_ids) + ("\n" if error_ids else ""), encoding="utf-8")

    filtered_predictions_path = prep_dir / "error_subset_predictions.jsonl"
    _write_jsonl(filtered_predictions_path, filtered_predictions)

    run_id = args.new_run_id or _default_run_id(run_dir.name)
    if args.command_workdir:
        command_workdir = Path(args.command_workdir).resolve()
    else:
        command_workdir = run_dir.parents[2]

    rerun_command = _build_rerun_command(
        dataset_name=args.dataset_name,
        split=args.split,
        agent=args.agent,
        model_name_or_path=model_name_or_path,
        output_dir=args.run_agent_output_dir,
        run_id=run_id,
        max_workers=args.max_workers,
        max_iterations=args.max_iterations,
        instance_ids_file=ids_file,
        command_workdir=command_workdir,
    )

    command_file = prep_dir / "rerun_command.sh"
    command_file.write_text(rerun_command + "\n", encoding="utf-8")

    prompt_text = (
        "Run only failed instances from imported run logs.\n"
        f"run_source: {run_dir}\n"
        f"new_run_id: {run_id}\n"
        f"num_workers(max_workers): {args.max_workers}\n"
        f"exit_reason_filter: {target_reason}\n"
        f"instance_ids_file: {ids_file}\n"
        f"instance_count: {len(error_ids)}\n"
        f"model_name_or_path: {model_name_or_path}\n"
        f"command: {rerun_command}\n"
    )
    prompt_file = prep_dir / "rerun_prompt.txt"
    prompt_file.write_text(prompt_text, encoding="utf-8")

    merge_command = (
        f"cd {json.dumps(str(command_workdir))} && "
        f"python3 {json.dumps(str(Path(__file__).resolve()))} merge "
        f"--old_predictions {json.dumps(str(predictions_path))} "
        f"--new_predictions {json.dumps(str(Path(args.run_agent_output_dir) / run_id / 'predictions.jsonl'))} "
        f"--output_predictions {json.dumps(str(prep_dir / 'predictions.merged.jsonl'))}"
    )
    merge_file = prep_dir / "merge_command.sh"
    merge_file.write_text(merge_command + "\n", encoding="utf-8")

    reason_counts = Counter(m.exit_reason for m in metrics_records)
    report = {
        "run_dir": str(run_dir),
        "model_dirs": model_dirs,
        "prep_dir": str(prep_dir),
        "target_exit_reason": target_reason,
        "selected_instances": len(error_ids),
        "summary_expected_selected": expected_errors,
        "counts_by_exit_reason": dict(sorted(reason_counts.items())),
        "new_run_id": run_id,
        "max_workers": args.max_workers,
        "max_iterations": args.max_iterations,
        "command_workdir": str(command_workdir),
        "dataset_name": args.dataset_name,
        "split": args.split,
        "agent": args.agent,
        "model_name_or_path": model_name_or_path,
        "artifacts": {
            "instance_ids": str(ids_file),
            "filtered_predictions": str(filtered_predictions_path),
            "rerun_command": str(command_file),
            "rerun_prompt": str(prompt_file),
            "merge_command": str(merge_file),
        },
    }
    _write_json(prep_dir / "error_filter_report.json", report)

    print(f"Prepared rerun artifacts in: {prep_dir}")
    print(f"Selected {len(error_ids)} instances with exit_reason={target_reason!r}")
    if expected_errors is not None and expected_errors != len(error_ids):
        print(
            "WARNING: selected count does not match summary exit_reasons count "
            f"({len(error_ids)} != {expected_errors})."
        )
    print(f"Rerun command file: {command_file}")
    print(f"Prompt text file: {prompt_file}")
    print(f"Merge command file: {merge_file}")
    return 0


def merge(args: argparse.Namespace) -> int:
    old_records = _read_jsonl(args.old_predictions.resolve())
    new_records = _read_jsonl(args.new_predictions.resolve())

    merged: dict[str, dict] = {}
    for row in old_records:
        instance_id = str(row.get("instance_id", "")).strip()
        if instance_id:
            merged[instance_id] = row
    for row in new_records:
        instance_id = str(row.get("instance_id", "")).strip()
        if instance_id:
            merged[instance_id] = row

    output_path = args.output_predictions.resolve()
    rows = [merged[key] for key in sorted(merged)]
    _write_jsonl(output_path, rows)

    stats = {
        "old_records": len(old_records),
        "new_records": len(new_records),
        "merged_records": len(rows),
        "output_predictions": str(output_path),
        "merge_rule": "prefer_newest_by_instance_id",
    }
    report_path = output_path.with_suffix(".merge_report.json")
    _write_json(report_path, stats)

    print(f"Merged predictions written to: {output_path}")
    print(f"Merge report written to: {report_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare reruns for failed agent instances and merge predictions."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="Prepare error-only rerun")
    prepare_parser.add_argument(
        "--run_dir",
        type=Path,
        default=Path("./predictions/logs/my-codex-run"),
        help="Run directory containing summary.json, predictions.jsonl, and model subfolders.",
    )
    prepare_parser.add_argument(
        "--output_dir",
        type=Path,
        default=Path("./predictions/logs"),
        help="Where to place generated prep artifacts.",
    )
    prepare_parser.add_argument(
        "--prep_name",
        type=str,
        default="my-codex-run-error-rerun-prep",
        help="Artifact folder name inside output_dir.",
    )
    prepare_parser.add_argument(
        "--exit_reason",
        type=str,
        default="error",
        help="Exit reason to select for rerun.",
    )
    prepare_parser.add_argument(
        "--dataset_name",
        type=str,
        default="SWE-bench/SWE-bench_Lite",
        help="Dataset for run_agent rerun command.",
    )
    prepare_parser.add_argument(
        "--split",
        type=str,
        default="test",
        help="Dataset split for run_agent rerun command.",
    )
    prepare_parser.add_argument(
        "--agent",
        type=str,
        default="claude",
        help="Agent for run_agent rerun command.",
    )
    prepare_parser.add_argument(
        "--model_name_or_path",
        type=str,
        default="",
        help="Model for rerun command. Defaults to value from predictions/metrics.",
    )
    prepare_parser.add_argument(
        "--new_run_id",
        type=str,
        default="",
        help="New run_id for rerun. If omitted, auto-generated from source run name.",
    )
    prepare_parser.add_argument(
        "--max_workers",
        type=int,
        default=1,
        help="max_workers value for rerun command (run_agent default).",
    )
    prepare_parser.add_argument(
        "--max_iterations",
        type=int,
        default=30,
        help="max_iterations value for rerun command (run_agent default).",
    )
    prepare_parser.add_argument(
        "--run_agent_output_dir",
        type=str,
        default="./predictions",
        help="output_dir argument value passed to run_agent.",
    )
    prepare_parser.add_argument(
        "--command_workdir",
        type=str,
        default="",
        help="Working directory prepended to generated commands. Defaults to SWE-bench root inferred from run_dir.",
    )

    merge_parser = subparsers.add_parser("merge", help="Merge predictions JSONL files")
    merge_parser.add_argument("--old_predictions", type=Path, required=True)
    merge_parser.add_argument("--new_predictions", type=Path, required=True)
    merge_parser.add_argument("--output_predictions", type=Path, required=True)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "prepare":
        return prepare(args)
    if args.command == "merge":
        return merge(args)
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
