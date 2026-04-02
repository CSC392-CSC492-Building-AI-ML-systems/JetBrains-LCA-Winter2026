"""
VulnCodexAgent — security audit agent backed by the local `codex` CLI.

Mirrors VulnClaudeCodeAgent but drives the OpenAI Codex CLI subprocess
(`codex exec --json`) instead of the claude CLI.

Actual NDJSON event shapes (verified against codex-cli 0.114.0):

  Thread start:
    {"type": "thread.started", "thread_id": "..."}

  Turn start:
    {"type": "turn.started"}

  Assistant text message:
    {"type": "item.completed",
     "item": {"id": "...", "type": "agent_message", "text": "..."}}

  Shell command started:
    {"type": "item.started",
     "item": {"id": "...", "type": "command_execution", "command": "...", ...}}

  Shell command completed:
    {"type": "item.completed",
     "item": {"id": "...", "type": "command_execution",
              "aggregated_output": "...", "exit_code": 0, ...}}

  Turn complete with token usage:
    {"type": "turn.completed",
     "usage": {"input_tokens": N, "cached_input_tokens": N, "output_tokens": N}}

Notes:
  - There is no dedicated system-prompt flag in `codex exec`. The security
    instructions are prepended directly to the user prompt.
  - The default model is GPT-5 (ChatGPT account). Model override via
    `-c model=...` only works with an OpenAI API key, not a ChatGPT account.
  - Findings are extracted from agent_message text blocks using the same
    VULNAGENTBENCH_FINDINGS: sentinel and JSON parser as VulnClaudeCodeAgent.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from typing import TYPE_CHECKING

from swebench.agent.agent_base import AgentBase, AgentResult
from swebench.security.prompts import get_system_prompt
from swebench.security.vuln_claude_code_agent import _FINDINGS_SENTINEL, _extract_findings

if TYPE_CHECKING:
    from swebench.agent.container_session import ContainerSession
    from swebench.agent.metrics import AgentMetrics
    from swebench.security.dataset import VulnInstance


class VulnCodexAgent(AgentBase):
    """
    Codex CLI agent adapted for VulnAgentBench security audits.

    Uses `codex exec --json` to spawn the Codex CLI as a subprocess.
    Security instructions are embedded in the prompt (no separate system-prompt
    flag). Findings are extracted from agent_message text blocks using the
    VULNAGENTBENCH_FINDINGS: sentinel.
    """

    def __init__(
        self,
        model_name_or_path: str = "default",
        agent_timeout: int = 600,
        max_budget_usd: float = 1.0,
        **kwargs,
    ):
        super().__init__(model_name_or_path=model_name_or_path, **kwargs)
        self.agent_timeout = agent_timeout
        self.max_budget_usd = max_budget_usd
        self._findings: list[dict] = []

        self.codex_path = shutil.which("codex")
        if not self.codex_path:
            raise RuntimeError(
                "Codex CLI not found. Install with: npm install -g @openai/codex"
            )

    def solve(
        self,
        instance: "VulnInstance",
        session: "ContainerSession",
        metrics: "AgentMetrics",
    ) -> AgentResult:
        logger = session.logger
        container_name = session.container.name

        # Codex has no --system-prompt flag, so prepend the security context
        # directly to the user prompt.
        full_prompt = self._build_full_prompt(container_name, instance)

        logger.info(f"Launching Codex (security audit) for {instance.instance_id}")
        logger.info(f"Container: {container_name}")

        cmd = [
            self.codex_path,
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "--skip-git-repo-check",
            "--json",
            full_prompt,
        ]

        # Model override only works with an OpenAI API key, not ChatGPT account.
        # Only add it when an explicit (non-default) model is requested.
        if self.model_name_or_path and self.model_name_or_path != "default":
            cmd = cmd[:3] + ["-c", f'model="{self.model_name_or_path}"'] + cmd[3:]

        start_time = time.time()
        exit_reason = "completed"

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.agent_timeout,
                cwd="/tmp",
            )

            elapsed = time.time() - start_time
            logger.info(
                f"Codex finished in {elapsed:.1f}s (exit code {proc.returncode})"
            )

            if proc.stderr:
                logger.info(f"Codex stderr:\n{proc.stderr[:2000]}")

            result_data = self._parse_security_output(proc.stdout, logger)

            metrics.input_tokens = result_data["input_tokens"]
            metrics.output_tokens = result_data["output_tokens"]
            metrics.iterations = result_data["num_turns"]
            metrics.commands_executed = result_data["num_execution_steps"]
            metrics.reasoning_steps = 0  # Codex CLI does not expose reasoning events

            self._findings = result_data["findings"]
            logger.info(f"Extracted {len(self._findings)} findings from Codex output.")

            if proc.returncode != 0:
                logger.error(f"Codex exited with code {proc.returncode}")
                exit_reason = "error"

        except subprocess.TimeoutExpired:
            logger.error(f"Codex timed out after {self.agent_timeout}s")
            exit_reason = "timeout"
            self._findings = []

        except Exception as e:
            logger.error(f"Failed to run Codex: {e}")
            exit_reason = "error"
            self._findings = []

        try:
            patch = session.get_patch()
        except Exception as e:
            logger.error(f"Failed to get patch: {e}")
            patch = ""

        model_patch = patch if patch else None
        metrics.finalize(model_patch, exit_reason)

        return AgentResult(
            instance_id=instance.instance_id,
            model_name_or_path=self.model_name_or_path,
            model_patch=model_patch,
            metrics=metrics,
            exit_reason=exit_reason,
        )

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_full_prompt(self, container_name: str, instance: "VulnInstance") -> str:
        """
        Combine the security system prompt, docker exec instructions, findings
        format, and the user task into a single prompt string.

        Codex has no --system-prompt flag, so everything goes into the
        user-visible prompt.
        """
        system_section = get_system_prompt(instance.track)

        docker_section = f"""
