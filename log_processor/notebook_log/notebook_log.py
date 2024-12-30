import json
from typing import Any, Dict, List

from log_processor.notebook_log.notebook_activity import NotebookActivity
from log_processor.notebook_log.notebook_cell_activity import NotebookCellActivity
from log_processor.notebook_log.notebook_cell_activity_composite import (
    NotebookCellActivityComposite,
)
from log_processor.notebook_log.notebook_log_entry import NotebookLogEntry


class NotebookLog(NotebookActivity):
    """A processed notebook log containing log entries."""

    @staticmethod
    def load_from_file(file_path: str):
        with open(file_path, "r") as file:
            data = file.read()
            data = "[" + data[:-1] + "]"
            data = json.loads(data)

        return NotebookLog.load(data)

    @staticmethod
    def load(dict: Any):
        log_entries = [NotebookLogEntry.load(entry) for entry in dict]

        return NotebookLog(log_entries)

    def __init__(self, log_entries: List[NotebookLogEntry]):
        super().__init__(log_entries)

    def get_notebook_cell_activities(self) -> List[NotebookCellActivity]:
        current_subtask = []
        subtasks = {"first": current_subtask}

        for entry in self._log_entries:

            # New subtasks when switching cells
            event_name = entry.eventDetail.eventName
            if event_name == "ActiveCellChangeEvent":
                eventInfo = entry.eventDetail.eventInfo
                assert eventInfo is not None, "eventInfo should not be None"
                cells = eventInfo.cells
                assert cells is not None, "cells should not be None"
                cell_id = cells[0].id
                if cell_id not in subtasks:
                    subtasks[cell_id] = []
                current_subtask = subtasks[cell_id]

            current_subtask.append(entry)

        return [NotebookCellActivity(subtask) for subtask in subtasks.values()]

    def get_notebook_cell_activity_composites(
        self,
    ) -> List[NotebookCellActivityComposite]:
        tasks: Dict[str, List[NotebookCellActivity]] = {}
        notebook_cell_sub_activities = self.get_notebook_cell_activities()

        for notebook_cell_sub_activity in notebook_cell_sub_activities:
            cell_id = notebook_cell_sub_activity.get_cell_id()
            if cell_id not in tasks:
                tasks[cell_id] = []
            tasks[cell_id].append(notebook_cell_sub_activity)

        return [NotebookCellActivityComposite(task) for task in tasks.values()]
