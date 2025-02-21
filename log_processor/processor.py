import os

from dotenv import load_dotenv

from log_processor.users import Users


class Processor:
    def __init__(self):
        load_dotenv()

        path = "output/users.pkl"

        if os.path.exists(path):
            self.processor = Users.load_from_file(path)
        else:
            self.processor = Users()
            self.processor.load_users_from_directory(
                "W:/staff-umbrella/DataStorageJELAI/CDL First Run/_logs",
                "W:/staff-umbrella/DataStorageJELAI/CDL First Run",
                verbose=True,
            )
            self.processor.save_to_file(path)

    def run(self):
        print(self.processor.get_summary())
