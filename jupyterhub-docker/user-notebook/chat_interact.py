import os
import sys
import re
import time
import json
import logging
import uuid
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from langserve import RemoteRunnable

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Check if the script is running in a Docker container
def is_running_in_docker():
    return os.path.exists('/.dockerenv')

# Set the URL based on the environment
if is_running_in_docker():
    chat_chain_url = "http://host.docker.internal:8002"
else:
    chat_chain_url = "http://localhost:8002"

# Set up the RemoteRunnable for the chat_chain
chat_chain = RemoteRunnable(chat_chain_url)

class ChatHandler(FileSystemEventHandler):
    def __init__(self, chat_directory, loop):
        self.chat_directory = os.path.abspath(chat_directory)
        self.last_processed_messages = {}
        self.working_message_ids = {}
        self.loop = loop
        logging.info(f"Monitoring directory: {self.chat_directory}")

    def on_modified(self, event):
        if event.is_directory:
            return
        file_path = os.path.abspath(event.src_path)
        if file_path.endswith('.chat'):
            logging.info(f"Detected modification in: {file_path}")
            self.handle_new_message(file_path)

    def handle_new_message(self, file_path):
        try:
            with open(file_path, 'r+') as file:
                content = json.load(file)

                # Add context from processed logs if available
                session_id = self.extract_session_id_from_filename(file_path)
                processed_log_data = self.get_processed_log_data(session_id)
                content['processed_log'] = processed_log_data

                # Check if 'Juno' user exists
                if 'Juno' not in content['users']:
                    # Create a new user entry for 'Juno'
                    content['users']['Juno'] = {
                        "display_name": "Juno",
                        "username": "Juno",
                        "avatar_url": None,
                        "initials": "J",
                        "name": "Juno",
                        "color": "var(--jp-collaborator-color7)"
                    }
                    # Save the updated content back to the file
                    file.seek(0)
                    json.dump(content, file, indent=4)
                    file.truncate()

                if not content["messages"]:
                    return
                last_message = content["messages"][-1]
                if last_message != self.last_processed_messages.get(file_path) and "automated" not in last_message:
                    self.last_processed_messages[file_path] = last_message
                    logging.info(f"New message in {file_path}: {last_message['body']}")
                    asyncio.run_coroutine_threadsafe(self.automate_response(last_message, content, file_path), self.loop)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.error(f"Error reading file {file_path}: {e}")

    def extract_session_id_from_filename(self, file_path):
        # Assuming session_id is part of the file name, extract it
        file_name = os.path.basename(file_path)
        session_id = file_name[:-5]  # Remove the .chat extension
        # Sanitize the session_id: lowercase, replace spaces with underscores, remove non-alphanumeric characters
        session_id = re.sub(r'[^a-z0-9_]', '', session_id.replace(" ", "_").lower())
        return session_id

    def format_log_entry(self, log):
        """Format a single log entry into a readable string."""
        event_type = log['event']
        cell_index = log.get('cell_index', 'Unknown')
        
        event_formatters = {
            "Executed cells": lambda: f"Executed cell {cell_index} with input: {log.get('input', 'No input provided')}, "
                                    f"output: {log.get('output', 'No output provided')}",
            "Edited cell": lambda: f"Edited cell {cell_index} with content: {log.get('content', 'No content provided')}",
            "Added new cell": lambda: f"Added a new cell at index {cell_index}",
            "Deleted cell": lambda: f"Deleted cell at index {cell_index}",
            "Moved cell": lambda: f"Moved cell from index {log.get('from_index', 'Unknown')} to {cell_index}",
            "Cell output": lambda: f"Output generated for cell {cell_index}: {log.get('output', 'No output provided')}",
            "Pasted content": lambda: f"Pasted content at cell {cell_index}, content: {log.get('content', 'No content provided')}",
            "CellExecuteEvent": lambda: f"Executed cell {cell_index} at {log.get('time', 'Unknown time')}",
            "Opened notebook": lambda: f"Opened notebook '{log.get('notebook', 'Unknown notebook')}' at {log.get('time', 'Unknown time')}",
            "Closed notebook": lambda: f"Closed notebook '{log.get('notebook', 'Unknown notebook')}' at {log.get('time', 'Unknown time')}",
            "Notebook became visible": lambda: f"Notebook '{log.get('notebook', 'Unknown notebook')}' became visible at {log.get('time', 'Unknown time')}"
}

        return event_formatters.get(event_type, lambda: f"Event: {event_type} at cell {cell_index}")()

    def get_processed_log_data(self, session_id):
        # Locate the processed_logs directory
        processed_logs_dir = os.path.join(self.chat_directory, 'processed_logs')

        # Check if the directory exists
        if not os.path.exists(processed_logs_dir):
            logging.error(f"Processed logs directory not found: {processed_logs_dir}")
            return None

        # Find the first (or only) file in the processed_logs directory
        try:
            log_file_name = next(os.path.join(processed_logs_dir, f) for f in os.listdir(processed_logs_dir) if f.endswith('.json'))
        except StopIteration:
            logging.error("No log files found in processed_logs directory.")
            return None

        # Open and read the log file
        with open(log_file_name, 'r') as log_file:
            try:
                logs = json.load(log_file)
            except json.JSONDecodeError as e:
                logging.error(f"Error decoding JSON from log file: {e}")
                return None

        # Sanitize session_id (already sanitized before calling this function)
        sanitized_session_id = re.sub(r'[^a-z0-9_]', '', session_id.replace(" ", "_").lower())

        # Find the log with the matching notebook, strip prefix (e.g., "RTC:") and ".ipynb" suffix
        matching_logs = []
        # TODO - improve the matching logic, verify the log file location and structure
        
        for log in logs:
            notebook = log.get('notebook', '').lower()
            if notebook:
                # Extract the notebook name by removing the prefix and suffix
                notebook_name = notebook.split(":")[-1].replace(".ipynb", "")
                sanitized_notebook_name = re.sub(r'[^a-z0-9_]', '', notebook_name.replace(" ", "_").lower())
                if sanitized_notebook_name == sanitized_session_id:
                    matching_logs.append(log)

        # Send the last 6 matching logs, formatted as text
        if matching_logs:
            last_logs = matching_logs[-6:]  # Get the last 6 logs
            formatted_logs = [self.format_log_entry(log) for log in last_logs]  # Format each log entry
            return "\n".join(formatted_logs)  # Return as a single string, separated by newlines
        
        else:
            logging.info(f"No matching logs found for session ID: {sanitized_session_id} , {sanitized_notebook_name}")
            return None


    async def automate_response(self, message, content, file_path):
        # Start a background task to send "working on it" messages
        working_task = asyncio.create_task(self.send_working_messages(content, file_path))
        file_name = os.path.basename(file_path)
        # Clean the file name, remove the .chat extension
        file_name = file_name.replace(".chat", "")
        sanitized_file_name = re.sub(r'[^a-z0-9_]', '', file_name.replace(" ", "_").lower())
        logging.info(f"file_name: {sanitized_file_name}")
        sanitized_sender = re.sub(r'[^a-z0-9_]', '', message.get('sender', '').replace(" ", "_").lower())
        session_id = f"{sanitized_sender}_{sanitized_file_name}"
        logging.info(f"session_id: {session_id}")

        # Send the message to the LLM app and get the response
        # response_text = await self.get_llm_response(message["body"], session_id)
        logging.info(f"Message: {message['body']}")
        logging.info(f"Context: {content.get('processed_log')}")
        response_text = await self.get_llm_response(message["body"], session_id, context=content.get('processed_log'))
        
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
                "sender": "Juno",
                "type": "msg",
                "id": str(uuid.uuid4()),
                "time": time.time(),
                "raw_time": False,
                "automated": True
            }
            logging.info(f"Sending response to {file_path}: {response}")
            self.replace_working_message(response, content, file_path)

    async def get_llm_response(self, user_message, session_id, context=None):
        try:
            # Ensure context is a dict
            if isinstance(context, list):
                context = {"notebook_events": context}
            # If context is a string, convert it to a dict
            if isinstance(context, str):
                context = {"notebook_events": [context]}

            input_data = {
                "human_input": user_message,
                "context": context or {}
            }
            logging.info(f"Input data: {input_data}")
            response = await chat_chain.ainvoke(input_data, {'configurable': {'session_id': session_id}})
            response = "".join(response)  # Convert the response from list to string if needed
            return response
        except Exception as e:
            logging.error(f"Error getting LLM response: {e}")
            return None


    async def send_working_messages(self, content, file_path):
        working_messages = [
            "I'm working on it...",
            "Just a moment, please...",
            "Processing your request...",
            "Hang tight, I'm on it..."
        ]
        idx = 0
        self.working_message_ids[file_path] = str(uuid.uuid4())
        while True:
            # Create or update the "working on it" message
            working_message = {
                "body": working_messages[idx],
                "sender": "auto_responder",
                "type": "msg",
                "id": self.working_message_ids[file_path],  # Use the same ID for the "working on it" message
                "time": time.time(),
                "raw_time": False,
                "automated": True  # Flag to identify automated messages
            }
            self.update_working_message(working_message, content, file_path)
            idx = (idx + 1) % len(working_messages)
            await asyncio.sleep(5 + idx % 3)  # Wait 5-7 seconds

    def update_working_message(self, working_message, content, file_path):
        try:
            with open(file_path, 'r+') as file:
                # Find and update the existing "working on it" message
                for i, message in enumerate(content["messages"]):
                    if message["id"] == self.working_message_ids[file_path]:
                        content["messages"][i] = working_message
                        break
                else:
                    # If not found, append it
                    content["messages"].append(working_message)
                file.seek(0)
                json.dump(content, file, indent=4)
                file.truncate()
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.error(f"Error updating working message in {file_path}: {e}")

    def replace_working_message(self, response, content, file_path):
        try:
            with open(file_path, 'r+') as file:
                # Find and replace the "working on it" message with the final response
                for i, message in enumerate(content["messages"]):
                    if message["id"] == self.working_message_ids[file_path]:
                        content["messages"][i] = response
                        break
                else:
                    # If not found, append it
                    content["messages"].append(response)
                file.seek(0)
                json.dump(content, file, indent=4)
                file.truncate()
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.error(f"Error replacing working message in {file_path}: {e}")

def main(directory_path):
    chat_directory = os.path.abspath(directory_path)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    event_handler = ChatHandler(chat_directory, loop)
    observer = Observer()
    observer.schedule(event_handler, path=chat_directory, recursive=False)
    observer.start()
    try:
        print("Monitoring started. Press Ctrl+C to exit.")
        loop.run_forever()
    except KeyboardInterrupt:
        print("Keyboard interrupt received. Stopping...")
    finally:
        observer.stop()
        observer.join()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python chat_interact.py <directory_path>")
        sys.exit(1)
    directory_path = sys.argv[1]
    main(directory_path)
