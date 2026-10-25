"""Step 1: find Shorts in a niche and gather what it takes to judge them.

Five SerpApi engines, in this order:
  google_trends             what people search on YouTube around the seed topic
  youtube                   the Shorts YouTube shows for each of those searches
  youtube_video             exact views, likes, publish date and channel size
  youtube_channel           each channel's recent Shorts, for its baseline
  youtube_video_transcript  the opening lines of the strongest Shorts
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import date
from itertools import chain, zip_longest
from statistics import median

from .models import Short
from .parse import channel_ref, parse_count, parse_date
from .serp import Serp

REGION = {"gl": "us", "hl": "en"}
STOPWORDS = {"a", "an", "and", "for", "in", "of", "on", "the", "to", "with", "how", "what", "is", "vs"}
HOOK_SECONDS = 4
OPENING_SECONDS = 30


def content_words(text: str) -> list[str]:
    """Content words in order, lightly singularised: 'AI Agents' -> ['ai', 'agent']."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t[:-1] if len(t) > 3 and t.endswith("s") else t for t in tokens if t not in STOPWORDS]


def words(text: str) -> set[str]:
    return set(content_words(text))


def on_topic(query: str, seed: str) -> bool:
    """Shares most of the seed's words, and close together.

    'rogue ai agents' and 'ai agents course' pass for 'ai agents'; 'ai for real
    estate agents' doesn't: it has both words, but they mean something else.
    """
    seed_words = words(seed)
    query_words = content_words(query)
    found = [i for i, w in enumerate(query_words) if w in seed_words]
    if not found or len({query_words[i] for i in found}) < math.ceil(len(seed_words) * 2 / 3):
        return False
    return found[-1] - found[0] + 1 <= len(seed_words) + 1


def related_keywords(serp: Serp, seed: str, limit: int) -> list[str]:
    """The seed plus up to `limit` related YouTube searches from Google Trends.

    Rising and top queries alternate, so the list holds both what's growing and
    what's steady. A query must be on topic (Trends' related list also carries
    unrelated breakouts) and can't be a rewording of one already picked
    ('agents in ai' for 'ai agents').
    """
    if limit <= 0:
        return [seed]
    res = serp.search(
        {"engine": "google_trends", "q": seed, "gprop": "youtube", "data_type": "RELATED_QUERIES", "date": "today 3-m"},
        label=seed,
    )
    related = res.get("related_queries") or {}
    rising = [q.get("query", "") for q in related.get("rising", [])]
    top = [q.get("query", "") for q in related.get("top", [])]

    seen = {frozenset(words(seed))}
    picked: list[str] = []
    for query in chain.from_iterable(zip_longest(rising, top)):
        if not query:
            continue
        query_words = words(query)
        if not on_topic(query, seed) or frozenset(query_words) in seen:
            continue
        seen.add(frozenset(query_words))
        picked.append(query)
        if len(picked) == limit:
            break
    return [seed, *picked]


def discover_shorts(serp: Serp, keywords: list[str]) -> list[Short]:
    """Every Short YouTube shows for each search, de-duplicated across searches."""
    shorts: dict[str, Short] = {}
    for keyword in keywords:
        res = serp.search({"engine": "youtube", "search_query": keyword, **REGION}, label=keyword)
        for shelf in res.get("shorts_results") or []:
            for item in shelf.get("shorts") or []:
                video_id = item.get("video_id")
                if not video_id or video_id in shorts:
                    continue
                shorts[video_id] = Short(
                    id=video_id,
                    title=item.get("title") or "",
                    url=item.get("link") or f"https://www.youtube.com/shorts/{video_id}",
                    keyword=keyword,
                    views=parse_count(item.get("views") or item.get("views_original")),
                )
    return list(shorts.values())


def pick_for_details(shorts: list[Short], limit: int) -> list[Short]:
    """The most-viewed Shorts, taken in turns from each search so one keyword can't fill the list."""
    by_keyword: dict[str, list[Short]] = defaultdict(list)
    for short in sorted(shorts, key=lambda s: s.views or 0, reverse=True):
        by_keyword[short.keyword].append(short)
    queues = list(by_keyword.values())
    picked: list[Short] = []
    while len(picked) < limit and any(queues):
        for queue in queues:
            if queue and len(picked) < limit:
                picked.append(queue.pop(0))
    return picked


def add_details(serp: Serp, shorts: list[Short], today: date) -> None:
    """Exact views, likes, publish date and the channel's size, one lookup per Short."""
    for short in shorts:
        res = serp.search({"engine": "youtube_video", "v": short.id, **REGION}, label=short.title[:48])
        if res.get("error"):
            continue
        short.views = res.get("extracted_views") or parse_count(res.get("views")) or short.views
        short.likes = res.get("extracted_likes") or parse_count(res.get("likes"))
        published = parse_date(res.get("published_date"))
        if published:
            short.published = published.isoformat()
            short.age_days = max(0, (today - published).days)
        channel = res.get("channel") or {}
        short.channel_name = channel.get("name")
        short.channel_url = channel.get("link")
        short.subscribers = channel.get("extracted_subscribers") or parse_count(channel.get("subscribers"))


def add_baselines(serp: Serp, shorts: list[Short], limit: int) -> None:
    """Median views of each channel's recent Shorts: what normal looks like for that channel.

    With more channels than the budget allows, the ones whose Shorts out-ran
    their subscriber count the most go first.
    """
    channels: dict[str, list[Short]] = defaultdict(list)
    for short in shorts:
        ref = channel_ref(short.channel_url)
        if ref:
            channels[ref].append(short)

    def best_reach(ref: str) -> float:
        return max((s.views or 0) / max(s.subscribers or 1, 1) for s in channels[ref])

    for ref in sorted(channels, key=best_reach, reverse=True)[:limit]:
        name = channels[ref][0].channel_name or ref
        res = serp.search({"engine": "youtube_channel", "channel_id": ref, "tab": "shorts", **REGION}, label=name)
        views = [
            v
            for item in res.get("shorts_results") or []
            if (v := item.get("extracted_views") or parse_count(item.get("views"))) is not None
        ]
        if views:
            for short in channels[ref]:
                short.channel_median_views = float(median(views))


def add_hooks(serp: Serp, shorts: list[Short], limit: int) -> None:
    """The opening lines of the highest-scoring Shorts, word for word.

    A Short with no transcript usually has no speech (text on screen, music),
    so its hook is visual; that's recorded, and the next Short down is tried,
    up to twice `limit` tries in all.
    """
    ranked = sorted((s for s in shorts if s.radar_score is not None), key=lambda s: s.radar_score, reverse=True)
    found = 0
    for short in ranked[: 2 * limit]:
        if found == limit:
            break
        res = serp.search({"engine": "youtube_video_transcript", "v": short.id}, label=short.title[:48])
        lines = res.get("transcript") or []
        short.spoken = bool(lines)
        found += short.spoken
        short.opening = [
            {"start": round((line.get("start_ms") or 0) / 1000, 1), "text": " ".join((line.get("snippet") or "").split())}
            for line in lines
            if (line.get("start_ms") or 0) < OPENING_SECONDS * 1000
        ]
        hook = [seg["text"] for seg in short.opening if seg["start"] < HOOK_SECONDS]
        short.hook = " ".join(hook) or (short.opening[0]["text"] if short.opening else None)
