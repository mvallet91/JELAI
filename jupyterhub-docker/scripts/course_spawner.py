from dockerspawner import DockerSpawner
from tornado import gen
import httpx
import os
from traitlets import Unicode

class CourseDockerSpawner(DockerSpawner):

    course_id = Unicode('', config=True, help="The course ID to spawn for")

    async def get_options_form(self):
        middleware_url = os.environ.get('MIDDLEWARE_URL', 'http://middleware:8005')
        username = self.user.name
        courses = []
        try:
            async with httpx.AsyncClient() as client:
                headers = {'Authorization': f'Bearer {username}'}
                if self.user.admin:
                    headers['X-JELAI-ADMIN'] = 'true'
                resp = await client.get(f"{middleware_url}/api/courses", headers=headers)
                if resp.status_code == 200:
                    courses = resp.json()
                else:
                    self.log.error(f"Failed to get courses for user {username}: {resp.status_code} {resp.text}")
        except Exception as e:
            self.log.error(f"Failed to get courses for user {username}: {e}")

        if not courses:
            return """
            <p>You are not enrolled in any courses. Please contact your administrator.</p>
            """

        # Always show the course selection form if more than one course, or if no course is selected yet
        options = ""
        for course in courses:
            options += f"<option value='{course['id']}'>{course['title']}</option>"

        return f"""
        <label for="course">Select a course:</label>
        <select name="course_id" id="course" required>
            <option value="" disabled selected>Select your course</option>
            {options}
        </select>
        <br><br>
        <input type="submit" value="Launch Server">
        """
    
    def options_from_form(self, formdata):
        options = {}
        options['course_id'] = formdata.get('course_id', [''])[0]
        return options

    async def start(self, *args, **kwargs):
        self.course_id = self.user_options.get('course_id')
        if self.course_id:
            self.log.info(f"Spawning container for user {self.user.name} for course {self.course_id}")
            self.environment['SELECTED_COURSE_ID'] = self.course_id
        return await super().start(*args, **kwargs)
