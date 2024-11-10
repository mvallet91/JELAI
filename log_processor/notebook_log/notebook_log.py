import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from log_processor.notebook_log.log_entry import (
    EventDetail,
    EventInfo,
    LogEntry,
    NotebookState,
)
from log_processor.sub_task import SubTask
from log_processor.task import Task


class NotebookLog:
    log_entries: List[LogEntry]

    def __init__(self, log_entries: List[LogEntry]):
        self.log_entries = log_entries

    def get_event_count(self):
        return len(self.log_entries)

    def get_event_by_index(self, index: int) -> Optional[LogEntry]:
        if 0 <= index < len(self.log_entries):
            return self.log_entries[index]
        return None

    def split_into_subtasks(self) -> List[SubTask]:
        current_subtask = SubTask([])
        subtasks = {"first": current_subtask}

        self.log_entries.sort(key=lambda x: x.eventDetail.eventTime)

        for entry in self.log_entries:

            # New subtasks when switching cells
            event_name = entry.eventDetail.eventName
            if event_name == "ActiveCellChangeEvent":
                cells = entry.eventDetail.eventInfo.cells
                assert cells is not None, "cells should not be None"
                cell_id = cells[0]["id"]
                if cell_id not in subtasks:
                    subtasks[cell_id] = SubTask([])
                current_subtask = subtasks[cell_id]

            current_subtask.log_entries.append(entry)

        return list(subtasks.values())

    def split_into_tasks(self) -> List[Task]:
        tasks = {}
        subtasks = self.split_into_subtasks()

        for subtask in subtasks:
            task_id = subtask.get_task_id()
            if task_id not in tasks:
                tasks[task_id] = Task(task_id)
            tasks[task_id].subtasks.append(subtask)

        return list(tasks.values())


def load_notebook_log(file_path: str) -> NotebookLog:
    with open(file_path, "r", encoding="utf-8") as file:
        data = file.read()
        data = "[" + data[:-1] + "]"
        data = json.loads(data)

    log_entries = [
        LogEntry(
            eventDetail=EventDetail(
                eventName=entry["eventDetail"]["eventName"],
                eventTime=entry["eventDetail"]["eventTime"],
                eventInfo=EventInfo(**entry["eventDetail"]["eventInfo"]),
            ),
            notebookState=NotebookState(**entry["notebookState"]),
        )
        for entry in data
    ]

    return NotebookLog(log_entries)
