document.addEventListener('DOMContentLoaded', () => {
    const analyticsContent = document.getElementById('analyticsContent');
    const analyticsToggle = document.getElementById('analyticsToggle');
    const totalStudents = document.getElementById('totalStudents');
    const totalMessages = document.getElementById('totalMessages');
    const avgMessages = document.getElementById('avgMessages');
    const totalTasks = document.getElementById('totalTasks');
    const studentsOverviewList = document.getElementById('studentsOverviewList');

    // ... (existing code)

    function showCourseDetail(course) {
        currentCourse = course;
        courseTitle.textContent = course.name;
        coursesSection.style.display = 'none';
        courseDetailSection.style.display = 'block';
        showTab('students');
        loadStudents();
        loadAssignments();
        loadAnalytics();
    }

    // ... (existing code)

    function showTab(tab) {
        studentsTab.style.display = tab === 'students' ? 'block' : 'none';
        assignmentsTab.style.display = tab === 'assignments' ? 'block' : 'none';
        analyticsContent.style.display = tab === 'analytics' ? 'block' : 'none';
    }

    // ... (existing code for students and assignments)

    // Analytics
    function loadAnalytics() {
        fetch(`/api/proxy/courses/${currentCourse.id}/analytics`)
            .then(r => r.json())
            .then(data => {
                totalStudents.textContent = data.total_students;
                totalMessages.textContent = data.total_messages;
                avgMessages.textContent = data.avg_messages_per_student;
                totalTasks.textContent = data.unique_tasks;
                renderStudentAnalytics(data.students_overview);
            });
    }

    function renderStudentAnalytics(students) {
        studentsOverviewList.innerHTML = '';
        students.forEach(student => {
            const div = document.createElement('div');
            div.className = 'card';
            div.innerHTML = `<strong>${student.username}</strong>: ${student.message_count} messages`;
            studentsOverviewList.appendChild(div);
        });
    }

    analyticsToggle.onclick = () => {
        const isVisible = analyticsContent.style.display !== 'none';
        analyticsContent.style.display = isVisible ? 'none' : 'block';
        analyticsToggle.textContent = isVisible ? '▼' : '▲';
    };
});
