from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Short:
    """One YouTube Short and everything the radar learns about it."""

    id: str
    title: str
    url: str
    keyword: str  # the search that surfaced it
    views: int | None = None

    # From the youtube_video engine
    likes: int | None = None
    published: str | None = None  # ISO date
    age_days: int | None = None
    channel_name: str | None = None
    channel_url: str | None = None
    subscribers: int | None = None

    # From the youtube_channel engine (the channel's recent Shorts)
    channel_median_views: float | None = None

    # From score.py
    vs_channel: float | None = None  # views / channel's median Short views
    views_per_day: float | None = None
    views_per_sub: float | None = None
    radar_score: float | None = None  # 0 to 100

    # From the youtube_video_transcript engine
    hook: str | None = None  # roughly the first four seconds, word for word
    opening: list[dict] = field(default_factory=list)
    spoken: bool | None = None  # False: no transcript (text on screen or music); None: not checked

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Short:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Budget:
    """How many searches each step may spend. Defaults cost 39 to 42 per run."""

    keywords: int = 4  # related searches from Google Trends, plus the seed itself
    details: int = 20  # Shorts that get a youtube_video lookup
    channels: int = 10  # channels that get a baseline from their Shorts tab
    hooks: int = 3  # spoken openings to collect from the top Shorts (up to twice as many tries)

    def max_searches(self) -> int:
        return 1 + (self.keywords + 1) + self.details + self.channels + 2 * self.hooks
