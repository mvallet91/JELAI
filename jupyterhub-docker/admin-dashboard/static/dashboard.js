// JELAI Admin Dashboard JavaScript

// Global variables
let analyticsData = null;

// Utility functions
function showMessage(message, type = 'info') {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    messageDiv.style.cssText = `
        position: fixed; top: 20px; right: 20px; z-index: 1000;
        padding: 15px; border-radius: 5px; color: white;
        background: ${type === 'error' ? '#d32f2f' : type === 'success' ? '#388e3c' : '#1976d2'};
    `;
    messageDiv.textContent = message;
    document.body.appendChild(messageDiv);
    setTimeout(() => messageDiv.remove(), 5000);
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Workspace Templates Functions
function uploadWorkspaceTemplate() {
    const fileInput = document.getElementById('workspaceTemplateFile');
    const files = fileInput.files;
    
    if (!files || files.length === 0) {
        showMessage('Please select at least one file', 'error');
        return;
    }
    
    // Upload files one by one
    let uploadCount = 0;
    let successCount = 0;
    let errorCount = 0;
    
    Array.from(files).forEach((file, index) => {
        const formData = new FormData();
        formData.append('file', file);
        
        fetch('/api/proxy/workspace-templates', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            uploadCount++;
            if (data.success) {
                successCount++;
                showMessage(`${file.name} uploaded successfully!`, 'success');
            } else {
                errorCount++;
                showMessage(`Failed to upload ${file.name}: ${data.error}`, 'error');
            }
            
            // If all uploads are complete
            if (uploadCount === files.length) {
                loadWorkspaceTemplates();
                fileInput.value = '';
                if (successCount > 0) {
                    showMessage(`${successCount} file(s) uploaded successfully!`, 'success');
                }
                if (errorCount > 0) {
                    showMessage(`${errorCount} file(s) failed to upload`, 'error');
                }
            }
        })
        .catch(error => {
            uploadCount++;
            errorCount++;
            showMessage(`Upload failed for ${file.name}: ${error.message}`, 'error');
            
            // If all uploads are complete
            if (uploadCount === files.length) {
                loadWorkspaceTemplates();
                fileInput.value = '';
                if (successCount > 0) {
                    showMessage(`${successCount} file(s) uploaded successfully!`, 'success');
                }
                if (errorCount > 0) {
                    showMessage(`${errorCount} file(s) failed to upload`, 'error');
                }
            }
        });
    });
}

function loadWorkspaceTemplates() {
    fetch('/api/proxy/workspace-templates')
        .then(response => response.json())
        .then(data => {
            const templatesList = document.getElementById('workspaceTemplatesList');
            if (data.files && data.files.length > 0) {
                templatesList.innerHTML = data.files.map(file => `
                    <div class="file-item">
                        <span class="file-name">${file.name}</span>
                        <span class="file-size">${formatFileSize(file.size)}</span>
                        <span class="file-date">${new Date(file.modified).toLocaleDateString()}</span>
                        <button onclick="deleteWorkspaceTemplate('${file.name}')" class="delete-btn">Delete</button>
                    </div>
                `).join('');
            } else {
                templatesList.innerHTML = '<p>No workspace templates uploaded yet.</p>';
            }
        })
        .catch(error => {
            showMessage('Failed to load workspace templates: ' + error.message, 'error');
        });
}

