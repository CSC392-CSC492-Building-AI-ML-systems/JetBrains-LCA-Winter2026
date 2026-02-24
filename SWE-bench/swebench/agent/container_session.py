from __future__ import annotations

import logging
import shlex
from dataclasses import dataclass
from typing import TYPE_CHECKING

import docker

from swebench.harness.constants import DOCKER_USER, DOCKER_WORKDIR
from swebench.harness.docker_build import build_container
from swebench.harness.docker_utils import cleanup_container, exec_run_with_timeout

if TYPE_CHECKING:
    from swebench.harness.test_spec.test_spec import TestSpec

MAX_OUTPUT_BYTES = 100 * 1024  # 100KB
MAX_COMMAND_TIMEOUT = 600  # 10 minutes hard cap


@dataclass
class CommandResult:
    output: str
    exit_code: int
    timed_out: bool
    duration_seconds: float


class ContainerSession:
    def __init__(
        self,
        test_spec: TestSpec,
        client: docker.DockerClient,
        run_id: str,
        logger: logging.Logger,
        command_timeout: int = 120,
        force_rebuild: bool = False,
    ):
        self.test_spec = test_spec
        self.client = client
        self.run_id = run_id
        self.logger = logger
        self.command_timeout = command_timeout
        self.force_rebuild = force_rebuild
        self.container = None

    def start(self) -> None:
        self.logger.info(
            f"Building container for {self.test_spec.instance_id}..."
        )
        self.container = build_container(
            test_spec=self.test_spec,
            client=self.client,
            run_id=self.run_id,
            logger=self.logger,
            nocache=False,
            force_rebuild=self.force_rebuild,
        )
        self.container.start()
        self.logger.info(
            f"Container {self.container.name} started for {self.test_spec.instance_id}"
        )

    def execute(
        self,
        command: str,
        timeout: int | None = None,
        workdir: str = DOCKER_WORKDIR,
    ) -> CommandResult:
        if self.container is None:
            raise RuntimeError("Container not started. Call start() first.")

        # Clamp timeout to prevent unbounded waits
        if timeout is not None and timeout > 0:
            timeout = min(timeout, MAX_COMMAND_TIMEOUT)
        else:
            timeout = self.command_timeout

        # Wrap command to capture exit code reliably
        wrapped = (
            f"cd {shlex.quote(workdir)} && "
            f"({command}) 2>&1; echo \"SWEBENCH_EXIT:$?\""
        )

        output, timed_out, duration = exec_run_with_timeout(
            self.container,
            f"/bin/bash -c {shlex.quote(wrapped)}",
            timeout=timeout,
        )

        # Parse exit code from output
        exit_code = -1
        lines = output.rstrip("\n").split("\n")
        if not timed_out and lines:
            last_line = lines[-1]
            if last_line.startswith("SWEBENCH_EXIT:"):
                try:
                    exit_code = int(last_line.split(":", 1)[1])
                except ValueError:
                    pass
                output = "\n".join(lines[:-1])

        # Truncate if output is too large
        if len(output) > MAX_OUTPUT_BYTES:
            half = MAX_OUTPUT_BYTES // 2
            output = (
                output[:half]
                + f"\n\n... [output truncated: {len(output)} bytes total] ...\n\n"
                + output[-half:]
            )

        return CommandResult(
            output=output,
            exit_code=exit_code,
            timed_out=timed_out,
            duration_seconds=duration,
        )

    def get_patch(self) -> str:
        if self.container is None:
            raise RuntimeError("Container not started. Call start() first.")

        result = self.execute("git diff", workdir=DOCKER_WORKDIR)
        return result.output.strip()

    def cleanup(self) -> None:
        cleanup_container(self.client, self.container, self.logger)
        self.container = None

    def __enter__(self) -> ContainerSession:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.cleanup()
        return None
