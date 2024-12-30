from difflib import SequenceMatcher
from typing import List, Sequence

from log_processor.notebook_log.notebook_activity_composite import (
    NotebookActivityComposite,
)
from log_processor.notebook_log.notebook_cell_activity import NotebookCellActivity


class NotebookCellActivityComposite(NotebookActivityComposite):
    """
    All notebook activities that happend in a single notebook cell.
    """

    cell_activities: Sequence[NotebookCellActivity]

    def __init__(self, cell_activities: Sequence[NotebookCellActivity]):
        self.cell_activities = cell_activities

        super().__init__(cell_activities)

    def check_invariants(self):
        super().check_invariants()

        # Check that there is exactly one cell id
        ids = self.get_cell_ids()
        assert len(ids) == 1, "There should be exactly one cell id"

        # Check that sub activities do not onverlap
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

    def get_similarity_with_end_result_at(self, time: int):
        id = self.get_cell_id()
        end_result = self.get_state_of_cell_at(id, self.get_end_time())
        current_result = self.get_state_of_cell_at(id, time)
        if end_result is None or current_result is None:
            print("None result")
            return 0
        return SequenceMatcher(None, end_result, current_result).ratio()

    def get_cell_id(self):
        """Get the cell id of this activity"""
        ids = self.get_cell_ids()
        assert len(ids) == 1, "There should be exactly one cell id"
        return ids.pop()

    def get_summary(self) -> str:
        return (
            f"== Notebook summary of cell {self.get_cell_id()} ==\n"
            f"Times executed = {self.get_amount_of_executions()} times with {self.get_amount_of_execution_errors()} errors.\n"
            f"Completion time = {round(self.get_completion_time(), 1)}s"
        )

    def __str__(self):
        return f"Activity in cell {self.get_cell_id()} with {len(self.cell_activities)} sub activities"
