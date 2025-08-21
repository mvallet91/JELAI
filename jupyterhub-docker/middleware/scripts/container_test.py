"""
Quick container-side test script to call middleware endpoints using X-JELAI-ADMIN header
Run inside the middleware container or with network access to middleware at http://localhost:8005
"""
import requests
import os

base = os.environ.get('MIDDLEWARE_URL', 'http://localhost:8005')
headers = {'X-JELAI-ADMIN': 'true'}

print('Listing courses (direct middleware):')
r = requests.get(f'{base}/api/courses', headers=headers)
print(r.status_code)
print(r.text)

print('\nCreating test course:')
payload = {'title':'container-test-course','description':'created from container test'}
r = requests.post(f'{base}/api/courses', json=payload, headers=headers)
print(r.status_code)
print(r.text)

if r.status_code in (200,201):
    cid = r.json().get('id')
    if cid:
        print('\nAssigning teacher via form:')
        f = {'teacher':'container_admin'}
        r2 = requests.post(f'{base}/api/courses/{cid}/assign-teacher', data=f, headers=headers)
        print(r2.status_code, r2.text)

        print('\nEnrolling student via form:')
        f2 = {'student':'container_student'}
        r3 = requests.post(f'{base}/api/courses/{cid}/enroll', data=f2, headers=headers)
        print(r3.status_code, r3.text)
else:
    print('Create failed; status code', r.status_code)
