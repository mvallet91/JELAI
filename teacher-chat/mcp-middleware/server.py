"""
MCP Middleware Server for JELAI Teacher Chat.
Provides tools to query ClickHouse and perform semantic search.
Uses the mcp[cli] Python SDK.
"""

import os
import httpx
import clickhouse_connect
from mcp.server.fastmcp import FastMCP

# --- Config ---
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_DB = os.getenv("CLICKHOUSE_DB", "teacher_analytics")

OLLAMA_URL = os.getenv("OLLAMA_URL", "https://llm.learn.ewi.tudelft.nl")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3:latest")

mcp = FastMCP("teacher-analytics", host="0.0.0.0", port=8005)

# Global ClickHouse client
_ch_client = None

def get_db():
    global _ch_client
    if _ch_client is None:
        _ch_client = clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            database=CLICKHOUSE_DB
        )
    return _ch_client

def get_embedding(text: str) -> list[float]:
    url = f"{OLLAMA_URL.rstrip('/')}/api/embed"
    payload = {"model": EMBEDDING_MODEL, "input": text}
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("embeddings", [[]])[0]
    except Exception as e:
        return []

@mcp.tool()
def get_dataset_stats() -> str:
    """Returns basic counts of total events, unique students, and tasks in the dataset."""
    db = get_db()
    total = db.query("SELECT count() FROM events").result_rows[0][0]
    students = db.query("SELECT count(distinct student_id) FROM events").result_rows[0][0]
    tasks = db.query("SELECT count(distinct task_label) FROM events").result_rows[0][0]
    
    return f"Dataset Statistics:\n- Total Events: {total}\n- Unique Students: {students}\n- Total Tasks: {tasks}"

@mcp.tool()
def get_student_summary(student_id: str) -> str:
    """
    Get a high-level summary of a specific student's activity.
    Args:
        student_id: The ID of the student (e.g. "S01C", "S15T").
    """
    db = get_db()
    
    # Check if student exists
    exists = db.query(f"SELECT count() FROM events WHERE student_id = '{student_id}'").result_rows[0][0]
    if exists == 0:
        return f"No data found for student {student_id}"

    # Get event breakdown
    ev_counts = db.query(f"""
        SELECT event, count() as cnt 
        FROM events 
        WHERE student_id = '{student_id}' 
        GROUP BY event 
        ORDER BY cnt DESC
    """)
    
    ev_str = "\n".join([f"  - {row[0]}: {row[1]}" for row in ev_counts.result_rows])
    
    # Get errors encountered
    errors = db.query(f"""
        SELECT task_label, error, count() as occurences
        FROM events
        WHERE student_id = '{student_id}' AND error != ''
        GROUP BY task_label, error
        ORDER BY occurences DESC
        LIMIT 5
    """)
    
    err_str = "None"
    if errors.result_rows:
        err_str = "\n".join([f"  - ({row[0]}) {row[1]} (x{row[2]})" for row in errors.result_rows])

    return f"""
Activity Summary for {student_id}:
Event Breakdown:
{ev_str}

Top Errors Encountered:
{err_str}
"""

@mcp.tool()
def search_events(student_id: str = "", task_label: str = "", event_type: str = "", limit: int = 20) -> str:
    """
    Search chronological logs of exact events matching the given criteria.
    Args:
        student_id: Optional student ID to filter by
        task_label: Optional task label to filter by (e.g. 'Task1', 'Task2')
        event_type: Optional event type to filter by (e.g. 'Edited cell', 'Executed cells with error')
        limit: Max number of events to return
    """
    db = get_db()
    
    conditions = []
    if student_id: conditions.append(f"student_id = '{student_id}'")
    if task_label: conditions.append(f"task_label = '{task_label}'")
    if event_type: conditions.append(f"event = '{event_type}'")
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    query = f"""
        SELECT 
            time, 
            student_id, 
            task_label, 
            event, 
            content,
            error,
            message_text
        FROM events
        WHERE {where_clause}
        ORDER BY time ASC
        LIMIT {limit}
    """
    
    results = db.query(query).result_rows
    
    if not results:
        return "No matching events found."
        
    out = []
    for r in results:
        time = r[0]
        s_id = r[1]
        t_lbl = r[2]
        evt = r[3]
        
        detail = ""
        if r[4]: detail += f" | Code: {r[4][:100]}..."
        if r[5]: detail += f" | Error: {r[5][:100]}..."
        if r[6]: detail += f" | Msg: {r[6]}"
            
        out.append(f"[{time}] {s_id} - {t_lbl} - {evt}{detail}")
        
    return "\n".join(out)

@mcp.tool()
def semantic_search(query: str, limit: int = 15) -> str:
    """
    Perform semantic search on student code edits, chat messages, and errors based on the meaning of a query.
    Use this when searching for concepts (e.g. "student struggling with pandas syntax" or "questions about loops").
    
    Args:
        query: The natural language search query
        limit: Max number of results to return
    """
    q_vec = get_embedding(query)
    if not q_vec:
        return "Failed to generate embedding for the query. Ollama might be unavailable."
        
    db = get_db()
    
    # Cosine distance semantic search
    sql = f"""
        SELECT 
            student_id,
            task_label,
            event,
            content,
            error,
            message_text,
            cosineDistance(vector_embedding, {q_vec}) as distance
        FROM events
        WHERE length(vector_embedding) > 0
        ORDER BY distance ASC
        LIMIT {limit}
    """
    
    try:
        results = db.query(sql).result_rows
        
        if not results:
            return "No semantic search results found."
            
        out = []
        for r in results:
            s_id = r[0]
            t_lbl = r[1]
            evt = r[2]
            dist = r[6]
            
            detail = ""
            if r[3]: detail += f" | Code: {r[3]}"
            if r[4]: detail += f" | Error: {r[4]}"
            if r[5]: detail += f" | Msg: {r[5]}"
                
            out.append(f"(Dist: {dist:.3f}) {s_id} - {t_lbl} - {evt}{detail}")
            
        return "\n\n".join(out)
        
    except Exception as e:
        return f"Vector search error: {str(e)}"

# The app entrypoint for FastMCP is handled by the MCP CLI
# Run with: mcp run server.py
