from log_processor.activity.cell_activity import CellActivity
from log_processor.chat_log.analyser.chat_message_analyser import ChatMessageAnalyser
from log_processor.chat_log.chat_activity import ChatActivity
from log_processor.chat_log.chat_log import ChatLog
from log_processor.notebook_log.notebook_log import NotebookLog


class User:
    def __init__(self, username: str, chat_message_analyser: ChatMessageAnalyser):
        self.username = username
        self.chat_log = ChatLog(chat_message_analyser)
        self.notebook_log = NotebookLog()
        self.notebook_files = []

    def load_chat_log_files(self, file_paths: list[str]):
        for path in file_paths:
            self.chat_log.load_file(path)

    def load_notebook_log_files(self, file_paths: list[str]):
        for path in file_paths:
            self.notebook_log.load_file(path)

    def load_notebook_files(self, file_paths: list[str]):
        self.notebook_files.extend(file_paths)

    def get_cell_activities(self) -> list[CellActivity]:
        activities: list[CellActivity] = []

        notebook_activities = self.notebook_log.get_notebook_cell_activity_composites()
        for notebook_activity in notebook_activities:
            messages = []
            users = {}
            for notebook_sub_activity in notebook_activity.cell_activities:
                activity = self.chat_log.get_activity_between(
                    notebook_sub_activity.get_start_time(),
                    notebook_sub_activity.get_end_time(),
                )
                messages.extend(activity.messages)
                users.update(activity.users)
            activities.append(
                CellActivity(notebook_activity, ChatActivity(messages, users))
            )

        return activities
    
    def get_event_sequence(self):
        sequence = self.notebook_log.get_event_sequence()
        sequence2 = self.chat_log.get_event_sequence()
        sequence.extend(sequence2)
        sequence.sort(key=lambda x: x[0])
        return sequence

    def get_overview(self, level=1):
        activities = "\n".join(
            [
                activity.get_overview(level + 1)
                for activity in self.get_cell_activities()
            ]
        )
        return (
            f"{'#' * level} Summary for user {self.username}\n\n"
            f"{self.chat_log.get_overview(level )}\n"
            f"{self.notebook_log.get_overview(level)}\n"
            f"{'#' * (level + 1)} Cell activities\n\n"
            f"{activities}"
        )

    def get_summary(self):
        return f"User {self.username}"
