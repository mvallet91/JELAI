from typing import List

from log_processor.notebook_log.notebook_activity import NotebookActivity
from log_processor.notebook_log.notebook_log_entry import NotebookLogEntry


class NotebookCellSubActivity(NotebookActivity):
    """
    Represents a continous span of working on a single cell

    Attributes:
        notebook_log_entries: All notebook log entries that relate to this cell

    notebook_log_entries and chat_log_entries are always sorted by event time

    """

    def __init__(
        self,
        log_entries: List[NotebookLogEntry],
    ):
        super().__init__(log_entries)

    def get_cell_id(self):
        ids = self.get_cell_ids()
        assert len(ids) == 1, "There should be exactly one cell id"
        return ids.pop()
