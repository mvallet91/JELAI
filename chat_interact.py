import os
import sys
import time
import json
import logging
import uuid
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from langserve import RemoteRunnable
from langchain_community.llms import Ollama

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

model = Ollama(model="llama2")

# Set up the RemoteRunnable for the chat_chain
# chat_chain = RemoteRunnable("http://localhost:9001/chat")
chat_chain = RemoteRunnable("http://localhost:8001")

class ChatHandler(FileSystemEventHandler):
    def __init__(self, chat_file, loop):
        self.chat_file = os.path.abspath(chat_file)
        self.last_processed_message = None
        self.working_message_id = None
        self.loop = loop
        self.load_last_message()
        logging.info(f"Monitoring file: {self.chat_file}")

    def load_last_message(self):
        try:
            with open(self.chat_file, 'r') as file:
                content = json.load(file)
                if content["messages"]:
                    self.last_processed_message = content["messages"][-1]
                logging.info(f"Loaded last message: {self.last_processed_message}")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.error(f"Error loading last message: {e}")
            self.last_processed_message = None

    def on_modified(self, event):
        if os.path.abspath(event.src_path) == self.chat_file:
            logging.info(f"Detected modification in: {event.src_path}")
            self.handle_new_message()

    def handle_new_message(self):
        try:
            with open(self.chat_file, 'r') as file:
                content = json.load(file)
                if not content["messages"]:
                    return
                last_message = content["messages"][-1]
                if last_message != self.last_processed_message and "automated" not in last_message:
                    self.last_processed_message = last_message
                    logging.info(f"New message: {last_message['body']}")
                    asyncio.run_coroutine_threadsafe(self.automate_response(last_message, content), self.loop)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.error(f"Error reading file: {e}")

    async def automate_response(self, message, content):
        # Start a background task to send "working on it" messages
        working_task = asyncio.create_task(self.send_working_messages(content))
        session_id = message.get('sender')
        # Send the message to the LLM app and get the response
        response_text = await self.get_llm_response(message["body"], session_id)
        
        # Cancel the "working on it" messages task
        working_task.cancel()
        try:
            await working_task
        except asyncio.CancelledError:
            pass

        if response_text:
            # Create a response message with the required structure
            response = {
                "body": response_text,
                "sender": "auto_responder",
                "type": "msg",
                "id": str(uuid.uuid4()),  # Generate a unique ID for the response
                "time": time.time(),
                "raw_time": False,
                "automated": True  # Flag to identify automated messages
            }
            logging.info(f"Sending response: {response}")
            self.replace_working_message(response, content)

    async def get_llm_response(self, user_message, session_id):
        try:

            ### ORIGINAL CHAT #########
            # Make an async request to the LLM app's chat endpoint
            # messages = ' '.join([message['body'] for message in content['messages']])
            # response = await chat_chain.ainvoke({"input": user_message, "messages": messages})
            ### ORIGINAL CHAT #########


            response = await chat_chain.ainvoke({"human_input": user_message}, {'configurable': { 'session_id': session_id } })
            
            # Convert the response from a list to a string
            response = "".join(response)
            return response
        except Exception as e:
            logging.error(f"Error getting LLM response: {e}")
            return None

    async def send_working_messages(self, content):
        working_messages = [
            "I'm working on it...",
            "Just a moment, please...",
            "Processing your request...",
            "Hang tight, I'm on it..."
        ]
        idx = 0
        self.working_message_id = str(uuid.uuid4())
        while True:
            # Create or update the "working on it" message
            working_message = {
                "body": working_messages[idx],
                "sender": "auto_responder",
                "type": "msg",
                "id": self.working_message_id,  # Use the same ID for the "working on it" message
                "time": time.time(),
                "raw_time": False,
                "automated": True  # Flag to identify automated messages
            }
            self.update_working_message(working_message, content)
            idx = (idx + 1) % len(working_messages)
            await asyncio.sleep(5 + idx % 3)  # Wait 5-7 seconds

    def update_working_message(self, working_message, content):
        try:
            with open(self.chat_file, 'r+') as file:
                # Find and update the existing "working on it" message
                for i, message in enumerate(content["messages"]):
                    if message["id"] == self.working_message_id:
                        content["messages"][i] = working_message
                        break
                else:
                    # If not found, append it
                    content["messages"].append(working_message)
                file.seek(0)
                json.dump(content, file, indent=4)
                file.truncate()
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.error(f"Error updating working message: {e}")

    def replace_working_message(self, response, content):
        try:
            with open(self.chat_file, 'r+') as file:
                # Find and replace the "working on it" message with the final response
                for i, message in enumerate(content["messages"]):
                    if message["id"] == self.working_message_id:
                        content["messages"][i] = response
                        break
                else:
                    # If not found, append it
                    content["messages"].append(response)
                file.seek(0)
                json.dump(content, file, indent=4)
                file.truncate()
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.error(f"Error replacing working message: {e}")

def main(filepath = None):
    if filepath:
        chat_file = filepath
    else:
        chat_file = './ChatPandas.chat'
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    event_handler = ChatHandler(chat_file, loop)
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(os.path.abspath(chat_file)), recursive=False)
    observer.start()
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == '-chatfile-path':
        filepath = args[1]
    main(filepath)
