import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from regex import D


@dataclass
class Cell:
    id: str
    index: int


@dataclass
class KernelError:
    errorName: str
    errorValue: str
    traceback: List[str]


@dataclass
class EventInfo:
    index: Optional[int] = None
    doc: Optional[List[str]] = None
    changes: Optional[List[Union[int, List[Union[int, str]]]]] = None
    cells: Optional[List[Cell]] = None
    environ: Optional[Dict[str, str]] = None
    success: Optional[bool] = None
    kernelError: Optional[KernelError] = None


@dataclass
class EventDetail:
    eventName: str
    eventTime: int
    eventInfo: EventInfo


@dataclass
class NotebookState:
    sessionID: str
    notebookPath: str
    notebookContent: Optional[Any]


@dataclass
class LogEntry:
    eventDetail: EventDetail
    notebookState: NotebookState
