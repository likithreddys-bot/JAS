import pytest

from app.tools.base import Risk
from app.tools.files import FileAccess, FileAccessError, file_tools


@pytest.fixture
def home(tmp_path):
    root = tmp_path / "home"
    (root / "project").mkdir(parents=True)
    (root / "project" / "schemas.py").write_text("class User:\n    name: str\n", encoding="utf-8")
    (root / "project" / ".env").write_text("GEMINI_API_KEY=secret", encoding="utf-8")
    (root / "AppData" / "Local").mkdir(parents=True)
    access = FileAccess(root, tmp_path / "backups", tmp_path / "notes")
    return root, access, {t.name: t for t in file_tools(access)}


def test_paths_stay_inside_the_allowed_folder(home):
    root, access, _ = home
    assert access.resolve("project/schemas.py") == (root / "project" / "schemas.py").resolve()
    for outside in ["../outside.txt", "C:/Windows/System32/drivers/etc/hosts", "project/../../escape.txt"]:
        with pytest.raises(FileAccessError):
            access.resolve(outside)
    with pytest.raises(FileAccessError, match="off limits"):
        access.resolve("AppData/Local/secrets.db")


def test_reads_code_but_never_secret_files(home):
    root, _, tools = home
    result = tools["read_file"].run(path="project/schemas.py")
    assert result.ok and "class User" in result.data["content"] and result.data["lines"] == 3
    secret = tools["read_file"].run(path="project/.env")
    assert not secret.ok and "secret files" in secret.error


def test_find_list_and_create(home):
    root, _, tools = home
    assert tools["find_files"].run(name="schemas").data["matches"] == [str(root / "project" / "schemas.py")]
    assert tools["create_folder"].run(path="project/api/v1").ok
    assert "api/" in tools["list_folder"].run(path="project").data["entries"]


def test_overwrite_needs_confirmation_and_keeps_a_backup(home):
    root, access, tools = home
    write = tools["write_file"]
    assert write.risk_for({"path": "project/new.py", "content": "x"}) is Risk.LOW
    assert write.risk_for({"path": "project/schemas.py", "content": "x"}) is Risk.MEDIUM

    result = write.run(path="project/schemas.py", content="class User:\n    name: str\n    age: int\n")
    assert result.ok and result.data["backup"]
    assert "age: int" in (root / "project" / "schemas.py").read_text(encoding="utf-8")
    assert "age" not in open(result.data["backup"], encoding="utf-8").read()  # backup has the old version


def test_delete_goes_to_recycle_bin_with_high_risk(home):
    root, _, tools = home
    delete = tools["delete_path"]
    assert delete.risk_for({"path": "project/schemas.py"}) is Risk.HIGH
    assert delete.run(path="project/schemas.py").ok
    assert not (root / "project" / "schemas.py").exists()
    assert not delete.run(path=str(root)).ok  # never the whole home folder


def test_vscode_title_parsing():
    from app.tools.files import parse_vscode_title

    assert parse_vscode_title("schemas.py - AI-Tester - Visual Studio Code") == ("schemas.py", "AI-Tester", False)
    assert parse_vscode_title("\u25cf main.py - digitap_replica - Visual Studio Code") == ("main.py", "digitap_replica", True)
    assert parse_vscode_title("Claude Code - JARVIS - Visual Studio Code") is None
    assert parse_vscode_title("Welcome - Visual Studio Code") is None


def test_vscode_project_folders_from_state(tmp_path):
    import json

    from app.tools.files import vscode_folders

    state = tmp_path / "storage.json"
    state.write_text(json.dumps({"windowsState": {
        "lastActiveWindow": {"folder": "file:///c%3A/Users/jaya%20lakshmi/digitap_replica"},
        "openedWindows": [{"folder": "file:///c%3A/Users/jaya%20lakshmi/AI-Tester"}]}}), encoding="utf-8")
    folders = vscode_folders(state)
    assert str(folders["AI-Tester"]).replace("/", "\\") == r"c:\Users\jaya lakshmi\AI-Tester"
    assert "digitap_replica" in folders


def test_jarvis_can_rewrite_its_own_file_without_asking(tmp_path):
    """Asking every time made it invent "_v2" files instead of editing what it had just made."""
    from app.tools.base import Risk
    from app.tools.files import FileAccess, file_tools

    access = FileAccess(tmp_path, tmp_path / "backups", tmp_path / "notes")
    tools = {t.name: t for t in file_tools(access)}
    write = tools["write_file"]
    page = tmp_path / "site" / "index.html"

    assert write.risk_for({"path": str(page)}) is Risk.LOW  # brand new file
    assert write.run(path=str(page), content="<h1>one</h1>").ok

    assert write.risk_for({"path": str(page)}) is Risk.LOW  # its own work: no confirmation
    result = write.run(path=str(page), content="<h1>two</h1>")
    assert result.ok and page.read_text() == "<h1>two</h1>"
    assert result.data["backup"], "a backup is still kept even though it didn't ask"

    someone_elses = tmp_path / "notes.txt"
    someone_elses.write_text("important")
    assert write.risk_for({"path": str(someone_elses)}) is Risk.MEDIUM  # still asks for these
