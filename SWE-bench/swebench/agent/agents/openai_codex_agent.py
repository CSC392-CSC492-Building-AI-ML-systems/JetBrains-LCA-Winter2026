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
        pass

if __name__ == "__main__":
    # Basic smoke test
    agent = OpenAICodexAgent()
    print("OpenAICodexAgent initialized successfully")