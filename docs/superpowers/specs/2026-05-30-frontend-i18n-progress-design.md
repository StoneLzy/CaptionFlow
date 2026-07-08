# Frontend i18n Progress Redesign Design

## Goal

Improve the local workbench UI, make Chinese the default interface language with an English toggle, and show live job progress while jobs are starting or running.

## Layout

Use the approved v2 three-column workbench:

- Left: a compact job rail for history, status, and current progress percentage.
- Center: the primary job configuration surface, wider than today and organized into clear sections.
- Right: a stable-width progress panel for the selected job.

The interface should stay operational rather than marketing-like. It should be dense enough for repeated local use, with restrained borders, clear section headings, and no nested decorative cards.

## Language Switching

Chinese is the default language. The top bar exposes a segmented `中文 / EN` language switch. The selected language is stored in `localStorage` under `tm_ui_language`. If no stored value exists, the UI starts in Chinese.

Use a small local translation dictionary rather than adding an i18n framework. It must cover all visible frontend labels, buttons, hints, empty states, job status labels, and progress stage labels touched by this feature.

## Live Progress

The frontend should continue polling while any job is not terminal. Terminal statuses are `completed` and `failed`; `created` and `running` should poll. This fixes the current issue where a newly-started job can appear stuck because the first response has not yet flipped to `running`.

The backend already stores `StageProgress`, but the runner does not update stages during work. Add repository helpers and runner updates so the selected job can show meaningful phase changes:

- Upload is completed when the runner starts.
- Transcription is running/completed/skipped depending on job type.
- Merge is running/completed/skipped depending on merge settings.
- Translation is running/completed/skipped depending on translation settings.
- Export is completed at the end.
- Failures mark the current relevant stage as failed and store the error summary.

For translation, processed/total should be visible when available from segment counts.

## Testing

Add backend tests for persisted stage updates and runner progress. Add frontend tests for default Chinese labels, English switching, polling for `created` jobs, and localized progress display.
