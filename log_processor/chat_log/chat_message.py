from typing import Optional


class ChatMessage:
    type: str
    time: float
    id: str
    raw_time: bool
    body: str
    sender: str
    automated: Optional[bool] = None

    def __init__(
        self,
        type: str,
        time: float,
        id: str,
        raw_time: bool,
        body: str,
        sender: str,
        automated: Optional[bool] = None,
    ):
        self.type = type
        self.time = time
        self.id = id
        self.raw_time = raw_time
        self.body = body
        self.sender = sender
        self.automated = automated

    def get_message_length(self):
        return len(self.body)

    def is_question(self):
        return self.type == "question"

    def is_answer(self):
        return self.type == "answer"

    def __str__(self):
        return f"{self.sender} ({self.time}): {self.body}"
