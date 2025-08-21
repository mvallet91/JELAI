import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure middleware package is importable by adding its directory to sys.path
HERE = Path(__file__).resolve().parent
MIDDLEWARE_PATH = HERE.parent / 'middleware'
if str(MIDDLEWARE_PATH) not in sys.path:
    sys.path.insert(0, str(MIDDLEWARE_PATH))
# Also support running tests from inside the middleware container where the
# application lives at /app and tests are copied to /app/tests. Add /app to
# sys.path so `import admin_api` works in that environment.
if '/app' not in sys.path:
    sys.path.insert(0, '/app')

@pytest.fixture(scope='function')
def client(tmp_path, monkeypatch):
    # Configure a per-test courses data dir before importing middleware modules
    data_dir = tmp_path / 'data'
    monkeypatch.setenv('COURSES_DATA_DIR', str(data_dir))
    monkeypatch.setenv('ALLOW_DEV_AUTH', '1')
    # Ensure the data dir exists
    data_dir.mkdir(parents=True, exist_ok=True)

    # Import the middleware app AFTER environment is set so modules pick up env vars
    import importlib
    # Try several import strategies in order:
    # 1) top-level 'admin_api' (when running from source)
    # 2) installed package 'middleware.admin_api' (when middleware is pip-installed)
    # 3) load source file directly from known paths
    admin_api = None
    try:
        admin_api = importlib.import_module('admin_api')
    except ModuleNotFoundError:
        try:
            admin_api = importlib.import_module('middleware.admin_api')
        except ModuleNotFoundError:
            # Fall through to file loading below
            admin_api = None
    if admin_api is None:
        # Fallback: try to load the source file directly from the middleware path
        import importlib.util
        possible_paths = [MIDDLEWARE_PATH / 'admin_api.py', Path('/app') / 'admin_api.py']
        loaded = False
        for p in possible_paths:
            p = Path(p)
            if p.exists():
                spec = importlib.util.spec_from_file_location('admin_api', str(p))
                module = importlib.util.module_from_spec(spec)
                sys.modules['admin_api'] = module
                spec.loader.exec_module(module)
                admin_api = module
                loaded = True
                break
        if not loaded:
            raise
    # reload courses module to ensure it uses the monkeypatched COURSES_DATA_DIR
    import courses as courses_mod
    importlib.reload(courses_mod)

    client = TestClient(admin_api.app)
    yield client

    # Teardown: remove any created files (tmp_path is cleaned by pytest)
