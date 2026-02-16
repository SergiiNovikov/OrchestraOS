from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from runtime.runner import run_pipeline_v0

from apps.front_cli.adapters import (
    EnvelopeOnlyValidatorV0,
    build_request_envelope_from_text,
    environment_from_profile,
    ensure_specs_dir,
    minimal_specs_from_profile,
    roles_from_profile,
    validate_envelope_fail_closed,
)
from apps.front_cli.config import load_profile
from apps.front_cli.io import print_run_output, run_repl, save_run_artifacts

from extensions.conversation.state_store import create_new_state, load_state, save_state_atomic
from extensions.conversation.clarify_policy_v1 import draft_spec_outline

# M18 Cognitive Front Manager (Problem Discovery Engine)
from extensions.cognitive.problem_model_v1 import (
    append_statement as pm_append_statement,
    apply_cognitive_step,
    default_problem_model,
    validate_problem_model_fail_closed,
)
from extensions.cognitive.cognitive_policy_v1 import stabilization_criteria
from extensions.cognitive.cognitive_rules_v1 import run_rules_step
from extensions.cognitive.cognitive_llm_v1 import CognitiveLLMError, run_llm_step
from extensions.cognitive.requirement_extractor_v1 import extract_requirement_model_v1_from_problem
from extensions.cognitive.settings import read_cognitive_settings_from_env

# M16 rules-only spec
from extensions.spec_writer.spec_writer_v1 import build_spec_document_v1

# M17 llm spec
from extensions.architect.architect_v1 import ArchitectError, run_architect_v1
from extensions.spec_writer.spec_writer_llm_v1 import build_spec_document_v1_llm

# -------------------------
# M19 additions (modules)
# -------------------------
from extensions.cognitive.cognitive_expander_v1 import CognitiveExpanderConfig, run_cognitive_expander_v1
from extensions.extraction.requirement_extractor_v1 import RequirementExtractorConfig, run_requirement_extractor_v1
from extensions.extraction.quality_gate_v1 import StrategicQualityGateConfig, run_quality_gate_v1
from extensions.approval.approval_gate_v1 import ApprovalGateConfig, is_approved_v1


def _ensure_utf8_stdio() -> None:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="strict")  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="strict")  # type: ignore[attr-defined]
    except Exception:
        pass


def run_once(text: str, profile: Dict[str, Any]) -> Tuple[Any, Any, Dict[str, Any], str, Path]:
    env = build_request_envelope_from_text(text=text, profile=profile)
    validate_envelope_fail_closed(env)

    specs_dir = Path(str(profile["specs_dir"]))
    ensure_specs_dir(specs_dir)

    environment = environment_from_profile(profile)
    roles = roles_from_profile(profile)
    validator = EnvelopeOnlyValidatorV0()
    specs = minimal_specs_from_profile(profile)

    out, err, manifest = run_pipeline_v0(
        primary_input=env,
        specs_dir=specs_dir,
        environment=environment,
        roles=roles,
        validator=validator,
        specs=specs,
    )

    manifest_dict = manifest.to_dict()
    trace_id = env["header"]["trace_id"]
    work_dir = Path(str(profile["work_dir"]))
    return out, err, manifest_dict, trace_id, work_dir


def run_text_mode(*, text: str, profile_arg: Optional[str]) -> int:
    _ensure_utf8_stdio()

    try:
        prof = load_profile(profile_arg)
    except Exception as e:
        sys.stderr.write(f"[ERROR] profile load failed: {e}\n")
        return 2

    try:
        mode = _read_spec_mode(prof.data)
    except Exception as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return 2

    if mode == "conversation":
        try:
            out_text = _run_m19_text_turn(text=text, profile=prof.data)
            sys.stdout.write(out_text + "\n")
            sys.stdout.flush()
            return 0
        except Exception as e:
            sys.stderr.write(f"[ERROR] {e}\n")
            return 1

    try:
        out, err, m, trace_id, work_dir = run_once(text, prof.data)
        print_run_output(out, err, m)
        save_run_artifacts(work_dir=work_dir, trace_id=trace_id, out=out, err=err, manifest_dict=m)
        return 0 if err is None else 1
    except Exception as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return 1


