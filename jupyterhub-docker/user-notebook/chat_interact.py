# chat_interact.py (Synchronous Call Version)
import os
import sys
import re
import time
import json
import logging
import uuid
import asyncio
import random
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import httpx
from typing import Optional, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - CHAT_INTERACT - %(message)s')

# --- Configuration ---
# def is_running_in_docker():
#     return os.path.exists('/.dockerenv')

# if is_running_in_docker():
#     TA_URL = "http://host.docker.internal:8004/receive_student_message"
# else:
#     TA_URL = "http://localhost:8004/receive_student_message"

TA_URL_BASE = os.getenv("TA_MIDDLEWARE_URL", "http://localhost:8004")
TA_URL = f"{TA_URL_BASE}/receive_student_message"
LOG_ENTRY_LIMIT = 10

class ChatHandler(FileSystemEventHandler):
    def __init__(self, chat_directory, loop, processed_logs_dir):
        # (Initialization remains the same)
        self.chat_directory = os.path.abspath(chat_directory)
        self.processed_logs_dir = os.path.abspath(processed_logs_dir)
        os.makedirs(self.chat_directory, exist_ok=True)
        os.makedirs(self.processed_logs_dir, exist_ok=True)
        self.last_processed_messages: Dict[str, Dict[str, Any]] = {}
        self.working_message_ids: Dict[str, str] = {}
        self.loop = loop
        logging.info(f"Monitoring directory: {self.chat_directory}")
        logging.info(f"Looking for processed logs in: {self.processed_logs_dir}")

    def on_modified(self, event):
        if event.is_directory:
            return
        file_path = os.path.abspath(event.src_path)
        if file_path.endswith('.chat') and os.path.exists(file_path):
            logging.info(f"Detected modification in: {file_path}")
            self.loop.call_soon_threadsafe(self.handle_new_message, file_path)

    def handle_new_message(self, file_path: str):
        try:
            if not os.path.exists(file_path):
                logging.warning(f"File {file_path} was modified but no longer exists. Skipping.")
                return

            with open(file_path, 'r+') as file:
                try:
                    content = json.load(file)
                except json.JSONDecodeError:
                    logging.error(f"Could not decode JSON from {file_path}. Skipping.")
                    return
                if not isinstance(content, dict) or "messages" not in content or "users" not in content:
                    logging.error(f"Invalid chat file structure in {file_path}. Skipping.")
                    return

                if 'Juno' not in content['users']:
                    content['users']['Juno'] = {
                        "display_name": "Juno", "username": "Juno", "avatar_url": None,
                        "initials": "J", "name": "Juno", "color": "var(--jp-collaborator-color7)"
                    }
                    file.seek(0); json.dump(content, file, indent=4); file.truncate()
                    logging.info(f"Added Juno user to {file_path}")

                if not content["messages"]: return

                last_message = content["messages"][-1]

                if (last_message != self.last_processed_messages.get(file_path) and
                        not last_message.get("automated", False) and
                        "body" in last_message and "sender" in last_message):

                    self.last_processed_messages[file_path] = last_message
                    logging.info(f"New message detected in {file_path} from {last_message['sender']}: '{last_message['body'][:50]}...'")

                    student_id = last_message.get('sender', 'unknown_student')
                    message_text = last_message['body']
                    file_name = os.path.basename(file_path)

                    session_id_for_logs = self.extract_session_id_from_filename(file_path)
                    processed_log_data = self.get_processed_log_data(session_id_for_logs)

                    # --- Schedule the interaction task ---
                    asyncio.create_task(self.manage_interaction(content, file_path, student_id, message_text, processed_log_data, file_name))

        except FileNotFoundError: logging.warning(f"File not found: {file_path}.")
        except PermissionError: logging.error(f"Permission denied: {file_path}.")
        except Exception as e: logging.error(f"Error handling {file_path}: {e}", exc_info=True)

    async def manage_interaction(self, content, file_path, student_id, message_text, processed_log_data, file_name):
        """Sends message to TA, waits for response, updates chat file."""
        # decide whether to send full logs or limited slice
        session_id_for_logs = self.extract_session_id_from_filename(file_path)
        if message_text.strip().lower() == "/report":
            # no limit ⇒ full history
            processed_log_data = self.get_processed_log_data(session_id_for_logs, limit=None)
        # Start "working" messages
        working_task = asyncio.create_task(self.send_working_messages(content, file_path))

        final_response_message = None
        error_occured = False

        try:
            # Call TA and WAIT for the response
            async with httpx.AsyncClient() as client:
                logging.info(f"Sending message to TA at {TA_URL} and waiting for response...")
                ta_response = await client.post( # Use await here
                    TA_URL,
                    json={
                        "student_id": student_id,
                        "message_text": message_text,
                        "processed_logs": processed_log_data,
                        "file_name": file_name
                    },
                    timeout=120.0 # Increased timeout since TA does all work now
                )
                ta_response.raise_for_status() # Check if TA processing was successful (e.g., 200 OK)

                # Extract final response from TA's JSON payload
                response_data = ta_response.json()
                final_text = response_data.get("final_response", "Error: TA response format incorrect.")
                logging.info(f"Received final response from TA: '{final_text[:100]}...'")

                # Prepare the chat message structure
                final_response_message = {
                    "body": final_text, "sender": "Juno", "type": "msg",
                    "id": str(uuid.uuid4()), "time": time.time(),
                    "raw_time": False, "automated": True
                }

        except httpx.RequestError as e:
            logging.error(f"Error sending message to TA: {e}")
            final_response_message = {
                "body": "Sorry, I couldn't reach the tutoring service.", "sender": "Juno",
                "type": "msg", "id": str(uuid.uuid4()), "time": time.time(),
                "raw_time": False, "automated": True
            }
            error_occured = True
        except httpx.HTTPStatusError as e:
            logging.error(f"TA returned error status {e.response.status_code}: {e.response.text}")
            try:
                 ta_error_detail = e.response.json().get("detail", "an internal error occurred")
            except json.JSONDecodeError:
                 ta_error_detail = e.response.text[:100] # Use raw text if not JSON
            final_response_message = {
                "body": f"Sorry, error processing request: {ta_error_detail}", "sender": "Juno",
                "type": "msg", "id": str(uuid.uuid4()), "time": time.time(),
                "raw_time": False, "automated": True
            }
            error_occured = True
        except Exception as e:
            logging.error(f"Unexpected error during TA interaction: {e}", exc_info=True)
            final_response_message = {
                "body": "Sorry, an unexpected error occurred.", "sender": "Juno",
                "type": "msg", "id": str(uuid.uuid4()), "time": time.time(),
                "raw_time": False, "automated": True
            }
            error_occured = True
        finally:
            # Stop the "working" messages *before* writing the final response/error
            logging.debug(f"Cancelling working task for {file_path}")
            working_task.cancel()
            try:
                await working_task
            except asyncio.CancelledError:
                logging.debug(f"Working task cancelled successfully for {file_path}.")

            # --- Write Final Response/Error to Chat File ---
            if final_response_message:
                # Re-read current content just before writing
                try:
                    if not os.path.exists(file_path):
                         logging.error(f"File {file_path} disappeared before writing final response.")
                         return # Cannot write if file is gone

                    with open(file_path, 'r') as f: current_content = json.load(f)
                    self.replace_working_message(final_response_message, current_content, file_path)
                except Exception as write_err:
                     logging.error(f"Failed to write final/error message to {file_path}: {write_err}")

    def extract_session_id_from_filename(self, file_path: str) -> str:
        # (Same as before)
        file_name = os.path.basename(file_path)
        session_id = file_name.replace(".chat", "")
        session_id = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', session_id).lower()
        return session_id

    def format_log_entry(self, log: Dict[str, Any]) -> str:
       # (Same as before)
       event_type = log.get('event', 'Unknown Event')
       cell_index = log.get('cell_index', 'N/A')
       timestamp = log.get('time', '')
       details = ""
       if event_type == "Executed cells": details = f"Input: {log.get('input', '')[:200]} Output: {log.get('output', '')[:200]}"
       if event_type == "Executed cells with error": details = f"Input: {log.get('content', '')[:200]} Error: {log.get('error', '')[:200]}"
       if event_type in ["Edited cell", "Pasted content"]: details = f"Content: {log.get('content', '')[:200]}"
       return f"{timestamp} - {event_type} (Cell {cell_index}): {details}"

    def get_processed_log_data(self, session_id: str, limit: Optional[int] = LOG_ENTRY_LIMIT) -> Optional[str]:
        logging.debug(f"Looking for logs matching session_id: {session_id} in {self.processed_logs_dir}")
        try:
            matching_log_files = [ f for f in os.listdir(self.processed_logs_dir) if f.endswith('.json') ]
            if not matching_log_files:
                logging.warning(f"No *.json log files found in {self.processed_logs_dir}")
                return None
            
            # Find the most recently modified log file
            log_files_with_mtime = []
            for f in matching_log_files:
                file_path = os.path.join(self.processed_logs_dir, f)
                try:
                    mtime = os.path.getmtime(file_path)
                    log_files_with_mtime.append((f, mtime))
                except OSError:
                    continue
            
            if not log_files_with_mtime:
                logging.warning(f"No accessible log files found in {self.processed_logs_dir}")
                return None
                
            # Sort by modification time (most recent first) and take the first one
            most_recent_file = sorted(log_files_with_mtime, key=lambda x: x[1], reverse=True)[0][0]
            log_file_path = os.path.join(self.processed_logs_dir, most_recent_file)
            logging.info(f"Reading most recent log file: {log_file_path}")
            
            with open(log_file_path, 'r') as log_file:
                try: all_logs = json.load(log_file)
                except json.JSONDecodeError: logging.error(f"Error decoding JSON: {log_file_path}"); return None
                if not isinstance(all_logs, list): logging.error(f"Log file not a list: {log_file_path}"); return None

            matching_logs = []
            for log in all_logs:
                notebook_path = log.get('notebook', '')
                if notebook_path:
                    notebook_name = os.path.basename(notebook_path).removesuffix(".ipynb")
                    sanitized_notebook_name = re.sub(r'^rtc[^a-zA-Z0-9]*', '', notebook_name, flags=re.IGNORECASE)
                    sanitized_notebook_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', sanitized_notebook_name).lower()
                    if sanitized_notebook_name == session_id: matching_logs.append(log)

            if not matching_logs: logging.info(f"No matching logs for '{session_id}' in {log_file_path}"); return None

            # apply limit if given, otherwise use entire session
            if limit is not None and len(matching_logs) > limit:
                selected = matching_logs[-limit:]
            else:
                selected = matching_logs
            formatted_logs = [
                self.format_log_entry(log)
                for log in selected
                if log.get('event') not in ["Notebook became visible", "Closed notebook"]
            ]
            log_context = "\n".join(formatted_logs)
            logging.info(f"Found {len(formatted_logs)} relevant log entries.")
            return log_context
        except FileNotFoundError: logging.warning(f"Log dir not found: {self.processed_logs_dir}"); return None
        except Exception as e: logging.error(f"Error processing logs for {session_id}: {e}", exc_info=True); return None

    async def send_working_messages(self, content: Dict[str, Any], file_path: str):
        # (Same as before)
        working_phrases = [ "Juno is working on it...", "Just a moment, processing...", "Thinking...", "Checking notes...", ]
        idx = 0; message_id = str(uuid.uuid4())
        self.working_message_ids[file_path] = message_id
        logging.info(f"Started working messages for {file_path} with ID {message_id}")
        try:
            while True:
                working_message = {
                    "body": working_phrases[idx % len(working_phrases)], "sender": "Juno", "type": "msg",
                    "id": message_id, "time": time.time(), "raw_time": False, "automated": True
                }
                self.update_working_message(working_message, content, file_path)
                idx += 1
                await asyncio.sleep(random.uniform(3, 5.5)) # Random delay 
        except asyncio.CancelledError: logging.info(f"Stopped working messages for {file_path} (ID: {message_id})")
        except Exception as e: logging.error(f"Error in send_working_messages loop for {file_path}: {e}", exc_info=True)

    def update_working_message(self, working_message: Dict[str, Any], content: Dict[str, Any], file_path: str):
        # (Same as before - updates 'content' dict and writes to file)
        message_id = working_message["id"]; found = False
        current_messages = content.get("messages", [])
        for i, msg in enumerate(current_messages):
            if msg.get("id") == message_id: current_messages[i] = working_message; found = True; break
        if not found: current_messages.append(working_message)
        content["messages"] = current_messages
        try:
            with open(file_path, 'w') as file: json.dump(content, file, indent=4)
        except Exception as e: logging.error(f"Error writing working message to {file_path}: {e}")

    def replace_working_message(self, final_response: Dict[str, Any], content: Dict[str, Any], file_path: str):
        # (Same as before - replaces message by ID or appends, updates 'content' dict and writes file)
        working_message_id = self.working_message_ids.get(file_path); found = False
        current_messages = content.get("messages", [])
        if working_message_id:
            for i, msg in enumerate(current_messages):
                if msg.get("id") == working_message_id:
                    current_messages[i] = final_response; found = True
                    logging.info(f"Replaced working message {working_message_id} in {file_path}")
                    break
            if found: del self.working_message_ids[file_path] # Clean up ID
        if not found:
            logging.warning(f"Working message ID {working_message_id} not found in {file_path}. Appending response.")
            current_messages.append(final_response)
        content["messages"] = current_messages
        try:
            with open(file_path, 'w') as file: json.dump(content, file, indent=4)
        except Exception as e: logging.error(f"Error writing final response to {file_path}: {e}")
        

