from __future__ import annotations

from swebench.agent.agent_base import AgentBase
from swebench.agent.agents.dummy_agent import DummyAgent

AGENT_REGISTRY: dict[str, type[AgentBase]] = {
    "dummy": DummyAgent,
}

# Lazy-register claude agent to avoid hard dependency on anthropic
_LAZY_AGENTS = {
    "claude": "swebench.agent.agents.claude_agent.ClaudeAgent",
    "claude-code": "swebench.agent.agents.claude_code_agent.ClaudeCodeAgent",
    "gemini": "swebench.agent.agents.gemini_agent.GeminiAgent",
}


def create_agent(name: str, model_name_or_path: str, **kwargs) -> AgentBase:
    if name in AGENT_REGISTRY:
        return AGENT_REGISTRY[name](model_name_or_path=model_name_or_path, **kwargs)

    if name in _LAZY_AGENTS:
        import importlib

        module_path, class_name = _LAZY_AGENTS[name].rsplit(".", 1)
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        AGENT_REGISTRY[name] = cls
        return cls(model_name_or_path=model_name_or_path, **kwargs)

    available = sorted(set(AGENT_REGISTRY) | set(_LAZY_AGENTS))
    raise ValueError(
        f"Unknown agent: {name!r}. Available agents: {available}"
    )
