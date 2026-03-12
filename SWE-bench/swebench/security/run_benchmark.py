"""
VulnAgentBench — CLI entry point.

Runs the VulnAgent on security benchmark instances and scores findings
against ground truth. Reuses ContainerSession and Docker infrastructure
from swebench.agent without modifying any existing harness files.
"""
from __future__ import annotations

import dataclasses
import json
import platform
import subprocess
import traceback
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pathlib import Path

if platform.system() == "Linux":
    import resource

import docker
from tqdm.auto import tqdm

from swebench.harness.docker_build import close_logger, setup_logger
from swebench.harness.docker_utils import clean_images, list_images

from swebench.agent.container_session import ContainerSession
from swebench.agent.metrics import AgentMetrics

from swebench.security.dataset import VulnInstance, load_dataset
from swebench.security.metrics import VulnSecurityMetrics, aggregate_vuln_metrics
from swebench.security.scorer import score_instance
from swebench.security.vuln_agent import VulnAgent


# ---------------------------------------------------------------------------
# VulnTestSpec: thin wrapper satisfying the interface build_container() needs
# ---------------------------------------------------------------------------

class VulnTestSpec:
    """
    Minimal TestSpec-compatible object for VulnAgentBench instances.

    build_container() reads: instance_id, instance_image_key, is_remote_image,
    docker_specs, platform, get_instance_container_name(run_id).

    We set is_remote_image=True so build_container() skips the SWE-bench
    multi-tier build and just uses the pre-built image directly.
    """

    def __init__(self, instance_id: str, image_name: str):
        self.instance_id = instance_id
        self.instance_image_key = image_name
        self.is_remote_image = True
        self.docker_specs: dict = {}
        self.platform = _get_platform()

    def get_instance_container_name(self, run_id: str) -> str:
        safe_id = self.instance_id.replace("_", "-").replace(".", "-")
        return f"vulnagent-{safe_id}-{run_id}"


def _get_platform() -> str:
    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        return "linux/arm64"
    return "linux/amd64"


# ---------------------------------------------------------------------------
# Image building
# ---------------------------------------------------------------------------

def _image_name(project_id: str) -> str:
    return f"vulnagentbench-{project_id}:latest"


def build_project_image(
    project_id: str,
    project_path: Path,
    client: docker.DockerClient,
    force_rebuild: bool = False,
) -> str:
    """Build (or reuse) a Docker image for a vulnerable project. Returns image name."""
    image_name = _image_name(project_id)

    if not force_rebuild:
        try:
            client.images.get(image_name)
            print(f"  Image {image_name} already exists, skipping build.")
            return image_name
        except docker.errors.ImageNotFound:
            pass

    print(f"  Building image {image_name} from {project_path}...")
    subprocess.run(
        ["docker", "build", "-t", image_name, str(project_path)],
        check=True,
    )
    return image_name


def build_all_project_images(
    instances: list[VulnInstance],
    client: docker.DockerClient,
    force_rebuild: bool = False,
) -> None:
    """Pre-build Docker images for all unique projects in the instance list."""
    seen: set[str] = set()
    for instance in instances:
        if instance.project_id not in seen:
            seen.add(instance.project_id)
            build_project_image(
                instance.project_id,
                instance.project_path,
                client,
                force_rebuild,
            )


# ---------------------------------------------------------------------------
# Per-instance runner
# ---------------------------------------------------------------------------

def run_instance(
    instance: VulnInstance,
    model_name_or_path: str,
    max_iterations: int,
    agent_timeout: int,
    command_timeout: int,
    client: docker.DockerClient,
    run_id: str,
    output_dir: Path,
    force_rebuild: bool,
) -> dict:
    """Run VulnAgent on a single instance, score findings, and return result dict."""
    instance_id = instance.instance_id

    log_dir = output_dir / "logs" / run_id / model_name_or_path / instance_id
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "agent.log"
    logger = setup_logger(instance_id, log_file)

    base_metrics = AgentMetrics(
        instance_id=instance_id,
        model_name_or_path=model_name_or_path,
    )
    base_metrics.start_timer()

    vuln_metrics = VulnSecurityMetrics(base=base_metrics, track=instance.track)

    session = None
    try:
        image_name = _image_name(instance.project_id)
        test_spec = VulnTestSpec(instance_id=instance_id, image_name=image_name)

        session = ContainerSession(
            test_spec=test_spec,
            client=client,
            run_id=run_id,
            logger=logger,
            command_timeout=command_timeout,
            force_rebuild=force_rebuild,
        )
        session.start()

        agent = VulnAgent(
            model_name_or_path=model_name_or_path,
            max_iterations=max_iterations,
            agent_timeout=agent_timeout,
        )
        result = agent.solve(instance, session, base_metrics)

        # Score findings against ground truth
        score = score_instance(
            findings=agent._findings,
            ground_truth_path=instance.ground_truth_path,
            track=instance.track,
            patch=result.model_patch,
        )

        vuln_metrics.raw_findings = agent._findings
        vuln_metrics.vulnerabilities_found = score["vulnerabilities_found"]
        vuln_metrics.true_positives = score["true_positives"]
        vuln_metrics.false_positives = score["false_positives"]
        vuln_metrics.false_negatives = score["false_negatives"]
        vuln_metrics.precision = score["precision"]
        vuln_metrics.recall = score["recall"]
        vuln_metrics.f1 = score["f1"]
        vuln_metrics.new_vulnerabilities_introduced = score["new_vulnerabilities_introduced"]

        # Save patch
        patch_path = log_dir / "patch.diff"
        patch_path.write_text(result.model_patch or "")

        logger.info(
            f"Completed {instance_id}: track={instance.track} "
            f"findings={score['vulnerabilities_found']} "
            f"TP={score['true_positives']} FP={score['false_positives']} "
            f"FN={score['false_negatives']} F1={score['f1']:.3f}"
        )

        instance_result = {
            "instance_id": instance_id,
            "project_id": instance.project_id,
            "track": instance.track,
            "model_name_or_path": model_name_or_path,
            **score,
            "raw_findings": agent._findings,
            "exit_reason": result.exit_reason,
        }
        return instance_result

    except Exception as e:
        logger.error(f"Error processing {instance_id}: {e}\n{traceback.format_exc()}")
        if not base_metrics.end_time:
            base_metrics.finalize(None, "error")
        return {
            "instance_id": instance_id,
            "project_id": instance.project_id,
            "track": instance.track,
            "model_name_or_path": model_name_or_path,
            "true_positives": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "vulnerabilities_found": 0,
            "ground_truth_total": 0,
            "new_vulnerabilities_introduced": 0,
            "raw_findings": [],
            "exit_reason": "error",
        }

    finally:
        try:
            if base_metrics.end_time == 0:
                base_metrics.finalize(None, "error")
            vuln_metrics.save(log_dir / "metrics.json")
        except Exception:
            pass

        if session is not None:
            try:
                session.cleanup()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

        close_logger(logger)


