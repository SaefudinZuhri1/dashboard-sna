"""Skrip uji cepat untuk utils/chart_builder.py — jalankan: python test_chart_builder.py"""

from utils.chart_builder import (
    bar_chart_confidence,
    bar_chart_platform,
    bar_chart_sentiment,
    bar_chart_top_words,
    gauge_confidence,
    grouped_bar_platform_sentiment,
    heatmap_topics,
    pie_chart_sentiment,
    scatter_followers_degree,
    timeline_sentiment,
)
from utils.data_loader import load_sentiment_data
from utils.dummy_data import get_dummy_influencer_data, get_dummy_topics

FUNCS = [
    ("bar_chart_sentiment", lambda: bar_chart_sentiment(load_sentiment_data("IndiHome"))),
    ("pie_chart_sentiment", lambda: pie_chart_sentiment(load_sentiment_data("IndiHome"))),
    ("bar_chart_confidence", lambda: bar_chart_confidence(load_sentiment_data("IndiHome"))),
    ("timeline_sentiment", lambda: timeline_sentiment(load_sentiment_data("IndiHome"))),
    ("bar_chart_platform", lambda: bar_chart_platform(load_sentiment_data("IndiHome"))),
    (
        "grouped_bar_platform_sentiment",
        lambda: grouped_bar_platform_sentiment(load_sentiment_data("IndiHome")),
    ),
    ("scatter_followers_degree", lambda: scatter_followers_degree(get_dummy_influencer_data())),
    (
        "bar_chart_top_words",
        lambda: bar_chart_top_words(
            [("internet", 12), ("jaringan", 9), ("lambat", 7)], "negative"
        ),
    ),
    (
        "heatmap_topics",
        lambda: heatmap_topics(
            [
                {
                    "label": t["name"],
                    "keywords": list(zip(t["keywords"], [0.9 - i * 0.1 for i in range(len(t["keywords"]))])),
                }
                for t in get_dummy_topics()
            ]
        ),
    ),
    ("gauge_confidence", lambda: gauge_confidence(0.82, "Confidence Prediksi")),
]

if __name__ == "__main__":
    ok = 0
    for name, fn in FUNCS:
        fig = fn()
        assert fig is not None, f"{name}: None"
        assert len(fig.data) > 0 or name == "gauge_confidence", f"{name}: figure kosong"
        print(f"OK  {name}")
        ok += 1
    print(f"\nSemua {ok}/{len(FUNCS)} fungsi chart berhasil diuji.")
