"""Classification of student messages and selection of reactive interventions.

The rules come from the sections ``classification`` and ``interventions``
of agent_config.yaml. The functions here do not call the database, so it
is easy to test them.
"""

import logging
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional

from config_loader import fill_placeholders, read_input

logger = logging.getLogger("jelai.pedagogy")


def category_names(classification_cfg: Dict[str, Any]) -> List[str]:
    names = []
    for item in classification_cfg.get("categories") or []:
        name = item.get("name") if isinstance(item, dict) else item
        if name:
            names.append(str(name).strip().lower())
    return names


def default_category(classification_cfg: Dict[str, Any]) -> str:
    names = category_names(classification_cfg)
    value = str(classification_cfg.get("default_category") or "").strip().lower()
    if value:
        return value
    return names[-1] if names else "other"


def build_classification_prompt(classification_cfg: Dict[str, Any], values: Dict[str, Any]) -> str:
    """Return the system prompt for classification, with the categories filled in."""
    prompt = ""
    if classification_cfg.get("prompt_file"):
        prompt = read_input(classification_cfg["prompt_file"])
    if not prompt:
        prompt = classification_cfg.get("prompt") or ""

    lines = []
    for item in classification_cfg.get("categories") or []:
        if isinstance(item, dict):
            desc = item.get("description")
            lines.append(f"- {item.get('name')}: {desc}" if desc else f"- {item.get('name')}")
        else:
            lines.append(f"- {item}")
    categories_text = "\n".join(lines)

    names = category_names(classification_cfg)
    if "{categories}" not in prompt:
        prompt = prompt.rstrip() + f"\n\nCategories:\n{categories_text}" if prompt else f"Categories:\n{categories_text}"
    prompt = fill_placeholders(prompt, dict(values, categories=categories_text))
    prompt += f"\n\nReply with exactly one of: {', '.join(names)}."
    return prompt


def parse_category(raw: str, classification_cfg: Dict[str, Any]) -> str:
    """Map the LLM reply to a category name.

    The reply can contain other words. An exact match wins; else the first
    category name that occurs as a word in the reply is used.
    """
    names = category_names(classification_cfg)
    fallback = default_category(classification_cfg)
    if not raw:
        return fallback
    text = raw.strip().lower()
    # Remove the reasoning block of some models.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    cleaned = text.strip(" \t\n\"'`*.:;!")
    if cleaned in names:
        return cleaned
    positions = []
    for name in names:
        match = re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text)
        if match:
            positions.append((match.start(), name))
    if positions:
        return min(positions)[1]
    logger.warning("Classification reply '%s' does not match a category. Using '%s'.", raw[:80], fallback)
    return fallback


async def classify_message(
    text: str,
    classification_cfg: Dict[str, Any],
    llm: Callable[..., Awaitable[str]],
    values: Optional[Dict[str, Any]] = None,
) -> str:
    """Classify one student message. ``llm(messages)`` sends the request."""
    if not classification_cfg.get("enabled", True):
        return default_category(classification_cfg)
    messages = [
        {"role": "system", "content": build_classification_prompt(classification_cfg, values or {})},
        {"role": "user", "content": f"Classify: {text}"},
    ]
    try:
        raw = await llm(messages)
    except Exception as e:
        logger.error("Classification failed: %s", e)
        return default_category(classification_cfg)
    return parse_category(raw, classification_cfg)


def next_streak(category: str, previous_category: Optional[str], previous_streak: int) -> int:
    """Return the number of consecutive messages in ``category``, this one included."""
    if previous_category and category == previous_category:
        return max(previous_streak, 0) + 1
    return 1


def rule_matches(rule: Dict[str, Any], category: str, previous_category: Optional[str], streak: int) -> bool:
    if str(rule.get("category", "")).lower() != category:
        return False
    if "previous_category" in rule and rule["previous_category"] is not None:
        if str(rule["previous_category"]).lower() != (previous_category or ""):
            return False
    if "streak" in rule and rule["streak"] is not None and int(rule["streak"]) != streak:
        return False
    if "min_streak" in rule and rule["min_streak"] is not None and streak < int(rule["min_streak"]):
        return False
    return True


def select_reactive_hint(
    interventions_cfg: Dict[str, Any],
    category: str,
    previous_category: Optional[str],
    streak: int,
    values: Dict[str, Any],
) -> Optional[Dict[str, str]]:
    """Return {"name", "hint"} of the first matching rule, or None."""
    reactive = interventions_cfg.get("reactive") or {}
    if not reactive.get("enabled", True):
        return None
    for rule in reactive.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        if rule_matches(rule, category, previous_category, streak):
            hint = fill_placeholders(str(rule.get("hint", "")).strip(), values)
            if hint:
                return {"name": str(rule.get("name") or "unnamed rule"), "hint": hint}
    return None


def example_values(profile: Dict[str, Any], categories: List[str]) -> Dict[str, Any]:
    """Return {last_<category>_example: text} for all categories."""
    examples = profile.get("last_examples") or {}
    values = {}
    for name in categories:
        key = f"last_{re.sub(r'[^a-z0-9]+', '_', name)}_example"
        values[key] = examples.get(name) or profile.get(key) or "your previous question"
    return values


def update_profile(
    profile: Dict[str, Any],
    category: str,
    streak: int,
    question_text: str,
    timestamp: float,
    classification_cfg: Dict[str, Any],
    interventions_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    """Return the profile with the counts, streak, example and flag updated."""
    profile = dict(profile)
    counts = dict(profile.get("category_counts") or {})
    counts[category] = counts.get(category, 0) + 1
    profile["category_counts"] = counts
    profile["total_questions"] = profile.get("total_questions", 0) + 1

    examples = dict(profile.get("last_examples") or {})
    examples[category] = question_text[:500] + ("..." if len(question_text) > 500 else "")
    profile["last_examples"] = examples

    profile["last_question_classification"] = category
    profile["category_streak"] = streak
    profile["last_interaction_timestamp"] = timestamp

    # Fields of earlier versions, which the dashboard and analyses use.
    for name in ("instrumental", "executive"):
        profile[f"{name}_count"] = counts.get(name, 0)
        profile[f"last_{name}_example"] = examples.get(name)
    profile["other_count"] = sum(v for k, v in counts.items() if k not in ("instrumental", "executive"))
    profile["consecutive_executive_count"] = streak if category == "executive" else 0

    flag_cfg = interventions_cfg.get("needs_guidance") or {}
    flag_category = str(flag_cfg.get("category") or "").lower()
    if flag_category:
        fallback = default_category(classification_cfg)
        counted = sum(v for k, v in counts.items() if k != fallback)
        share = counts.get(flag_category, 0) / counted if counted else 0.0
        profile["needs_guidance_flag"] = bool(
            counted >= int(flag_cfg.get("min_questions", 6)) and share > float(flag_cfg.get("min_ratio", 0.6))
        )
    return profile
