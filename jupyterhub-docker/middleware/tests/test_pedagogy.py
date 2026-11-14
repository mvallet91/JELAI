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


def test_learning_objective_fuzzy_fallback():
    from lo_matcher import LearningObjectiveMatcher
    matcher = LearningObjectiveMatcher()
    matcher.load()
    objectives = ["Make a bar plot", "Load data with pd.read_csv()", "Group data with groupby"]
    best, score = matcher.best_match("how do I read the csv data", objectives)
    assert best == "Load data with pd.read_csv()"
    assert 0 <= score <= 1
    assert matcher.best_match("x", []) == (None, 0.0)


def test_guardrail_detects_and_removes_long_code():
    settings = pedagogy.guardrail_settings({"max_code_lines": 2})
    short = "Try this:\n```python\ndf.head()\n```"
    long = "Here:\n```python\nimport pandas as pd\ndf = pd.read_csv('a.csv')\nprint(df.nunique())\n```\nDone."
    assert not pedagogy.breaks_guardrail(short, settings)
    assert pedagogy.breaks_guardrail(long, settings)
    assert "read_csv" not in pedagogy.remove_code_blocks(long)
    assert pedagogy.guardrail_applies(settings, "Executive")
    assert not pedagogy.guardrail_applies(settings, "instrumental")
    assert not pedagogy.guardrail_applies(pedagogy.guardrail_settings({"enabled": False}), "executive")


def test_enforce_guardrail_rewrites_then_falls_back():
    import asyncio
    settings = pedagogy.guardrail_settings({"max_code_lines": 1})
    long = "```python\na = 1\nb = 2\n```"

    async def good_rewrite(messages):
        return "What does groupby do?"

    async def bad_rewrite(messages):
        return long

    assert asyncio.run(pedagogy.enforce_guardrail("No code here.", settings, bad_rewrite)) == "No code here."
    assert asyncio.run(pedagogy.enforce_guardrail(long, settings, good_rewrite)) == "What does groupby do?"
    assert "a = 1" not in asyncio.run(pedagogy.enforce_guardrail(long, settings, bad_rewrite))


def test_guardrail_defaults_catch_a_one_line_solution():
    settings = pedagogy.guardrail_settings({})
    assert settings["max_code_lines"] == 0
    assert settings["max_inline_code_chars"] == 20
    block = "The key idea:\n```python\nsharks_df.groupby('species')['id'].nunique()\n```"
    inline = "Use `sharks_df.groupby('species')['id'].nunique()` for this."
    hint = "Look at `groupby` and `.nunique()` in the pandas documentation."
    assert pedagogy.breaks_guardrail(block, settings)
    assert pedagogy.breaks_guardrail(inline, settings)
    assert not pedagogy.breaks_guardrail(hint, settings)
    cleaned = pedagogy.remove_solution_code(inline + "\n" + block, settings)
    assert "nunique()" not in cleaned
    assert pedagogy.remove_solution_code(hint, settings) == hint


def test_enforce_guardrail_removes_inline_solution_when_rewrite_fails():
    import asyncio
    settings = pedagogy.guardrail_settings({})
    answer = "Write `df.groupby('species')['name'].nunique()` and run it."

    async def failing_rewrite(messages):
        raise RuntimeError("no LLM")

    result = asyncio.run(pedagogy.enforce_guardrail(answer, settings, failing_rewrite))
    assert "nunique" not in result
    assert result == "Write `...` and run it."
