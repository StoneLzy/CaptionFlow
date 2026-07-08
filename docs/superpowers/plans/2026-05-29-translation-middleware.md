# Translation Middleware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first local MVP for video transcription, subtitle merging, provider-based translation, job history, and progress visualization.

**Architecture:** FastAPI owns jobs, files, subprocess adapters, subtitle processing, and provider calls. React/Vite owns the local workbench UI and talks only to REST APIs. SQLite stores job/config metadata while generated media and subtitle files live under `data/jobs/<job_id>/`.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy, pytest, httpx, React, Vite, TypeScript, Vitest, Testing Library.

---

## File Structure

Create this structure:

```text
backend/
  app/
    __init__.py
    main.py
    api/
      __init__.py
      jobs.py
      settings.py
    core/
      __init__.py
      config.py
      constants.py
      progress.py
    db/
      __init__.py
      models.py
      session.py
    jobs/
      __init__.py
      repository.py
      runner.py
      schemas.py
      service.py
    subtitles/
      __init__.py
      merge.py
      schemas.py
      srt.py
    translation/
      __init__.py
      openai_compatible.py
      provider.py
    whisper/
      __init__.py
      adapter.py
      schemas.py
  tests/
    conftest.py
    test_jobs_api.py
    test_jobs_repository.py
    test_job_runner.py
    test_openai_compatible_provider.py
    test_srt_service.py
    test_subtitle_merge.py
    test_whisper_adapter.py
frontend/
  index.html
  package.json
  tsconfig.json
  vite.config.ts
  src/
    App.tsx
    api/client.ts
    components/JobHistory.tsx
    components/JobWorkbench.tsx
    components/ProgressTimeline.tsx
    components/SubtitlePreview.tsx
    constants/languages.ts
    types.ts
    main.tsx
    styles.css
    test/
      setup.ts
  src/__tests__/
    App.test.tsx
    ProgressTimeline.test.tsx
pyproject.toml
README.md
```

Responsibility boundaries:

- `subtitles/*` has no database, HTTP, provider, or filesystem side effects beyond parsing/formatting text.
- `translation/*` has no job knowledge; it translates segment payloads and returns aligned results.
- `whisper/*` only validates and invokes the local CLI.
- `jobs/*` orchestrates files, adapters, providers, status, and retry behavior.
- `api/*` maps HTTP requests to services and schemas.
- `frontend/src/components/*` stays presentational except for API calls passed down from `App.tsx`.

---

### Task 1: Project Scaffold And Tooling

**Files:**
- Create: `pyproject.toml`
- Create: `backend/app/main.py`
- Create: `backend/app/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles.css`
- Create: `frontend/src/test/setup.ts`
- Create: `README.md`

- [ ] **Step 1: Create Python project metadata**

Add `pyproject.toml`:

```toml
[project]
name = "translation-middleware"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "pydantic>=2.8.0",
  "pydantic-settings>=2.4.0",
  "sqlalchemy>=2.0.0",
  "httpx>=0.27.0",
  "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0.0",
  "pytest-asyncio>=0.23.0",
  "ruff>=0.6.0",
]

[tool.pytest.ini_options]
testpaths = ["backend/tests"]
pythonpath = ["backend"]

[tool.ruff]
line-length = 100
target-version = "py311"
```

- [ ] **Step 2: Create minimal FastAPI app**

Add `backend/app/main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="Translation Middleware")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

Add empty `backend/app/__init__.py`.

- [ ] **Step 3: Add backend test client fixture**

Add `backend/tests/conftest.py`:

```python
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.main import app


def pytest_configure() -> None:
    pass


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
```

- [ ] **Step 4: Create frontend package**

Add `frontend/package.json`:

```json
{
  "name": "translation-middleware-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc && vite build",
    "test": "vitest --run"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^5.4.0",
    "typescript": "^5.5.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "lucide-react": "^0.468.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/user-event": "^14.5.0",
    "jsdom": "^25.0.0",
    "vitest": "^2.0.0"
  }
}
```

Add `frontend/index.html`:

```html
<div id="root"></div>
<script type="module" src="/src/main.tsx"></script>
```

Add `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2020"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"],
  "references": []
}
```

Add `frontend/vite.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
```

- [ ] **Step 5: Create minimal React app**

Add `frontend/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

Add `frontend/src/App.tsx`:

```tsx
export function App() {
  return (
    <main className="shell">
      <h1>Translation Middleware</h1>
      <p>Local transcription and translation workbench</p>
    </main>
  );
}
```

Add `frontend/src/styles.css`:

```css
:root {
  color: #172033;
  background: #f6f7f9;
  font-family:
    Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

body {
  margin: 0;
}

.shell {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px;
}
```

Add `frontend/src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 6: Document local startup**

Add `README.md`:

```markdown
# Translation Middleware

Local-first video transcription and subtitle translation workbench.

## Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --app-dir backend
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```
```

- [ ] **Step 7: Run scaffold checks**

Run:

```bash
pytest
```

Expected: no tests collected or pass without import errors.

Run:

```bash
cd frontend && npm install && npm run build
```

Expected: TypeScript and Vite build succeed.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml README.md backend frontend
git commit -m "chore: scaffold local translation workbench"
```

---

### Task 2: Core Constants, Schemas, And Progress Model

**Files:**
- Create: `backend/app/core/constants.py`
- Create: `backend/app/core/progress.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/jobs/schemas.py`
- Create: `frontend/src/constants/languages.ts`
- Create: `frontend/src/types.ts`
- Test: `frontend/src/__tests__/ProgressTimeline.test.tsx`

- [ ] **Step 1: Define backend constants**

Add `backend/app/core/constants.py`:

```python
from enum import StrEnum


class SourceLanguage(StrEnum):
    AUTO = "auto"
    CHINESE = "zh"
    ENGLISH = "en"
    JAPANESE = "ja"
    KOREAN = "ko"
    FRENCH = "fr"
    GERMAN = "de"
    SPANISH = "es"
    RUSSIAN = "ru"


class TargetLanguage(StrEnum):
    SIMPLIFIED_CHINESE = "zh-Hans"
    JAPANESE = "ja"
    ENGLISH = "en"
    TRADITIONAL_CHINESE = "zh-Hant"
    FRENCH = "fr"
    GERMAN = "de"


DEFAULT_TARGET_LANGUAGE = TargetLanguage.SIMPLIFIED_CHINESE
```

- [ ] **Step 2: Define progress schemas**

Add `backend/app/core/progress.py`:

```python
from enum import StrEnum

from pydantic import BaseModel, Field


class StageName(StrEnum):
    UPLOAD = "upload"
    TRANSCRIPTION = "transcription"
    MERGE = "merge"
    TRANSLATION = "translation"
    EXPORT = "export"


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageProgress(BaseModel):
    name: StageName
    status: StageStatus = StageStatus.PENDING
    detail: str = ""
    percent: int | None = Field(default=None, ge=0, le=100)
    processed: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=0)
    elapsed_seconds: float | None = Field(default=None, ge=0)
