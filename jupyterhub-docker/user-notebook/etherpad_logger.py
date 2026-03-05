import os
import time
import json
import logging
import httpx
import asyncio
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - ETHERPAD_LOGGER - %(message)s')

ETHERPAD_URL = os.getenv("ETHERPAD_URL", "http://etherpad:9001")
ETHERPAD_API_KEY = os.getenv("ETHERPAD_API_KEY", "jelai_secret_api_key_123")
POLL_INTERVAL = 10  # Seconds

# Format matching the one expected by utils.py / JupyterLab Pioneer logs
def _make_log_entry(content: str, notebook_path: str):
    return {
        "eventDetail": {
            "eventName": "PadEditEvent",
            "eventTime": int(time.time() * 1000),
            "content": content
        },
        "notebookState": {
            "notebookPath": notebook_path,
            "sessionID": "etherpad_session" 
        }
    }

async def poll_etherpad(pad_id: str, log_file_path: str):
    """
    Polls the Etherpad API for text changes. 
    If text changes, appends a PadEditEvent to the log tracking file.
    """
    last_text = None
    url = f"{ETHERPAD_URL}/api/1/getText"
    
    # We will pretend the pad is "attached" to a generic Etherpad notebook name
    notebook_path = f"{pad_id}.ipynb" 
    
    logging.info(f"Starting to poll Etherpad for padID: {pad_id} at {url}")

    async with httpx.AsyncClient() as client:
        while True:
            try:
                response = await client.get(url, params={"apikey": ETHERPAD_API_KEY, "padID": pad_id}, timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0:
                        current_text = data.get("data", {}).get("text", "")
                        
                        if last_text is not None and current_text != last_text:
                            logging.info(f"Pad {pad_id} changed! Length: {len(current_text)}")
                            
                            # Write event to log file
                            entry = _make_log_entry(current_text, notebook_path)
                            try:
                                # Append to the raw log file
                                with open(log_file_path, "a", encoding="utf-8") as f:
                                    f.write(json.dumps(entry) + ",\n")
                            except Exception as e:
                                logging.error(f"Failed to write to log file: {e}")

                        last_text = current_text
                    elif data.get("code") == 1 and data.get("message") == "padID does not exist":
                        # Pad hasn't been created yet
                        pass
                    else:
                        logging.warning(f"Etherpad API returned error code {data.get('code')}: {data.get('message')}")
                else:
                    logging.warning(f"Etherpad API returned status code {response.status_code}")
                    
            except httpx.RequestError as e:
                logging.error(f"Error connecting to Etherpad: {e}")
            except Exception as e:
                logging.error(f"Unexpected error in polling loop: {e}")

            await asyncio.sleep(POLL_INTERVAL)

def main(pad_id: str, log_file_path: str):
    logging.info(f"Etherpad Logger starting. Pad ID: {pad_id}, Log File: {log_file_path}")
    
    # Ensure log directory exists
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    
    # Ensure log file exists (and has opening bracket if we're simulating a JSON array)
    if not os.path.exists(log_file_path):
        with open(log_file_path, "w", encoding="utf-8") as f:
            f.write("") # Will be handled by the JSON fix in utils.load_log_file

    try:
        asyncio.run(poll_etherpad(pad_id, log_file_path))
    except KeyboardInterrupt:
        logging.info("Etherpad logger stopped.")

if __name__ == "__main__":
    import sys
    # For JupyterHub we might use the username as pad_id
    # Defaulting to 'test_pad' for local dev
    pad_id_arg = sys.argv[1] if len(sys.argv) > 1 else os.getenv("JUPYTERHUB_USER", "test_pad")
    
    # Use the same default log path that process_logs.py expects
    log_file_path_arg = sys.argv[2] if len(sys.argv) > 2 else "/home/jovyan/logs/log"
    
    main(pad_id_arg, log_file_path_arg)
