from pathlib import Path

DTW_PRESET_RULES: tuple[tuple[str, str], ...] = (
    ("large-v3-turbo", "large.v3.turbo"),
    ("large-v3", "large.v3"),
    ("large-v2", "large.v2"),
    ("large-v1", "large.v1"),
    ("medium.en", "medium.en"),
    ("medium", "medium"),
    ("small.en", "small.en"),
    ("small", "small"),
    ("base.en", "base.en"),
    ("base", "base"),
    ("tiny.en", "tiny.en"),
    ("tiny", "tiny"),
)


def infer_dtw_preset(model_path: Path) -> str:
    name = model_path.name.lower()
    for fragment, preset in DTW_PRESET_RULES:
        if fragment in name:
            return preset
    return ""


def resolve_dtw_preset(model_path: Path, explicit_preset: str = "") -> str:
    if explicit_preset.strip():
        return explicit_preset.strip()
    return infer_dtw_preset(model_path)
