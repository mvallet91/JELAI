from log_processor.cell_activity import CellActivity
from log_processor.chat_log.chat_message import ChatMessage


class PromptMetric:
    task: CellActivity
    prompt: ChatMessage
    response: ChatMessage

    def __init__(self, task: CellActivity, prompt: ChatMessage, response: ChatMessage):
        self.task = task
        self.prompt = prompt
        self.response = response

    def get_message_length(self):
        return self.prompt.get_message_length()

    def get_response_length(self):
        return self.response.get_message_length()

    def get_typing_time(self):
        raise NotImplementedError

    def get_waiting_time(self):
        return self.response.time - self.prompt.time

    # def get_prompt_similarity_with_task_description(self):
    #     return self.prompt.get_text_similarity(self.task.description)

    def get_current_correctness_score(self):
        return self.task.get_correctness_score_at(self.prompt.time)

    # def get_time_since_notebook_open(self):
    #     return self.task.get_time_notebook_open_until(self.prompt.time)

    def __str__(self):
        return f"Task: {self.task}, Prompt: {self.prompt}, Response: {self.response}"
