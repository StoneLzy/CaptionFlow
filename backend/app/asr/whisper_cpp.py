from app.asr.output import write_transcription_outputs
from app.asr.schemas import AsrConfig, TranscribeRequest, TranscriptionResult, TranscriptionSegment
from app.subtitles.srt import parse_srt
from app.whisper.adapter import WhisperCppAdapter
from app.whisper.schemas import WhisperRequest


class WhisperCppTranscriber:
    def __init__(self, config: AsrConfig, adapter: WhisperCppAdapter | None = None) -> None:
        self.config = config
        self.adapter = adapter or WhisperCppAdapter()

    def transcribe(self, request: TranscribeRequest) -> TranscriptionResult:
        if not request.audio_path.exists():
            raise FileNotFoundError(f"audio file not found: {request.audio_path}")

        whisper_request = WhisperRequest(
            executable_path=self.config.executable_path,
            model_path=self.config.model_path,
            input_path=request.audio_path,
            output_prefix=request.output_prefix,
            source_language=request.source_language,
            timestamp_precision=request.whisper_settings.timestamp_precision,
            dtw_preset=request.whisper_settings.dtw_preset,
        )
        self.adapter.run(whisper_request)

        transcript_path = request.output_prefix.with_suffix(".srt")
        parsed_segments = parse_srt(transcript_path.read_text(encoding="utf-8"))
        segments = [
            TranscriptionSegment(
                id=index,
                start=segment.start_ms / 1000.0,
                end=segment.end_ms / 1000.0,
                text=segment.text,
            )
            for index, segment in enumerate(parsed_segments)
        ]
        duration = segments[-1].end if segments else 0.0
        result = TranscriptionResult(
            language=request.source_language.value,
            duration=duration,
            segments=segments,
            text=" ".join(segment.text.strip() for segment in segments if segment.text.strip()),
        )
        write_transcription_outputs(
            request.output_prefix,
            result,
            self.config.segmentation,
            output_formats=request.output_formats,
            pipeline_requires_srt=request.pipeline_requires_srt,
        )
        return result
