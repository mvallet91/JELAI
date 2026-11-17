"""Test setup: import the middleware modules without the heavy dependencies.

The tests replace fastembed with a small stub, and
use a temporary inputs directory and database.
"""

import shutil
import sys
import types
from pathlib import Path

import pytest

MIDDLEWARE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MIDDLEWARE_DIR))


def _install_stubs():
    # No model download in tests: the matcher uses fuzzy matching.
    if "fastembed" not in sys.modules:
        fastembed = types.ModuleType("fastembed")

        class TextEmbedding:  # stub
            def __init__(self, *args, **kwargs):
                raise RuntimeError("no embedding model in tests")

        fastembed.TextEmbedding = TextEmbedding
        sys.modules["fastembed"] = fastembed


_install_stubs()


@pytest.fixture
def inputs_dir(tmp_path, monkeypatch):
    """A copy of the inputs directory, with the defaults file next to it."""
    target = tmp_path / "inputs"
    shutil.copytree(MIDDLEWARE_DIR / "inputs", target)
    defaults = tmp_path / "defaults" / "agent_config.yaml"
    defaults.parent.mkdir()
    shutil.copy(MIDDLEWARE_DIR / "inputs" / "agent_config.yaml", defaults)
    return target
