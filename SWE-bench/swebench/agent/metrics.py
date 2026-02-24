from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AgentMetrics:
    instance_id: str
    model_name_or_path: str
    start_time: float = 0.0
    end_time: float = 0.0
    wall_clock_seconds: float = 0.0
    iterations: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    commands_executed: int = 0
    commands_timed_out: int = 0
    exit_reason: str = ""
    patch_produced: bool = False
    patch_size_bytes: int = 0
    estimated_cost_usd: float = 0.0

    def start_timer(self) -> None:
        self.start_time = time.time()

    def stop_timer(self) -> None:
        self.end_time = time.time()
        self.wall_clock_seconds = self.end_time - self.start_time

    def finalize(self, patch: str | None, exit_reason: str) -> None:
        self.stop_timer()
        self.exit_reason = exit_reason
        self.total_tokens = self.input_tokens + self.output_tokens
        if patch:
            self.patch_produced = True
            self.patch_size_bytes = len(patch.encode("utf-8"))
        else:
            self.patch_produced = False
            self.patch_size_bytes = 0

    def to_dict(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "model_name_or_path": self.model_name_or_path,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "wall_clock_seconds": self.wall_clock_seconds,
            "iterations": self.iterations,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "commands_executed": self.commands_executed,
            "commands_timed_out": self.commands_timed_out,
            "exit_reason": self.exit_reason,
            "patch_produced": self.patch_produced,
            "patch_size_bytes": self.patch_size_bytes,
            "estimated_cost_usd": self.estimated_cost_usd,
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))


def aggregate_metrics(metrics_list: list[AgentMetrics]) -> dict:
    if not metrics_list:
        return {}
    total_cost = sum(m.estimated_cost_usd for m in metrics_list)
    total_tokens = sum(m.total_tokens for m in metrics_list)
    total_input = sum(m.input_tokens for m in metrics_list)
    total_output = sum(m.output_tokens for m in metrics_list)
    total_commands = sum(m.commands_executed for m in metrics_list)
    total_timeouts = sum(m.commands_timed_out for m in metrics_list)
    patches_produced = sum(1 for m in metrics_list if m.patch_produced)
    total_wall_clock = sum(m.wall_clock_seconds for m in metrics_list)
    total_iterations = sum(m.iterations for m in metrics_list)
    n = len(metrics_list)
    return {
        "num_instances": n,
        "patches_produced": patches_produced,
        "patch_rate": patches_produced / n,
        "total_wall_clock_seconds": total_wall_clock,
        "avg_wall_clock_seconds": total_wall_clock / n,
        "total_iterations": total_iterations,
        "avg_iterations": total_iterations / n,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_tokens,
        "avg_tokens_per_instance": total_tokens / n,
        "total_commands_executed": total_commands,
        "total_commands_timed_out": total_timeouts,
        "total_estimated_cost_usd": total_cost,
        "avg_cost_per_instance_usd": total_cost / n,
        "exit_reasons": _count_exit_reasons(metrics_list),
    }


def _count_exit_reasons(metrics_list: list[AgentMetrics]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for m in metrics_list:
        counts[m.exit_reason] = counts.get(m.exit_reason, 0) + 1
    return counts
