import io
import zipfile

import pytest

import course_materials as cm


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv("COURSE_MATERIALS_DIR", str(tmp_path))
    return tmp_path


def test_save_and_list(root):
    cm.save_file("Task1.ipynb", b"{}")
    cm.save_file("data/x.csv", b"a,b")
    assert [f["path"] for f in cm.list_files()] == ["Task1.ipynb", "data/x.csv"]


@pytest.mark.parametrize("bad", ["", "../x", "a/../../x", "/etc/passwd/..", ".hidden", "a/.b", "course.yaml"])
def test_unsafe_paths_are_refused(root, bad):
    with pytest.raises(cm.MaterialsError):
        cm.save_file(bad, b"x")
    assert cm.list_files() == []


def test_zip_extracts_and_skips_metadata_and_unsafe_names(root):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("Week1/Task1.ipynb", "{}")
        z.writestr("__MACOSX/Week1/._Task1.ipynb", "x")
        z.writestr("../evil.txt", "x")
    saved = cm.extract_zip(buffer.getvalue())
    assert [s["path"] for s in saved] == ["Week1/Task1.ipynb"]
    assert not (root.parent / "evil.txt").exists()


def test_zip_without_files_is_refused(root):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("../evil.txt", "x")
    with pytest.raises(cm.MaterialsError):
        cm.extract_zip(buffer.getvalue())


def test_size_limit(root, monkeypatch):
    monkeypatch.setenv("COURSE_MATERIALS_MAX_MB", "1")
    with pytest.raises(cm.MaterialsError):
        cm.save_file("big.bin", b"x" * (1024 * 1024 + 1))


def test_start_notebook(root):
    assert cm.get_start_notebook() == ""
    with pytest.raises(cm.MaterialsError):
        cm.set_start_notebook("missing.ipynb")
    cm.save_file("Week1/Task1.ipynb", b"{}")
    assert cm.set_start_notebook("Week1/Task1.ipynb") == "Week1/Task1.ipynb"
    assert cm.get_start_notebook() == "Week1/Task1.ipynb"
    assert cm.set_start_notebook("") == ""
    assert cm.get_start_notebook() == ""


def test_delete(root):
    cm.save_file("data/x.csv", b"a")
    cm.delete_path("data")
    assert cm.list_files() == []
    with pytest.raises(cm.MaterialsError):
        cm.delete_path("data")
