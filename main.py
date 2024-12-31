from log_processor.chat_log.chat_log import ChatLog
from log_processor.log import Log
from log_processor.notebook_log.notebook_log import NotebookLog

if __name__ == "__main__":
    chat_log = ChatLog.load_from_file("output/test.chat")
    notebook_log = NotebookLog.load_from_file("output/log")
    log = Log(chat_log, notebook_log)

    for task in log.get_cell_activities():
        print(task.get_summary())
        print()

    interactions = log.chat_log.get_interactions()
    for interaction in interactions:
        print(interaction.get_waiting_time())
        print()
