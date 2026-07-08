import re

_INVALID_FILENAME_CHARS = re.compile(r'[/\\:*?"<>|\n\r\t]+')
_WHITESPACE = re.compile(r"\s+")


def sanitize_job_display_name(name: str, *, max_length: int = 200) -> str:
    cleaned = _INVALID_FILENAME_CHARS.sub(" ", name.strip())
    cleaned = _WHITESPACE.sub(" ", cleaned).strip()
    if not cleaned:
        raise ValueError("Display name cannot be empty")
    if len(cleaned) > max_length:
        cleaned = cleaned[: max_length - 1].rstrip() + "…"
    return cleaned
