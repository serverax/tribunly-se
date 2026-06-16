"""Base types for orchestrator tool registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolResult:
    tool_name: str
    status: str  # ok | unavailable | error | experimental
    data: dict = field(default_factory=dict)
    message: Optional[str] = None
    experimental: bool = False

    def to_dict(self) -> dict:
        return {
            "tool": self.tool_name,
            "status": self.status,
            "data": self.data,
            "message": self.message,
            "experimental": self.experimental,
        }


class AgentTool(ABC):
    """Callable tool exposed to the orchestrator / agents."""

    name: str = "base_tool"
    description: str = ""
    experimental: bool = False

    @abstractmethod
    def invoke(self, **kwargs: Any) -> ToolResult:
        """Run the tool with keyword arguments."""
