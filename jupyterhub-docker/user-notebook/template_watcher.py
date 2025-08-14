#!/usr/bin/env python3
"""
Template Watcher Service for User Notebook
Monitors workspace template volume for new files and automatically copies them to user workspace
"""

import os
import time
import shutil
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/jovyan/logs/template_watcher.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TemplateHandler(FileSystemEventHandler):
    """Handles file system events for workspace templates"""
    
    def __init__(self, source_dir, target_dir):
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        logger.info(f"Watching {source_dir} for changes, copying to {target_dir}")
    
    def on_created(self, event):
        """Handle file creation events"""
        if event.is_directory:
            return
        
        self.copy_file(event.src_path)
    
    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return
        
        self.copy_file(event.src_path)
    
    def copy_file(self, src_path):
        """Copy a file from source to target directory"""
        try:
            src_file = Path(src_path)
            relative_path = src_file.relative_to(self.source_dir)
            target_file = self.target_dir / relative_path
            
            # Create target directory if it doesn't exist
            target_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy the file
            shutil.copy2(src_file, target_file)
            
            # Set proper ownership (jovyan:users)
            shutil.chown(target_file, user='jovyan', group='users')
            
            logger.info(f"Copied template: {relative_path}")
            
        except Exception as e:
            logger.error(f"Error copying {src_path}: {e}")

def initial_sync(source_dir, target_dir):
    """Perform initial synchronization of existing files"""
    source_path = Path(source_dir)
    target_path = Path(target_dir)
    
    if not source_path.exists():
        logger.info(f"Source directory {source_dir} doesn't exist yet")
        return
    
    logger.info("Performing initial template synchronization...")
    
    for src_file in source_path.rglob('*'):
        if src_file.is_file():
            try:
                relative_path = src_file.relative_to(source_path)
                target_file = target_path / relative_path
                
                # Skip if target is newer than source
                if target_file.exists() and target_file.stat().st_mtime >= src_file.stat().st_mtime:
                    continue
                
                # Create target directory if needed
                target_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy the file
                shutil.copy2(src_file, target_file)
                shutil.chown(target_file, user='jovyan', group='users')
                
                logger.info(f"Synced template: {relative_path}")
                
            except Exception as e:
                logger.error(f"Error syncing {src_file}: {e}")

def main():
    """Main template watcher service"""
    # Directories
    template_volume = "/mnt/workspace-templates"  # Volume mount point
    workspace_dir = "/home/jovyan/work"           # User workspace
    
    # Ensure directories exist
    Path(template_volume).mkdir(parents=True, exist_ok=True)
    Path(workspace_dir).mkdir(parents=True, exist_ok=True)
    
    # Perform initial sync
    initial_sync(template_volume, workspace_dir)
    
    # Set up file watcher
    event_handler = TemplateHandler(template_volume, workspace_dir)
    observer = Observer()
    observer.schedule(event_handler, template_volume, recursive=True)
    
    # Start watching
    observer.start()
    logger.info("Template watcher service started")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Template watcher service stopped")
    
    observer.join()

if __name__ == "__main__":
    main()
