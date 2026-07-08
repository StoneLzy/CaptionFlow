from pathlib import Path

from app.whisper.dtw import infer_dtw_preset, resolve_dtw_preset


def test_infer_dtw_preset_from_large_v3_model() -> None:
    assert infer_dtw_preset(Path("/models/ggml-large-v3.bin")) == "large.v3"


def test_infer_dtw_preset_from_large_v3_turbo_model() -> None:
    assert infer_dtw_preset(Path("/models/ggml-large-v3-turbo.bin")) == "large.v3.turbo"


def test_resolve_dtw_preset_prefers_explicit_value() -> None:
    assert (
        resolve_dtw_preset(Path("/models/ggml-large-v3.bin"), "medium.en") == "medium.en"
    )


def test_resolve_dtw_preset_falls_back_to_inference() -> None:
    assert resolve_dtw_preset(Path("/models/ggml-small.bin"), "") == "small"
