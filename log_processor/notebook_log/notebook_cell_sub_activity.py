from typing import List

from log_processor.notebook_log.notebook_log_entry import NotebookLogEntry


class NotebookCellSubActivity:
    """
    Represents a continous span of working on a single cell

    Attributes:
        notebook_log_entries: All notebook log entries that relate to this cell

    notebook_log_entries and chat_log_entries are always sorted by event time

    """

    log_entries: List[NotebookLogEntry]

    def __init__(
        self,
        log_entries: List[NotebookLogEntry],
    ):
        self.log_entries = log_entries

        self.log_entries.sort(key=lambda x: x.eventDetail.eventTime)

    def get_start_time(self):
        return self.log_entries[0].eventDetail.eventTime

    def get_end_time(self):
        return self.log_entries[-1].eventDetail.eventTime

    def get_completion_time(self):
        return self.get_end_time() - self.get_start_time()

    def get_cell_id(self):
        if self.log_entries[0].eventDetail.eventName == "NotebookOpenEvent":
            return "first-cell"

        for entry in self.log_entries:
            event_name = entry.eventDetail.eventName
            if event_name == "ActiveCellChangeEvent":
                eventInfo = entry.eventDetail.eventInfo
                assert eventInfo is not None, "eventInfo should not be None"
                cells = eventInfo.cells
                assert cells is not None, "cells should not be None"
                return cells[0].id
            
        raise Exception("No cell id found")

    def get_amount_of_executions(self):
        total = 0
        for entry in self.log_entries:
            event_name = entry.eventDetail.eventName
            if event_name == "CellExecuteEvent":
                total += 1

        return total

    def get_amount_of_execution_errors(self):
        total = 0
        for entry in self.log_entries:
            event_name = entry.eventDetail.eventName
            if event_name == "CellExecuteEvent":
                eventInfo = entry.eventDetail.eventInfo
                assert eventInfo is not None, "eventInfo should not be None"
                if eventInfo.success == False:
                    total += 1

        return total
