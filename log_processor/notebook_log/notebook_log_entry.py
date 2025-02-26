from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from log_processor.chat_log.notebook_content.notebook_content import NotebookContent


@dataclass
class NotebookCell:
    @staticmethod
    def load(dict: Dict[str, Any]):
        return NotebookCell(dict.get("id"), dict["index"])

    id: Optional[str]
    index: int


@dataclass
class NotebookKernelError:
    @staticmethod
    def load(dict: Dict[str, Any]):
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

        seconds = dict["eventTime"] / 1000
        eventTime = datetime.fromtimestamp(seconds)

        return NotebookEventDetail(
            dict["eventName"],
            eventTime,
            eventInfo,
        )

    eventName: str
    eventTime: datetime
    eventInfo: Optional[NotebookEventInfo]


class NotebookState:
    @staticmethod
    def load(dict: dict[str, Any]):
        notebookContent = None
        if dict["notebookContent"] is not None:
            notebookContent = NotebookContent.load(dict["notebookContent"])

        return NotebookState(
            dict.get("sessionID"),
            dict["notebookPath"],
            notebookContent,
        )

    def __init__(
        self,
        sessionID: Optional[str],
        notebookPath: str,
        notebookContent: Optional[NotebookContent],
    ):
        self.sessionID = sessionID
        self.notebookPath = notebookPath
        self.notebookContent = notebookContent


@dataclass
class NotebookLogEntry:
    @staticmethod
    def load(dict: Any):
        eventDetail = NotebookEventDetail.load(dict["eventDetail"])
        notebookState = NotebookState.load(dict["notebookState"])

        return NotebookLogEntry(eventDetail, notebookState)

    eventDetail: NotebookEventDetail
    notebookState: NotebookState
