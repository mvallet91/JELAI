"""Test setup: import the middleware modules without the heavy dependencies.

The tests replace sentence_transformers and torch with small stubs, and
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
    if "sentence_transformers" not in sys.modules:
        st = types.ModuleType("sentence_transformers")

        class SentenceTransformer:  # noqa: D401 - stub
            def __init__(self, *args, **kwargs):
                raise RuntimeError("no embedding model in tests")

        st.SentenceTransformer = SentenceTransformer
        st.util = types.SimpleNamespace(cos_sim=None)
        sys.modules["sentence_transformers"] = st
    if "torch" not in sys.modules:
        torch = types.ModuleType("torch")
        torch.cuda = types.SimpleNamespace(is_available=lambda: False)
        sys.modules["torch"] = torch


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