IMPORTANT: All commands MUST be run inside the Docker container using:
  docker exec {container_name} bash -c '<command>'

The web application source code is at /app inside the container. Examples:
  docker exec {container_name} bash -c 'ls /app'
  docker exec {container_name} bash -c 'cat /app/routes/users.py'
  docker exec {container_name} bash -c 'grep -rn "password" /app'

Do NOT operate on local files — everything is inside the container."""

        findings_section = f"""

OUTPUT FORMAT — MANDATORY:
After completing your analysis, you MUST end your response with the following
block (use an empty array if you found nothing):

{_FINDINGS_SENTINEL}
[
  {{
    "file": "relative/path/to/file.py",
    "line": 42,
    "vuln_type": "SQL Injection",
    "cwe_id": "CWE-89",
    "severity": "critical",
    "description": "Clear explanation of the vulnerability."
  }}
]

The JSON array must be valid and must immediately follow the sentinel line.

---

TASK:
{instance.prompt}"""

        return system_section + "\n" + docker_section + findings_section

    # ------------------------------------------------------------------
    # Output parsing
    # ------------------------------------------------------------------

    def _parse_security_output(
        self, stdout: str, logger: logging.Logger
    ) -> dict:
        """
        Parse the Codex --json NDJSON stream.

        Returns:
          input_tokens, output_tokens, num_turns, num_execution_steps, findings
        """
        result = {
            "input_tokens": 0,
            "output_tokens": 0,
            "num_turns": 0,
            "num_execution_steps": 0,
            "findings": [],
        }

        all_text_blocks: list[str] = []

        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type", "")
            item = event.get("item") or {}

            # Assistant text message
            if event_type == "item.completed" and item.get("type") == "agent_message":
                text = item.get("text", "")
                if text:
                    all_text_blocks.append(text)

            # Shell command started → count as execution step
            if event_type == "item.started" and item.get("type") == "command_execution":
                result["num_execution_steps"] += 1

            # Turn completed → token usage
            if event_type == "turn.completed":
                usage = event.get("usage", {})
                result["input_tokens"] += usage.get("input_tokens", 0)
                result["output_tokens"] += usage.get("output_tokens", 0)
                result["num_turns"] += 1

        full_text = "\n".join(all_text_blocks)
        result["findings"] = _extract_findings(full_text, logger)

        if not result["input_tokens"] and not result["output_tokens"]:
            logger.warning("Could not extract token usage from Codex output.")

        return result
