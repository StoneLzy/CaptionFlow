import pytest

from app.jobs.names import sanitize_job_display_name


def test_sanitize_job_display_name_strips_invalid_chars() -> None:
    assert sanitize_job_display_name('  My Video: Part 1/2  ') == "My Video Part 1 2"


def test_sanitize_job_display_name_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        sanitize_job_display_name("  /\\  ")


def test_sanitize_job_display_name_truncates_long_values() -> None:
    result = sanitize_job_display_name("a" * 250, max_length=200)
    assert len(result) == 200
    assert result.endswith("…")
