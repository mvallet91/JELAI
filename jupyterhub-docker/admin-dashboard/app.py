#!/usr/bin/env python3
"""
JELAI Admin Dashboard - Web interface for educators to manage the system
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import requests
import os
import json
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MIDDLEWARE_URL = os.environ.get('MIDDLEWARE_URL', 'http://middleware:8005')
JUPYTERHUB_URL = os.environ.get('JUPYTERHUB_URL', 'http://hub:8000')

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/proxy/<path:endpoint>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_to_middleware(endpoint):
    """Proxy requests to middleware admin API"""
    try:
        url = f"{MIDDLEWARE_URL}/api/{endpoint}"
        
        if request.method == 'GET':
            response = requests.get(url)
        elif request.method == 'POST':
            if request.is_json:
                response = requests.post(url, json=request.json)
            else:
                response = requests.post(url, files=request.files)
        elif request.method == 'PUT':
            response = requests.put(url, json=request.json)
        elif request.method == 'DELETE':
            response = requests.delete(url)
        
        return response.json(), response.status_code
    except Exception as e:
        logger.error(f"Error proxying request to {url}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    logger.info("Starting JELAI Admin Dashboard on port 8006")
    app.run(host='0.0.0.0', port=8006, debug=True)
