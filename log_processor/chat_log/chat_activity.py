import re
from datetime import datetime
from typing import List, Optional

from log_processor.chat_log.chat_message import ChatMessage
from log_processor.chat_log.chat_user import ChatUser


class ChatActivity:
    """
    Collection of chat messages.

    """

    def __init__(
        self,
        messages: Optional[list[ChatMessage]] = None,
        users: Optional[dict[str, ChatUser]] = None,
    ):
        self.messages: list[ChatMessage] = messages if messages is not None else []
        self.users: dict[str, ChatUser] = users if users is not None else {}

        self.messages.sort(key=lambda x: x.time)

        self.check_invariants()

    def add_messages(self, messages: list[ChatMessage]):
        self.messages.extend(messages)
        self.messages.sort(key=lambda x: x.time)
        self.check_invariants()

    def add_users(self, users: dict[str, ChatUser]):
        self.users.update(users)
        self.check_invariants()

    def check_invariants(self):
        # Check if messages are sorted by time
        for i in range(len(self.messages) - 1):
            assert self.messages[i].time <= self.messages[i + 1].time

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

    def get_activity_between(self, start: datetime, end: datetime):
        return ChatActivity(
            [message for message in self.messages if start <= message.time <= end],
            self.users,
        )

    def get_code_snippets(
        self, include_questions: bool = True, include_answers: bool = True
    ):
        codes: List[str] = []
        for message in self.messages:
            if (include_questions and message.is_question()) or (
                include_answers and message.is_answer()
            ):
                matches = re.finditer(
                    r"(\`\`\`python|\`)((.|\n)+?)\`{1,3}", message.body, re.DOTALL
                )
                for match in matches:
                    code_snippet = match.group(2)
                    codes.append(code_snippet.strip())

        return codes

    def get_generated_code_snippets(self):
        return self.get_code_snippets(False, True)

    def get_send_code_snippets(self):
        return self.get_code_snippets(True, False)

    def get_list_of_messages(self):
        messages = []
        for message in self.messages:
            if message.is_question():
                text = f"{self.users[message.sender].name} asked: {message.body}"
                messages.append(text)
            elif message.is_answer():
                text = f"{self.users[message.sender].name} answered: {message.body}"
                messages.append(text)

        return messages

    def get_interactions(self):
        from log_processor.chat_log.chat_interaction import (
            ChatInteraction,
        )  # avoid circular import

        interactions: List[ChatInteraction] = []
        for i in range(0, len(self.messages) - 1):
            if self.messages[i].is_question() and self.messages[i + 1].is_answer():
                interactions.append(
                    ChatInteraction(
                        [self.messages[i], self.messages[i + 1]], self.users
                    )
                )

        return interactions
    
    def get_event_sequence(self):
        '''Get sequence of events in the chat log.
        Each event is a tuple with the time and the type of event.
        '''
        sequence = []
        for message in self.messages:
            if message.is_question():
                sequence.append((message.time, "Question"))
            elif message.is_answer():
                sequence.append((message.time, "Answer"))
        return sequence

    def get_overview(self, level=1):
        interactions = "\n".join(
            [
                interaction.get_overview(level + 2)
                for interaction in self.get_interactions()
            ]
        )
        generated_code = "\n\n".join(
            ["```python\n" + x + "\n```" for x in self.get_generated_code_snippets()]
        )
        return (
            f"{'#' * level} Chat activity\n\n"
            f"Amount of questions = {self.get_amount_of_messages()}\n\n"
            f"{'#' * (level + 1)} Generated code snippets\n\n"
            f"{generated_code}\n\n"
            f"{'#' * (level + 1)} Interactions\n\n"
            f"{interactions}"
        )
