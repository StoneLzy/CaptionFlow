import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

from app.asr.output import write_transcription_outputs
from app.asr.schemas import (
    AsrConfig,
    TranscribeRequest,
    TranscriptionResult,
    TranscriptionSegment,
    WordTimestamp,
)
from app.asr.whisperkit_runtime import (
    resolve_whisperkit_executable,
    resolve_whisperkit_model_path,
)
from app.core.constants import SourceLanguage


class WhisperKitServerTranscriber:
    def __init__(self, config: AsrConfig) -> None:
        self.config = config

    def find_free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((self.config.whisperkit_host, 0))
            return int(sock.getsockname()[1])

    def resolve_cli_executable(self) -> Path | None:
        return resolve_whisperkit_executable(
            self.config.whisperkit_executable_path,
            self.config.whisperkit_cli_workdir,
        )

    def resolve_model_path(self) -> Path | None:
        return resolve_whisperkit_model_path(
            self.config.whisperkit_model_path,
            self.config.whisperkit_cli_workdir,
            self.config.whisperkit_model,
        )

    def build_command(self, port: int) -> list[str]:
        executable = self.resolve_cli_executable()
        if executable is None:
            workdir = self.config.whisperkit_cli_workdir
            if not workdir or not workdir.exists():
                raise FileNotFoundError(
                    "WhisperKit executable not found. Configure "
                    "TM_WHISPERKIT_EXECUTABLE_PATH or TM_WHISPERKIT_CLI_WORKDIR."
                )
            command = [
                "swift",
                "run",
                "argmax-cli",
                "serve",
                "--host",
                self.config.whisperkit_host,
                "--port",
                str(port),
            ]
        else:
            command = [
                str(executable),
                "serve",
                "--host",
                self.config.whisperkit_host,
                "--port",
                str(port),
            ]

        model_path = self.resolve_model_path()
        if model_path is not None:
            command.extend(["--model-path", str(model_path)])
        else:
            command.extend(["--model", self.config.whisperkit_model])
        return command

    def start_server(self, port: int, *, stderr_path: Path | None = None) -> subprocess.Popen:
        workdir = self.config.whisperkit_cli_workdir
        env = {**os.environ, "BUILD_ALL": "1"}
        command = self.build_command(port)
        executable = self.resolve_cli_executable()
        if workdir and workdir.exists():
            process_cwd = workdir
        elif executable is not None:
            process_cwd = executable.parent
        else:
            raise FileNotFoundError("WhisperKit runtime directory could not be resolved")
        stderr_target = (
            stderr_path.open("ab") if stderr_path is not None else subprocess.DEVNULL
        )
        return subprocess.Popen(
            command,
            cwd=process_cwd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=stderr_target,
        )

    def create_http_client(self) -> httpx.Client:
        return httpx.Client(trust_env=False)

    def base_url(self, port: int) -> str:
        return f"http://{self.config.whisperkit_host}:{port}/v1"

    def readiness_url(self, port: int) -> str:
        return f"http://{self.config.whisperkit_host}:{port}/health"

    def wait_until_ready(self, process, port: int, client) -> None:
        deadline = time.monotonic() + self.config.whisperkit_startup_timeout_seconds
        health_url = self.readiness_url(port)
        last_error = ""

        while time.monotonic() < deadline:
            returncode = process.poll()
            if returncode is not None:
                raise RuntimeError(
                    f"WhisperKit server exited before startup completed with code {returncode}"
                )
            try:
                response = client.get(health_url)
                if response.status_code == 502:
                    last_error = "model still loading (502)"
                    time.sleep(0.5)
                    continue
                response.raise_for_status()
                payload = response.json()
                if payload.get("status") == "ok":
                    return
                last_error = f"unexpected health payload: {payload}"
            except Exception as exc:
                last_error = str(exc)
                time.sleep(0.25)

        raise TimeoutError(
            "WhisperKit server did not become ready within "
            f"{self.config.whisperkit_startup_timeout_seconds:g}s: {last_error}"
        )

    def terminate_server(self, process) -> None:
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    def normalize_word(self, word: dict[str, Any]) -> WordTimestamp | None:
        text = str(word.get("word", "")).strip()
        start = word.get("start")
        end = word.get("end")
        if not text or start is None or end is None:
            return None
        start_float = float(start)
        end_float = float(end)
        if end_float <= start_float:
            return None
        probability = word.get("probability", word.get("confidence"))
        return WordTimestamp(
            word=text,
            start=start_float,
            end=end_float,
            probability=probability,
        )

    def normalize_words(self, words: list[dict[str, Any]] | None) -> list[WordTimestamp]:
        normalized: list[WordTimestamp] = []
        for word in words or []:
            normalized_word = self.normalize_word(word)
            if normalized_word is not None:
                normalized.append(normalized_word)
        return normalized

    def normalize_response(self, payload: dict[str, Any]) -> TranscriptionResult:
        raw_segments = payload.get("segments") or []
        top_level_words = self.normalize_words(payload.get("words"))
        segments: list[TranscriptionSegment] = []
        text_parts: list[str] = []

        for index, segment in enumerate(raw_segments):
            text = str(segment.get("text", "")).strip()
            words = self.normalize_words(segment.get("words"))
            segments.append(
                TranscriptionSegment(
                    id=int(segment.get("id", index)),
                    start=float(segment.get("start", words[0].start if words else 0.0)),
                    end=float(segment.get("end", words[-1].end if words else 0.0)),
                    text=text,
                    words=words,
                )
            )
            if text:
                text_parts.append(text)

        if not any(segment.words for segment in segments) and top_level_words:
            text = str(payload.get("text") or " ".join(word.word for word in top_level_words)).strip()
            segments = [
                TranscriptionSegment(
                    id=0,
                    start=top_level_words[0].start,
                    end=top_level_words[-1].end,
                    text=text,
                    words=top_level_words,
                )
            ]
            text_parts = [text] if text else []

        usable_segments = [
            segment
            for segment in segments
            if segment.text.strip() or segment.words or segment.end > segment.start
        ]
        if not usable_segments:
            raise RuntimeError("WhisperKit returned no usable transcription segments")

        duration = float(payload.get("duration") or max(segment.end for segment in usable_segments))
        text = str(payload.get("text") or " ".join(text_parts)).strip()
        return TranscriptionResult(
            language=str(payload.get("language") or "unknown"),
            duration=duration,
            segments=usable_segments,
            text=text,
        )

    def transcription_data(self, source_language: SourceLanguage) -> dict[str, Any]:
        data: dict[str, Any] = {
            "model": self.config.whisperkit_model,
            "response_format": "verbose_json",
            "timestamp_granularities[]": ["word", "segment"],
        }
        if source_language != SourceLanguage.AUTO:
            data["language"] = source_language.value
        return data

    def transcribe(self, request: TranscribeRequest) -> TranscriptionResult:
        if not request.audio_path.exists():
            raise FileNotFoundError(f"audio file not found: {request.audio_path}")

        port = self.find_free_port()
        process = None
        client = self.create_http_client()
        stderr_path = request.job_dir / "whisperkit.stderr"
        try:
            process = self.start_server(port, stderr_path=stderr_path)
            self.wait_until_ready(process, port, client)
            with request.audio_path.open("rb") as audio_file:
                response = client.post(
                    f"{self.base_url(port)}/audio/transcriptions",
                    data=self.transcription_data(request.source_language),
                    files={"file": (request.audio_path.name, audio_file)},
                    timeout=self.config.whisperkit_request_timeout_seconds,
                )
                response.raise_for_status()
                result = self.normalize_response(response.json())
            write_transcription_outputs(
                request.output_prefix,
                result,
                self.config.segmentation,
                output_formats=request.output_formats,
                pipeline_requires_srt=request.pipeline_requires_srt,
            )
            return result
        finally:
            self.terminate_server(process)
            close = getattr(client, "close", None)
            if close is not None:
                close()
