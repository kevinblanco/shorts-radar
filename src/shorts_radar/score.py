"""Step 2: judge every Short against its own channel, not against everyone.

Raw views mostly measure how big the channel is. Three measures that don't:

  vs_channel     views / the median views of that channel's recent Shorts
  views_per_day  views / days since it was posted
  views_per_sub  views / the channel's subscribers

Each Short gets a percentile on each measure within this run, and its radar
score (0 to 100) is the average. A Short is scored only once it has been
judged against its own channel (vs_channel), because views per day on its own
mostly measures how big the channel is. High on all three means a pattern
worth studying.
"""

from __future__ import annotations

from .models import Short

MEASURES = ("vs_channel", "views_per_day", "views_per_sub")
REQUIRED = "vs_channel"
MIN_MEASURES = 2  # a score from a single measure says too little


def add_measures(short: Short) -> None:
    views = short.views
    if not views:
        return
    if short.channel_median_views:
        short.vs_channel = views / short.channel_median_views
    if short.age_days is not None:
        short.views_per_day = views / max(short.age_days, 1)
    if short.subscribers:
        short.views_per_sub = views / short.subscribers


def percentiles(values: list[float]) -> list[float]:
    """Each value's position in the list from 0 to 1, ties sharing their average position."""
    if len(values) == 1:
        return [1.0]
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 / (len(values) - 1)
        i = j + 1
    return ranks


def score(shorts: list[Short]) -> list[Short]:
    """Fills the three measures and the radar score; returns the Shorts best first."""
    for short in shorts:
        add_measures(short)

    per_short: dict[str, list[float]] = {s.id: [] for s in shorts}
    for measure in MEASURES:
        have = [s for s in shorts if getattr(s, measure) is not None]
        for short, pct in zip(have, percentiles([getattr(s, measure) for s in have])):
            per_short[short.id].append(pct)

    for short in shorts:
        pcts = per_short[short.id]
        judged = getattr(short, REQUIRED) is not None
        short.radar_score = round(100 * sum(pcts) / len(pcts), 1) if judged and len(pcts) >= MIN_MEASURES else None

    return sorted(shorts, key=lambda s: (s.radar_score is not None, s.radar_score or 0), reverse=True)
