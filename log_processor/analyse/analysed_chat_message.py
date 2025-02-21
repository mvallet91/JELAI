from log_processor.chat_log.chat_message import ChatMessage


class AnalysedChatMessage:
    
    def __init__(self, chat_message: ChatMessage):
        self.chat_message = chat_message