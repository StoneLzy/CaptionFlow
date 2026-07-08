# Translation Middleware Design

## Overview

Build a local-first translation workflow middleware for video transcription, subtitle cleanup, and large-model translation. The first version is a Python backend and separated web frontend running locally on the user's Mac.

The product is a workbench, not a marketing site. Users create a local job, choose a source video and source language, run local `whisper.cpp` transcription, optionally merge short or poorly segmented subtitles, translate through a provider abstraction, and export usable subtitle and review files.

## Goals

- Run as a local web app with a FastAPI backend and React/Vite frontend.
- Connect to the user's existing local `whisper.cpp` executable and model file instead of managing installation or model downloads.
- Transcribe selected videos with source language selection and export transcription as SRT, TXT, or Markdown.
- Translate uploaded SRT files or freshly transcribed SRT files through an abstract provider layer.
- Provide controllable subtitle merge rules before translation.
- Support system prompts and phrase terminology for translation behavior.
- Store local job history, outputs, progress, and logs without login or multi-user support.

## Non-Goals

- No account system, login, or multi-user permissions.
- No cloud file storage.
- No automatic installation, compilation, or model download for `whisper.cpp`.
- No Redis/Celery-style external queue in the first version.
- No free-form target language entry in the first version.
- No pause or cancel support in the first version.

## Recommended Approach

Use the local workbench MVP approach:

- Frontend: React/Vite app for workflow UI, task history, settings, subtitle preview, merge controls, provider settings, and progress visualization.
- Backend: FastAPI service with REST endpoints, a process-local background job runner, SQLite job index, and file outputs under `data/jobs/<job_id>/`.
- Transcription: `whisper_adapter` invokes the user's configured local `whisper.cpp` CLI and model path.
- Translation: business workflow depends on a generic translation provider interface. The first provider is OpenAI-compatible and accepts `base_url`, `api_key`, and `model`.

This keeps the first version easy to run locally while preserving clear extension points for future providers, local models, or a stronger queue.

## Architecture

### Frontend

The frontend is a single local workbench screen with:

- A local history list of recent jobs, status, outputs, and retry entry points.
- A current job panel for upload/selection, configuration, progress, subtitles, and exports.
- Forms for source language, target language, `whisper.cpp` settings, transcription formats, merge settings, provider settings, system prompt, and terminology.
- A stage timeline progress component showing upload, transcription, merge, translation, and export.

The frontend does not call `whisper.cpp` or model providers directly. It only talks to the FastAPI backend.

### Backend

The backend owns workflow state and file operations:

- `jobs`: creates jobs, stores status, records progress, exposes history, logs errors, and supports retry after configuration changes.
- `whisper_adapter`: validates executable/model paths, constructs the `whisper.cpp` command, runs transcription, captures progress, and writes transcription outputs.
- `subtitle_service`: parses SRT, normalizes subtitle segments, formats SRT/TXT/Markdown, and validates segment structure.
- `merge_service`: applies user-controlled subtitle merge rules.
- `translation_provider`: defines a provider interface independent of any specific model vendor.
- `OpenAICompatibleProvider`: first provider implementation using `base_url`, `api_key`, and `model`.
- `export_service`: writes final translation and bilingual review files.

SQLite stores job metadata, status, configuration snapshots, output file references, and progress state. Job files are stored under `data/jobs/<job_id>/`.

## Workflow

1. User creates a job by selecting a video and a source language.
2. Backend copies the video into `data/jobs/<job_id>/`.
3. Backend runs the configured local `whisper.cpp` executable with the configured model path.
4. Backend writes transcription outputs, including `transcript.srt`, and optional TXT/Markdown exports.
5. User either translates the fresh SRT or uploads an external SRT.
6. User optionally enables subtitle merge and sets merge parameters.
7. Backend parses and optionally merges subtitle segments.
8. User selects target language, provider settings, system prompt, and terminology.
9. Backend translates subtitle batches through the selected provider.
10. Backend maps translated text back to subtitle timing and writes outputs.
11. Frontend shows finished output files and keeps the job in local history.

## Languages

Source language choices:

- Auto detect
- Chinese
- English
- Japanese
- Korean
- French
- German
- Spanish
- Russian

Target language choices:

