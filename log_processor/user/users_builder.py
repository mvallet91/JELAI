import os

from log_processor.user.user import User
from log_processor.user.users import Users


class UsersBuilder:

    def __init__(self, verbose=False):
        self.users = {}
        self.verbose = verbose
    
    def load_log_directory(
        self, log_directory: str
    ):
        if self.verbose:
            print("Loading users from directory")

        # Extract all notebook logs
        for file_name in os.listdir(log_directory):
            path = os.path.join(log_directory, file_name)
            if os.path.isfile(path):

                # Add notebook log file path to user
                username = file_name.replace("jupyter-", "").replace("-log", "")
                user_data = self.users.get(username, {})
                notebook_log_file_paths = user_data.get("notebook_log_file_paths", [])
                notebook_log_file_paths.append(path)
                user_data["notebook_log_file_paths"] = notebook_log_file_paths
                self.users[username] = user_data
    
    def load_volumes_directory(
        self, volumes_directory: str
    ):

        if self.verbose:
            print("Finding users in volumes directory")

        # Extract all chat logs and notebooks
        for folder_name in os.listdir(volumes_directory):
            path = os.path.join(volumes_directory, folder_name)
            if os.path.isdir(path) and not folder_name.startswith("_"):
                username = folder_name
                if self.verbose:
                    print(f"Finding data of user {username}")
                user_data = self.users.get(username, {})
                for file_name in os.listdir(path):
                    file_path = os.path.join(path, file_name)
                    if os.path.isfile(file_path):
                        if file_name.endswith(".ipynb"):

                            # Add notebook file path to user
                            notebook_file_paths = user_data.get(
                                "notebook_file_paths", []
                            )
                            notebook_file_paths.append(file_path)
                            user_data["notebook_file_paths"] = notebook_file_paths

                        elif file_name.endswith(".chat"):

                            # Add chat log file path to user
                            chat_log_file_paths = user_data.get(
                                "chat_log_file_paths", []
                            )
                            chat_log_file_paths.append(file_path)
                            user_data["chat_log_file_paths"] = chat_log_file_paths
                self.users[username] = user_data
    
    def load_grades(self):
        pass

    def build(self, chat_message_analyser):
        build_users = Users(chat_message_analyser)
        # Load data into objects
        for username, user_data in self.users.items():
            try:
                if self.verbose:
                    print(f"Loading user {username}")

                user = User(username, chat_message_analyser)
                user.load_chat_log_files(user_data.get("chat_log_file_paths", []))
                user.load_notebook_log_files(
                    user_data.get("notebook_log_file_paths", [])
                )
                user.load_notebook_files(user_data.get("notebook_file_paths", []))

                build_users.users.append(user)
            except Exception as e:
                print(f"Error loading user {username}: {e}")
        return build_users