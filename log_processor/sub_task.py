from typing import List

from log_processor.notebook_log.notebook_log import LogEntry


class SubTask:
    """Represents a continous span of working on a single task"""

    log_entries: List[LogEntry]

    def __init__(self, log_entries):
        self.log_entries = log_entries

    def get_start_time(self):
        self.log_entries.sort(key=lambda x: x.eventDetail.eventTime)
        return self.log_entries[0].eventDetail.eventTime

    def get_end_time(self):
        self.log_entries.sort(key=lambda x: x.eventDetail.eventTime)
        return self.log_entries[-1].eventDetail.eventTime

    def get_duration(self):
        return self.get_end_time() - self.get_start_time()

    def get_task_id(self):
        for entry in self.log_entries:
            event_name = entry.eventDetail.eventName
            if event_name == "ActiveCellChangeEvent":
                cells = entry.eventDetail.eventInfo.cells
                assert cells is not None, "cells should not be None"
                cell_id = cells[0]["id"]
                return cell_id

        return None
