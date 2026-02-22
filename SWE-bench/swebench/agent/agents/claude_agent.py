from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING

import anthropic

from swebench.agent.agent_base import AgentBase, AgentResult
from swebench.agent.prompts import get_system_prompt, get_user_prompt

if TYPE_CHECKING:
    from swebench.agent.container_session import ContainerSession
    from swebench.agent.metrics import AgentMetrics
    from swebench.harness.constants import SWEbenchInstance

DEFAULT_MODEL = "claude-sonnet-4-20250514"
OUTPUT_TRUNCATION_CHARS = 50_000
HALF_TRUNCATION = OUTPUT_TRUNCATION_CHARS // 2

TOOLS = [
    {
        "name": "execute_command",
        "description": (
            "Execute a shell command in the Docker container at /testbed. "
            "Returns the command output (stdout+stderr) and exit code."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute.",
                },
                "timeout": {
                    "type": "integer",
                    "description": (
                        "Optional timeout in seconds for this command. "
                        "Defaults to 120 seconds."
                    ),
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "submit_patch",
        "description": (
            "Submit your fix. Call this when you believe you have fixed the bug. "
            "Your changes (git diff) will be captured automatically."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of the fix.",
                },
            },
            "required": ["reasoning"],
        },
    },
    {
        "name": "give_up",
        "description": (
            "Signal that you cannot fix the bug. "
            "Any partial changes will still be captured."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why you are giving up.",
                },
            },
            "required": ["reason"],
        },
    },
]


class ClaudeAgent(AgentBase):
    def __init__(
        self,
        model_name_or_path: str = DEFAULT_MODEL,
        max_iterations: int = 30,
        agent_timeout: int = 1800,
        max_token_budget: int = 0,
        **kwargs,
    ):
        super().__init__(model_name_or_path=model_name_or_path, **kwargs)
        self.max_iterations = max_iterations
        self.agent_timeout = agent_timeout
        self.max_token_budget = max_token_budget  # 0 = unlimited
        self.api_client = anthropic.Anthropic()

    def solve(
        self,
        instance: SWEbenchInstance,
        session: ContainerSession,
        metrics: AgentMetrics,
    ) -> AgentResult:
        logger = session.logger
        system_prompt = get_system_prompt(instance)
        user_prompt = get_user_prompt(instance)

        messages = [{"role": "user", "content": user_prompt}]
        exit_reason = "max_iterations"
        start_wall = time.time()

        for iteration in range(1, self.max_iterations + 1):
            # Check wall-clock timeout
            elapsed = time.time() - start_wall
            if elapsed > self.agent_timeout:
                exit_reason = "timeout"
                logger.info(
                    f"Agent timeout after {elapsed:.0f}s at iteration {iteration}"
                )
                break

            metrics.iterations = iteration
            logger.info(f"--- Iteration {iteration}/{self.max_iterations} ---")

            try:
                response = self.api_client.messages.create(
                    model=self.model_name_or_path,
                    max_tokens=4096,
                    system=system_prompt,
                    tools=TOOLS,
                    messages=messages,
                )
            except Exception as e:
                logger.error(f"API error at iteration {iteration}: {e}")
                exit_reason = "error"
                break

            # Track tokens
            metrics.input_tokens += response.usage.input_tokens
            metrics.output_tokens += response.usage.output_tokens

            # Check token budget
            if self.max_token_budget > 0:
                total_used = metrics.input_tokens + metrics.output_tokens
                if total_used >= self.max_token_budget:
                    logger.info(
                        f"Token budget exhausted: {total_used} >= {self.max_token_budget}"
                    )
                    exit_reason = "token_budget"
                    break

            # Process response
            assistant_message = {"role": "assistant", "content": response.content}
            messages.append(assistant_message)

            # Log any text blocks
            for block in response.content:
                if block.type == "text":
                    logger.info(f"Agent: {block.text[:500]}")

            # Check stop reason
            if response.stop_reason != "tool_use":
                logger.info(
                    f"Model stopped without tool use (stop_reason={response.stop_reason})"
                )
                exit_reason = "completed"
                break

            # Process tool calls
            tool_results = []
            should_break = False

            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_input = block.input
                tool_use_id = block.id

                logger.info(f"Tool call: {tool_name}({json.dumps(tool_input)[:200]})")

                if tool_name == "execute_command":
                    result_text = self._handle_execute(
                        session, metrics, tool_input, logger
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": result_text,
                        }
                    )

                elif tool_name == "submit_patch":
                    reasoning = tool_input.get("reasoning", "")
                    logger.info(f"Agent submitted patch. Reasoning: {reasoning}")
                    exit_reason = "completed"
                    should_break = True
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": "Patch submitted successfully.",
                        }
                    )

                elif tool_name == "give_up":
                    reason = tool_input.get("reason", "")
                    logger.info(f"Agent gave up. Reason: {reason}")
                    exit_reason = "gave_up"
                    should_break = True
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": "Acknowledged.",
                        }
                    )

                else:
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": f"Unknown tool: {tool_name}",
                            "is_error": True,
                        }
                    )

            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            if should_break:
                break

        # Capture final patch
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

    def _handle_execute(
        self,
        session: ContainerSession,
        metrics: AgentMetrics,
        tool_input: dict,
        logger: logging.Logger,
    ) -> str:
        command = tool_input.get("command", "")
        timeout = tool_input.get("timeout")

        metrics.commands_executed += 1

        result = session.execute(command, timeout=timeout)

        if result.timed_out:
            metrics.commands_timed_out += 1

        output = result.output
        # Truncate large outputs for the API context
        if len(output) > OUTPUT_TRUNCATION_CHARS:
            output = (
                output[:HALF_TRUNCATION]
                + f"\n\n... [output truncated: {len(result.output)} chars total] ...\n\n"
                + output[-HALF_TRUNCATION:]
            )

        parts = [output] if output else []
        parts.append(f"Exit code: {result.exit_code}")
        if result.timed_out:
            parts.append(f"Command timed out after {result.duration_seconds:.1f}s")

        logger.info(
            f"  exit_code={result.exit_code} timed_out={result.timed_out} "
            f"output_len={len(result.output)} duration={result.duration_seconds:.1f}s"
        )

        return "\n".join(parts)
