# Frontend i18n Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved v2 frontend redesign, add Chinese-default language switching, and show live task progress.

**Architecture:** Add small frontend i18n utilities and pass `t`/language props through the existing components. Keep polling in `App` and broaden it to non-terminal jobs. Add backend repository stage-update helpers and runner calls so existing `StageProgress` data becomes meaningful.

**Tech Stack:** FastAPI/Pydantic/SQLAlchemy backend, React/Vite/TypeScript frontend, pytest, Vitest, CSS.

---

### Task 1: Backend Stage Progress

**Files:**
- Modify: `backend/app/jobs/repository.py`
- Modify: `backend/app/jobs/runner.py`
- Test: `backend/tests/test_jobs_repository.py`
- Test: `backend/tests/test_job_runner.py`

- [ ] Add failing repository test for updating one stage without losing other stages.
- [ ] Implement `JobRepository.update_stage(job_id, stage_name, status, detail="", percent=None, processed=None, total=None, elapsed_seconds=None)`.
- [ ] Add failing runner test asserting video jobs mark upload/transcription/translation/export completed.
- [ ] Add runner progress updates around SRT and video phases, including skipped merge/translation stages.
- [ ] Run `conda run -n translation-middleware python -m pytest backend/tests/test_jobs_repository.py backend/tests/test_job_runner.py -v`.
- [ ] Commit as `feat: track job stage progress`.

### Task 2: Frontend i18n and Polling

**Files:**
- Create: `frontend/src/i18n.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/JobHistory.tsx`
- Modify: `frontend/src/components/ProgressTimeline.tsx`
- Modify: `frontend/src/components/JobWorkbench.tsx`
- Test: `frontend/src/__tests__/App.test.tsx`
- Test: `frontend/src/__tests__/ProgressTimeline.test.tsx`

- [ ] Add failing frontend tests for default Chinese labels and English switching.
- [ ] Add failing frontend test proving `created` jobs are polled.
- [ ] Create local translation dictionary with `zh` and `en`.
- [ ] Store language in `localStorage` and default to `zh`.
- [ ] Localize visible labels, hints, statuses, stage names, and errors touched by this flow.
- [ ] Change polling to refresh while any job status is not `completed` or `failed`.
- [ ] Run `npm test -- App.test.tsx ProgressTimeline.test.tsx`.
- [ ] Commit as `feat: add localized live job UI`.

### Task 3: Approved v2 UI Polish

**Files:**
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/components/JobWorkbench.tsx`
- Modify: `frontend/src/components/JobHistory.tsx`
- Modify: `frontend/src/components/ProgressTimeline.tsx`

- [ ] Convert the shell to the approved three-column layout: compact left rail, wider center workbench, stable right progress panel.
- [ ] Rework the workbench into concise sections: file, basic language/output row, pipeline, merge, provider/prompt/terminology.
- [ ] Add visual progress bars for job rail and stage cards.
- [ ] Verify responsive behavior at narrow widths by CSS media query.
- [ ] Run `npm test` and `npm run build`.
- [ ] Commit as `style: polish localized workbench layout`.

### Task 4: Full Verification

**Files:**
- All touched files.

- [ ] Run `conda run -n translation-middleware python -m pytest`.
- [ ] Run `conda run -n translation-middleware python -m ruff check backend`.
- [ ] Run `npm test`.
- [ ] Run `npm run build`.
- [ ] Run `git status --short --branch`.
