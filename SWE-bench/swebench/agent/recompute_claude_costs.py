#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SONNET_4_6_PRICING_PER_MTOK = {
    "base_input": 3.0,
    "cache_write_5m": 3.75,
    "cache_write_1h": 6.0,
    "cache_hit": 0.30,
    "output": 15.0,
}

CONTAINER_RE = re.compile(r"docker exec (sweb\.eval\.([^.\s]+)\.([^.\s]+))")


@dataclass
class SessionRef:
    session_id: str
    session_file: Path
    enqueue_timestamp: datetime
    container_name: str
    instance_id: str
    run_id: str


@dataclass
class UsageTotals:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_creation_5m_tokens: int = 0
    cache_creation_1h_tokens: int = 0



def parse_ts(ts: str) -> datetime:
    # Example: 2026-03-20T08:33:55.220Z
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt



def to_int(value: Any) -> int:
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



def collect_latest_sessions(
    sessions_dir: Path,
    target_instances: set[str],
    run_id_filter: str,
) -> dict[str, SessionRef]:
    latest: dict[str, SessionRef] = {}

    for jsonl_file in sessions_dir.glob("*.jsonl"):
        try:
            with jsonl_file.open("r", encoding="utf-8") as handle:
                for raw in handle:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        obj = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    if obj.get("type") != "queue-operation" or obj.get("operation") != "enqueue":
                        continue

                    content = obj.get("content")
                    if not isinstance(content, str):
                        continue

                    match = CONTAINER_RE.search(content)
                    if not match:
                        continue

                    container_name = match.group(1)
                    instance_id = match.group(2)
                    run_id = match.group(3)

                    if run_id != run_id_filter:
                        continue
                    if instance_id not in target_instances:
                        continue

                    session_id = obj.get("sessionId")
                    ts_raw = obj.get("timestamp")
                    if not isinstance(session_id, str) or not isinstance(ts_raw, str):
                        continue

                    ref = SessionRef(
                        session_id=session_id,
                        session_file=jsonl_file,
                        enqueue_timestamp=parse_ts(ts_raw),
                        container_name=container_name,
                        instance_id=instance_id,
                        run_id=run_id,
                    )

                    prev = latest.get(instance_id)
                    if prev is None or ref.enqueue_timestamp > prev.enqueue_timestamp:
                        latest[instance_id] = ref
        except OSError:
            continue

    return latest



