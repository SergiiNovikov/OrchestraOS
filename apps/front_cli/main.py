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
from extensions.rolepacks.v1_req.elicitor import elicitation_step

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
    try:
        prof = load_profile(profile_arg)
    except Exception as e:
        sys.stderr.write(f"[ERROR] profile load failed: {e}\n")
        return 2

    try:
        out, err, m, trace_id, work_dir = run_once(text, prof.data)
        print_run_output(out, err, m)
        save_run_artifacts(work_dir=work_dir, trace_id=trace_id, out=out, err=err, manifest_dict=m)
        return 0 if err is None else 1
    except Exception as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return 1


def run_repl_mode(*, profile_arg: Optional[str]) -> int:
    try:
        prof = load_profile(profile_arg)
    except Exception as e:
        sys.stderr.write(f"[ERROR] profile load failed: {e}\n")
        return 2

    return run_repl(build_and_run=lambda t: run_once(t, prof.data))


def _read_spec_mode(profile: Dict[str, Any]) -> str:
    """
    ENV > profile > default.
    Allowed: rules | llm
    """
    env_mode = os.environ.get("ORCHESTRA_SPEC_MODE")
    if isinstance(env_mode, str) and env_mode.strip():
        mode = env_mode.strip().lower()
    else:
        v = profile.get("spec_mode", "rules")
        mode = str(v).strip().lower()

    if mode not in {"rules", "llm"}:
        raise ValueError(f"Invalid spec_mode={mode!r}. Allowed: rules, llm")
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
    """
    Fail-closed:
      - generate spec_doc
      - set status=done
      - atomic save (single transaction)
    If save fails: no persisted status change.
    """
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

    # Update in-memory state to match persisted state (post-commit)
    state.clear()
    state.update(state2)


def run_conversation_mode(*, profile_arg: Optional[str], new_conversation: bool, conversation_id: Optional[str]) -> int:
    """
    Milestone 18:
      - Cognitive Layer runs FIRST to stabilize problem_model_v1
      - Only after stabilized -> fill RequirementModel v1 (minimal extractor) -> SpecWriter (M16/M17)
      - Fail-closed for LLM replay miss / missing provider: do not persist any state changes
      - Atomic save: status=done only after spec_document_v1 is written in the same atomic commit
    """
    if new_conversation and conversation_id is not None:
        raise ValueError("new_conversation and conversation_id are mutually exclusive")

    try:
        prof = load_profile(profile_arg)
    except Exception as e:
        sys.stderr.write(f"[ERROR] profile load failed: {e}\n")
        return 2

    work_dir = Path(str(prof.data["work_dir"]))
    spec_mode = _read_spec_mode(prof.data)

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

        # Fast-path: if already ready/done -> print outline + (re)generate spec per spec_mode.
        model0 = state["requirement_model_v1"]
        status0 = model0.get("status")
        if status0 in {"ready_for_spec", "done"}:
            outline = draft_spec_outline(model0)
            try:
                _finalize_spec_and_persist(
                    state=state,
                    conversation_id=str(conversation_id),
                    work_dir=work_dir,
                    spec_mode=spec_mode,
                )
            except ArchitectError as e:
                sys.stderr.write(f"[ERROR] {e}\n")
                return 1

            spec_doc = state["spec_document_v1"]
            _print_ready_with_spec(outline=outline, spec_doc=spec_doc)
            return 0

        # Ensure ProblemModel v1 exists
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

        # Main loop:
        # - ask a question (based on hypotheses/uncertainty)
        # - user answers
        # - run cognitive step (rules/llm/auto), update problem model
        # - if stabilized: extract requirements -> spec -> done (atomic)
        while True:
            pm = state.get("problem_model_v1")
            if not isinstance(pm, dict):
                raise ValueError("problem_model_v1 missing or invalid")
            validate_problem_model_fail_closed(pm)

            # If stabilized -> proceed
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
                        spec_mode=spec_mode,
                    )
                except ArchitectError as e:
                    sys.stderr.write(f"[ERROR] {e}\n")
                    return 1

                spec_doc = state["spec_document_v1"]
                _print_ready_with_spec(outline=outline2, spec_doc=spec_doc)
                return 0

            # Ensure we have a question to ask
            last_q = pm.get("last_question")
            if not isinstance(last_q, dict) or not isinstance(last_q.get("text"), str) or not last_q["text"].strip():
                # Default first question (before any user statement)
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

            # Build in-memory updated pm with user statement (NOT persisted yet; fail-closed protection).
            pm_user = pm_append_statement(pm, "user", answer)
            pm_user = {**pm_user, "turn_index": int(pm_user.get("turn_index", 0)) + 1, "last_question": None}

            # Select cognitive mode
            cog = read_cognitive_settings_from_env()
            try:
                if cog.mode == "rules":
                    step = run_rules_step(pm_user)
                elif cog.mode == "llm":
                    step = run_llm_step(pm_user, cog.llm)
                else:
                    raise ValueError(f"Invalid cognitive.mode: {cog.mode!r}")
            except CognitiveLLMError as e:
                # Fail-closed: do not persist any changes (including user's last answer).
                sys.stderr.write(f"[ERROR] {e}\n")
                return 1

            pm_next = apply_cognitive_step(pm_user, step)

            # Policy-level stabilization check
            if pm_next.get("status") == "stabilized" and not stabilization_criteria(pm_next):
                pm_next = {**pm_next, "status": "exploring"}

            # If next_question exists, append as assistant statement for context.
            nq = step.get("next_question")
            if isinstance(nq, dict) and isinstance(nq.get("text"), str) and nq["text"].strip():
                pm_next = pm_append_statement(pm_next, "assistant", str(nq["text"]))

            # Update state (now safe to persist)
            state["problem_model_v1"] = pm_next
            state["step"] = int(state.get("step", 0)) + 1
            state["pending_question_id"] = None
            save_state_atomic(state, str(conversation_id), work_dir)

            # Loop will either finalize (stabilized) or ask the next question.
            continue

    except Exception as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return 1
