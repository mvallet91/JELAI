from typing import List, Optional

from log_processor.notebook_log.notebook_log_entry import NotebookLogEntry
from datetime import datetime

class NotebookActivity:
    """
    A collection of notebook log entries.
    """

    _log_entries: List[NotebookLogEntry]

    def __init__(
        self,
        log_entries: List[NotebookLogEntry],
    ):
        self._log_entries = log_entries

        self._log_entries.sort(key=lambda x: x.eventDetail.eventTime)

        self.check_invariants()

    def check_invariants(self):
        # Check that the log entries are not empty
        assert len(self._log_entries) > 0, "Log entries should not be empty"

        # Check that the log entries are sorted by time
        for i in range(1, len(self._log_entries)):
            assert (
                self._log_entries[i].eventDetail.eventTime
                >= self._log_entries[i - 1].eventDetail.eventTime
            ), "Log entries should be sorted by event time"

    def get_start_time(self):
        for entry in self._log_entries:
            if entry.eventDetail.eventName not in [
                "NotebookVisibleEvent",
                "NotebookHiddenEvent",
            ]:
                return entry.eventDetail.eventTime
        assert False, "No event found"

    def get_end_time(self):
        for entry in reversed(self._log_entries):
            if entry.eventDetail.eventName not in [
                "NotebookVisibleEvent",
                "NotebookHiddenEvent",
            ]:
                return entry.eventDetail.eventTime
        assert False, "No event found"

    def get_completion_time(self):
        return self.get_end_time() - self.get_start_time()

    def get_cell_indexes(self):
        """Get indexes of the cells which are used in this activity"""
        ids = set()

        for entry in self._log_entries:
            eventInfo = entry.eventDetail.eventInfo
            if eventInfo is None:
                continue

            cell_id = eventInfo.index
            if cell_id is None:
                continue

            ids.add(cell_id)

        return ids

    def get_cell_ids(self):
        """Get ids of cells with indexes found in get cell indexes"""
        ids = set()
        indexes = self.get_cell_indexes()

        for entry in self._log_entries:
            eventInfo = entry.eventDetail.eventInfo
            if eventInfo is None:
                continue
            if eventInfo.cells is not None:
                for cell in eventInfo.cells:
                    if cell.index in indexes:
                        ids.add(cell.id)

        return ids

    def get_amount_of_executions(self):
        total = 0
        for entry in self._log_entries:
            event_name = entry.eventDetail.eventName
            if event_name == "CellExecuteEvent":
                total += 1

        return total

    def get_event_count(self):
        return len(self._log_entries)

    def get_event_by_index(self, index: int) -> Optional[NotebookLogEntry]:
        if 0 <= index < len(self._log_entries):
            return self._log_entries[index]
        return None

    def get_amount_of_runtime_errors(self):
        total = 0
        for entry in self._log_entries:
            event_name = entry.eventDetail.eventName
            if event_name == "CellExecuteEvent":
                eventInfo = entry.eventDetail.eventInfo
                assert eventInfo is not None, "eventInfo should not be None"
                if eventInfo.success == False:
                    total += 1

        return total

    def get_state_of_cell_at(self, cell_id: str, time: datetime):
        final_state = ""
        for entry in self._log_entries:
            event_name = entry.eventDetail.eventName
            if event_name == "CellExecuteEvent" and entry.eventDetail.eventTime <= time:
                notebook_content = entry.notebookState.notebookContent
                assert (
                    notebook_content is not None
                ), "notebook_content should not be None"
                cells = notebook_content.cells
                for cell in cells:
                    if cell.id == cell_id:
                        final_state = cell.source

        return final_state

    def get_amount_of_tab_switches(self):
        total = 0
        for entry in self._log_entries:
            event_name = entry.eventDetail.eventName
            time = entry.eventDetail.eventTime
            if event_name == "NotebookVisibleEvent" and time >= self.get_start_time() and time <= self.get_end_time():
                total += 1

        return total

    def get_amount_of_edit_cycles(self):
        """
        How many times is the program run and then edited
        """
        total = 0
        edited = False
        for entry in self._log_entries:
            event_name = entry.eventDetail.eventName
            if event_name == "CellExecuteEvent" and edited:
                total += 1
                edited = False
            if event_name in ["CellEditEvent", "NotebookVisibleEvent"]:
                edited = True

        return total
