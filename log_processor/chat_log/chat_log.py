import json
from typing import Any, Optional

from log_processor.chat_log.chat_activity import ChatActivity
from log_processor.chat_log.chat_message import ChatMessage
from log_processor.chat_log.chat_user import ChatUser


class ChatLog(ChatActivity):
    """A processed chat log containing messages and users."""

    processed_log: Optional[Any]

    def __init__(self):
        super().__init__([], {})
        self.processed_log = None


def load_chat_log(file_path: str) -> ChatLog:
    with open(file_path, "r") as file:
        data = json.load(file)

    chat_log = ChatLog()

    chat_log.messages = [ChatMessage(**msg) for msg in data["messages"]]
    chat_log.users = {key: ChatUser(**value) for key, value in data["users"].items()}
    chat_log.processed_log = data["processed_log"]

    return chat_log
