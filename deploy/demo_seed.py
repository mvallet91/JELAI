"""Add made-up students to the JELAI demo, so the teacher dashboard shows a class.

The script runs in the middleware container (deploy/demo-seed.sh starts it).
It writes the chat history, the activity logs and the Etherpad pads of eight
made-up students who work on Task 1 (the shark data). The times are relative
to now, so the students show as active, idle or away.

Usage (in the middleware container, working directory /app):
    python3 - add    < demo_seed.py   add the students (old seed data is replaced)
    python3 - remove < demo_seed.py   remove the students

The real demo account (demo-student) is not changed.
"""

import logging
import os
import sqlite3
import sys
import time
from datetime import datetime

logging.disable(logging.CRITICAL)  # The Etherpad request URL holds the API key.

from learning_story import (  # noqa: E402  (the middleware modules)
    DATABASE_FILE, ETHERPAD_API_KEY, ETHERPAD_URL, INGESTED_LOGS_DIR,
    _safe_name, pad_id_for, store_student_logs,
)

CHAT_FILE = "chats/Task1.chat"
NOTEBOOK = "Task1.ipynb"

LOAD = "import pandas as pd\nsharks_df = pd.read_csv('sharks.csv')"
SHAPE = "print(sharks_df.shape)"
INFO = "sharks_df.info()"
MISSING = "print(sharks_df['species'].isna().sum())"
COUNT = "shark_counts = sharks_df.groupby('species')['id'].nunique()\nprint(shark_counts)"
TOP = "print(shark_counts.nlargest(3))"

ANSWER = {
    "instrumental": "Good question. Look at the exact column names with `sharks_df.columns`. "
                    "What do you see, and how does it compare with the name in your code?",
    "executive": "Let us do this step by step. First group the rows by species. "
                 "Which pandas method counts the distinct values in each group?",
    "other": "Hi! I am Juno. Ask me when you are stuck, or when you want to check your idea.",
}

# Each student: minutes since the last activity, then a list of events.
# Event kinds: run (code, output), error (code, error), ask (text, category),
# nudge (text), pad (text).
STUDENTS = {
    "sara.j": (2, [
        ("run", LOAD, ""), ("run", SHAPE, "(65793, 12)"), ("run", INFO, "RangeIndex: 65793 entries"),
        ("ask", "Why can one shark have many rows in this file?", "instrumental"),
        ("run", MISSING, "0"), ("run", COUNT, "species\nblue 41\nmako 25\ntiger 187\n..."),
        ("ask", "Is nunique the right choice if some ids are missing?", "instrumental"),
        ("run", TOP, "tiger 187\nwhite 112\nblue 41"),
        ("pad", "Shark inventory. The file has 65793 rows and 12 columns. One shark has many "
                "rows, because each row is one location report. I counted unique ids per species "
                "with groupby and nunique. Tiger sharks have the most individuals (187), then white "
                "sharks (112). Missing species values: 0, so the count is complete."),
    ]),
    "tom.b": (11, [
        ("run", LOAD, ""),
        ("ask", "give me the code for step 3", "executive"),
        ("ask", "just write the code", "executive"),
        ("run", SHAPE, "(65793, 12)"),
        ("ask", "can you do step 5 for me", "executive"),
        ("ask", "what is the answer to step 6", "executive"),
        ("ask", "How do I check for missing values?", "instrumental"),
        ("ask", "ok now give me the full code for step 6", "executive"),
    ]),
    "lina.k": (6, [
        ("error", "sharks_df = pd.read_csv('shark.csv')", "FileNotFoundError: [Errno 2] No such file or directory: 'shark.csv'"),
        ("error", "sharks_df = pd.read_csv('Sharks.csv')", "FileNotFoundError: [Errno 2] No such file or directory: 'Sharks.csv'"),
        ("error", "sharks_df = pd.read_csv('data/sharks.csv')", "FileNotFoundError: [Errno 2] No such file or directory: 'data/sharks.csv'"),
        ("error", "print(sharks_df.shape)", "NameError: name 'sharks_df' is not defined"),
        ("nudge", "I see that the file does not load. Look at the file browser on the left: what is "
                  "the exact name of the data file?"),
    ]),
    "noah.v": (3, [
        ("run", LOAD, ""),
        ("error", "sharks_df['Species'].isna().sum()", "KeyError: 'Species'"),
        ("ask", "Why do I get a KeyError for 'Species'?", "instrumental"),
        ("error", "sharks_df.groupby('Species')", "KeyError: 'Species'"),
        ("error", "sharks_df.groupby('species')['ID'].nunique()", "KeyError: 'ID'"),
        ("ask", "Which column has the shark identifier?", "instrumental"),
        ("error", "sharks_df.groupby('species').nunique('id')", "TypeError: nunique() got an unexpected keyword argument"),
        ("run", COUNT, "species\nblue 41\n..."),
    ]),
    "emma.d": (48, [
        ("run", LOAD, ""), ("run", SHAPE, "(65793, 12)"), ("run", INFO, "RangeIndex: 65793 entries"),
        ("run", MISSING, "0"),
        ("ask", "What is the difference between count and nunique?", "instrumental"),
        ("run", COUNT, "species\nblue 41\nmako 25\ntiger 187\n..."), ("run", TOP, "tiger 187\nwhite 112\nblue 41"),
    ]),
    "yusuf.a": (14, [
        ("run", LOAD, ""), ("run", SHAPE, "(65793, 12)"),
        ("ask", "What does info() tell me that shape does not?", "instrumental"),
        ("run", INFO, "RangeIndex: 65793 entries"),
        ("error", "sharks_df.species.nunique", "<bound method ...> (no number)"),
        ("ask", "Just tell me the code for counting", "executive"),
        ("ask", "Sorry, what does groupby do exactly?", "instrumental"),
        ("pad", "The data has 65793 rows. I think there are many species, I will count them next."),
    ]),
    "mila.r": (1, [
        ("ask", "hello", "other"),
        ("run", LOAD, ""),
    ]),
    "finn.h": (24, [
        ("run", LOAD, ""),
        ("pad", "Sharks are important for the ocean. In this report I look at which species are "
                "common. I expect that white sharks are the most common, because they are well "
                "known. Next I will look at the data to check this idea."),
        ("ask", "How can I check my idea with the data?", "instrumental"),
    ]),
}


