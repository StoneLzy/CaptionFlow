# WhisperKit Per-Job Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `whisperkit_server` ASR backend that starts a WhisperKit local server subprocess per transcription job and terminates it after the job to release model memory.

**Architecture:** Extend the existing ASR factory with a `WhisperKitServerTranscriber`. The transcriber owns subprocess startup, readiness polling, one OpenAI-compatible transcription request, response normalization, output writing, and process termination in `finally`.

**Tech Stack:** FastAPI backend, Pydantic settings, pytest, httpx, subprocess, sockets, React/Vite settings display.

---

## File Structure

- Create `backend/app/asr/whisperkit_server.py`: subprocess lifecycle, HTTP request, response normalization, and output writing.
- Create `backend/tests/test_whisperkit_server_transcriber.py`: fake subprocess and fake HTTP client tests.
- Modify `backend/app/asr/schemas.py`: add `WHISPERKIT_SERVER` and WhisperKit config fields.
- Modify `backend/app/core/config.py`: add `TM_WHISPERKIT_*` settings.
- Modify `backend/app/asr/factory.py`: map settings and construct the WhisperKit transcriber.
- Modify `backend/app/api/settings.py`: expose active WhisperKit settings.
- Modify `backend/tests/test_asr_factory.py`: assert factory support.
- Modify `backend/tests/test_settings.py`: assert settings API fields.
- Modify `frontend/src/api/client.ts`: type WhisperKit settings.
- Modify `frontend/src/__tests__/App.test.tsx`: include WhisperKit settings in mock.
- Modify `README.md`: document setup, model download, and `.env` example.

## Task 1: Config And Factory

**Files:**
- Modify: `backend/app/asr/schemas.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/asr/factory.py`
- Create: `backend/app/asr/whisperkit_server.py`
- Test: `backend/tests/test_asr_factory.py`

- [ ] **Step 1: Write the failing factory test**

Add this test to `backend/tests/test_asr_factory.py`:

```python
from app.asr.whisperkit_server import WhisperKitServerTranscriber


def test_build_transcriber_selects_whisperkit_server_when_configured() -> None:
    config = asr_config_from_settings(
        Settings(
            asr_backend=AsrBackend.WHISPERKIT_SERVER,
            whisperkit_cli_workdir="/tmp/argmax-oss-swift",
            _env_file=None,
        )
    )
    transcriber = build_transcriber(config)

    assert isinstance(transcriber, WhisperKitServerTranscriber)
    assert config.whisperkit_model == "large-v3-v20240930_626MB"
    assert str(config.whisperkit_cli_workdir) == "/tmp/argmax-oss-swift"
```

- [ ] **Step 2: Run the focused test and verify failure**

Run:

```bash
conda run -n translation-middleware python -m pytest backend/tests/test_asr_factory.py -v
```

Expected: FAIL because `AsrBackend.WHISPERKIT_SERVER` and `WhisperKitServerTranscriber` do not exist.

- [ ] **Step 3: Add schema and settings fields**

Update `backend/app/asr/schemas.py`:

```python
class AsrBackend(StrEnum):
    WHISPER_CPP = "whisper_cpp"
    FASTER_WHISPER = "faster_whisper"
    MLX_WHISPER = "mlx_whisper"
    WHISPERKIT_SERVER = "whisperkit_server"
```

Add these fields to `AsrConfig`:

```python
whisperkit_cli_workdir: Path = Path()
whisperkit_model: str = "large-v3-v20240930_626MB"
whisperkit_host: str = "127.0.0.1"
whisperkit_startup_timeout_seconds: float = Field(default=120.0, gt=0)
whisperkit_request_timeout_seconds: float = Field(default=1800.0, gt=0)
```

Update `backend/app/core/config.py`:

```python
whisperkit_cli_workdir: Path = Path()
whisperkit_model: str = "large-v3-v20240930_626MB"
whisperkit_host: str = "127.0.0.1"
whisperkit_startup_timeout_seconds: float = 120.0
whisperkit_request_timeout_seconds: float = 1800.0
```

- [ ] **Step 4: Add factory wiring and stub**

Create `backend/app/asr/whisperkit_server.py`:

```python
from app.asr.schemas import AsrConfig, TranscribeRequest, TranscriptionResult


class WhisperKitServerTranscriber:
    def __init__(self, config: AsrConfig) -> None:
        self.config = config

    def transcribe(self, request: TranscribeRequest) -> TranscriptionResult:
        raise NotImplementedError("WhisperKit server transcription is implemented in Task 2")
```

Update `backend/app/asr/factory.py` to import `WhisperKitServerTranscriber`, populate the new fields, and return it when `config.backend == AsrBackend.WHISPERKIT_SERVER`.

- [ ] **Step 5: Run the focused test and verify pass**

Run:

```bash
conda run -n translation-middleware python -m pytest backend/tests/test_asr_factory.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/asr/schemas.py backend/app/core/config.py backend/app/asr/factory.py backend/app/asr/whisperkit_server.py backend/tests/test_asr_factory.py
git commit -m "feat: add whisperkit server asr config"
```

