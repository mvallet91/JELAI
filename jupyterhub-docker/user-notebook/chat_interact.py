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
import hashlib
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import httpx
from typing import Optional, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - CHAT_INTERACT - %(message)s')

# --- Configuration ---
PROACTIVITY_URL_BASE = os.getenv("TA_MIDDLEWARE_URL", "http://localhost:8004")
PROACTIVITY_URL = f"{PROACTIVITY_URL_BASE}/evaluate_proactivity"
AGENT_CONFIG_URL = f"{PROACTIVITY_URL_BASE}/agent_config"

TA_URL_BASE = os.getenv("TA_MIDDLEWARE_URL", "http://localhost:8004")
TA_URL = f"{TA_URL_BASE}/receive_student_message"
LOG_ENTRY_LIMIT = 10

# --- Message Gateway ---
class MessageGateway:
    """Final filter — only clean student-facing messages reach the chat."""

    DEFAULT_BLOCKED_PATTERNS = [
        "NO_INTERVENTION", "[INTERNAL CONTEXT]", "[END INTERNAL",
        "Profile Hint", "Learning Objective", "should intervene",
        "The student seems", "The student is mostly", "The student has executed",
        "I notice the student", "Based on the logs", "Based on the context",
        "Question Classification:", "Technical Information:",
    ]

    def __init__(self, config: dict = None):
        gw_config = (config or {}).get("message_gateway", {})
        self.blocked_patterns = gw_config.get("blocked_patterns", self.DEFAULT_BLOCKED_PATTERNS)
        self.min_length = gw_config.get("min_message_length", 15)
        self.max_length = gw_config.get("max_message_length", 2000)
        logging.info(f"MessageGateway initialized with {len(self.blocked_patterns)} blocked patterns")

    def validate(self, text: str) -> tuple:
        """Returns (is_valid, cleaned_text). Rejects leaked internals."""
        if not text or not text.strip():
            return False, ""

        # Reject if it starts with NO_INTERVENTION
        if text.strip().upper().startswith("NO_INTERVENTION"):
            return False, ""

        # Strip any reasoning preamble (LLM sometimes prefixes analysis)
        cleaned = self._strip_reasoning_preamble(text)

        # Reject if blocked patterns remain in the cleaned text
        for pattern in self.blocked_patterns:
            if pattern.lower() in cleaned.lower():
                logging.warning(f"Gateway blocked message containing '{pattern}'")
                return False, ""

        # Length checks
        if len(cleaned.strip()) < self.min_length:
            logging.warning(f"Gateway blocked message: too short ({len(cleaned)} chars)")
            return False, ""
        if len(cleaned.strip()) > self.max_length:
            cleaned = cleaned[:self.max_length].rsplit(' ', 1)[0] + "..."

        return True, cleaned.strip()

    def _strip_reasoning_preamble(self, text: str) -> str:
        """Strip common LLM reasoning preambles before the actual message."""
        # Pattern: LLM writes analysis then double-newline then the actual message
        parts = text.split("\n\n")
        if len(parts) >= 2:
            # Check if the first part looks like internal reasoning
            first = parts[0].lower()
            reasoning_indicators = [
                "the student", "i should", "i will", "based on",
                "it looks like", "they seem", "they haven't",
                "analysis:", "observation:", "reasoning:"
            ]
            if any(indicator in first for indicator in reasoning_indicators):
                return "\n\n".join(parts[1:])
        return text