def rule_for(category, previous, streak):
    """Name of the intervention rule, like the default rules of agent_config.yaml."""
    if category == "instrumental":
        return "Positive reinforcement" if previous == "executive" else "Standard support"
    if category == "executive":
        return {1: "First executive", 2: "Second executive", 3: "Third executive"}.get(streak, "Fourth or more executive")
    return None


def ensure_schema(con):
    con.execute("""CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, timestamp REAL NOT NULL,
        message_type TEXT NOT NULL, message_text TEXT NOT NULL, message_classification TEXT,
        file_name TEXT)""")
    columns = [row[1] for row in con.execute("PRAGMA table_info(chat_history)")]
    if "intervention_rule" not in columns:
        con.execute("ALTER TABLE chat_history ADD COLUMN intervention_rule TEXT")


def etherpad(method, **params):
    if not ETHERPAD_API_KEY:
        return None
    import httpx
    try:
        return httpx.post(f"{ETHERPAD_URL}/api/1/{method}",
                          data=dict(params, apikey=ETHERPAD_API_KEY), timeout=5.0).json()
    except Exception:
        return None


def remove(con):
    for student in STUDENTS:
        con.execute("DELETE FROM chat_history WHERE student_id = ?", (student,))
        for table in ("student_profiles", "learner_models"):
            try:
                con.execute(f"DELETE FROM {table} WHERE student_id = ?", (student,))
            except sqlite3.OperationalError:
                pass
        path = os.path.join(INGESTED_LOGS_DIR, f"{_safe_name(student)}.json")
        if os.path.exists(path):
            os.remove(path)
        etherpad("deletePad", padID=pad_id_for(student))
    con.commit()


def add(con):
    now = time.time()
    for student, (minutes_ago, events) in STUDENTS.items():
        # The events are 1.5 minutes apart and end minutes_ago minutes before now.
        start = now - minutes_ago * 60 - (len(events) - 1) * 90
        logs, previous, streak = [], None, 0
        for i, event in enumerate(events):
            t = start + i * 90
            stamp = datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")
            kind = event[0]
            if kind == "run":
                logs.append({"event": "Executed cells", "time": stamp, "notebook": NOTEBOOK,
                             "cell_index": i, "input": event[1], "output": event[2]})
            elif kind == "error":
                logs.append({"event": "Executed cells with error", "time": stamp, "notebook": NOTEBOOK,
                             "cell_index": i, "content": event[1], "error": event[2]})
            elif kind == "pad":
                logs.append({"event": "Edited Pad", "time": stamp, "notebook": f"{student}.ipynb",
                             "content": event[1]})
                pad = pad_id_for(student)
                etherpad("createPad", padID=pad)
                etherpad("setText", padID=pad, text=event[1])
            elif kind == "nudge":
                con.execute("INSERT INTO chat_history (student_id, timestamp, message_type, message_text, "
                            "message_classification, file_name) VALUES (?, ?, 'response', ?, 'proactive', ?)",
                            (student, t, event[1], CHAT_FILE))
            elif kind == "ask":
                category = event[2]
                streak = streak + 1 if category == previous else 1
                rule = rule_for(category, previous, streak)
                con.execute("INSERT INTO chat_history (student_id, timestamp, message_type, message_text, "
                            "message_classification, file_name, intervention_rule) VALUES (?, ?, 'question', ?, ?, ?, ?)",
                            (student, t, event[1], category, CHAT_FILE, rule))
                con.execute("INSERT INTO chat_history (student_id, timestamp, message_type, message_text, "
                            "message_classification, file_name) VALUES (?, ?, 'response', ?, NULL, ?)",
                            (student, t + 8, ANSWER[category], CHAT_FILE))
                previous = category
        store_student_logs(student, logs)
    con.commit()


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "add"
    os.makedirs(os.path.dirname(DATABASE_FILE), exist_ok=True)
    con = sqlite3.connect(DATABASE_FILE)
    ensure_schema(con)
    remove(con)
    if action == "add":
        add(con)
        print(f"Added {len(STUDENTS)} made-up students: {', '.join(STUDENTS)}.")
    elif action == "remove":
        print(f"Removed the made-up students: {', '.join(STUDENTS)}.")
    else:
        sys.exit("Use 'add' or 'remove'.")


if __name__ == "__main__":
    main()
