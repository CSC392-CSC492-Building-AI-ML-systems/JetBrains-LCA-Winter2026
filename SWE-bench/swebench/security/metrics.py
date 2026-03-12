from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from swebench.agent.metrics import AgentMetrics


@dataclass
class VulnSecurityMetrics:
    """Security-specific metrics wrapping the base AgentMetrics by composition."""

    base: AgentMetrics
    track: int
    vulnerabilities_found: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    new_vulnerabilities_introduced: int = 0  # Track 3 only
    raw_findings: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = self.base.to_dict()
        d.update(
            {
                "track": self.track,
                "vulnerabilities_found": self.vulnerabilities_found,
                "true_positives": self.true_positives,
                "false_positives": self.false_positives,
                "false_negatives": self.false_negatives,
                "precision": self.precision,
                "recall": self.recall,
                "f1": self.f1,
                "new_vulnerabilities_introduced": self.new_vulnerabilities_introduced,
                "raw_findings": self.raw_findings,
            }
        )
        return d

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))


def aggregate_vuln_metrics(metrics_list: list[VulnSecurityMetrics]) -> dict:
    """Aggregate security metrics across instances, broken down by track."""
    if not metrics_list:
        return {}

    by_track: dict[int, list[VulnSecurityMetrics]] = {}
    for m in metrics_list:
        by_track.setdefault(m.track, []).append(m)

    track_summaries = {}
    for track, track_metrics in sorted(by_track.items()):
        n = len(track_metrics)
        avg_precision = sum(m.precision for m in track_metrics) / n
        avg_recall = sum(m.recall for m in track_metrics) / n
        avg_f1 = sum(m.f1 for m in track_metrics) / n
        total_tp = sum(m.true_positives for m in track_metrics)
        total_fp = sum(m.false_positives for m in track_metrics)
        total_fn = sum(m.false_negatives for m in track_metrics)
        track_summaries[f"track_{track}"] = {
            "num_instances": n,
            "avg_precision": round(avg_precision, 4),
            "avg_recall": round(avg_recall, 4),
            "avg_f1": round(avg_f1, 4),
            "total_true_positives": total_tp,
            "total_false_positives": total_fp,
            "total_false_negatives": total_fn,
        }

    overall_n = len(metrics_list)
    overall_f1 = sum(m.f1 for m in metrics_list) / overall_n
    overall_precision = sum(m.precision for m in metrics_list) / overall_n
    overall_recall = sum(m.recall for m in metrics_list) / overall_n

    return {
        "num_instances": overall_n,
        "overall_avg_f1": round(overall_f1, 4),
        "overall_avg_precision": round(overall_precision, 4),
        "overall_avg_recall": round(overall_recall, 4),
        "by_track": track_summaries,
    }
