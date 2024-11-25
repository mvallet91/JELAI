from log_processor.chat_log.chat_activity import ChatActivity
from log_processor.notebook_log.notebook_cell_activity import NotebookCellActivity


class CellActivity:
    """
    Represents all activity related to a single cell.

    Attributes:
        subtasks: A list of moment that the user spend on this task.
    """

    notebook_activity: NotebookCellActivity
    chat_activity: ChatActivity

    def __init__(
        self, notebook_activity: NotebookCellActivity, chat_activity: ChatActivity
    ):
        self.notebook_activity = notebook_activity
        self.chat_activity = chat_activity

    # def get_used_ai_code(self):
    #     codes = self.chat_activity.get_all_generate_code()
    #     matches = self.notebook_activity.check_matching_code(codes)
    #     return matches

    def get_summary(self) -> str:
        return (
            f"Summary for cell {self.notebook_activity.get_cell_id()}\n"
            f"{self.notebook_activity.get_summary()}\n"
            f"{self.chat_activity.get_summary()}"
        )

    def __str__(self):
        return f"Cell activity for cell {self.notebook_activity.get_cell_id()}"
