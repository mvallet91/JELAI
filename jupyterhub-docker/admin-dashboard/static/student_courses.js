document.addEventListener('DOMContentLoaded', () => {
    const studentName = document.getElementById('studentName');
    const coursesList = document.getElementById('coursesList');
    const noCourses = document.getElementById('noCourses');
    let studentId = null;

    // Fetch student info (simulate, replace with real auth/user fetch)
    fetch('/api/proxy/user')
        .then(r => r.json())
        .then(user => {
            studentName.textContent = user.full_name || user.name;
            studentId = user.id;
            loadCourses();
        });

    function loadCourses() {
        fetch(`/api/proxy/users/${studentId}`)
            .then(r => r.json())
            .then(student => {
                if (!student.enrolled_courses || student.enrolled_courses.length === 0) {
                    coursesList.style.display = 'none';
                    noCourses.style.display = 'block';
                } else {
                    coursesList.style.display = 'block';
                    noCourses.style.display = 'none';
                    renderCourses(student.enrolled_courses);
                }
            });
    }

    function renderCourses(courses) {
        coursesList.innerHTML = '';
        courses.forEach(course => {
            const div = document.createElement('div');
            div.className = 'card';
            div.textContent = course.name;
            div.onclick = () => launchCourse(course);
            coursesList.appendChild(div);
        });
    }

    function launchCourse(course) {
        // Launch JupyterLab for the selected course by redirecting to the spawner
        window.location.href = `/hub/spawn?course_id=${course.id}`;
    }
});
