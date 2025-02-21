import json
from typing import Any

from log_processor.chat_log.chat_activity import ChatActivity
from log_processor.chat_log.chat_message import ChatMessage
from log_processor.chat_log.chat_user import ChatUser


class ChatLog(ChatActivity):
    """
    A processed chat log containing messages and users.
    """

    def __init__(self):
        super().__init__()

    def load_file(self, file_path: str):
        with open(file_path, "r") as file:
            if file.read(1) == '':
                return []
            else:
                file.seek(0)
                data = json.load(file)

        self.load(data)

    def load(self, data: Any):
        messages = [ChatMessage(**msg) for msg in data["messages"]]
        users = {key: ChatUser(**value) for key, value in data["users"].items()}
        self.add_messages(messages)
        self.add_users(users)
