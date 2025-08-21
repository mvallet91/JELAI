Development auth bypass for admin-dashboard

This file documents the `ALLOW_DEV_AUTH` development flag added to `app.py`.

Purpose
- Allow testing the dashboard proxy and API calls from `curl` / CLI without a JupyterHub cookie or full OAuth flow during local development.

How it works
- If the environment variable `ALLOW_DEV_AUTH` is set to `1`, `true`, or `yes`, the dashboard will accept lightweight authentication forms for development-only testing.
- Accepted forms when `ALLOW_DEV_AUTH` is enabled:
  - HTTP header: `Authorization: Bearer <username>`
  - Query parameter: `?user=<username>`
  - Header override: `X-DEV-USER: <username>`
- To mark a dev user as admin for testing, set header `X-ADMIN: true` or use the same username as `ADMIN_USER` env var.

Security
- This bypass is FOR DEVELOPMENT ONLY. Never enable `ALLOW_DEV_AUTH` in production.

Examples (run admin-dashboard locally on port 8006)

1) List courses via dashboard proxy as teacher "teacher1":

```bash
curl -v 'http://localhost:8006/api/proxy/courses' -H 'Authorization: Bearer teacher1'
```

(note: if the service is mounted at a JupyterHub service prefix when run behind Hub, include the prefix e.g. `/services/learn-dashboard/api/proxy/courses`)

2) Create a course as admin using the dev admin flag:

```bash
curl -v -X POST 'http://localhost:8006/api/proxy/courses' \
  -H 'Authorization: Bearer admin' \
  -H 'Content-Type: application/json' \
  -d '{"title":"Test Course","description":"dev created"}'
```

3) Enroll a student into a course (teacher or admin allowed):

```bash
curl -v -X POST 'http://localhost:8006/api/proxy/courses/<course_id>/enroll' \
  -H 'Authorization: Bearer teacher1' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data 'student=student1'
```

Direct middleware testing (without proxy)
- Middleware already supports simple header or query param authentication. You can call middleware directly (typically at port 8005):

```bash
curl -v 'http://localhost:8005/api/courses' -H 'Authorization: Bearer teacher1'

curl -v -X POST 'http://localhost:8005/api/courses/<id>/enroll' \
  -H 'Authorization: Bearer teacher1' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data 'student=student1'
```

Environment variables useful when testing
- `ALLOW_DEV_AUTH=1` (enables dev bypass in dashboard)
- `ADMIN_USER` (username treated as admin by middleware/dev flag), default `admin`

If you want, I can add a small test script to exercise common flows using the dev auth bypass.
