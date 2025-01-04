import re
from typing import List

from log_processor.chat_log.chat_message import ChatMessage
from log_processor.chat_log.chat_user import ChatUser


class ChatActivity:
    """
    Collection of chat messages.

    """

    _messages: list[ChatMessage]
    _users: dict[str, ChatUser]

    def __init__(self, messages: list[ChatMessage], users: dict[str, ChatUser]):
        self._messages = messages
        self._users = users

        self._messages.sort(key=lambda x: x.time)

        self.check_invariants()

    def check_invariants(self):
        # Check if messages are sorted by time
        for i in range(len(self._messages) - 1):
            assert self._messages[i].time <= self._messages[i + 1].time

    def get_questions(self):
        messages = [message for message in self._messages if message.is_question()]
        return ChatActivity(messages, self._users)

    def get_answers(self):
        messages = [message for message in self._messages if message.is_answer()]
        return ChatActivity(messages, self._users)

    def get_amount_of_messages(self):
        return len(self._messages)

    def get_messages_length(self):
        length = 0
        for message in self._messages:
            length += message.get_message_length()
        return length

    def get_activity_between(self, start: float, end: float):
        return ChatActivity(
            [message for message in self._messages if start <= message.time <= end],
            self._users,
        )

    def get_code_snippets(
        self, include_questions: bool = True, include_answers: bool = True
    ):
        codes: List[str] = []
        for message in self._messages:
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
        for message in self._messages:
            if message.is_question():
                text = f"{self._users[message.sender].name} asked: {message.body}"
                messages.append(text)
            elif message.is_answer():
                text = f"{self._users[message.sender].name} answered: {message.body}"
                messages.append(text)

        return messages

    def get_interactions(self):
        from log_processor.chat_log.chat_interaction import (
            ChatInteraction,
        )  # avoid circular import

        interactions: List[ChatInteraction] = []
        for i in range(0, len(self._messages) - 1):
            if self._messages[i].is_question() and self._messages[i + 1].is_answer():
                interactions.append(
                    ChatInteraction(
                        [self._messages[i], self._messages[i + 1]], self._users
                    )
                )

        return interactions

    def get_summary(self, level=1):
        interactions = "\n".join(
            [
                interaction.get_summary(level + 2)
                for interaction in self.get_interactions()
            ]
        )
        generated_code = "\n\n".join(["```python\n"+x+"\n```" for x in self.get_generated_code_snippets()])
        return (
            f"{'#' * level} Chat activity\n\n"
            f"Amount of questions = {self.get_amount_of_messages()}\n\n"
            f"{'#' * (level + 1)} Generated code snippets\n\n"
            f"{generated_code}\n\n"
            f"{'#' * (level + 1)} Interactions\n\n"
            f"{interactions}"
        )
