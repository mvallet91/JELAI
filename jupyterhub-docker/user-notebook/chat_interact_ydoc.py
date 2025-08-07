# chat_interact_ydoc.py - YDoc-based Implementation with Typing Indicators
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

# YDoc imports
try:
    from jupyter_ydoc import ydocs
    from pycrdt import Doc
    from jupyterlab_chat.models import User, NewMessage, Message
    from typing import TYPE_CHECKING
    
    YChat = ydocs['chat']  # Get YChat class from registry
    
    if TYPE_CHECKING:
        YChatType = YChat
    else:
        YChatType = None
    YDOC_AVAILABLE = True
except ImportError:
    YDOC_AVAILABLE = False
    logging.warning("YDoc not available. Install with: pip install jupyterlab-chat pycrdt")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - CHAT_INTERACT_YDOC - %(message)s')

# Configuration
TA_URL_BASE = os.getenv("TA_MIDDLEWARE_URL", "http://localhost:8004")
TA_URL = f"{TA_URL_BASE}/receive_student_message"
LOG_ENTRY_LIMIT = 10

class YDocChatHandler:
    """Handles YDoc-based chat document operations"""
    
    def __init__(self, chat_directory: str):
        self.chat_directory = os.path.abspath(chat_directory)
        self.chat_docs: Dict[str, Any] = {}  # YChat instances
        self._doc_locks: Dict[str, asyncio.Lock] = {}
        
    def get_or_create_chat_doc(self, file_path: str):  # Returns YChat instance
        """Get existing YChat document or create new one"""
        if file_path not in self.chat_docs:
            # Create new YDoc with awareness
            from pycrdt import Doc, Awareness
            ydoc = Doc()
            awareness = Awareness(ydoc)
            ychat = YChat(ydoc)
            
            # Store both YChat and awareness
            self.chat_docs[file_path] = {
                'ychat': ychat,
                'awareness': awareness
            }
            
            # Load existing content if file exists
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        content = json.load(f)
                    
                    # Set the document content using YChat's set method
                    ychat.set(json.dumps(content))
                    logging.info(f"Loaded existing chat document: {file_path}")
                except Exception as e:
                    logging.error(f"Error loading chat file {file_path}: {e}")
            
            self._doc_locks[file_path] = asyncio.Lock()
            
            # Set up observer for changes
            ychat.observe(lambda topic, event: self._on_document_change(file_path, topic, event))
            
        return self.chat_docs[file_path]['ychat']
    
    def _on_document_change(self, file_path: str, topic: str, event):
        """Handle document changes and save to file"""
        try:
            # Only save on specific topics to avoid overwriting user messages
            if topic not in ['messages', 'users', 'metadata']:
                logging.debug(f"Skipping save for topic: {topic}")
                return
                
            ychat = self.chat_docs[file_path]['ychat']
            
            # Get the current content from YDoc
            ydoc_content = json.loads(ychat.get())
            
            # Read the current file content to preserve user messages
            current_content = {"messages": [], "users": {}, "metadata": {}}
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        current_content = json.load(f)
                except Exception as e:
                    logging.warning(f"Could not read current file {file_path}: {e}")
            
            # Merge YDoc changes with current content
            if "messages" in ydoc_content:
                # Add new Juno messages to existing messages
                current_messages = current_content.get("messages", [])
                ydoc_messages = ydoc_content.get("messages", [])
                
                # Find new messages (messages that are in YDoc but not in current file)
                current_ids = {msg.get("id") for msg in current_messages if msg.get("id")}
                for ydoc_msg in ydoc_messages:
                    if ydoc_msg.get("id") and ydoc_msg.get("id") not in current_ids:
                        current_messages.append(ydoc_msg)
                
                current_content["messages"] = current_messages
            
            if "users" in ydoc_content:
                current_content["users"].update(ydoc_content["users"])
            
            if "metadata" in ydoc_content:
                current_content["metadata"].update(ydoc_content["metadata"])
            
            # Write atomically
            temp_file = file_path + '.tmp'
            with open(temp_file, 'w') as f:
                json.dump(current_content, f, indent=4)
            os.rename(temp_file, file_path)
                
            logging.debug(f"Saved changes to {file_path} (topic: {topic})")
        except Exception as e:
            logging.error(f"Error saving changes to {file_path}: {e}")
    
    async def ensure_juno_user(self, file_path: str):
        """Ensure Juno user exists in the chat"""
        async with self._doc_locks.get(file_path, asyncio.Lock()):
            ychat = self.get_or_create_chat_doc(file_path)
            
            existing_user = ychat.get_user("Juno")
            if not existing_user:
                juno_user = User(
                    username="Juno",
                    name="Juno",
                    display_name="Juno",
                    initials="J",
                    color="var(--jp-collaborator-color7)"
                )
                
                ychat.set_user(juno_user)
                logging.info(f"Added Juno user to {file_path}")

    async def set_typing_indicator(self, file_path: str, is_typing: bool = True):
        """Set typing indicator for Juno using awareness"""
        try:
            async with self._doc_locks.get(file_path, asyncio.Lock()):
                ychat = self.get_or_create_chat_doc(file_path)
                awareness = self.chat_docs[file_path]['awareness']
                
                # Get existing Juno user or create if doesn't exist
                existing_user = ychat.get_user("Juno")
                if not existing_user:
                    await self.ensure_juno_user(file_path)
                
                # Set typing status through awareness
                if is_typing:
                    awareness.set_local_state_field("user", {
                        "username": "Juno",
                        "name": "Juno AI Assistant", 
                        "display_name": "Juno",
                        "initials": "J",
                        "color": "#2196F3",
                        "typing": True
                    })
                    logging.info("Set Juno typing indicator ON")
                else:
                    awareness.set_local_state_field("user", {
                        "username": "Juno",
                        "name": "Juno AI Assistant",
                        "display_name": "Juno", 
                        "initials": "J",
                        "color": "#2196F3",
                        "typing": False
                    })
                    logging.info("Set Juno typing indicator OFF")
                    
        except Exception as e:
            logging.error(f"Error setting typing indicator: {e}")
    
    async def add_message(self, file_path: str, message_text: str, sender: str = "Juno") -> str:
        """Add a message to the chat using YDoc"""
        async with self._doc_locks.get(file_path, asyncio.Lock()):
            ychat = self.get_or_create_chat_doc(file_path)
            
            # Create new message (ID is generated automatically)
            new_message = NewMessage(
                body=message_text,
                sender=sender
            )
            
            # Add the message and get the ID
            message_id = ychat.add_message(new_message)
            
            logging.info(f"Added message to {file_path}: {message_text[:50]}...")
            return message_id
    
    async def update_message_by_id(self, file_path: str, message_id: str, new_text: str):
        """Update an existing message by ID"""
        async with self._doc_locks.get(file_path, asyncio.Lock()):
            ychat = self.get_or_create_chat_doc(file_path)
            
            # Find message by ID
            messages = ychat.get_messages()
            for msg in messages:
                if msg.id == message_id:
                    # Create updated message
                    updated_msg = Message(
                        id=msg.id,
                        body=new_text,
                        sender=msg.sender,
                        time=time.time(),
                        raw_time=False
                    )
                    ychat.update_message(updated_msg)
                    logging.debug(f"Updated message {message_id} in {file_path}")
                    return True
            
            logging.warning(f"Message {message_id} not found in {file_path}")
            return False
    
    def cleanup(self):
        """Clean up resources"""
        for chat_data in self.chat_docs.values():
            try:
                chat_data['ychat'].dispose()
            except:
                pass
            try:
                chat_data['awareness'].stop()
            except:
                pass
        self.chat_docs.clear()
        self._doc_locks.clear()

