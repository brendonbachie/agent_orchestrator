from unittest.mock import patch

import pytest

from utils.storage import list_projects, save_project


@pytest.fixture
def tmp_store(tmp_path):
    data_file = tmp_path / "projetos.json"
    with patch("utils.storage._DATA_DIR", tmp_path), patch(
        "utils.storage._DATA_FILE", data_file
    ):
        yield data_file


def test_list_projects_empty_when_file_missing(tmp_store):
    assert list_projects() == []


def test_save_and_list(tmp_store):
    save_project("/my/project", ["CLAUDE.md", ".claude/agents/x.md"], "Start coding")
    projects = list_projects()
    assert len(projects) == 1
    p = projects[0]
    assert p["pasta"] == "/my/project"
    assert p["files"] == ["CLAUDE.md", ".claude/agents/x.md"]
    assert p["primeiro_prompt"] == "Start coding"
    assert "criado_em" in p


def test_save_appends_multiple_projects(tmp_store):
    save_project("/proj/a", [], "first")
    save_project("/proj/b", [], "second")
    projects = list_projects()
    assert len(projects) == 2
    assert projects[0]["pasta"] == "/proj/a"
    assert projects[1]["pasta"] == "/proj/b"


def test_list_projects_corrupted_json_returns_empty(tmp_store):
    tmp_store.write_text("not valid json }{")
    assert list_projects() == []


def test_list_projects_non_list_json_returns_empty(tmp_store):
    tmp_store.write_text('{"key": "value"}')
    assert list_projects() == []


def test_save_creates_data_dir(tmp_store, tmp_path):
    nested = tmp_path / "sub" / "dir"
    data_file = nested / "projetos.json"
    with patch("utils.storage._DATA_DIR", nested), patch(
        "utils.storage._DATA_FILE", data_file
    ):
        save_project("/p", [], "x")
        assert data_file.exists()
