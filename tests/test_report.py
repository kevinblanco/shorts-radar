from shorts_radar import report
from shorts_radar.models import Short


def test_snapshot_table_survives_pipes_in_names():
    s = Short(id="a", title="Agents | Part 1", url="u", keyword="k", views=1000, channel_name="Ed Hill | AI Automation",
              channel_median_views=10, age_days=5, subscribers=100, radar_score=80.0, vs_channel=100, views_per_day=200, views_per_sub=10)
    md = report.snapshot_markdown(report.build_dataset("ai agents", ["ai agents"], [s], {"live": 1, "cached": 0}))
    row = next(line for line in md.splitlines() if line.startswith("| 1 |"))
    assert row.replace("\\|", "").count("|") == 9  # 8 columns
    assert "Ed Hill \\| AI Automation" in row


def test_compact_numbers():
    assert report.compact(1_820_000) == "1.8M"
    assert report.compact(768_300) == "768.3K"
    assert report.compact(48) == "48"
    assert report.times(1602.4) == "1602×"
    assert report.times(2.04) == "2.0×"
