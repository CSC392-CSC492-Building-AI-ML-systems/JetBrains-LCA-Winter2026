from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from typing import TYPE_CHECKING

from swebench.agent.agent_base import AgentBase, AgentResult

if TYPE_CHECKING:
    from swebench.agent.container_session import ContainerSession
    from swebench.agent.metrics import AgentMetrics
    from swebench.harness.constants import SWEbenchInstance


DEFAULT_MAX_BUDGET_USD = 1.0

_KEEP_KEYS = {
"PATH", "HOME", "USER", "SHELL", "LANG", "LC_ALL", "LC_CTYPE",
"TERM", "TMPDIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME",
"DOCKER_HOST", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH",  # Docker connectivity
}


def _clean_env() -> dict[str, str]:
    """Build a minimal clean environment with no Claude Code session state."""
    return {k: v for k, v in os.environ.items() if k in _KEEP_KEYS}


class OpenAICodexAgent(AgentBase):
    """Agent that uses OpenAI Codex models via the OpenAI API.

    The agent interacts with the Docker container by executing commands via
    the `execute_command` tool, which runs commands in the container and returns
    their output. The agent can also submit a patch when it thinks it's ready.
    """

    def __init__(
        self,
        model_name_or_path: str = "code-davinci-002",
        max_iterations: int = 30,
        agent_timeout: int = 1800,
        max_budget_usd: float = DEFAULT_MAX_BUDGET_USD,
        **kwargs,
    ):
        super().__init__(model_name_or_path=model_name_or_path, **kwargs)
        self.max_iterations = max_iterations
        self.agent_timeout = agent_timeout
        self.max_budget_usd = max_budget_usd

        # Verify codex CLI is available
        self.codex_path = shutil.which("codex")
        if not self.codex_path:
            raise RuntimeError(
                "Codex CLI not found. Install it."
                # "https://docs.anthropic.com/en/docs/claude-code"
            )
        
    def solve(
        self,
        instance: SWEbenchInstance,
        session: ContainerSession,
        metrics: AgentMetrics,
    ) -> AgentResult:
        
        logger = session.logger

        container_name = session.container.name
        repo = instance["repo"]
        problem_statement = instance["problem_statement"]
        
        prompt = self._build_prompt(container_name, repo, problem_statement)
        system_prompt = self._build_system_prompt(container_name)

        logger.info(f"Launching Codex for {instance['instance_id']}")
        logger.info(f"Container: {container_name}")
        logger.info(f"Model: {self.model_name_or_path}")
        logger.info(f"Budget: ${self.max_budget_usd}")

        cmd = [
            self.codex_path,
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            # "--model", self.model_name_or_path,
            "-c developer_instructions={system_prompt}"
            "--json",
            "--output-last-message", "./results_json.txt",
            prompt, 
        ]

        start_time = time.time()
        exit_reason = "completed"

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.agent_timeout,
                cwd="/tmp",
                # env=env,
            )

            elapsed = time.time() - start_time
            logger.info(f"Codex finished in {elapsed:.1f}s (exit code {proc.returncode})")

            # Log stderr (contains progress info)
            if proc.stderr:
                logger.info(f"Codex stderr:\n{proc.stderr[:2000]}")

            print(f"Codex raw output:\n{proc.stdout[:2000]}")
            with open("./results.txt", "w") as file:
                file.write(proc.stdout)
        
        except subprocess.TimeoutExpired:
            print("Timedout")
            logger.error(f"Codex timed out after {self.agent_timeout}s")
            exit_reason = "timeout"

        except Exception as e:
            print("error")
            logger.error(f"Failed to run Codex: {e}")
            exit_reason = "error"

        return AgentResult(
            instance_id=instance["instance_id"],
            model_name_or_path=self.model_name_or_path,
            model_patch=None,
            metrics=metrics,
            exit_reason=exit_reason,
        )

    def _build_system_prompt(self, container_name: str) -> str:
        return f"""\
You are an expert software engineer fixing a bug inside a Docker container.

IMPORTANT: All commands MUST be run inside the Docker container using:
  docker exec {container_name} bash -c '<command>'

The repository is at /testbed inside the container. Examples:
  docker exec {container_name} bash -c 'ls /testbed'
  docker exec {container_name} bash -c 'cd /testbed && git diff'
  docker exec {container_name} bash -c 'cd /testbed && cat path/to/file.py'
  docker exec {container_name} bash -c 'cd /testbed && python -m pytest tests/test_foo.py'

To edit files, use sed or a heredoc via docker exec. Do NOT use local tools \
like Edit or Write — those operate on the host, not in the container.

Guidelines:
1. Explore the codebase first — read the problem, find the relevant code.
2. Reproduce the bug with a small test or script.
3. Make minimal changes — only fix the bug, don't refactor unrelated code.
4. Run the relevant tests to verify your fix.
5. When done, just say you're finished. Your changes will be captured via git diff."""

    def _build_prompt(
        self,
        container_name: str,
        repo: str,
        problem_statement: str,
    ) -> str:
        return f"""\
Fix the following bug in the `{repo}` repository. The repo is checked out \
inside the Docker container `{container_name}` at `/testbed`.

## Problem Statement

{problem_statement}

Start by exploring the repository structure and understanding the relevant \
code, then reproduce the bug, implement a fix, and verify it with tests. \
Remember: all commands must be run via `docker exec {container_name} bash -c '...'`."""
    
if __name__ == "__main__":
    # Basic smoke test
    agent = OpenAICodexAgent()
    print("OpenAICodexAgent initialized successfully")