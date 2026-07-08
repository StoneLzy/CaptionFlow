import os
import sys
from pathlib import Path

APP_NAME = "CaptionFlow"
BUNDLE_ID = "com.stonelzy.captionflow"


def default_app_support_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_NAME
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_NAME


def default_data_dir() -> Path:
    return default_app_support_dir() / "Data"


def default_sqlite_path() -> Path:
    return default_app_support_dir() / "app.db"


def default_models_dir() -> Path:
    return default_app_support_dir() / "Models"


def default_logs_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / APP_NAME
    return default_app_support_dir() / "Logs"


def default_settings_path() -> Path:
    return default_app_support_dir() / "settings.json"
