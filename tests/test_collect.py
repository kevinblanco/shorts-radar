"""The whole pipeline against a fake client. Responses follow the shapes SerpApi
returned for these engines on October 25, 2026; the Shorts themselves are made up."""

import json
from datetime import date

from shorts_radar import collect, report
from shorts_radar.score import score

TODAY = date(2026, 10, 25)


class FakeSerp:
    def __init__(self):
        self.calls = []
        self.live = 0
        self.cached = 0

    def search(self, params, label=""):
        self.calls.append(params)
        self.live += 1
        engine = params["engine"]
        if engine == "google_trends":
            return {
                "related_queries": {
                    "rising": [{"query": "rogue ai agents"}, {"query": "celebrity news"}, {"query": "ai for real estate agents"}, {"query": "best ai agents"}],
                    "top": [{"query": "agents in ai"}, {"query": "build ai agents"}, {"query": "ai course"}],
                }
            }
        if engine == "youtube":
            q = params["search_query"].replace(" ", "")
            return {
                "shorts_results": [
                    {"shorts": [{"video_id": f"{q}-{i}", "title": f"{params['search_query']} short {i}", "views": (i + 1) * 10_000} for i in range(4)]},
                    {"shorts": [{"video_id": "shared-1", "title": "In every search", "views_original": "1.2M views"}]},
                ]
            }
        if engine == "youtube_video":
            vid = params["v"]
            small = vid.endswith("-3")  # the most-viewed Short of each search comes from a small channel
            return {
                "extracted_views": 40_000 if vid != "shared-1" else 1_200_000,
                "extracted_likes": 900,
                "published_date": "Oct 1, 2026",
                "channel": {
                    "name": f"chan-{vid}" if small else "Big Channel",
                    "link": f"https://www.youtube.com/@chan{vid.replace('-', '')}" if small else "https://www.youtube.com/@big",
                    "extracted_subscribers": 2_000 if small else 5_000_000,
                },
            }
        if engine == "youtube_channel":
            base = 1_000 if params["channel_id"] != "big" else 900_000
            return {"shorts_results": [{"extracted_views": base * k} for k in (1, 1, 2)]}
        if engine == "youtube_video_transcript":
            if params["v"].startswith("rogue"):  # a Short with no speech
                return {"error": "YouTube Video Transcript hasn't returned any results for this query."}
            return {"transcript": [
                {"start_ms": 0, "snippet": "Stop building agents"},
                {"start_ms": 1800, "snippet": "like it's 2024?"},
                {"start_ms": 6000, "snippet": "Here's the setup."},
                {"start_ms": 31000, "snippet": "Too late to count."},
            ]}
        raise AssertionError(f"unexpected call {params}")


def test_on_topic_needs_the_seed_words_close_together():
    assert collect.on_topic("rogue ai agents", "ai agents")
    assert collect.on_topic("ai agents course", "ai agents")
    assert not collect.on_topic("ai for real estate agents", "ai agents")
    assert not collect.on_topic("ai course", "ai agents")


def test_keywords_stay_on_topic_and_skip_rewordings():
    serp = FakeSerp()
    keywords = collect.related_keywords(serp, "ai agents", 4)
    assert keywords == ["ai agents", "rogue ai agents", "build ai agents", "best ai agents"]
    assert serp.calls[0]["gprop"] == "youtube"


def test_full_run():
    serp = FakeSerp()
    keywords = collect.related_keywords(serp, "ai agents", 2)
    found = collect.discover_shorts(serp, keywords)
    assert len(found) == 3 * 4 + 1  # the shared Short is counted once

    picked = collect.pick_for_details(found, 6)
    assert {s.keyword for s in picked} == set(keywords)  # every search gets a turn

    collect.add_details(serp, picked, TODAY)
    collect.add_baselines(serp, picked, limit=3)
    ranked = score(found)
    collect.add_hooks(serp, ranked, 2)

    top = ranked[0]
    assert top.channel_name.startswith("chan-")  # a small channel's hit wins, not the big channel
    assert top.vs_channel == 40.0 and top.age_days == 24
    hooked = [s for s in ranked if s.hook]
    assert len(hooked) == 2 and hooked[0].hook == "Stop building agents like it's 2024?"
    assert len(hooked[0].opening) == 3
    silent = [s for s in ranked if s.spoken is False]
    assert all(s.id.startswith("rogue") for s in silent)

    channel_calls = [c for c in serp.calls if c["engine"] == "youtube_channel"]
    assert len(channel_calls) == 3 and all(c["tab"] == "shorts" for c in channel_calls)
    transcript_calls = [c for c in serp.calls if c["engine"] == "youtube_video_transcript"]
    assert len(transcript_calls) == 2 + len(silent)  # silent Shorts are skipped past, within 2x the limit
    assert len(serp.calls) == 1 + 3 + 6 + 3 + len(transcript_calls)

    data = report.build_dataset("ai agents", keywords, ranked, {"live": serp.live, "cached": 0})
    assert json.loads(json.dumps(data))["counts"]["with_hook"] == 2
    md = report.snapshot_markdown(data)
    assert md.startswith("# Shorts radar: ai agents")
    assert "Stop building agents like it's 2024?" in md
    assert "—" not in md