def run_repl_mode(*, profile_arg: Optional[str]) -> int:
    _ensure_utf8_stdio()
    try:
        prof = load_profile(profile_arg)
    except Exception as e:
        sys.stderr.write(f"[ERROR] profile load failed: {e}\n")
        return 2
    return run_repl(build_and_run=lambda t: run_once(t, prof.data))


def _read_spec_mode(profile: Dict[str, Any]) -> str:
    env_mode = os.environ.get("ORCHESTRA_SPEC_MODE")
    if isinstance(env_mode, str) and env_mode.strip():
        mode = env_mode.strip().lower()
    else:
        v = profile.get("spec_mode", "rules")
        mode = str(v).strip().lower()

    if mode not in {"rules", "llm", "conversation"}:
        raise ValueError(f"Invalid spec_mode={mode!r}. Allowed: rules, llm, conversation")
    return mode


def _print_ready_with_spec(*, outline: str, spec_doc: Dict[str, Any]) -> None:
    sys.stdout.write("status: ready_for_spec\n")
    sys.stdout.write(outline + "\n")
    sys.stdout.write("\n=== SPEC_v1 ===\n\n")
    sys.stdout.write(str(spec_doc["content"]) + "\n")
    sys.stdout.flush()


def _finalize_spec_and_persist(
    *,
    state: Dict[str, Any],
    conversation_id: str,
    work_dir: Path,
    spec_mode: str,
) -> None:
    model = state["requirement_model_v1"]

    if spec_mode == "rules":
        spec_doc = build_spec_document_v1(model=model, conversation_id=conversation_id)
    elif spec_mode == "llm":
        architect_out, audit = run_architect_v1(model=model)
        spec_doc = build_spec_document_v1_llm(
            requirement_model_v1=model,
            conversation_id=conversation_id,
            architect_out=architect_out,
            audit=audit,
        )
    else:
        raise ValueError(f"Unknown spec_mode: {spec_mode!r}")

    model_done = {**model, "status": "done"}
    state2 = {
        **state,
        "requirement_model_v1": model_done,
        "spec_document_v1": spec_doc,
        "pending_question_id": None,
    }
    save_state_atomic(state2, conversation_id, work_dir)
    state.clear()
    state.update(state2)


# -------------------------
# M19: active conversation pointer in work_dir
# -------------------------

def _active_conversation_id_path(work_dir: Path) -> Path:
    return work_dir / "front_cli_active_conversation_id.txt"


def _write_active_conversation_id_atomic(work_dir: Path, cid: str) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    p = _active_conversation_id_path(work_dir)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(cid, encoding="utf-8")
    os.replace(str(tmp), str(p))


def _read_active_conversation_id(work_dir: Path) -> str:
    p = _active_conversation_id_path(work_dir)
    if not p.exists():
        raise RuntimeError("ACTIVE CONVERSATION ID NOT SET (run --new-conversation first)")
    cid = p.read_text(encoding="utf-8").strip()
    if not cid:
        raise RuntimeError("ACTIVE CONVERSATION ID EMPTY")
    return cid


# -------------------------
# M19 helpers
# -------------------------

def _m19_get_turns(state: Dict[str, Any]) -> list[dict]:
    turns = state.get("m19_turns")
    if isinstance(turns, list):
        out: list[dict] = []
        for t in turns:
            if not isinstance(t, dict):
                continue
            role = t.get("role")
            text = t.get("text")
            if role in ("user", "assistant") and isinstance(text, str):
                out.append({"role": role, "text": text})
        return out
    return []


def _m19_set_turns(state: Dict[str, Any], turns: list[dict]) -> None:
    state["m19_turns"] = [{"role": t["role"], "text": t["text"]} for t in turns]


