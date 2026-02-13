from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Tuple

from extensions.conversation.requirement_model_v1 import default_model, validate_model_fail_closed

# Milestone 18: optional ProblemModel v1 in conversation state
try:
    from extensions.cognitive.problem_model_v1 import (
        default_problem_model,
        validate_problem_model_fail_closed,
    )
except Exception:  # pragma: no cover
    default_problem_model = None  # type: ignore[assignment]

    def validate_problem_model_fail_closed(_: Dict[str, Any]) -> None:  # type: ignore[no-redef]
        return


def _conversations_dir(work_dir: Path) -> Path:
    return work_dir / "conversations"


def _state_path(conversation_id: str, work_dir: Path) -> Path:
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise ValueError("Invalid conversation_id")
    if "/" in conversation_id or "\\" in conversation_id or conversation_id.strip() != conversation_id:
        raise ValueError("Invalid conversation_id")
    return _conversations_dir(work_dir) / f"{conversation_id}.json"


def _dumps_deterministic(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)


def create_new_state() -> Tuple[str, Dict[str, Any]]:
    conversation_id = uuid.uuid4().hex
    model = default_model()
    validate_model_fail_closed(model)

    state: Dict[str, Any] = {
        "schema_version": "conversation_state_v1",
        "conversation_id": conversation_id,
        "step": 0,
        "pending_question_id": None,
        "requirement_model_v1": model,
    }

    # Optional Milestone 18+: initialize cognitive problem model if extension is present.
    if default_problem_model is not None:
        pm = default_problem_model()
        validate_problem_model_fail_closed(pm)
        state["problem_model_v1"] = pm

    return conversation_id, state


def load_state(conversation_id: str, work_dir: Path) -> Dict[str, Any]:
    path = _state_path(conversation_id, work_dir)
    raw = path.read_bytes()

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("utf-8")

    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Conversation state must be a JSON object")
    if data.get("schema_version") != "conversation_state_v1":
        raise ValueError("Unsupported conversation state schema_version")
    if data.get("conversation_id") != conversation_id:
        raise ValueError("conversation_id mismatch")
    if not isinstance(data.get("step"), int) or int(data["step"]) < 0:
        raise ValueError("Invalid step")

    pq = data.get("pending_question_id")
    if pq is not None and not isinstance(pq, str):
        raise ValueError("pending_question_id must be str|null")

    model = data.get("requirement_model_v1")
    if not isinstance(model, dict):
        raise ValueError("requirement_model_v1 must be an object")
    validate_model_fail_closed(model)

    # Optional Milestone 18+: validate problem_model_v1 if present (fail-closed).
    pm = data.get("problem_model_v1")
    if pm is not None:
        if not isinstance(pm, dict):
            raise ValueError("problem_model_v1 must be an object")
        validate_problem_model_fail_closed(pm)

    return data


def save_state_atomic(state: Dict[str, Any], conversation_id: str, work_dir: Path) -> None:
    if not isinstance(state, dict):
        raise ValueError("state must be dict")
    if state.get("schema_version") != "conversation_state_v1":
        raise ValueError("Unsupported conversation state schema_version")
    if state.get("conversation_id") != conversation_id:
        raise ValueError("conversation_id mismatch")

    model = state.get("requirement_model_v1")
    if not isinstance(model, dict):
        raise ValueError("requirement_model_v1 must be an object")
    validate_model_fail_closed(model)

    pm = state.get("problem_model_v1")
    if pm is not None:
        if not isinstance(pm, dict):
            raise ValueError("problem_model_v1 must be an object")
        validate_problem_model_fail_closed(pm)

    conv_dir = _conversations_dir(work_dir)
    conv_dir.mkdir(parents=True, exist_ok=True)

    final_path = _state_path(conversation_id, work_dir)
    tmp_path = final_path.with_suffix(final_path.suffix + f".tmp.{os.getpid()}")
    tmp_path.write_text(_dumps_deterministic(state), encoding="utf-8")
    os.replace(str(tmp_path), str(final_path))
