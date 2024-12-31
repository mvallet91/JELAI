import json
from typing import Any, Optional

from log_processor.chat_log.chat_activity import ChatActivity
from log_processor.chat_log.chat_message import ChatMessage
from log_processor.chat_log.chat_user import ChatUser


class ChatLog(ChatActivity):
    """
    A processed chat log containing messages and users.
    """

    processed_log: Optional[Any]

    @staticmethod
    def load_from_file(file_path: str):
        with open(file_path, "r") as file:
            data = json.load(file)

        return ChatLog.load(data)

    @staticmethod
    def load(data: Any):
        return ChatLog(
            [ChatMessage(**msg) for msg in data["messages"]],
            {key: ChatUser(**value) for key, value in data["users"].items()},
            data["processed_log"],
        )

    def __init__(self, messages, users, processed_log):
        super().__init__(messages, users)
        self.processed_log = processed_log
        