from typing import List

from log_processor.notebook_log.notebook_cell_sub_activity import (
    NotebookCellSubActivity,
)


class NotebookCellActivity:
    """
    Represents all notebook activity related to a single cell.

    Attributes:
        subtasks: A list of moment that the user spend on this task.
    """

    sub_activities: List[NotebookCellSubActivity]

    def __init__(self):
        self.sub_activities = []

    def get_correctness_score_at(self, time: float):
        raise NotImplementedError

    def get_time_notebook_open_until(self, time: float):
        """Time since last time that the notebook was opened until the given time."""

        raise NotImplementedError

    def get_completion_time(self):
        """Get the total time spent on this activity"""
        total = 0
        for sub_activity in self.sub_activities:
            total += sub_activity.get_completion_time()
        return total

    def get_amount_of_executions(self):
        """Get the total amount of executions of this activity"""
        total = 0
        for sub_activity in self.sub_activities:
            total += sub_activity.get_amount_of_executions()
        return total

    def get_amount_of_execution_errors(self):
        """Get the total amount of execution errors of this activity"""
        total = 0
        for sub_activity in self.sub_activities:
            total += sub_activity.get_amount_of_execution_errors()
        return total

    def get_cell_id(self):
        """Get the cell id of this activity"""
        return self.sub_activities[0].get_cell_id()

    def get_summary(self) -> str:
        return (
            f"==Notebook summary for cell {self.get_cell_id()}==\n"
            f"Times executed = {self.get_amount_of_executions()} times with {self.get_amount_of_execution_errors()} errors.\n"
            f"Completion time = {self.get_completion_time()}"
        )

    def __str__(self):
        return f"Activity in cell {self.get_cell_id()} with {len(self.sub_activities)} sub activities"
