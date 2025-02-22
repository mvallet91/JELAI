from datetime import datetime
from difflib import SequenceMatcher
from typing import Sequence

from log_processor.notebook_log.notebook_activity_composite import (
    NotebookActivityComposite,
)
from log_processor.notebook_log.notebook_cell_activity import NotebookCellActivity


class NotebookCellActivityComposite(NotebookActivityComposite, NotebookCellActivity):
    """
    All notebook activities that happend in a single notebook cell.
    """

    def __init__(self, cell_activities: Sequence[NotebookCellActivity]):
        self.cell_activities = cell_activities

        super().__init__(cell_activities)

    def check_invariants(self):
        super().check_invariants()

        # Check that sub activities do not overlap
        for i in range(len(self.cell_activities)):
            for j in range(i + 1, len(self.cell_activities)):
                assert (
                    self.cell_activities[i].get_start_time()
                    >= self.cell_activities[j].get_end_time()
                    or self.cell_activities[j].get_start_time()
                    >= self.cell_activities[i].get_end_time()
                ), "Sub activities should not overlap"

        for sub_activity in self.cell_activities:
            sub_activity.check_invariants()

    def get_similarity_between_cell_states(self, time1: datetime, time2: datetime):
        id = self.get_cell_id()
        end_result = self.get_state_of_cell_at(id, time1)
        current_result = self.get_state_of_cell_at(id, time2)
        return SequenceMatcher(None, end_result, current_result).ratio()

    def get_overview(self, level=1) -> str:
        return (
            f"{'#' * level} Notebook summary of cell {self.get_cell_id()}\n\n"
            f"Worked on from {self.get_start_time()} to {self.get_end_time()}\\\n"
            f"Completion time = {self.get_completion_time()}\\\n"
            f"Tab switches = {self.get_amount_of_tab_switches()}\\\n"
            f"Times executed = {self.get_amount_of_executions()} times\\\n"
            f"Runtime errors = {self.get_amount_of_runtime_errors()}\\\n"
            f"Edit cycles = {self.get_amount_of_edit_cycles()}\\\n"
            f"Similarity between initial and final state = {round(self.get_similarity_between_cell_states(self.get_start_time(), self.get_end_time()), 2)}\\\n"
            f"{'#' * (level + 1)} Initial state\n\n"
            f"```python\n{self.get_state_of_cell_at(self.get_cell_id(), self.get_start_time())}\n```\n\n"
            f"{'#' * (level + 1)} Final state\n\n"
            f"```python\n{self.get_state_of_cell_at(self.get_cell_id(), self.get_end_time())}\n```\n\n"
        )