class ChatHandler(FileSystemEventHandler):
    def __init__(self, chat_directory, loop, processed_logs_dir):
        self.chat_directory = os.path.abspath(chat_directory)
        self.processed_logs_dir = os.path.abspath(processed_logs_dir)
        os.makedirs(self.chat_directory, exist_ok=True)
        os.makedirs(self.processed_logs_dir, exist_ok=True)
        self.last_processed_messages: Dict[str, Dict[str, Any]] = {}
        self.working_message_ids: Dict[str, str] = {}
        self.loop = loop
        
        # --- Proactivity state ---
        self.last_intervention_time: Dict[str, float] = {}   # chat_file -> timestamp
        self.last_log_hash: Dict[str, str] = {}              # chat_file -> hash of logs
        self.last_intervention_text: Dict[str, str] = {}     # chat_file -> last message text
        self.unanswered_count: Dict[str, int] = {}           # chat_file -> consecutive unanswered
        self.last_activity_time: float = time.time()         # for dynamic interval
        
        # --- Gateway and config ---
        self.agent_config = self._fetch_agent_config()
        self.gateway = MessageGateway(self.agent_config)
        
        logging.info(f"Monitoring directory: {self.chat_directory}")
        logging.info(f"Looking for processed logs in: {self.processed_logs_dir}")

    def _fetch_agent_config(self) -> dict:
        """Fetch central agent config from the middleware at startup."""
        try:
            response = httpx.get(AGENT_CONFIG_URL, timeout=5.0)
            if response.status_code == 200:
                config = response.json()
                logging.info(f"Loaded agent config from middleware: {list(config.keys())}")
                return config
        except Exception as e:
            logging.warning(f"Could not fetch agent config from middleware: {e}")
        # Return defaults
        return {
            "proactivity": {"min_cooldown_seconds": 300, "max_unanswered_interventions": 2, "wait_for_student_response": True,
                            "poll_interval_active": 30, "poll_interval_idle": 300, "idle_threshold_seconds": 180},
            "message_gateway": {"blocked_patterns": MessageGateway.DEFAULT_BLOCKED_PATTERNS, "min_message_length": 15}
        }


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
                    # Student sent a message — reset proactivity state
                    self._reset_unanswered_count(file_path)

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
        file_name = os.path.basename(file_path)
        session_id = file_name.replace(".chat", "")
        session_id = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', session_id).lower()
        return session_id

    def format_log_entry(self, log: Dict[str, Any]) -> str:
       event_type = log.get('event', 'Unknown Event')
       cell_index = log.get('cell_index', 'N/A')
       timestamp = log.get('time', '')
       source = log.get('source', 'jupyter')
       notebook = os.path.basename(log.get('notebook', ''))
       details = ""
       if event_type == "Executed cells": details = f"Input: {log.get('input', '')[:200]} Output: {log.get('output', '')[:200]}"
       if event_type == "Executed cells with error": details = f"Input: {log.get('content', '')[:200]} Error: {log.get('error', '')[:200]}"
       if event_type in ["Edited cell", "Pasted content"]: details = f"Content: {log.get('content', '')[:200]}"
       if event_type == "Edited Pad": details = f"Content: {log.get('content', '')[:500]}"
       return f"[{source.upper()}] {timestamp} - {event_type} ({notebook}, Cell {cell_index}): {details}"

    def get_processed_log_data(self, session_id: str, limit: Optional[int] = LOG_ENTRY_LIMIT) -> Optional[str]:
        """Aggregate logs from ALL processed JSON files — unified view across Jupyter + Etherpad."""
        logging.debug(f"Aggregating all logs from {self.processed_logs_dir}")
        try:
            matching_log_files = [f for f in os.listdir(self.processed_logs_dir) if f.endswith('.json')]
            if not matching_log_files:
                logging.warning(f"No *.json log files found in {self.processed_logs_dir}")
                return None
            
            # Aggregate ALL logs from ALL files (unified view)
            all_logs = []
            for fname in matching_log_files:
                log_file_path = os.path.join(self.processed_logs_dir, fname)
                try:
                    with open(log_file_path, 'r') as log_file:
                        logs = json.load(log_file)
                except json.JSONDecodeError:
                    logging.error(f"Error decoding JSON: {log_file_path}")
                    continue
                except Exception as e:
                    logging.error(f"Error reading {log_file_path}: {e}")
                    continue
                if not isinstance(logs, list):
                    logging.error(f"Log file not a list: {log_file_path}")
                    continue
                all_logs.extend(logs)

            if not all_logs:
                logging.info(f"No log entries found in any JSON file")
                return None

            # Filter out noise events
            relevant_logs = [
                log for log in all_logs
                if log.get('event') not in ["Notebook became visible", "Closed notebook"]
            ]

            if not relevant_logs:
                return None

            # Sort by time and apply limit
            relevant_logs.sort(key=lambda x: x.get('time', ''))
            if limit is not None and len(relevant_logs) > limit:
                selected = relevant_logs[-limit:]
            else:
                selected = relevant_logs

            formatted_logs = [self.format_log_entry(log) for log in selected]
            log_context = "\n".join(formatted_logs)
            logging.info(f"Found {len(formatted_logs)} relevant log entries across all sources.")
            return log_context
        except FileNotFoundError:
            logging.warning(f"Log dir not found: {self.processed_logs_dir}")
            return None
        except Exception as e:
            logging.error(f"Error processing logs: {e}", exc_info=True)
            return None

    async def send_working_messages(self, content: Dict[str, Any], file_path: str):
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
        
    async def proactivity_loop(self):
        """Adaptive proactivity loop with cooldown, dedup, and gateway filtering."""
        logging.info("Starting adaptive proactivity loop...")
        
        proactivity_cfg = self.agent_config.get("proactivity", {})
        min_cooldown = proactivity_cfg.get("min_cooldown_seconds", 300)
        max_unanswered = proactivity_cfg.get("max_unanswered_interventions", 2)
        wait_for_response = proactivity_cfg.get("wait_for_student_response", True)
        poll_active = proactivity_cfg.get("poll_interval_active", 30)
        poll_idle = proactivity_cfg.get("poll_interval_idle", 300)
        idle_threshold = proactivity_cfg.get("idle_threshold_seconds", 180)
        
        logging.info(f"Proactivity config: cooldown={min_cooldown}s, max_unanswered={max_unanswered}, "
                     f"poll_active={poll_active}s, poll_idle={poll_idle}s")
        
        while True:
            # Dynamic interval: poll faster when active, slower when idle
            since_activity = time.time() - self.last_activity_time
            poll_interval = poll_active if since_activity < idle_threshold else poll_idle
            await asyncio.sleep(poll_interval)
            
            try:
                chat_files = [
                    os.path.join(self.chat_directory, f)
                    for f in os.listdir(self.chat_directory)
                    if f.endswith('.chat')
                ]
                
                for file_path in chat_files:
                    if not os.path.exists(file_path):
                        continue
                    
                    try:
                        await self._evaluate_proactivity_for_chat(
                            file_path, min_cooldown, max_unanswered, wait_for_response
                        )
                    except Exception as e:
                        logging.error(f"Error in proactivity evaluation for {file_path}: {e}")
                        
            except Exception as e:
                logging.error(f"Error in proactivity loop: {e}")

    async def _evaluate_proactivity_for_chat(
        self, file_path: str, min_cooldown: int, max_unanswered: int, wait_for_response: bool
    ):
        """Evaluate proactivity for a single chat file with all safeguards."""
        
        # --- Check 1: Cooldown ---
        last_time = self.last_intervention_time.get(file_path, 0)
        if time.time() - last_time < min_cooldown:
            logging.debug(f"Cooldown active for {file_path}, skipping")
            return
        
        # --- Check 2: Max unanswered interventions ---
        if self.unanswered_count.get(file_path, 0) >= max_unanswered:
            logging.debug(f"Max unanswered ({max_unanswered}) reached for {file_path}, backing off")
            return
        
        # --- Read chat file ---
        with open(file_path, 'r') as f:
            content = json.load(f)
        
        messages = content.get("messages", [])
        
        # --- Check 3: Wait for student response ---
        if wait_for_response and messages:
            last_msg = messages[-1]
            if last_msg.get("automated", False) and last_msg.get("sender") == "Juno":
                logging.debug(f"Waiting for student response in {file_path}, skipping")
                return
        
        # --- Get student ID ---
        student_id = "unknown_student"
        for msg in reversed(messages):
            if not msg.get("automated", False):
                student_id = msg.get("sender", "unknown_student")
                break
        
        # --- Get logs ---
        file_name = os.path.basename(file_path)
        session_id = self.extract_session_id_from_filename(file_path)
        processed_log_data = self.get_processed_log_data(session_id, limit=20)
        
        if not processed_log_data:
            return
        
        # --- Check 4: Content hash dedup (skip if logs haven't changed) ---
        log_hash = hashlib.md5(processed_log_data.encode()).hexdigest()
        if self.last_log_hash.get(file_path) == log_hash:
            logging.debug(f"Logs unchanged for {file_path}, skipping LLM call")
            return
        self.last_log_hash[file_path] = log_hash
        
        # --- Call TA for evaluation ---
        async with httpx.AsyncClient() as client:
            logging.info(f"Evaluating proactivity for {student_id} ({file_name})...")
            response = await client.post(
                PROACTIVITY_URL,
                json={
                    "student_id": student_id,
                    "file_name": file_name,
                    "processed_logs": processed_log_data
                },
                timeout=60.0
            )
            response.raise_for_status()
            intervention_data = response.json()
            intervention_text = intervention_data.get("intervention", "NO_INTERVENTION")
        
        # --- Check 5: NO_INTERVENTION ---
        if not intervention_text or "NO_INTERVENTION" in intervention_text.upper():
            logging.info(f"No intervention needed for {student_id}")
            return
        
        # --- Check 6: Message Gateway (client-side final filter) ---
        is_valid, cleaned_text = self.gateway.validate(intervention_text)
        if not is_valid:
            logging.info(f"Gateway rejected proactive message for {student_id}")
            return
        
        # --- Check 7: Message dedup (don't repeat same message) ---
        if self.last_intervention_text.get(file_path) == cleaned_text:
            logging.info(f"Duplicate intervention for {file_path}, skipping")
            return
        
        # --- All checks passed: write the message ---
        logging.info(f"Proactive intervention for {student_id}: {cleaned_text[:80]}...")
        
        intervention_message = {
            "body": cleaned_text,
            "sender": "Juno",
            "type": "msg",
            "id": str(uuid.uuid4()),
            "time": time.time(),
            "raw_time": False,
            "automated": True
        }
        
        # Re-read file to avoid race conditions
        with open(file_path, 'r') as f:
            current_content = json.load(f)
        current_messages = current_content.get("messages", [])
        current_messages.append(intervention_message)
        current_content["messages"] = current_messages
        with open(file_path, 'w') as f:
            json.dump(current_content, f, indent=4)
        
        # Update state
        self.last_intervention_time[file_path] = time.time()
        self.last_intervention_text[file_path] = cleaned_text
        self.unanswered_count[file_path] = self.unanswered_count.get(file_path, 0) + 1
        
        logging.info(f"Proactive message written to {file_path} (unanswered count: {self.unanswered_count[file_path]})")

    def _reset_unanswered_count(self, file_path: str):
        """Called when a student sends a message — resets the unanswered counter."""
        if file_path in self.unanswered_count:
            self.unanswered_count[file_path] = 0
        self.last_activity_time = time.time()

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
    
    # Start proactivity loop
    loop.create_task(event_handler.proactivity_loop())

    # --- Run Observer Loop ---
    try:
        print(f"Monitoring directory: {chat_directory}")
        print(f"Using processed logs from: {processed_logs_path}")
        print(f"TA URL: {TA_URL}")
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