from log_processor.chat_log.chat_log import ChatLog
from log_processor.log import Log
from log_processor.notebook_log.notebook_log import NotebookLog

if __name__ == "__main__":
    chat_log = ChatLog.load_from_file("jupyterlab_data/testChat.chat")
    notebook_log = NotebookLog.load_from_file("jupyterlab_data/log")
    log = Log(chat_log, notebook_log)

    for task in log.get_cell_activities():
        print(task.get_summary())
        print()