## Task 2: WhisperKit Server Transcriber

**Files:**
- Modify: `backend/app/asr/whisperkit_server.py`
- Test: `backend/tests/test_whisperkit_server_transcriber.py`

- [ ] **Step 1: Write failing transcriber tests**

Create `backend/tests/test_whisperkit_server_transcriber.py` with tests for command building, response normalization, request fields, and process cleanup:

```python
from pathlib import Path

import pytest

from app.asr.schemas import AsrConfig, TranscribeRequest
from app.asr.whisperkit_server import WhisperKitServerTranscriber
from app.core.constants import SourceLanguage


class FakeProcess:
    def __init__(self) -> None:
        self.terminated = False
        self.killed = False
        self.returncode = None

    def poll(self):
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout=None):
        return 0

    def kill(self) -> None:
        self.killed = True


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(self.text)

    def json(self) -> dict:
        return self.payload


class FakeHttpClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.posts: list[dict] = []
        self.gets: list[str] = []

    def get(self, url: str):
        self.gets.append(url)
        return FakeResponse({"data": []})

    def post(self, url: str, *, data, files, timeout):
        self.posts.append({"url": url, "data": data, "files": files, "timeout": timeout})
        return self.responses.pop(0)


def make_transcriber(tmp_path: Path) -> WhisperKitServerTranscriber:
    return WhisperKitServerTranscriber(
        AsrConfig(
            whisperkit_cli_workdir=tmp_path,
            whisperkit_model="large-v3-v20240930_626MB",
            whisperkit_host="127.0.0.1",
            whisperkit_startup_timeout_seconds=1,
            whisperkit_request_timeout_seconds=30,
        )
    )


def test_build_command_uses_swift_run_and_model(tmp_path: Path) -> None:
    transcriber = make_transcriber(tmp_path)

    command = transcriber.build_command(50001)

    assert command == [
        "swift",
        "run",
        "argmax-cli",
        "serve",
        "--host",
        "127.0.0.1",
        "--port",
        "50001",
        "--model",
        "large-v3-v20240930_626MB",
    ]


def test_transcribe_posts_verbose_json_and_releases_process(tmp_path: Path, monkeypatch) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_text("audio", encoding="utf-8")
    process = FakeProcess()
    client = FakeHttpClient(
        [
            FakeResponse(
                {
                    "language": "ja",
                    "text": "こんにちは 世界。",
                    "segments": [
                        {
                            "id": 0,
                            "start": 0.3,
                            "end": 1.2,
                            "text": "こんにちは 世界。",
                            "words": [
                                {"word": "こんにちは", "start": 0.3, "end": 0.8},
                                {"word": "世界。", "start": 0.82, "end": 1.2},
                            ],
                        }
                    ],
                }
            )
        ]
    )
    transcriber = make_transcriber(tmp_path)
    monkeypatch.setattr(transcriber, "find_free_port", lambda: 50001)
    monkeypatch.setattr(transcriber, "start_server", lambda port: process)
    monkeypatch.setattr(transcriber, "wait_until_ready", lambda process, port, client: None)
    monkeypatch.setattr(transcriber, "create_http_client", lambda: client)

    result = transcriber.transcribe(
        TranscribeRequest(
            audio_path=audio_path,
            job_dir=tmp_path,
            output_prefix=tmp_path / "transcript",
            source_language=SourceLanguage.JAPANESE,
        )
    )

    assert client.posts[0]["data"]["response_format"] == "verbose_json"
    assert client.posts[0]["data"]["timestamp_granularities[]"] == ["word", "segment"]
    assert client.posts[0]["data"]["language"] == "ja"
    assert result.segments[0].words[0].word == "こんにちは"
    assert process.terminated is True
    assert (tmp_path / "transcript.srt").exists()


def test_transcribe_releases_process_after_request_failure(tmp_path: Path, monkeypatch) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_text("audio", encoding="utf-8")
    process = FakeProcess()

    class FailingClient(FakeHttpClient):
        def post(self, url: str, *, data, files, timeout):
            raise RuntimeError("request failed")

    transcriber = make_transcriber(tmp_path)
    monkeypatch.setattr(transcriber, "find_free_port", lambda: 50001)
    monkeypatch.setattr(transcriber, "start_server", lambda port: process)
    monkeypatch.setattr(transcriber, "wait_until_ready", lambda process, port, client: None)
    monkeypatch.setattr(transcriber, "create_http_client", lambda: FailingClient([]))

    with pytest.raises(RuntimeError, match="request failed"):
        transcriber.transcribe(
            TranscribeRequest(
                audio_path=audio_path,
                job_dir=tmp_path,
                output_prefix=tmp_path / "transcript",
            )
        )

    assert process.terminated is True
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
conda run -n translation-middleware python -m pytest backend/tests/test_whisperkit_server_transcriber.py -v
```

