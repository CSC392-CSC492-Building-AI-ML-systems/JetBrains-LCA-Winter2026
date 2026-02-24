from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from swebench.agent.container_session import ContainerSession
    from swebench.agent.metrics import AgentMetrics
    from swebench.harness.constants import SWEbenchInstance


@dataclass
class AgentResult:
    instance_id: str
    model_name_or_path: str
    model_patch: Optional[str]
    metrics: AgentMetrics
    exit_reason: str


class AgentBase(ABC):
    def __init__(self, model_name_or_path: str, **kwargs):
        self.model_name_or_path = model_name_or_path

    @abstractmethod
    def solve(
        self,
        instance: SWEbenchInstance,
        session: ContainerSession,
        metrics: AgentMetrics,
    ) -> AgentResult:
        ...
