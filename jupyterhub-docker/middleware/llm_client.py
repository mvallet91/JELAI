"""OpenAI-compatible LLM client shared by the Tutor Agent and the Expert Agent.

All LLM calls in JELAI go through ``call_llm``. The client talks to any
server that implements the OpenAI ``/chat/completions`` API. This includes
OpenAI, a local or remote Ollama server, Open WebUI, and hosted services
with a free tier (Groq, OpenRouter, Google Gemini, Mistral, Ollama Cloud).

Configuration comes from environment variables:

``LLM_PROVIDER``
    A preset name from ``PROVIDER_PRESETS`` (for example ``ollama``,
    ``openai``, ``openwebui``, ``groq``). The preset gives a default base
    URL and default models. Use ``custom`` for any other server.
``LLM_BASE_URL``
    The base URL of the API. It overrides the preset URL. For Open WebUI,
    give the server URL (for example ``https://chat.example.org``).
``LLM_API_KEY``
    The API key. Local Ollama does not need one.
``LLM_MODEL``
    The default model for all roles.
``LLM_MODEL_CLASSIFICATION``, ``LLM_MODEL_RESPONSE``, ``LLM_MODEL_EXPERT``,
``LLM_MODEL_PROACTIVITY``, ``LLM_MODEL_REPORT``
    Optional models for each role. Use a small model for classification
    to make it fast and to save quota on free tiers.
``LLM_TIMEOUT_SECONDS``, ``LLM_MAX_RETRIES``
    The request timeout and the number of retries after a rate limit
    (HTTP 429) or a server error (HTTP 5xx).

The earlier variables ``ollama_url``, ``webui_url``, ``webui_api_key``,
``ollama_classification_model``, ``ollama_response_model`` and
``ollama_ea_model`` are still read when the new variables are not set.
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger("jelai.llm")

ROLES = ("classification", "response", "expert", "proactivity", "report")

# Each preset gives a base URL and default models. ``models`` maps a role
# to a model; the key ``default`` applies to roles without an entry.
# Models of hosted services change often: set LLM_MODEL to override.
PROVIDER_PRESETS: Dict[str, Dict] = {
    "ollama": {
        "label": "Ollama (self-hosted)",
        "base_url": "http://host.docker.internal:11434/v1",
        "requires_key": False,
        "models": {"default": "gemma3:4b"},
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "requires_key": True,
        "models": {"default": "gpt-5-mini", "classification": "gpt-5-nano"},
    },
    "openwebui": {
        "label": "Open WebUI",
        "base_url": None,  # The server URL is necessary.
        "path_suffix": "/api",
        "requires_key": True,
        "models": {"default": "gemma3:4b"},
    },
    "groq": {
        "label": "Groq (free tier available)",
        "base_url": "https://api.groq.com/openai/v1",
        "requires_key": True,
        "models": {"default": "openai/gpt-oss-120b", "classification": "openai/gpt-oss-20b"},
    },
    "openrouter": {
        "label": "OpenRouter (free models available)",
        "base_url": "https://openrouter.ai/api/v1",
        "requires_key": True,
        "models": {},  # Set LLM_MODEL, for example a model ID that ends in ':free'.
    },
    "gemini": {
        "label": "Google Gemini (free tier available)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "requires_key": True,
        "models": {"default": "gemini-2.5-flash", "classification": "gemini-2.5-flash-lite"},
    },
    "mistral": {
        "label": "Mistral AI (free monthly credits)",
        "base_url": "https://api.mistral.ai/v1",
        "requires_key": True,
        "models": {"default": "mistral-small-latest"},
    },
    "ollama-cloud": {
        "label": "Ollama Cloud (free tier available)",
        "base_url": "https://ollama.com/v1",
        "requires_key": True,
        "models": {"default": "gpt-oss:120b", "classification": "gpt-oss:20b"},
    },
    "custom": {
        "label": "Other OpenAI-compatible server",
        "base_url": None,
        "requires_key": False,
        "models": {},
    },
}

LEGACY_MODEL_VARS = {
    "classification": "ollama_classification_model",
    "response": "ollama_response_model",
    "expert": "ollama_ea_model",
    "proactivity": "ollama_response_model",
    "report": "ollama_response_model",
}

FALLBACK_MODEL = "gemma3:4b"


class LLMError(Exception):
    """An LLM call failed. ``status_code`` is the HTTP status, if known."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class LLMSettings:
    provider: str
    base_url: str
    api_key: str = ""
    models: Dict[str, str] = field(default_factory=dict)
    timeout: float = 90.0
    max_retries: int = 2

    @property
    def chat_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def describe(self) -> Dict:
        """Return the settings without the API key, for logs and the teacher UI."""
        return {
            "provider": self.provider,
            "provider_label": PROVIDER_PRESETS.get(self.provider, {}).get("label", self.provider),
            "base_url": self.base_url,
            "api_key_set": bool(self.api_key),
            "models": dict(self.models),
        }


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip().strip("'\"")


def _normalize_base_url(url: str, path_suffix: str = "") -> str:
    url = url.rstrip("/")
    if url.endswith("/chat/completions"):
        url = url[: -len("/chat/completions")]
    if path_suffix and not url.endswith(path_suffix) and not url.endswith("/v1"):
        url += path_suffix
    return url


