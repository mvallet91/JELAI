from typing import Sequence

from log_processor.notebook_log.notebook_activity import NotebookActivity


class NotebookActivityComposite(NotebookActivity):
    """
    Collection of activities
    """

    _activities: Sequence[NotebookActivity]

    def __init__(self, activities: Sequence[NotebookActivity]):
        self._activities = activities

        super().__init__(
            [
                log_entry
                for sub_activity in activities
                for log_entry in sub_activity._log_entries
            ]
        )

    def get_time_notebook_open_until(self, time: float):
        """Time since last time that the notebook was opened until the given time."""

        raise NotImplementedError

    def get_completion_time(self):
        """Get the total time spent on this activity"""
        total = 0
        for sub_activity in self._activities:
            total += sub_activity.get_completion_time()
        return total

    def get_amount_of_executions(self):
        """Get the total amount of executions of this activity"""
        total = 0
        for sub_activity in self._activities:
            total += sub_activity.get_amount_of_executions()
        return total

    def get_amount_of_runtime_errors(self):
        """Get the total amount of execution errors of this activity"""
        total = 0
        for sub_activity in self._activities:
            total += sub_activity.get_amount_of_runtime_errors()
        return total

    def get_cell_ids(self):
        """Get the cell id of this activity"""
        ids = set()
        for activity in self._activities:
            ids.update(activity.get_cell_ids())
        return ids
