from typing import List, Optional

from log_processor.notebook_log.notebook_log_entry import NotebookLogEntry
from difflib import SequenceMatcher


class NotebookActivity:
    """
    Represents a collection of notebook activity.

    Attributes:
        subtasks: A list of moment that the user spend on this task.
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

    def get_cell_ids(self):
        ids = set()
        if self.log_entries[0].eventDetail.eventName == "NotebookOpenEvent":
            ids.add("first-cell")

        for entry in self.log_entries:
            event_name = entry.eventDetail.eventName
            if event_name == "ActiveCellChangeEvent":
                eventInfo = entry.eventDetail.eventInfo
                assert eventInfo is not None, "eventInfo should not be None"
                cells = eventInfo.cells
                assert cells is not None, "cells should not be None"
                ids.add(cells[0].id)

        return ids

    def get_amount_of_executions(self):
        total = 0
        for entry in self.log_entries:
            event_name = entry.eventDetail.eventName
            if event_name == "CellExecuteEvent":
                total += 1

        return total

    def get_event_count(self):
        return len(self.log_entries)

    def get_event_by_index(self, index: int) -> Optional[NotebookLogEntry]:
        if 0 <= index < len(self.log_entries):
            return self.log_entries[index]
        return None

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
    
    def get_final_state(self):
        return self.log_entries[-1].eventDetail.eventInfo
    
    def get_text_similarity(self, other: str):
        similarity_scores = []
        for entry in self.log_entries:
            eventInfo = entry.eventDetail.eventInfo
            if eventInfo and hasattr(eventInfo, 'text'):
                similarity = SequenceMatcher(None, eventInfo.text, other).ratio()
                similarity_scores.append(similarity)

        if similarity_scores:
            return max(similarity_scores)
        return 0.0

        # return SequenceMatcher(None, self.body, other).ratio()
