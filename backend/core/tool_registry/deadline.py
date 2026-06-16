"""Deadline calculator tool — delegates to deterministic rules engine."""

from __future__ import annotations

from backend.core.tool_registry.base import AgentTool, ToolResult


class DeadlineCalculateTool(AgentTool):
    name = "deadline_calculate"
    description = "Compute ET limitation date from EDT and ACAS EC dates via rules table."

    def invoke(self, **kwargs) -> ToolResult:
        event_date = kwargs.get("event_date") or kwargs.get("edt")
        event_type = kwargs.get("event_type") or kwargs.get("claim_type") or "dismissal"
        jurisdiction = kwargs.get("jurisdiction") or "EW"
        if not event_date:
            return ToolResult(
                tool_name=self.name,
                status="error",
                message="event_date (or edt) is required",
            )
        try:
            from backend.core import tools as preview_tools

            data = preview_tools.calculate_deadline(
                str(event_date), str(event_type), str(jurisdiction)
            )
            return ToolResult(tool_name=self.name, status="ok", data=data)
        except preview_tools.ToolDataUnavailable as exc:
            return ToolResult(tool_name=self.name, status="unavailable", message=str(exc))
        except (ValueError, TypeError) as exc:
            return ToolResult(tool_name=self.name, status="error", message=str(exc))
