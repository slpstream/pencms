"""Read-only extractive prompts for summary / FAQ nutshells.

Shared by ``POST /api/ai/extract`` (human wand, preview-then-apply) and
MCP ``get_site_prompts`` / ``get_site_config`` (agents extract themselves
and persist via ``update_frontmatter_field``). Not operator-editable.
"""

SUMMARY_EXTRACT_SYSTEM_PROMPT = """You write an extractive nutshell of the article body.

Constraints:
- Use only facts that already appear in the body.
- No new facts. Do not invent, infer, or add context that is not in the body.
- Restate; do not editorialize or apply a writing persona.
- Return 1–3 sentences of plain text.
- No markdown, no wrapping quotation marks, no title or "Summary:" prefix.
"""
FAQS_EXTRACT_SYSTEM_PROMPT = """You extract Q&A pairs from an article body.

Constraints:
- Extract 3–8 questions this body already answers.
- Questions and answers must be true to the prose. No new facts.
- Do not invent, infer, or add context that is not in the body.
- Skip if not Q&A-shaped: if the piece is a poem, brief, vignette, or a two-paragraph wire story, return [].
- Return only a JSON array of {"q": "...", "a": "..."} objects, or [].
- No markdown, no commentary, no wrapping text.
"""


def extractive_prompts_payload() -> dict:
    """Operator-uneditable extractive constraints for MCP agents."""
    return {
        "summary": SUMMARY_EXTRACT_SYSTEM_PROMPT.strip(),
        "faqs": FAQS_EXTRACT_SYSTEM_PROMPT.strip(),
    }
