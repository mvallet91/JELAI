import os

import pandas as pd
from dotenv import load_dotenv

from log_processor.chat_log.analyser.chatbot_chat_message_analyser import (
    ChatbotChatMessageAnalyser,
)
from log_processor.chatbot import Chatbot
from log_processor.user.users import Users
from log_processor.user.users_builder import UsersBuilder


class Processor:
    def __init__(self):
        load_dotenv()

        self.chatbot_cache = "output/chatbot_cache.json"
        self.chatbot = Chatbot()
        self.chatbot.load_cache(self.chatbot_cache)

        self.chat_message_analyser = ChatbotChatMessageAnalyser(self.chatbot)

        self.users_cache = "output/users.pkl"

        if os.path.exists(self.users_cache):
            print("Loading users from saved file")
            self.users = Users.load_from_file(self.users_cache, self.chat_message_analyser)
        else:
            builder = UsersBuilder(verbose=True)
            builder.load_log_directory(
                "W:/staff-umbrella/DataStorageJELAI/CDL First Run/_logs"
            )
            builder.load_volumes_directory(
                "W:/staff-umbrella/DataStorageJELAI/CDL First Run"
            )
            self.users = builder.build(self.chat_message_analyser)
            self.users.save_to_file(self.users_cache)

    def generate_analysed_questions_report(self):
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
    
    def run(self):
        self.generate_analysed_questions_report()
        self.stop()

    def stop(self):
        self.chatbot.save_cache(self.chatbot_cache)
