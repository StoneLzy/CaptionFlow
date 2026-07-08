from app.subtitles.srt import format_markdown, format_srt, format_txt, parse_srt


SAMPLE_SRT = """1
00:00:01,000 --> 00:00:02,000
Hello

2
00:00:02,200 --> 00:00:03,000
world.
"""


def test_parse_srt_segments() -> None:
    segments = parse_srt(SAMPLE_SRT)

    assert len(segments) == 2
    assert segments[0].index == 1
    assert segments[0].start_ms == 1000
    assert segments[0].end_ms == 2000
    assert segments[0].text == "Hello"


def test_format_srt_round_trips_basic_timing() -> None:
    segments = parse_srt(SAMPLE_SRT)

    rendered = format_srt(segments)

    assert "00:00:01,000 --> 00:00:02,000" in rendered
    assert "world." in rendered


def test_format_txt_and_markdown() -> None:
    segments = parse_srt(SAMPLE_SRT)

    assert format_txt(segments) == "Hello\nworld.\n"
    assert "| 1 | 00:00:01,000 | 00:00:02,000 | Hello |" in format_markdown(segments)


def test_preserves_multiline_srt_text_and_formats_display_outputs() -> None:
    content = """1
00:00:01,000 --> 00:00:03,000
Hello | there
General Kenobi
"""

    segments = parse_srt(content)

    assert segments[0].text == "Hello | there\nGeneral Kenobi"
    assert format_srt(segments) == content
    assert format_txt(segments) == "Hello | there General Kenobi\n"
    assert (
        "| 1 | 00:00:01,000 | 00:00:03,000 | Hello \\| there<br>General Kenobi |"
        in format_markdown(segments)
    )
