"""
Script to drop and recreate the teacher_analytics.events table with the vector_embedding column.
Run this from inside the mcp-middleware container: `python /app/scripts/recreate_table.py`
"""

import os
import clickhouse_connect

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_DB = os.getenv("CLICKHOUSE_DB", "teacher_analytics")

def main():
    print(f"Connecting to ClickHouse at {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}...")
    client = clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
    )
    
    print(f"Creating database {CLICKHOUSE_DB} if not exists...")
    client.command(f"CREATE DATABASE IF NOT EXISTS {CLICKHOUSE_DB}")
    
    client = clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database=CLICKHOUSE_DB,
    )

    print("Dropping existing events table...")
    client.command("DROP TABLE IF EXISTS events")

    create_sql = """
    CREATE TABLE events (
        event        String,
        time         UInt64,
        student_id   String,
        task_label   String,
        cell_index   Nullable(Float64),
        content      Nullable(String),
        input        Nullable(String),
        output       Nullable(String),
        error        Nullable(String),
        message_type Nullable(String),
        message_text Nullable(String),
        message_classification Nullable(String),
        experiment_assignment  Nullable(String),
        classifier_v6_intent   Nullable(String),
        classifier_v6_phase    Nullable(String),
        
        experiment_group       String DEFAULT '',
        source_file            String DEFAULT '',
        
        vector_embedding       Array(Float32)
    ) ENGINE = MergeTree()
    ORDER BY (student_id, task_label, time)
    """
    
    print("Creating new events table with vector_embedding column...")
    client.command(create_sql)
    print("Done. Table created successfully.")

if __name__ == "__main__":
    main()
