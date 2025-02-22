from datetime import datetime
from enum import Enum

from log_processor.chat_log.analyser.chat_message_analyser import ChatMessageAnalyser


class QuestionPurpose(Enum):
    EXECUTIVE = "executive"
    INSTRUMENTAL = "instrumental"
    NOT_DETECTED = "unable to detect the questions purpose"


class QuestionType(Enum):
    """Enumeration of different types of questions a chatbot might encounter."""

    ANSWER_TO_QUESTION_OF_CHATBOT = "The user is responding to a question asked by the chatbot rather than asking a new one."

    CODE_COMPREHENSION = "The user is asking for an explanation of a piece of code, how it works, or what it does."

    CONCEPT_COMPREHENSION = "The user is asking for an explanation of a theoretical or abstract concept, often related to programming, science, or another domain."

    ERROR_COMPREHENSION = "The user is asking for help in understanding an error message, its cause, and how to fix it."

    QUESTION_COMPREHENSION = "The user is asking for clarification about a question itself, such as what it means or how to interpret it."

    COPIED_QUESTION = "The user has copied and pasted a question from another source without modification."

    FIX_CODE = "The user is asking for help in correcting a bug, syntax issue, or logical error in a piece of code."

    TASK_DELEGATION = "The user is asking the chatbot to perform a specific task, such as generating code, writing a document, or performing an analysis."

    PASTED_CODE_WITHOUT_CONTEXT = "The user has pasted a piece of code without providing an explicit question or any context."

    OTHER = "The user's question does not fit into any of the predefined categories."

    NOT_DETECTED = "The chatbot is unable to determine the type of question due to ambiguity or lack of information."


class ChatMessage:
    """
    A single chat message
    """

    def __init__(
        self,
        chat_message_analyser: ChatMessageAnalyser,
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
        self.chat_message_analyser = chat_message_analyser
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

    def get_question_purpose(self):
        return self.chat_message_analyser.get_question_purpose(self)

    def get_question_type(self):
        return self.chat_message_analyser.get_question_type(self)

    def __str__(self):
        return f"{self.sender} ({self.time}): {self.body}"
