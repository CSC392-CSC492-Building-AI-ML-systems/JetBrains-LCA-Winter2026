from abc import ABC, abstractmethod
from typing import Dict, Any, List

from src.baselines.utils.type_utils import ChatMessage


class BaseBackbone(ABC):

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def localize_bugs(self, dp: dict, **kwargs) -> Dict[str, Any]:
        """Compose prompt from data point and call LLM."""
        pass

    @abstractmethod
    def call_llm(self, messages: List[ChatMessage]) -> Dict[str, Any]:
        """
        Make an LLM API call with pre-composed messages saved in cache

        Returns the same dict format as localize_bugs:
            {"messages", "raw_completion", "json_completion"}
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """The model identifier used for prompt composition / tokenisation."""
        pass

    @property
    @abstractmethod
    def context_composer(self):
        """The context composer instance attached to this backbone."""
        pass
