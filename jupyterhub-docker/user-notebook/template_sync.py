#!/usr/bin/env python3
"""
Smart Template Sync Service
Fetches new templates from middleware without overwriting existing student work
"""

import os
import json
import requests
import logging
import time
import shutil
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/jovyan/logs/template_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

MIDDLEWARE_URL = "http://middleware:8005"
WORKSPACE_DIR = "/home/jovyan/work"
SYNC_STATE_FILE = "/home/jovyan/work/.template_sync_state.json"

def load_sync_state():
    """Load the current sync state (which templates this student has)"""
    try:
        if os.path.exists(SYNC_STATE_FILE):
            with open(SYNC_STATE_FILE, 'r') as f:
                return json.load(f)
        return {"synced_templates": {}, "last_sync": 0}
    except Exception as e:
        logger.error(f"Error loading sync state: {e}")
        return {"synced_templates": {}, "last_sync": 0}

def save_sync_state(state):
    """Save the current sync state"""
    try:
        with open(SYNC_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving sync state: {e}")

def get_available_templates():
    """Get list of available templates from middleware"""
    try:
        response = requests.get(f"{MIDDLEWARE_URL}/api/workspace-templates", timeout=10)
        if response.status_code == 200:
            return response.json().get('files', [])
        else:
            logger.error(f"Failed to get templates: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error fetching templates: {e}")
        return []

def download_template(filename):
    """Download a specific template file"""
    try:
        response = requests.get(f"{MIDDLEWARE_URL}/api/workspace-templates/{filename}", timeout=30)
        if response.status_code == 200:
            target_path = os.path.join(WORKSPACE_DIR, filename)
            with open(target_path, 'wb') as f:
                f.write(response.content)
            
            # Set proper ownership
            os.chown(target_path, 1000, 100)  # jovyan:users
            logger.info(f"Downloaded new template: {filename}")
            return True
        else:
            logger.error(f"Failed to download {filename}: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error downloading {filename}: {e}")
        return False

def sync_templates():
    """Smart sync: only download templates that are new or updated"""
    logger.info("Starting template sync...")
    
    # Load current state
    state = load_sync_state()
    synced_templates = state.get("synced_templates", {})
    
    # Get available templates
    available_templates = get_available_templates()
    
    if not available_templates:
        logger.info("No templates available or failed to fetch")
        return
    
    new_templates = []
    updated_templates = []
    
    for template in available_templates:
        filename = template['name']
        modified_time = template['modified']
        local_path = os.path.join(WORKSPACE_DIR, filename)
        
        # NEVER overwrite existing files - students may have modified them
        if os.path.exists(local_path):
            # File exists locally, mark as synced but don't download
            if filename not in synced_templates:
                synced_templates[filename] = modified_time
                logger.info(f"Found existing file {filename}, marking as synced without overwriting")
            continue
        
        # Only download if file doesn't exist locally
        if filename not in synced_templates:
            # New template, student doesn't have it
            new_templates.append(filename)
        else:
            # Template exists in sync state but not on disk (student deleted it)
            # Check if template was updated since last sync
            last_synced = synced_templates[filename]
            if modified_time > last_synced:
                updated_templates.append(filename)
    
    # Download new templates
    for filename in new_templates:
        if download_template(filename):
            template = next(t for t in available_templates if t['name'] == filename)
            synced_templates[filename] = template['modified']
    
    # Download updated templates (only if student deleted their copy)
    for filename in updated_templates:
        if download_template(filename):
            template = next(t for t in available_templates if t['name'] == filename)
            synced_templates[filename] = template['modified']
    
    # Update sync state
    state["synced_templates"] = synced_templates
    state["last_sync"] = time.time()
    save_sync_state(state)
    
    total_synced = len(new_templates) + len(updated_templates)
    if total_synced > 0:
        logger.info(f"Sync complete: {len(new_templates)} new, {len(updated_templates)} updated")
    else:
        logger.info("Sync complete: no new templates")

def main():
    """Main sync service - run once at startup"""
    logger.info("Template sync service starting...")
    
    # Wait a bit for container to fully start
    time.sleep(5)
    
    # Ensure workspace directory exists
    os.makedirs(WORKSPACE_DIR, exist_ok=True)
    
    # Run sync once at startup
    sync_templates()
    
    logger.info("Template sync service completed")

if __name__ == "__main__":
    main()

def get_templates_from_api():
    """Get list of templates from the middleware API"""
    try:
        response = requests.get('http://middleware:8005/api/workspace-templates', timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('files', [])
        else:
            logger.warning(f"API returned status {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error fetching templates from API: {e}")
        return []

def download_template(filename, target_dir):
    """Download a template file from the middleware API"""
    try:
        response = requests.get(f'http://middleware:8005/api/workspace-templates/{filename}', timeout=30)
        if response.status_code == 200:
            target_file = Path(target_dir) / filename
            target_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(target_file, 'wb') as f:
                f.write(response.content)
            
            # Set proper ownership
            shutil.chown(target_file, user='jovyan', group='users')
            logger.info(f"Downloaded template: {filename}")
            return True
        else:
            logger.error(f"Failed to download {filename}: status {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error downloading {filename}: {e}")
        return False

def sync_templates():
    """Sync templates from API to local workspace"""
    workspace_dir = "/home/jovyan/work"
    
    try:
        # Get current template list
        templates = get_templates_from_api()
        logger.info(f"Found {len(templates)} templates available")
        
        synced_count = 0
        for template in templates:
            filename = template['name']
            target_file = Path(workspace_dir) / filename
            
            # Check if file exists and is up to date
            should_download = True
            if target_file.exists():
                # Compare modification times if available
                api_modified = template.get('modified')
                if api_modified:
                    try:
                        from datetime import datetime
                        api_time = datetime.fromisoformat(api_modified.replace('Z', '+00:00'))
                        local_time = datetime.fromtimestamp(target_file.stat().st_mtime)
                        if local_time >= api_time.replace(tzinfo=None):
                            should_download = False
                    except:
                        pass  # If time comparison fails, download anyway
            
            if should_download:
                if download_template(filename, workspace_dir):
                    synced_count += 1
        
        if synced_count > 0:
            logger.info(f"Synced {synced_count} templates")
        
        return synced_count
        
    except Exception as e:
        logger.error(f"Error in sync_templates: {e}")
        return 0

def main():
    """Main template sync service"""
    logger.info("Starting Template Sync Service")
    
    # Initial sync
    logger.info("Performing initial template sync...")
    sync_templates()
    
    # Periodic sync every 30 seconds
    try:
        while True:
            time.sleep(30)  # Check every 30 seconds
            sync_templates()
    except KeyboardInterrupt:
        logger.info("Template sync service stopped")

if __name__ == "__main__":
    main()
