from typing import Sequence

from log_processor.notebook_log.notebook_activity import NotebookActivity
from datetime import timedelta

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

    def get_completion_time(self):
        """
        Get the total time spent on this activity
        
        Note: Different from NotebookActivity, because this one does not count breaks between editing sessions
        """
        total = timedelta(seconds=0)
        for sub_activity in self._activities:
            total += sub_activity.get_completion_time()
        return total