def load_settings(env: Optional[Dict[str, str]] = None) -> LLMSettings:
    """Build the LLM settings from environment variables.

    ``env`` replaces ``os.environ`` when given. Tests use it.
    """
    if env is not None:
        get = lambda name: (env.get(name) or "").strip().strip("'\"")  # noqa: E731
    else:
        get = _env

    provider = get("LLM_PROVIDER").lower()
    base_url = get("LLM_BASE_URL")
    api_key = get("LLM_API_KEY")

    if not provider:
        # Earlier configuration: Open WebUI when a key is set, else Ollama.
        if get("webui_api_key"):
            provider = "openwebui"
            base_url = base_url or get("webui_url") or "http://localhost:3000"
            api_key = api_key or get("webui_api_key")
        elif get("ollama_url") and not base_url:
            provider = "ollama"
            base_url = get("ollama_url").rstrip("/") + "/v1"
        else:
            provider = "custom" if base_url else "ollama"

    if provider not in PROVIDER_PRESETS:
        logger.warning("Unknown LLM_PROVIDER '%s'. Using it as a custom OpenAI-compatible server.", provider)
        preset = PROVIDER_PRESETS["custom"]
    else:
        preset = PROVIDER_PRESETS[provider]

    if not base_url:
        base_url = preset.get("base_url") or ""
    if not base_url:
        raise LLMError(
            f"LLM_BASE_URL is necessary for the provider '{provider}'. "
            "Set it in the .env file."
        )
    base_url = _normalize_base_url(base_url, preset.get("path_suffix", ""))

    if preset.get("requires_key") and not api_key:
        logger.warning("The provider '%s' usually needs an API key, but LLM_API_KEY is empty.", provider)

    default_model = get("LLM_MODEL")
    models = {}
    for role in ROLES:
        models[role] = (
            get(f"LLM_MODEL_{role.upper()}")
            or default_model
            or get(LEGACY_MODEL_VARS[role])
            or preset["models"].get(role)
            or preset["models"].get("default")
            or FALLBACK_MODEL
        )

    timeout = float(get("LLM_TIMEOUT_SECONDS") or 90)
    max_retries = int(get("LLM_MAX_RETRIES") or 2)
    return LLMSettings(provider, base_url, api_key, models, timeout, max_retries)


_settings: Optional[LLMSettings] = None


def get_settings() -> LLMSettings:
    global _settings
    if _settings is None:
        _settings = load_settings()
        logger.info("LLM settings: %s", _settings.describe())
    return _settings


def model_for(role: str, override: Optional[str] = None) -> str:
    """Return the model for a role. A non-empty ``override`` wins."""
    if override:
        return override
    settings = get_settings()
    return settings.models.get(role) or settings.models.get("response") or FALLBACK_MODEL


def _retry_delay(response: Optional[httpx.Response], attempt: int) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), 30.0)
            except ValueError:
                pass
    return min(2.0 ** attempt, 30.0)


def _error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
        error = body.get("error", body)
        if isinstance(error, dict):
            return str(error.get("message", error))[:300]
        return str(error)[:300]
    except ValueError:
        return response.text[:300]


async def call_llm(
    messages: List[Dict[str, str]],
    role: str = "response",
    model: Optional[str] = None,
    purpose: str = "LLM call",
    settings: Optional[LLMSettings] = None,
) -> str:
    """Send a chat completion request and return the text of the answer.

    ``role`` selects the model from the settings. ``model`` overrides it.
    The call retries after HTTP 429 and 5xx responses. It raises
    ``LLMError`` when all attempts fail.
    """
    settings = settings or get_settings()
    model_name = model or settings.models.get(role) or settings.models.get("response") or FALLBACK_MODEL
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if settings.api_key:
        headers["Authorization"] = f"Bearer {settings.api_key}"
    payload = {"model": model_name, "messages": messages, "stream": False}

    last_error: Optional[LLMError] = None
    async with httpx.AsyncClient(timeout=settings.timeout) as client:
        for attempt in range(settings.max_retries + 1):
            response = None
            try:
                response = await client.post(settings.chat_url, headers=headers, json=payload)
                if response.status_code == 429 or response.status_code >= 500:
                    last_error = LLMError(
                        f"{settings.provider} returned HTTP {response.status_code} for {purpose}: "
                        f"{_error_detail(response)}",
                        response.status_code,
                    )
                elif response.status_code >= 400:
                    raise LLMError(
                        f"{settings.provider} returned HTTP {response.status_code} for {purpose} "
                        f"(model '{model_name}'): {_error_detail(response)}",
                        response.status_code,
                    )
                else:
                    data = response.json()
                    try:
                        content = data["choices"][0]["message"]["content"]
                    except (KeyError, IndexError, TypeError):
                        raise LLMError(f"Unexpected response format for {purpose}: {str(data)[:300]}", 502)
                    logger.info("LLM call for %s succeeded (model %s).", purpose, model_name)
                    return (content or "").strip()
            except httpx.RequestError as e:
                last_error = LLMError(f"Could not connect to {settings.chat_url} for {purpose}: {e}", 503)

            if attempt < settings.max_retries:
                delay = _retry_delay(response, attempt)
                logger.warning("%s Retry in %.1f s.", last_error, delay)
                await asyncio.sleep(delay)

    raise last_error or LLMError(f"LLM call for {purpose} failed.")


async def test_connection(settings: Optional[LLMSettings] = None) -> Dict:
    """Send one short request for each distinct model. Return the results."""
    settings = settings or get_settings()
    results = []
    for model_name in sorted(set(settings.models.values())):
        start = time.time()
        try:
            text = await call_llm(
                [{"role": "user", "content": "Reply with the word OK."}],
                model=model_name,
                purpose="connection test",
                settings=LLMSettings(settings.provider, settings.base_url, settings.api_key,
                                     settings.models, settings.timeout, 0),
            )
            results.append({"model": model_name, "ok": True, "seconds": round(time.time() - start, 2),
                            "reply": text[:80]})
        except LLMError as e:
            results.append({"model": model_name, "ok": False, "seconds": round(time.time() - start, 2),
                            "error": str(e)})
    return {"settings": settings.describe(), "results": results}
