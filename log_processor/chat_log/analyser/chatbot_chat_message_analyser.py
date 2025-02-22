from log_processor.chat_log.analyser.chat_message_analyser import ChatMessageAnalyser
from log_processor.chat_log.chat_message import (
    ChatMessage,
    QuestionPurpose,
    QuestionType,
)
from log_processor.chatbot import Chatbot


class ChatbotChatMessageAnalyser(ChatMessageAnalyser):

    def __init__(self, chatbot: Chatbot):
        self.chatbot = chatbot

    def get_question_purpose(self, message: ChatMessage):
        query = f"Is this message executive or instrumental. Only answer 'executive' or 'instrumental'.\nThe message: \n\n{message.body}"
        response = self.chatbot.ask_question(query).lower().strip()
        for i in range(3):
            if response == "executive":
                return QuestionPurpose.EXECUTIVE
            elif response == "instrumental":
                return QuestionPurpose.INSTRUMENTAL

            # Try again
            response = self.chatbot.ask_question_without_cache(query)

        return QuestionPurpose.NOT_DETECTED

    #TODO check if not two question types are returned in the response
    def get_question_type(self, message: ChatMessage):
        explanations = "\n".join([f"{e.name}: {e.value}" for e in QuestionType])
        
        query = f"Which type of question is this? Choose from the following options: \n{explanations}\n\n Only answer the chosen option. \n The message: \n\n{message.body}"

        response = self.chatbot.ask_question(query).lower().strip()
        
        for i in range(3):
            detected_types = []
            for question_type in QuestionType:
                if question_type.name in response:
                    detected_types.append(question_type)
            
            if len(detected_types) == 1:
                return detected_types[0]
            
            # Try again
            response = self.chatbot.ask_question_without_cache(query)

        return QuestionType.NOT_DETECTED
