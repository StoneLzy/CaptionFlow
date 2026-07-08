from pydantic import BaseModel, Field, field_validator


class SubtitleSegment(BaseModel):
    index: int = Field(ge=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    text: str

    @field_validator("end_ms")
    @classmethod
    def end_after_start(cls, value: int, info) -> int:
        start_ms = info.data.get("start_ms")
        if start_ms is not None and value < start_ms:
            raise ValueError("end_ms must be greater than or equal to start_ms")
        return value

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms
