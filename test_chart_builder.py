"""Skrip uji cepat utils/chart_builder.py.

Cara menjalankan dari folder proyek:
    python test_chart_builder.py
"""

from __future__ import annotations

import pandas as pd

from utils.chart_builder import (
    bar_chart_confidence,
    bar_chart_platform,
    bar_chart_sentiment,
    bar_chart_top_words,
    create_heatmap,
    create_network_stats_bar,
    create_sentiment_bar,
    create_sentiment_pie,
    create_top_words_bar,
    create_trend_line,
    gauge_confidence,
    grouped_bar_platform_sentiment,
    heatmap_topics,
    pie_chart_sentiment,
    scatter_followers_degree,
    timeline_sentiment,
)

sentiment_df = pd.DataFrame(
    {
        "date": pd.date_range("2025-11-01", periods=9, freq="D"),
        "platform": ["twitter", "instagram", "tiktok"] * 3,
        "predicted_sentiment": [
            "positive",
            "neutral",
            "negative",
            "negative",
            "positive",
            "neutral",
            "negative",
            "positive",
            "negative",
        ],
        "confidence": [0.91, 0.72, 0.88, 0.81, 0.94, 0.69, 0.85, 0.90, 0.77],
    }
)

node_df = pd.DataFrame(
    {
        "username": ["akun_a", "akun_b", "akun_c"],
        "platform": ["twitter", "instagram", "tiktok"],
        "followers": [174, 1060, 1612],
        "degree_centrality": [0.103, 0.069, 0.138],
        "degree": [3, 2, 4],
        "in_degree": [2, 1, 1],
        "out_degree": [1, 1, 3],
    }
)

network_stats_df = pd.DataFrame(
    {
        "metric": ["degree_centrality", "in_degree", "out_degree", "followers"],
        "value": [0.138, 2, 3, 1612],
    }
)

matrix_df = pd.DataFrame(
    [[10, 4, 3], [8, 3, 2], [6, 2, 1]],
    index=["Twitter/X", "Instagram", "TikTok"],
    columns=["Gangguan Jaringan", "Apresiasi", "Harga Kuota"],
)

topics = [
    {"label": "Gangguan Jaringan", "keywords": [("sinyal", 0.9), ("jaringan", 0.8), ("down", 0.7)]},
    {"label": "Apresiasi", "keywords": [("cepat", 0.8), ("terima kasih", 0.7), ("keren", 0.6)]},
]

FUNCS = [
    ("create_sentiment_pie", lambda: create_sentiment_pie(sentiment_df)),
    ("create_sentiment_bar", lambda: create_sentiment_bar(sentiment_df)),
    ("create_trend_line", lambda: create_trend_line(sentiment_df)),
    ("create_top_words_bar", lambda: create_top_words_bar({"internet": 12, "jaringan": 9, "lambat": 7}, "negative")),
    ("create_network_stats_bar", lambda: create_network_stats_bar(network_stats_df)),
    ("create_heatmap", lambda: create_heatmap(matrix_df)),
    ("bar_chart_sentiment", lambda: bar_chart_sentiment(sentiment_df)),
    ("pie_chart_sentiment", lambda: pie_chart_sentiment(sentiment_df)),
    ("bar_chart_confidence", lambda: bar_chart_confidence(sentiment_df)),
    ("timeline_sentiment", lambda: timeline_sentiment(sentiment_df)),
    ("bar_chart_platform", lambda: bar_chart_platform(sentiment_df)),
    ("grouped_bar_platform_sentiment", lambda: grouped_bar_platform_sentiment(sentiment_df)),
    ("scatter_followers_degree", lambda: scatter_followers_degree(node_df)),
    ("bar_chart_top_words", lambda: bar_chart_top_words([("internet", 12), ("jaringan", 9), ("lambat", 7)], "negative")),
    ("heatmap_topics", lambda: heatmap_topics(topics)),
    ("gauge_confidence", lambda: gauge_confidence(0.82, "Confidence Prediksi")),
]

if __name__ == "__main__":
    ok = 0
    for name, fn in FUNCS:
        fig = fn()
        assert fig is not None, f"{name}: None"
        assert hasattr(fig, "to_dict"), f"{name}: bukan objek Plotly Figure"
        assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)", f"{name}: paper_bgcolor belum transparan"
        assert fig.layout.plot_bgcolor == "rgba(0,0,0,0)", f"{name}: plot_bgcolor belum transparan"
        print(f"OK  {name}")
        ok += 1
    print(f"\nSemua {ok}/{len(FUNCS)} fungsi chart berhasil diuji.")
