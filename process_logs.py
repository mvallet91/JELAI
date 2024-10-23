import os
import json
import logging
import asyncio
import sys
from watchgod import awatch
from datetime import datetime
from collections import OrderedDict
from utils import load_log_file, reconstruct_cell_contents

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class LogFileListener:
    """Listens to the log file and processes it when specific events occur."""

    def __init__(self, log_file_path, processed_logs_dir):
        self.log_file_path = os.path.abspath(log_file_path)
        self.processed_logs_dir = os.path.abspath(processed_logs_dir)
        self.last_processed_event_time = None

    async def watch_log_file(self):
        """Watch the log file for changes and process it on specific events."""
        async for changes in awatch(self.log_file_path):
            for change_type, path in changes:
                if change_type.name == 'modified':
                    logging.info(f"Detected modification in: {path}")
                    await self.process_log_file()

    async def process_log_file(self):
        """Process the log file if a CellExecuteEvent is detected."""
        try:
            log_data = load_log_file(self.log_file_path)
            if not log_data:
                return

            # Check if the last event is a CellExecuteEvent
            last_event = log_data[-1].get('eventDetail', {}).get('eventName', '')
            if last_event == 'CellExecuteEvent':
                logging.info("CellExecuteEvent detected. Processing the entire log file...")
                events, event_dict = reconstruct_cell_contents(log_data)

                # Save the processed log data
                await self.save_processed_logs(event_dict)
        except Exception as e:
            logging.error(f"Error processing log file: {e}")

    async def save_processed_logs(self, event_dict):
        """Save the processed logs to the specified directory."""
        if not event_dict:
            return

        # Extract session ID and notebook name from the first entry
        first_entry = event_dict[0]
        session_id = first_entry.get('notebookState', {}).get('sessionID', 'unknown_session')
        notebook_name = first_entry.get('notebook', 'unknown_notebook').replace(':', '_')

        # Use the notebook name to create a consistent output filename
        # This ensures alignment with the chat filenames
        output_filename = f"{session_id}_{notebook_name}.json"
        output_file_path = os.path.join(self.processed_logs_dir, output_filename)

        try:
            with open(output_file_path, 'w', encoding='utf-8') as file:
                json.dump(event_dict, file, indent=4, default=str)
            logging.info(f"Processed log written to {output_file_path}")
        except Exception as e:
            logging.error(f"Error writing processed log to {output_file_path}: {e}")

async def main(log_file_path, processed_logs_dir):
    """Main function to set up the log file listener and watch for changes."""
    # Ensure the processed logs directory exists
    if not os.path.exists(processed_logs_dir):
        os.makedirs(processed_logs_dir)

    log_listener = LogFileListener(log_file_path, processed_logs_dir)
    logging.info(f"Log processing started, watching file: {log_file_path}")
    await log_listener.watch_log_file()

if __name__ == "__main__":

    if len(sys.argv) != 3:
        print("Usage: python process_logs.py <file_path> <processed_logs_dir>")
        sys.exit(1)
    log_file_path = sys.argv[1]
    processed_logs_dir = sys.argv[2]

    try:
        asyncio.run(main(log_file_path, processed_logs_dir))
    except KeyboardInterrupt:
        logging.info("Interrupted. Exiting...")
