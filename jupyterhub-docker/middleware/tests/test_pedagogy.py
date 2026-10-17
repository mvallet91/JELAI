import asyncio

import yaml

import config_loader
import pedagogy


def load_default_config():
    with open(config_loader.APP_DIR / "inputs" / "agent_config.yaml") as f:
        return yaml.safe_load(f)


CONFIG = load_default_config()
CLS = CONFIG["classification"]
INT = CONFIG["interventions"]


def test_default_config_is_valid():
    result = config_loader.validate_config(CONFIG)
    assert result["errors"] == []


def test_parse_category():
    assert pedagogy.parse_category("Executive.", CLS) == "executive"
    assert pedagogy.parse_category("**instrumental**", CLS) == "instrumental"
    assert pedagogy.parse_category("I think this is executive help-seeking", CLS) == "executive"
    assert pedagogy.parse_category("<think>maybe instrumental</think> other", CLS) == "other"
    assert pedagogy.parse_category("no idea", CLS) == "other"


def test_classification_prompt_contains_categories():
    prompt = pedagogy.build_classification_prompt(CLS, {})
    for name in ("instrumental", "executive", "other"):
        assert f"- {name}:" in prompt
    assert "{categories}" not in prompt


def test_classify_message_uses_llm():
    async def fake_llm(messages):
        assert messages[1]["content"] == "Classify: give me the code"
        return "executive"

    assert asyncio.run(pedagogy.classify_message("give me the code", CLS, fake_llm)) == "executive"


def test_classification_disabled_returns_default():
    async def fail(messages):
        raise AssertionError("must not be called")

    cfg = dict(CLS, enabled=False)
    assert asyncio.run(pedagogy.classify_message("x", cfg, fail)) == "other"


def hint_name(category, previous, streak, values=None):
    hint = pedagogy.select_reactive_hint(INT, category, previous, streak, values or {})
    return hint and hint["name"]


def test_default_rules_follow_the_executive_sequence():
    assert hint_name("instrumental", "executive", 1) == "Positive reinforcement"
    assert hint_name("instrumental", "instrumental", 2) == "Standard support"
    assert hint_name("executive", None, 1) == "First executive"
    assert hint_name("executive", "executive", 2) == "Second executive"
    assert hint_name("executive", "executive", 3) == "Third executive"
    assert hint_name("executive", "executive", 7) == "Fourth or more executive"
    assert hint_name("other", "executive", 1) is None


def test_hint_placeholders_are_filled():
    hint = pedagogy.select_reactive_hint(INT, "executive", "executive", 3,
                                         {"last_executive_example": "plot it for me"})
    assert "plot it for me" in hint["hint"]


def test_reactive_disabled():
    cfg = {"reactive": dict(INT["reactive"], enabled=False)}
    assert pedagogy.select_reactive_hint(cfg, "executive", None, 1, {}) is None


def test_streak():
    assert pedagogy.next_streak("executive", "executive", 2) == 3
    assert pedagogy.next_streak("executive", "instrumental", 5) == 1
    assert pedagogy.next_streak("executive", None, 0) == 1


def test_update_profile_counts_and_flag():
    profile = {}
    streak = 0
    previous = None
    for i in range(6):
        streak = pedagogy.next_streak("executive", previous, streak)
        profile = pedagogy.update_profile(profile, "executive", streak, f"q{i}", float(i), CLS, INT)
        previous = "executive"
    assert profile["category_counts"] == {"executive": 6}
    assert profile["executive_count"] == 6
    assert profile["consecutive_executive_count"] == 6
    assert profile["last_examples"]["executive"] == "q5"
    assert profile["needs_guidance_flag"] is True


def test_custom_categories():
    cls = {"categories": [{"name": "planning"}, {"name": "performance"}, {"name": "other"}],
           "default_category": "other", "prompt": "Classify by SRL phase."}
    rules = {"reactive": {"rules": [{"name": "Plan", "category": "planning", "hint": "Support {question}"}]}}
    assert pedagogy.parse_category("Planning", cls) == "planning"
    hint = pedagogy.select_reactive_hint(rules, "planning", None, 1, {"question": "my plan"})
    assert hint["hint"] == "Support my plan"
    assert "{last_planning_example}" not in str(pedagogy.example_values({}, ["planning"]))
