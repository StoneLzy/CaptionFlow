import json

import httpx

from app.core.config import Settings


class FakeSecretStore:
    def __init__(self, secret: str = "") -> None:
        self.secret = secret
        self.supported = True

    def read(self) -> str:
        return self.secret

    def write(self, value: str) -> None:
        self.secret = value

    def delete(self) -> None:
        self.secret = ""


def test_settings_ignore_unrelated_dotenv_entries(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "UNRELATED_SETTING=ignored\nTM_PROVIDER_MODEL=translation-model\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    settings = Settings()

    assert settings.provider_model == "translation-model"


def test_settings_include_mlx_asr_fields(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("TM_ASR_BACKEND", "mlx_whisper")
    monkeypatch.setenv("TM_MLX_WHISPER_MODEL", "mlx-community/whisper-large-v3-mlx")
    monkeypatch.setattr(
        "app.api.settings.MacOSKeychainSecretStore.read",
        lambda self: "",
    )

    response = client.get("/api/settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["asr_backend"] == "mlx_whisper"
    assert payload["mlx_whisper_model"] == "mlx-community/whisper-large-v3-mlx"
    assert payload["asr_max_subtitle_chars"] == 42


def test_settings_include_whisperkit_fields(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("TM_ASR_BACKEND", "whisperkit_server")
    monkeypatch.setenv(
        "TM_WHISPERKIT_EXECUTABLE_PATH",
        str(tmp_path / "runtime" / "argmax-cli"),
    )
    monkeypatch.setenv("TM_WHISPERKIT_CLI_WORKDIR", str(tmp_path / "argmax-oss-swift"))
    monkeypatch.setenv(
        "TM_WHISPERKIT_MODEL_PATH",
        str(tmp_path / "Models" / "whisperkit"),
    )
    monkeypatch.setattr(
        "app.api.settings.MacOSKeychainSecretStore.read",
        lambda self: "",
    )

    response = client.get("/api/settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["asr_backend"] == "whisperkit_server"
    assert payload["whisperkit_executable_path"].endswith("runtime/argmax-cli")
    assert payload["whisperkit_model"] == "large-v3-v20240930_626MB"
    assert payload["whisperkit_model_path"].endswith("Models/whisperkit")
    assert payload["whisperkit_host"] == "127.0.0.1"


def test_update_settings_persists_values_and_keychain_secret(
    client,
    monkeypatch,
    tmp_path,
) -> None:
    settings_path = tmp_path / "settings.json"
    fake_secret_store = FakeSecretStore()
    monkeypatch.setenv("TM_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("TM_PROVIDER_BASE_URL", "")
    monkeypatch.setenv("TM_PROVIDER_MODEL", "")
    monkeypatch.setattr(
        "app.api.settings.MacOSKeychainSecretStore",
        lambda: fake_secret_store,
    )

    response = client.patch(
        "/api/settings",
        json={
            "provider_base_url": "https://example.test/v1/",
            "provider_model": "test-model",
            "provider_api_key": "stored-secret",
            "whisperkit_model": "test-whisperkit",
            "onboarding_completed": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider_base_url"] == "https://example.test/v1"
    assert payload["provider_model"] == "test-model"
    assert payload["provider_api_key_storage"] == "keychain"
    assert payload["onboarding_completed"] is True
    assert fake_secret_store.secret == "stored-secret"
    persisted = json.loads(settings_path.read_text(encoding="utf-8"))
    assert persisted["provider_model"] == "test-model"
    assert "provider_api_key" not in persisted


def test_provider_connection_uses_submitted_api_key(
    client,
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("TM_SETTINGS_PATH", str(tmp_path / "settings.json"))
    original_async_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://example.test/v1/models"
        assert request.headers["Authorization"] == "Bearer submitted-secret"
        return httpx.Response(200, json={"data": []})

    monkeypatch.setattr(
        "app.api.settings.httpx.AsyncClient",
        lambda **kwargs: original_async_client(
            transport=httpx.MockTransport(handler),
        ),
    )

    response = client.post(
        "/api/settings/provider/test",
        json={
            "base_url": "https://example.test/v1",
            "model": "test-model",
            "api_key": "submitted-secret",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "model": "test-model"}