function deleteWorkspaceTemplate(filename) {
    if (!confirm(`Are you sure you want to delete ${filename}?`)) return;
    
    fetch(`/api/proxy/workspace-templates/${filename}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Workspace template deleted successfully!', 'success');
            loadWorkspaceTemplates();
        } else {
            showMessage(data.error || 'Delete failed', 'error');
        }
    })
    .catch(error => {
        showMessage('Delete failed: ' + error.message, 'error');
    });
}

// Shared Resources Functions
function uploadSharedResource() {
    const fileInput = document.getElementById('sharedResourceFile');
    const files = fileInput.files;
    
    if (!files || files.length === 0) {
        showMessage('Please select at least one file', 'error');
        return;
    }
    
    // Upload files one by one
    let uploadCount = 0;
    let successCount = 0;
    let errorCount = 0;
    
    Array.from(files).forEach((file, index) => {
        const formData = new FormData();
        formData.append('file', file);
        
        fetch('/api/proxy/shared-resources', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            uploadCount++;
            if (data.success) {
                successCount++;
                showMessage(`${file.name} uploaded successfully!`, 'success');
            } else {
                errorCount++;
                showMessage(`Failed to upload ${file.name}: ${data.error}`, 'error');
            }
            
            // If all uploads are complete
            if (uploadCount === files.length) {
                loadSharedResources();
                fileInput.value = '';
                if (successCount > 0) {
                    showMessage(`${successCount} file(s) uploaded successfully!`, 'success');
                }
                if (errorCount > 0) {
                    showMessage(`${errorCount} file(s) failed to upload`, 'error');
                }
            }
        })
        .catch(error => {
            uploadCount++;
            errorCount++;
            showMessage(`Upload failed for ${file.name}: ${error.message}`, 'error');
            
            // If all uploads are complete
            if (uploadCount === files.length) {
                loadSharedResources();
                fileInput.value = '';
                if (successCount > 0) {
                    showMessage(`${successCount} file(s) uploaded successfully!`, 'success');
                }
                if (errorCount > 0) {
                    showMessage(`${errorCount} file(s) failed to upload`, 'error');
                }
            }
        });
    });
}

function loadSharedResources() {
    fetch('/api/proxy/shared-resources')
        .then(response => response.json())
        .then(data => {
            const resourcesList = document.getElementById('sharedResourcesList');
            if (data.files && data.files.length > 0) {
                resourcesList.innerHTML = data.files.map(file => `
                    <div class="file-item">
                        <span class="file-name">${file.name}</span>
                        <span class="file-size">${formatFileSize(file.size)}</span>
                        <span class="file-date">${new Date(file.modified).toLocaleDateString()}</span>
                        <button onclick="deleteSharedResource('${file.name}')" class="delete-btn">Delete</button>
                    </div>
                `).join('');
            } else {
                resourcesList.innerHTML = '<p>No shared resources uploaded yet.</p>';
            }
        })
        .catch(error => {
            showMessage('Failed to load shared resources: ' + error.message, 'error');
        });
}

function deleteSharedResource(filename) {
    if (!confirm(`Are you sure you want to delete ${filename}?`)) return;
    
    fetch(`/api/proxy/shared-resources/${filename}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Shared resource deleted successfully!', 'success');
            loadSharedResources();
        } else {
            showMessage(data.error || 'Delete failed', 'error');
        }
    })
    .catch(error => {
        showMessage('Delete failed: ' + error.message, 'error');
    });
}

// Learning Objectives Functions
function loadObjectives() {
    fetch('/api/proxy/learning-objectives')
        .then(response => response.json())
        .then(data => {
            const objectivesList = document.getElementById('objectivesList');
            
            if (data && Object.keys(data).length > 0) {
                objectivesList.innerHTML = Object.entries(data).map(([taskName, objective]) => `
                    <div class="objective-card">
                        <h3>📄 ${taskName}</h3>
                        <div class="objective-content">
                            ${objective ? objective.replace(/\n/g, '<br>') : '<em>No learning objective defined</em>'}
                        </div>
                        <div class="objective-actions">
                            <button onclick="editObjective('${taskName}')" class="edit-objective-btn">Edit Objective</button>
                        </div>
                    </div>
                `).join('');
            } else {
                objectivesList.innerHTML = '<div class="no-objectives">No learning objectives found. Upload workspace templates first, then define objectives for each task.</div>';
            }
        })
        .catch(error => {
            showMessage('Failed to load objectives: ' + error.message, 'error');
        });
}

function editObjective(taskName) {
    // Create modal HTML
    const modalHTML = `
        <div id="objectiveModal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Edit Learning Objective: ${taskName}</h3>
                    <span class="close" onclick="closeObjectiveModal()">&times;</span>
                </div>
                <form onsubmit="saveObjective(event, '${taskName}')">
                    <div class="form-group">
                        <label for="objectiveText">Learning Objective:</label>
                        <textarea id="objectiveText" placeholder="Loading existing content..." disabled></textarea>
                    </div>
                    <div class="modal-actions">
                        <button type="button" onclick="closeObjectiveModal()" class="button secondary">Cancel</button>
                        <button type="submit" class="button">Save Objective</button>
                    </div>
                </form>
            </div>
        </div>
    `;
    
    // Add modal to page
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    // Show modal immediately
    document.getElementById('objectiveModal').style.display = 'block';
    
    // Load current objective content
    fetch(`/api/proxy/learning-objectives/${taskName}`)
        .then(response => response.json())
        .then(data => {
            const textarea = document.getElementById('objectiveText');
            textarea.disabled = false;
            textarea.placeholder = "Enter the learning objective for this task...";
            
            if (data.content && data.content.trim()) {
                textarea.value = data.content;
                console.log(`Loaded content for ${taskName}:`, data.content.substring(0, 50) + '...');
            } else {
                textarea.value = '';
                console.log(`No content found for ${taskName}, starting with empty form`);
            }
        })
        .catch(error => {
            console.error(`Error loading content for ${taskName}:`, error);
            const textarea = document.getElementById('objectiveText');
            textarea.disabled = false;
            textarea.placeholder = "Enter the learning objective for this task...";
            textarea.value = '';
        });
}

