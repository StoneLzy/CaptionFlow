from pathlib import Path

from app.asr.output import write_transcription_outputs
from app.asr.schemas import TranscriptionResult, TranscriptionSegment
from app.jobs.export_outputs import collect_transcript_outputs
from app.jobs.schemas import JobCreate, OutputFormat


def test_write_transcription_outputs_respects_selected_formats(tmp_path: Path) -> None:
    prefix = tmp_path / "transcript"
    result = TranscriptionResult(
        language="en",
        duration=1.0,
        segments=[TranscriptionSegment(id=0, start=0.0, end=1.0, text="Hello")],
        text="Hello",
    )

    write_transcription_outputs(prefix, result, output_formats=["srt"])

    assert prefix.with_suffix(".srt").exists()
    assert not prefix.with_suffix(".txt").exists()
    assert not prefix.with_suffix(".md").exists()
    assert not prefix.with_suffix(".json").exists()


def test_write_transcription_outputs_can_write_json_only(tmp_path: Path) -> None:
    prefix = tmp_path / "transcript"
    result = TranscriptionResult(
        language="en",
        duration=1.0,
        segments=[TranscriptionSegment(id=0, start=0.0, end=1.0, text="Hello")],
        text="Hello",
    )

    path = write_transcription_outputs(prefix, result, output_formats=["json"])

    assert path == prefix.with_suffix(".json")
    assert prefix.with_suffix(".json").exists()
    assert not prefix.with_suffix(".srt").exists()


def test_write_transcription_outputs_writes_internal_srt_when_pipeline_requires_it(
    tmp_path: Path,
) -> None:
    prefix = tmp_path / "transcript"
    result = TranscriptionResult(
        language="en",
        duration=1.0,
        segments=[TranscriptionSegment(id=0, start=0.0, end=1.0, text="Hello")],
        text="Hello",
    )

    write_transcription_outputs(
        prefix,
        result,
        output_formats=["json"],
        pipeline_requires_srt=True,
    )

    assert prefix.with_suffix(".json").exists()
    assert prefix.with_suffix(".srt").exists()


def test_collect_transcript_outputs_only_lists_selected_formats(tmp_path: Path) -> None:
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    (job_dir / "transcript.srt").write_text("srt", encoding="utf-8")
    (job_dir / "transcript.json").write_text("{}", encoding="utf-8")

    outputs = collect_transcript_outputs(
        job_dir,
        JobCreate(output_formats=[OutputFormat.SRT]),
    )

    assert outputs == {"transcript_srt": str(job_dir / "transcript.srt")}
