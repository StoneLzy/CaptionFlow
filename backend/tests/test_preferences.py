import json
from pathlib import Path

from app.core.preferences import AppPreferences, PreferencesStore


def test_preferences_round_trip_with_private_permissions(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    store = PreferencesStore(path)
    preferences = AppPreferences(
        onboarding_completed=True,
        provider_base_url="https://example.test/v1",
        provider_model="test-model",
        whisperkit_model="test-whisperkit",
    )

    store.save(preferences)

    assert store.load() == preferences
    assert path.stat().st_mode & 0o777 == 0o600
    assert "api_key" not in json.loads(path.read_text(encoding="utf-8"))


def test_missing_preferences_do_not_override_environment_values(
    tmp_path: Path,
) -> None:
    preferences = PreferencesStore(tmp_path / "missing.json").load()

    assert preferences.settings_overrides() == {}