def _m19_slice_turns(turns: list[dict], n: int = 8) -> list[dict]:
    return turns[-n:]


def _m19_generate_draft_spec(m19_req: Dict[str, Any]) -> str:
    goals = m19_req.get("goals", []) or []
    success = m19_req.get("success_criteria", []) or []
    constraints = m19_req.get("constraints", []) or []
    oq = m19_req.get("open_questions", []) or []

    lines: list[str] = []
    lines.append("# Draft Spec (M19)")
    lines.append("")
    lines.append("## Strategic Goal")
    if goals:
        for g in goals:
            lines.append(f"- {g}")
    else:
        lines.append("- (not specified)")
    lines.append("")
    lines.append("## Success Criteria")
    if success:
        for s in success:
            lines.append(f"- {s}")
    else:
        lines.append("- (not specified)")
    if constraints:
        lines.append("")
        lines.append("## Constraints")
        for c in constraints:
            lines.append(f"- {c}")
    if oq:
        lines.append("")
        lines.append("## Open Questions (must be resolved)")
        for q in oq:
            lines.append(f"- {q}")
    lines.append("")
    lines.append("## Approval")
    lines.append("Reply with: approved / утверждаю / согласовано")
    return "\n".join(lines)


def _run_m19_text_turn(*, text: str, profile: Dict[str, Any]) -> str:
    work_dir = Path(str(profile["work_dir"]))
    conversation_id = _read_active_conversation_id(work_dir)
    state = load_state(conversation_id, work_dir)

    # Keep PM valid, but M19 slice must not depend on PM internal schema.
    pm = state.get("problem_model_v1")
    if pm is None:
        pm = default_problem_model()
        validate_problem_model_fail_closed(pm)
    elif not isinstance(pm, dict):
        raise ValueError("problem_model_v1 must be an object")
    else:
        validate_problem_model_fail_closed(pm)

    turns = _m19_get_turns(state)

    # If we are waiting for approval:
    if state.get("m19_status") == "ready_for_spec":
        approval_cfg = ApprovalGateConfig(approval_required=True)
        if is_approved_v1(text, approval_cfg):
            turns2 = turns + [{"role": "user", "text": text}]
            state2 = {**state, "m19_status": "approved_for_spec", "approved_for_spec": True}
            _m19_set_turns(state2, turns2)
            save_state_atomic(state2, conversation_id, work_dir)
            return "APPROVED. State marked as approved_for_spec."

        turns2 = turns + [{"role": "user", "text": text}]
        state2 = dict(state)
        _m19_set_turns(state2, turns2)
        save_state_atomic(state2, conversation_id, work_dir)

        draft = state.get("m19_draft_spec_v1")
        if not isinstance(draft, str) or not draft.strip():
            draft = "(draft spec missing)"
        return draft + "\n\n(Approval required: reply with approved / утверждаю / согласовано)"

    # Normal turn
    turns2 = turns + [{"role": "user", "text": text.strip()}]
    slice_turns = _m19_slice_turns(turns2, n=8)

    # Also still append into PM for continuity (but not used for slicing)
    pm_user = pm_append_statement(pm, "user", text.strip())
    pm_user = {**pm_user, "turn_index": int(pm_user.get("turn_index", 0)) + 1}

    c_cfg = CognitiveExpanderConfig(
        cognitive_mode="rules",
        llm_mode="off",
        llm_provider="stub",
        cache_dir=str(profile.get("llm_cache_dir", ".llm_cache")),
    )
    c_rec = run_cognitive_expander_v1(problem_model_v1=pm_user, conversation_turns=slice_turns, cfg=c_cfg)
    c_parsed = c_rec["parsed_output"]

    r_cfg = RequirementExtractorConfig(
        extraction_mode="rules",
        llm_mode="off",
        llm_provider="stub",
        cache_dir=str(profile.get("llm_cache_dir", ".llm_cache")),
    )
    r_rec = run_requirement_extractor_v1(
        problem_model_v1=pm_user,
        cognitive_hypotheses_v1=c_parsed,
        conversation_turns=slice_turns,
        cfg=r_cfg,
    )
    m19_req = r_rec["parsed_output"]

    m19_q = run_quality_gate_v1(requirement_model_v1=m19_req, cfg=StrategicQualityGateConfig())

    if m19_q["needs_refinement"]:
        nq = str(m19_q.get("next_question") or "").strip()
        if nq:
            turns3 = turns2 + [{"role": "assistant", "text": nq}]
        else:
            turns3 = turns2

        # Also add assistant question into PM for continuity
        pm_next = pm_user
        if nq:
            pm_next = pm_append_statement(pm_next, "assistant", nq)

        state2 = {
            **state,
            "problem_model_v1": pm_next,
            "m19_status": "needs_refinement",
            "m19_cognitive_hypotheses_v1": c_parsed,
            "m19_requirement_model_v1": m19_req,
            "m19_quality_gate_v1": m19_q,
            "m19_draft_spec_v1": None,
            "approved_for_spec": False,
        }
        _m19_set_turns(state2, turns3)
        save_state_atomic(state2, conversation_id, work_dir)
        return nq or "Уточните, пожалуйста: какой проверяемый критерий успеха вы ожидаете?"

    draft = _m19_generate_draft_spec(m19_req)
    state2 = {
        **state,
        "problem_model_v1": pm_user,
        "m19_status": "ready_for_spec",
        "m19_cognitive_hypotheses_v1": c_parsed,
        "m19_requirement_model_v1": m19_req,
        "m19_quality_gate_v1": m19_q,
        "m19_draft_spec_v1": draft,
        "approved_for_spec": False,
    }
    _m19_set_turns(state2, turns2)
    save_state_atomic(state2, conversation_id, work_dir)
    return draft + "\n\n(Approval required: reply with approved / утверждаю / согласовано)"