class ChatHandlerYDoc(FileSystemEventHandler):
    def __init__(self, chat_directory, loop, processed_logs_dir):
        self.chat_directory = os.path.abspath(chat_directory)
        self.processed_logs_dir = os.path.abspath(processed_logs_dir)
        os.makedirs(self.chat_directory, exist_ok=True)
        os.makedirs(self.processed_logs_dir, exist_ok=True)
        self.last_processed_messages: Dict[str, Dict[str, Any]] = {}
        self.loop = loop
        
        # Initialize YDoc handler if available
        if YDOC_AVAILABLE:
            self.ydoc_handler = YDocChatHandler(chat_directory)
        else:
            self.ydoc_handler = None
            logging.error("YDoc not available - falling back to basic JSON operations")
        
        logging.info(f"Monitoring directory: {self.chat_directory}")
        logging.info(f"Looking for processed logs in: {self.processed_logs_dir}")

    def on_modified(self, event):
        if event.is_directory:
            return
        
        file_path = os.path.abspath(event.src_path)
        
        # Skip temporary files (starting with .~ or ._)
        filename = os.path.basename(file_path)
        if filename.startswith('.~') or filename.startswith('._'):
            return
            
        if file_path.endswith('.chat') and os.path.exists(file_path):
            logging.info(f"Detected modification in: {file_path}")
            self.loop.call_soon_threadsafe(self.handle_new_message, file_path)

    def handle_new_message(self, file_path: str):
        try:
            if not os.path.exists(file_path):
                logging.warning(f"File {file_path} was modified but no longer exists. Skipping.")
                return
                
            # Skip temporary files again as safeguard
            filename = os.path.basename(file_path)
            if filename.startswith('.~') or filename.startswith('._'):
                return

            # Read current content for message detection
            with open(file_path, 'r') as file:
                try:
                    content = json.load(file)
                except json.JSONDecodeError as e:
                    logging.error(f"Could not decode JSON from {file_path}. Error: {e}. Skipping.")
                    return
                    
                if not isinstance(content, dict) or "messages" not in content or "users" not in content:
                    logging.error(f"Invalid chat file structure in {file_path}. Skipping.")
                    return

                # Ensure Juno user exists (async operation)
                if self.ydoc_handler:
                    asyncio.create_task(self.ydoc_handler.ensure_juno_user(file_path))

                if not content["messages"]:
                    return

                last_message = content["messages"][-1]

                # Check if message is not from Juno and hasn't been processed
                if (last_message != self.last_processed_messages.get(file_path) and
                        last_message.get("sender") != "Juno" and
                        "body" in last_message and "sender" in last_message):

                    self.last_processed_messages[file_path] = last_message
                    logging.info(f"New message detected in {file_path} from {last_message['sender']}: '{last_message['body'][:50]}...'")

                    student_id = last_message.get('sender', 'unknown_student')
                    message_text = last_message['body']
                    file_name = os.path.basename(file_path)

                    session_id_for_logs = self.extract_session_id_from_filename(file_path)
                    processed_log_data = self.get_processed_log_data(session_id_for_logs)

                    # Schedule the interaction task
                    if self.ydoc_handler:
                        asyncio.create_task(self.manage_interaction_ydoc(
                            file_path, student_id, message_text, processed_log_data, file_name
                        ))
                    else:
                        # Fallback to original implementation
                        logging.error("YDoc handler not available - no fallback implemented")

        except FileNotFoundError:
            logging.warning(f"File not found: {file_path}.")
        except PermissionError:
            logging.error(f"Permission denied: {file_path}.")
        except Exception as e:
            logging.error(f"Error handling {file_path}: {e}", exc_info=True)

    async def manage_interaction_ydoc(self, file_path: str, student_id: str, message_text: str, 
                                     processed_log_data: Optional[str], file_name: str):
        """Manage interaction using YDoc with typing indicators"""
        if not self.ydoc_handler:
            logging.error("YDoc handler not available")
            return
            
        # Decide whether to send full logs or limited slice
        session_id_for_logs = self.extract_session_id_from_filename(file_path)
        if message_text.strip().lower() == "/report":
            processed_log_data = self.get_processed_log_data(session_id_for_logs, limit=None)

        final_response_text = None
        error_occurred = False

        try:
            # Set typing indicator ON
            await self.ydoc_handler.set_typing_indicator(file_path, is_typing=True)

            # Call TA and WAIT for the response
            async with httpx.AsyncClient() as client:
                logging.info(f"Sending message to TA at {TA_URL} and waiting for response...")
                ta_response = await client.post(
                    TA_URL,
                    json={
                        "student_id": student_id,
                        "message_text": message_text,
                        "processed_logs": processed_log_data,
                        "file_name": file_name
                    },
                    timeout=120.0
                )
                ta_response.raise_for_status()

                response_data = ta_response.json()
                final_response_text = response_data.get("final_response", "Error: TA response format incorrect.")
                logging.info(f"Received final response from TA: '{final_response_text[:100]}...'")

        except httpx.RequestError as e:
            logging.error(f"Error sending message to TA: {e}")
            final_response_text = "Sorry, I couldn't reach the tutoring service."
            error_occurred = True
        except httpx.HTTPStatusError as e:
            logging.error(f"TA returned error status {e.response.status_code}: {e.response.text}")
            try:
                ta_error_detail = e.response.json().get("detail", "an internal error occurred")
            except json.JSONDecodeError:
                ta_error_detail = e.response.text[:100]
            final_response_text = f"Sorry, error processing request: {ta_error_detail}"
            error_occurred = True
        except Exception as e:
            logging.error(f"Unexpected error during TA interaction: {e}", exc_info=True)
            final_response_text = "Sorry, an unexpected error occurred."
            error_occurred = True
        finally:
            # Turn OFF typing indicator
            await self.ydoc_handler.set_typing_indicator(file_path, is_typing=False)

            # Add final response message
            if final_response_text:
                await self.ydoc_handler.add_message(
                    file_path, 
                    final_response_text, 
                    sender="Juno"
                )

    def extract_session_id_from_filename(self, file_path: str) -> str:
        file_name = os.path.basename(file_path)
        session_id = file_name.replace(".chat", "")
        session_id = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', session_id).lower()
        return session_id

    def format_log_entry(self, log: Dict[str, Any]) -> str:
        event_type = log.get('event', 'Unknown Event')
        cell_index = log.get('cell_index', 'N/A')
        timestamp = log.get('time', '')
        details = ""
        if event_type == "Executed cells":
            details = f"Input: {log.get('input', '')[:200]} Output: {log.get('output', '')[:200]}"
        if event_type == "Executed cells with error":
            details = f"Input: {log.get('content', '')[:200]} Error: {log.get('error', '')[:200]}"
        if event_type in ["Edited cell", "Pasted content"]:
            details = f"Content: {log.get('content', '')[:200]}"
        return f"{timestamp} - {event_type} (Cell {cell_index}): {details}"

    def get_processed_log_data(self, session_id: str, limit: Optional[int] = LOG_ENTRY_LIMIT) -> Optional[str]:
        logging.debug(f"Looking for logs matching session_id: {session_id} in {self.processed_logs_dir}")
        try:
            matching_log_files = [f for f in os.listdir(self.processed_logs_dir) if f.endswith('.json')]
            if not matching_log_files:
                logging.warning(f"No *.json log files found in {self.processed_logs_dir}")
                return None
            
            # Collect logs from all JSON files
            all_logs = []
            for log_file_name in matching_log_files:
                log_file_path = os.path.join(self.processed_logs_dir, log_file_name)
                logging.debug(f"Reading log file: {log_file_path}")
                
                try:
                    with open(log_file_path, 'r') as log_file:
                        file_logs = json.load(log_file)
                        
                    if not isinstance(file_logs, list):
                        logging.warning(f"Log file not a list, skipping: {log_file_path}")
                        continue
                        
                    all_logs.extend(file_logs)
                    logging.debug(f"Added {len(file_logs)} logs from {log_file_name}")
                    
                except json.JSONDecodeError:
                    logging.error(f"Error decoding JSON, skipping: {log_file_path}")
                    continue
                except Exception as e:
                    logging.error(f"Error reading log file {log_file_path}: {e}")
                    continue
            
            if not all_logs:
                logging.warning(f"No valid logs found in any JSON files")
                return None
                
            logging.info(f"Loaded {len(all_logs)} total logs from {len(matching_log_files)} files")

            matching_logs = []
            for log in all_logs:
                notebook_path = log.get('notebook', '')
                if notebook_path:
                    notebook_name = os.path.basename(notebook_path).removesuffix(".ipynb")
                    sanitized_notebook_name = re.sub(r'^rtc[^a-zA-Z0-9]*', '', notebook_name, flags=re.IGNORECASE)
                    sanitized_notebook_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', sanitized_notebook_name).lower()
                    if sanitized_notebook_name == session_id:
                        matching_logs.append(log)

            if not matching_logs:
                logging.info(f"No matching logs for '{session_id}' in processed logs")
                return None

            # Apply limit if given, otherwise use entire session
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
        except FileNotFoundError:
            logging.warning(f"Log dir not found: {self.processed_logs_dir}")
            return None
        except Exception as e:
            logging.error(f"Error processing logs for {session_id}: {e}", exc_info=True)
            return None

