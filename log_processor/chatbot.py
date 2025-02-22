import json
import os

import requests


class Chatbot:
    def __init__(self):
        self.cache: dict[str, str] = {}
        server = os.getenv("OPEN_WEB_UI_SERVER")
        if server is None:
            raise ValueError("OPEN_WEB_UI_SERVER is not set")
        self.url = f"{server}/api/chat/completions"
        key = os.getenv("OPEN_WEB_UI_API_KEY")
        if key is None:
            raise ValueError("OPEN_WEB_UI_API_KEY is not set")
        self.key: str = key

    def ask_question(self, question):
        if question in self.cache:
            return self.cache[question]

        return self.ask_question_without_cache(question)

    def ask_question_without_cache(self, question):
        headers = {
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": "llama3.2:latest",
            "messages": [{"role": "user", "content": question}],
        }

        response = requests.post(self.url, headers=headers, json=data)

        self.cache[question] = response.json()["choices"][0]["message"]["content"]
        return self.cache[question]

    def save_cache(self, path: str):
        with open(path, "w") as file:
            file.write(json.dumps(self.cache))

    def load_cache(self, path: str):
        if os.path.exists(path):
            with open(path, "r") as file:
                self.cache = json.load(file)
