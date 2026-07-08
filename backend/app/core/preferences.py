import json
import os
from pathlib import Path

from pydantic import BaseModel


class AppPreferences(BaseModel):
    onboarding_completed: bool = False
    provider_base_url: str | None = None
    provider_model: str | None = None
    whisperkit_executable_path: str | None = None
    whisperkit_model: str | None = None
    whisperkit_model_path: str | None = None

    def settings_overrides(self) -> dict[str, object]:
        values = self.model_dump(exclude_none=True, exclude={"onboarding_completed"})
        for field in ("whisperkit_executable_path", "whisperkit_model_path"):
            if field in values:
                values[field] = Path(str(values[field])) if values[field] else Path()
        return values


class PreferencesStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> AppPreferences:
        if not self.path.is_file():
            return AppPreferences()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return AppPreferences.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(f"Failed to load application settings: {exc}") from exc

    def save(self, preferences: AppPreferences) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(preferences.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.chmod(temporary, 0o600)
        temporary.replace(self.path)
