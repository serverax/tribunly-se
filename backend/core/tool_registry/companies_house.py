"""Companies House lookup — experimental stub until API key provisioned."""

from __future__ import annotations

import os

from backend.core.tool_registry.base import AgentTool, ToolResult


class CompaniesHouseLookupTool(AgentTool):
    name = "companies_house_lookup"
    description = "Look up UK company registration details (requires COMPANIES_HOUSE_API_KEY)."
    experimental = True

    def invoke(self, **kwargs) -> ToolResult:
        company_number = (kwargs.get("company_number") or "").strip()
        if not company_number:
            return ToolResult(
                tool_name=self.name,
                status="error",
                message="company_number is required",
                experimental=True,
            )
        api_key = os.getenv("COMPANIES_HOUSE_API_KEY", "").strip()
        if not api_key:
            return ToolResult(
                tool_name=self.name,
                status="unavailable",
                experimental=True,
                message=(
                    "Companies House API key not configured. "
                    "Set COMPANIES_HOUSE_API_KEY to enable live lookups."
                ),
                data={"company_number": company_number},
            )
        # Phase 2: HTTP call to Companies House API
        return ToolResult(
            tool_name=self.name,
            status="experimental",
            experimental=True,
            message="Live Companies House integration not yet implemented.",
            data={"company_number": company_number},
        )
