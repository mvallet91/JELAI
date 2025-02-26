from typing import Any, Dict, List, Optional


class NotebookContentCell:
    @staticmethod
    def load(dict: Dict[str, Any]):
        return NotebookContentCell(
            dict["id"],
            dict["cell_type"],
            dict["source"],
            dict["metadata"],
            dict.get("outputs", []),
            dict.get("execution_count", None),
        )

    def __init__(
        self,
        id: str,
        cell_type: str,
        source: str,
        metadata: Dict[str, Any],
        outputs: List[Dict[str, Any]],
        execution_count: Optional[int],
    ):
        self.id = id
        self.cell_type = cell_type
        self.source = source
        self.metadata = metadata
        self.outputs = outputs
        self.execution_count = execution_count
