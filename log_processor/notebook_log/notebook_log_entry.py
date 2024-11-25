from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union


@dataclass
class NotebookCell:
    @staticmethod
    def load(dict: Any):
        return NotebookCell(dict["id"], dict["index"])

    id: str
    index: int


@dataclass
class NotebookKernelError:
    @staticmethod
    def load(dict: Any):
        return NotebookKernelError(
            dict["errorName"],
            dict["errorValue"],
            dict["traceback"],
        )

    errorName: str
    errorValue: str
    traceback: List[str]


@dataclass
class NotebookEventInfo:
    @staticmethod
    def load(dict: Dict[str, Any]):
        cells = None
        if "cells" in dict:
            cells = [NotebookCell.load(cell) for cell in dict["cells"]]
        kernelError = None
        if kernelError in dict:
            kernelError = NotebookKernelError.load(
                dict["kernelError"],
            )

        return NotebookEventInfo(
            dict.get("index"),
            dict.get("doc"),
            dict.get("changes"),
            cells,
            dict.get("environ"),
            dict.get("success"),
            kernelError,
            dict.get("selection"),
        )

    index: Optional[int] = None
    doc: Optional[List[str]] = None
    changes: Optional[List[Union[int, List[Union[int, str]]]]] = None
    cells: Optional[List[NotebookCell]] = None
    environ: Optional[Dict[str, str]] = None
    success: Optional[bool] = None
    kernelError: Optional[NotebookKernelError] = None
    selection: Optional[str] = None


@dataclass
class NotebookEventDetail:
    @staticmethod
    def load(dict: Any):
        eventInfo = None
        if dict["eventInfo"] is not None:
            eventInfo = NotebookEventInfo.load(dict["eventInfo"])

        return NotebookEventDetail(
            dict["eventName"],
            dict["eventTime"] / 1000,
            eventInfo,
        )

    eventName: str
    eventTime: int
    eventInfo: Optional[NotebookEventInfo]


@dataclass
class NotebookState:
    @staticmethod
    def load(dict: Any):
        return NotebookState(
            dict["sessionID"],
            dict["notebookPath"],
            dict["notebookContent"],
        )

    sessionID: str
    notebookPath: str
    notebookContent: Optional[Any]


@dataclass
class NotebookLogEntry:
    @staticmethod
    def load(dict: Any):
        eventDetail = NotebookEventDetail.load(dict["eventDetail"])
        notebookState = NotebookState.load(dict["notebookState"])

        return NotebookLogEntry(eventDetail, notebookState)

    eventDetail: NotebookEventDetail
    notebookState: NotebookState
