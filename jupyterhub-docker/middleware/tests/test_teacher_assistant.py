"""Tests of the help assistant of the teacher pages."""

import pytest

import llm_client
import teacher_assistant
from test_ta_handler import auth, ta  # noqa: F401  (pytest fixture)

REPLY_WITH_EDIT = """Open the file and change the name.

```jelai-edit path=agent_config.yaml
<<<<<<< FIND
  name: "Juno"
=======
  name: "Nova"
>>>>>>> REPLACE
```

Then the tutor uses the new name."""


def test_parse_reply_extracts_proposals():
    text, proposals = teacher_assistant.parse_reply(REPLY_WITH_EDIT)
    assert "[Proposal 1]" in text
    assert "<<<<<<<" not in text
    assert text.endswith("Then the tutor uses the new name.")
    assert len(proposals) == 1
    assert proposals[0].path == "agent_config.yaml"
    assert proposals[0].edits == [('  name: "Juno"', '  name: "Nova"')]


def test_parse_reply_marks_incomplete_proposal():
    _, proposals = teacher_assistant.parse_reply("```jelai-edit path=x.txt\n<<<<<<< FIND\nabc\n")
    assert proposals[0].error


def test_apply_edits_exact_and_trailing_spaces():
    content = "a: 1\nb: 2   \nc: 3\n"
    assert teacher_assistant.apply_edits(content, [("a: 1", "a: 5")]) == "a: 5\nb: 2   \nc: 3\n"
    # The LLM often drops spaces at the end of a line.
    assert teacher_assistant.apply_edits(content, [("b: 2\nc: 3", "b: 7\nc: 3")]) == "a: 1\nb: 7\nc: 3\n"


def test_apply_edits_refuses_ambiguous_or_missing_text():
    with pytest.raises(ValueError):
        teacher_assistant.apply_edits("x\nx\n", [("x", "y")])
    with pytest.raises(ValueError):
        teacher_assistant.apply_edits("x\n", [("z", "y")])


def test_apply_edits_empty_find_replaces_file():
    assert teacher_assistant.apply_edits("old\n", [("", "new")]) == "new\n"


def test_assignment_gaps(inputs_dir, monkeypatch):
    monkeypatch.setattr(teacher_assistant, "INPUTS_DIR", inputs_dir)
    (inputs_dir / "learning_objectives" / "Task2.txt").write_text("Use groupby\n")
    gaps = teacher_assistant.assignment_gaps(["Task2.ipynb"])
    assert len(gaps) == 1
    assert "assignment_descriptions/Task2.txt" in gaps[0]
    assert "learning_objectives" not in gaps[0]


def test_split_markdown_and_yaml():
    md = teacher_assistant._split_markdown("docs/a.md", "# Title\nIntro\n\n## One\nText one\n\n## Two\nText two")
    assert [c.title for c in md] == ["docs/a.md", "docs/a.md: One", "docs/a.md: Two"]
    yml = teacher_assistant._split_yaml("x.yaml", "# head\nagent:\n  name: A\n\n# Models\nllm:\n  models: {}\n")
    assert [c.title for c in yml] == ["x.yaml: agent", "x.yaml: llm"]
    # The comment above a key goes with that key.
    assert yml[1].text.startswith("\n# Models") or yml[1].text.startswith("# Models")
    assert "# head" in yml[0].text


def test_select_chunks_prefers_related_parts_and_respects_budget(inputs_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(teacher_assistant, "INPUTS_DIR", inputs_dir)
    monkeypatch.setenv("TEACHER_DOCS_DIR", str(tmp_path / "docs"))
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text(
        "# Guide\n\n## Add an assignment\nUpload the notebook.\n\n## LLM provider\nSet LLM_PROVIDER in .env.\n")
    chunks = teacher_assistant.load_chunks()
    titles = [c.title for c in chunks]
    assert "agent_config.yaml: agent" in titles
    assert any(t.startswith("ta_system_prompt.txt") for t in titles)

    selected = teacher_assistant.select_chunks(chunks, ["Rename the tutor: agent name"], 3000)
    assert "agent_config.yaml: agent" in [c.title for c in selected]
    assert sum(len(c.text) for c in selected) <= 3000

    selected = teacher_assistant.select_chunks(chunks, ["Wie ändere ich den LLM-Anbieter?"], 3000)
    assert "docs/guide.md: LLM provider" in [c.title for c in selected]

    knowledge = teacher_assistant.format_knowledge(chunks, selected)
    assert "Other parts" in knowledge and "agent_config.yaml: interventions" in knowledge


def test_prompt_fits_free_tier_limit(inputs_dir, monkeypatch):
    """The prompt must stay far below 8000 tokens (Groq free tier) with the real docs."""
    from conftest import MIDDLEWARE_DIR
    monkeypatch.setattr(teacher_assistant, "INPUTS_DIR", inputs_dir)
    monkeypatch.setenv("TEACHER_DOCS_DIR", str(MIDDLEWARE_DIR.parent.parent / "docs"))
    monkeypatch.setenv("COURSE_MATERIALS_DIR", str(inputs_dir / "none"))
    history = [{"role": "user", "content": q} for q in (
        "How do I change the prompt of the tutor?", "How do I add a new assignment?")]
    messages = teacher_assistant.build_prompt(history, {"models": {"response": "m"}}, "ta_system_prompt.txt")
    chars = sum(len(m["content"]) for m in messages)
    assert chars < 20000  # about 5000 tokens


def test_assistant_role_uses_response_model():
    s = llm_client.load_settings({"LLM_PROVIDER": "groq", "LLM_API_KEY": "k"})
    assert s.models["assistant"] == s.models["response"] == "openai/gpt-oss-120b"
    s = llm_client.load_settings({"LLM_PROVIDER": "groq", "LLM_MODEL_ASSISTANT": "m-help"})
    assert s.models["assistant"] == "m-help"


@pytest.fixture
def assistant(ta, monkeypatch, tmp_path):  # noqa: F811
    module, client, _ = ta
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "teacher-configuration.md").write_text("# Teacher configuration\n\n## Rename the tutor\nUse the settings page.")
    monkeypatch.setenv("TEACHER_DOCS_DIR", str(docs))
    monkeypatch.setenv("COURSE_MATERIALS_DIR", str(tmp_path / "materials"))
    (tmp_path / "materials").mkdir()
    (tmp_path / "materials" / "Task2.ipynb").write_text("{}")
    import importlib
    importlib.reload(teacher_assistant)
    calls = []
    replies = []

    async def fake_call_llm(messages, role="response", model=None, purpose="", settings=None):
        calls.append({"role": role, "messages": messages})
        return replies.pop(0)

    monkeypatch.setattr(llm_client, "call_llm", fake_call_llm)
    return client, calls, replies


