from datetime import date

import pytest

from shorts_radar.parse import channel_ref, parse_count, parse_date


@pytest.mark.parametrize(
    "text, expected",
    [("765,636 views", 765636), ("1.2K views", 1200), ("3.4M", 3_400_000), ("21K", 21000), ("No views", 0), (5321, 5321), (None, None)],
)
def test_parse_count(text, expected):
    assert parse_count(text) == expected


@pytest.mark.parametrize(
    "label, expected",
    [("Feb 17, 2025", date(2025, 2, 17)), ("Premiered Mar 3, 2024", date(2024, 3, 3)), ("September 9, 2025", date(2025, 9, 9)), ("2025-02-17", date(2025, 2, 17))],
)
def test_parse_date(label, expected):
    assert parse_date(label) == expected


def test_parse_date_rejects_relative_labels():
    assert parse_date("3 weeks ago") is None


def test_channel_ref_gives_what_youtube_channel_takes():
    assert channel_ref("https://www.youtube.com/@kenkai") == "kenkai"
    assert channel_ref("https://www.youtube.com/channel/UCUgIHlYBOD3yA3yDIRhg_mg") == "UCUgIHlYBOD3yA3yDIRhg_mg"
    assert channel_ref("https://example.com/x") is None
