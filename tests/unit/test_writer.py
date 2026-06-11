from core.writer import check_conflicts, write


def test_write_creates_files(tmp_path):
    files = {
        "CLAUDE.md": "# Hello",
        ".claude/agents/test.md": "# Agent",
        ".claude/settings.json": "{}",
    }
    write(files, str(tmp_path))
    assert (tmp_path / "CLAUDE.md").read_text() == "# Hello"
    assert (tmp_path / ".claude/agents/test.md").read_text() == "# Agent"
    assert (tmp_path / ".claude/settings.json").read_text() == "{}"


def test_write_creates_nested_directories(tmp_path):
    write({"deep/nested/file.md": "content"}, str(tmp_path))
    assert (tmp_path / "deep/nested/file.md").read_text() == "content"


def test_write_creates_root_dir_if_missing(tmp_path):
    target = tmp_path / "new-project"
    write({"f.txt": "hi"}, str(target))
    assert target.is_dir()
    assert (target / "f.txt").read_text() == "hi"


def test_write_unicode_content(tmp_path):
    write({"README.md": "Olá, mundo! 🎉"}, str(tmp_path))
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "Olá, mundo! 🎉"


def test_write_uses_unix_newlines(tmp_path):
    write({"script.sh": "#!/bin/bash\necho ok\n"}, str(tmp_path))
    assert (tmp_path / "script.sh").read_bytes() == b"#!/bin/bash\necho ok\n"


def test_write_empty_files_dict_only_creates_root(tmp_path):
    target = tmp_path / "empty-proj"
    write({}, str(target))
    assert target.is_dir()


def test_check_conflicts_no_existing_files(tmp_path):
    files = {"CLAUDE.md": "# x", ".claude/agents/a.md": "# a"}
    assert check_conflicts(files, str(tmp_path)) == []


def test_check_conflicts_returns_existing_paths(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("old")
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    (tmp_path / ".claude" / "agents" / "a.md").write_text("old")
    files = {
        "CLAUDE.md": "new",
        ".claude/agents/a.md": "new",
        ".claude/settings.json": "{}",
    }
    assert check_conflicts(files, str(tmp_path)) == ["CLAUDE.md", ".claude/agents/a.md"]


def test_check_conflicts_missing_root_dir(tmp_path):
    files = {"CLAUDE.md": "# x"}
    assert check_conflicts(files, str(tmp_path / "nao-existe")) == []