def test_chat_gives_context_and_proposal(assistant, inputs_dir):
    client, calls, replies = assistant
    replies.append(REPLY_WITH_EDIT)
    r = client.post("/teacher/assistant/chat", headers=auth(), json={
        "messages": [{"role": "user", "content": "How do I rename the tutor?"}],
        "current_path": "ta_system_prompt.txt",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    system = calls[0]["messages"][0]["content"]
    assert calls[0]["role"] == "assistant"
    assert "Use the settings page." in system          # documentation
    assert "Task2.ipynb" in system                      # course materials
    assert "assignment_descriptions/Task2.txt" in system  # gap
    assert "k" not in [line.strip() for line in system.splitlines()]
    assert "API key set: yes" in system
    proposal = data["proposals"][0]
    assert proposal["applicable"], proposal
    assert '+  name: "Nova"' in proposal["diff"]

    # Nothing is saved before Apply.
    assert 'name: "Juno"' in (inputs_dir / "agent_config.yaml").read_text()
    saved = client.post("/teacher/assistant/apply", headers=auth(), json={
        "path": proposal["path"], "content": proposal["content"], "base_sha256": proposal["base_sha256"]})
    assert saved.status_code == 200, saved.text
    assert 'name: "Nova"' in (inputs_dir / "agent_config.yaml").read_text()

    # The same proposal again: the file changed, so it is refused.
    again = client.post("/teacher/assistant/apply", headers=auth(), json={
        "path": proposal["path"], "content": proposal["content"], "base_sha256": proposal["base_sha256"]})
    assert again.status_code == 409


def test_chat_proposal_for_new_file_and_invalid_yaml(assistant, inputs_dir):
    client, _, replies = assistant
    replies.append(
        "```jelai-edit path=learning_objectives/Task2.txt\n<<<<<<< FIND\n=======\nUse groupby\n>>>>>>> REPLACE\n```\n"
        "```jelai-edit path=agent_config.yaml\n<<<<<<< FIND\n  name: \"Juno\"\n=======\n  name: [\n>>>>>>> REPLACE\n```\n"
        "```jelai-edit path=../.env\n<<<<<<< FIND\n=======\nx\n>>>>>>> REPLACE\n```"
    )
    data = client.post("/teacher/assistant/chat", headers=auth(), json={
        "messages": [{"role": "user", "content": "Add objectives"}]}).json()
    new_file, bad_yaml, env = data["proposals"]
    assert new_file["applicable"] and new_file["new_file"]
    assert new_file["base_sha256"] == teacher_assistant.sha256("")
    assert not bad_yaml["applicable"] and bad_yaml["errors"]
    assert not env["applicable"] and "cannot be edited" in env["error"]

    bad = client.post("/teacher/assistant/apply", headers=auth(), json={
        "path": "agent_config.yaml", "content": bad_yaml["content"], "base_sha256": bad_yaml["base_sha256"]})
    assert bad.status_code == 422
    ok = client.post("/teacher/assistant/apply", headers=auth(), json={
        "path": new_file["path"], "content": new_file["content"], "base_sha256": new_file["base_sha256"]})
    assert ok.status_code == 200
    assert (inputs_dir / "learning_objectives" / "Task2.txt").read_text() == "Use groupby\n"


def test_assistant_needs_password_and_can_be_off(assistant, inputs_dir):
    client, _, _ = assistant
    assert client.post("/teacher/assistant/chat", json={"messages": []}).status_code == 401
    assert client.get("/teacher/assistant.js", headers=auth()).status_code == 200
    config = inputs_dir / "agent_config.yaml"
    config.write_text(config.read_text().replace("teacher_assistant:\n  enabled: true", "teacher_assistant:\n  enabled: false"))
    r = client.post("/teacher/assistant/chat", headers=auth(), json={
        "messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 403
