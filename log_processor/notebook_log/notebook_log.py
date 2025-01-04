import json
from typing import Any, Dict, List

from log_processor.notebook_log.notebook_activity import NotebookActivity
from log_processor.notebook_log.notebook_cell_activity import NotebookCellActivity
from log_processor.notebook_log.notebook_cell_activity_composite import (
    NotebookCellActivityComposite,
)
from log_processor.notebook_log.notebook_log_entry import NotebookLogEntry


class NotebookLog(NotebookActivity):
    """
    A processed notebook log containing log entries.
    """

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

    # TODO make protection againgt changes the index of a cell
    def get_notebook_cell_activities(self) -> List[NotebookCellActivity]:
        cell_index_to_activity = {}

        for entry in self._log_entries:
            event_name = entry.eventDetail.eventName

            eventInfo = entry.eventDetail.eventInfo
            if eventInfo is None:
                print(f"No event info found for {event_name}")
                continue

            if eventInfo.cells is not None:
                cells = eventInfo.cells
                cell_ids = [cell.index for cell in cells]
            else:
                cell_ids = [eventInfo.index]
                if cell_ids[0] is None:
                    print(f"No cell index found for {event_name}")
                    continue

            for cell_id in cell_ids:
                if cell_id not in cell_index_to_activity:
                    cell_index_to_activity[cell_id] = []

                cell_index_to_activity[cell_id].append(entry)

        return [
            NotebookCellActivity(subtask) for subtask in cell_index_to_activity.values()
        ]

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

    def get_summary(self, level=1):
        return f"{'#' * level} Notebook activity\n\n" f"None yet"
