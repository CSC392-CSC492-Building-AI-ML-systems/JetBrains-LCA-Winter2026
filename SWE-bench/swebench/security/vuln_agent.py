from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING

from swebench.agent.agent_base import AgentResult
from swebench.agent.agents.claude_agent import ClaudeAgent
from swebench.security.prompts import get_system_prompt
from swebench.security.tools import get_tools_for_track

if TYPE_CHECKING:
    from swebench.agent.container_session import ContainerSession
    from swebench.agent.metrics import AgentMetrics
    from swebench.security.dataset import VulnInstance


class VulnAgent(ClaudeAgent):
    """
    Security-focused agent for VulnAgentBench.

    Extends ClaudeAgent with submit_findings tool support and track-specific
    prompts/tools. The agent's findings are stored on self._findings after solve()
    returns for the caller to read.
    """

    def solve(
        self,
        instance: VulnInstance,
        session: ContainerSession,
        metrics: AgentMetrics,
    ) -> AgentResult:
        logger = session.logger
        system_prompt = get_system_prompt(instance.track)
        user_prompt = instance.prompt

        self._findings: list[dict] = []

        messages = [{"role": "user", "content": user_prompt}]
        tools = get_tools_for_track(instance.track)
        exit_reason = "max_iterations"
        start_wall = time.time()

        for iteration in range(1, self.max_iterations + 1):
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
                    tools=tools,
                    messages=messages,
                )
            except Exception as e:
                logger.error(f"API error at iteration {iteration}: {e}")
                exit_reason = "error"
                break

            metrics.input_tokens += response.usage.input_tokens
            metrics.output_tokens += response.usage.output_tokens

            if self.max_token_budget > 0:
                total_used = metrics.input_tokens + metrics.output_tokens
                if total_used >= self.max_token_budget:
                    logger.info(
                        f"Token budget exhausted: {total_used} >= {self.max_token_budget}"
                    )
                    exit_reason = "token_budget"
                    break

            assistant_message = {"role": "assistant", "content": response.content}
            messages.append(assistant_message)

            for block in response.content:
                if block.type == "text":
                    logger.info(f"Agent: {block.text[:500]}")

            if response.stop_reason != "tool_use":
                logger.info(
                    f"Model stopped without tool use (stop_reason={response.stop_reason})"
                )
                exit_reason = "completed"
                break

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

                elif tool_name == "submit_findings":
                    result_text, findings = self._handle_submit_findings(
                        tool_input, logger
                    )
                    self._findings.extend(findings)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": result_text,
                        }
                    )
                    # Tracks 1 and 2 end after findings submission
                    if instance.track in (1, 2):
                        exit_reason = "completed"
                        should_break = True

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

        # Capture patch (relevant for track 3)
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

    def _handle_submit_findings(
        self,
        tool_input: dict,
        logger: logging.Logger,
    ) -> tuple[str, list[dict]]:
        findings = tool_input.get("findings", [])
        if not isinstance(findings, list):
            return "Error: findings must be a list.", []

        logger.info(f"Agent submitted {len(findings)} finding(s).")
        for i, f in enumerate(findings):
            logger.info(
                f"  Finding {i + 1}: {f.get('vuln_type', '?')} in "
                f"{f.get('file', '?')}:{f.get('line', '?')} "
                f"[{f.get('cwe_id', '?')}] severity={f.get('severity', '?')}"
            )

        return f"Findings submitted: {len(findings)} issue(s) recorded.", findings
