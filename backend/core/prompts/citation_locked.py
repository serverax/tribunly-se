"""
Citation-locked prompt builder — Phase 3.
Refactored from Iterlaw citationBoundPrompt.ts
"""
from typing import List, TypedDict, Optional

class CitationBoundPromptOutput(TypedDict):
    system_prompt: str
    user_prompt: str
    allowed_citation_ids: List[str]

SYSTEM_PROMPT = """
You are lawapp, a UK employment law information assistant.
Rules:
1. Use ONLY the legal sources I supply below. Do not invent statutes, regulations, cases, or guidance pages.
2. Cite by source_id in square brackets, e.g. [source_abc].
3. If the supplied sources do not support a complete answer, respond exactly with: insufficient_sources
4. Do not include secrets, database connection strings, API keys, or any unrelated personal data.
5. Do not present yourself as a qualified solicitor. Use phrasing like 'AI legal assistant' or 'source-grounded legal information'.
""".strip()

MAX_CHUNK_SNIPPET = 1200

def truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"

def build_citation_bound_prompt(
    question: str,
    retrieved_chunks: List[dict],
    jurisdiction: str = "UK",
    applicable_on: Optional[str] = None,
) -> CitationBoundPromptOutput:
    """
    Composes a system + user prompt that contains ONLY the supplied retrieved 
    chunks plus strict citation rules.
    """
    allowed_ids = []
    source_lines = []

    for idx, chunk in enumerate(retrieved_chunks):
        # We need a unique ID for the LLM to cite. 
        # lawapp authorities don't always have a 'id' field, so we use index or url hash.
        source_id = chunk.get("source_id") or f"src_{idx+1}"
        allowed_ids.append(source_id)
        
        cite_label = chunk.get("cite") or chunk.get("heading") or "Authority"
        url = chunk.get("url") or "no-url"
        text_body = truncate(chunk.get("text", ""), MAX_CHUNK_SNIPPET)
        
        source_lines.append(
            f"{idx + 1}. [{source_id}] {cite_label}\n"
            f"   URL: {url}\n"
            f"   Text: {text_body}"
        )

    source_list = "\n\n".join(source_lines)

    lines = [
        f"Jurisdiction: {jurisdiction}",
        f"Law as at: {applicable_on or 'current'}",
        "",
        f"Question: {question}",
        "",
        "Sources (cite by [source_id]):"
    ]
    
    if not source_lines:
        lines.append("(no sources supplied)")
    else:
        lines.append(source_list)
        
    lines.append("")
    lines.append("If the supplied sources cannot answer the question completely, respond: insufficient_sources")

    return {
        "system_prompt": SYSTEM_PROMPT,
        "user_prompt": "\n".join(lines),
        "allowed_citation_ids": allowed_ids,
    }
