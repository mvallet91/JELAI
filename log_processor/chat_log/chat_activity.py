import re

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

    def get_questions(self):
        messages = [message for message in self.messages if message.is_question()]
        return ChatActivity(messages, self.users)
    
    def get_answers(self):
        messages = [message for message in self.messages if message.is_answer()]
        return ChatActivity(messages, self.users)
        
    def get_amount_of_messages(self):
        return len(self.messages)

    def get_messages_length(self):
        length = 0
        for message in self.messages:
                length += message.get_message_length()
        return length

    def get_activity_between(self, start: float, end: float):
        return ChatActivity(
            [message for message in self.messages if start <= message.time <= end],
            self.users,
        )

    def get_all_generate_code(self):
        codes = []
        for message in self.messages:
            if message.is_answer():
                matches = re.finditer(r"(\`\`\`python|\`)((.|\n)+?)\`{1,3}", message.body, re.DOTALL)
                for match in matches:
                    a = match.group(2)
                    codes.append(a)

        return codes

    def get_all_interactions(self):
        interactions = []
        for message in self.messages:
            if message.is_question():
                text = f"{self.users[message.sender].name} asked: {message.body}"
                interactions.append(text)
            elif message.is_answer():
                text = f"{self.users[message.sender].name} answered: {message.body}"
                interactions.append(text)

        return interactions

    

    def get_summary(self) -> str:
        return (
            "== Chat activity ==\n"
            f"Amount of questions = {self.get_amount_of_messages()}\n"
            f"Interactions = {self.get_all_interactions()}\n"
            f"Generated code = {self.get_all_generate_code()}"
        )
