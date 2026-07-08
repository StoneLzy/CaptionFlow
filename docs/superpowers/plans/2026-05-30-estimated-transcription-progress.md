# Estimated Transcription Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show useful estimated transcription progress for WhisperKit-style backends that do not expose internal progress.

**Architecture:** Probe uploaded media duration with `ffprobe`, then run a small progress ticker while synchronous transcription is blocking. The ticker writes estimated `transcription.percent` values to the existing job repository and caps at 95% until the real transcription result finishes.

**Tech Stack:** FastAPI background tasks, Python `threading`, existing SQLite job repository, `ffprobe` from the ffmpeg toolchain, Vitest/pytest.

---

### Task 1: Media Duration Probe

**Files:**
- Modify: `backend/app/whisper/audio.py`
- Test: `backend/tests/test_whisper_audio.py`

- [x] **Step 1: Write failing tests**

Add tests for a successful `ffprobe` duration parse and a missing/failed probe returning `None`.

- [x] **Step 2: Run test to verify failure**

Run: `conda run -n translation-middleware python -m pytest backend/tests/test_whisper_audio.py -v`

- [x] **Step 3: Implement duration probe**

Add `probe_media_duration_seconds(path: Path) -> float | None` using `ffprobe -show_entries format=duration`.

- [x] **Step 4: Verify**

Run: `conda run -n translation-middleware python -m pytest backend/tests/test_whisper_audio.py -v`

### Task 2: Estimated Transcription Ticker

**Files:**
- Modify: `backend/app/jobs/runner.py`
- Test: `backend/tests/test_job_runner.py`

- [x] **Step 1: Write failing test**

Add a transcription job test that forces a short estimate interval and verifies an in-flight transcription stage receives an estimated percent before completion.

- [x] **Step 2: Run test to verify failure**

Run: `conda run -n translation-middleware python -m pytest backend/tests/test_job_runner.py::test_runner_updates_estimated_transcription_progress -v`

- [x] **Step 3: Implement ticker**

Use the measured baseline `75 / 824 = 0.091` as the default transcription time multiplier. Start a daemon thread before `transcribe_video`, update `percent` from 1 to 95 based on elapsed time, stop it in `finally`, then set 100 only after transcription completes.

- [x] **Step 4: Verify**

Run: `conda run -n translation-middleware python -m pytest backend/tests/test_job_runner.py -v`

### Task 3: Final Verification

**Files:**
- No additional files.

- [x] **Step 1: Run backend tests**

Run: `conda run -n translation-middleware python -m pytest backend/tests -v`

- [x] **Step 2: Run frontend checks**

Run: `npm test` and `npm run build` in `frontend`.

- [x] **Step 3: Lint**

Run: `conda run -n translation-middleware python -m ruff check backend`

- [x] **Step 4: Commit and push**

Commit: `feat: estimate transcription progress`
