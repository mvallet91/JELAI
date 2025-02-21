import os
import pickle

from log_processor.user import User


class Users:
    users: list[User]

    @staticmethod
    def load_from_file(path: str):
        with open(path, "rb") as f:
            loaded_processor: Users = pickle.load(f)
            return loaded_processor

    def __init__(self):
        self.users = []

    def save_to_file(self, path: str):
        with open(path, "wb") as f:
            pickle.dump(self, f)

    def load_users_from_directory(
        self, log_directory: str, volumes_directory: str, verbose=False
    ):
        if verbose:
            print("Loading users from directory")

        users = {}

        # Extract all notebook logs
        for file_name in os.listdir(log_directory):
            path = os.path.join(log_directory, file_name)
            if os.path.isfile(path):

                # Add notebook log file path to user
                username = file_name.replace("jupyter-", "").replace("-log", "")
                user_data = users.get(username, {})
                notebook_log_file_paths = user_data.get("notebook_log_file_paths", [])
                notebook_log_file_paths.append(path)
                user_data["notebook_log_file_paths"] = notebook_log_file_paths
                users[username] = user_data

        # Extract all chat logs and notebooks
        for folder_name in os.listdir(volumes_directory):
            path = os.path.join(volumes_directory, folder_name)
            if os.path.isdir(path) and not folder_name.startswith("_"):
                username = folder_name
                if verbose:
                    print(f"Finding data of user {username}")
                user_data = users.get(username, {})
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
                users[username] = user_data

        # Load data into objects
        for username, user_data in users.items():
            try:
                if verbose:
                    print(f"Loading user {username}")

                user = User(username)
                user.load_chat_log_files(user_data.get("chat_log_file_paths", []))
                user.load_notebook_log_files(
                    user_data.get("notebook_log_file_paths", [])
                )
                user.load_notebook_files(user_data.get("notebook_file_paths", []))
                
                self.users.append(user)
            except Exception as e:
                print(f"Error loading user {username}: {e}")

    def get_summary(self):
        return "\n".join([user.get_summary() for user in self.users])
