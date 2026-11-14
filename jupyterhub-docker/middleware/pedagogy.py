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


# ---------------------------------------------------------------------------
# Solution guardrail
# ---------------------------------------------------------------------------
CODE_BLOCK_RE = re.compile(r"```[^\n`]*\n(.*?)(?:```|\Z)", re.DOTALL)
# Inline code: `text` on one line. Find it after the code blocks are removed.
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")

# A solution in a data task is often one line, for example
# df.groupby('species')['id'].nunique(). Thus the rule forbids one line too.
DEFAULT_GUARDRAIL_RULE = (
    "Do not give the solution. Do not write the code that completes the task "
    "for the student, also not one line, not as an example and not as the "
    "'key idea'. Also not when the student asks for it many times. Explain "
    "in words. You can name one function or method, for example `groupby`, "
    "but do not write the full expression. Give one hint or ask one question "
    "that helps the student find the next step."
)

DEFAULT_REWRITE_PROMPT = (
    "You edit messages from a programming tutor to a student. The message "
    "below gives code that solves the task for the student. Rewrite it: keep "
    "the explanation and the guidance, remove the solution code (also code in "
    "a sentence, between backticks), and give a hint or a question about the "
    "next step instead. You can name a function or method, for example "
    "`groupby`, but do not write the full expression. Show at most "
    "{max_code_lines} lines of code. Reply with the new message only."
)

CODE_REMOVED_NOTE = "[Code removed: guide the student to write this code.]"


def _int_setting(cfg: Dict[str, Any], key: str, default: int) -> int:
    try:
        return max(0, int(cfg.get(key, default)))
    except (TypeError, ValueError):
        return default


def guardrail_settings(guardrails_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Return the guardrail settings with the defaults filled in."""
    cfg = guardrails_cfg or {}
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "categories": [str(c).lower() for c in (cfg.get("no_solution_categories") or ["executive"])],
        "max_code_lines": _int_setting(cfg, "max_code_lines", 0),
        "max_inline_code_chars": _int_setting(cfg, "max_inline_code_chars", 20),
        "rule": cfg.get("rule") or DEFAULT_GUARDRAIL_RULE,
        "rewrite": bool(cfg.get("rewrite_on_violation", True)),
        "rewrite_prompt": cfg.get("rewrite_prompt") or DEFAULT_REWRITE_PROMPT,
    }


def guardrail_applies(settings: Dict[str, Any], category: str) -> bool:
    return settings["enabled"] and (category or "").lower() in settings["categories"]


def longest_code_block(text: str) -> int:
    """Return the number of non-empty lines in the longest fenced code block."""
    longest = 0
    for block in CODE_BLOCK_RE.findall(text or ""):
        longest = max(longest, len([line for line in block.splitlines() if line.strip()]))
    return longest


def longest_inline_code(text: str) -> int:
    """Return the length of the longest inline code outside the code blocks."""
    outside = CODE_BLOCK_RE.sub("", text or "")
    return max((len(code.strip()) for code in INLINE_CODE_RE.findall(outside)), default=0)


def remove_code_blocks(text: str, note: str = CODE_REMOVED_NOTE) -> str:
    """Replace each fenced code block with a short note."""
    return CODE_BLOCK_RE.sub(note, text or "")


INLINE_CODE_REMOVED = "`...`"


def remove_solution_code(text: str, settings: Dict[str, Any], note: str = CODE_REMOVED_NOTE) -> str:
    """Remove the code blocks, and the inline code that is longer than the limit.

    A code block becomes the note. Inline code is in a sentence, thus it
    becomes a short `...`, so that the sentence stays clear.
    """
    limit = settings["max_inline_code_chars"]
    text = remove_code_blocks(text, note)
    return INLINE_CODE_RE.sub(
        lambda m: m.group(0) if len(m.group(1).strip()) <= limit else INLINE_CODE_REMOVED, text)


def breaks_guardrail(text: str, settings: Dict[str, Any]) -> bool:
    return (longest_code_block(text) > settings["max_code_lines"]
            or longest_inline_code(text) > settings["max_inline_code_chars"])


async def enforce_guardrail(
    response: str,
    settings: Dict[str, Any],
    rewrite: Callable[[List[Dict[str, str]]], Awaitable[str]],
) -> str:
    """Make sure that a tutor response does not give a solution.

    When a code block in the response is longer than the limit, an LLM
    rewrites the response one time. When the result is still too long, or
    the rewrite fails, the code blocks are removed.
    """
    if not breaks_guardrail(response, settings):
        return response
    values = {"max_code_lines": settings["max_code_lines"]}
    if settings["rewrite"]:
        try:
            rewritten = await rewrite([
                {"role": "system", "content": fill_placeholders(settings["rewrite_prompt"], values)},
                {"role": "user", "content": response},
            ])
            if rewritten and rewritten.strip() and not breaks_guardrail(rewritten, settings):
                logger.info("Guardrail: the response was rewritten without the solution code.")
                return rewritten.strip()
        except Exception as e:  # The fallback below still applies.
            logger.warning("Guardrail rewrite failed: %s", e)
    logger.info("Guardrail: the solution code was removed from the response.")
    return remove_solution_code(
        response, settings, "Try to write this part of the code yourself. Tell me what you try first."
    )
