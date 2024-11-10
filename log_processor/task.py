from typing import List
from log_processor.sub_task import SubTask


class Task:
    subtasks: List[SubTask]

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.subtasks = []
    
    def __str__(self):
        return f"Task {self.task_id} with {len(self.subtasks)} subtasks"
    
    