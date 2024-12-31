from typing import List

from log_processor.notebook_log.notebook_activity import NotebookActivity
from log_processor.notebook_log.notebook_log_entry import NotebookLogEntry


class NotebookCellActivity(NotebookActivity):
    """
    Notebook logs that happend during a continous span of working on a single cell
    """

    def __init__(
        self,
        log_entries: List[NotebookLogEntry],
    ):
        super().__init__(log_entries)

    def check_invariants(self):
        super().check_invariants()

        # Check that all cells have the same index
        indexes = self.get_cell_indexes()
        assert len(indexes) == 1, "All cells should have the same index"

        # Check that there is exactly one cell id
        ids = self.get_cell_ids()
        assert len(ids) == 1, "There should be one cell id"

    def get_cell_id(self):
        ids = self.get_cell_ids()
        assert len(ids) == 1, "There should be one cell id"
        return ids.pop()
    
    def get_cell_index(self):
        indexes = self.get_cell_indexes()
        assert len(indexes) == 1, "All cells should have the same index"
        return indexes.pop()