- Simplified Chinese, default
- Japanese
- English
- Traditional Chinese
- French
- German

The target language is selection-only. There is no custom text input for target language in the first version.

## Subtitle Merge Rules

The first version supports these user-controlled parameters:

- Minimum subtitle duration: short subtitles become merge candidates.
- Maximum characters per merged subtitle: merged text cannot exceed this limit.
- Maximum gap between adjacent subtitles: subtitles separated by a larger gap are not merged.
- Sentence-ending punctuation protection: the merge logic avoids crossing obvious sentence boundaries by default.

The merge direction is forward-biased: short subtitles preferentially merge into following subtitles when constraints allow. The result remains a list of timed subtitle segments and can be previewed before translation.

## Translation Provider

The translation workflow depends on a provider interface, not a concrete vendor.

Provider input:

- Source subtitle segments
- Source language
- Target language
- System prompt
- Terminology entries
- Provider configuration

Provider output:

- Translated text aligned back to the input subtitle segment IDs.
- Provider metadata useful for logs, such as model name and batch status.

The first provider is OpenAI-compatible:

- `base_url`
- `api_key`
- `model`

This enables OpenAI-compatible services and local compatible gateways without changing workflow code.

## Terminology

Terminology is a per-job phrase table. The first version stores entries as source phrase and preferred target phrase pairs. The backend includes these entries with the system prompt when making translation requests.

Terminology is saved with the job configuration so users can adjust phrases and retry translation on the same subtitle input.

## Outputs

Transcription outputs:

- `transcript.srt`
- `transcript.txt`
- `transcript.md`

Translation outputs:

- `translation.srt`: target-language subtitles only, suitable for direct video use.
- `bilingual.txt`: source and target text for review.
- `bilingual.md`: source and target text for review.

Output files live under the job directory and are linked from the job detail UI.

## Progress Visualization

Use a stage timeline with current detail. Stages:

- Upload
- Transcription
- Subtitle merge
- Translation
- Export

Each stage records status such as pending, running, completed, or failed. The current stage can also include detail text, elapsed time, estimated remaining time when available, percentage, or processed item counts.

The first version does not need perfect `whisper.cpp` percentage accuracy. It should show useful status based on captured process output, known file creation steps, elapsed time, and translation batch counts.

## Error Handling

Errors are stored on the job and exposed in the UI with readable summaries and log access.

Expected error categories:

- Missing or invalid `whisper.cpp` executable path.
- Missing or invalid model path.
- `whisper.cpp` command failure.
- Unsupported or unreadable video file.
- SRT parse or validation failure.
- Provider authentication failure.
- Provider timeout or network failure.
- Translation result shape mismatch, such as missing segment IDs.
- Output write failure.

Failed jobs keep their input files and configuration. Users can adjust settings and retry relevant stages.

## Configuration

Global local settings:

- `whisper.cpp` executable path.
- `whisper.cpp` model path.
- OpenAI-compatible provider `base_url`.
- Provider API key.
- Provider model.

Per-job settings:

- Source language.
- Target language.
- Requested transcription output formats.
- Merge enabled/disabled.
- Merge parameters.
- System prompt.
- Terminology entries.

For the first version, secrets can be loaded from `.env` or a local config file. There is no account-level secret management.

## Testing Strategy

Backend tests:

- SRT parsing and formatting.
- TXT and Markdown export formatting.
- Merge rules for short duration, max characters, max gap, and punctuation protection.
- Provider interface contract and OpenAI-compatible request construction with a fake HTTP client.
- Job state transitions for success and failure paths.
- Retry behavior using fake adapters.

Frontend tests:

- New job form state and validation.
- Target language default and allowed choices.
- Merge parameter controls.
- Provider settings form.
- Job history rendering.
- Stage timeline rendering for running, completed, and failed states.

Smoke tests:

- Create a job with fake transcription.
- Load job history.
- Simulate merged subtitles.
- Simulate provider translation.
- Verify output links appear.

## Open Questions Deferred From MVP

- Whether to add cancellation and pause/resume.
- Whether to add full `whisper.cpp` language coverage.
- Whether to add a dedicated local model provider beyond OpenAI-compatible gateways.
- Whether to use a stronger persistent task queue after the first usable local version.
