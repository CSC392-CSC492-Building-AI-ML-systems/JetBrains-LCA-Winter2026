from __future__ import annotations

from typing import TYPE_CHECKING

from swebench.agent.agent_base import AgentBase, AgentResult

if TYPE_CHECKING:
    from swebench.agent.container_session import ContainerSession
    from swebench.agent.metrics import AgentMetrics
    from swebench.harness.constants import SWEbenchInstance


class DummyAgent(AgentBase):
    """No-op agent for pipeline testing. Produces no patch."""

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
