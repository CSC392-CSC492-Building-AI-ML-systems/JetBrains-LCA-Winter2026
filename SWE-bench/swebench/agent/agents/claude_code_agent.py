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


class ClaudeCodeAgent(AgentBase):
    """Agent that delegates to the locally installed `claude` CLI (Claude Code).

    Instead of calling the Anthropic API directly, this spawns `claude --print`
    as a subprocess. Claude Code uses its own authentication (OAuth or API key)
    so no separate ANTHROPIC_API_KEY is needed.

    The agent tells Claude Code to interact with the Docker container via
    `docker exec`, so it can explore the repo, edit files, and run tests
    just like a human would.
    """

    def __init__(
        self,
        model_name_or_path: str = "sonnet",
        max_iterations: int = 30,
        agent_timeout: int = 1800,
        max_budget_usd: float = DEFAULT_MAX_BUDGET_USD,
        **kwargs,
    ):
        super().__init__(model_name_or_path=model_name_or_path, **kwargs)
        self.max_iterations = max_iterations
        self.agent_timeout = agent_timeout
        self.max_budget_usd = max_budget_usd

        # Verify claude CLI is available
        self.claude_path = shutil.which("claude")
        if not self.claude_path:
            raise RuntimeError(
                "Claude Code CLI not found. Install it from "
                "https://docs.anthropic.com/en/docs/claude-code"
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

        logger.info(f"Launching Claude Code for {instance['instance_id']}")
        logger.info(f"Container: {container_name}")
        logger.info(f"Model: {self.model_name_or_path}")
        logger.info(f"Budget: ${self.max_budget_usd}")

        cmd = [
            self.claude_path,
            "--print",
            "--output-format", "json",
            "--model", self.model_name_or_path,
            "--max-budget-usd", str(self.max_budget_usd),
            "--dangerously-skip-permissions",
            "--system-prompt", system_prompt,
            "--allowedTools", f"Bash(docker exec {container_name}:*)",
            "-p", prompt,
        ]

        start_time = time.time()
        exit_reason = "completed"

        # Build a clean environment so this is a fully independent Claude Code session,
        # not a nested one (Claude Code refuses to launch inside another session).
        env = _clean_env()

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.agent_timeout,
                cwd="/tmp",
                env=env,
            )

            elapsed = time.time() - start_time
            logger.info(f"Claude Code finished in {elapsed:.1f}s (exit code {proc.returncode})")

            # Log stderr (contains progress info)
            if proc.stderr:
                logger.info(f"Claude Code stderr:\n{proc.stderr[:2000]}")

            # Parse JSON output
            result_data = self._parse_output(proc.stdout, logger)

            if result_data:
                metrics.input_tokens = result_data.get("input_tokens", 0)
                metrics.output_tokens = result_data.get("output_tokens", 0)
                # Count tool uses as iterations
                num_turns = result_data.get("num_turns", 0)
                metrics.iterations = num_turns

            if proc.returncode != 0:
                logger.error(f"Claude Code exited with code {proc.returncode}")
                exit_reason = "error"

        except subprocess.TimeoutExpired:
            logger.error(f"Claude Code timed out after {self.agent_timeout}s")
            exit_reason = "timeout"

        except Exception as e:
            logger.error(f"Failed to run Claude Code: {e}")
            exit_reason = "error"

        # Capture the patch from the container
        try:
            patch = session.get_patch()
        except Exception as e:
            logger.error(f"Failed to get patch: {e}")
            patch = ""

        model_patch = patch if patch else None
        metrics.finalize(model_patch, exit_reason)

        return AgentResult(
            instance_id=instance["instance_id"],
            model_name_or_path=self.model_name_or_path,
            model_patch=model_patch,
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

    def _parse_output(self, stdout: str, logger: logging.Logger) -> dict | None:
        """Parse Claude Code's JSON output to extract token usage."""
        if not stdout.strip():
            return None

        try:
            data = json.loads(stdout)
            # Claude Code --output-format json returns:
            # {"result": "...", "input_tokens": N, "output_tokens": N, "num_turns": N, ...}
            return data
        except json.JSONDecodeError:
            # Might be multiple JSON objects or plain text
            logger.warning(f"Could not parse Claude Code output as JSON (len={len(stdout)})")
            # Try to find the last JSON object
            for line in reversed(stdout.strip().split("\n")):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
            return None


# Keys to keep from the parent environment for independent Claude Code sessions.
# Intentionally excludes ANTHROPIC_API_KEY — Claude Code uses its own OAuth auth,
# and passing the key would let the model read it via `env` on the host.
_KEEP_KEYS = {
    "PATH", "HOME", "USER", "SHELL", "LANG", "LC_ALL", "LC_CTYPE",
    "TERM", "TMPDIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME",
    "DOCKER_HOST", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH",  # Docker connectivity
}


def _clean_env() -> dict[str, str]:
    """Build a minimal clean environment with no Claude Code session state."""
    return {k: v for k, v in os.environ.items() if k in _KEEP_KEYS}
