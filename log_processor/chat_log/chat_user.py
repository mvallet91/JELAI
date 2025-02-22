from typing import Optional


class ChatUser:
    """
    User in the chat log.
    """

    def __init__(
        self,
        initials: str,
        color: str,
        name: str,
        username: str,
        display_name: str,
        avatar_url: Optional[str] = None,
    ):
        self.initials = initials
        self.color = color
        self.name = name
        self.username = username
        self.display_name = display_name
        self.avatar_url = avatar_url

    def get_amount_of_messages(self, messages):
        return len([msg for msg in messages if msg.sender == self.username])

    def __str__(self):
        return f"{self.display_name} ({self.username})"