# ---------------------------------------------------------------------------
# Resume support
# ---------------------------------------------------------------------------

def _load_completed_ids(results_dir: Path) -> set[str]:
    completed: set[str] = set()
    if results_dir.exists():
        for f in results_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                completed.add(data["instance_id"])
            except Exception:
                pass
    return completed


def _save_result(results_dir: Path, result: dict) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / f"{result['instance_id']}.json"
    path.write_text(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(
    projects: list[str] | None,
    tracks: list[int] | None,
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
):
    assert run_id, "run_id must be provided"
    assert agent in ("claude",), f"Only 'claude' agent is supported; got {agent!r}"

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    results_dir = out / "results" / run_id

    instances = load_dataset(projects=projects, tracks=tracks)
    if not instances:
        print("No instances found.")
        return

    completed_ids = _load_completed_ids(results_dir)
    remaining = [i for i in instances if i.instance_id not in completed_ids]
    if not remaining:
        print(f"All {len(instances)} instances already completed.")
        return

    skipped = len(instances) - len(remaining)
    if skipped:
        print(f"Skipping {skipped} already-completed instances.")
    print(f"Running on {len(remaining)} instances...")

    if platform.system() == "Linux":
        resource.setrlimit(resource.RLIMIT_NOFILE, (4096, 4096))

    client = docker.from_env()
    existing_images = list_images(client)

    print("Building project images...")
    build_all_project_images(remaining, client, force_rebuild)

    all_results: list[dict] = []
    pbar = tqdm(remaining, desc="Running VulnAgentBench", unit="instance")

    for instance in pbar:
        pbar.set_postfix_str(f"{instance.instance_id}")

        result = run_instance(
            instance=instance,
            model_name_or_path=model_name_or_path,
            max_iterations=max_iterations,
            agent_timeout=agent_timeout,
            command_timeout=command_timeout,
            client=client,
            run_id=run_id,
            output_dir=out,
            force_rebuild=force_rebuild,
        )

        _save_result(results_dir, result)
        all_results.append(result)

    clean_images(client, existing_images, cache_level, clean)

    # Write aggregate summary
    if all_results:
        from swebench.security.reporting import generate_report
        generate_report(results_dir, run_id, output_dir=out)


if __name__ == "__main__":
    parser = ArgumentParser(
        description="Run VulnAgentBench: security vulnerability detection benchmark.",
        formatter_class=ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--projects",
        nargs="+",
        choices=["project_a", "project_b", "project_c"],
        default=None,
        help="Projects to run (default: all)",
    )
    parser.add_argument(
        "--tracks",
        nargs="+",
        type=int,
        choices=[1, 2, 3],
        default=None,
        help="Tracks to run (default: all)",
    )
    parser.add_argument(
        "--agent",
        type=str,
        default="claude",
        choices=["claude"],
        help="Agent backend to use",
    )
    parser.add_argument(
        "--model_name_or_path",
        type=str,
        default="claude-sonnet-4-20250514",
        help="Model name for the agent",
    )
    parser.add_argument(
        "--max_iterations",
        type=int,
        default=30,
        help="Max agent loop iterations per instance",
    )
    parser.add_argument(
        "--agent_timeout",
        type=int,
        default=1800,
        help="Wall-clock timeout (seconds) per instance",
    )
    parser.add_argument(
        "--command_timeout",
        type=int,
        default=120,
        help="Timeout (seconds) per shell command",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="./vuln_results",
        help="Output directory for results and logs",
    )
    parser.add_argument(
        "--run_id",
        type=str,
        required=True,
        help="Unique run identifier",
    )
    parser.add_argument(
        "--max_workers",
        type=int,
        default=1,
        help="Workers for parallel image building (currently unused)",
    )
    parser.add_argument(
        "--force_rebuild",
        action="store_true",
        default=False,
        help="Force rebuild Docker images",
    )
    parser.add_argument(
        "--cache_level",
        type=str,
        choices=["none", "base", "env", "instance"],
        default="instance",
        help="Docker image cache level",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        default=False,
        help="Remove Docker images above cache_level after run",
    )

    args = parser.parse_args()
    main(**vars(args))
