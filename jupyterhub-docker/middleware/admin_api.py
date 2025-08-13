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
CHAT_DB_PATH = '/app/chat_histories/chat_history.db'

# Ensure directories exist
os.makedirs(INPUTS_DIR, exist_ok=True)
os.makedirs(f"{INPUTS_DIR}/learning_objectives", exist_ok=True)
os.makedirs(MATERIALS_DIR, exist_ok=True)

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
            <h2>Learning Objectives</h2>
            <input type="text" id="task-name" placeholder="Task name (e.g., task1)">
            <button class="button" onclick="loadObjectives()">Load Objectives</button>
            <br><br>
            <textarea id="objectives" placeholder="Enter learning objectives..."></textarea>
            <br><button class="button" onclick="saveObjectives()">Save Objectives</button>
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
                const task = document.getElementById('task-name').value;
                if (!task) {
                    alert('Please enter a task name');
                    return;
                }
                
                fetch('/api/learning-objectives/' + task)
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('objectives').value = data.content || '';
                    })
                    .catch(error => console.error('Error:', error));
            }
            
            function saveObjectives() {
                const task = document.getElementById('task-name').value;
                const content = document.getElementById('objectives').value;
                
                if (!task) {
                    alert('Please enter a task name');
                    return;
                }
                
                fetch('/api/learning-objectives/' + task, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: content })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Objectives saved successfully!');
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
            username,
            COUNT(*) as message_count,
            MIN(timestamp) as first_interaction,
            MAX(timestamp) as last_interaction
        FROM chat_history 
        WHERE role = 'user'
        GROUP BY username
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
            DATE(timestamp) as date,
            COUNT(*) as messages,
            COUNT(DISTINCT username) as active_students
        FROM chat_history 
        WHERE timestamp >= ? AND role = 'user'
        GROUP BY DATE(timestamp)
        ORDER BY date DESC
        """
        
        df = pd.read_sql_query(query, conn, params=[since_date])
        conn.close()
        
        return jsonify(df.to_dict('records'))
    except Exception as e:
        logger.error(f"Error getting chat summary: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/materials', methods=['GET', 'POST'])
def manage_materials():
    """List and upload learning materials"""
    if request.method == 'GET':
        try:
            files = []
            if os.path.exists(MATERIALS_DIR):
                for root, dirs, filenames in os.walk(MATERIALS_DIR):
                    for filename in filenames:
                        if not filename.startswith('.'):
                            rel_path = os.path.relpath(os.path.join(root, filename), MATERIALS_DIR)
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

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    logger.info("Starting JELAI Admin API on port 8005")
    app.run(host='0.0.0.0', port=8005, debug=True)
