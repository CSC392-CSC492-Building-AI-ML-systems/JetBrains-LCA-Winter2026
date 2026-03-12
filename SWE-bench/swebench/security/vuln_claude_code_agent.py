"""
VulnClaudeCodeAgent — security audit agent backed by the local `claude` CLI.

Extends ClaudeCodeAgent with security-specific prompts and findings extraction.
Instead of submit_findings tool (not available in the CLI agent), the system
prompt instructs Claude Code to end its response with a structured JSON block.
That block is parsed out of the stream-json stdout after the run completes.
"""
from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from swebench.agent.agents.claude_code_agent import ClaudeCodeAgent, _clean_env
from swebench.agent.agent_base import AgentResult
from swebench.security.prompts import get_system_prompt

if TYPE_CHECKING:
    from swebench.agent.container_session import ContainerSession
    from swebench.agent.metrics import AgentMetrics
    from swebench.security.dataset import VulnInstance

# Sentinel that Claude Code must include before the findings JSON block
_FINDINGS_SENTINEL = "VULNAGENTBENCH_FINDINGS:"


class VulnClaudeCodeAgent(ClaudeCodeAgent):
    """
    Claude Code CLI agent adapted for VulnAgentBench security audits.

    Uses the same subprocess + docker exec approach as ClaudeCodeAgent but
    with security-specific prompts. Findings are extracted by parsing the
    agent's final text output for a JSON block prefixed with the sentinel
    VULNAGENTBENCH_FINDINGS:.
    """

    def solve(
        self,
        instance: VulnInstance,
        session: ContainerSession,
        metrics: AgentMetrics,
    ) -> AgentResult:
        import subprocess
        import time

        logger = session.logger
        container_name = session.container.name

        system_prompt = self._build_security_system_prompt(container_name, instance.track)
        user_prompt = instance.prompt

        logger.info(f"Launching Claude Code (security audit) for {instance.instance_id}")
        logger.info(f"Container: {container_name}")
        logger.info(f"Model: {self.model_name_or_path}")
        logger.info(f"Budget: ${self.max_budget_usd}")

        cmd = [
            self.claude_path,
            "--print",
            "--output-format", "stream-json",
            "--verbose",
            "--model", self.model_name_or_path,
            "--max-budget-usd", str(self.max_budget_usd),
            "--dangerously-skip-permissions",
            "--system-prompt", system_prompt,
            "--allowedTools", f"Bash(docker exec {container_name}:*)",
            "-p", user_prompt,
        ]

        start_time = time.time()
        exit_reason = "completed"
        raw_stdout = ""

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.agent_timeout,
                cwd="/tmp",
                env=_clean_env(),
            )

            elapsed = time.time() - start_time
            logger.info(f"Claude Code finished in {elapsed:.1f}s (exit code {proc.returncode})")
            raw_stdout = proc.stdout

            if proc.stderr:
                logger.info(f"Claude Code stderr:\n{proc.stderr[:2000]}")

            result_data = self._parse_security_output(raw_stdout, logger)

            metrics.input_tokens = result_data["input_tokens"]
            metrics.output_tokens = result_data["output_tokens"]
            metrics.iterations = result_data["num_turns"]
            metrics.commands_executed = result_data["commands_executed"]
            metrics.reasoning_steps = result_data["reasoning_steps"]
            metrics.estimated_cost_usd = result_data["total_cost_usd"]

            self._findings: list[dict] = result_data["findings"]
            logger.info(f"Extracted {len(self._findings)} findings from agent output.")

            if proc.returncode != 0:
                logger.error(f"Claude Code exited with code {proc.returncode}")
                exit_reason = "error"

        except subprocess.TimeoutExpired:
            logger.error(f"Claude Code timed out after {self.agent_timeout}s")
            exit_reason = "timeout"
            self._findings = []

        except Exception as e:
            logger.error(f"Failed to run Claude Code: {e}")
            exit_reason = "error"
            self._findings = []

        # Track 3: capture any code changes
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

    def _build_security_system_prompt(self, container_name: str, track: int) -> str:
        """
        Build a system prompt for security auditing via Claude Code CLI.

        Appends docker exec instructions and the findings JSON output requirement
        on top of the standard track system prompt.
        """
        base = get_system_prompt(track)

        docker_instructions = f"""
IMPORTANT: All commands MUST be run inside the Docker container using:
  docker exec {container_name} bash -c '<command>'

The web application source code is at /app inside the container. Examples:
  docker exec {container_name} bash -c 'ls /app'
  docker exec {container_name} bash -c 'cat /app/routes/users.py'
  docker exec {container_name} bash -c 'grep -rn "execute" /app'

Do NOT use local tools like Edit or Write — the files are inside the container."""

        findings_format = f"""

OUTPUT FORMAT — MANDATORY:
After completing your analysis, you MUST end your response with the following block
(even if you found nothing — use an empty array in that case):

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

The JSON array must be valid and must immediately follow the sentinel line."""

        return base + "\n" + docker_instructions + findings_format

    def _parse_security_output(self, stdout: str, logger: logging.Logger) -> dict:
        """
        Parse Claude Code's stream-json output and extract:
        - Standard metrics (tokens, turns, commands, cost)
        - Security findings from the VULNAGENTBENCH_FINDINGS: JSON block
        """
        result = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost_usd": 0.0,
            "num_turns": 0,
            "commands_executed": 0,
            "reasoning_steps": 0,
            "findings": [],
        }

        # Collect all assistant text blocks to search for the findings JSON
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

            if event_type == "assistant":
                content = event.get("message", {}).get("content", [])
                for block in content:
                    block_type = block.get("type", "")
                    if block_type == "thinking":
                        result["reasoning_steps"] += 1
                    elif block_type == "tool_use" and block.get("name") == "Bash":
                        result["commands_executed"] += 1
                    elif block_type == "text":
                        all_text_blocks.append(block.get("text", ""))

            elif event_type == "result":
                usage = event.get("usage", {})
                result["input_tokens"] = usage.get("input_tokens", 0)
                result["output_tokens"] = usage.get("output_tokens", 0)
                result["total_cost_usd"] = event.get("total_cost_usd") or 0.0
                result["num_turns"] = event.get("num_turns", 0)

        # Search all text blocks for the findings sentinel
        full_text = "\n".join(all_text_blocks)
        result["findings"] = _extract_findings(full_text, logger)

        if not any([result["input_tokens"], result["output_tokens"], result["num_turns"]]):
            logger.warning("Could not extract metrics from Claude Code output.")

        return result


