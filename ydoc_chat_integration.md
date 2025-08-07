# Using YDoc to Properly Change Chat Files

## Overview

The current `chat_interact.py` manually modifies chat files using JSON read/write operations. This approach can lead to race conditions and doesn't properly handle collaborative editing features provided by the jupyter-chat extension. The proper way is to use YDoc (Yjs Document) which provides:

- **Collaborative editing**: Multiple users can edit simultaneously
- **Conflict resolution**: Automatic merging of concurrent changes
- **Awareness**: Real-time updates about who is editing
- **Atomic transactions**: All changes happen atomically
- **Undo/Redo support**: Built-in history management

## YChat Document Structure

The YChat document (used by jupyter-chat extension) has the following schema:

```typescript
{
  "state": YMap<string, any>,     // Document state (dirty, path, etc.)
  "users": YMap<string, IUser>,   // All users in the chat
  "messages": YArray<IYmessage>,  // Array of chat messages
  "attachments": YMap<string, IAttachment>, // File attachments
  "metadata": YMap<string, any>   // Chat metadata (id, etc.)
}
```

### Message Structure
```typescript
interface IYmessage {
  id: string;
  body: string;
  type: 'msg';
  time: number;
  sender: string;  // username
  raw_time?: boolean;
  automated?: boolean;
  edited?: boolean;
  deleted?: boolean;
  mentions?: string[];  // array of usernames
  attachments?: string[]; // array of attachment IDs
}
```

### User Structure
```typescript
interface IUser {
  username: string;
  name?: string;
  display_name?: string;
  initials?: string;
  avatar_url?: string;
  color?: string;
  mention_name?: string;
}
```

## Implementation Approaches

### Option 1: Use YChat Python Class (Recommended)

Install the required dependencies:
```bash
pip install jupyterlab-chat pycrdt
```

Create a new implementation using YChat:

```python
import os
import json
import asyncio
from typing import Optional, Dict, Any
from jupyterlab_chat.ychat import YChat
from jupyterlab_chat.models import Message, NewMessage, User
from pycrdt import Doc
import logging

class YDocChatHandler:
    def __init__(self, chat_directory: str):
        self.chat_directory = os.path.abspath(chat_directory)
        self.chat_docs: Dict[str, YChat] = {}
        
    def get_or_create_chat_doc(self, file_path: str) -> YChat:
        """Get existing YChat document or create new one"""
        if file_path not in self.chat_docs:
            # Create new YDoc
            ydoc = Doc()
            ychat = YChat(ydoc)
            
            # Load existing content if file exists
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        content = json.load(f)
                    
                    # Set the document content
                    ychat.set(json.dumps(content))
                except Exception as e:
                    logging.error(f"Error loading chat file {file_path}: {e}")
            
            self.chat_docs[file_path] = ychat
            
            # Set up observer for changes
            ychat.observe(lambda topic, event: self._on_document_change(file_path, topic, event))
            
        return self.chat_docs[file_path]
    
    def _on_document_change(self, file_path: str, topic: str, event):
        """Handle document changes and save to file"""
        try:
            ychat = self.chat_docs[file_path]
            content = json.loads(ychat.get())
            
            with open(file_path, 'w') as f:
                json.dump(content, f, indent=4)
                
            logging.info(f"Saved changes to {file_path} (topic: {topic})")
        except Exception as e:
            logging.error(f"Error saving changes to {file_path}: {e}")
    
    def add_juno_user(self, file_path: str):
        """Add Juno user to the chat if not exists"""
        ychat = self.get_or_create_chat_doc(file_path)
        
        juno_user = User(
            username="Juno",
            name="Juno",
            display_name="Juno",
            initials="J",
            color="var(--jp-collaborator-color7)"
        )
        
        # Check if Juno user exists
        existing_user = ychat.get_user("Juno")
        if not existing_user:
            ychat.set_user(juno_user)
            logging.info(f"Added Juno user to {file_path}")
    
    def add_message(self, file_path: str, message_text: str, sender: str = "Juno", automated: bool = True) -> str:
        """Add a message to the chat using YDoc"""
        ychat = self.get_or_create_chat_doc(file_path)
        
        # Create new message
        new_message = NewMessage(
            body=message_text,
            sender=sender
        )
        
        # Add the message
        message_id = ychat.add_message(new_message)
        
        # Get the added message and mark as automated
        messages = ychat.get_messages()
        for i, msg in enumerate(messages):
            if msg.id == message_id:
                msg.automated = automated
                msg.raw_time = False
                ychat.update_message(msg)
                break
        
        logging.info(f"Added message to {file_path}: {message_text[:50]}...")
        return message_id
    
    def update_working_message(self, file_path: str, message_id: str, new_text: str):
        """Update an existing message"""
        ychat = self.get_or_create_chat_doc(file_path)
        
        # Find message by ID
        messages = ychat.get_messages()
        for i, msg in enumerate(messages):
            if msg.id == message_id:
                msg.body = new_text
                msg.time = time.time()
                ychat.update_message(msg)
                break
        
        logging.info(f"Updated message {message_id} in {file_path}")
    
    def replace_working_message(self, file_path: str, old_message_id: str, final_text: str, sender: str = "Juno"):
        """Replace a working message with final response"""
        ychat = self.get_or_create_chat_doc(file_path)
        
        # Find and update the message
        messages = ychat.get_messages()
        for i, msg in enumerate(messages):
            if msg.id == old_message_id:
                msg.body = final_text
                msg.sender = sender
                msg.automated = True
                msg.raw_time = False
                msg.time = time.time()
                ychat.update_message(msg)
                logging.info(f"Replaced working message {old_message_id} in {file_path}")
                return
        
        # If message not found, add new one
        self.add_message(file_path, final_text, sender, automated=True)
    
    def cleanup(self):
        """Clean up resources"""
        for ychat in self.chat_docs.values():
            ychat.dispose()
        self.chat_docs.clear()

# Usage in chat_interact.py
async def manage_interaction_with_ydoc(self, file_path, student_id, message_text, processed_log_data, file_name):
    """Updated interaction method using YDoc"""
    
    # Initialize YDoc handler
    ydoc_handler = YDocChatHandler(self.chat_directory)
    
    try:
        # Ensure Juno user exists
        ydoc_handler.add_juno_user(file_path)
        
        # Add working message
        working_message_id = ydoc_handler.add_message(
            file_path, 
            "Juno is working on it...", 
            sender="Juno", 
            automated=True
        )
        
        # Start cycling through working messages
        working_task = asyncio.create_task(
            self.send_working_messages_ydoc(ydoc_handler, file_path, working_message_id)
        )
        
        final_response_message = None
        error_occurred = False
        
        try:
            # Call TA and wait for response
            async with httpx.AsyncClient() as client:
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
                final_text = response_data.get("final_response", "Error: TA response format incorrect.")
                
                logging.info(f"Received final response from TA: '{final_text[:100]}...'")
                
        except Exception as e:
            logging.error(f"Error during TA interaction: {e}")
            final_text = "Sorry, an unexpected error occurred."
            error_occurred = True
            
        finally:
            # Cancel working messages
            working_task.cancel()
            try:
                await working_task
            except asyncio.CancelledError:
                pass
            
            # Replace working message with final response
            ydoc_handler.replace_working_message(
                file_path, 
                working_message_id, 
                final_text, 
                sender="Juno"
            )
            
    finally:
        # Clean up
        ydoc_handler.cleanup()

async def send_working_messages_ydoc(self, ydoc_handler: YDocChatHandler, file_path: str, message_id: str):
    """Send cycling working messages using YDoc"""
    working_phrases = [
        "Juno is working on it...", 
        "Just a moment, processing...", 
        "Thinking...", 
        "Checking notes..."
    ]
    
    idx = 0
    try:
        while True:
            phrase = working_phrases[idx % len(working_phrases)]
            ydoc_handler.update_working_message(file_path, message_id, phrase)
            idx += 1
            await asyncio.sleep(random.uniform(3, 5.5))
    except asyncio.CancelledError:
        logging.info(f"Stopped working messages for {file_path}")
```

