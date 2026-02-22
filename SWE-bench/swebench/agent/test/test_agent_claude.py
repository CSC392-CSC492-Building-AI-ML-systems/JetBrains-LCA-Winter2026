"""
Integration tests for the agent pipeline.

The main test uses `claude-code` agent which runs the locally installed
`claude` CLI — no ANTHROPIC_API_KEY needed, it uses Claude Code's own auth.

Requires:
  - Docker running locally
  - `claude` CLI installed and authenticated

Run with:
  pytest swebench/agent/test/test_agent_claude.py -v -s

Token/dollar budget is capped to prevent runaway costs from bugs.
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest

docker = pytest.importorskip("docker")

from swebench.agent.agents import create_agent
from swebench.agent.container_session import ContainerSession
from swebench.agent.metrics import AgentMetrics
from swebench.harness.constants import KEY_INSTANCE_ID, KEY_MODEL, KEY_PREDICTION
from swebench.harness.docker_build import (
    build_env_images,
    close_logger,
    setup_logger,
)
from swebench.harness.test_spec.test_spec import make_test_spec
from swebench.harness.utils import load_swebench_dataset

# --------------------------------------------------------------------------- #
# Safety limits
# --------------------------------------------------------------------------- #
AGENT_TIMEOUT_SECONDS = 120  # 2 minutes wall clock
COMMAND_TIMEOUT_SECONDS = 60
MAX_BUDGET_USD = 0.25  # hard dollar cap for claude-code agent
# --------------------------------------------------------------------------- #

INSTANCE_ID = "astropy__astropy-6938"
DATASET_NAME = "SWE-bench/SWE-bench_Lite"
SPLIT = "test"

OUTPUT_DIR = Path(__file__).parent / "output"


def _docker_available() -> bool:
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


def _claude_cli_available() -> bool:
    return shutil.which("claude") is not None


skip_no_docker = pytest.mark.skipif(
    not _docker_available(), reason="Docker not available"
)
skip_no_claude_cli = pytest.mark.skipif(
    not _claude_cli_available(), reason="claude CLI not installed"
)
integration = pytest.mark.integration


@integration
@skip_no_docker
@skip_no_claude_cli
def test_claude_code_agent_generates_patch():
    """
    End-to-end test: run the claude-code agent (local CLI) on a single
    instance and verify it produces a structurally valid prediction.

    Uses --max-budget-usd to cap costs, and a wall-clock timeout as backstop.
    Outputs are saved to swebench/agent/test/output/ for inspection.
    """
    run_id = f"test-{uuid.uuid4().hex[:8]}"
    model = "sonnet"
    client = docker.from_env()

    # Load the single instance
    dataset = load_swebench_dataset(DATASET_NAME, SPLIT, [INSTANCE_ID])
    assert len(dataset) == 1
    instance = dataset[0]

    # Build environment images
    build_env_images(
        client,
        dataset,
        force_rebuild=False,
        max_workers=1,
        instance_image_tag="latest",
        env_image_tag="latest",
    )

    # Set up output directory
    log_dir = OUTPUT_DIR / run_id
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logger(INSTANCE_ID, log_dir / "agent.log")

    test_spec = make_test_spec(instance)
    metrics = AgentMetrics(
        instance_id=INSTANCE_ID,
        model_name_or_path=model,
    )
    metrics.start_timer()

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

        agent = create_agent(
            "claude-code",
            model_name_or_path=model,
            agent_timeout=AGENT_TIMEOUT_SECONDS,
            max_budget_usd=MAX_BUDGET_USD,
        )

        result = agent.solve(instance, session, metrics)

        # ---- Assertions ---- #

        # Result structure is valid
        assert result.instance_id == INSTANCE_ID
        assert result.model_name_or_path == model
        assert result.exit_reason in (
            "completed",
            "gave_up",
            "max_iterations",
            "timeout",
            "error",
        )

        # Metrics have timing data
        assert result.metrics.wall_clock_seconds > 0

        # The prediction is valid JSONL-compatible format
        prediction = {
            KEY_INSTANCE_ID: result.instance_id,
            KEY_MODEL: result.model_name_or_path,
            KEY_PREDICTION: result.model_patch,
        }
        serialized = json.dumps(prediction)
        deserialized = json.loads(serialized)
        assert deserialized[KEY_INSTANCE_ID] == INSTANCE_ID

        # Save outputs for inspection
        pred_path = OUTPUT_DIR / "predictions.jsonl"
        with open(pred_path, "a") as f:
            f.write(serialized + "\n")

        metrics_path = log_dir / "metrics.json"
        result.metrics.save(metrics_path)

        patch_path = log_dir / "patch.diff"
        patch_path.write_text(result.model_patch or "")

        # Print summary for -s output
        print(f"\n{'='*60}")
        print(f"Instance:       {INSTANCE_ID}")
        print(f"Agent:          claude-code (local CLI)")
        print(f"Model:          {model}")
        print(f"Exit reason:    {result.exit_reason}")
        print(f"Patch produced: {result.metrics.patch_produced}")
        print(f"Iterations:     {result.metrics.iterations}")
        print(f"Input tokens:   {result.metrics.input_tokens:,}")
        print(f"Output tokens:  {result.metrics.output_tokens:,}")
        print(f"Wall clock:     {result.metrics.wall_clock_seconds:.1f}s")
        print(f"Output dir:     {OUTPUT_DIR}")
        print(f"  agent.log:    {log_dir / 'agent.log'}")
        print(f"  patch.diff:   {patch_path}")
        print(f"  metrics.json: {metrics_path}")
        print(f"  predictions:  {pred_path}")
        if result.model_patch:
            patch_lines = result.model_patch.count("\n")
            print(f"Patch lines:    {patch_lines}")
            print(f"Patch preview:\n{result.model_patch[:500]}")
        else:
            print("Patch:          (none produced)")
        print(f"{'='*60}\n")

    finally:
        session.cleanup()
        close_logger(logger)


@skip_no_claude_cli
def test_claude_code_agent_creation():
    """
    Verify claude-code agent can be created and has correct attributes.
    """
    agent = create_agent(
        "claude-code",
        model_name_or_path="sonnet",
        max_budget_usd=0.25,
        agent_timeout=60,
    )
    assert agent.model_name_or_path == "sonnet"
    assert agent.max_budget_usd == 0.25
    assert agent.agent_timeout == 60
    assert agent.claude_path is not None


def test_dummy_agent_does_not_require_api_key():
    """
    Verify the dummy agent can be created without any API key or Docker.
    """
    agent = create_agent("dummy", model_name_or_path="dummy")
    assert agent.model_name_or_path == "dummy"
