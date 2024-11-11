from typing import List

from log_processor.sub_task import SubTask


class Task:
    """
    All information about a single task. A single task is a single code block in which a specific question is implemented.

    Attributes:
        description: The description of the task.
        subtasks: A list of moment that the user spend on this task.
    """

    description: str

    subtasks: List[SubTask]

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.subtasks = []

    def get_correctness_score_at(self, time: float):
        raise NotImplementedError

    def get_time_notebook_open_until(self, time: float):
        """Time since last time that the notebook was opened until the given time."""
        raise NotImplementedError

    def __str__(self):
        return f"Task {self.task_id} with {len(self.subtasks)} subtasks"