def run_conversation_mode(*, profile_arg: Optional[str], new_conversation: bool, conversation_id: Optional[str]) -> int:
    _ensure_utf8_stdio()

    if new_conversation and conversation_id is not None:
        raise ValueError("new_conversation and conversation_id are mutually exclusive")

    try:
        prof = load_profile(profile_arg)
    except Exception as e:
        sys.stderr.write(f"[ERROR] profile load failed: {e}\n")
        return 2

    work_dir = Path(str(prof.data["work_dir"]))

    try:
        spec_mode = _read_spec_mode(prof.data)
    except Exception as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return 2

    if spec_mode == "conversation":
        try:
            if new_conversation:
                cid, state = create_new_state()
                save_state_atomic(state, cid, work_dir)
                _write_active_conversation_id_atomic(work_dir, str(cid))
                sys.stdout.write(f"conversation_id: {cid}\n")
                sys.stdout.flush()
                return 0

            if conversation_id is None:
                raise ValueError("conversation_id is required")

            state = load_state(str(conversation_id), work_dir)
            save_state_atomic(state, str(conversation_id), work_dir)
            _write_active_conversation_id_atomic(work_dir, str(conversation_id))
            sys.stdout.write(f"conversation_id: {conversation_id}\n")
            sys.stdout.flush()
            return 0

        except Exception as e:
            sys.stderr.write(f"[ERROR] {e}\n")
            return 1

    # -------------------------
    # M18 original conversation mode (unchanged)
    # -------------------------
    spec_mode_legacy = spec_mode
    try:
        if new_conversation:
            cid, state = create_new_state()
            save_state_atomic(state, cid, work_dir)
            sys.stdout.write(f"conversation_id: {cid}\n")
            conversation_id = cid
        else:
            if conversation_id is None:
                raise ValueError("conversation_id is required")
            state = load_state(conversation_id, work_dir)

        sys.stdout.write("OrchestraOS Conversation Mode. Ctrl-D / EOF to quit.\n")
        sys.stdout.flush()

        model0 = state["requirement_model_v1"]
        status0 = model0.get("status")
        if status0 in {"ready_for_spec", "done"}:
            outline = draft_spec_outline(model0)
            try:
                _finalize_spec_and_persist(
                    state=state,
                    conversation_id=str(conversation_id),
                    work_dir=work_dir,
                    spec_mode=spec_mode_legacy,
                )
            except ArchitectError as e:
                sys.stderr.write(f"[ERROR] {e}\n")
                return 1

            spec_doc = state["spec_document_v1"]
            _print_ready_with_spec(outline=outline, spec_doc=spec_doc)
            return 0

        pm = state.get("problem_model_v1")
        if pm is None:
            pm = default_problem_model()
            validate_problem_model_fail_closed(pm)
            state["problem_model_v1"] = pm
            save_state_atomic(state, str(conversation_id), work_dir)
        elif not isinstance(pm, dict):
            raise ValueError("problem_model_v1 must be an object")
        else:
            validate_problem_model_fail_closed(pm)

        while True:
            pm = state.get("problem_model_v1")
            if not isinstance(pm, dict):
                raise ValueError("problem_model_v1 missing or invalid")
            validate_problem_model_fail_closed(pm)

            if pm.get("status") == "stabilized" or stabilization_criteria(pm):
                pm2 = {**pm, "status": "stabilized"}
                state["problem_model_v1"] = pm2

                req = extract_requirement_model_v1_from_problem(pm2, step_index=int(state.get("step", 0)))
                state["requirement_model_v1"] = req
                state["pending_question_id"] = None

                outline2 = draft_spec_outline(req)
                try:
                    _finalize_spec_and_persist(
                        state=state,
                        conversation_id=str(conversation_id),
                        work_dir=work_dir,
                        spec_mode=spec_mode_legacy,
                    )
                except ArchitectError as e:
                    sys.stderr.write(f"[ERROR] {e}\n")
                    return 1

                spec_doc = state["spec_document_v1"]
                _print_ready_with_spec(outline=outline2, spec_doc=spec_doc)
                return 0

            last_q = pm.get("last_question")
            if not isinstance(last_q, dict) or not isinstance(last_q.get("text"), str) or not last_q["text"].strip():
                last_q = {"id": "q1", "text": "Опиши задачу/проблему в 1–3 предложениях (цель, контекст, ограничения)."}
                pm = {**pm, "last_question": last_q}
                state["problem_model_v1"] = pm
                save_state_atomic(state, str(conversation_id), work_dir)

            qtext = str(last_q["text"])
            sys.stdout.write(qtext + "\n")
            sys.stdout.flush()

            try:
                answer = input("> ")
            except EOFError:
                sys.stdout.write("\n")
                return 0

            answer = answer.strip()
            if not answer:
                continue

            pm_user = pm_append_statement(pm, "user", answer)
            pm_user = {**pm_user, "turn_index": int(pm_user.get("turn_index", 0)) + 1, "last_question": None}

            cog = read_cognitive_settings_from_env()
            try:
                if cog.mode == "rules":
                    step = run_rules_step(pm_user)
                elif cog.mode == "llm":
                    step = run_llm_step(pm_user, cog.llm)
                else:
                    raise ValueError(f"Invalid cognitive.mode: {cog.mode!r}")
            except CognitiveLLMError as e:
                sys.stderr.write(f"[ERROR] {e}\n")
                return 1

            pm_next = apply_cognitive_step(pm_user, step)

            if pm_next.get("status") == "stabilized" and not stabilization_criteria(pm_next):
                pm_next = {**pm_next, "status": "exploring"}

            nq = step.get("next_question")
            if isinstance(nq, dict) and isinstance(nq.get("text"), str) and nq["text"].strip():
                pm_next = pm_append_statement(pm_next, "assistant", str(nq["text"]))

            state["problem_model_v1"] = pm_next
            state["step"] = int(state.get("step", 0)) + 1
            state["pending_question_id"] = None
            save_state_atomic(state, str(conversation_id), work_dir)

            continue

    except Exception as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return 1
