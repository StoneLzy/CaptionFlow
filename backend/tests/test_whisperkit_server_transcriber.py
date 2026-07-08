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
        self.closed = False

    def get(self, url: str):
        self.gets.append(url)
        if self.responses:
            return self.responses.pop(0)
        return FakeResponse({"data": []})

    def post(self, url: str, *, data, files, timeout):
        self.posts.append({"url": url, "data": data, "files": files, "timeout": timeout})
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


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


def test_build_command_uses_release_binary_when_available(tmp_path: Path) -> None:
    release_dir = tmp_path / ".build" / "release"
    release_dir.mkdir(parents=True)
    release_binary = release_dir / "argmax-cli"
    release_binary.write_text("#!/bin/sh\n", encoding="utf-8")
    transcriber = make_transcriber(tmp_path)

    command = transcriber.build_command(50001)

    assert command[0] == str(release_binary.resolve())
    assert command[1:] == [
        "serve",
        "--host",
        "127.0.0.1",
        "--port",
        "50001",
        "--model",
        "large-v3-v20240930_626MB",
    ]


def test_build_command_uses_explicit_packaged_executable(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    executable = runtime_dir / "argmax-cli"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    transcriber = WhisperKitServerTranscriber(
        AsrConfig(
            whisperkit_executable_path=executable,
            whisperkit_model="large-v3-v20240930_626MB",
        )
    )

    command = transcriber.build_command(50001)

    assert command[0] == str(executable.resolve())
    assert command[1:] == [
        "serve",
        "--host",
        "127.0.0.1",
        "--port",
        "50001",
        "--model",
        "large-v3-v20240930_626MB",
    ]


def test_build_command_uses_local_model_path_when_cached(tmp_path: Path) -> None:
    release_dir = tmp_path / ".build" / "release"
    release_dir.mkdir(parents=True)
    release_binary = release_dir / "argmax-cli"
    release_binary.write_text("#!/bin/sh\n", encoding="utf-8")
    model_dir = (
        tmp_path
        / "Models"
        / "whisperkit-coreml"
        / "openai_whisper-large-v3-v20240930_626MB"
    )
    model_dir.mkdir(parents=True)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    transcriber = make_transcriber(tmp_path)

    command = transcriber.build_command(50001)

    assert command == [
        str(release_binary.resolve()),
        "serve",
        "--host",
        "127.0.0.1",
        "--port",
        "50001",
        "--model-path",
        str(model_dir.resolve()),
    ]


def test_create_http_client_disables_system_proxy(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}

    class CaptureClient:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.asr.whisperkit_server.httpx.Client", CaptureClient)
    transcriber = make_transcriber(tmp_path)

    client = transcriber.create_http_client()

    assert captured.get("trust_env") is False
    client.close()


def test_wait_until_ready_uses_health_endpoint(tmp_path: Path) -> None:
    process = FakeProcess()
    client = FakeHttpClient([])
    client.responses = [FakeResponse({"status": "ok"})]
    transcriber = make_transcriber(tmp_path)

    transcriber.wait_until_ready(process, 50001, client)

    assert client.gets == ["http://127.0.0.1:50001/health"]


def test_transcribe_posts_verbose_json_and_releases_process(
    tmp_path: Path, monkeypatch
) -> None:
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
    monkeypatch.setattr(transcriber, "start_server", lambda port, **kwargs: process)
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
    assert client.posts[0]["timeout"] == 30
    assert result.segments[0].words[0].word == "こんにちは"
    assert process.terminated is True
    assert client.closed is True
    assert (tmp_path / "transcript.srt").exists()


def test_transcribe_releases_process_after_request_failure(
    tmp_path: Path, monkeypatch
) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_text("audio", encoding="utf-8")
    process = FakeProcess()

    class FailingClient(FakeHttpClient):
        def post(self, url: str, *, data, files, timeout):
            raise RuntimeError("request failed")

    client = FailingClient([])
    transcriber = make_transcriber(tmp_path)
    monkeypatch.setattr(transcriber, "find_free_port", lambda: 50001)
    monkeypatch.setattr(transcriber, "start_server", lambda port, **kwargs: process)
    monkeypatch.setattr(transcriber, "wait_until_ready", lambda process, port, client: None)
    monkeypatch.setattr(transcriber, "create_http_client", lambda: client)

    with pytest.raises(RuntimeError, match="request failed"):
        transcriber.transcribe(
            TranscribeRequest(
                audio_path=audio_path,
                job_dir=tmp_path,
                output_prefix=tmp_path / "transcript",
            )
        )

    assert process.terminated is True
    assert client.closed is True


def test_normalize_response_handles_top_level_words(tmp_path: Path) -> None:
    transcriber = make_transcriber(tmp_path)

    result = transcriber.normalize_response(
        {
            "language": "en",
            "text": "Hello world.",
            "words": [
                {"word": "Hello", "start": 0.1, "end": 0.4},
                {"word": "world.", "start": 0.5, "end": 0.9},
            ],
        }
    )

    assert result.duration == 0.9
    assert result.segments[0].start == 0.1
    assert result.segments[0].end == 0.9
    assert [word.word for word in result.segments[0].words] == ["Hello", "world."]
