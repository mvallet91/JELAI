import json


def test_admin_can_create_and_list_course(client):
    # Admin creates a course
    resp = client.post('/api/courses', json={'title': 'New Course', 'description': 'desc'}, headers={'Authorization': 'Bearer admin'})
    assert resp.status_code == 200 or resp.status_code == 201
    course = resp.json()
    assert course['title'] == 'New Course'

    # Admin can list courses and see the new one
    resp = client.get('/api/courses', headers={'Authorization': 'Bearer admin'})
    assert resp.status_code == 200
    courses = resp.json()
    assert any(c['id'] == course['id'] for c in courses)


def test_teacher_sees_only_assigned_courses(client):
    # Create two courses as admin
    r1 = client.post('/api/courses', json={'title': 'Course A'}, headers={'Authorization': 'Bearer admin'})
    r2 = client.post('/api/courses', json={'title': 'Course B'}, headers={'Authorization': 'Bearer admin'})
    c1 = r1.json()
    c2 = r2.json()

    # Assign teacher1 to Course A
    resp = client.post(f"/api/courses/{c1['id']}/assign-teacher", data={'teacher': 'teacher1'}, headers={'Authorization': 'Bearer admin'})
    assert resp.status_code == 200

    # As teacher1, GET /api/courses should return only Course A
    r = client.get('/api/courses', headers={'Authorization': 'Bearer teacher1'})
    assert r.status_code == 200
    courses = r.json()
    ids = [c['id'] for c in courses]
    assert c1['id'] in ids
    assert c2['id'] not in ids


def test_teacher_can_enroll_student_in_their_course(client):
    # Admin creates course and assigns teacher
    r = client.post('/api/courses', json={'title': 'Enroll Course'}, headers={'Authorization': 'Bearer admin'})
    course = r.json()
    client.post(f"/api/courses/{course['id']}/assign-teacher", data={'teacher': 'teacher1'}, headers={'Authorization': 'Bearer admin'})

    # Teacher enrolls a student
    r = client.post(f"/api/courses/{course['id']}/enroll", data={'student': 'student1'}, headers={'Authorization': 'Bearer teacher1'})
    assert r.status_code == 200
    updated = r.json()
    assert 'student1' in updated['students']


def test_student_cannot_enroll_others(client):
    # Admin creates a course and assigns teacher
    r = client.post('/api/courses', json={'title': 'Student Course'}, headers={'Authorization': 'Bearer admin'})
    course = r.json()
    client.post(f"/api/courses/{course['id']}/assign-teacher", data={'teacher': 'teacher1'}, headers={'Authorization': 'Bearer admin'})

    # A student tries to enroll another student -> 403
    r = client.post(f"/api/courses/{course['id']}/enroll", data={'student': 'student2'}, headers={'Authorization': 'Bearer student1'})
    assert r.status_code == 403
