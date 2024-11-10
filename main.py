from log_processor.chat_log.chat_log import load_chat_log
from log_processor.notebook_log.notebook_log import load_notebook_log

if __name__ == "__main__":
    chat_log = load_chat_log("jupyterlab_data/hi.chat")
    notebook_log = load_notebook_log("jupyterlab_data/log")
    print(chat_log.get_message_count())
    for task in (notebook_log.split_into_tasks()):
        print(task)

