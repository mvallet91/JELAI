from log_processor.cell_activity import CellActivity
from log_processor.chat_log.chat_activity import ChatActivity
from log_processor.chat_log.chat_log import ChatLog
from log_processor.notebook_log.notebook_log import NotebookLog


class Log:
    chat_log: ChatLog
    notebook_log: NotebookLog

    @staticmethod
    def load_from_files(chat_log_file_path: str, notebook_log_file_path: str):
        chat_log = ChatLog.load_from_file(chat_log_file_path)
        notebook_log = NotebookLog.load_from_file(notebook_log_file_path)
        log = Log(chat_log, notebook_log)
        return log

    def __init__(self, chat_log: ChatLog, notebook_log: NotebookLog):
        self.chat_log = chat_log
        self.notebook_log = notebook_log

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
                messages.extend(activity._messages)
                users.update(activity._users)
            activities.append(
                CellActivity(notebook_activity, ChatActivity(messages, users))
            )

        return activities

    def get_summary(self, level=1):
        activities = "\n".join(
            [activity.get_summary(level + 2) for activity in self.get_cell_activities()]
        )
        return (
            f"{'#' * level} Log summary\n"
            f"{self.chat_log.get_summary(level + 1)}\n"
            f"{self.notebook_log.get_summary(level + 1)}\n"
            f"{'#' * (level + 1)} Cell activities\n"
            f"{activities}"
        )
