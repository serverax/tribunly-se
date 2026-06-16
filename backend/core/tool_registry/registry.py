"""Central tool registry for orchestrator tool-calling."""

from __future__ import annotations

import logging
from typing import Optional

from backend.core.tool_registry.base import AgentTool, ToolResult
from backend.core.tool_registry.deadline import DeadlineCalculateTool
from backend.core.tool_registry.companies_house import CompaniesHouseLookupTool
from backend.core.tool_registry.document_extract import DocumentExtractTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        for tool in (
            DeadlineCalculateTool(),
            CompaniesHouseLookupTool(),
            DocumentExtractTool(),
        ):
            self._tools[tool.name] = tool

    def register(self, tool: AgentTool, *, overwrite: bool = False) -> None:
        if tool.name in self._tools and not overwrite:
            raise ValueError(f"Tool {tool.name!r} already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[AgentTool]:
        return self._tools.get(name)

    def list_tools(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "experimental": t.experimental,
            }
            for t in self._tools.values()
        ]

    def invoke(self, name: str, **kwargs) -> ToolResult:
        tool = self.get(name)
        if tool is None:
            return ToolResult(tool_name=name, status="error", message=f"Unknown tool: {name}")
        return tool.invoke(**kwargs)


_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
