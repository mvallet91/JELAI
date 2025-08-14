#!/usr/bin/env python3
"""
Admin API for JELAI - Provides web-based management interface for educators
"""

from flask import Flask, request, jsonify, send_file, render_template_string
from werkzeug.utils import secure_filename
import os
import json
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import logging

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base paths
INPUTS_DIR = '/app/inputs'
MATERIALS_DIR = '/app/learning_materials'
WORKSPACE_TEMPLATES_DIR = '/app/workspace_templates'
SHARED_RESOURCES_DIR = '/app/shared_resources'
LEARNING_OBJECTIVES_DIR = '/app/learning_objectives'
CHAT_DB_PATH = '/app/chat_histories/chat_history.db'

# Ensure directories exist
os.makedirs(INPUTS_DIR, exist_ok=True)
os.makedirs(f"{INPUTS_DIR}/learning_objectives", exist_ok=True)
os.makedirs(MATERIALS_DIR, exist_ok=True)
os.makedirs(WORKSPACE_TEMPLATES_DIR, exist_ok=True)
os.makedirs(SHARED_RESOURCES_DIR, exist_ok=True)
os.makedirs(LEARNING_OBJECTIVES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(CHAT_DB_PATH), exist_ok=True)  # Create chat_histories directory

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>JELAI Admin Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; }
            .button { background: #007cba; color: white; padding: 10px 20px; border: none; cursor: pointer; }
            .button:hover { background: #005a8c; }
            textarea { width: 100%; height: 200px; }
            input[type="file"] { margin: 10px 0; }
            .analytics-card { display: inline-block; margin: 10px; padding: 15px; background: #f5f5f5; }
        </style>
    </head>
    <body>
        <h1>JELAI Admin Dashboard</h1>
        
        <div class="section">
            <h2>AI Tutor Configuration</h2>
            <h3>Tutor System Prompt</h3>
            <textarea id="tutor-prompt" placeholder="Loading..."></textarea>
            <br><button class="button" onclick="savePrompt('tutor')">Save Tutor Prompt</button>
            
            <h3>Expert System Prompt</h3>
            <textarea id="expert-prompt" placeholder="Loading..."></textarea>
            <br><button class="button" onclick="savePrompt('expert')">Save Expert Prompt</button>
        </div>
        
        <div class="section">
            <h2>📚 Learning Objectives</h2>
            <p>Define learning objectives for specific tasks or assignments</p>
            
            <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                <select id="task-selector" style="flex: 1; padding: 10px;" onchange="loadSelectedObjectives()">
                    <option value="">Select existing task or type new name below...</option>
                </select>
                <button class="button secondary" onclick="loadAllObjectives()">🔄 Refresh</button>
            </div>
            
            <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                <input type="text" id="task-name" placeholder="Task name (e.g., data_analysis_week1)" style="flex: 1;">
                <button class="button secondary" onclick="loadObjectives()">📖 Load</button>
                <button class="button" onclick="saveObjectives()">💾 Save</button>
            </div>
            
            <textarea id="objectives" placeholder="Enter learning objectives (one per line)...
Example:
Data loading and file I/O
Pandas DataFrame manipulation
Basic statistical analysis"></textarea>
            
            <div id="objectives-list" style="margin-top: 15px; padding: 10px; background: #f8f9fa; border-radius: 4px;">
                <h4>Existing Learning Objectives:</h4>
                <div id="objectives-content">Loading...</div>
            </div>
        </div>
        
        <div class="section">
            <h2>Learning Materials</h2>
            <input type="file" id="file-upload" multiple>
            <button class="button" onclick="uploadFiles()">Upload Files</button>
            <br><br>
            <div id="files-list">Loading files...</div>
        </div>
        
        <div class="section">
            <h2>Student Analytics</h2>
            <button class="button" onclick="loadAnalytics()">Refresh Analytics</button>
            <div id="analytics-content">Click refresh to load analytics...</div>
        </div>
        
        <script>
            // Load initial data
            window.onload = function() {
                loadPrompt('tutor');
                loadPrompt('expert');
                loadFiles();
                loadAllObjectives();
            };
            
            function loadPrompt(type) {
                fetch('/api/prompts/' + type)
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById(type + '-prompt').value = data.content || '';
                    })
                    .catch(error => console.error('Error:', error));
            }
            
            function savePrompt(type) {
                const content = document.getElementById(type + '-prompt').value;
                fetch('/api/prompts/' + type, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: content })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Prompt saved successfully!');
                    } else {
                        alert('Error saving prompt: ' + data.error);
                    }
                })
                .catch(error => console.error('Error:', error));
            }
            
            function loadObjectives() {
                const task = document.getElementById('task-name').value.trim();
                if (!task) {
                    alert('Please enter a task name');
                    return;
                }
                
                fetch('/api/learning-objectives/' + encodeURIComponent(task))
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('objectives').value = data.content || '';
                        if (data.content) {
                            alert(`Loaded objectives for: ${task}`);
                        } else {
                            alert(`No objectives found for: ${task}. You can create new ones.`);
                        }
                    })
                    .catch(error => console.error('Error:', error));
            }
            
            function loadSelectedObjectives() {
                const selector = document.getElementById('task-selector');
                const taskName = selector.value;
                if (taskName) {
                    document.getElementById('task-name').value = taskName;
                    loadObjectives();
                }
            }
            
            function loadAllObjectives() {
                fetch('/api/learning-objectives')
                    .then(response => response.json())
                    .then(data => {
                        // Populate selector
                        const selector = document.getElementById('task-selector');
                        selector.innerHTML = '<option value="">Select existing task or type new name below...</option>';
                        Object.keys(data).forEach(task => {
                            const option = document.createElement('option');
                            option.value = task;
                            option.textContent = task;
                            selector.appendChild(option);
                        });
                        
                        // Show all objectives
                        const content = document.getElementById('objectives-content');
                        if (Object.keys(data).length === 0) {
                            content.innerHTML = '<p>No learning objectives found. Create your first one above!</p>';
                        } else {
                            content.innerHTML = Object.entries(data).map(([task, objectives]) => `
                                <div style="margin-bottom: 15px; padding: 10px; border-left: 3px solid #007cba; background: white;">
                                    <h5 style="margin: 0 0 5px 0; color: #007cba;">${task}</h5>
                                    <div style="font-size: 0.9em; color: #666;">
                                        ${objectives.split('\\n').map(obj => obj.trim()).filter(obj => obj).map(obj => `• ${obj}`).join('<br>')}
                                    </div>
                                </div>
                            `).join('');
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        document.getElementById('objectives-content').innerHTML = '<p>Error loading objectives</p>';
                    });
            }

            function saveObjectives() {
                const task = document.getElementById('task-name').value.trim();
                const content = document.getElementById('objectives').value.trim();
                
                if (!task) {
                    alert('Please enter a task name');
                    return;
                }
                
                if (!content) {
                    alert('Please enter some learning objectives');
                    return;
                }
                
                fetch('/api/learning-objectives/' + encodeURIComponent(task), {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: content })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert(`Objectives saved successfully for: ${task}`);
                        loadAllObjectives(); // Refresh the list
                    } else {
                        alert('Error saving objectives: ' + data.error);
                    }
                })
                .catch(error => console.error('Error:', error));
            }
            
            function loadFiles() {
                fetch('/api/materials')
                    .then(response => response.json())
                    .then(data => {
                        const filesList = document.getElementById('files-list');
                        filesList.innerHTML = '<h3>Current Files:</h3>' + 
                            data.files.map(file => '<div>📄 ' + file + '</div>').join('');
                    })
                    .catch(error => console.error('Error:', error));
            }
            
            function uploadFiles() {
                const fileInput = document.getElementById('file-upload');
                const files = fileInput.files;
                
                if (files.length === 0) {
                    alert('Please select files to upload');
                    return;
                }
                
                for (let file of files) {
                    const formData = new FormData();
                    formData.append('file', file);
                    
                    fetch('/api/materials', {
                        method: 'POST',
                        body: formData
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            console.log('File uploaded:', data.filename);
                        } else {
                            alert('Error uploading file: ' + data.error);
                        }
                    })
                    .catch(error => console.error('Error:', error));
                }
                
                setTimeout(loadFiles, 1000); // Refresh file list after upload
                fileInput.value = ''; // Clear file input
            }
            
            function loadAnalytics() {
                fetch('/api/analytics/students')
                    .then(response => response.json())
                    .then(data => {
                        const content = document.getElementById('analytics-content');
                        content.innerHTML = '<h3>Student Activity Summary:</h3>' +
                            data.map(student => 
                                '<div class="analytics-card">' +
                                '<strong>' + student.username + '</strong><br>' +
                                'Messages: ' + student.message_count + '<br>' +
                                'First: ' + student.first_interaction + '<br>' +
                                'Last: ' + student.last_interaction +
                                '</div>'
                            ).join('');
                    })
                    .catch(error => {
                        document.getElementById('analytics-content').innerHTML = 
                            'Error loading analytics: ' + error.message;
                    });
            }
        </script>
    </body>
    </html>
    """)

# Configuration management endpoints
@app.route('/api/prompts/<prompt_type>', methods=['GET', 'PUT'])
def manage_prompts(prompt_type):
    """Manage system prompts (tutor/expert)"""
    prompt_files = {
        'tutor': f'{INPUTS_DIR}/ta_system_prompt.txt',
        'expert': f'{INPUTS_DIR}/ea_system_prompt.txt'
    }
    
    if prompt_type not in prompt_files:
        return jsonify({'error': 'Invalid prompt type'}), 400
        
    if request.method == 'GET':
        try:
            with open(prompt_files[prompt_type], 'r') as f:
                return jsonify({'content': f.read()})
        except FileNotFoundError:
            return jsonify({'content': ''})
            
    elif request.method == 'PUT':
        content = request.json.get('content', '')
        try:
            with open(prompt_files[prompt_type], 'w') as f:
                f.write(content)
            logger.info(f"Updated {prompt_type} prompt")
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error updating {prompt_type} prompt: {e}")
            return jsonify({'error': str(e)}), 500

@app.route('/api/learning-objectives', methods=['GET'])
def list_objectives():
    """List all available learning objectives"""
    try:
        objectives = {}
        if os.path.exists(f'{INPUTS_DIR}/learning_objectives'):
            for filename in os.listdir(f'{INPUTS_DIR}/learning_objectives'):
                if filename.endswith('.txt'):
                    task_name = filename[:-4]  # Remove .txt extension
                    try:
                        with open(f'{INPUTS_DIR}/learning_objectives/{filename}', 'r') as f:
                            content = f.read().strip()
                            objectives[task_name] = content
                    except Exception as e:
                        logger.warning(f"Could not read {filename}: {e}")
        return jsonify(objectives)
    except Exception as e:
        logger.error(f"Error listing objectives: {e}")
        return jsonify({}), 500

@app.route('/api/learning-objectives/<task>', methods=['GET', 'PUT'])
def manage_objectives(task):
    """Manage learning objectives for specific tasks"""
    # Sanitize task name
    task = secure_filename(task)
    obj_file = f'{INPUTS_DIR}/learning_objectives/{task}.txt'
    
    if request.method == 'GET':
        try:
            with open(obj_file, 'r') as f:
                return jsonify({'content': f.read()})
        except FileNotFoundError:
            return jsonify({'content': ''})
            
    elif request.method == 'PUT':
        content = request.json.get('content', '')
        try:
            os.makedirs(os.path.dirname(obj_file), exist_ok=True)
            with open(obj_file, 'w') as f:
                f.write(content)
            logger.info(f"Updated learning objectives for task: {task}")
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error updating objectives for {task}: {e}")
            return jsonify({'error': str(e)}), 500

@app.route('/api/sync-learning-objectives', methods=['POST'])
def sync_learning_objectives():
    """Create learning objective files for any templates that don't have them"""
    try:
        created_files = []
        
        # Get all template files
        if os.path.exists(WORKSPACE_TEMPLATES_DIR):
            for template_file in os.listdir(WORKSPACE_TEMPLATES_DIR):
                if os.path.isfile(os.path.join(WORKSPACE_TEMPLATES_DIR, template_file)):
                    # Get base name without extension
                    base_name = os.path.splitext(template_file)[0]
                    obj_file = f'{INPUTS_DIR}/learning_objectives/{base_name}.txt'
                    
                    # Create if doesn't exist
                    if not os.path.exists(obj_file):
                        os.makedirs(os.path.dirname(obj_file), exist_ok=True)
                        with open(obj_file, 'w') as f:
                            f.write('')  # Create empty file
                        created_files.append(f"{base_name}.txt")
                        logger.info(f"Created learning objective file: {base_name}.txt")
        
        return jsonify({
            'success': True, 
            'created_files': created_files,
            'message': f'Created {len(created_files)} learning objective files'
        })
        
    except Exception as e:
        logger.error(f"Error syncing learning objectives: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/experiments', methods=['GET', 'PUT'])
def manage_experiments():
    """Configure A/B testing experiments"""
    exp_file = f'{INPUTS_DIR}/ab_experiments.json'
    
    if request.method == 'GET':
        try:
            with open(exp_file, 'r') as f:
                return jsonify(json.load(f))
        except FileNotFoundError:
            return jsonify({})
            
    elif request.method == 'PUT':
        experiments = request.json
        try:
            with open(exp_file, 'w') as f:
                json.dump(experiments, f, indent=2)
            logger.info("Updated A/B experiments configuration")
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error updating experiments: {e}")
            return jsonify({'error': str(e)}), 500

# Analytics endpoints
@app.route('/api/analytics/students')
def student_analytics():
    """Provide student interaction analytics"""
    try:
        if not os.path.exists(CHAT_DB_PATH):
            return jsonify([])
            
        conn = sqlite3.connect(CHAT_DB_PATH)
        
        # Basic student stats
        query = """
        SELECT 
            student_id as username,
            COUNT(*) as message_count,
            MIN(timestamp) as first_interaction,
            MAX(timestamp) as last_interaction
        FROM chat_history 
        WHERE message_type = 'question'
        GROUP BY student_id
        ORDER BY message_count DESC
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        return jsonify(df.to_dict('records'))
    except Exception as e:
        logger.error(f"Error getting student analytics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/chat-summary')
def chat_summary():
    """Provide chat interaction summary"""
    try:
        if not os.path.exists(CHAT_DB_PATH):
            return jsonify([])
            
        conn = sqlite3.connect(CHAT_DB_PATH)
        
        # Get recent activity
        since_date = datetime.now() - timedelta(days=7)
        query = """
        SELECT 
            DATE(datetime(timestamp, 'unixepoch')) as date,
            COUNT(*) as messages,
            COUNT(DISTINCT student_id) as active_students
        FROM chat_history 
        WHERE timestamp >= ? AND message_type = 'question'
        GROUP BY DATE(datetime(timestamp, 'unixepoch'))
        ORDER BY date DESC
        """
        
        df = pd.read_sql_query(query, conn, params=[since_date.timestamp()])
        conn.close()
        
        return jsonify(df.to_dict('records'))
    except Exception as e:
        logger.error(f"Error getting chat summary: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/materials', methods=['GET', 'POST'])
@app.route('/api/materials/<path:filename>', methods=['DELETE'])
def manage_materials(filename=None):
    """List, upload, and delete learning materials"""
    if request.method == 'GET':
        try:
            files = []
            if os.path.exists(MATERIALS_DIR):
                for root, dirs, filenames in os.walk(MATERIALS_DIR):
                    for fname in filenames:
                        if not fname.startswith('.'):
                            rel_path = os.path.relpath(os.path.join(root, fname), MATERIALS_DIR)
                            files.append(rel_path)
            return jsonify({'files': sorted(files)})
        except Exception as e:
            logger.error(f"Error listing materials: {e}")
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        try:
            filename = secure_filename(file.filename)
            file_path = os.path.join(MATERIALS_DIR, filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            
            logger.info(f"Uploaded file: {filename}")
            return jsonify({'success': True, 'filename': filename})
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'DELETE' and filename:
        try:
            file_path = os.path.join(MATERIALS_DIR, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file: {filename}")
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'File not found'}), 404
        except Exception as e:
            logger.error(f"Error deleting file {filename}: {e}")
            return jsonify({'error': str(e)}), 500

@app.route('/api/workspace-templates', methods=['GET', 'POST', 'DELETE'])
@app.route('/api/workspace-templates/<filename>', methods=['DELETE'])
def manage_workspace_templates(filename=None):
    """Manage workspace template files"""
    if request.method == 'GET':
        try:
            files = []
            if os.path.exists(WORKSPACE_TEMPLATES_DIR):
                for file in os.listdir(WORKSPACE_TEMPLATES_DIR):
                    if os.path.isfile(os.path.join(WORKSPACE_TEMPLATES_DIR, file)):
                        file_path = os.path.join(WORKSPACE_TEMPLATES_DIR, file)
                        files.append({
                            'name': file,
                            'size': os.path.getsize(file_path),
                            'modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                        })
            return jsonify({'files': files})
        except Exception as e:
            logger.error(f"Error listing workspace templates: {e}")
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            logger.info(f"Received file upload: filename='{file.filename}', content_type='{file.content_type}'")
            
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            filename = secure_filename(file.filename)
            logger.info(f"Secured filename: '{filename}'")
            file_path = os.path.join(WORKSPACE_TEMPLATES_DIR, filename)
            file.save(file_path)
            
            # Auto-create learning objective file for the new template
            base_name = os.path.splitext(filename)[0]  # Remove extension
            obj_file = f'{INPUTS_DIR}/learning_objectives/{base_name}.txt'
            
            # Only create if it doesn't exist
            if not os.path.exists(obj_file):
                os.makedirs(os.path.dirname(obj_file), exist_ok=True)
                with open(obj_file, 'w') as f:
                    f.write('')  # Create empty learning objective file
                logger.info(f"Auto-created empty learning objective file: {base_name}.txt")
            
            logger.info(f"Uploaded workspace template: {filename}")
            return jsonify({'success': True, 'filename': filename})
        except Exception as e:
            logger.error(f"Error uploading workspace template: {e}")
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'DELETE' and filename:
        try:
            file_path = os.path.join(WORKSPACE_TEMPLATES_DIR, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted workspace template: {filename}")
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'File not found'}), 404
        except Exception as e:
            logger.error(f"Error deleting workspace template {filename}: {e}")
            return jsonify({'error': str(e)}), 500

@app.route('/api/workspace-templates/<filename>', methods=['GET'])
def download_workspace_template(filename):
    """Download a specific workspace template file"""
    try:
        file_path = os.path.join(WORKSPACE_TEMPLATES_DIR, filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=filename)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        logger.error(f"Error downloading workspace template {filename}: {e}")
        return jsonify({'error': str(e)}), 500

# --- Shared Resources Management ---

@app.route('/api/shared-resources', methods=['GET', 'POST', 'DELETE'])
@app.route('/api/shared-resources/<filename>', methods=['DELETE'])
def manage_shared_resources(filename=None):
    """Manage shared resource files"""
    if request.method == 'GET':
        try:
            files = []
            if os.path.exists(SHARED_RESOURCES_DIR):
                for file in os.listdir(SHARED_RESOURCES_DIR):
                    if os.path.isfile(os.path.join(SHARED_RESOURCES_DIR, file)):
                        file_path = os.path.join(SHARED_RESOURCES_DIR, file)
                        files.append({
                            'name': file,
                            'size': os.path.getsize(file_path),
                            'modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                        })
            return jsonify({'files': files})
        except Exception as e:
            logger.error(f"Error listing shared resources: {e}")
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            filename = secure_filename(file.filename)
            file_path = os.path.join(SHARED_RESOURCES_DIR, filename)
            file.save(file_path)
            
            logger.info(f"Uploaded shared resource: {filename}")
            return jsonify({'success': True, 'filename': filename})
        except Exception as e:
            logger.error(f"Error uploading shared resource: {e}")
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'DELETE' and filename:
        try:
            file_path = os.path.join(SHARED_RESOURCES_DIR, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted shared resource: {filename}")
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'File not found'}), 404
        except Exception as e:
            logger.error(f"Error deleting shared resource {filename}: {e}")
            return jsonify({'error': str(e)}), 500

@app.route('/api/rebuild-workspaces', methods=['POST'])
def rebuild_workspaces():
    """Sync workspace templates - user containers will detect and copy automatically via file watchers"""
    try:
        # Templates are already in the volume via mount, just signal that they're ready
        template_files = []
        if os.path.exists(WORKSPACE_TEMPLATES_DIR):
            for file in os.listdir(WORKSPACE_TEMPLATES_DIR):
                file_path = os.path.join(WORKSPACE_TEMPLATES_DIR, file)
                if os.path.isfile(file_path):
                    template_files.append(file)
                    logger.info(f"Template available for auto-sync: {file}")
        
        # Write success status for dashboard
        with open('/tmp/build_status.txt', 'w') as f:
            f.write(f'completed: Templates ready for auto-sync ({len(template_files)} files)')
        
        logger.info(f"Template sync completed - {len(template_files)} files ready for user container auto-sync")
        
        return jsonify({
            'success': True, 
            'status': 'completed',
            'message': f'Templates ready! User containers will automatically sync {len(template_files)} files.',
            'template_files': template_files
        })
        
    except Exception as e:
        logger.error(f"Error in template sync: {e}")
        with open('/tmp/build_status.txt', 'w') as f:
            f.write(f'failed: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/build-status', methods=['GET'])
def get_build_status():
    """Get the current status of workspace template sync"""
    try:
        if os.path.exists('/tmp/build_status.txt'):
            with open('/tmp/build_status.txt', 'r') as f:
                status_text = f.read().strip()
                
                # Parse status format: "status: message"
                if ':' in status_text:
                    status, message = status_text.split(':', 1)
                    return jsonify({
                        'status': status.strip(), 
                        'message': message.strip(),
                        'timestamp': os.path.getmtime('/tmp/build_status.txt')
                    })
                else:
                    return jsonify({
                        'status': status_text, 
                        'message': 'Template sync status',
                        'timestamp': os.path.getmtime('/tmp/build_status.txt')
                    })
        else:
            return jsonify({
                'status': 'ready', 
                'message': 'No sync in progress'
            })
    except Exception as e:
        logger.error(f"Error getting build status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    logger.info("Starting JELAI Admin API on port 8005")
    app.run(host='0.0.0.0', port=8005, debug=True)
