document.addEventListener('DOMContentLoaded', () => {
    const userInfo = document.getElementById('userInfo');
    const coursesList = document.getElementById('courses-list');
    const addCourseBtn = document.getElementById('add-course-btn');
    const courseDetailView = document.getElementById('course-detail-view');
    const courseDetailName = document.getElementById('course-detail-name');
    const courseTeachersList = document.getElementById('course-teachers-list');
    const courseStudentsList = document.getElementById('course-students-list');
    const backToCoursesBtn = document.getElementById('back-to-courses-btn');

    // Fetch user info
    fetch('/api/user')
        .then(response => response.json())
        .then(user => {
            userInfo.textContent = `Welcome, ${user.name}`;
        });

    // Fetch and display courses
    function loadCourses() {
        fetch('/api/proxy/courses')
            .then(response => response.json())
            .then(courses => {
                coursesList.innerHTML = '';
                courses.forEach(course => {
                    const courseElement = document.createElement('div');
                    courseElement.className = 'course-item';
                    courseElement.textContent = course.name;
                    courseElement.onclick = () => showCourseDetails(course);
                    coursesList.appendChild(courseElement);
                });
            });
    }

    function showCourseDetails(course) {
        document.getElementById('courses-section').style.display = 'none';
        courseDetailView.style.display = 'block';
        courseDetailName.textContent = course.name;
        
        // Fetch and display teachers
        fetch(`/api/proxy/courses/${course.id}/teachers`)
            .then(response => response.json())
            .then(teachers => {
                courseTeachersList.innerHTML = '';
                teachers.forEach(teacher => {
                    const li = document.createElement('li');
                    li.textContent = teacher.username;
                    courseTeachersList.appendChild(li);
                });
            });

        // Fetch and display students
        fetch(`/api/proxy/courses/${course.id}/students`)
            .then(response => response.json())
            .then(students => {
                courseStudentsList.innerHTML = '';
                students.forEach(student => {
                    const li = document.createElement('li');
                    li.textContent = student.username;
                    courseStudentsList.appendChild(li);
                });
            });
    }

    backToCoursesBtn.addEventListener('click', () => {
        courseDetailView.style.display = 'none';
        document.getElementById('courses-section').style.display = 'block';
    });

    // Add new course
    addCourseBtn.addEventListener('click', () => {
        const courseName = prompt('Enter the name of the new course:');
        if (courseName) {
            fetch('/api/proxy/courses', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ name: courseName, description: "New course", learning_materials_path: `/workspace/materials/${courseName}` })
            })
            .then(response => response.json())
            .then(newCourse => {
                loadCourses();
            });
        }
    });

    loadCourses();
});