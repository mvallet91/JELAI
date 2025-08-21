// JELAI Admin Dashboard JavaScript

// Global variables
let analyticsData = null;

// Helper function to build API URLs with service prefix
function apiUrl(endpoint) {
    const prefix = window.SERVICE_PREFIX || '';
    const url = prefix + '/api/proxy/' + endpoint;
    // console.log('API URL:', url, 'for endpoint:', endpoint, 'with prefix:', prefix);
    return url;
}

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
        
        fetch(apiUrl('workspace-templates'), {
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
    fetch(apiUrl('workspace-templates'))
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
    
    fetch(apiUrl(`workspace-templates/${filename}`), {
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
        
        fetch(apiUrl('shared-resources'), {
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
    fetch(apiUrl('shared-resources'))
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
    
    fetch(apiUrl(`shared-resources/${filename}`), {
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
    fetch(apiUrl('learning-objectives'))
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
    fetch(apiUrl(`learning-objectives/${taskName}`))
        .then(response => response.json())
        .then(data => {
            const textarea = document.getElementById('objectiveText');
            textarea.disabled = false;
            textarea.placeholder = "Enter the learning objective for this task...";
            
            if (data.content && data.content.trim()) {
                textarea.value = data.content;
                // console.log(`Loaded content for ${taskName}:`, data.content.substring(0, 50) + '...');
            } else {
                textarea.value = '';
                // console.log(`No content found for ${taskName}, starting with empty form`);
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
    
    fetch(apiUrl(`learning-objectives/${taskName}`), {
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
    fetch(apiUrl('analytics/students'))
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

// AI Configuration Functions
function loadTutorPrompt() {
    fetch(apiUrl('prompts/tutor'))
        .then(response => response.json())
        .then(data => {
            const textarea = document.getElementById('tutorPrompt');
            textarea.disabled = false;
            textarea.value = data.content || '';
            textarea.placeholder = 'Enter the system prompt for the Tutor Agent (Juno)...';
        })
        .catch(error => {
            showMessage('Failed to load tutor prompt: ' + error.message, 'error');
            document.getElementById('tutorPrompt').disabled = false;
        });
}

function loadExpertPrompt() {
    fetch(apiUrl('prompts/expert'))
        .then(response => response.json())
        .then(data => {
            const textarea = document.getElementById('expertPrompt');
            textarea.disabled = false;
            textarea.value = data.content || '';
            textarea.placeholder = 'Enter the system prompt for the Expert Agent...';
        })
        .catch(error => {
            showMessage('Failed to load expert prompt: ' + error.message, 'error');
            document.getElementById('expertPrompt').disabled = false;
        });
}

function saveTutorPrompt() {
    const content = document.getElementById('tutorPrompt').value;
    
    fetch(apiUrl('prompts/tutor'), {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content: content })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Tutor prompt saved successfully!', 'success');
        } else {
            showMessage('Failed to save tutor prompt: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        showMessage('Save failed: ' + error.message, 'error');
    });
}

function saveExpertPrompt() {
    const content = document.getElementById('expertPrompt').value;
    
    fetch(apiUrl('prompts/expert'), {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content: content })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Expert prompt saved successfully!', 'success');
        } else {
            showMessage('Failed to save expert prompt: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        showMessage('Save failed: ' + error.message, 'error');
    });
}

function resetTutorPrompt() {
    if (!confirm('Are you sure you want to reset the tutor prompt to default? This will overwrite any custom changes.')) {
        return;
    }
    
    // You could implement a default prompt restoration here
    // For now, just clear the textarea
    document.getElementById('tutorPrompt').value = '';
    showMessage('Tutor prompt cleared. Enter a new prompt and save.', 'info');
}

function resetExpertPrompt() {
    if (!confirm('Are you sure you want to reset the expert prompt to default? This will overwrite any custom changes.')) {
        return;
    }
    
    // You could implement a default prompt restoration here
    // For now, just clear the textarea
    document.getElementById('expertPrompt').value = '';
    showMessage('Expert prompt cleared. Enter a new prompt and save.', 'info');
}

function reloadLearningObjectives() {
    if (!confirm('Are you sure you want to reload learning objectives? This will refresh all learning objectives from the files without restarting the system.')) {
        return;
    }
    
    // console.log('Reloading learning objectives...');
    
    fetch(apiUrl('reload-learning-objectives'), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            showMessage('Learning objectives reloaded successfully! Changes are now active.', 'success');
            // Optionally refresh the objectives display
            loadObjectives();
        } else {
            showMessage(`Failed to reload learning objectives: ${data.message}`, 'error');
        }
    })
    .catch(error => {
        console.error('Error reloading learning objectives:', error);
        showMessage('Network error while reloading learning objectives. Please try again.', 'error');
    });
}

// Initialize dashboard when page loads
window.onload = function() {
    loadWorkspaceTemplates();
    loadSharedResources();
    loadObjectives();
    loadAnalytics();
    loadTutorPrompt();
    loadExpertPrompt();
    // Load current user first, then refresh courses so UI can hide/show controls
    loadCurrentUser().then(() => refreshCourses());
};

// --- Courses UI functions ---
function loadCurrentUser() {
    // Use the admin-dashboard proxy to resolve the effective user and roles
    return fetch(apiUrl('user'))
        .then(r => r.json())
        .then(user => {
            // user shape: { name, admin, teacher_of: [...], enrolled_in: [...] }
            window.currentUserObj = user || { name: 'unknown', admin: false, teacher_of: [], enrolled_in: [] };
            window.currentUser = window.currentUserObj.name || 'unknown';
            const el = document.getElementById('currentCourseDisplay');
            if (el && localStorage.getItem('selectedCourseTitle')) {
                el.textContent = `Selected: ${localStorage.getItem('selectedCourseTitle')}`;
            }
            return window.currentUserObj;
        })
        .catch(err => {
            console.warn('Could not fetch current user', err);
            window.currentUserObj = { name: 'unknown', admin: false, teacher_of: [], enrolled_in: [] };
            window.currentUser = window.currentUserObj.name;
            return window.currentUserObj;
        });
}

function refreshCourses() {
    fetch(apiUrl('courses'))
        .then(r => r.json())
        .then(courses => renderCourses(courses))
        .catch(err => showMessage('Failed to load courses: ' + err.message, 'error'));
}

function renderCourses(courses) {
    const container = document.getElementById('coursesList');
    if (!container) return;
    if (!courses || courses.length === 0) {
        container.innerHTML = '<p>No courses available.</p>';
        return;
    }

    // Ensure we have the current user roles resolved
    const user = window.currentUserObj || { name: 'unknown', admin: false, teacher_of: [], enrolled_in: [] };

    container.innerHTML = courses.map(c => {
        const isAdmin = !!user.admin;
        const isTeacher = Array.isArray(user.teacher_of) && user.teacher_of.indexOf(c.id) !== -1;
        const canEnroll = isAdmin || isTeacher;
        const assignBtn = isAdmin ? `<button onclick="assignMeAsTeacher('${c.id}')" class="button small">Assign Me as Teacher</button>` : '';
        const enrollBtn = canEnroll ? `<button onclick="promptEnroll('${c.id}')" class="button small">Enroll Student</button>` : '';
        const selectBtn = `<button onclick="selectCourse('${c.id}', '${escapeHtml(c.title)}')" class="button small">Select Course</button>`;

        return `
        <div class="course-card">
            <h4>${c.title}</h4>
            <p>${c.description || ''}</p>
            <p>Teachers: ${c.teachers.join(', ') || 'None'}</p>
            <p>Students: ${c.students.join(', ') || 'None'}</p>
            <div class="course-actions">
                ${assignBtn}
                ${enrollBtn}
                ${selectBtn}
            </div>
        </div>
    `;
    }).join('');
}

function escapeHtml(s) {
    return s.replace(/'/g, "\\'").replace(/"/g, '\\"');
}

function createCoursePrompt() {
    const title = prompt('Enter course title:');
    if (!title) return;
    const description = prompt('Enter course description (optional):') || '';
    fetch(apiUrl('courses'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title, description: description })
    })
    .then(r => r.json())
    .then(data => {
        showMessage('Course created: ' + (data.title || data.id), 'success');
        refreshCourses();
    })
    .catch(err => showMessage('Failed to create course: ' + err.message, 'error'));
}

function assignMeAsTeacher(courseId) {
    // POST to assign-teacher with form body
    const form = new URLSearchParams();
    form.append('teacher', window.currentUser || 'admin');
    fetch(apiUrl(`courses/${courseId}/assign-teacher`), {
        method: 'POST',
        body: form
    })
    .then(r => r.json())
    .then(data => {
        showMessage('Assigned as teacher', 'success');
        refreshCourses();
    })
    .catch(err => showMessage('Failed to assign teacher: ' + err.message, 'error'));
}

function promptEnroll(courseId) {
    const student = prompt('Enter student username to enroll:');
    if (!student) return;
    const form = new URLSearchParams();
    form.append('student', student);
    fetch(apiUrl(`courses/${courseId}/enroll`), {
        method: 'POST',
        body: form
    })
    .then(r => r.json())
    .then(data => {
        showMessage('Student enrolled', 'success');
        refreshCourses();
    })
    .catch(err => showMessage('Failed to enroll student: ' + err.message, 'error'));
}

function selectCourse(courseId, title) {
    localStorage.setItem('selectedCourse', courseId);
    localStorage.setItem('selectedCourseTitle', title);
    const el = document.getElementById('currentCourseDisplay');
    if (el) el.textContent = `Selected: ${title}`;
    showMessage('Selected course: ' + title, 'success');
}

// Expose functions to global window so inline onclick handlers work even if JS executes in strict mode
window.refreshCourses = refreshCourses;
window.createCoursePrompt = createCoursePrompt;
window.assignMeAsTeacher = assignMeAsTeacher;
window.promptEnroll = promptEnroll;
window.selectCourse = selectCourse;
