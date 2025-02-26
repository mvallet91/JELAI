from math import e
import os

import pandas as pd
from dotenv import load_dotenv

from log_processor.chat_log.analyser.chatbot_chat_message_analyser import (
    ChatbotChatMessageAnalyser,
)
from log_processor.chatbot import Chatbot
from log_processor.processor import questions_analyser
from log_processor.processor.event_sequence_analysis import EventSequenceAnalysis
from log_processor.processor.questions_analyser import QuestionsAnalyser
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
        
    def run(self):
        # print("Analyzing questions")
        # questions_analyser = QuestionsAnalyser(self.users)
        # questions_analyser.generate_report()

        print("Analyzing event sequences")
        event_sequence_analyser = EventSequenceAnalysis(self.users)
        event_sequence_analyser.generate_report()

        self.stop()

    def stop(self):
        self.chatbot.save_cache(self.chatbot_cache)
