# WhisperKit Per-Job Server Design

## Overview

Add a WhisperKit ASR backend that starts an Argmax/WhisperKit local server as a
child process for each video transcription job, sends one OpenAI-compatible
audio transcription request to that server, normalizes the verbose JSON response
into the existing `TranscriptionResult`, then terminates the child process in a
`finally` block.

This design prioritizes memory release after each job. Startup cost is accepted:
the WhisperKit model is loaded for the job and released when the server process
exits.

## Goals

- Add `whisperkit_server` as a first-class ASR backend.
- Keep FastAPI and WhisperKit in separate processes.
- Start one WhisperKit server per transcription job.
- Use an automatically selected free localhost port per job.
- Request `verbose_json` with word and segment timestamps.
- Normalize WhisperKit server responses into the existing ASR result schema.
- Reuse the existing word-based subtitle segmentation and output writer.
- Always terminate the WhisperKit child process after success or failure.
- Keep `mlx_whisper`, `faster_whisper`, and `whisper_cpp` available as fallbacks.

## Non-Goals

- Do not build or install Argmax/WhisperKit from the backend.
- Do not download WhisperKit models from the backend.
- Do not keep a shared WhisperKit server warm across jobs.
- Do not add streaming transcription in this iteration.
- Do not add diarization or SpeakerKit integration.
- Do not change translation provider behavior.

## Recommended Approach

Use the Argmax CLI local server rather than linking Swift code into the Python
backend. The server implements an OpenAI Audio API-compatible endpoint:

```text
POST /v1/audio/transcriptions
```

The Python backend owns the child process lifecycle and calls the local server
with `httpx`. This keeps the implementation small and isolates CoreML/ANE/GPU
memory in the child process, so process exit becomes the memory cleanup
mechanism.

## Architecture

### Backend Selection

`app.asr.schemas.AsrBackend` gains:

```text
whisperkit_server
```

`build_transcriber(config)` returns `WhisperKitServerTranscriber` when that
backend is selected.

### Configuration

Add settings with `TM_` environment support:

```text
TM_ASR_BACKEND=whisperkit_server
TM_WHISPERKIT_CLI_WORKDIR=/absolute/path/to/argmax-oss-swift
TM_WHISPERKIT_MODEL=large-v3-v20240930_626MB
TM_WHISPERKIT_HOST=127.0.0.1
TM_WHISPERKIT_STARTUP_TIMEOUT_SECONDS=120
TM_WHISPERKIT_REQUEST_TIMEOUT_SECONDS=1800
```

Field meanings:

- `whisperkit_cli_workdir`: directory where the Argmax CLI command should run.
- `whisperkit_model`: model identifier passed to `argmax-cli serve`.
- `whisperkit_host`: bind host, defaulting to localhost.
- `whisperkit_startup_timeout_seconds`: max wait for the local server to become
  reachable.
- `whisperkit_request_timeout_seconds`: max wait for the transcription request.

The backend finds a free TCP port for each job and does not expose a port config.

### Process Lifecycle

`WhisperKitServerTranscriber.transcribe(request)` performs:

1. Validate that `request.audio_path` exists.
2. Pick a free localhost port.
3. Start the server child process in `whisperkit_cli_workdir`.
4. Wait until `GET /v1/models` or another lightweight endpoint responds.
5. Send the transcription request.
6. Normalize the response and write outputs.
7. Terminate the child process in `finally`.
8. Kill the child process if it does not exit after a short grace period.

The subprocess command is:

```bash
BUILD_ALL=1 swift run argmax-cli serve \
  --host 127.0.0.1 \
  --port <free-port> \
  --model large-v3-v20240930_626MB
```

The first implementation uses `swift run` from the configured workdir. Homebrew
CLI support is out of scope for this iteration.

### Request Mapping

The backend sends multipart form data to:

```text
http://127.0.0.1:<port>/v1/audio/transcriptions
```

Fields:

- `file`: extracted audio file.
- `model`: `whisperkit_model`.
- `response_format`: `verbose_json`.
- `timestamp_granularities[]`: `word`.
- `timestamp_granularities[]`: `segment`.
- `language`: source language code when not auto-detect.

### Response Normalization

Expected response fields:

- `text`
- `language`
- `duration`, when present
- `segments[]`, when present
- `words[]`, either top-level or nested under segments depending on server
  response shape

Normalization rules:

- Convert segment `start`/`end` seconds into `TranscriptionSegment`.
- Convert word `start`/`end` seconds into `WordTimestamp`.
- Drop malformed words with missing or invalid timing.
- If words are top-level only, attach them to a synthetic segment when no
  segment-level words exist.
- If segments are absent but words exist, create one segment spanning the word
  range.
- Raise a readable error if neither usable segments nor usable words exist.

### Error Handling

Expected errors:

- `whisperkit_cli_workdir` is missing.
- `swift run argmax-cli serve` exits before becoming ready.
- Server startup times out.
- The transcription request fails.
- WhisperKit returns a non-JSON or error JSON response.
- WhisperKit returns no usable timing data.

All errors should include enough stderr/stdout context from the child process to
debug missing models, build issues, or CLI startup failures.

### Memory Behavior

Model memory lives in the WhisperKit child process. The Python backend must not
attempt to keep a server or client object alive across jobs.

After each job, the backend terminates the server process. This should release
WhisperKit model memory more reliably than in-process MLX cleanup because the
operating system owns final reclamation.

## Testing Strategy

Backend tests:

- factory builds `WhisperKitServerTranscriber` for `whisperkit_server`.
- config maps WhisperKit settings into `AsrConfig`.
- command builder includes host, free port, and model.
- startup wait succeeds when a fake server becomes reachable.
- startup wait fails with a readable timeout.
- transcription request sends expected multipart fields.
- response normalization handles segment-level words.
- response normalization handles top-level words.
- child process terminates after success.
- child process terminates after failure.
- output writer receives a normal `TranscriptionResult`.

Integration tests use fake subprocess objects and fake `httpx` clients. They do
not start Swift, build Argmax, or download models.

Frontend tests:

- settings rendering shows `whisperkit_server` and the configured model.
- existing whisper.cpp timestamp controls remain hidden unless backend is
  `whisper_cpp`.

## Rollout

1. Add the backend and config fields behind `TM_ASR_BACKEND=whisperkit_server`.
2. Keep `mlx_whisper` as an available fallback.
3. Update README with WhisperKit setup and model download instructions.
4. Run fake backend tests and existing frontend tests.
5. Let the user run a real smoke test with an installed Argmax CLI/model.

## References

- Argmax open-source SDK README: local server command, OpenAI Audio API
  endpoints, and supported `timestamp_granularities[]`.
- WhisperKit memory guidance: model memory is substantial and process isolation
  is the safest release boundary for this project.
