from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import docker

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

INSTANCE_ID = "astropy__astropy-6938"
DATASET_NAME = "SWE-bench/SWE-bench_Lite"
SPLIT = "test"

OUTPUT_DIR = Path(__file__).parent / "output"

# --------------------------------------------------------------------------- #
# Safety limits
# --------------------------------------------------------------------------- #
AGENT_TIMEOUT_SECONDS = 120*5  # 2 minutes wall clock
COMMAND_TIMEOUT_SECONDS = 60
MAX_BUDGET_USD = 0.25  # hard dollar cap for claude-code agent
# --------------------------------------------------------------------------- #

def test_codex_functions():
    run_id = f"test-{uuid.uuid4().hex[:8]}"
    model = "codex"
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
        print("Starting session")
        session.start()

        agent = create_agent(
            "codex",
            model_name_or_path=model,
            agent_timeout=AGENT_TIMEOUT_SECONDS,
            max_budget_usd=MAX_BUDGET_USD,
        )

        result = agent.solve(instance, session, metrics)

    finally:
        session.cleanup()
        close_logger(logger)

if __name__ == "__main__":
    test_codex_functions()

