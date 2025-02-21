from datetime import datetime


class ChatMessage:
    """
    A single chat message
    """

    def __init__(
        self,
        type: str,
        time: float,
        id: str,
        raw_time: bool,
        body: str,
        sender: str,
        automated: bool = False,
        deleted: bool = False,
        edited: bool = False,
    ):
        self.type = type
        self.time = datetime.fromtimestamp(time)
        self.id = id
        self.raw_time = raw_time
        self.body = body
        self.sender = sender
        self.automated = automated
        self.deleted = deleted
        self.edited = edited

    def get_message_length(self):
        return len(self.body)

    def is_question(self):
        if self.automated == True:
            return False
        if self.sender == "Juno":
            return False
        return True

    def is_answer(self):
        return self.sender == "Juno"

    def __str__(self):
        return f"{self.sender} ({self.time}): {self.body}"
