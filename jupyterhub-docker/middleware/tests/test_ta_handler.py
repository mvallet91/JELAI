"""End-to-end tests of the Tutor Agent API with a fake LLM."""

import base64
import importlib
import importlib.util

import pytest
from fastapi.testclient import TestClient

import config_loader
import llm_client
from conftest import MIDDLEWARE_DIR


@pytest.fixture
def ta(inputs_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("JELAI_INPUTS_DIR", str(inputs_dir))
    monkeypatch.setenv("AGENT_CONFIG_DEFAULTS", str(inputs_dir.parent / "defaults" / "agent_config.yaml"))
    monkeypatch.setenv("DATABASE_FILE", str(tmp_path / "db" / "chat.db"))
    monkeypatch.setenv("INGESTED_LOGS_DIR", str(tmp_path / "student_logs"))
    monkeypatch.setenv("PROCESSED_LOGS_DIR", str(tmp_path / "none"))
    monkeypatch.setenv("TEACHER_PASSWORD", "secret")
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("ETHERPAD_ENABLED", "false")
    importlib.reload(config_loader)
    import learner_model, learning_story, pedagogy, teacher_view
    for module in (learner_model, learning_story, pedagogy, teacher_view):
        importlib.reload(module)
    llm_client._settings = None

    calls = []

    async def fake_call_llm(messages, role="response", model=None, purpose="", settings=None):
        calls.append({"role": role, "model": model, "messages": messages})
        if role == "classification":
            return "executive"
        if role == "proactivity":
            return '{"reasoning": "stuck", "message": "Do you want a hint about the error in your plot?"}'
        return "Here is a hint."

    monkeypatch.setattr(llm_client, "call_llm", fake_call_llm)

    spec = importlib.util.spec_from_file_location("ta_handler", MIDDLEWARE_DIR / "ta-handler.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.EA_URL = "http://127.0.0.1:1/expert_query"  # unreachable: the EA fallback is used
    return module, TestClient(module.app), calls


def auth(password="secret"):
    token = base64.b64encode(f"teacher:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def ask(client, text, student="ana"):
    return client.post("/receive_student_message", json={
        "student_id": student, "message_text": text, "file_name": "Task.chat",
        "processed_logs": "[JUPYTER] ran a cell",
        "structured_logs": [{"event": "Executed cells", "time": "2026-01-01T10:00:00",
                             "notebook": "Task.ipynb", "cell_index": 1, "input": "import pandas as pd"}],
    })


def test_message_flow_applies_intervention_rules(ta):
    module, client, calls = ta
    assert ask(client, "give me the code").json()["final_response"] == "Here is a hint."
    response_call = [c for c in calls if c["role"] == "response"][-1]
    assert "Profile Hint (First executive)" in response_call["messages"][0]["content"]

    ask(client, "just write it")
    response_call = [c for c in calls if c["role"] == "response"][-1]
    assert "Profile Hint (Second executive)" in response_call["messages"][0]["content"]

    profile = module.get_student_profile("ana", "Task.chat")
    assert profile["category_counts"] == {"executive": 2}
    assert profile["category_streak"] == 2


def test_teacher_model_override_and_agent_name(ta, inputs_dir):
    module, client, calls = ta
    (inputs_dir / "agent_config.yaml").write_text(
        "agent:\n  name: Ada\nllm:\n  models:\n    response: big-model\nexpert_agent:\n  enabled: false\n")
    ask(client, "why does this fail?")
    response_call = [c for c in calls if c["role"] == "response"][-1]
    assert response_call["model"] == "big-model"
    assert "as Ada" in response_call["messages"][-1]["content"]
    assert client.get("/agent_config").json()["agent"]["name"] == "Ada"


def test_logs_are_stored_for_the_dashboard(ta):
    module, client, calls = ta
    ask(client, "hello")
    story = client.get("/teacher/student/ana/canvas", headers=auth()).json()
    assert story["jupyter"]["total_executions"] == 1
    assert "pandas import" in story["jupyter"]["concepts_used"]


def test_proactivity_and_disable(ta, inputs_dir):
    module, client, calls = ta
    payload = {"student_id": "ana", "file_name": "Task.chat", "processed_logs": "x"}
    result = client.post("/evaluate_proactivity", json=payload).json()
    assert result["intervention"].startswith("Do you want a hint")
    (inputs_dir / "agent_config.yaml").write_text("proactivity:\n  enabled: false\n")
    assert client.post("/evaluate_proactivity", json=payload).json()["intervention"] == "NO_INTERVENTION"


def test_report_and_completion_commands(ta, inputs_dir):
    module, client, calls = ta
    assert ask(client, "/report").json()["final_response"] == "Here is a hint."
    assert [c for c in calls if c["role"] == "report"]
    (inputs_dir / "agent_config.yaml").write_text(
        "commands:\n  completion:\n    enabled: true\n    min_minutes: 0\n    min_questions: 0\n    code: ABC-1\n")
    assert "ABC-1" in ask(client, "/finish").json()["final_response"]


def test_teacher_pages_need_password(ta):
    module, client, calls = ta
    assert client.get("/teacher/students").status_code == 401
    assert client.get("/teacher/students", headers=auth("wrong")).status_code == 401
    assert client.get("/teacher/students", headers=auth()).status_code == 200
    assert client.get("/teacher-settings", headers=auth()).status_code == 200


def test_settings_api_edits_files(ta, inputs_dir):
    module, client, calls = ta
    files = client.get("/teacher/settings/files", headers=auth()).json()
    paths = [f["path"] for f in files["groups"]["configuration"]]
    assert "agent_config.yaml" in paths

    sample = client.get("/teacher/settings/file", params={"path": "ta_system_prompt.txt"}, headers=auth()).json()
    assert sample["from_sample"] is True

    bad = client.put("/teacher/settings/file", headers=auth(),
                     json={"path": "agent_config.yaml", "content": "classification:\n  categories: []\n"})
    assert bad.status_code == 422

    ok = client.put("/teacher/settings/file", headers=auth(),
                    json={"path": "learning_objectives/Week1.txt", "content": "Use loops"})
    assert ok.status_code == 200
    assert (inputs_dir / "learning_objectives" / "Week1.txt").read_text() == "Use loops"

    for path in ("../secret.txt", "templates/x.html", "agent_config.py"):
        r = client.put("/teacher/settings/file", headers=auth(), json={"path": path, "content": "x"})
        assert r.status_code == 400, path

    status = client.get("/teacher/settings/status", headers=auth()).json()
    assert status["llm"]["provider"] == "groq"
    assert "k" != status["llm"].get("api_key")