def extract_usage_for_session(session_file: Path, session_id: str) -> UsageTotals:
    by_request: dict[str, UsageTotals] = {}

    with session_file.open("r", encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if obj.get("type") != "assistant":
                continue
            if obj.get("sessionId") != session_id:
                continue

            request_id = obj.get("requestId")
            if not isinstance(request_id, str) or not request_id:
                continue

            usage = ((obj.get("message") or {}).get("usage") or {})
            if not isinstance(usage, dict) or not usage:
                continue

            slot = by_request.setdefault(request_id, UsageTotals())
            slot.input_tokens = max(slot.input_tokens, to_int(usage.get("input_tokens", 0)))
            slot.output_tokens = max(slot.output_tokens, to_int(usage.get("output_tokens", 0)))
            slot.cache_read_input_tokens = max(
                slot.cache_read_input_tokens,
                to_int(usage.get("cache_read_input_tokens", 0)),
            )
            slot.cache_creation_input_tokens = max(
                slot.cache_creation_input_tokens,
                to_int(usage.get("cache_creation_input_tokens", 0)),
            )

            cache_creation = usage.get("cache_creation")
            if isinstance(cache_creation, dict):
                slot.cache_creation_5m_tokens = max(
                    slot.cache_creation_5m_tokens,
                    to_int(cache_creation.get("ephemeral_5m_input_tokens", 0)),
                )
                slot.cache_creation_1h_tokens = max(
                    slot.cache_creation_1h_tokens,
                    to_int(cache_creation.get("ephemeral_1h_input_tokens", 0)),
                )

    total = UsageTotals()
    for req_usage in by_request.values():
        total.input_tokens += req_usage.input_tokens
        total.output_tokens += req_usage.output_tokens
        total.cache_read_input_tokens += req_usage.cache_read_input_tokens
        total.cache_creation_input_tokens += req_usage.cache_creation_input_tokens
        total.cache_creation_5m_tokens += req_usage.cache_creation_5m_tokens
        total.cache_creation_1h_tokens += req_usage.cache_creation_1h_tokens

    return total



def estimate_cost_sonnet_4_6(usage: UsageTotals, fallback_cache_write_tier: str) -> float:
    write_5m, write_1h = resolve_cache_write_tokens(usage, fallback_cache_write_tier)

    cost = (
        SONNET_4_6_PRICING_PER_MTOK["base_input"] * usage.input_tokens
        + SONNET_4_6_PRICING_PER_MTOK["cache_write_5m"] * write_5m
        + SONNET_4_6_PRICING_PER_MTOK["cache_write_1h"] * write_1h
        + SONNET_4_6_PRICING_PER_MTOK["cache_hit"] * usage.cache_read_input_tokens
        + SONNET_4_6_PRICING_PER_MTOK["output"] * usage.output_tokens
    ) / 1_000_000.0

    return cost


def resolve_cache_write_tokens(usage: UsageTotals, fallback_cache_write_tier: str) -> tuple[int, int]:
    write_5m = usage.cache_creation_5m_tokens
    write_1h = usage.cache_creation_1h_tokens
    

    if write_5m == 0 and write_1h == 0 and usage.cache_creation_input_tokens > 0:
        if fallback_cache_write_tier == "1h":
            write_1h = usage.cache_creation_input_tokens
        else:
            write_5m = usage.cache_creation_input_tokens

    return write_5m, write_1h


def estimate_effective_input_tokens(usage: UsageTotals, fallback_cache_write_tier: str) -> int:
    write_5m, write_1h = resolve_cache_write_tokens(usage, fallback_cache_write_tier)
    return usage.input_tokens + write_5m + write_1h + usage.cache_read_input_tokens



def process_metrics(
    run_logs_dir: Path,
    sessions_dir: Path,
    run_id: str,
    dry_run: bool,
    fallback_cache_write_tier: str,
) -> int:
    if not run_logs_dir.exists():
        raise FileNotFoundError(f"Run logs directory not found: {run_logs_dir}")
    if not sessions_dir.exists():
        raise FileNotFoundError(f"Sessions directory not found: {sessions_dir}")

    instance_dirs = [p for p in run_logs_dir.iterdir() if p.is_dir()]
    target_instances = {p.name for p in instance_dirs if (p / "metrics.json").exists()}

    latest = collect_latest_sessions(
        sessions_dir=sessions_dir,
        target_instances=target_instances,
        run_id_filter=run_id,
    )

    updated = 0
    missing = 0

    for instance_dir in sorted(instance_dirs):
        metrics_path = instance_dir / "metrics.json"
        if not metrics_path.exists():
            continue

        instance_id = instance_dir.name
        ref = latest.get(instance_id)
        if ref is None:
            missing += 1
            continue

        usage = extract_usage_for_session(ref.session_file, ref.session_id)
        new_cost = estimate_cost_sonnet_4_6(usage, fallback_cache_write_tier)
        effective_input_tokens = estimate_effective_input_tokens(
            usage, fallback_cache_write_tier
        )

        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

        metrics["input_tokens"] = effective_input_tokens
        metrics["output_tokens"] = usage.output_tokens
        metrics["total_tokens"] = effective_input_tokens + usage.output_tokens
        metrics["estimated_cost_usd"] = new_cost

        # Add traceability fields (safe, backward-compatible extra keys)
        metrics["claude_session_id"] = ref.session_id
        metrics["claude_enqueue_timestamp"] = ref.enqueue_timestamp.isoformat()
        metrics["claude_cache_read_input_tokens"] = usage.cache_read_input_tokens
        metrics["claude_cache_creation_input_tokens"] = usage.cache_creation_input_tokens
        metrics["claude_cache_creation_5m_tokens"] = usage.cache_creation_5m_tokens
        metrics["claude_cache_creation_1h_tokens"] = usage.cache_creation_1h_tokens

        if dry_run:
            print(
                f"[DRY-RUN] {instance_id}: input={effective_input_tokens} output={usage.output_tokens} "
                f"cache_read={usage.cache_read_input_tokens} cost=${new_cost:.8f}"
            )
            updated += 1
            continue

        metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
        updated += 1

    print(f"Instances with metrics.json: {len(target_instances)}")
    print(f"Matched sessions (latest by enqueue timestamp): {len(latest)}")
    print(f"Updated metrics files: {updated}")
    if missing:
        print(f"Missing session matches: {missing}")

    return 0



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute Claude Sonnet 4.6 usage/cost from ~/.claude/projects/-tmp session logs "
            "and update metrics.json files in a run log directory."
        )
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
        "--sessions-dir",
        type=Path,
        default=Path("/home/rafay/.claude/projects/-tmp"),
        help="Directory containing Claude session .jsonl files.",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default="my-claude-run",
        help="Run id suffix used in container name (e.g., *.my-claude-run).",
    )
    parser.add_argument(
        "--fallback-cache-write-tier",
        choices=["5m", "1h"],
        default="5m",
        help=(
            "If cache_creation_input_tokens is present but 5m/1h split is absent, "
            "assign all cache-write tokens to this tier."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned updates without modifying files.",
    )
    return parser



def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    return process_metrics(
        run_logs_dir=args.run_logs_dir,
        sessions_dir=args.sessions_dir,
        run_id=args.run_id,
        dry_run=args.dry_run,
        fallback_cache_write_tier=args.fallback_cache_write_tier,
    )


if __name__ == "__main__":
    raise SystemExit(main())