```

- [ ] **Step 3: Define local settings**

Add `backend/app/core/config.py`:

```python
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    data_dir: Path = Path("data")
    sqlite_path: Path = Path("data/app.db")
    whisper_executable_path: str = ""
    whisper_model_path: str = ""
    provider_base_url: str = ""
    provider_api_key: str = ""
    provider_model: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="TM_")


def get_settings() -> Settings:
    return Settings()
```

Add empty `backend/app/core/__init__.py`.

- [ ] **Step 4: Define job request/response schemas**

Add `backend/app/jobs/schemas.py`:

```python
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.constants import DEFAULT_TARGET_LANGUAGE, SourceLanguage, TargetLanguage
from app.core.progress import StageProgress


class JobStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class OutputFormat(StrEnum):
    SRT = "srt"
    TXT = "txt"
    MD = "md"


class MergeSettings(BaseModel):
    enabled: bool = False
    min_duration_ms: int = Field(default=1200, ge=0)
    max_chars: int = Field(default=80, ge=1)
    max_gap_ms: int = Field(default=800, ge=0)
    protect_sentence_endings: bool = True


class TerminologyEntry(BaseModel):
    source: str
    target: str


class ProviderSettings(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""


class JobCreate(BaseModel):
    source_language: SourceLanguage = SourceLanguage.AUTO
    target_language: TargetLanguage = DEFAULT_TARGET_LANGUAGE
    output_formats: list[OutputFormat] = Field(default_factory=lambda: [OutputFormat.SRT])
    merge_settings: MergeSettings = Field(default_factory=MergeSettings)
    system_prompt: str = ""
    terminology: list[TerminologyEntry] = Field(default_factory=list)
    provider_settings: ProviderSettings = Field(default_factory=ProviderSettings)


class JobSummary(BaseModel):
    id: UUID
    filename: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    progress: list[StageProgress]
    error_summary: str | None = None
    outputs: dict[str, str] = Field(default_factory=dict)


class JobDetail(JobSummary):
    config: JobCreate
```

- [ ] **Step 5: Define frontend types and language constants**

Add `frontend/src/types.ts`:

```ts
export type StageName = "upload" | "transcription" | "merge" | "translation" | "export";
export type StageStatus = "pending" | "running" | "completed" | "failed" | "skipped";
export type JobStatus = "created" | "running" | "completed" | "failed";

export interface StageProgress {
  name: StageName;
  status: StageStatus;
  detail: string;
  percent?: number | null;
  processed?: number | null;
  total?: number | null;
  elapsed_seconds?: number | null;
}

export interface JobSummary {
  id: string;
  filename: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  progress: StageProgress[];
  error_summary?: string | null;
  outputs: Record<string, string>;
}
```

Add `frontend/src/constants/languages.ts`:

```ts
export const SOURCE_LANGUAGES = [
  { value: "auto", label: "Auto detect" },
  { value: "zh", label: "Chinese" },
  { value: "en", label: "English" },
  { value: "ja", label: "Japanese" },
  { value: "ko", label: "Korean" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "es", label: "Spanish" },
  { value: "ru", label: "Russian" },
] as const;

export const TARGET_LANGUAGES = [
  { value: "zh-Hans", label: "Simplified Chinese" },
  { value: "ja", label: "Japanese" },
  { value: "en", label: "English" },
  { value: "zh-Hant", label: "Traditional Chinese" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
] as const;

export const DEFAULT_TARGET_LANGUAGE = "zh-Hans";
```

- [ ] **Step 6: Run checks**

Run:

```bash
pytest
cd frontend && npm run build
```

Expected: backend imports pass and frontend builds.

- [ ] **Step 7: Commit**

```bash
git add backend/app/core backend/app/jobs/schemas.py frontend/src/constants frontend/src/types.ts
git commit -m "feat: define core language and job schemas"
```

---

### Task 3: Subtitle Parsing, Formatting, And Merge Rules

**Files:**
- Create: `backend/app/subtitles/__init__.py`
- Create: `backend/app/subtitles/schemas.py`
- Create: `backend/app/subtitles/srt.py`
- Create: `backend/app/subtitles/merge.py`
- Test: `backend/tests/test_srt_service.py`
- Test: `backend/tests/test_subtitle_merge.py`

- [ ] **Step 1: Write failing SRT parse/format tests**

Add `backend/tests/test_srt_service.py`:

```python
from app.subtitles.srt import format_markdown, format_srt, format_txt, parse_srt


SAMPLE_SRT = """1
00:00:01,000 --> 00:00:02,000
Hello

2
00:00:02,200 --> 00:00:03,000
world.
"""


def test_parse_srt_segments() -> None:
    segments = parse_srt(SAMPLE_SRT)

    assert len(segments) == 2
    assert segments[0].index == 1
    assert segments[0].start_ms == 1000
    assert segments[0].end_ms == 2000
    assert segments[0].text == "Hello"


def test_format_srt_round_trips_basic_timing() -> None:
    segments = parse_srt(SAMPLE_SRT)

    rendered = format_srt(segments)

    assert "00:00:01,000 --> 00:00:02,000" in rendered
    assert "world." in rendered


def test_format_txt_and_markdown() -> None:
    segments = parse_srt(SAMPLE_SRT)

    assert format_txt(segments) == "Hello\nworld.\n"
    assert "| 1 | 00:00:01,000 | 00:00:02,000 | Hello |" in format_markdown(segments)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest backend/tests/test_srt_service.py -v
```

Expected: FAIL because `app.subtitles.srt` does not exist.

- [ ] **Step 3: Implement subtitle schemas and SRT functions**

Add `backend/app/subtitles/schemas.py`:

```python
from pydantic import BaseModel, Field, field_validator


class SubtitleSegment(BaseModel):
    index: int = Field(ge=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    text: str

    @field_validator("end_ms")
    @classmethod
    def end_after_start(cls, value: int, info) -> int:
        start_ms = info.data.get("start_ms")
        if start_ms is not None and value < start_ms:
            raise ValueError("end_ms must be greater than or equal to start_ms")
        return value

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms
```

Add `backend/app/subtitles/srt.py`:

```python
from app.subtitles.schemas import SubtitleSegment


def parse_timestamp(value: str) -> int:
    hours, minutes, rest = value.split(":")
    seconds, milliseconds = rest.split(",")
    return (
        int(hours) * 3_600_000
        + int(minutes) * 60_000
        + int(seconds) * 1_000
        + int(milliseconds)
    )


def format_timestamp(ms: int) -> str:
    hours, remainder = divmod(ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def parse_srt(content: str) -> list[SubtitleSegment]:
    blocks = [block.strip() for block in content.replace("\r\n", "\n").split("\n\n") if block.strip()]
    segments: list[SubtitleSegment] = []
    for block in blocks:
        lines = block.splitlines()
        if len(lines) < 3:
            raise ValueError(f"Invalid SRT block: {block}")
        index = int(lines[0].strip())
        start_raw, end_raw = [part.strip() for part in lines[1].split("-->")]
        text = " ".join(line.strip() for line in lines[2:] if line.strip())
        segments.append(
            SubtitleSegment(
                index=index,
                start_ms=parse_timestamp(start_raw),
                end_ms=parse_timestamp(end_raw),
                text=text,
            )
        )
    return segments


def format_srt(segments: list[SubtitleSegment]) -> str:
    blocks: list[str] = []
    for output_index, segment in enumerate(segments, start=1):
        blocks.append(
            "\n".join(
                [
                    str(output_index),
                    f"{format_timestamp(segment.start_ms)} --> {format_timestamp(segment.end_ms)}",
                    segment.text,
                ]
            )
        )
    return "\n\n".join(blocks) + "\n"


def format_txt(segments: list[SubtitleSegment]) -> str:
    return "".join(f"{segment.text}\n" for segment in segments)


def format_markdown(segments: list[SubtitleSegment]) -> str:
    rows = ["| # | Start | End | Text |", "|---:|---|---|---|"]
    for segment in segments:
        text = segment.text.replace("|", "\\|")
        rows.append(
            f"| {segment.index} | {format_timestamp(segment.start_ms)} | "
            f"{format_timestamp(segment.end_ms)} | {text} |"
        )
    return "\n".join(rows) + "\n"
```

Add empty `backend/app/subtitles/__init__.py`.

- [ ] **Step 4: Run SRT tests**

Run:

```bash
pytest backend/tests/test_srt_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Write failing merge tests**

Add `backend/tests/test_subtitle_merge.py`:

```python
from app.jobs.schemas import MergeSettings
from app.subtitles.merge import merge_segments
from app.subtitles.schemas import SubtitleSegment


def seg(index: int, start: int, end: int, text: str) -> SubtitleSegment:
    return SubtitleSegment(index=index, start_ms=start, end_ms=end, text=text)


def test_merges_short_segment_forward_when_within_limits() -> None:
    merged = merge_segments(
        [
            seg(1, 0, 500, "Hello"),
            seg(2, 650, 1500, "world"),
        ],
        MergeSettings(enabled=True, min_duration_ms=800, max_chars=30, max_gap_ms=300),
    )

    assert len(merged) == 1
    assert merged[0].text == "Hello world"
    assert merged[0].start_ms == 0
    assert merged[0].end_ms == 1500


def test_does_not_merge_across_large_gap() -> None:
    merged = merge_segments(
        [seg(1, 0, 500, "Hello"), seg(2, 2000, 2600, "world")],
        MergeSettings(enabled=True, min_duration_ms=800, max_chars=30, max_gap_ms=300),
    )

    assert len(merged) == 2


def test_does_not_cross_sentence_ending_when_protected() -> None:
    merged = merge_segments(
        [seg(1, 0, 500, "Done."), seg(2, 650, 1500, "Next")],
        MergeSettings(enabled=True, min_duration_ms=800, max_chars=30, max_gap_ms=300),
    )

    assert len(merged) == 2


def test_respects_max_chars() -> None:
    merged = merge_segments(
        [seg(1, 0, 500, "A very long phrase"), seg(2, 650, 1500, "continues")],
        MergeSettings(enabled=True, min_duration_ms=800, max_chars=10, max_gap_ms=300),
    )

    assert len(merged) == 2
```

- [ ] **Step 6: Run merge tests to verify failure**

Run:

```bash
pytest backend/tests/test_subtitle_merge.py -v
```

Expected: FAIL because `merge_segments` does not exist.

- [ ] **Step 7: Implement merge rules**

Add `backend/app/subtitles/merge.py`:

```python
from app.jobs.schemas import MergeSettings
from app.subtitles.schemas import SubtitleSegment

SENTENCE_ENDINGS = (".", "!", "?", "。", "！", "？")


def should_merge(current: SubtitleSegment, nxt: SubtitleSegment, settings: MergeSettings) -> bool:
    if current.duration_ms >= settings.min_duration_ms:
        return False
    if nxt.start_ms - current.end_ms > settings.max_gap_ms:
        return False
    if settings.protect_sentence_endings and current.text.rstrip().endswith(SENTENCE_ENDINGS):
        return False
    combined = f"{current.text} {nxt.text}".strip()
    return len(combined) <= settings.max_chars


def merge_two(left: SubtitleSegment, right: SubtitleSegment) -> SubtitleSegment:
    return SubtitleSegment(
        index=left.index,
        start_ms=left.start_ms,
        end_ms=right.end_ms,
        text=f"{left.text} {right.text}".strip(),
    )


def reindex(segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
    return [
        SubtitleSegment(index=index, start_ms=segment.start_ms, end_ms=segment.end_ms, text=segment.text)
        for index, segment in enumerate(segments, start=1)
    ]


def merge_segments(
    segments: list[SubtitleSegment], settings: MergeSettings
) -> list[SubtitleSegment]:
    if not settings.enabled:
        return reindex(segments)

    output: list[SubtitleSegment] = []
    index = 0
    while index < len(segments):
        current = segments[index]
        if index + 1 < len(segments) and should_merge(current, segments[index + 1], settings):
            output.append(merge_two(current, segments[index + 1]))
            index += 2
        else:
            output.append(current)
            index += 1
    return reindex(output)
```

- [ ] **Step 8: Run subtitle tests**

Run:

```bash
pytest backend/tests/test_srt_service.py backend/tests/test_subtitle_merge.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/subtitles backend/tests/test_srt_service.py backend/tests/test_subtitle_merge.py
git commit -m "feat: add subtitle parsing and merge rules"
```

---

### Task 4: SQLite Job Repository

**Files:**
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/models.py`
- Create: `backend/app/db/session.py`
- Create: `backend/app/jobs/repository.py`
- Test: `backend/tests/test_jobs_repository.py`

- [ ] **Step 1: Write failing repository test**

Add `backend/tests/test_jobs_repository.py`:

```python
from pathlib import Path

from app.jobs.repository import JobRepository
from app.jobs.schemas import JobCreate, JobStatus


def test_create_and_list_job(tmp_path: Path) -> None:
    repo = JobRepository(tmp_path / "app.db")

    job = repo.create_job(filename="sample.mp4", config=JobCreate())
    jobs = repo.list_jobs()

    assert job.filename == "sample.mp4"
    assert job.status == JobStatus.CREATED
    assert len(jobs) == 1
    assert jobs[0].id == job.id
    assert jobs[0].progress[0].name == "upload"


def test_mark_failed_persists_error(tmp_path: Path) -> None:
    repo = JobRepository(tmp_path / "app.db")
    job = repo.create_job(filename="sample.mp4", config=JobCreate())

    repo.mark_failed(job.id, "whisper executable missing")
    updated = repo.get_job(job.id)

    assert updated.status == JobStatus.FAILED
    assert updated.error_summary == "whisper executable missing"
```

- [ ] **Step 2: Run repository test to verify failure**

Run:

```bash
pytest backend/tests/test_jobs_repository.py -v
```

Expected: FAIL because repository does not exist.

- [ ] **Step 3: Implement database model and session helper**

Add `backend/app/db/models.py`:

```python
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class JobRecord(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    filename: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    progress: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    outputs: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_summary: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
```

Add `backend/app/db/session.py`:

```python
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base


def make_session_factory(sqlite_path: Path) -> sessionmaker[Session]:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{sqlite_path}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
```

Add empty `backend/app/db/__init__.py`.

- [ ] **Step 4: Implement repository**

Add `backend/app/jobs/repository.py`:

```python
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from app.core.progress import StageName, StageProgress, StageStatus
from app.db.models import JobRecord
from app.db.session import make_session_factory
from app.jobs.schemas import JobCreate, JobDetail, JobStatus, JobSummary


def initial_progress() -> list[dict]:
    return [
        StageProgress(name=stage, status=StageStatus.PENDING).model_dump(mode="json")
        for stage in [
            StageName.UPLOAD,
            StageName.TRANSCRIPTION,
            StageName.MERGE,
            StageName.TRANSLATION,
            StageName.EXPORT,
        ]
    ]


class JobRepository:
    def __init__(self, sqlite_path: Path) -> None:
        self.session_factory = make_session_factory(sqlite_path)

    def _to_summary(self, record: JobRecord) -> JobSummary:
        return JobSummary(
            id=UUID(record.id),
            filename=record.filename,
            status=JobStatus(record.status),
            created_at=record.created_at,
            updated_at=record.updated_at,
            progress=[StageProgress(**stage) for stage in record.progress],
            error_summary=record.error_summary,
            outputs=record.outputs,
        )

    def _to_detail(self, record: JobRecord) -> JobDetail:
        return JobDetail(
            **self._to_summary(record).model_dump(),
            config=JobCreate(**record.config),
        )

    def create_job(self, filename: str, config: JobCreate) -> JobSummary:
        with self.session_factory() as session:
            record = JobRecord(
                filename=filename,
                status=JobStatus.CREATED.value,
                config=config.model_dump(mode="json"),
                progress=initial_progress(),
                outputs={},
            )
            session.add(record)
            session.commit()
            return self._to_summary(record)

    def list_jobs(self) -> list[JobSummary]:
        with self.session_factory() as session:
            records = session.query(JobRecord).order_by(JobRecord.updated_at.desc()).all()
            return [self._to_summary(record) for record in records]

    def get_job(self, job_id: UUID) -> JobDetail:
        with self.session_factory() as session:
            record = session.get(JobRecord, str(job_id))
            if record is None:
                raise KeyError(str(job_id))
            return self._to_detail(record)

    def mark_failed(self, job_id: UUID, error_summary: str) -> JobSummary:
        with self.session_factory() as session:
            record = session.get(JobRecord, str(job_id))
            if record is None:
                raise KeyError(str(job_id))
            record.status = JobStatus.FAILED.value
            record.error_summary = error_summary
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
            return self._to_summary(record)
```

- [ ] **Step 5: Run repository tests**

Run:

```bash
pytest backend/tests/test_jobs_repository.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/db backend/app/jobs/repository.py backend/tests/test_jobs_repository.py
git commit -m "feat: persist local job history in sqlite"
```

---

### Task 5: Translation Provider Interface And OpenAI-Compatible Provider

**Files:**
- Create: `backend/app/translation/__init__.py`
- Create: `backend/app/translation/provider.py`
- Create: `backend/app/translation/openai_compatible.py`
- Test: `backend/tests/test_openai_compatible_provider.py`

- [ ] **Step 1: Write failing provider test**

Add `backend/tests/test_openai_compatible_provider.py`:

```python
import httpx
import pytest

from app.jobs.schemas import ProviderSettings, TerminologyEntry
from app.subtitles.schemas import SubtitleSegment
from app.translation.openai_compatible import OpenAICompatibleProvider


@pytest.mark.asyncio
async def test_provider_returns_aligned_segments() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '[{"id":1,"text":"こんにちは"},{"id":2,"text":"世界"}]'
                        }
                    }
                ]
            },
        )

    import json

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(client=client)

    result = await provider.translate(
        segments=[
            SubtitleSegment(index=1, start_ms=0, end_ms=500, text="Hello"),
            SubtitleSegment(index=2, start_ms=600, end_ms=1200, text="world"),
        ],
        source_language="en",
        target_language="ja",
        system_prompt="Translate naturally.",
        terminology=[TerminologyEntry(source="world", target="世界")],
        settings=ProviderSettings(
            base_url="https://example.test/v1",
            api_key="secret",
            model="test-model",
        ),
    )

    assert [item.text for item in result.items] == ["こんにちは", "世界"]
