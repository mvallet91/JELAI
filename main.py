from log_processor.chat_log.chat_log import load_chat_log
from log_processor.log import Log
from log_processor.notebook_log.notebook_log import load_notebook_log

if __name__ == "__main__":
    chat_log = load_chat_log("jupyterlab_data/testChat.chat")
    notebook_log = load_notebook_log("jupyterlab_data/log")
    log = Log(chat_log, notebook_log)

    for task in log.get_cell_activities():
        print(task.get_summary())
        print()