# --- Main Function ---
def main(directory_path, processed_logs_dir):
    chat_directory = os.path.abspath(directory_path)
    processed_logs_path = os.path.abspath(processed_logs_dir)

    # --- Setup Asyncio Event Loop ---
    try: loop = asyncio.get_running_loop()
    except RuntimeError: loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)

    # --- Setup Watchdog ---
    # Instantiate ChatHandler directly
    event_handler = ChatHandler(chat_directory, loop, processed_logs_path)
    observer = Observer()
    observer.schedule(event_handler, path=chat_directory, recursive=False)
    observer.start()
    logging.info("Watchdog observer started.")

    # --- Run Observer Loop ---
    try:
        print(f"Monitoring directory: {chat_directory}")
        print(f"Using processed logs from: {processed_logs_path}")
        print(f"TA URL: {TA_URL}")
        # REMOVED: print(f"Chat Interact receiver running...")
        print("Press Ctrl+C to exit.")
        # Run the asyncio loop forever to keep watchdog alive
        loop.run_forever()

    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Stopping...")
    finally:
        print("Stopping observer...")
        observer.stop()
        observer.join()
        print("Observer stopped.")
        # Stop the loop if it's still running
        if loop.is_running():
            loop.stop()
        # Close the loop cleanly
        # loop.close() # Closing might cause issues if tasks are pending shutdown
        print("Chat Interact script finished.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python chat_interact.py <chat_directory_path> <processed_logs_dir_path>")
        print("Example: python chat_interact.py ./chats ./processed_logs")
        sys.exit(1)

    directory_path_arg = sys.argv[1]
    processed_logs_dir_arg = sys.argv[2]

    main(directory_path_arg, processed_logs_dir_arg)