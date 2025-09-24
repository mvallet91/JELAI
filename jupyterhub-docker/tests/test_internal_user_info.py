import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'middleware'))
from admin_api import app, get_user_from_request

client = TestClient(app)

# Simple monkeypatch for get_user_from_request for these tests
@app.middleware('http')
async def inject_test_user(request, call_next):
    test_user = request.headers.get('X-Test-User')
    if test_user:
        request.scope['x_test_user'] = test_user
    response = await call_next(request)
    return response

def override_get_user_from_request(request):
    return request.headers.get('X-Test-User', 'anonymous')

app.dependency_overrides[get_user_from_request] = override_get_user_from_request

def test_internal_user_info_unknown():
    r = client.get('/api/internal/user-info', params={'username': 'ghost'})
    assert r.status_code == 200
    data = r.json()
    assert data['username'] == 'ghost'
    assert data['role'] is None

# We rely on initialize_db seeding: admin, teacher1, student1

def test_internal_user_info_seeded_admin():
    r = client.get('/api/internal/user-info', params={'username': 'admin'})
    assert r.status_code == 200
    data = r.json()
    assert data['username'] == 'admin'


def test_admin_course_list_requires_admin():
    # Non-admin should be forbidden
    r = client.get('/api/admin/courses', headers={'Authorization': 'Bearer teacher1'})
    assert r.status_code == 403


def test_admin_course_list_as_admin():
    r = client.get('/api/admin/courses', headers={'Authorization': 'Bearer admin'})
    # 200 even if empty courses
    assert r.status_code == 200
    assert isinstance(r.json(), list)
