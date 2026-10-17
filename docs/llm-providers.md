# LLM providers

JELAI sends all LLM requests to one OpenAI-compatible API. You select the
provider in `jupyterhub-docker/.env` (or with `./setup.sh`). This page tells
you how to configure each provider and which providers have a free tier for
schools that do not have a GPU server or a budget for an API.

## Settings

| Variable | Description |
|---|---|
| `LLM_PROVIDER` | The preset: `ollama`, `openai`, `openwebui`, `groq`, `gemini`, `mistral`, `openrouter`, `ollama-cloud` or `custom`. |
| `LLM_BASE_URL` | The API base URL. Empty means the default URL of the preset. |
| `LLM_API_KEY` | The API key. A local Ollama server does not need one. |
| `LLM_MODEL` | The model for all tasks. Empty means the default model of the preset. |
| `LLM_MODEL_CLASSIFICATION`, `LLM_MODEL_RESPONSE`, `LLM_MODEL_EXPERT`, `LLM_MODEL_PROACTIVITY`, `LLM_MODEL_REPORT` | Optional: a different model for each task. |
| `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES` | The request timeout, and the number of retries after HTTP 429 (rate limit) or HTTP 5xx. |

Teachers can also set the model for each task in `agent_config.yaml`
(section `llm.models`). A value there has priority over the `.env` file.

After you change the `.env` file, restart the middleware:

```bash
cd jupyterhub-docker
docker compose up -d middleware
```

To check the connection, open the teacher settings page
(`http://<server>:8004/teacher-settings`) and click **Test connection**.

## Presets

| Preset | Default base URL | Default models | Key |
|---|---|---|---|
| `ollama` | `http://host.docker.internal:11434/v1` | `gemma3:4b` | No |
| `openai` | `https://api.openai.com/v1` | `gpt-5-mini`, classification `gpt-5-nano` | Yes |
| `openwebui` | Your server URL; JELAI adds `/api` | `gemma3:4b` | Yes |
| `groq` | `https://api.groq.com/openai/v1` | `openai/gpt-oss-120b`, classification `openai/gpt-oss-20b` | Yes |
| `gemini` | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.5-flash`, classification `gemini-2.5-flash-lite` | Yes |
| `mistral` | `https://api.mistral.ai/v1` | `mistral-small-latest` | Yes |
| `openrouter` | `https://openrouter.ai/api/v1` | None: set `LLM_MODEL` | Yes |
| `ollama-cloud` | `https://ollama.com/v1` | `gpt-oss:120b`, classification `gpt-oss:20b` | Yes |
| `custom` | None: set `LLM_BASE_URL` | `gemma3:4b` | Optional |

Hosted providers change their model names often. If a request fails with
"model not found", set `LLM_MODEL` to a model from the list of the provider.

### Examples

Self-hosted Ollama on the same machine:

```dotenv
LLM_PROVIDER=ollama
LLM_MODEL=gemma3:12b
```

Ollama on a different GPU server:

```dotenv
LLM_PROVIDER=ollama
LLM_BASE_URL=http://gpu-server.example.org:11434/v1
```

Open WebUI of a university:

```dotenv
LLM_PROVIDER=openwebui
LLM_BASE_URL=https://chat.example.org
LLM_API_KEY=sk-...
LLM_MODEL=gemma3:27b
```

OpenAI:

```dotenv
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
```

## Free options for schools without a GPU server

Each of these services has a free tier with an OpenAI-compatible API. Free
tiers have rate limits, and the limits change often. The values below are
from October 2026. Do a check on the website of the provider before a course.

| Provider | Free limits (October 2026) | Card necessary | Notes |
|---|---|---|---|
| **Groq** (`groq`) | 30 requests/minute, 1,000 requests/day and 200,000 tokens/day, for each model | No | Fast. The limits apply to the organization, not to each key. |
| **Mistral AI** (`mistral`) | Free monthly API credits (about 10 USD) | No | Servers in the EU. Read the data settings of the free plan (see Privacy). |
| **Google Gemini** (`gemini`) | Free tier; limits are shown in Google AI Studio | No | Not for the EU, UK or Switzerland: there, Google requires the paid service for apps that serve users. Free-tier data can be used to improve Google products. |
| **OpenRouter** (`openrouter`) | Models that end in `:free`: 20 requests/minute, 50 requests/day; 1,000 requests/day after a one-time purchase of 10 USD credits | No | Set `LLM_MODEL` to a free model. Free models can log prompts. |
| **Ollama Cloud** (`ollama-cloud`) | Free tier with session and weekly limits (not published) | No | Uses the same models as self-hosted Ollama. |

Sources: [OpenRouter: free LLM APIs compared](https://openrouter.ai/blog/tutorials/free-llm-apis-compared/),
[Free LLM API tiers in October 2026](https://dev.to/tariqnasser/free-llm-api-tiers-in-october-2026-whats-left-and-how-i-chain-them-227l),
[Free LLM API tiers, verified daily](https://gravity.fast/data/free-llm-api-tiers/),
[Ollama Cloud free tier](https://freellm.net/providers/ollama-cloud).

**Our recommendation:** for a full class, start with **Mistral**: the
monthly credits give the most tokens, and the servers are in the EU. Use
**Groq** to try JELAI or for small groups: its daily token limit is low (see
below). Both need only an e-mail address.

### Another free option: a partner university

Many universities and national research networks run an Open WebUI or Ollama
server for education. Ask your partner university if your school can get an
API key. Then use the `openwebui` or `ollama` preset with their URL.

### How many requests does a class use?

Each student question uses up to three LLM requests: classification, expert
agent and tutor response. Proactive messages use one more request when the
activity of a student changes (at most once each `min_cooldown_seconds`).

One request uses about 1,000 to 3,000 tokens, because the prompt contains
the conversation history and the recent notebook activity. Thus, for most
free tiers, the **token limit** is reached before the request limit.

Example: 25 students ask 10 questions each. This is 250 questions, or up to
750 requests and about 1 to 2 million tokens in one day.

- Groq (200,000 tokens/day for each model) gives about 70 to 200 requests per
  model each day. This is sufficient for a test or a small group, not for a
  full class.
- Mistral credits of 10 USD give tens of millions of tokens with a small model
  (for example `mistral-small-latest`). This is sufficient for a class for a month.

To use less quota, edit `agent_config.yaml` (or the settings page):

- Set `expert_agent.enabled: false`. This removes one request per question.
- Set `proactivity.enabled: false`, or make `min_cooldown_seconds` larger.
- Use a different model for classification (`LLM_MODEL_CLASSIFICATION`).
  On Groq and Gemini, the limits apply to each model, so two models give
  you more requests per day.

When a provider sends HTTP 429 (rate limit), JELAI waits and tries again
(`LLM_MAX_RETRIES`). If the limit stays, the student gets a message to wait
and ask again.

### Privacy

Student messages and notebook activity go to the LLM provider. Before you
use a hosted provider with students:

- Get approval from your school (for example the data protection officer).
- Read the data terms of the provider. Some free tiers use your data to train
  or improve their models. Use the setting to opt out where the provider has one.
- Tell students that their messages go to an external service.
- Do not use the students' real names as JupyterHub user names, if possible.
