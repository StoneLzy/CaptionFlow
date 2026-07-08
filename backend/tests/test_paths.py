from pathlib import Path

from app.core import paths


def test_default_macos_paths_use_user_library(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths.sys, "platform", "darwin")
    monkeypatch.setattr(paths.Path, "home", lambda: tmp_path)

    app_support = tmp_path / "Library" / "Application Support" / "CaptionFlow"
    assert paths.default_data_dir() == app_support / "Data"
    assert paths.default_sqlite_path() == app_support / "app.db"
    assert paths.default_models_dir() == app_support / "Models"
    assert paths.default_logs_dir() == (
        tmp_path / "Library" / "Logs" / "CaptionFlow"
    )
    assert paths.default_settings_path() == app_support / "settings.json"
