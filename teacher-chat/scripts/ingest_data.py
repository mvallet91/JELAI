"""
Data Ingestion Script for 4TU Dataset.
Reads anonymized logs, hits Ollama for embeddings, and inserts into ClickHouse.

Usage: docker exec mcp-middleware python /app/scripts/ingest_data.py
"""

import os
import json
import httpx
import logging
from pathlib import Path
from typing import List, Dict, Any

import clickhouse_connect

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Configuration ---
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_DB = os.getenv("CLICKHOUSE_DB", "teacher_analytics")

OLLAMA_URL = os.getenv("OLLAMA_URL", "https://llm.learn.ewi.tudelft.nl")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3:latest") 

BATCH_SIZE = 500

# Mount path inside the container
# We will mount the host datasets directory to /app/datasets in docker-compose
DATA_ROOT = Path("/app/datasets/anonymized_logs/anonymized_logs")


def get_embedding(text: str) -> List[float]:
    """Call Ollama for the text embedding."""
    if not text or not text.strip():
        return []
    
    url = f"{OLLAMA_URL.rstrip('/')}/api/embed"
    payload = {
        "model": EMBEDDING_MODEL,
        "input": text
    }
    
    try:
        # 30s timeout for dense code embeddings
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("embeddings", [[]])[0]
    except Exception as e:
        logger.error(f"Failed to get embedding for text (length {len(text)}): {e}")
        return []

def extract_text_to_embed(event: Dict[str, Any]) -> str:
    """Determine what text (if any) to embed based on the event."""
    text_parts = []
    
    event_type = event.get("event")
    
    if event_type in ["question_instrumental", "question_executive", "question_other", "juno_response"]:
        text_parts.append(event.get("message_text", ""))
        
    elif event_type == "Edited cell":
        text_parts.append(event.get("content", ""))
        
    elif event_type == "Executed cells with error":
        # Often helpful to embed the code that caused the error AND the error stacktrace
        content = event.get("content", "")
        error = event.get("error", "")
        if content: text_parts.append(f"Code: {content}")
        if error: text_parts.append(f"Error: {error}")
        
    combined = " ".join([str(p) for p in text_parts if p]).strip()
    return combined

def ingest_all():
    logger.info("Connecting to ClickHouse...")
    client = clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST, 
        port=CLICKHOUSE_PORT,
        database=CLICKHOUSE_DB
    )
    
    if not DATA_ROOT.exists() or not DATA_ROOT.is_dir():
        logger.error(f"Data root {DATA_ROOT} does not exist. Ensure volume is mounted.")
        return

    # List all S01C... S20T folders
    student_dirs = [d for d in DATA_ROOT.iterdir() if d.is_dir() and (d.name.startswith("S") and len(d.name) == 4)]
    logger.info(f"Found {len(student_dirs)} student directories to process.")
    
    columns = [
        "event", "time", "student_id", "task_label", "cell_index", 
        "content", "input", "output", "error", 
        "message_type", "message_text", "message_classification", 
        "experiment_assignment", "classifier_v6_intent", "classifier_v6_phase",
        "experiment_group", "source_file", "vector_embedding"
    ]
    
    batch_data = []
    total_inserted = 0
    total_embedded = 0
    
    for s_dir in student_dirs:
        student_id = s_dir.name
        # 'C' means control, 'T' means treatment
        exp_group = "control" if student_id.endswith("C") else "treatment"
        
        for task_file in s_dir.glob("*.json"):
            logger.info(f"Processing {task_file.relative_to(DATA_ROOT)}...")
            try:
                with open(task_file, "r", encoding="utf-8") as f:
                    events = json.load(f)
            except Exception as e:
                logger.error(f"Error reading {task_file}: {e}")
                continue
                
            for e in events:
                # 1. Base fields mapping
                row = [
                    e.get("event") or "",
                    e.get("time") or 0,
                    e.get("student_id") or student_id,
                    e.get("task_label") or task_file.stem,
                    e.get("cell_index", None),
                    e.get("content", None),
                    e.get("input", None),
                    e.get("output", None),
                    e.get("error", None),
                    e.get("message_type", None),
                    e.get("message_text", None),
                    e.get("message_classification", None),
                    e.get("experiment_assignment", None),
                    e.get("classifier_v6_intent", None),
                    e.get("classifier_v6_phase", None),
                    exp_group,
                    f"{student_id}/{task_file.name}",
                ]
                
                # 2. Extract and fetch semantic embeddings
                text_to_embed = extract_text_to_embed(e)
                vector = []
                if text_to_embed:
                    # Note: This is a synchronous call per event. In a massive production dataset 
                    # we'd do async batching, but for ~120 students tasks this is acceptable.
                    vector = get_embedding(text_to_embed)
                    if vector:
                        total_embedded += 1

                row.append(vector)
                batch_data.append(row)
                
                # 3. Insert in batches
                if len(batch_data) >= BATCH_SIZE:
                    client.insert("events", batch_data, column_names=columns)
                    total_inserted += len(batch_data)
                    logger.info(f"Inserted {total_inserted} events so far... (Embedded: {total_embedded})")
                    batch_data = []
                    
    # Insert any remaining rows
    if batch_data:
        client.insert("events", batch_data, column_names=columns)
        total_inserted += len(batch_data)
        
    logger.info(f"Ingestion complete. Total events inserted: {total_inserted}. Total embeddings generated: {total_embedded}.")

if __name__ == "__main__":
    ingest_all()