### Option 2: Direct YJS Integration (Advanced)

For more direct control, you can use the JavaScript YJS library:

```python
import subprocess
import json
import tempfile

class YJSChatHandler:
    def __init__(self):
        # This would require a Node.js script that uses @jupyter/ydoc
        self.node_script = """
        const { YChat } = require('@jupyter/ydoc');
        const Y = require('yjs');
        const fs = require('fs');

        // Create YDoc
        const ydoc = new Y.Doc();
        const ychat = new YChat({ ydoc });

        // Load existing content
        if (process.argv[3] && fs.existsSync(process.argv[3])) {
            const content = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
            ychat.setSource(content);
        }

        // Add message
        const message = {
            id: process.argv[4],
            body: process.argv[5],
            type: 'msg',
            time: Date.now() / 1000,
            sender: process.argv[6] || 'Juno',
            automated: true
        };

        ychat.addMessage(message);

        // Save result
        const result = ychat.getSource();
        fs.writeFileSync(process.argv[3], JSON.stringify(result, null, 4));
        """
    
    def add_message_via_yjs(self, file_path: str, message_id: str, message_text: str, sender: str = "Juno"):
        """Add message using Node.js YJS script"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(self.node_script)
            script_path = f.name
        
        try:
            subprocess.run([
                'node', script_path, file_path, message_id, message_text, sender
            ], check=True)
        finally:
            os.unlink(script_path)
```

## Migration Strategy

1. **Install Dependencies**:
   ```bash
   pip install jupyterlab-chat pycrdt jupyter-ydoc
   ```

2. **Update chat_interact_requirements.txt**:
   ```
   langserve
   watchdog
   fastapi
   asyncio
   watchdog
   watchgod
   uvicorn
   jupyterlab-chat
   pycrdt
   jupyter-ydoc
   ```

3. **Modify ChatHandler Class**:
   - Replace direct JSON operations with YChat methods
   - Use transactions for atomic updates
   - Implement proper change observers

4. **Test Collaborative Features**:
   - Open same chat file in multiple browser tabs
   - Verify real-time synchronization
   - Test conflict resolution

## Benefits of YDoc Integration

1. **Collaborative Editing**: Multiple users can edit simultaneously
2. **Conflict Resolution**: Automatic merging of concurrent changes
3. **Real-time Updates**: Changes appear immediately in all connected clients
4. **Awareness**: See who is currently editing
5. **Undo/Redo**: Built-in history management
6. **Atomic Operations**: All changes are transactional
7. **Type Safety**: Structured document schema
8. **Performance**: Efficient delta-based synchronization

## Considerations

1. **Dependencies**: Additional Python packages required
2. **Complexity**: More complex than direct JSON manipulation
3. **Memory Usage**: YDoc keeps document in memory
4. **Learning Curve**: Need to understand YDoc/YJS concepts
5. **Debugging**: More complex error scenarios

## Recommended Next Steps

1. Create a branch for YDoc integration
2. Implement YDocChatHandler class
3. Update ChatHandler to use YDoc methods
4. Test with existing chat files
5. Verify collaborative features work
6. Update documentation
7. Deploy and monitor
