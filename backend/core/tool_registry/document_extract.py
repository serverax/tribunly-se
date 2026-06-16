"""Document extract tool  -  interface to upload/OCR fact extraction pipeline."""

from __future__ import annotations

from backend.core.tool_registry.base import AgentTool, ToolResult


class DocumentExtractTool(AgentTool):
    name = "document_extract"
    description = "Extract structured facts from an uploaded document (upload_id required)."
    experimental = True

    def invoke(self, **kwargs) -> ToolResult:
        upload_id = kwargs.get("upload_id")
        case_id = kwargs.get("case_id")
        if not upload_id:
            return ToolResult(
                tool_name=self.name,
                status="error",
                message="upload_id is required",
                experimental=True,
            )
        try:
            from ingestion.db import get_connection
            import psycopg2.extras

            conn = get_connection()
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT field_name, normalised_value, confidence, status
                        FROM document_facts
                        WHERE upload_id = %s::uuid
                        ORDER BY created_at DESC
                        LIMIT 50
                        """,
                        (str(upload_id),),
                    )
                    rows = [dict(r) for r in cur.fetchall()]
            finally:
                conn.close()
            if not rows:
                return ToolResult(
                    tool_name=self.name,
                    status="ok",
                    experimental=True,
                    message="No extracted facts found for this upload.",
                    data={"upload_id": str(upload_id), "facts": []},
                )
            return ToolResult(
                tool_name=self.name,
                status="ok",
                experimental=True,
                data={"upload_id": str(upload_id), "case_id": case_id, "facts": rows},
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status="error",
                experimental=True,
                message=f"document_facts query failed: {exc}",
            )