def main(directory_path, processed_logs_dir):
    chat_directory = os.path.abspath(directory_path)
    processed_logs_path = os.path.abspath(processed_logs_dir)

    # Setup Asyncio Event Loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Setup Watchdog
    event_handler = ChatHandlerYDoc(chat_directory, loop, processed_logs_path)
    observer = Observer()
    observer.schedule(event_handler, path=chat_directory, recursive=False)
    observer.start()
    logging.info("Watchdog observer started.")

    # Run Observer Loop
    try:
        print(f"Monitoring directory: {chat_directory}")
        print(f"Using processed logs from: {processed_logs_path}")
        print(f"TA URL: {TA_URL}")
        print(f"YDoc available: {YDOC_AVAILABLE}")
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
        
        # Cleanup YDoc handler
        if hasattr(event_handler, 'ydoc_handler') and event_handler.ydoc_handler:
            event_handler.ydoc_handler.cleanup()
        
        # Stop the loop if it's still running
        if loop.is_running():
            loop.stop()
        print("Chat Interact YDoc script finished.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python chat_interact_ydoc.py <chat_directory_path> <processed_logs_dir_path>")
        print("Example: python chat_interact_ydoc.py ./chats ./processed_logs")
        sys.exit(1)

    directory_path_arg = sys.argv[1]
    processed_logs_dir_arg = sys.argv[2]

    main(directory_path_arg, processed_logs_dir_arg)
