"""
Live integration test for VulnAgentBench — Codex backend.

Runs VulnCodexAgent (local `codex` CLI) on project_a track 1
(explicit security audit) and verifies it finds at least one of the planted
vulnerabilities.

Requires:
  - Docker running locally
  - `codex` CLI installed and authenticated

Run with:
  .venv/bin/pytest swebench/security/test/test_live_audit_codex.py -v -s
"""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest

docker = pytest.importorskip("docker")

from swebench.harness.docker_build import close_logger, setup_logger
from swebench.agent.container_session import ContainerSession
from swebench.agent.metrics import AgentMetrics

from swebench.security.dataset import load_dataset, PROJECTS_DIR
from swebench.security.metrics import VulnSecurityMetrics
from swebench.security.run_benchmark import VulnTestSpec, _image_name, build_project_image
from swebench.security.scorer import score_instance
from swebench.security.vuln_codex_agent import VulnCodexAgent

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ID = "project_a"
TRACK = 1
AGENT_TIMEOUT_SECONDS = 300
COMMAND_TIMEOUT_SECONDS = 60

OUTPUT_DIR = Path(__file__).parent / "output"

# ---------------------------------------------------------------------------
# Skip conditions
# ---------------------------------------------------------------------------


def _docker_available() -> bool:
    try:
        docker.from_env().ping()
        return True
    except Exception:
        return False


def _codex_cli_available() -> bool:
    return shutil.which("codex") is not None


skip_no_docker = pytest.mark.skipif(
    not _docker_available(), reason="Docker not available"
)
skip_no_codex_cli = pytest.mark.skipif(
    not _codex_cli_available(), reason="codex CLI not installed"
)
integration = pytest.mark.integration


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@integration
@skip_no_docker
@skip_no_codex_cli
def test_vuln_codex_agent_audits_project_a():
    """
    End-to-end live test: run VulnCodexAgent (local codex CLI) on project_a
    (SQL injection, XSS, hardcoded secret) using track 1 (explicit security
    audit) and verify it finds at least one planted vulnerability.

    Outputs are saved to swebench/security/test/output/<run_id>/ for inspection.
    """
    run_id = f"codex-test-{uuid.uuid4().hex[:8]}"
    instance_id = f"{PROJECT_ID}__track_{TRACK}"

    client = docker.from_env()

    instances = load_dataset(projects=[PROJECT_ID], tracks=[TRACK])
    assert len(instances) == 1
    instance = instances[0]
    assert instance.instance_id == instance_id

    build_project_image(PROJECT_ID, PROJECTS_DIR / PROJECT_ID, client, force_rebuild=False)

    log_dir = OUTPUT_DIR / run_id
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logger(instance_id, log_dir / "agent.log")

    base_metrics = AgentMetrics(
        instance_id=instance_id,
        model_name_or_path="codex-default",
    )
    base_metrics.start_timer()
    vuln_metrics = VulnSecurityMetrics(base=base_metrics, track=TRACK)

    test_spec = VulnTestSpec(
        instance_id=instance_id,
        image_name=_image_name(PROJECT_ID),
    )
    session = ContainerSession(
        test_spec=test_spec,
        client=client,
        run_id=run_id,
        logger=logger,
        command_timeout=COMMAND_TIMEOUT_SECONDS,
        force_rebuild=False,
    )

    try:
        session.start()

        agent = VulnCodexAgent(agent_timeout=AGENT_TIMEOUT_SECONDS)

        result = agent.solve(instance, session, base_metrics)
        findings = agent._findings

        score = score_instance(
            findings=findings,
            ground_truth_path=instance.ground_truth_path,
            track=TRACK,
        )

        vuln_metrics.raw_findings = findings
        vuln_metrics.vulnerabilities_found = score["vulnerabilities_found"]
        vuln_metrics.true_positives = score["true_positives"]
        vuln_metrics.false_positives = score["false_positives"]
        vuln_metrics.false_negatives = score["false_negatives"]
        vuln_metrics.precision = score["precision"]
        vuln_metrics.recall = score["recall"]
        vuln_metrics.f1 = score["f1"]

        # ---- Assertions ---- #

        assert result.instance_id == instance_id
        assert result.exit_reason in (
            "completed", "gave_up", "max_iterations", "timeout", "error"
        )

        assert base_metrics.wall_clock_seconds > 0
        assert base_metrics.commands_executed >= 1

        # Core quality bar: at least 1 TP out of 3 planted vulnerabilities
        assert score["true_positives"] >= 1, (
            f"Expected at least 1 TP but got 0.\n"
            f"Findings submitted:\n{json.dumps(findings, indent=2)}"
        )

        # ---- Save outputs ---- #

        vuln_metrics.save(log_dir / "metrics.json")
        (log_dir / "findings.json").write_text(json.dumps(findings, indent=2))
        (log_dir / "result.json").write_text(json.dumps({
            "instance_id": instance_id,
            "project_id": PROJECT_ID,
            "track": TRACK,
            "model": "codex-default",
            **score,
            "raw_findings": findings,
            "exit_reason": result.exit_reason,
        }, indent=2))

        # ---- Print summary ---- #

        gt = instance.load_ground_truth()

        print(f"\n{'='*65}")
        print(f"VulnAgentBench — Codex Live Test Result")
        print(f"{'='*65}")
        print(f"Instance:         {instance_id}")
        print(f"Agent:            codex (local CLI)")
        print(f"Exit reason:      {result.exit_reason}")
        print(f"Wall clock:       {base_metrics.wall_clock_seconds:.1f}s")
        print(f"Commands run:     {base_metrics.commands_executed}")
        print(f"Input tokens:     {base_metrics.input_tokens:,}")
        print(f"Output tokens:    {base_metrics.output_tokens:,}")
        print(f"")
        print(f"Findings submitted: {len(findings)}")
        print(f"Ground truth total: {score['ground_truth_total']}")
        print(f"True positives:     {score['true_positives']}")
        print(f"False positives:    {score['false_positives']}")
        print(f"False negatives:    {score['false_negatives']}")
        print(f"Precision:          {score['precision']:.3f}")
        print(f"Recall:             {score['recall']:.3f}")
        print(f"F1:                 {score['f1']:.3f}")
        print(f"")
        print(f"Ground truth vulnerabilities:")
        for entry in gt:
            found_cwe = {f.get("cwe_id", "").upper() for f in findings}
            status = "FOUND" if entry["cwe_id"].upper() in found_cwe else "MISSED"
            print(
                f"  [{status}] {entry['cwe_id']} in "
                f"{entry['file']}:{entry['line_start']} — "
                f"{entry['description'][:60]}"
            )
        print(f"")
        print(f"Agent findings:")
        if findings:
            for f in findings:
                print(
                    f"  {f.get('cwe_id', '?')} in "
                    f"{f.get('file', '?')}:{f.get('line', '?')} "
                    f"[{f.get('severity', '?')}] — {f.get('vuln_type', '?')}"
                )
        else:
            print(f"  (none)")
        print(f"")
        print(f"Output dir:       {log_dir}")
        print(f"{'='*65}\n")

    finally:
        session.cleanup()
        close_logger(logger)
