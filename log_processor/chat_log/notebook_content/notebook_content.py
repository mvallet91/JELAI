import ast
from difflib import SequenceMatcher
from typing import Any, Dict, List

from log_processor.chat_log.notebook_content.notebook__content_cell import (
    NotebookContentCell,
)


class NotebookContent:
    @staticmethod
    def load(dict: dict[str, Any]):
        return NotebookContent(
            dict["metadata"],
            dict["nbformat"],
            dict["nbformat_minor"],
            [NotebookContentCell.load(cell) for cell in dict["cells"]],
        )

    def __init__(
        self,
        metadata: Dict[str, Any],
        nbformat: int,
        nbformat_minor: int,
        cells: List[NotebookContentCell],
    ):
        self.metadata = metadata
        self.nbformat = nbformat
        self.nbformat_minor = nbformat_minor
        self.cells = cells

    def get_source_as_string(self):
        """
        Get the content of the notebook as a string.
        """
        return "\n\n".join([cell.source for cell in self.cells])

    def get_valid_outputs(self):
        """
        Get the outputs of the notebook.
        """
        outputs = []
        for cell in self.cells:
            assert len(cell.outputs) <= 1, "Only one output per cell is supported"
            output = cell.outputs[0]
            for output in cell.outputs:
                if output.name == "stdout":
                    outputs.append(output.text)
                elif output.name == "error":
                    outputs.append(output.ename)

        return outputs

    def get_ast_difference_ratio(self, other: "NotebookContent"):
        """
        Get the difference between this notebook content and another notebook content as a percentage.
        """

        ast1 = ast.dump(ast.parse(self.get_source_as_string()))
        ast2 = ast.dump(ast.parse(other.get_source_as_string()))

        similarity = SequenceMatcher(None, ast1, ast2).ratio()

        return similarity

    def get_output_difference_ratio(self, other: "NotebookContent"):
        """
        Get the difference between this notebook content and another notebook content as a percentage.
        """

        ast1 = ast.dump(ast.parse(self.get_source_as_string()))
        ast2 = ast.dump(ast.parse(other.get_source_as_string()))

        similarity = SequenceMatcher(None, ast1, ast2).ratio()

        return similarity
