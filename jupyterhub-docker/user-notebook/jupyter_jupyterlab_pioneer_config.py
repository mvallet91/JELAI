import getpass
username = getpass.getuser()

c.JupyterLabPioneerApp.exporters = [
    {
        # writes telemetry data to local file
        "type": "file_exporter",
        "args": {
            "path": f"/home/{username}/work/logs/log"
        },
    },
]

c.JupyterLabPioneerApp.activeEvents = [
    {"name": "ActiveCellChangeEvent", "logWholeNotebook": False},
    {"name": "CellAddEvent", "logWholeNotebook": False},
    {"name": "CellEditEvent", "logWholeNotebook": False},
    {"name": "CellExecuteEvent", "logWholeNotebook": True},
    {"name": "CellRemoveEvent", "logWholeNotebook": False},
    {"name": "ClipboardCopyEvent", "logWholeNotebook": False},
    {"name": "ClipboardCutEvent", "logWholeNotebook": False},
    {"name": "ClipboardPasteEvent", "logWholeNotebook": False},
    {"name": "NotebookHiddenEvent", "logWholeNotebook": False},
    {"name": "NotebookOpenEvent", "logWholeNotebook": True},
    {"name": "NotebookSaveEvent", "logWholeNotebook": False},
    {"name": "NotebookScrollEvent", "logWholeNotebook": False},
    {"name": "NotebookVisibleEvent", "logWholeNotebook": False}
]
