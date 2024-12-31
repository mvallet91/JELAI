from log_processor.chat_log.chat_log import ChatLog
from log_processor.log import Log
from log_processor.notebook_log.notebook_log import NotebookLog

if __name__ == "__main__":
    log = Log.load_from_files("output/test.chat", "output/log")

    for task in log.get_cell_activities():
        print(task.get_summary())
        print()

    interactions = log.chat_log.get_interactions()
    for interaction in interactions:
        print(interaction.get_waiting_time())
        print()