function closeObjectiveModal() {
    const modal = document.getElementById('objectiveModal');
    if (modal) {
        modal.remove();
    }
}

function saveObjective(event, taskName) {
    event.preventDefault();
    
    const objectiveText = document.getElementById('objectiveText').value.trim();
    
    // Allow saving empty content (to clear objectives)
    
    fetch(`/api/proxy/learning-objectives/${taskName}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content: objectiveText })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Learning objective saved successfully!', 'success');
            closeObjectiveModal();
            loadObjectives();
        } else {
            showMessage(data.error || 'Save failed', 'error');
        }
    })
    .catch(error => {
        showMessage('Save failed: ' + error.message, 'error');
    });
}

// Close modal when clicking outside of it
window.onclick = function(event) {
    const modal = document.getElementById('objectiveModal');
    if (event.target === modal) {
        closeObjectiveModal();
    }
}

// Analytics Functions
function toggleAnalytics() {
    const content = document.getElementById('analyticsContent');
    const toggle = document.getElementById('analyticsToggle');
    
    if (content.style.display === 'none') {
        content.style.display = 'block';
        toggle.textContent = '▲';
    } else {
        content.style.display = 'none';
        toggle.textContent = '▼';
    }
}

function loadAnalytics() {
    fetch('/api/proxy/analytics/students')
        .then(response => response.json())
        .then(students => {
            // Calculate summary statistics from raw student data
            const totalStudents = students.length;
            const totalMessages = students.reduce((sum, student) => sum + student.message_count, 0);
            const avgMessages = totalStudents > 0 ? Math.round(totalMessages / totalStudents * 10) / 10 : 0;
            
            const summaryData = {
                total_students: totalStudents,
                total_messages: totalMessages,
                avg_messages_per_student: avgMessages,
                total_tasks: 0, // This would need to be calculated if task data is available
                students: students.map(student => ({
                    student_id: student.username,
                    message_count: student.message_count,
                    unique_tasks: 0, // This would need task data
                    last_message: student.last_interaction * 1000 // Convert timestamp to milliseconds
                }))
            };
            
            analyticsData = summaryData;
            updateAnalyticsSummary(summaryData);
            loadStudentsList(summaryData.students);
        })
        .catch(error => {
            showMessage('Failed to load analytics: ' + error.message, 'error');
        });
}

function updateAnalyticsSummary(data) {
    document.getElementById('totalStudents').textContent = data.total_students || 0;
    document.getElementById('totalMessages').textContent = data.total_messages || 0;
    document.getElementById('avgMessages').textContent = data.avg_messages_per_student || 0;
    document.getElementById('totalTasks').textContent = data.total_tasks || 0;
}

function loadStudentsList(students) {
    const studentsList = document.getElementById('studentsList');
    if (students.length > 0) {
        studentsList.innerHTML = students.map(student => `
            <div class="student-card" onclick="showStudentDetails('${student.student_id}')">
                <h4>${student.student_id}</h4>
                <p>Messages: ${student.message_count}</p>
                <p>Tasks: ${student.unique_tasks}</p>
                <p>Last Activity: ${new Date(student.last_message).toLocaleDateString()}</p>
            </div>
        `).join('');
    } else {
        studentsList.innerHTML = '<p>No student data available.</p>';
    }
}

function showStudentDetails(studentId) {
    if (!analyticsData || !analyticsData.students) return;
    
    const student = analyticsData.students.find(s => s.student_id === studentId);
    if (!student) return;
    
    const details = `
        Student ID: ${student.student_id}
        Total Messages: ${student.message_count}
        Unique Tasks: ${student.unique_tasks}
        First Message: ${new Date(student.first_message).toLocaleString()}
        Last Message: ${new Date(student.last_message).toLocaleString()}
    `;
    
    alert(details);
}

// Initialize dashboard when page loads
window.onload = function() {
    loadWorkspaceTemplates();
    loadSharedResources();
    loadObjectives();
    loadAnalytics();
};