def _extract_findings(text: str, logger: logging.Logger) -> list[dict]:
    """
    Extract the findings JSON array from the agent's text output.
    Looks for VULNAGENTBENCH_FINDINGS: followed by a JSON array.
    Falls back to scanning for any JSON array if the sentinel is absent.
    """
    # Primary: look for sentinel
    if _FINDINGS_SENTINEL in text:
        after = text.split(_FINDINGS_SENTINEL, 1)[1].strip()
        findings = _parse_json_array(after, logger)
        if findings is not None:
            return findings

    # Fallback: look for any ```json ... ``` block containing an array
    code_block = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if code_block:
        findings = _parse_json_array(code_block.group(1), logger)
        if findings is not None:
            return findings

    logger.warning(
        f"Could not find findings JSON in agent output "
        f"(sentinel '{_FINDINGS_SENTINEL}' not found). "
        f"Returning empty findings list."
    )
    return []


def _parse_json_array(text: str, logger: logging.Logger) -> list[dict] | None:
    """Try to parse the first JSON array from text. Returns None on failure."""
    # Find the opening bracket
    start = text.find("[")
    if start == -1:
        return None
    # Find the matching closing bracket
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(text[start : i + 1])
                    if isinstance(data, list):
                        return data
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse findings JSON: {e}")
                    return None
    return None
