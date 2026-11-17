"""Load the teacher configuration (agent_config.yaml) and the input files.

The teacher file is merged over the default file that is part of the
image. The teacher file can therefore contain only the keys that change.
The configuration is read again when the file changes on disk.
"""

import copy
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger("jelai.config")

APP_DIR = Path(__file__).parent
INPUTS_DIR = Path(os.getenv("JELAI_INPUTS_DIR", APP_DIR / "inputs"))
CONFIG_FILE = Path(os.getenv("AGENT_CONFIG_FILE", INPUTS_DIR / "agent_config.yaml"))
DEFAULT_CONFIG_FILE = Path(os.getenv("AGENT_CONFIG_DEFAULTS", APP_DIR / "defaults" / "agent_config.yaml"))

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Merge ``override`` into a copy of ``base``. Lists are replaced, not merged."""
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _read_yaml(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping at the top level.")
    return data


class ConfigStore:
    """Cache of the merged configuration. It reloads when a file changes."""

    def __init__(self, config_file: Path = CONFIG_FILE, default_file: Path = DEFAULT_CONFIG_FILE):
        self.config_file = Path(config_file)
        self.default_file = Path(default_file)
        self._stamp = None
        self._config: Dict[str, Any] = {}
        self.last_error: Optional[str] = None

    def _current_stamp(self):
        stamps = []
        for path in (self.default_file, self.config_file):
            try:
                stamps.append(path.stat().st_mtime_ns)
            except OSError:
                stamps.append(None)
        return tuple(stamps)

    def get(self) -> Dict[str, Any]:
        stamp = self._current_stamp()
        if stamp != self._stamp:
            self._load()
            self._stamp = stamp
        return self._config

    def _load(self):
        defaults: Dict[str, Any] = {}
        if self.default_file.exists():
            try:
                defaults = _read_yaml(self.default_file)
            except Exception as e:
                logger.error("Could not read the default configuration %s: %s", self.default_file, e)
        teacher: Dict[str, Any] = {}
        self.last_error = None
        if self.config_file.exists() and self.config_file.resolve() != self.default_file.resolve():
            try:
                teacher = _read_yaml(self.config_file)
            except Exception as e:
                # Keep the tutor running with the defaults and show the error to the teacher.
                self.last_error = f"{self.config_file.name}: {e}"
                logger.error("Could not read %s, using the defaults: %s", self.config_file, e)
        self._config = migrate_legacy_keys(deep_merge(defaults, teacher))
        logger.info("Loaded the agent configuration (%s).", self.config_file)


def migrate_legacy_keys(config: Dict[str, Any]) -> Dict[str, Any]:
    """Accept keys from earlier versions of agent_config.yaml."""
    # Earlier versions had "models" at the top level.
    legacy_models = config.get("models")
    if isinstance(legacy_models, dict):
        models = config.setdefault("llm", {}).setdefault("models", {})
        for role, name in legacy_models.items():
            if name and not models.get(role):
                models[role] = name
    # Earlier versions had "concept_patterns" at the top level.
    if config.get("concept_patterns") and isinstance(config.get("identification"), dict):
        config["identification"]["concept_patterns"] = config["concept_patterns"]
    return config


_store = ConfigStore()


def get_config() -> Dict[str, Any]:
    """Return the current merged configuration."""
    return _store.get()


def config_error() -> Optional[str]:
    """Return the last error from the teacher file, or None."""
    _store.get()
    return _store.last_error


def section(name: str) -> Dict[str, Any]:
    value = get_config().get(name)
    return value if isinstance(value, dict) else {}


def agent_name() -> str:
    return section("agent").get("name") or "Juno"


def model_override(role: str) -> Optional[str]:
    """Return the model that the teacher set for a role, or None."""
    models = section("llm").get("models") or {}
    value = models.get(role) if isinstance(models, dict) else None
    return value or None


def fill_placeholders(text: str, values: Dict[str, Any]) -> str:
    """Replace {name} with values[name]. Unknown placeholders stay as they are."""
    if not text:
        return ""

    def replace(match):
        key = match.group(1)
        if key in values and values[key] is not None:
            return str(values[key])
        return match.group(0)

    return _PLACEHOLDER.sub(replace, text)


def resolve_input(relative: str) -> Optional[Path]:
    """Return the path of an input file, or of its '.sample' file, or None."""
    if not relative:
        return None
    # Earlier versions gave paths relative to the app directory ("./inputs/x.txt").
    for prefix in ("./inputs/", "inputs/"):
        if relative.startswith(prefix):
            relative = relative[len(prefix):]
    path = Path(relative)
    if not path.is_absolute():
        path = INPUTS_DIR / path
    path = path.resolve()
    # Only files in the inputs directory are allowed.
    if INPUTS_DIR.resolve() not in path.parents:
        logger.warning("Input file %s is not in %s. It is ignored.", relative, INPUTS_DIR)
        return None
    if path.is_file():
        return path
    sample = path.with_name(path.name + ".sample")
    if sample.is_file():
        return sample
    return None


def read_input(relative: str, default: str = "") -> str:
    path = resolve_input(relative)
    if path is None:
        return default
    try:
        text = path.read_text(encoding="utf-8").strip()
        return text or default
    except OSError as e:
        logger.error("Could not read %s: %s", path, e)
        return default


def load_text_dir(name: str, as_lines: bool = False) -> Dict[str, Any]:
    """Load all '*.txt' files of an inputs subdirectory, keyed by file stem.

    When the directory has no '*.txt' file for a stem, the '*.txt.sample'
    file is used.
    """
    directory = INPUTS_DIR / name
    result: Dict[str, Any] = {}
    if not directory.is_dir():
        return result
    files = {}
    for path in sorted(directory.glob("*.txt.sample")):
        files[path.name[: -len(".txt.sample")]] = path
    for path in sorted(directory.glob("*.txt")):
        files[path.stem] = path
    for key, path in files.items():
        text = path.read_text(encoding="utf-8")
        result[key] = [line.strip() for line in text.splitlines() if line.strip()] if as_lines else text.strip()
    return result


def validate_config(config: Dict[str, Any]) -> Dict[str, list]:
    """Check a configuration. Return {"errors": [...], "warnings": [...]}.

    The configuration is the teacher file merged over the defaults.
    """
    errors, warnings = [], []
    classification = config.get("classification") or {}
    names = []
    for item in classification.get("categories") or []:
        name = item.get("name") if isinstance(item, dict) else item
        if not name:
            errors.append("classification.categories: each category must have a name.")
        else:
            names.append(str(name).strip().lower())
    if not names:
        errors.append("classification.categories: add at least one category.")
    if len(set(names)) != len(names):
        errors.append("classification.categories: the names must be different.")
    default = str(classification.get("default_category") or "").lower()
    if default and names and default not in names:
        warnings.append(f"classification.default_category '{default}' is not in the categories.")

    reactive = (config.get("interventions") or {}).get("reactive") or {}
    for index, rule in enumerate(reactive.get("rules") or []):
        label = f"interventions.reactive.rules[{index}]"
        if not isinstance(rule, dict):
            errors.append(f"{label}: a rule must be a mapping.")
            continue
        for key in ("category", "previous_category"):
            value = rule.get(key)
            if value and names and str(value).lower() not in names:
                warnings.append(f"{label}: {key} '{value}' is not in the categories.")
        if not rule.get("category"):
            errors.append(f"{label}: 'category' is necessary.")
        if not str(rule.get("hint") or "").strip():
            errors.append(f"{label}: 'hint' is necessary.")
        for key in ("streak", "min_streak"):
            if key in rule and rule[key] is not None:
                try:
                    if int(rule[key]) < 1:
                        raise ValueError
                except (TypeError, ValueError):
                    errors.append(f"{label}: '{key}' must be a number of 1 or more.")

    proactivity = config.get("proactivity") or {}
    for key in ("min_cooldown_seconds", "max_unanswered_interventions", "poll_interval_active",
                "poll_interval_idle", "idle_threshold_seconds"):
        if key in proactivity and not isinstance(proactivity[key], (int, float)):
            errors.append(f"proactivity.{key} must be a number.")
    if proactivity.get("enabled", True) and "{" not in str(proactivity.get("system_prompt", "{")):
        warnings.append("proactivity.system_prompt does not ask for the JSON reply format.")

    for item in (config.get("identification") or {}).get("concept_patterns") or []:
        if not isinstance(item, dict) or not item.get("label") or not isinstance(item.get("patterns"), list):
            errors.append("identification.concept_patterns: each entry needs 'label' and a list 'patterns'.")
            break
    return {"errors": errors, "warnings": warnings}


def validate_teacher_yaml(text: str, defaults_file: Path = DEFAULT_CONFIG_FILE) -> Dict[str, list]:
    """Parse the text of agent_config.yaml and validate it with the defaults."""
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        return {"errors": [f"YAML syntax error: {e}"], "warnings": []}
    if not isinstance(data, dict):
        return {"errors": ["The file must contain a YAML mapping at the top level."], "warnings": []}
    defaults = {}
    if Path(defaults_file).exists():
        try:
            defaults = _read_yaml(Path(defaults_file))
        except Exception:
            defaults = {}
    return validate_config(migrate_legacy_keys(deep_merge(defaults, data)))
