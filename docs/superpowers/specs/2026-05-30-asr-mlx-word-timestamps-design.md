# ASR MLX Word Timestamps Design

## Overview

Refactor the backend transcription path so Apple Silicon users can use
`mlx-whisper` as the preferred local ASR backend, while subtitle timing is
generated from normalized word timestamps instead of relying on model segment
boundaries.

The goal is to improve local transcription speed and subtitle timestamp
precision without tying the rest of the job workflow to one ASR implementation.
The existing `whisper.cpp` and `faster-whisper` paths remain available as
fallbacks.

## Goals

- Add `mlx_whisper` as a first-class ASR backend.
- Make `mlx_whisper` the default backend for local Mac use.
- Preserve the existing `Transcriber` factory boundary used by `JobRunner`.
- Normalize backend output into one internal `TranscriptionResult` shape.
- Prefer word-level timestamps when writing SRT/TXT/Markdown/JSON outputs.
- Add configurable subtitle segmentation rules that rebuild subtitle lines from
  words.
- Keep `whisper.cpp` available as a legacy fallback for users who already have
  it configured.
- Keep `faster-whisper` available but no longer rely on it as the default path.

## Non-Goals

- Do not integrate WhisperKit or Argmax CLI in this iteration.
- Do not add streaming transcription.
- Do not add diarization.
- Do not build a model download UI.
- Do not remove existing `whisper.cpp` or `faster-whisper` tests unless their
  expectations need small updates for the shared output layer.
- Do not change the translation provider workflow.

## Recommended Approach

Use the existing ASR abstraction and add a new backend:

- `AsrBackend.MLX_WHISPER`
- `MlxWhisperTranscriber`
- MLX-specific settings in `Settings` and `AsrConfig`
- a shared word-based subtitle segmentation module

`JobRunner` should continue to call `build_transcriber(config)` and should not
need to know which ASR implementation is active.

The output writer should prefer:

1. words, when at least one segment contains usable `WordTimestamp` entries
2. original model segments, when word timestamps are unavailable

This keeps old backends working while making precise subtitle generation the
normal path for `mlx-whisper`.

## Architecture

### Backend Selection

`app.asr.schemas.AsrBackend` gains:

```text
mlx_whisper
```

Default settings change from:

```text
faster_whisper
```

to:

```text
mlx_whisper
```

The factory remains the single construction point:

```text
Settings + JobCreate -> AsrConfig -> build_transcriber -> Transcriber
```

### MLX Transcriber

`MlxWhisperTranscriber` wraps the Python `mlx_whisper.transcribe` API.

Input:

- audio path
- source language, or auto-detect
- model reference or local model path
- word timestamp flag
- optional temperature / verbose options if needed later

Output:

- detected language
- total duration when present
- segment text and timing
- word-level timing when present
- combined transcript text

Expected result parsing should be defensive because MLX returns dictionaries,
not Pydantic models. Missing optional fields should not crash transcription if
the core text and segment timings are present.

### Word Timestamp Normalization

Each backend maps its native word shape into:

```text
WordTimestamp(word, start, end, probability)
```

Rules:

- Strip only obvious surrounding whitespace from `word`.
- Drop words with missing `start` or `end`.
- Drop words whose `end <= start`.
- Preserve punctuation attached to words because it helps sentence-boundary
  segmentation.
- Keep segment-level text even when words are absent.

### Subtitle Segmentation

Add a shared module:

```text
app.asr.segmentation
```

It converts a `TranscriptionResult` into `SubtitleSegment` values.

Default word-based segmentation rules:

- Maximum characters per subtitle: 42
- Maximum subtitle duration: 6 seconds
- Minimum subtitle duration target: 0.8 seconds
- Maximum gap inside a subtitle: 0.8 seconds
- Prefer breaking after sentence-ending punctuation.
- Prefer breaking after phrase punctuation when the subtitle is already near
  the character limit.
- Never cross a large word timestamp gap.
- Fall back to segment boundaries if there are no usable words.

The exact defaults can be adjusted after trying real files, but the rule shape
should be stable.

### Configuration

Add settings with `TM_` environment support:

```text
TM_ASR_BACKEND=mlx_whisper
TM_MLX_WHISPER_MODEL=mlx-community/whisper-large-v3-mlx
TM_MLX_WHISPER_MODEL_DIR=
TM_MLX_WHISPER_WORD_TIMESTAMPS=true
TM_ASR_MAX_SUBTITLE_CHARS=42
TM_ASR_MAX_SUBTITLE_DURATION_MS=6000
TM_ASR_MIN_SUBTITLE_DURATION_MS=800
TM_ASR_MAX_WORD_GAP_MS=800
```

Use these setting names in the first implementation so documentation, tests, and
environment configuration stay aligned.

`/api/settings` should expose enough ASR settings for the frontend to display
which backend and model are active.

### Frontend Surface

Keep the first frontend change small:

- show current ASR backend
- show current MLX model when backend is `mlx_whisper`
- keep existing `whisper.cpp` timestamp controls visible only when the active
  backend is `whisper_cpp`

Avoid a full ASR configuration UI in this iteration. Environment settings are
enough for the first backend switch.

## Workflow

1. User creates a video job.
2. `JobRunner` extracts audio when needed.
3. `JobRunner` builds the configured transcriber.
4. `MlxWhisperTranscriber` calls `mlx_whisper.transcribe` with word timestamps.
5. The backend normalizes MLX output into `TranscriptionResult`.
6. The shared output writer rebuilds subtitles from words.
7. The existing merge and translation workflow consumes the generated
   `transcript.srt`.

## Error Handling

Expected errors:

- `mlx-whisper` is not installed.
- MLX cannot load the configured model.
- Model download/cache path is not writable.
- Audio file is missing or unreadable.
- MLX returns no segments.
- MLX returns segments but no usable word timestamps.

When word timestamps are missing but segment timings exist, the job should
complete using segment-based output and include enough detail in logs or errors
to explain that precise segmentation was not used.

## Testing Strategy

Backend unit tests:

- factory builds `MlxWhisperTranscriber` for `mlx_whisper`.
- MLX result dictionaries map into `TranscriptionResult`.
- missing `mlx_whisper` dependency raises a readable error.
- word timestamps are filtered and normalized.
- word-based segmentation respects max characters.
- word-based segmentation respects max duration.
- word-based segmentation breaks on large word gaps.
- word-based segmentation prefers sentence punctuation.
- output writer falls back to segment-based output when words are unavailable.
- existing `whisper.cpp` and `faster-whisper` tests still pass.

Integration-style tests:

- fake MLX transcriber writes `transcript.srt`, `transcript.txt`,
  `transcript.md`, and `transcript.json`.
- transcription jobs still feed merge and translation through the same SRT path.

Frontend tests:

- settings rendering shows the active ASR backend.
- Whisper timestamp controls are hidden for `mlx_whisper`.
- existing workbench tests remain green.

## Rollout

1. Add MLX backend behind the existing `TM_ASR_BACKEND` setting.
2. Add shared word-based subtitle segmentation.
3. Switch the default backend to `mlx_whisper`.
4. Update README setup instructions for Apple Silicon.
5. Keep `whisper.cpp` setup instructions as fallback guidance.

## References

- `mlx-whisper` README: Python API, CLI, model selection, and word-level
  timestamp support.
- Argmax/WhisperKit README: local OpenAI Audio API server and word/segment
  timestamp parameters, reserved for a later backend.
- `faster-whisper` README: current backend behavior, word timestamp support,
  VAD options, and performance considerations.
