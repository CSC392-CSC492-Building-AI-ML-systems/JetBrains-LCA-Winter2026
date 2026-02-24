from __future__ import annotations

import dataclasses
import json
import platform
import traceback

if platform.system() == "Linux":
    import resource

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pathlib import Path

import docker
from tqdm.auto import tqdm

from swebench.harness.constants import (
    KEY_INSTANCE_ID,
    KEY_MODEL,
    KEY_PREDICTION,
)
from swebench.harness.docker_build import (
    build_env_images,
    close_logger,
    setup_logger,
)
from swebench.harness.docker_utils import clean_images, list_images
from swebench.harness.test_spec.test_spec import make_test_spec
from swebench.harness.utils import load_swebench_dataset, str2bool

from swebench.agent.agents import create_agent
from swebench.agent.container_session import ContainerSession
from swebench.agent.metrics import AgentMetrics, aggregate_metrics

RUN_AGENT_LOG_DIR = Path("logs/run_agent")


def _validate_path_component(value: str, name: str) -> None:
    """Reject path traversal characters in values used to build file paths."""
    if ".." in value or "/" in value or "\\" in value:
        raise ValueError(
            f"{name} contains path traversal characters: {value!r}"
        )


def run_instance_with_agent(
    instance: dict,
    agent_name: str,
    model_name_or_path: str,
    max_iterations: int,
    agent_timeout: int,
    command_timeout: int,
    client: docker.DockerClient,
    run_id: str,
    output_dir: Path,
    force_rebuild: bool,
) -> dict:
    instance_id = instance[KEY_INSTANCE_ID]
    _validate_path_component(instance_id, "instance_id")
    _validate_path_component(model_name_or_path, "model_name_or_path")
    _validate_path_component(run_id, "run_id")
    test_spec = make_test_spec(instance)

    # Set up logging
    log_dir = output_dir / "logs" / run_id / model_name_or_path / instance_id
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "agent.log"
    logger = setup_logger(instance_id, log_file)

    metrics = AgentMetrics(
        instance_id=instance_id,
        model_name_or_path=model_name_or_path,
    )
    metrics.start_timer()

    container = None
    session = None
    try:
        # Create session and start container
        session = ContainerSession(
            test_spec=test_spec,
            client=client,
            run_id=run_id,
            logger=logger,
            command_timeout=command_timeout,
            force_rebuild=force_rebuild,
        )
        session.start()

        # Create agent and solve
        agent = create_agent(
            agent_name,
            model_name_or_path=model_name_or_path,
            max_iterations=max_iterations,
            agent_timeout=agent_timeout,
        )
        result = agent.solve(instance, session, metrics)

        prediction = {
            KEY_INSTANCE_ID: instance_id,
            KEY_MODEL: model_name_or_path,
            KEY_PREDICTION: result.model_patch,
        }

        logger.info(
            f"Completed {instance_id}: exit_reason={result.exit_reason} "
            f"patch_produced={result.metrics.patch_produced}"
        )

        # Save the generated patch to the log directory
        patch_path = log_dir / "patch.diff"
        patch_path.write_text(result.model_patch or "")

        return prediction

    except Exception as e:
        logger.error(f"Error processing {instance_id}: {e}\n{traceback.format_exc()}")
        metrics.finalize(None, "error")
        return {
            KEY_INSTANCE_ID: instance_id,
            KEY_MODEL: model_name_or_path,
            KEY_PREDICTION: None,
        }

    finally:
        # Save metrics
        metrics_path = log_dir / "metrics.json"
        try:
            if metrics.end_time == 0:
                metrics.finalize(None, "error")
            metrics.save(metrics_path)
        except Exception:
            pass

        # Clean up
        if session is not None:
            try:
                session.cleanup()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

        close_logger(logger)


