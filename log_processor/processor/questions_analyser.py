from log_processor.user.user import User
from log_processor.user.users import Users
import pandas as pd

class QuestionsAnalyser:
    def __init__(self, users: Users):
        self.users = users

    def generate_report(self):
        data = []
        for user in self.users.users:
            print(f"Processing user {user.username}")
            messages = user.chat_log.get_questions().messages
            for question in messages:
                print(f"Processing question {question.id}")
                body = question.body
                purpose = question.get_question_purpose()
                question_type = question.get_question_type()
                data.append(
                    {
                        "user": user.username,
                        "question": body,
                        "question_type": question_type,
                        "purpose": purpose,
                    }
                )

        df = pd.DataFrame(data)
        df.to_csv("output/question_type_report.csv", index=False)
