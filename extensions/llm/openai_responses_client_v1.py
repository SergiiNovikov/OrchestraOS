from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


class OpenAIClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenAIEnvConfig:
    api_key: str
    model: str
    base_url: str
    organization: Optional[str]

    @staticmethod
    def from_env_fail_closed() -> "OpenAIEnvConfig":
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        model = os.environ.get("OPENAI_MODEL", "").strip()
        base_url = os.environ.get("OPENAI_BASE_URL", "").strip() or "https://api.openai.com"
        organization = os.environ.get("OPENAI_ORG", "").strip() or None

        if not api_key:
            raise OpenAIClientError("OPENAI_API_KEY is required for LLM_PROVIDER=openai in LLM_MODE=record.")
        if not model:
            raise OpenAIClientError("OPENAI_MODEL is required for LLM_PROVIDER=openai in LLM_MODE=record.")

        return OpenAIEnvConfig(api_key=api_key, model=model, base_url=base_url, organization=organization)


def _extract_output_text_fail_closed(resp_json: Dict[str, Any]) -> str:
    """
    Responses API returns:
      { "output": [ { "type": "message", "content": [ { "type": "output_text", "text": "..." }, ... ] }, ... ] }
    We deterministically concatenate all output_text chunks in order.
    """
    out = resp_json.get("output")
    if not isinstance(out, list):
        raise OpenAIClientError("OpenAI response missing 'output' array.")

    chunks: List[str] = []
    for item in out:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "output_text":
                text = part.get("text")
                if isinstance(text, str):
                    chunks.append(text)

    joined = "".join(chunks).strip()
    if not joined:
        raise OpenAIClientError("OpenAI response had no output_text.")
    return joined


def call_openai_responses_json_mode_fail_closed(
    *,
    input_messages: List[Dict[str, Any]],
    temperature: float = 0.0,
    timeout_s: int = 60,
) -> Tuple[Dict[str, Any], str]:
    """
    Calls POST {base_url}/v1/responses with JSON mode enabled:
      text: { format: { type: "json_object" } }
    We still instruct JSON in the system message on the caller side (fail-closed parsing anyway).

    Returns:
      (raw_response_json, output_text)
    """
    cfg = OpenAIEnvConfig.from_env_fail_closed()
    url = cfg.base_url.rstrip("/") + "/v1/responses"

    body: Dict[str, Any] = {
        "model": cfg.model,
        "input": input_messages,
        "temperature": float(temperature),
        "text": {"format": {"type": "json_object"}},
        # Do NOT set store flags here unless you have a policy; keep minimal surface.
    }

    data = json.dumps(body, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }
    if cfg.organization:
        headers["OpenAI-Organization"] = cfg.organization

    req = urllib.request.Request(url=url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw_bytes = resp.read()
    except urllib.error.HTTPError as e:
        # Fail-closed with response body included (best-effort) for debugging.
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except Exception:
            detail = "<unreadable>"
        raise OpenAIClientError(f"OpenAI HTTPError {e.code}: {detail}") from e
    except Exception as e:
        raise OpenAIClientError(f"OpenAI request failed: {e}") from e

    try:
        resp_json = json.loads(raw_bytes.decode("utf-8"))
    except Exception as e:
        raise OpenAIClientError(f"OpenAI response was not valid JSON: {e}") from e

    output_text = _extract_output_text_fail_closed(resp_json)
    return resp_json, output_text