Expected: FAIL because the transcriber is a stub.

- [ ] **Step 3: Implement the transcriber**

Replace `backend/app/asr/whisperkit_server.py` with implementation containing:

- `find_free_port()` using `socket`.
- `build_command(port)` returning the exact command from Task 2 tests.
- `start_server(port)` using `subprocess.Popen(..., cwd=config.whisperkit_cli_workdir, env={**os.environ, "BUILD_ALL": "1"})`.
- `wait_until_ready(process, port, client)` polling `GET /v1/models`.
- `create_http_client()` returning `httpx.Client(base_url=f"http://{host}:{port}/v1")` is not used; use full URLs in methods.
- `transcribe(request)` that starts process, posts multipart, writes outputs, and terminates in `finally`.
- `normalize_response(payload)` mapping segments and words into `TranscriptionResult`.

- [ ] **Step 4: Run focused tests and verify pass**

Run:

```bash
conda run -n translation-middleware python -m pytest backend/tests/test_whisperkit_server_transcriber.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/asr/whisperkit_server.py backend/tests/test_whisperkit_server_transcriber.py
git commit -m "feat: add whisperkit per-job transcriber"
```

## Task 3: Settings API, Frontend, And README

**Files:**
- Modify: `backend/app/api/settings.py`
- Modify: `backend/tests/test_settings.py`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/__tests__/App.test.tsx`
- Modify: `README.md`

- [ ] **Step 1: Add settings API assertions**

Extend `test_settings_include_mlx_asr_fields` or add a new test in `backend/tests/test_settings.py`:

```python
def test_settings_include_whisperkit_fields(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_ASR_BACKEND", "whisperkit_server")
    monkeypatch.setenv("TM_WHISPERKIT_CLI_WORKDIR", str(tmp_path / "argmax-oss-swift"))

    response = client.get("/api/settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["asr_backend"] == "whisperkit_server"
    assert payload["whisperkit_model"] == "large-v3-v20240930_626MB"
    assert payload["whisperkit_host"] == "127.0.0.1"
```

- [ ] **Step 2: Run settings test and verify failure**

Run:

```bash
conda run -n translation-middleware python -m pytest backend/tests/test_settings.py -v
```

Expected: FAIL because WhisperKit fields are not exposed.

- [ ] **Step 3: Expose settings and update frontend types**

Add these response fields in `backend/app/api/settings.py`:

```python
"whisperkit_cli_workdir": str(settings.whisperkit_cli_workdir),
"whisperkit_model": settings.whisperkit_model,
"whisperkit_host": settings.whisperkit_host,
"whisperkit_startup_timeout_seconds": settings.whisperkit_startup_timeout_seconds,
"whisperkit_request_timeout_seconds": settings.whisperkit_request_timeout_seconds,
```

Add matching fields to `frontend/src/api/client.ts`.

- [ ] **Step 4: Update frontend settings mock**

In `frontend/src/__tests__/App.test.tsx`, add:

```ts
whisperkit_cli_workdir: "/tmp/argmax-oss-swift",
whisperkit_model: "large-v3-v20240930_626MB",
whisperkit_host: "127.0.0.1",
whisperkit_startup_timeout_seconds: 120,
whisperkit_request_timeout_seconds: 1800,
```

- [ ] **Step 5: Update README**

Document:

```bash
TM_ASR_BACKEND=whisperkit_server
TM_WHISPERKIT_CLI_WORKDIR=/absolute/path/to/argmax-oss-swift
TM_WHISPERKIT_MODEL=large-v3-v20240930_626MB
TM_WHISPERKIT_HOST=127.0.0.1
TM_WHISPERKIT_STARTUP_TIMEOUT_SECONDS=120
TM_WHISPERKIT_REQUEST_TIMEOUT_SECONDS=1800
```

Also document that the backend does not install WhisperKit or models; the user must run Argmax setup and download the model first.

- [ ] **Step 6: Run focused checks**

Run:

```bash
conda run -n translation-middleware python -m pytest backend/tests/test_settings.py -v
npm test -- App.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/settings.py backend/tests/test_settings.py frontend/src/api/client.ts frontend/src/__tests__/App.test.tsx README.md
git commit -m "docs: expose whisperkit server settings"
```

## Task 4: Full Verification

**Files:**
- No new files.

- [ ] **Step 1: Run backend tests**

```bash
conda run -n translation-middleware python -m pytest
```

Expected: all tests pass.

- [ ] **Step 2: Run backend lint**

```bash
conda run -n translation-middleware python -m ruff check backend
```

Expected: no lint errors.

- [ ] **Step 3: Run frontend tests**

```bash
npm test
```

Expected: all frontend tests pass.

- [ ] **Step 4: Run frontend build**

```bash
npm run build
```

Expected: production build succeeds.

- [ ] **Step 5: Final status**

```bash
git status --short --branch
```

Expected: clean working tree on `master`.
