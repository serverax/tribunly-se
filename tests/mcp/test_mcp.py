"""
MCP Connector unit tests — lawapp tool registry and safety.

Tests the MCP interface layer:
  - deny-by-default for unlisted tools
  - prohibited tools blocked at registration
  - allowed tools are whitelisted
  - every tool call is logged
  - no tool may file claims, represent users, or send emails

The MCP connector is in deny-by-default mode. Runtime connector
integration is PARTIAL — interface and safety tests run here.
"""

import os
import pytest


# ── MCP allowed tool registry (deny-by-default) ──────────────────────────────

_PROHIBITED_TOOLS = {
    "file_et1",
    "contact_tribunal",
    "send_email_on_behalf",
    "contact_employer",
    "represent_user_at_hearing",
    "sign_document_for_user",
    "submit_claim_to_employment_tribunal",
}

_ALLOWED_TOOLS = {
    "retrieve_legislation_section",
    "retrieve_case_law",
    "retrieve_acas_guidance",
    "calculate_deadline",
    "generate_document",
    "check_source_freshness",
}


class TestMCPToolRegistry:
    def test_prohibited_tools_not_in_allowed(self):
        overlap = _PROHIBITED_TOOLS & _ALLOWED_TOOLS
        assert overlap == set(), f"Prohibited tools in allowed: {overlap}"

    def test_all_allowed_tools_are_read_or_compute(self):
        for tool in _ALLOWED_TOOLS:
            # Allowed tools should be retrieval, computation, or generation
            assert any(prefix in tool for prefix in
                       ["retrieve", "calculate", "check", "generate"]), \
                f"Unexpected allowed tool: {tool}"

    def test_et1_filing_is_prohibited(self):
        assert "file_et1" in _PROHIBITED_TOOLS

    def test_email_on_behalf_is_prohibited(self):
        assert "send_email_on_behalf" in _PROHIBITED_TOOLS

    def test_represent_user_is_prohibited(self):
        assert "represent_user_at_hearing" in _PROHIBITED_TOOLS


class TestMCPAuditTable:
    """Verify mcp_tool_calls table exists and has correct schema."""

    def test_mcp_tool_calls_table_exists(self):
        import psycopg2
        conn = psycopg2.connect(host=os.environ.get('POSTGRES_HOST','localhost'), port=int(os.environ.get('POSTGRES_PORT','5435')), dbname=os.environ.get('POSTGRES_DB','lawapp'),
                                user=os.environ.get('POSTGRES_USER','lawapp'), password=os.environ.get('POSTGRES_PASSWORD','lawapp'))
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'mcp_tool_calls'
            ORDER BY ordinal_position;
        """)
        cols = [r[0] for r in cur.fetchall()]
        conn.close()
        assert "tool_name" in cols
        assert "action" in cols
        assert "allowed" in cols
        assert "consent" in cols

    def test_mcp_audit_has_trace_id(self):
        import psycopg2
        conn = psycopg2.connect(host=os.environ.get('POSTGRES_HOST','localhost'), port=int(os.environ.get('POSTGRES_PORT','5435')), dbname=os.environ.get('POSTGRES_DB','lawapp'),
                                user=os.environ.get('POSTGRES_USER','lawapp'), password=os.environ.get('POSTGRES_PASSWORD','lawapp'))
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'mcp_tool_calls' AND column_name = 'trace_id';
        """)
        assert cur.fetchone() is not None
        conn.close()


class TestMCPRuntimeConnectors:
    """Test actual MCP connector implementations."""

    def test_call_tool_blocks_prohibited(self):
        from backend.core.mcp_connectors import call_tool
        result = call_tool("file_et1", "submit", {})
        assert result["status"] == "blocked"

    def test_call_tool_blocks_unknown(self):
        from backend.core.mcp_connectors import call_tool
        result = call_tool("some_unknown_tool", "do_thing", {})
        assert result["status"] == "blocked"

    def test_rules_lookup_returns_rules(self):
        from backend.core.mcp_connectors import call_tool
        result = call_tool("rules_lookup", "lookup", {
            "claim_type": "unfair_dismissal",
            "jurisdiction": "EW",
        })
        assert result["status"] == "ok"
        assert result["result"]["count"] > 0

    def test_rules_lookup_has_era1996_authority(self):
        from backend.core.mcp_connectors import call_tool
        result = call_tool("rules_lookup", "lookup", {
            "claim_type": "unfair_dismissal",
            "jurisdiction": "EW",
        })
        rules = result["result"]["rules"]
        refs = [r.get("authority_ref", "") for r in rules]
        assert any("ERA 1996" in r for r in refs)

    def test_legislation_lookup_returns_results(self):
        from backend.core.mcp_connectors import call_tool
        result = call_tool("legislation_lookup", "lookup", {
            "section_ref": "ERA 1996",
            "jurisdiction": "EW",
        })
        assert result["status"] == "ok"
        # May return empty if no legislation ingested — check structure
        assert "results" in result["result"]

    def test_mcp_audit_written_on_call(self):
        import psycopg2
        conn = psycopg2.connect(host=os.environ.get('POSTGRES_HOST','localhost'), port=int(os.environ.get('POSTGRES_PORT','5435')), dbname=os.environ.get('POSTGRES_DB','lawapp'),
                                user=os.environ.get('POSTGRES_USER','lawapp'), password=os.environ.get('POSTGRES_PASSWORD','lawapp'))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM mcp_tool_calls;")
        before = cur.fetchone()[0]

        from backend.core.mcp_connectors import call_tool
        call_tool("rules_lookup", "lookup", {"claim_type": "unfair_dismissal"},
                  trace_id="test-mcp-audit")

        cur.execute("SELECT COUNT(*) FROM mcp_tool_calls;")
        after = cur.fetchone()[0]
        conn.close()
        assert after > before, "MCP tool call not logged to DB"

    def test_list_allowed_tools(self):
        from backend.core.mcp_connectors import list_allowed_tools
        tools = list_allowed_tools()
        assert "rules_lookup" in tools
        assert "legislation_lookup" in tools
        assert "document_generate" in tools

    def test_list_prohibited_tools(self):
        from backend.core.mcp_connectors import list_prohibited_tools
        prohibited = list_prohibited_tools()
        assert "file_et1" in prohibited
        assert "represent_user_at_hearing" in prohibited


class TestMCPSafetyBoundary:
    def test_prohibited_tool_is_not_callable_via_brain(self):
        """Brain agents do not list prohibited tools in allowed_tools."""
        from backend.core.agents.registry import get_registry
        registry = get_registry()
        agents = registry.list_all()
        all_allowed = []
        for agent in agents:
            all_allowed.extend(agent.get("allowed_tools", []))
        for prohibited in _PROHIBITED_TOOLS:
            assert prohibited not in all_allowed, \
                f"Prohibited tool '{prohibited}' found in agent allowed_tools"

    def test_agents_have_prohibited_actions_list(self):
        from backend.core.agents.registry import get_registry
        registry = get_registry()
        for agent_cfg in registry.list_all():
            assert "prohibited_actions" in agent_cfg
            assert len(agent_cfg["prohibited_actions"]) > 0
