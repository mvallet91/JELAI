import config_loader


def test_teacher_file_overrides_defaults(inputs_dir):
    teacher = inputs_dir / "agent_config.yaml"
    teacher.write_text("agent:\n  name: Ada\nproactivity:\n  enabled: false\n")
    store = config_loader.ConfigStore(teacher, inputs_dir.parent / "defaults" / "agent_config.yaml")
    config = store.get()
    assert config["agent"]["name"] == "Ada"
    assert config["proactivity"]["enabled"] is False
    # Keys that the teacher file does not have come from the defaults.
    assert config["proactivity"]["min_cooldown_seconds"] == 300
    assert config["classification"]["categories"]


def test_invalid_teacher_file_keeps_defaults(inputs_dir):
    teacher = inputs_dir / "agent_config.yaml"
    teacher.write_text("agent: [unclosed\n")
    store = config_loader.ConfigStore(teacher, inputs_dir.parent / "defaults" / "agent_config.yaml")
    config = store.get()
    assert config["agent"]["name"] == "Juno"
    assert store.last_error


def test_reload_after_change(inputs_dir):
    import os
    teacher = inputs_dir / "agent_config.yaml"
    store = config_loader.ConfigStore(teacher, inputs_dir.parent / "defaults" / "agent_config.yaml")
    assert store.get()["agent"]["name"] == "Juno"
    teacher.write_text("agent:\n  name: Grace\n")
    stat = teacher.stat()
    os.utime(teacher, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**9))
    assert store.get()["agent"]["name"] == "Grace"


def test_legacy_models_key():
    config = config_loader.migrate_legacy_keys({"models": {"response": "gemma3:27b"}})
    assert config["llm"]["models"]["response"] == "gemma3:27b"


def test_validation_reports_unknown_category(inputs_dir):
    result = config_loader.validate_teacher_yaml(
        "interventions:\n  reactive:\n    rules:\n      - category: planning\n        hint: x\n",
        inputs_dir.parent / "defaults" / "agent_config.yaml",
    )
    assert any("planning" in w for w in result["warnings"])
    assert config_loader.validate_teacher_yaml("a: [")["errors"]


def test_fill_placeholders_keeps_unknown_and_json():
    text = 'Hi {agent_name} {unknown} {"reasoning": "x"}'
    assert config_loader.fill_placeholders(text, {"agent_name": "Juno"}) == 'Hi Juno {unknown} {"reasoning": "x"}'


def test_sample_fallback(monkeypatch, inputs_dir):
    monkeypatch.setattr(config_loader, "INPUTS_DIR", inputs_dir)
    assert config_loader.resolve_input("ta_system_prompt.txt").name == "ta_system_prompt.txt.sample"
    assert config_loader.resolve_input("./inputs/ta_system_prompt.txt").name == "ta_system_prompt.txt.sample"
    assert config_loader.resolve_input("../../etc/passwd") is None
    descs = config_loader.load_text_dir("assignment_descriptions")
    assert "Task" in descs
    (inputs_dir / "assignment_descriptions" / "Task.txt").write_text("Real task")
    assert config_loader.load_text_dir("assignment_descriptions")["Task"] == "Real task"
