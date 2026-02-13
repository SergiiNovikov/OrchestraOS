from __future__ import annotations

import json
import os
import types
import urllib.request
import pytest

from extensions.llm.openai_responses_client_v1 import (
    OpenAIClientError,
    call_openai_responses_json_mode_fail_closed,
)


class _FakeHTTPResponse:
    def __init__(self, payload: dict):
        self._b = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def read(self) -> bytes:
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_openai_client_env_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    with pytest.raises(OpenAIClientError):
        call_openai_responses_json_mode_fail_closed(
            input_messages=[{"role": "user", "content": "hi"}],
        )


def test_openai_client_parses_output_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test_key")
    monkeypatch.setenv("OPENAI_MODEL", "test_model")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com")

    def fake_urlopen(req: urllib.request.Request, timeout: int = 0):
        payload = {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "{\"ok\":true}"}],
                }
            ]
        }
        return _FakeHTTPResponse(payload)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    raw, out_text = call_openai_responses_json_mode_fail_closed(
        input_messages=[{"role": "user", "content": "hi"}],
        temperature=0.0,
        timeout_s=5,
    )
    assert isinstance(raw, dict)
    assert out_text == "{\"ok\":true}"