```

- [ ] **Step 2: Run provider test to verify failure**

Run:

```bash
pytest backend/tests/test_openai_compatible_provider.py -v
```

Expected: FAIL because provider files do not exist.

- [ ] **Step 3: Implement provider contract**

Add `backend/app/translation/provider.py`:

```python
from typing import Protocol

from pydantic import BaseModel

from app.jobs.schemas import ProviderSettings, TerminologyEntry
from app.subtitles.schemas import SubtitleSegment


class TranslatedSegment(BaseModel):
    id: int
    text: str


class TranslationResult(BaseModel):
    items: list[TranslatedSegment]
    model: str


class TranslationProvider(Protocol):
    async def translate(
        self,
        *,
        segments: list[SubtitleSegment],
        source_language: str,
        target_language: str,
        system_prompt: str,
        terminology: list[TerminologyEntry],
        settings: ProviderSettings,
    ) -> TranslationResult:
        raise NotImplementedError
```

- [ ] **Step 4: Implement OpenAI-compatible provider**

Add `backend/app/translation/openai_compatible.py`:

```python
import json

import httpx

from app.jobs.schemas import ProviderSettings, TerminologyEntry
from app.subtitles.schemas import SubtitleSegment
from app.translation.provider import TranslatedSegment, TranslationResult


