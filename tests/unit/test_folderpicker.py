import subprocess
from unittest.mock import MagicMock, patch

import pytest

import core.folderpicker as folderpicker
from core.folderpicker import FolderPickerTimeout, _to_win_path, pick_folder


def _proc(stdout=""):
    r = MagicMock()
    r.stdout = stdout
    return r


# ── _to_win_path ─────────────────────────────────────────────────────────────

def test_to_win_path_converts_mnt_path():
    with patch.object(folderpicker, "_ON_WINDOWS", False):
        assert _to_win_path("/mnt/c/Users/brend/proj") == "C:\\Users\\brend\\proj"


def test_to_win_path_drive_only():
    with patch.object(folderpicker, "_ON_WINDOWS", False):
        assert _to_win_path("/mnt/d") == "D:\\"


def test_to_win_path_windows_passes_through():
    with patch.object(folderpicker, "_ON_WINDOWS", True):
        assert _to_win_path("C:\\Users\\brend\\proj") == "C:\\Users\\brend\\proj"


def test_to_win_path_non_mnt_passes_through():
    with patch.object(folderpicker, "_ON_WINDOWS", False):
        assert _to_win_path("/home/user/proj") == "/home/user/proj"


# ── pick_folder ──────────────────────────────────────────────────────────────

def test_pick_folder_returns_chosen_path():
    with patch(
        "core.folderpicker.subprocess.run",
        return_value=_proc("C:\\Users\\brend\\proj\n"),
    ) as run:
        assert pick_folder() == "C:\\Users\\brend\\proj"
    run.assert_called_once()


def test_pick_folder_returns_empty_when_cancelled():
    with patch("core.folderpicker.subprocess.run", return_value=_proc("")):
        assert pick_folder() == ""


def test_pick_folder_raises_on_timeout():
    with patch(
        "core.folderpicker.subprocess.run",
        side_effect=subprocess.TimeoutExpired("python", 120),
    ):
        with pytest.raises(FolderPickerTimeout):
            pick_folder()
