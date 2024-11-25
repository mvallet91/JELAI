import json
from typing import Any, Dict, List, Optional

from log_processor.notebook_log.notebook_activity import NotebookActivity
from log_processor.notebook_log.notebook_cell_activity import NotebookCellActivity
from log_processor.notebook_log.notebook_cell_sub_activity import (
    NotebookCellSubActivity,
)
from log_processor.notebook_log.notebook_log_entry import NotebookLogEntry


class NotebookLog(NotebookActivity):
    """A processed notebook log containing log entries."""

    @staticmethod
    def load_from_file(file_path: str):
        with open(file_path, "r") as file:
            data = file.read()
            data = '[' + data[:-1] + ']'
            data = json.loads(data)

        return NotebookLog.load(data)

    @staticmethod
    def load(dict: Any):
        log_entries = [NotebookLogEntry.load(entry) for entry in dict]

        return NotebookLog(log_entries)

    def __init__(self, log_entries: List[NotebookLogEntry]):
        super().__init__(log_entries)

    def get_notebook_sub_activities(self) -> List[NotebookCellSubActivity]:
        current_subtask: NotebookCellSubActivity = NotebookCellSubActivity([])
        subtasks = {"first": current_subtask}

        self.log_entries.sort(key=lambda x: x.eventDetail.eventTime)

        for entry in self.log_entries:

            # New subtasks when switching cells
            event_name = entry.eventDetail.eventName
            if event_name == "ActiveCellChangeEvent":
                eventInfo = entry.eventDetail.eventInfo
                assert eventInfo is not None, "eventInfo should not be None"
                cells = eventInfo.cells
                assert cells is not None, "cells should not be None"
                cell_id = cells[0].id
                if cell_id not in subtasks:
                    subtasks[cell_id] = NotebookCellSubActivity([])
                current_subtask = subtasks[cell_id]

            current_subtask.log_entries.append(entry)

        return list(subtasks.values())

    def get_notebook_activities(self) -> List[NotebookCellActivity]:
        tasks: Dict[str, NotebookCellActivity] = {}
        notebook_cell_sub_activities = self.get_notebook_sub_activities()

        for notebook_cell_sub_activity in notebook_cell_sub_activities:
            cell_id = notebook_cell_sub_activity.get_cell_id()
            if cell_id not in tasks:
                tasks[cell_id] = NotebookCellActivity()
            tasks[cell_id].sub_activities.append(notebook_cell_sub_activity)

        return list(tasks.values())
