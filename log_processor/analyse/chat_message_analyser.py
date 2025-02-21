from log_processor.chat_log.chat_message import ChatMessage
from log_processor.chatbot import Chatbot
from enum import Enum

class QuestionPurpose(Enum):
    EXECUTIVE = "executive"
    INSTRUMENTAL = "instrumental"

class QuestionType(Enum):
    ANSWER_TO_QUESTION_OF_CHATBOT = "answer to question of chatbot"

    CODE_COMPREHENSION = "code comprehension"
    CONCEPT_COMPREHENSION = "concept comprehension"
    ERROR_COMPREHENSION = "error comprehension"
    QUESTION_COMPREHENSION = "question comprehension"

    COPIED_QUESTION = "copied question"

    FIX_CODE = "fix code"

    TASK_DELEGATION = "task delegation"

    PASTED_CODE_WITHOUT_CONTEXT = "pasted code without context"

    OTHER = "other"


class ChatMessageAnalyser:

    def __init__(self, chatbot: Chatbot):
        self.chatbot = chatbot

    def analyse(self, message: ChatMessage):
        purpose = self.get_question_purpose(message)
        question_type = self.get_question_type(message)

    def get_question_purpose(self, message: ChatMessage):
        query = f"Is this message executive or instrumental. Only answer 'executive' or 'instrumental'.\n{message.body}"
        response = self.chatbot.ask_question(query).lower().strip()
        for i in range(3):
            if response == "executive":
                return QuestionPurpose.EXECUTIVE
            elif response == "instrumental":
                return QuestionPurpose.INSTRUMENTAL
            response = self.chatbot.ask_question_without_cache(query)
        
        raise Exception("Could not determine if message is executive or instrumental")
    
    def get_question_type(self, message: ChatMessage):
        options = ", ".join([e.value for e in QuestionType])
        query = f"Which type of question is this? Choose from the following options: {options}.\n{message.body}"
        response = self.chatbot.ask_question(query).lower().strip()
        for i in range(3):
            for question_type in QuestionType:
                if response == question_type.value:
                    return question_type
            response = self.chatbot.ask_question_without_cache(query)
        
        raise Exception("Could not determine the question type")

