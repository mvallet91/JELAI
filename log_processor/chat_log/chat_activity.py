import re
from typing import Optional

from log_processor.chat_log.chat_message import ChatMessage
from log_processor.chat_log.chat_user import ChatUser


class ChatActivity:
    """
    Represents multiple chat messages. Calculates matrics about this activity.

    """

    messages: list[ChatMessage]
    users: dict[str, ChatUser]

    def __init__(self, messages: list[ChatMessage], users: dict[str, ChatUser]):
        self.messages = messages
        self.users = users

    def get_activity_between(self, start: float, end: float):
        return ChatActivity(
            [message for message in self.messages if start <= message.time <= end],
            self.users,
        )

    def get_all_generate_code(self):
        codes = []
        for message in self.messages:
            if message.is_answer():
                matches = re.findall(r"\`(.+?)\`", message.body)
                for match in matches:
                    codes.append(match)

        return codes
    
    def get_amount_of_questions(self):
        total = 0
        for message in self.messages:
            if message.is_question():
                total += 1

        return total

    def get_summary(self) -> str:
        return (
            "== Chat activity ==\n"
            f"Amount of questions = {self.get_amount_of_questions()}\n"
            f"Generated code = {self.get_all_generate_code()}"
        )
