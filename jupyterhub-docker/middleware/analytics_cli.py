import sqlite3
from collections import Counter
from datetime import datetime

DB_PATH = "/app/chat_histories/chat_history.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Total number of questions
    c.execute("SELECT COUNT(*) FROM chat_history WHERE message_type = 'question'")
    total_questions = c.fetchone()[0]
    print(f"Total questions: {total_questions}")

    # Total number of responses
    c.execute("SELECT COUNT(*) FROM chat_history WHERE message_type = 'response'")
    total_responses = c.fetchone()[0]
    print(f"Total responses: {total_responses}")

    # Number of unique students
    c.execute("SELECT COUNT(DISTINCT student_id) FROM chat_history")
    unique_students = c.fetchone()[0]
    print(f"Unique students: {unique_students}")

    # Number of questions per student (top 10)
    c.execute("SELECT student_id, COUNT(*) FROM chat_history WHERE message_type = 'question' GROUP BY student_id ORDER BY COUNT(*) DESC LIMIT 10")
    print("\nTop 10 students by number of questions:")
    for student_id, count in c.fetchall():
        print(f"  {student_id}: {count}")

    # Distribution of question classifications
    c.execute("SELECT message_classification, COUNT(*) FROM chat_history WHERE message_type = 'question' GROUP BY message_classification")
    print("\nQuestion classification distribution:")
    for classification, count in c.fetchall():
        print(f"  {classification or 'Unclassified'}: {count}")

    # Number of questions per assignment (file_name, top 10)
    c.execute("SELECT file_name, COUNT(*) FROM chat_history WHERE message_type = 'question' GROUP BY file_name ORDER BY COUNT(*) DESC LIMIT 10")
    print("\nTop 10 assignments by number of questions:")
    for file_name, count in c.fetchall():
        print(f"  {file_name}: {count}")

    # Date range of activity
    c.execute("SELECT MIN(timestamp), MAX(timestamp) FROM chat_history")
    min_ts, max_ts = c.fetchone()
    if min_ts and max_ts:
        min_dt = datetime.fromtimestamp(min_ts)
        max_dt = datetime.fromtimestamp(max_ts)
        print(f"\nActivity date range: {min_dt} to {max_dt}")
    else:
        print("\nNo activity recorded.")

    # Students per experiment group
    print("\nStudents per experiment group:")
    c.execute("SELECT experiment_id, group_id, COUNT(DISTINCT student_id) FROM student_experiment_assignments GROUP BY experiment_id, group_id ORDER BY experiment_id, group_id")
    rows = c.fetchall()
    if rows:
        for experiment_id, group_id, count in rows:
            print(f"  Experiment: {experiment_id} | Group: {group_id} | Students: {count}")
    else:
        print("  No experiment group assignments found.")

    conn.close()

if __name__ == "__main__":
    main() 