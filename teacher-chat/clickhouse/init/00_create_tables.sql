-- ClickHouse init script: creates the teacher_analytics database and tables
-- This file is auto-executed on first container startup via /docker-entrypoint-initdb.d/

CREATE DATABASE IF NOT EXISTS teacher_analytics;

-- Main event log table: stores all student interaction events from the 4TU dataset
CREATE TABLE IF NOT EXISTS teacher_analytics.events (
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
    -- Derived/ingestion-time fields
    experiment_group       String DEFAULT '',      -- 'control' or 'treatment'
    source_file            String DEFAULT ''       -- e.g. 'S01T/Task1.json'
) ENGINE = MergeTree()
ORDER BY (student_id, task_label, time);


