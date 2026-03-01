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
            "-c", f"developer_instructions={system_prompt}",
            "--json",
            prompt
        ]

        start_time = time.time()
        exit_reason = "completed"

        num_reasoning_steps, num_execution_steps, input_tokens, output_tokens = 0, 0, 0, 0

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

            num_reasoning_steps, num_execution_steps, input_tokens, output_tokens = self._parse_output(proc.stdout)
            metrics.iterations = num_reasoning_steps
            metrics.commands_executed = num_execution_steps
            metrics.input_tokens = input_tokens
            metrics.output_tokens = output_tokens
        
        except subprocess.TimeoutExpired:
            print("Timedout")
            logger.error(f"Codex timed out after {self.agent_timeout}s")
            exit_reason = "timeout"

        except Exception as e:
            print("error")
            logger.error(f"Failed to run Codex: {e}")
            exit_reason = "error"

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
    
    def _parse_output(self, output: str):
        lines = output.split('\n')
        num_reasoning_steps = 0
        num_execution_steps = 0
        input_tokens = 0
        output_tokens = 0
        for line in lines:
            try:
                j = json.loads(line)
                if j.get("item") and j.get("item").get("type") == "reasoning":
                    num_reasoning_steps += 1
                elif j.get("type", "") == "item.started" and j.get("item") and j.get("item").get("type") == "reasoning":
                    num_execution_steps += 1

            except Exception as e:
                pass
        pass

        # Get the last line
        last_line = lines[-2]
        try:
            j = json.loads(last_line)
            input_tokens = j.get("usage").get("input_tokens")
            output_tokens = j.get("usage").get("output_tokens")
        except Exception as e:
            pass

        return num_reasoning_steps, num_execution_steps, input_tokens, output_tokens

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