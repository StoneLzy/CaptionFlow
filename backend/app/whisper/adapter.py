import subprocess
from pathlib import Path

from app.core.constants import SourceLanguage
from app.whisper.schemas import WhisperRequest, WhisperTimestampPrecision


class WhisperCppAdapter:
    def validate_paths(self, executable_path: Path, model_path: Path) -> None:
        if not executable_path.exists():
            raise FileNotFoundError(f"whisper executable not found: {executable_path}")
        if not model_path.exists():
            raise FileNotFoundError(f"whisper model not found: {model_path}")

    def apply_timestamp_flags(self, command: list[str], request: WhisperRequest) -> None:
        if request.timestamp_precision == WhisperTimestampPrecision.STANDARD:
            return
        command.extend(["-ml", "1", "-sow"])
        if request.timestamp_precision == WhisperTimestampPrecision.WORD_DTW:
            preset = request.resolved_dtw_preset()
            if not preset:
                raise ValueError(
                    "DTW preset is required for word_dtw mode. "
                    "Set whisper_settings.dtw_preset or use a recognized model filename."
                )
            command.extend(["--dtw", preset])

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
        self.apply_timestamp_flags(command, request)
        return command

    def run(self, request: WhisperRequest) -> subprocess.CompletedProcess[str]:
        command = self.build_command(request)
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        expected_srt = request.output_prefix.with_suffix(".srt")
        if result.returncode != 0 or not expected_srt.exists():
            details = (result.stderr or result.stdout or "whisper produced no subtitle output").strip()
            raise RuntimeError(f"whisper transcription failed: {details}")
        return result
