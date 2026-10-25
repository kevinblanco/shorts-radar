"""Turning YouTube's display strings into numbers, dates and channel ids."""

from __future__ import annotations

import re
from datetime import date, datetime

_SUFFIX = {"k": 1e3, "m": 1e6, "b": 1e9}


def parse_count(value: int | float | str | None) -> int | None:
    """'1.2K views' -> 1200, '765,636 views' -> 765636, 'No views' -> 0."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = value.strip().lower()
    if text.startswith("no "):
        return 0
    match = re.search(r"([\d.,]+)\s*([kmb])?", text)
    if not match:
        return None
    digits, suffix = match.groups()
    if suffix:
        return round(float(digits.replace(",", ".")) * _SUFFIX[suffix])
    return int(re.sub(r"[.,]", "", digits))


def parse_date(label: str | None) -> date | None:
    """'Feb 17, 2025', 'Premiered Mar 3, 2024' or '2025-02-17' -> a date."""
    if not label:
        return None
    match = re.search(r"([A-Z][a-z]{2})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", label)
    if match:
        month, day, year = match.groups()
        return datetime.strptime(f"{month} {day} {year}", "%b %d %Y").date()
    match = re.search(r"\d{4}-\d{2}-\d{2}", label)
    return date.fromisoformat(match.group(0)) if match else None


def channel_ref(url: str | None) -> str | None:
    """The channel_id SerpApi's youtube_channel engine takes: a bare handle or a UC... id.

    https://www.youtube.com/@kenkai -> 'kenkai'
    https://www.youtube.com/channel/UCxxxx -> 'UCxxxx'
    """
    if not url:
        return None
    match = re.search(r"youtube\.com/(?:@([\w.-]+)|channel/(UC[\w-]{22}))", url)
    if not match:
        return None
    return match.group(1) or match.group(2)
