import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from log_processor.chat_log.chat_message import ChatMessage
from log_processor.chat_log.chat_user import ChatUser


class ChatLog:
    messages: List[ChatMessage]
    users: Dict[str, ChatUser]
    processed_log: Optional[Any]

    def get_message_count(self):
        return len(self.messages)
    
    def get_first_message_before(self, time: float) -> Optional[ChatMessage]:
        for message in self.messages:
            if message.time < time:
                return message
        return None


def load_chat_log(file_path: str) -> ChatLog:
    with open(file_path, "r") as file:
        data = json.load(file)

    chat_log = ChatLog()

    chat_log.messages = [ChatMessage(**msg) for msg in data["messages"]]
    chat_log.users = {key: ChatUser(**value) for key, value in data["users"].items()}
    chat_log.processed_log = data["processed_log"]

    return chat_log
