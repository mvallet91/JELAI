import sqlite3
import json
import logging
import os
import time
import copy
from typing import Dict, Any

from config_loader import section

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - LEARNER_MODEL - %(message)s')
DATABASE_FILE = os.getenv("DATABASE_FILE", "/app/chat_histories/chat_history.db")

DEFAULT_LEARNER_MODEL = {
    "knowledge": {
        "data_loading": {"score": 0.0, "confidence": 0.0},
        "data_exploration": {"score": 0.0, "confidence": 0.0},
        "data_manipulation": {"score": 0.0, "confidence": 0.0},
        "visualization": {"score": 0.0, "confidence": 0.0},
        "data_interpretation": {"score": 0.0, "confidence": 0.0, "llm_evaluated": False}
    },
    "metacognition": {
        "state": "Unknown",
        "total_errors": 0,
        "time_since_last_help": 0,
        "code_to_writing_ratio": 0.0
    },
    "affect": {
        "state": "Neutral",
        "frustration_score": 0.0
    }
}

def get_learner_model(student_id: str, db_path: str = DATABASE_FILE) -> Dict[str, Any]:
    """Retrieve the learner model for a student, returning default if none exists."""
    try:
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT profile_data FROM learner_models WHERE student_id = ?", (student_id,))
            row = c.fetchone()
            if row:
                return json.loads(row[0])
    except Exception as e:
        logging.error(f"Error fetching learner model for {student_id}: {e}")
    return copy.deepcopy(DEFAULT_LEARNER_MODEL)

def save_learner_model(student_id: str, profile_data: Dict[str, Any], last_llm_eval: float = 0.0, db_path: str = DATABASE_FILE):
    """Save the learner model state to the database."""
    try:
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO learner_models (student_id, profile_data, last_updated, last_llm_eval) VALUES (?, ?, ?, ?)",
                (student_id, json.dumps(profile_data), time.time(), last_llm_eval)
            )
            conn.commit()
    except Exception as e:
        logging.error(f"Error saving learner model for {student_id}: {e}")

def update_rule_based_state(student_id: str, canvas: Dict[str, Any], db_path: str = DATABASE_FILE) -> Dict[str, Any]:
    """Update learner model based on raw activity canvas (rule-based). runs instantly.

    The knowledge components and the thresholds come from the section
    ``identification`` of agent_config.yaml.
    """
    model = get_learner_model(student_id, db_path)
    identification = section("identification")
    thresholds = identification.get("learner_states") or {}

    # 1. Update Knowledge (Rule-based)
    jupyter = canvas.get("jupyter", {})
    concepts = set(jupyter.get("concepts_used", []))
    errors = jupyter.get("errors", 0)
    successes = jupyter.get("successful_executions", 0)

    for kc_name, kc in (identification.get("knowledge_components") or {}).items():
        if not isinstance(kc, dict) or not concepts.intersection(kc.get("concepts") or []):
            continue
        entry = model["knowledge"].setdefault(kc_name, {"score": 0.0, "confidence": 0.0})
        step = float(kc.get("step", 0.1))
        entry["score"] = min(1.0, entry.get("score", 0.0) + step)
        entry["confidence"] = min(1.0, entry.get("confidence", 0.0) + step / 2)

    # 2. Update Metacognition (SRL)
    model["metacognition"]["total_errors"] = errors
    # Check most severe states first to avoid masking by weaker conditions
    if errors >= thresholds.get("trial_and_error_min_errors", 5):
        model["metacognition"]["state"] = "Trial and Error"
    elif errors >= thresholds.get("help_avoidant_min_errors", 4) and canvas.get("chat", {}).get("questions_asked", 0) == 0:
        model["metacognition"]["state"] = "Help Avoidant"
    elif successes > 0 and canvas.get("etherpad", {}).get("word_count", 0) >= thresholds.get("reflective_min_pad_words", 21):
        model["metacognition"]["state"] = "Reflective"
    else:
        model["metacognition"]["state"] = "Exploring"

    # 3. Update Affect
    flow_min = thresholds.get("flow_min_successes", 3)
    if errors >= thresholds.get("frustrated_min_errors", 5):
        model["affect"]["frustration_score"] = min(1.0, model["affect"]["frustration_score"] + 0.2)
        model["affect"]["state"] = "Frustrated"
    elif successes > flow_min and model["affect"]["frustration_score"] > 0:
        model["affect"]["frustration_score"] = max(0.0, model["affect"]["frustration_score"] - 0.2)
        model["affect"]["state"] = "Recovered / Flow"
    elif successes >= flow_min:
        model["affect"]["state"] = "Flow"

    save_learner_model(student_id, model, db_path=db_path)
    return model

def get_last_llm_eval_time(student_id: str, db_path: str = DATABASE_FILE) -> float:
    try:
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT last_llm_eval FROM learner_models WHERE student_id = ?", (student_id,))
            row = c.fetchone()
            if row:
                return row[0]
    except Exception:
        pass
    return 0.0
