from app.asr.factory import asr_config_from_settings, build_transcriber
from app.asr.schemas import AsrBackend
from app.asr.whisper_cpp import WhisperCppTranscriber
from app.asr.whisperkit_server import WhisperKitServerTranscriber
from app.core.config import Settings


def test_build_transcriber_selects_whisperkit_server_by_default() -> None:
    config = asr_config_from_settings(Settings(_env_file=None))
    transcriber = build_transcriber(config)

    assert config.backend == AsrBackend.WHISPERKIT_SERVER
    assert isinstance(transcriber, WhisperKitServerTranscriber)
    assert config.whisperkit_model == "large-v3-v20240930_626MB"
    assert config.segmentation.max_chars == 42


def test_build_transcriber_selects_faster_whisper_when_configured() -> None:
    config = asr_config_from_settings(Settings(asr_backend=AsrBackend.FASTER_WHISPER))
    transcriber = build_transcriber(config)

    assert transcriber.__class__.__name__ == "FasterWhisperTranscriber"


def test_build_transcriber_selects_whisper_cpp_when_configured() -> None:
    config = asr_config_from_settings(Settings(asr_backend=AsrBackend.WHISPER_CPP))
    transcriber = build_transcriber(config)

    assert isinstance(transcriber, WhisperCppTranscriber)


def test_build_transcriber_selects_whisperkit_server_when_configured() -> None:
    config = asr_config_from_settings(
        Settings(
            asr_backend=AsrBackend.WHISPERKIT_SERVER,
            whisperkit_cli_workdir="/tmp/argmax-oss-swift",
            _env_file=None,
        )
    )
    transcriber = build_transcriber(config)

    assert isinstance(transcriber, WhisperKitServerTranscriber)
    assert config.whisperkit_model == "large-v3-v20240930_626MB"
    assert str(config.whisperkit_cli_workdir) == "/tmp/argmax-oss-swift"