def _load_completed_ids(predictions_path: Path) -> set[str]:
    """Load instance IDs that already have predictions."""
    completed = set()
    if predictions_path.exists():
        with open(predictions_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        pred = json.loads(line)
                        completed.add(pred[KEY_INSTANCE_ID])
                    except (json.JSONDecodeError, KeyError):
                        pass
    return completed


def _append_prediction(predictions_path: Path, prediction: dict) -> None:
    """Append a single prediction to the JSONL file (crash-resilient)."""
    predictions_path.parent.mkdir(parents=True, exist_ok=True)
    with open(predictions_path, "a") as f:
        f.write(json.dumps(prediction) + "\n")


def main(
    dataset_name: str,
    split: str,
    instance_ids: list[str] | None,
    agent: str,
    model_name_or_path: str,
    max_iterations: int,
    agent_timeout: int,
    command_timeout: int,
    output_dir: str,
    run_id: str,
    max_workers: int,
    force_rebuild: bool,
    cache_level: str,
    clean: bool,
    open_file_limit: int,
):
    assert len(run_id) > 0, "Run ID must be provided"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = output_dir / "predictions.jsonl"

    # Load dataset
    dataset = load_swebench_dataset(dataset_name, split, instance_ids)
    if not dataset:
        print("No instances found in dataset.")
        return

    # Skip already-completed instances
    completed_ids = _load_completed_ids(predictions_path)
    remaining = [d for d in dataset if d[KEY_INSTANCE_ID] not in completed_ids]
    if not remaining:
        print(
            f"All {len(dataset)} instances already completed. "
            f"Predictions at: {predictions_path}"
        )
        return

    skipped = len(dataset) - len(remaining)
    if skipped > 0:
        print(f"Skipping {skipped} already-completed instances.")
    print(f"Running agent on {len(remaining)} instances...")

    # Set open file limit on Linux
    if platform.system() == "Linux":
        resource.setrlimit(resource.RLIMIT_NOFILE, (open_file_limit, open_file_limit))

    client = docker.from_env()
    existing_images = list_images(client)

    # Build environment images
    build_env_images(
        client,
        remaining,
        force_rebuild,
        max_workers,
        instance_image_tag="latest",
        env_image_tag="latest",
    )

    # Run instances
    all_metrics: list[AgentMetrics] = []
    pbar = tqdm(remaining, desc="Running agent", unit="instance")

    for instance in pbar:
        instance_id = instance[KEY_INSTANCE_ID]
        pbar.set_postfix_str(instance_id)

        prediction = run_instance_with_agent(
            instance=instance,
            agent_name=agent,
            model_name_or_path=model_name_or_path,
            max_iterations=max_iterations,
            agent_timeout=agent_timeout,
            command_timeout=command_timeout,
            client=client,
            run_id=run_id,
            output_dir=output_dir,
            force_rebuild=force_rebuild,
        )

        # Append prediction immediately (crash-resilient)
        _append_prediction(predictions_path, prediction)

        # Load metrics if saved
        metrics_path = (
            output_dir
            / "logs"
            / run_id
            / model_name_or_path
            / instance_id
            / "metrics.json"
        )
        if metrics_path.exists():
            try:
                data = json.loads(metrics_path.read_text())
                m = AgentMetrics(
                    instance_id=data["instance_id"],
                    model_name_or_path=data["model_name_or_path"],
                )
                allowed_fields = {f.name for f in dataclasses.fields(m)}
                for k, v in data.items():
                    if k in allowed_fields:
                        setattr(m, k, v)
                all_metrics.append(m)
            except Exception:
                pass

    # Clean images
    clean_images(client, existing_images, cache_level, clean)

    # Write summary
    if all_metrics:
        summary = aggregate_metrics(all_metrics)
        summary_path = output_dir / "logs" / run_id / "summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2))
        print(f"\nSummary saved to: {summary_path}")
        print(f"  Instances: {summary['num_instances']}")
        print(f"  Patches produced: {summary['patches_produced']}/{summary['num_instances']}")
        print(f"  Avg iterations: {summary['avg_iterations']:.1f}")
        print(f"  Total cost: ${summary['total_estimated_cost_usd']:.2f}")

    print(f"\nPredictions saved to: {predictions_path}")
    print(
        "To evaluate, run:\n"
        f"  python -m swebench.harness.run_evaluation \\\n"
        f"    --dataset_name {dataset_name} \\\n"
        f"    --predictions_path {predictions_path} \\\n"
        f"    --run_id {run_id}"
    )


if __name__ == "__main__":
    parser = ArgumentParser(
        description="Run an AI agent to generate patches for SWE-bench instances.",
        formatter_class=ArgumentDefaultsHelpFormatter,
    )

    # Dataset args
    parser.add_argument(
        "-d",
        "--dataset_name",
        default="SWE-bench/SWE-bench_Lite",
        type=str,
        help="Name of dataset or path to JSON file.",
    )
    parser.add_argument(
        "-s", "--split", type=str, default="test", help="Split of the dataset"
    )
    parser.add_argument(
        "-i",
        "--instance_ids",
        nargs="+",
        type=str,
        help="Instance IDs to run (space separated)",
    )

    # Agent args
    parser.add_argument(
        "--agent",
        type=str,
        default="claude",
        help="Agent to use (claude, dummy)",
    )
    parser.add_argument(
        "--model_name_or_path",
        type=str,
        default="claude-sonnet-4-20250514",
        help="Model name or path for the agent",
    )
    parser.add_argument(
        "--max_iterations",
        type=int,
        default=30,
        help="Maximum agent iterations per instance",
    )
    parser.add_argument(
        "--agent_timeout",
        type=int,
        default=1800,
        help="Wall-clock timeout (seconds) per instance for the agent",
    )
    parser.add_argument(
        "--command_timeout",
        type=int,
        default=120,
        help="Default timeout (seconds) per shell command",
    )

    # Output args
    parser.add_argument(
        "--output_dir",
        type=str,
        default="./predictions",
        help="Directory for predictions and logs",
    )
    parser.add_argument(
        "-id", "--run_id", type=str, required=True, help="Run ID - identifies the run"
    )

    # Docker args
    parser.add_argument(
        "--max_workers",
        type=int,
        default=1,
        help="Maximum number of workers for building images",
    )
    parser.add_argument(
        "--force_rebuild",
        type=str2bool,
        default=False,
        help="Force rebuild of all images",
    )
    parser.add_argument(
        "--cache_level",
        type=str,
        choices=["none", "base", "env", "instance"],
        default="env",
        help="Cache level - remove images above this level",
    )
    parser.add_argument(
        "--clean",
        type=str2bool,
        default=False,
        help="Clean images above cache level",
    )
    parser.add_argument(
        "--open_file_limit",
        type=int,
        default=4096,
        help="Open file limit (Linux only)",
    )

    args = parser.parse_args()
    main(**vars(args))
