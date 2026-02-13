from __future__ import annotations

from typing import Any, Dict, List

from extensions.architect.architect_v1 import ArchitectAudit, validate_architect_output_v1_fail_closed
from extensions.conversation.requirement_model_v1 import validate_model_fail_closed
from extensions.spec_writer.spec_writer_v1 import source_hash_requirement_model


def _md_list(items: List[str], *, empty: str = "_TBD_") -> str:
    if not items:
        return empty
    return "\n".join([f"- {x}" for x in items])


def render_spec_markdown_from_architect(*, architect_out: Dict[str, Any]) -> str:
    validate_architect_output_v1_fail_closed(architect_out)

    title = str(architect_out["title"])
    overview = str(architect_out["overview"])

    md = ""
    md += "# Spec v1 (LLM Draft)\n\n"
    md += "## 1) Overview\n\n"
    md += f"**Title:** {title}\n\n"
    md += f"{overview}\n\n"

    md += "## 2) Users & Context\n\n"
    md += _md_list(list(architect_out["users"])) + "\n\n"

    md += "## 3) Scope\n\n"
    md += "### In-scope\n\n"
    md += _md_list(list(architect_out["scope_in"])) + "\n\n"
    md += "### Out-of-scope\n\n"
    md += _md_list(list(architect_out["scope_out"])) + "\n\n"

    md += "## 4) Success Criteria\n\n"
    md += _md_list(list(architect_out["success_criteria"])) + "\n\n"

    md += "## 5) Constraints\n\n"
    md += _md_list(list(architect_out["constraints"])) + "\n\n"

    md += "## 6) Assumptions\n\n"
    md += _md_list(list(architect_out["assumptions"])) + "\n\n"

    md += "## 7) Acceptance Criteria\n\n"
    md += _md_list(list(architect_out["acceptance_criteria"]), empty="_TBD_") + "\n\n"

    md += "## 8) Definition of Done\n\n"
    md += _md_list(list(architect_out["definition_of_done"]), empty="_TBD_") + "\n\n"

    md += "## 9) Open Questions\n\n"
    md += _md_list(list(architect_out["open_questions"]), empty="_None_") + "\n"

    return md


def build_spec_document_v1_llm(
    *,
    requirement_model_v1: Dict[str, Any],
    conversation_id: str,
    architect_out: Dict[str, Any],
    audit: ArchitectAudit,
) -> Dict[str, Any]:
    validate_model_fail_closed(requirement_model_v1)
    validate_architect_output_v1_fail_closed(architect_out)

    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise ValueError("conversation_id must be non-empty str")

    title = str(architect_out["title"]).strip() or "Spec v1 (LLM Draft)"
    content = render_spec_markdown_from_architect(architect_out=architect_out)
    src_hash = source_hash_requirement_model(requirement_model_v1)

    return {
        "schema_version": "spec_document_v1",
        "format": "markdown",
        "title": title,
        "content": content,
        "generated_from": {
            "conversation_id": conversation_id,
            "requirement_model_version": "requirement_model_v1",
            "source_hash": src_hash,
            "llm_mode": audit.llm_mode,
            "llm_provider": audit.llm_provider,
            "llm_cache_key": audit.llm_cache_key,
            "architect_policy_version": audit.architect_policy_version,
        },
    }
