
from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING

# Requires: pip install google-genai
from google import genai
from google.genai import types

from swebench.agent.agent_base import AgentBase, AgentResult
from swebench.agent.prompts import get_system_prompt, get_user_prompt

if TYPE_CHECKING:
    from swebench.agent.container_session import ContainerSession
    from swebench.agent.metrics import AgentMetrics
    from swebench.harness.constants import SWEbenchInstance

# 1. Define Tools for Gemini
execute_command_decl = types.FunctionDeclaration(
    name="execute_command",
    description="Execute a shell command in the Docker container at /testbed. Returns the command output (stdout+stderr) and exit code.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "command": {"type": "STRING", "description": "The shell command to execute."},
            "timeout": {"type": "INTEGER", "description": "Optional timeout in seconds for this command. Defaults to 120 seconds."}
        },
        "required": ["command"]
    }
)

submit_patch_decl = types.FunctionDeclaration(
    name="submit_patch",
    description="Submit your fix. Call this when you believe you have fixed the bug. Your changes (git diff) will be captured automatically.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "reasoning": {"type": "STRING", "description": "Brief explanation of the fix."}
        },
        "required": ["reasoning"]
    }
)

give_up_decl = types.FunctionDeclaration(
    name="give_up",
    description="Signal that you cannot fix the bug. Any partial changes will still be captured.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "reason": {"type": "STRING", "description": "Why you are giving up."}
        },
        "required": ["reason"]
    }
)

class GeminiAgent(AgentBase):
    ""

    def solve(
        self,
        instance: SWEbenchInstance,
        session: ContainerSession,
        metrics: AgentMetrics,
    ) -> AgentResult:
        
        
        metrics.iterations = 0
        patch = session.get_patch()
        exit_reason = "completed"
        metrics.finalize(patch or None, exit_reason)
        return AgentResult(
            instance_id=instance["instance_id"],
            model_name_or_path=self.model_name_or_path,
            model_patch=patch or None,
            metrics=metrics,
            exit_reason=exit_reason,
        )

DEFAULT_MODEL = "gemini-3.1-pro"
OUTPUT_TRUNCATION_CHARS = 50_000
HALF_TRUNCATION = OUTPUT_TRUNCATION_CHARS // 2


GEMINI_TOOLS = types.Tool(
    function_declarations=[execute_command_decl, submit_patch_decl, give_up_decl]
)

class GeminiAgent(AgentBase):
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
        self.max_token_budget = max_token_budget
        # Initializes the client; assumes GEMINI_API_KEY is in the environment
        self.api_client = genai.Client()

    def solve(
        self,
        instance: SWEbenchInstance,
        session: ContainerSession,
        metrics: AgentMetrics,
    ) -> AgentResult:
        logger = session.logger
        system_prompt = get_system_prompt(instance)
        user_prompt = get_user_prompt(instance)

        # Gemini uses 'user' and 'model' roles via Content and Part objects
        messages = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_prompt)]
            )
        ]
        
        # Configuration block
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[GEMINI_TOOLS],
            temperature=0.0,
        )

        exit_reason = "max_iterations"
        start_wall = time.time()

        for iteration in range(1, self.max_iterations + 1):
            elapsed = time.time() - start_wall
            if elapsed > self.agent_timeout:
                exit_reason = "timeout"
                logger.info(f"Agent timeout after {elapsed:.0f}s at iteration {iteration}")
                break

            metrics.iterations = iteration
            logger.info(f"--- Iteration {iteration}/{self.max_iterations} ---")

            try:
                response = self.api_client.models.generate_content(
                    model=self.model_name_or_path,
                    contents=messages,
                    config=config,
                )
            except Exception as e:
                logger.error(f"API error at iteration {iteration}: {e}")
                exit_reason = "error"
                break

            # Track tokens
            usage = getattr(response, "usage_metadata", None)
            if usage:
                metrics.input_tokens += getattr(usage, "prompt_token_count", 0)
                metrics.output_tokens += getattr(usage, "candidates_token_count", 0)

            if self.max_token_budget > 0:
                total_used = metrics.input_tokens + metrics.output_tokens
                if total_used >= self.max_token_budget:
                    logger.info(f"Token budget exhausted: {total_used} >= {self.max_token_budget}")
                    exit_reason = "token_budget"
                    break

            if not response.candidates:
                logger.error("No candidates returned from API.")
                exit_reason = "error"
                break

            # Append the model's exact response back into the history
            assistant_content = response.candidates[0].content
            messages.append(assistant_content)

            # Log text blocks and find function calls
            function_calls = []
            for part in assistant_content.parts:
                if part.text:
                    logger.info(f"Agent: {part.text[:500]}")
                if part.function_call:
                    function_calls.append(part.function_call)

            # Check stop reason
            if not function_calls:
                logger.info("Model stopped without tool use.")
                exit_reason = "completed"
                break

            # Process tool calls
            tool_responses = []
            should_break = False

            for fc in function_calls:
                tool_name = fc.name
                tool_input = dict(fc.args) if fc.args else {}

                logger.info(f"Tool call: {tool_name}({json.dumps(tool_input)[:200]})")

                if tool_name == "execute_command":
                    result_text = self._handle_execute(
                        session, metrics, tool_input, logger
                    )
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response={"output": result_text}
                        )
                    )

                elif tool_name == "submit_patch":
                    reasoning = tool_input.get("reasoning", "")
                    logger.info(f"Agent submitted patch. Reasoning: {reasoning}")
                    exit_reason = "completed"
                    should_break = True
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response={"status": "Patch submitted successfully."}
                        )
                    )

                elif tool_name == "give_up":
                    reason = tool_input.get("reason", "")
                    logger.info(f"Agent gave up. Reason: {reason}")
                    exit_reason = "gave_up"
                    should_break = True
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response={"status": "Acknowledged."}
                        )
                    )

                else:
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response={"error": f"Unknown tool: {tool_name}"}
                        )
                    )

            if tool_responses:
                # Append the execution results so the model can read them on the next loop
                messages.append(
                    types.Content(
                        role="user",
                        parts=tool_responses
                    )
                )

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
        timeout_val = tool_input.get("timeout")
        timeout = int(timeout_val) if timeout_val is not None else None

        metrics.commands_executed += 1
        result = session.execute(command, timeout=timeout)

        if result.timed_out:
            metrics.commands_timed_out += 1

        output = result.output
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