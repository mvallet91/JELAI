from log_processor.chat_log.chat_log import ChatLog
from log_processor.notebook_log.notebook_log import NotebookLog


class Log:
    chat_log: ChatLog
    notebook_log: NotebookLog

    def __init__(self, chat_log: ChatLog, notebook_log: NotebookLog):
        self.chat_log = chat_log
        self.notebook_log = notebook_log
    
    