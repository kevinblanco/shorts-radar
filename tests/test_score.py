from shorts_radar.models import Short
from shorts_radar.score import percentiles, score


def short(id, views, subs, median, age):
    return Short(id=id, title=id, url="", keyword="k", views=views, subscribers=subs, channel_median_views=median, age_days=age)


def test_percentiles_share_ties():
    assert percentiles([10, 30, 20]) == [0.0, 1.0, 0.5]
    assert percentiles([5, 5, 9]) == [0.25, 0.25, 1.0]
    assert percentiles([7]) == [1.0]


def test_a_small_channel_hit_beats_a_big_channel_average():
    big = short("big", views=2_000_000, subs=10_000_000, median=1_500_000, age=60)  # a normal day for them
    small = short("small", views=765_636, subs=21_200, median=20_000, age=30)  # 36x its subscribers
    mid = short("mid", views=50_000, subs=100_000, median=40_000, age=10)
    ranked = score([big, small, mid])
    assert ranked[0].id == "small"
    assert round(ranked[0].views_per_sub) == 36
    assert ranked[0].vs_channel > 38


def test_scores_only_shorts_judged_against_their_channel():
    unjudged = short("x", views=5_000_000, subs=1_000_000, median=None, age=1)  # huge, but no baseline
    judged = short("y", views=100, subs=50, median=20, age=3)
    ranked = score([unjudged, judged])
    assert unjudged.radar_score is None
    assert judged.radar_score is not None
    assert ranked == [judged, unjudged]
