from log_processor.cell_activity import CellActivity
from log_processor.chat_log.chat_activity import ChatActivity
from log_processor.chat_log.chat_log import ChatLog
from log_processor.notebook_log.notebook_log import NotebookLog


class Log:
    chat_log: ChatLog
    notebook_log: NotebookLog

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
