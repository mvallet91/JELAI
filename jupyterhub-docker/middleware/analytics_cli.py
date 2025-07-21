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

def show_recent_activity(limit=20):
    """Show the most recent questions and responses with student info"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    print(f"\n=== Last {limit} Questions Asked ===")
    c.execute("""
        SELECT student_id, file_name, message_text, message_classification, timestamp
        FROM chat_history 
        WHERE message_type = 'question'
        ORDER BY timestamp DESC 
        LIMIT ?
    """, (limit,))
    
    for student_id, file_name, message_text, classification, timestamp in c.fetchall():
        dt = datetime.fromtimestamp(timestamp)
        # Truncate long messages
        display_message = message_text[:100] + "..." if len(message_text) > 100 else message_text
        print(f"[{dt.strftime('%Y-%m-%d %H:%M:%S')}] {student_id} ({file_name})")
        print(f"  Classification: {classification or 'Unclassified'}")
        print(f"  Question: {display_message}")
        print()
    
    print(f"\n=== Recent Activity Summary (Last {limit} interactions) ===")
    c.execute("""
        SELECT student_id, message_type, COUNT(*) as count
        FROM chat_history 
        WHERE rowid IN (
            SELECT rowid FROM chat_history 
            ORDER BY timestamp DESC 
            LIMIT ?
        )
        GROUP BY student_id, message_type
        ORDER BY student_id, message_type
    """, (limit * 2,))  # Get more to include both questions and responses
    
    current_student = None
    for student_id, message_type, count in c.fetchall():
        if current_student != student_id:
            if current_student is not None:
                print()
            print(f"{student_id}:")
            current_student = student_id
        print(f"  {message_type}s: {count}")
    
    conn.close()

def show_student_details(student_id=None):
    """Show detailed activity for a specific student or all students"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if student_id:
        print(f"\n=== Activity Details for {student_id} ===")
        where_clause = "WHERE student_id = ?"
        params = (student_id,)
    else:
        print("\n=== All Student Activity Details ===")
        where_clause = ""
        params = ()
    
    # Get student activity summary
    query = f"""
        SELECT student_id, file_name, 
               COUNT(CASE WHEN message_type = 'question' THEN 1 END) as questions,
               COUNT(CASE WHEN message_type = 'response' THEN 1 END) as responses,
               MIN(timestamp) as first_interaction,
               MAX(timestamp) as last_interaction
        FROM chat_history 
        {where_clause}
        GROUP BY student_id, file_name
        ORDER BY student_id, file_name
    """
    
    c.execute(query, params)
    
    for row in c.fetchall():
        student, file_name, questions, responses, first_ts, last_ts = row
        first_dt = datetime.fromtimestamp(first_ts)
        last_dt = datetime.fromtimestamp(last_ts)
        duration = (last_ts - first_ts) / 60  # minutes
        
        print(f"\n{student} - {file_name}:")
        print(f"  Questions: {questions} | Responses: {responses}")
        print(f"  Duration: {duration:.1f} minutes")
        print(f"  First: {first_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Last: {last_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Show classification breakdown for this student/file
        if student_id or questions > 0:
            c.execute("""
                SELECT message_classification, COUNT(*) 
                FROM chat_history 
                WHERE student_id = ? AND file_name = ? AND message_type = 'question'
                GROUP BY message_classification
            """, (student, file_name))
            
            classifications = c.fetchall()
            if classifications:
                print("  Classifications:", end=" ")
                class_summary = []
                for classification, count in classifications:
                    class_summary.append(f"{classification or 'unclassified'}({count})")
                print(", ".join(class_summary))
    
    conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "recent":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            show_recent_activity(limit)
        elif command == "student":
            student_id = sys.argv[2] if len(sys.argv) > 2 else None
            show_student_details(student_id)
        elif command == "summary":
            main()
        else:
            print("Usage:")
            print("  python analytics_cli.py summary          # Show overall statistics")
            print("  python analytics_cli.py recent [N]       # Show last N questions (default: 20)")
            print("  python analytics_cli.py student [ID]     # Show details for specific student or all")
            print("\nExamples:")
            print("  python analytics_cli.py recent 10")
            print("  python analytics_cli.py student alice123")
    else:
        # Default behavior - show summary
        main() 