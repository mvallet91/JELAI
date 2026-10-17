import asyncio

import httpx
import pytest

import llm_client


def settings(env):
    return llm_client.load_settings(env)


def test_preset_defaults():
    s = settings({"LLM_PROVIDER": "groq", "LLM_API_KEY": "k"})
    assert s.base_url == "https://api.groq.com/openai/v1"
    assert s.chat_url == "https://api.groq.com/openai/v1/chat/completions"
    assert s.models["classification"] == "openai/gpt-oss-20b"
    assert s.models["response"] == "openai/gpt-oss-120b"


def test_model_precedence():
    s = settings({"LLM_PROVIDER": "groq", "LLM_MODEL": "m-all", "LLM_MODEL_EXPERT": "m-expert"})
    assert s.models["expert"] == "m-expert"
    assert s.models["classification"] == "m-all"


def test_openwebui_appends_api_path():
    s = settings({"LLM_PROVIDER": "openwebui", "LLM_BASE_URL": "https://chat.example.org/", "LLM_API_KEY": "k"})
    assert s.chat_url == "https://chat.example.org/api/chat/completions"


def test_full_endpoint_url_is_accepted():
    s = settings({"LLM_PROVIDER": "custom", "LLM_BASE_URL": "https://x.org/v1/chat/completions"})
    assert s.chat_url == "https://x.org/v1/chat/completions"


def test_legacy_ollama_variables():
    s = settings({"ollama_url": "'http://gpu:11434'", "ollama_response_model": "gemma3:27b"})
    assert s.provider == "ollama"
    assert s.chat_url == "http://gpu:11434/v1/chat/completions"
    assert s.models["response"] == "gemma3:27b"


def test_legacy_webui_variables():
    s = settings({"webui_url": "https://webui.example.org", "webui_api_key": "secret"})
    assert s.provider == "openwebui"
    assert s.api_key == "secret"
    assert s.chat_url == "https://webui.example.org/api/chat/completions"


def test_missing_base_url_for_custom():
    with pytest.raises(llm_client.LLMError):
        settings({"LLM_PROVIDER": "custom"})


def test_api_key_not_in_description():
    s = settings({"LLM_PROVIDER": "openai", "LLM_API_KEY": "sk-secret"})
    assert "sk-secret" not in str(s.describe())


def _patch_transport(monkeypatch, handler):
    real_client = httpx.AsyncClient

    class Client(real_client):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(llm_client.httpx, "AsyncClient", Client)
    real_sleep = asyncio.sleep
    monkeypatch.setattr(llm_client.asyncio, "sleep", lambda *_: real_sleep(0))


def test_call_retries_after_rate_limit(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "1"}, json={"error": {"message": "slow down"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": " hello "}}]})

    _patch_transport(monkeypatch, handler)
    s = settings({"LLM_PROVIDER": "groq", "LLM_API_KEY": "k"})
    text = asyncio.run(llm_client.call_llm([{"role": "user", "content": "hi"}], role="classification", settings=s))
    assert text == "hello"
    assert len(calls) == 2
    assert calls[0].headers["Authorization"] == "Bearer k"
    assert b'"model":"openai/gpt-oss-20b"' in calls[0].content.replace(b" ", b"")


def test_call_does_not_retry_client_errors(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    _patch_transport(monkeypatch, handler)
    s = settings({"LLM_PROVIDER": "openai", "LLM_API_KEY": "k"})
    with pytest.raises(llm_client.LLMError) as err:
        asyncio.run(llm_client.call_llm([{"role": "user", "content": "hi"}], settings=s))
    assert err.value.status_code == 401
    assert "bad key" in str(err.value)
    assert len(calls) == 1