class OpenAICompatibleProvider:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client

    def build_messages(
        self,
        *,
        segments: list[SubtitleSegment],
        source_language: str,
        target_language: str,
        system_prompt: str,
        terminology: list[TerminologyEntry],
    ) -> list[dict[str, str]]:
        glossary = "\n".join(f"- {entry.source} => {entry.target}" for entry in terminology)
        user_payload = [
            {"id": segment.index, "text": segment.text}
            for segment in segments
        ]
        return [
            {
                "role": "system",
                "content": (
                    system_prompt
                    or "Translate subtitles faithfully. Return JSON array items with id and text."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Source language: {source_language}\n"
                    f"Target language: {target_language}\n"
                    f"Terminology:\n{glossary or '(none)'}\n"
                    f"Segments JSON:\n{json.dumps(user_payload, ensure_ascii=False)}"
                ),
            },
        ]

    async def translate(
        self,
        *,
        segments: list[SubtitleSegment],
        source_language: str,
        target_language: str,
        system_prompt: str,
        terminology: list[TerminologyEntry],
        settings: ProviderSettings,
    ) -> TranslationResult:
        client = self.client or httpx.AsyncClient(base_url=settings.base_url, timeout=60)
        close_client = self.client is None
        try:
            response = await client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {settings.api_key}"},
                json={
                    "model": settings.model,
                    "messages": self.build_messages(
                        segments=segments,
                        source_language=source_language,
                        target_language=target_language,
                        system_prompt=system_prompt,
                        terminology=terminology,
                    ),
                    "temperature": 0.2,
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            raw_items = json.loads(content)
            items = [TranslatedSegment(id=item["id"], text=item["text"]) for item in raw_items]
            expected_ids = {segment.index for segment in segments}
            actual_ids = {item.id for item in items}
            if actual_ids != expected_ids:
                raise ValueError("translation result IDs do not match input segment IDs")
            return TranslationResult(items=items, model=settings.model)
        finally:
            if close_client:
                await client.aclose()
```

Add empty `backend/app/translation/__init__.py`.

- [ ] **Step 5: Run provider tests**

Run:

```bash
pytest backend/tests/test_openai_compatible_provider.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/translation backend/tests/test_openai_compatible_provider.py
git commit -m "feat: add openai compatible translation provider"
```

---

### Task 6: Whisper.cpp Adapter

**Files:**
- Create: `backend/app/whisper/__init__.py`
- Create: `backend/app/whisper/schemas.py`
- Create: `backend/app/whisper/adapter.py`
- Test: `backend/tests/test_whisper_adapter.py`

- [ ] **Step 1: Write failing adapter tests**

Add `backend/tests/test_whisper_adapter.py`:

```python
from pathlib import Path

import pytest

from app.core.constants import SourceLanguage
from app.whisper.adapter import WhisperCppAdapter
from app.whisper.schemas import WhisperRequest


def test_builds_whisper_command(tmp_path: Path) -> None:
    exe = tmp_path / "whisper-cli"
    model = tmp_path / "model.bin"
    video = tmp_path / "video.mp4"
    output = tmp_path / "out"
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    model.write_text("model", encoding="utf-8")
    video.write_text("video", encoding="utf-8")

    adapter = WhisperCppAdapter()
    command = adapter.build_command(
        WhisperRequest(
            executable_path=exe,
            model_path=model,
            input_path=video,
            output_prefix=output,
            source_language=SourceLanguage.ENGLISH,
        )
    )

    assert str(exe) == command[0]
    assert "-m" in command
    assert str(model) in command
    assert "-l" in command
    assert "en" in command
    assert "-osrt" in command


def test_missing_executable_raises(tmp_path: Path) -> None:
    adapter = WhisperCppAdapter()

    with pytest.raises(FileNotFoundError):
        adapter.validate_paths(tmp_path / "missing", tmp_path / "model.bin")
```

- [ ] **Step 2: Run adapter tests to verify failure**

Run:

```bash
pytest backend/tests/test_whisper_adapter.py -v
```

Expected: FAIL because whisper adapter does not exist.

- [ ] **Step 3: Implement adapter schemas**

Add `backend/app/whisper/schemas.py`:

```python
from pathlib import Path

from pydantic import BaseModel

from app.core.constants import SourceLanguage


class WhisperRequest(BaseModel):
    executable_path: Path
    model_path: Path
    input_path: Path
    output_prefix: Path
    source_language: SourceLanguage = SourceLanguage.AUTO
```

- [ ] **Step 4: Implement command builder and runner**

Add `backend/app/whisper/adapter.py`:

```python
import subprocess
from pathlib import Path

from app.core.constants import SourceLanguage
from app.whisper.schemas import WhisperRequest


class WhisperCppAdapter:
    def validate_paths(self, executable_path: Path, model_path: Path) -> None:
        if not executable_path.exists():
            raise FileNotFoundError(f"whisper executable not found: {executable_path}")
        if not model_path.exists():
            raise FileNotFoundError(f"whisper model not found: {model_path}")

    def build_command(self, request: WhisperRequest) -> list[str]:
        self.validate_paths(request.executable_path, request.model_path)
        command = [
            str(request.executable_path),
            "-m",
            str(request.model_path),
            "-f",
            str(request.input_path),
            "-of",
            str(request.output_prefix),
            "-osrt",
            "-otxt",
        ]
        if request.source_language != SourceLanguage.AUTO:
            command.extend(["-l", request.source_language.value])
        return command

    def run(self, request: WhisperRequest) -> subprocess.CompletedProcess[str]:
        command = self.build_command(request)
        return subprocess.run(command, text=True, capture_output=True, check=True)
```

Add empty `backend/app/whisper/__init__.py`.

- [ ] **Step 5: Run adapter tests**

Run:

```bash
pytest backend/tests/test_whisper_adapter.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/whisper backend/tests/test_whisper_adapter.py
git commit -m "feat: add whisper cpp adapter"
```

---

### Task 7: Job Runner Workflow And Export Generation

**Files:**
- Create: `backend/app/jobs/runner.py`
- Create: `backend/app/jobs/service.py`
- Test: `backend/tests/test_job_runner.py`
- Modify: `backend/app/jobs/repository.py`

- [ ] **Step 1: Write failing runner test**

Add `backend/tests/test_job_runner.py`:

```python
from pathlib import Path

import pytest

from app.jobs.repository import JobRepository
from app.jobs.runner import JobRunner
from app.jobs.schemas import JobCreate, JobStatus


class FakeWhisper:
    def run(self, request):
        request.output_prefix.with_suffix(".srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nHello\n",
            encoding="utf-8",
        )


class FakeProvider:
    async def translate(self, **kwargs):
        from app.translation.provider import TranslatedSegment, TranslationResult

        return TranslationResult(items=[TranslatedSegment(id=1, text="你好")], model="fake")


@pytest.mark.asyncio
async def test_runner_creates_translation_outputs(tmp_path: Path) -> None:
    repo = JobRepository(tmp_path / "app.db")
    job = repo.create_job(filename="video.mp4", config=JobCreate())
    job_dir = tmp_path / "jobs" / str(job.id)
    job_dir.mkdir(parents=True)
    (job_dir / "input.mp4").write_text("video", encoding="utf-8")
    executable_path = tmp_path / "whisper-cli"
    model_path = tmp_path / "model.bin"
    executable_path.write_text("#!/bin/sh\n", encoding="utf-8")
    model_path.write_text("model", encoding="utf-8")

    runner = JobRunner(
        repo=repo,
        data_dir=tmp_path,
        whisper=FakeWhisper(),
        provider=FakeProvider(),
        whisper_executable_path=executable_path,
        whisper_model_path=model_path,
    )
    await runner.run_transcription_job(job.id)

    updated = repo.get_job(job.id)
    assert updated.status == JobStatus.COMPLETED
    assert (job_dir / "translation.srt").read_text(encoding="utf-8").strip().endswith("你好")
    assert "translation_srt" in updated.outputs
```

- [ ] **Step 2: Run runner test to verify failure**

Run:

```bash
pytest backend/tests/test_job_runner.py -v
```

Expected: FAIL because `JobRunner` does not exist and repository lacks update methods.

- [ ] **Step 3: Extend repository with progress/output methods**

Modify `backend/app/jobs/repository.py` to add:

```python
    def update_status(self, job_id: UUID, status: JobStatus) -> JobSummary:
        with self.session_factory() as session:
            record = session.get(JobRecord, str(job_id))
            if record is None:
                raise KeyError(str(job_id))
            record.status = status.value
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
            return self._to_summary(record)

    def set_outputs(self, job_id: UUID, outputs: dict[str, str]) -> JobSummary:
        with self.session_factory() as session:
            record = session.get(JobRecord, str(job_id))
            if record is None:
                raise KeyError(str(job_id))
            record.outputs = outputs
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
            return self._to_summary(record)
```

- [ ] **Step 4: Implement runner**

Add `backend/app/jobs/runner.py`:

```python
from pathlib import Path
from uuid import UUID

from app.jobs.repository import JobRepository
from app.jobs.schemas import JobStatus
from app.subtitles.merge import merge_segments
from app.subtitles.schemas import SubtitleSegment
from app.subtitles.srt import format_markdown, format_srt, format_timestamp, format_txt, parse_srt
from app.translation.provider import TranslationResult
from app.whisper.schemas import WhisperRequest


class JobRunner:
    def __init__(
        self,
        *,
        repo: JobRepository,
        data_dir: Path,
        whisper,
        provider,
        whisper_executable_path: Path,
        whisper_model_path: Path,
    ) -> None:
        self.repo = repo
        self.data_dir = data_dir
        self.whisper = whisper
        self.provider = provider
        self.whisper_executable_path = whisper_executable_path
        self.whisper_model_path = whisper_model_path

    def write_bilingual_outputs(
        self,
        job_dir: Path,
        source_segments: list[SubtitleSegment],
        translated_segments: list[SubtitleSegment],
    ) -> None:
        txt_blocks: list[str] = []
        md_rows = ["| # | Time | Source | Translation |", "|---:|---|---|---|"]
        for source, translated in zip(source_segments, translated_segments, strict=True):
            time_range = f"{format_timestamp(source.start_ms)} --> {format_timestamp(source.end_ms)}"
            txt_blocks.append(f"[{source.index}] {time_range}\n{source.text}\n{translated.text}\n")
            escaped_source = source.text.replace("|", "\\|")
            escaped_translation = translated.text.replace("|", "\\|")
            md_rows.append(
                f"| {source.index} | {time_range} | {escaped_source} | {escaped_translation} |"
            )
        (job_dir / "bilingual.txt").write_text("\n".join(txt_blocks), encoding="utf-8")
        (job_dir / "bilingual.md").write_text("\n".join(md_rows) + "\n", encoding="utf-8")

    async def translate_srt(self, job_id: UUID, srt_path: Path) -> None:
        job_dir = self.data_dir / "jobs" / str(job_id)
        job = self.repo.get_job(job_id)
        source_segments = parse_srt(srt_path.read_text(encoding="utf-8"))
        segments = merge_segments(source_segments, job.config.merge_settings)
        if job.config.merge_settings.enabled:
            (job_dir / "merged.srt").write_text(format_srt(segments), encoding="utf-8")
        result: TranslationResult = await self.provider.translate(
            segments=segments,
            source_language=job.config.source_language.value,
            target_language=job.config.target_language.value,
            system_prompt=job.config.system_prompt,
            terminology=job.config.terminology,
            settings=job.config.provider_settings,
        )
        translated = {item.id: item.text for item in result.items}
        translated_segments = [
            segment.model_copy(update={"text": translated[segment.index]})
            for segment in segments
        ]
        (job_dir / "translation.srt").write_text(format_srt(translated_segments), encoding="utf-8")
        self.write_bilingual_outputs(job_dir, segments, translated_segments)
        self.repo.set_outputs(
            job_id,
            {
                "translation_srt": str(job_dir / "translation.srt"),
                "bilingual_txt": str(job_dir / "bilingual.txt"),
                "bilingual_md": str(job_dir / "bilingual.md"),
            },
        )

    async def run_transcription_job(self, job_id: UUID) -> None:
        job_dir = self.data_dir / "jobs" / str(job_id)
        input_path = job_dir / "input.mp4"
        output_prefix = job_dir / "transcript"
        try:
            self.repo.update_status(job_id, JobStatus.RUNNING)
            job = self.repo.get_job(job_id)
            self.whisper.run(
                WhisperRequest(
                    executable_path=self.whisper_executable_path,
                    model_path=self.whisper_model_path,
                    input_path=input_path,
                    output_prefix=output_prefix,
                    source_language=job.config.source_language,
                )
            )
            transcript_path = output_prefix.with_suffix(".srt")
            segments = parse_srt(transcript_path.read_text(encoding="utf-8"))
            (job_dir / "transcript.txt").write_text(format_txt(segments), encoding="utf-8")
            (job_dir / "transcript.md").write_text(format_markdown(segments), encoding="utf-8")
            await self.translate_srt(job_id, transcript_path)
            existing = self.repo.get_job(job_id).outputs
            self.repo.set_outputs(
                job_id,
                {
                    **existing,
                    "transcript_srt": str(job_dir / "transcript.srt"),
                    "transcript_txt": str(job_dir / "transcript.txt"),
                    "transcript_md": str(job_dir / "transcript.md"),
                },
            )
            self.repo.update_status(job_id, JobStatus.COMPLETED)
        except Exception as exc:
            self.repo.mark_failed(job_id, str(exc))
            raise
```

- [ ] **Step 5: Run runner tests**

Run:

```bash
pytest backend/tests/test_job_runner.py backend/tests/test_jobs_repository.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/jobs/runner.py backend/app/jobs/repository.py backend/tests/test_job_runner.py
git commit -m "feat: add job runner workflow"
```

---

### Task 8: FastAPI Job And Settings APIs

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/jobs.py`
- Create: `backend/app/api/settings.py`
- Create: `backend/app/jobs/service.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_jobs_api.py`

- [ ] **Step 1: Write failing API tests**

Add `backend/tests/test_jobs_api.py`:

```python
def test_health(client) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_jobs_starts_empty(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))

    response = client.get("/api/jobs")

    assert response.status_code == 200
    assert response.json() == []


def test_create_video_job_copies_input(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    response = client.post(
        "/api/jobs/video",
        data={"config_json": "{}"},
        files={"file": ("sample.mp4", b"video", "video/mp4")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "sample.mp4"
    assert (tmp_path / "jobs" / payload["id"] / "input.mp4").exists()


def test_create_srt_job_copies_source_srt(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    response = client.post(
        "/api/jobs/srt",
        data={"config_json": "{}"},
        files={
            "file": (
                "source.srt",
                b"1\n00:00:00,000 --> 00:00:01,000\nHello\n",
                "application/x-subrip",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "source.srt"
    assert (tmp_path / "jobs" / payload["id"] / "source.srt").exists()
```

- [ ] **Step 2: Run API tests to verify failure**

Run:

```bash
pytest backend/tests/test_jobs_api.py -v
```

Expected: `/api/jobs`, `/api/jobs/video`, and `/api/jobs/srt` fail because routes are missing.

- [ ] **Step 3: Add job file service**

Add `backend/app/jobs/service.py`:

```python
import json
from pathlib import Path

from fastapi import UploadFile

from app.jobs.repository import JobRepository
from app.jobs.schemas import JobCreate, JobSummary


class JobService:
    def __init__(self, *, repo: JobRepository, data_dir: Path) -> None:
        self.repo = repo
        self.data_dir = data_dir

    def parse_config(self, config_json: str) -> JobCreate:
        if not config_json.strip():
            return JobCreate()
        return JobCreate(**json.loads(config_json))

    async def create_video_job(self, *, file: UploadFile, config_json: str) -> JobSummary:
        config = self.parse_config(config_json)
        job = self.repo.create_job(filename=file.filename or "input.mp4", config=config)
        job_dir = self.data_dir / "jobs" / str(job.id)
        job_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(file.filename or "input.mp4").suffix or ".mp4"
        target = job_dir / f"input{suffix}"
        target.write_bytes(await file.read())
        if target.name != "input.mp4":
            (job_dir / "input.mp4").write_bytes(target.read_bytes())
        return job

    async def create_srt_job(self, *, file: UploadFile, config_json: str) -> JobSummary:
        config = self.parse_config(config_json)
        job = self.repo.create_job(filename=file.filename or "source.srt", config=config)
        job_dir = self.data_dir / "jobs" / str(job.id)
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "source.srt").write_bytes(await file.read())
        return job
```

- [ ] **Step 4: Add jobs router**

Add `backend/app/api/jobs.py`:

```python
from fastapi import APIRouter, File, Form, UploadFile

from app.core.config import get_settings
from app.jobs.repository import JobRepository
from app.jobs.service import JobService
from app.jobs.schemas import JobSummary

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def get_repo() -> JobRepository:
    settings = get_settings()
    return JobRepository(settings.sqlite_path)


def get_service() -> JobService:
    settings = get_settings()
    return JobService(repo=get_repo(), data_dir=settings.data_dir)


@router.get("")
def list_jobs() -> list[JobSummary]:
    return get_repo().list_jobs()


@router.post("/video")
async def create_video_job(
    config_json: str = Form("{}"),
    file: UploadFile = File(...),
) -> JobSummary:
    return await get_service().create_video_job(file=file, config_json=config_json)


@router.post("/srt")
async def create_srt_job(
    config_json: str = Form("{}"),
    file: UploadFile = File(...),
) -> JobSummary:
    return await get_service().create_srt_job(file=file, config_json=config_json)
```

Add `backend/app/api/settings.py`:

```python
from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def read_settings() -> dict[str, str]:
    settings = get_settings()
    return {
        "whisper_executable_path": settings.whisper_executable_path,
        "whisper_model_path": settings.whisper_model_path,
        "provider_base_url": settings.provider_base_url,
        "provider_model": settings.provider_model,
    }
```

Add empty `backend/app/api/__init__.py`.

- [ ] **Step 5: Include routers in app**

Modify `backend/app/main.py`:

```python
from fastapi import FastAPI

from app.api.jobs import router as jobs_router
from app.api.settings import router as settings_router

app = FastAPI(title="Translation Middleware")
app.include_router(jobs_router)
app.include_router(settings_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 6: Run API tests**

Run:

```bash
pytest backend/tests/test_jobs_api.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api backend/app/jobs/service.py backend/app/main.py backend/tests/test_jobs_api.py
git commit -m "feat: expose jobs and settings api"
```

---

### Task 9: Frontend API Client, Workbench Layout, And Progress Timeline

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/components/ProgressTimeline.tsx`
- Create: `frontend/src/components/JobHistory.tsx`
- Create: `frontend/src/components/JobWorkbench.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/__tests__/ProgressTimeline.test.tsx`
- Test: `frontend/src/__tests__/App.test.tsx`

- [ ] **Step 1: Write failing timeline test**

Add `frontend/src/__tests__/ProgressTimeline.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { ProgressTimeline } from "../components/ProgressTimeline";

test("renders stage detail and count", () => {
  render(
    <ProgressTimeline
      stages={[
        {
          name: "translation",
          status: "running",
          detail: "Batch 2 of 5",
          processed: 2,
          total: 5,
        },
      ]}
    />,
  );

  expect(screen.getByText("Translation")).toBeInTheDocument();
  expect(screen.getByText("Batch 2 of 5")).toBeInTheDocument();
  expect(screen.getByText("2 / 5")).toBeInTheDocument();
});
```

- [ ] **Step 2: Write failing workbench test**

Add `frontend/src/__tests__/App.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { App } from "../App";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("renders local workbench controls with default target language", async () => {
  render(<App />);

  expect(await screen.findByText("No jobs yet.")).toBeInTheDocument();
  expect(screen.getByLabelText("Video or SRT file")).toBeInTheDocument();
  expect(screen.getByLabelText("Source language")).toHaveValue("auto");
  expect(screen.getByLabelText("Target language")).toHaveValue("zh-Hans");
  expect(screen.getByLabelText("Provider base URL")).toBeInTheDocument();
  expect(screen.getByLabelText("Terminology")).toBeInTheDocument();
});
```

- [ ] **Step 3: Run frontend test to verify failure**

Run:

```bash
cd frontend && npm run test
```

Expected: FAIL because components do not exist.

- [ ] **Step 4: Implement API client**

Add `frontend/src/api/client.ts`:

```ts
import type { JobSummary } from "../types";

export async function fetchJobs(): Promise<JobSummary[]> {
  const response = await fetch("/api/jobs");
  if (!response.ok) {
    throw new Error("Failed to load jobs");
  }
  return response.json();
}

export async function createVideoJob(formData: FormData): Promise<JobSummary> {
  const response = await fetch("/api/jobs/video", {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error("Failed to create video job");
  }
  return response.json();
}

export async function createSrtJob(formData: FormData): Promise<JobSummary> {
  const response = await fetch("/api/jobs/srt", {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error("Failed to create SRT job");
  }
  return response.json();
}
```

- [ ] **Step 5: Implement progress timeline**

Add `frontend/src/components/ProgressTimeline.tsx`:

```tsx
import type { StageProgress } from "../types";

const STAGE_LABELS: Record<string, string> = {
  upload: "Upload",
  transcription: "Transcription",
  merge: "Subtitle merge",
  translation: "Translation",
  export: "Export",
};

interface Props {
  stages: StageProgress[];
}

export function ProgressTimeline({ stages }: Props) {
  return (
    <div className="timeline" aria-label="Job progress">
      {stages.map((stage) => (
        <section className={`timeline-stage status-${stage.status}`} key={stage.name}>
          <div className="stage-title">{STAGE_LABELS[stage.name]}</div>
          <div className="stage-status">{stage.status}</div>
          {stage.detail ? <p>{stage.detail}</p> : null}
          {stage.processed != null && stage.total != null ? (
            <span className="stage-count">
              {stage.processed} / {stage.total}
            </span>
          ) : null}
        </section>
      ))}
    </div>
  );
}
```

- [ ] **Step 6: Implement history and workbench panels**

Add `frontend/src/components/JobHistory.tsx`:

```tsx
import type { JobSummary } from "../types";

interface Props {
  jobs: JobSummary[];
}

export function JobHistory({ jobs }: Props) {
  return (
    <aside className="history">
      <h2>History</h2>
      {jobs.length === 0 ? <p>No jobs yet.</p> : null}
      {jobs.map((job) => (
        <button className="job-row" key={job.id} type="button">
          <strong>{job.filename}</strong>
          <span>{job.status}</span>
        </button>
      ))}
    </aside>
  );
}
```

Add `frontend/src/components/JobWorkbench.tsx`:

```tsx
import { TARGET_LANGUAGES, SOURCE_LANGUAGES, DEFAULT_TARGET_LANGUAGE } from "../constants/languages";

export function JobWorkbench() {
  return (
    <section className="workbench">
      <h2>New job</h2>
      <label>
        Video or SRT file
        <input type="file" accept="video/*,.srt" />
      </label>
      <label>
        Source language
        <select defaultValue="auto">
          {SOURCE_LANGUAGES.map((language) => (
            <option key={language.value} value={language.value}>
              {language.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Target language
        <select defaultValue={DEFAULT_TARGET_LANGUAGE}>
          {TARGET_LANGUAGES.map((language) => (
            <option key={language.value} value={language.value}>
              {language.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Output formats
        <div className="inline-options">
          <label><input type="checkbox" defaultChecked /> SRT</label>
          <label><input type="checkbox" /> TXT</label>
          <label><input type="checkbox" /> Markdown</label>
        </div>
      </label>
      <fieldset>
        <legend>Subtitle merge</legend>
        <label><input type="checkbox" /> Enable merge before translation</label>
        <label>Minimum duration (ms)<input type="number" defaultValue={1200} min={0} /></label>
        <label>Maximum characters<input type="number" defaultValue={80} min={1} /></label>
        <label>Maximum gap (ms)<input type="number" defaultValue={800} min={0} /></label>
        <label><input type="checkbox" defaultChecked /> Protect sentence endings</label>
      </fieldset>
      <fieldset>
        <legend>Provider</legend>
        <label>Provider base URL<input aria-label="Provider base URL" type="url" /></label>
        <label>Provider API key<input type="password" /></label>
        <label>Provider model<input type="text" /></label>
      </fieldset>
      <label>
        System prompt
        <textarea rows={4} />
      </label>
      <label>
        Terminology
        <textarea aria-label="Terminology" rows={5} placeholder="source phrase => target phrase" />
      </label>
    </section>
  );
}
```

- [ ] **Step 7: Wire App and styles**

Modify `frontend/src/App.tsx`:

```tsx
import { useEffect, useState } from "react";
import { fetchJobs } from "./api/client";
import { JobHistory } from "./components/JobHistory";
import { JobWorkbench } from "./components/JobWorkbench";
import type { JobSummary } from "./types";

export function App() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);

  useEffect(() => {
    fetchJobs().then(setJobs).catch(() => setJobs([]));
  }, []);

  return (
    <main className="shell">
      <header className="topbar">
        <h1>Translation Middleware</h1>
        <p>Local transcription and translation workbench</p>
      </header>
      <div className="layout">
        <JobHistory jobs={jobs} />
        <JobWorkbench />
      </div>
    </main>
  );
}
```

Append to `frontend/src/styles.css`:

```css
.topbar {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
}

.layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 18px;
}

.history,
.workbench,
.timeline-stage {
  border: 1px solid #d9dee7;
  border-radius: 8px;
  background: #fff;
  padding: 16px;
}

.job-row {
  width: 100%;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 10px;
  border: 1px solid #d9dee7;
  background: #fff;
  border-radius: 6px;
}

.workbench {
  display: grid;
  gap: 14px;
}

label {
  display: grid;
  gap: 6px;
  font-weight: 600;
}

select,
textarea,
input {
  font: inherit;
  border: 1px solid #ccd3df;
  border-radius: 6px;
  padding: 8px;
}

fieldset {
  display: grid;
  gap: 10px;
  border: 1px solid #d9dee7;
  border-radius: 8px;
  padding: 12px;
}

.inline-options {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.timeline {
  display: grid;
  grid-template-columns: repeat(5, minmax(120px, 1fr));
  gap: 10px;
}

.stage-title {
  font-weight: 700;
}

.stage-status,
.stage-count {
  color: #586174;
}
```

- [ ] **Step 8: Run frontend tests and build**

Run:

```bash
cd frontend && npm run test && npm run build
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src
git commit -m "feat: add frontend workbench shell"
```

---

### Task 10: Local Smoke Verification And MVP Hardening

**Files:**
- Modify: `README.md`
- Modify: `backend/app/jobs/runner.py`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Run full backend test suite**

Run:

```bash
pytest
```

Expected: all backend tests pass.

- [ ] **Step 2: Run full frontend test suite and build**

Run:

```bash
cd frontend && npm run test && npm run build
```

Expected: all frontend tests pass and Vite emits `dist/`.

- [ ] **Step 3: Start backend server**

Run:

```bash
uvicorn app.main:app --reload --app-dir backend --port 8000
```

Expected: server starts and `/api/health` returns `{"status":"ok"}`.

- [ ] **Step 4: Start frontend server**

Run in a separate terminal:

```bash
cd frontend && npm run dev
```

Expected: Vite serves the app at `http://127.0.0.1:5173`.

- [ ] **Step 5: Open UI and verify layout**

Open `http://127.0.0.1:5173`.

Expected:

- Page shows local workbench, not a landing page.
- History column renders empty state.
- New job form shows source language auto-detect.
- Target language defaults to Simplified Chinese.
- Target language options are only Japanese, English, Traditional Chinese, French, and German in addition to the default.

- [ ] **Step 6: Update README with MVP limitations**

Append to `README.md`:

```markdown
## MVP Notes

- The app connects to an existing local whisper.cpp executable and model.
- The first provider is OpenAI-compatible through base_url, api_key, and model.
- Job files are stored under data/jobs/<job_id>/.
- No login, multi-user support, pause, or cancel in the first version.
```

- [ ] **Step 7: Final commit**

```bash
git add README.md backend frontend
git commit -m "chore: verify local mvp workflow"
```

---

## Plan Self-Review

Spec coverage:

- Local FastAPI + React/Vite app: Tasks 1, 8, 9, 10.
- Existing local `whisper.cpp`: Task 6 and Task 7 wiring.
- SRT/TXT/Markdown outputs: Task 3 and Task 7.
- SRT upload/fresh SRT translation path: Task 7 translation runner and Task 8 video/SRT upload endpoints.
- Merge controls: Task 3 backend and Task 9 frontend controls.
- Provider abstraction: Task 5.
- System prompt and terminology: Task 2 schemas, Task 5 provider message construction, Task 9 UI.
- Local history: Task 4 backend and Task 9 frontend.
- Progress timeline: Task 2 model and Task 9 UI.

Known risk:

- Real `whisper.cpp` progress percentages vary by CLI version, so Task 10 verifies the UI displays useful stage status even when exact percentages are unavailable.
