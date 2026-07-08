from pathlib import Path

import pytest

from app.jobs.folder_opener import open_folder


def test_open_folder_uses_macos_open(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr("app.jobs.folder_opener.platform.system", lambda: "Darwin")
    monkeypatch.setattr(
        "app.jobs.folder_opener.subprocess.Popen",
        lambda command: calls.append(command),
    )

    open_folder(tmp_path)

    assert calls == [["open", str(tmp_path)]]


def test_open_folder_uses_windows_explorer(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr("app.jobs.folder_opener.platform.system", lambda: "Windows")
    monkeypatch.setattr(
        "app.jobs.folder_opener.subprocess.Popen",
        lambda command: calls.append(command),
    )

    open_folder(tmp_path)

    assert calls == [["explorer", str(tmp_path)]]


def test_open_folder_rejects_unsupported_platform(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.jobs.folder_opener.platform.system", lambda: "Plan9")

    with pytest.raises(RuntimeError, match="Unsupported platform"):
        open_folder(tmp_path)
