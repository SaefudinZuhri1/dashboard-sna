"""Builder chart Plotly untuk dashboard analitik sentimen dan SNA."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

try:
    import streamlit as st
except Exception:  # pragma: no cover - fallback untuk pengujian utilitas
    st = None

# --- Warna standar proyek ---
SENTIMENT_COLORS = {
    "positive": "#4CAF50",
    "neutral": "#FF9800",
    "negative": "#F44336",
}

PLATFORM_COLORS = {
    "twitter": "#1DA1F2",
    "instagram": "#833AB4",
    "tiktok": "#000000",
}

PRIMARY_COLOR = "#1DA1F2"
ACCENT_COLOR = "#E53935"

SENTIMENT_ORDER = ["positive", "neutral", "negative"]
SENTIMENT_LABELS = {
    "positive": "Positif",
    "neutral": "Netral",
    "negative": "Negatif",
}

PLATFORM_ORDER = ["twitter", "instagram", "tiktok"]
PLATFORM_LABELS = {
    "twitter": "Twitter/X",
    "instagram": "Instagram",
    "tiktok": "TikTok",
}

_GAUGE_RED = "#F44336"
_GAUGE_YELLOW = "#FFC107"
_GAUGE_GREEN = "#4CAF50"


def _empty_figure(message: str = "Data tidak tersedia") -> go.Figure:
    """Kembalikan figure kosong dengan pesan singkat."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=14, color="rgba(150,150,150,1)"),
    )
    _apply_layout(fig)
    return fig


def _is_dark_mode() -> bool:
    """Ambil status mode gelap secara aman dari session Streamlit."""
    try:
        if st is None:
            return True
        return bool(st.session_state.get("dark_mode", True))
    except Exception:
        return True


def _apply_layout(fig: go.Figure, title: str = "") -> None:
    """Terapkan layout Plotly yang konsisten untuk mode terang dan gelap."""
    dark_mode = _is_dark_mode()
    text_color = "#F8FAFC" if dark_mode else "#1F2937"
    muted_color = "#A7B0BF" if dark_mode else "#64748B"
    border_color = "rgba(167,176,191,0.22)" if dark_mode else "rgba(100,116,139,0.18)"

    fig.update_layout(
        template="plotly_dark" if dark_mode else "plotly_white",
        title={
            "text": title or None,
            "font": {"color": text_color, "size": 16},
            "x": 0.0,
            "xanchor": "left",
        },
        font=dict(color=text_color, family="Inter, Arial, sans-serif"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=55 if title else 20, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color=text_color),
            bgcolor="rgba(0,0,0,0)",
        ),
        hoverlabel=dict(
            bgcolor="#151B26" if dark_mode else "#FFFFFF",
            bordercolor=border_color,
            font=dict(color=text_color),
        ),
    )
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        color=text_color,
        tickfont=dict(color=muted_color),
        title_font=dict(color=text_color),
        linecolor=border_color,
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=border_color,
        zeroline=False,
        color=text_color,
        tickfont=dict(color=muted_color),
        title_font=dict(color=text_color),
        linecolor=border_color,
    )

    # Label donut/pie dibuat putih agar tetap terbaca pada setiap warna sektor.
    fig.update_traces(textfont=dict(color="#FFFFFF"), selector=dict(type="pie"))


def _resolve_sentiment_col(df: pd.DataFrame) -> str:
    """Temukan kolom sentimen pada DataFrame."""
    for col in ("predicted_sentiment", "sentiment", "label"):
        if col in df.columns:
            return col
    raise KeyError("Kolom sentimen tidak ditemukan (predicted_sentiment / sentiment / label).")


def _count_sentiment(df: pd.DataFrame) -> pd.DataFrame:
    """Hitung jumlah komentar per sentimen dengan urutan tetap."""
    col = _resolve_sentiment_col(df)
    counts = (
        df[col]
        .astype(str)
        .str.lower()
        .str.strip()
        .value_counts()
        .reindex(SENTIMENT_ORDER, fill_value=0)
        .reset_index()
    )
    counts.columns = ["sentiment", "count"]
    counts["label"] = counts["sentiment"].map(SENTIMENT_LABELS)
    return counts


def _parse_keyword_weights(keywords: list) -> list[tuple[str, float]]:
    """
    Ubah daftar kata kunci menjadi pasangan (kata, bobot).

    Mendukung format [str, ...] atau [(kata, bobot), ...].
    """
    if not keywords:
        return []

    parsed: list[tuple[str, float]] = []
    for idx, item in enumerate(keywords):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            word = str(item[0]).strip()
            weight = float(item[1])
        else:
            word = str(item).strip()
            weight = max(1.0 - idx * 0.08, 0.1)
        if word:
            parsed.append((word, weight))
    return parsed


def bar_chart_sentiment(df: pd.DataFrame, title: str = "") -> go.Figure:
    """Bar chart vertikal jumlah komentar per sentimen."""
    try:
        if df is None or df.empty:
            return _empty_figure("Tidak ada data sentimen")

        counts = _count_sentiment(df)
        colors = [SENTIMENT_COLORS.get(s, PRIMARY_COLOR) for s in counts["sentiment"]]

        fig = go.Figure(
            go.Bar(
                x=counts["label"],
                y=counts["count"],
                marker_color=colors,
                text=counts["count"],
                textposition="outside",
                hovertemplate="%{x}: %{y} komentar<extra></extra>",
            )
        )
        fig.update_layout(yaxis_title="Jumlah Komentar", xaxis_title="Sentimen")
        _apply_layout(fig, title or "Distribusi Sentimen")
        return fig
    except Exception:
        return _empty_figure("Gagal memuat chart sentimen")


def pie_chart_sentiment(df: pd.DataFrame, title: str = "") -> go.Figure:
    """Donut chart persentase tiap sentimen."""
    try:
        if df is None or df.empty:
            return _empty_figure("Tidak ada data sentimen")

        counts = _count_sentiment(df)
        counts = counts[counts["count"] > 0]
        if counts.empty:
            return _empty_figure("Tidak ada data sentimen")

        colors = [SENTIMENT_COLORS.get(s, PRIMARY_COLOR) for s in counts["sentiment"]]

        fig = go.Figure(
            go.Pie(
                labels=counts["label"],
                values=counts["count"],
                hole=0.4,
                marker=dict(colors=colors),
                textinfo="label+percent",
                hovertemplate="%{label}: %{value} komentar (%{percent})<extra></extra>",
            )
        )
        _apply_layout(fig, title or "Persentase Sentimen")
        return fig
    except Exception:
        return _empty_figure("Gagal memuat donut chart sentimen")


def bar_chart_confidence(df: pd.DataFrame, title: str = "") -> go.Figure:
    """Bar chart rata-rata confidence score per sentimen (skala 0–1)."""
    try:
        if df is None or df.empty:
            return _empty_figure("Tidak ada data confidence")

        sent_col = _resolve_sentiment_col(df)
        if "confidence" not in df.columns:
            return _empty_figure("Kolom 'confidence' tidak ditemukan")

        temp = df[[sent_col, "confidence"]].copy()
        temp[sent_col] = temp[sent_col].astype(str).str.lower().str.strip()
        temp["confidence"] = pd.to_numeric(temp["confidence"], errors="coerce")
        temp = temp.dropna(subset=["confidence"])

        grouped = (
            temp.groupby(sent_col)["confidence"]
            .mean()
            .reindex(SENTIMENT_ORDER, fill_value=0)
            .reset_index()
        )
        grouped.columns = ["sentiment", "avg_confidence"]
        grouped["label"] = grouped["sentiment"].map(SENTIMENT_LABELS)
        grouped["avg_confidence"] = grouped["avg_confidence"].round(3)

        colors = [SENTIMENT_COLORS.get(s, PRIMARY_COLOR) for s in grouped["sentiment"]]

        fig = go.Figure(
            go.Bar(
                x=grouped["label"],
                y=grouped["avg_confidence"],
                marker_color=colors,
                text=grouped["avg_confidence"],
                texttemplate="%{y:.3f}",
                textposition="outside",
                hovertemplate="%{x}: %{y:.3f}<extra></extra>",
            )
        )
        fig.update_layout(
            yaxis_title="Rata-rata Confidence",
            xaxis_title="Sentimen",
            yaxis=dict(range=[0, 1]),
        )
        _apply_layout(fig, title or "Rata-rata Confidence per Sentimen")
        return fig
    except Exception:
        return _empty_figure("Gagal memuat chart confidence")


def timeline_sentiment(df: pd.DataFrame, title: str = "") -> go.Figure:
    """Line chart jumlah komentar per sentimen per tanggal."""
    try:
        if df is None or df.empty:
            return _empty_figure("Tidak ada data timeline")

        sent_col = _resolve_sentiment_col(df)
        if "date" not in df.columns:
            return _empty_figure("Kolom 'date' tidak ditemukan")

        temp = df[["date", sent_col]].copy()
        temp["date"] = pd.to_datetime(temp["date"], errors="coerce")
        temp = temp.dropna(subset=["date"])
        temp[sent_col] = temp[sent_col].astype(str).str.lower().str.strip()
        temp["tanggal"] = temp["date"].dt.date

        grouped = (
            temp.groupby(["tanggal", sent_col])
            .size()
            .reset_index(name="count")
        )

        fig = go.Figure()
        for sentiment in SENTIMENT_ORDER:
            subset = grouped[grouped[sent_col] == sentiment]
            if subset.empty:
                continue
            fig.add_trace(
                go.Scatter(
                    x=subset["tanggal"],
                    y=subset["count"],
                    mode="lines+markers",
                    name=SENTIMENT_LABELS.get(sentiment, sentiment),
                    line=dict(color=SENTIMENT_COLORS.get(sentiment, PRIMARY_COLOR)),
                    marker=dict(color=SENTIMENT_COLORS.get(sentiment, PRIMARY_COLOR)),
                    hovertemplate="%{x}<br>%{y} komentar<extra></extra>",
                )
            )

        if not fig.data:
            return _empty_figure("Tidak ada data timeline")

        fig.update_layout(
            xaxis_title="Tanggal",
            yaxis_title="Jumlah Komentar",
            hovermode="x unified",
        )
        _apply_layout(fig, title or "Tren Sentimen per Tanggal")
        return fig
    except Exception:
        return _empty_figure("Gagal memuat timeline sentimen")


def bar_chart_platform(df: pd.DataFrame, title: str = "") -> go.Figure:
    """Bar chart distribusi jumlah komentar per platform."""
    try:
        if df is None or df.empty:
            return _empty_figure("Tidak ada data platform")

        if "platform" not in df.columns:
            return _empty_figure("Kolom 'platform' tidak ditemukan")

        counts = (
            df["platform"]
            .astype(str)
            .str.lower()
            .str.strip()
            .value_counts()
            .reindex(PLATFORM_ORDER, fill_value=0)
            .reset_index()
        )
        counts.columns = ["platform", "count"]
        counts["label"] = counts["platform"].map(PLATFORM_LABELS)
        colors = [PLATFORM_COLORS.get(p, PRIMARY_COLOR) for p in counts["platform"]]

        fig = go.Figure(
            go.Bar(
                x=counts["label"],
                y=counts["count"],
                marker_color=colors,
                text=counts["count"],
                textposition="outside",
                hovertemplate="%{x}: %{y} komentar<extra></extra>",
            )
        )
        fig.update_layout(yaxis_title="Jumlah Komentar", xaxis_title="Platform")
        _apply_layout(fig, title or "Distribusi per Platform")
        return fig
    except Exception:
        return _empty_figure("Gagal memuat chart platform")


def grouped_bar_platform_sentiment(df: pd.DataFrame, title: str = "") -> go.Figure:
    """Grouped bar chart: platform (sumbu X) dikelompokkan per sentimen."""
    try:
        if df is None or df.empty:
            return _empty_figure("Tidak ada data platform-sentimen")

        sent_col = _resolve_sentiment_col(df)
        if "platform" not in df.columns:
            return _empty_figure("Kolom 'platform' tidak ditemukan")

        temp = df[["platform", sent_col]].copy()
        temp["platform"] = temp["platform"].astype(str).str.lower().str.strip()
        temp[sent_col] = temp[sent_col].astype(str).str.lower().str.strip()

        grouped = (
            temp.groupby(["platform", sent_col])
            .size()
            .reset_index(name="count")
        )

        fig = go.Figure()
        for sentiment in SENTIMENT_ORDER:
            subset = grouped[grouped[sent_col] == sentiment]
            if subset.empty:
                continue
            fig.add_trace(
                go.Bar(
                    x=subset["platform"].map(PLATFORM_LABELS),
                    y=subset["count"],
                    name=SENTIMENT_LABELS.get(sentiment, sentiment),
                    marker_color=SENTIMENT_COLORS.get(sentiment, PRIMARY_COLOR),
                    text=subset["count"],
                    textposition="outside",
                    hovertemplate="%{x} — %{fullData.name}: %{y}<extra></extra>",
                )
            )

        if not fig.data:
            return _empty_figure("Tidak ada data platform-sentimen")

        fig.update_layout(
            barmode="group",
            xaxis_title="Platform",
            yaxis_title="Jumlah Komentar",
        )
        _apply_layout(fig, title or "Platform per Sentimen")
        return fig
    except Exception:
        return _empty_figure("Gagal memuat grouped bar platform-sentimen")


def scatter_followers_degree(df_nodes: pd.DataFrame, title: str = "") -> go.Figure:
    """Scatter plot degree centrality (X) vs followers (Y), warna per platform."""
    try:
        if df_nodes is None or df_nodes.empty:
            return _empty_figure("Tidak ada data node SNA")

        degree_col = None
        for candidate in ("degree_centrality", "degree"):
            if candidate in df_nodes.columns:
                degree_col = candidate
                break
        if degree_col is None:
            return _empty_figure("Kolom 'degree_centrality' tidak ditemukan")

        required = ["followers", "username", "platform"]
        missing = [c for c in required if c not in df_nodes.columns]
        if missing:
            return _empty_figure(f"Kolom tidak ditemukan: {', '.join(missing)}")

        temp = df_nodes.copy()
        temp["platform"] = temp["platform"].astype(str).str.lower().str.strip()
        temp["followers"] = pd.to_numeric(temp["followers"], errors="coerce")
        temp[degree_col] = pd.to_numeric(temp[degree_col], errors="coerce")
        temp = temp.dropna(subset=["followers", degree_col])

        fig = go.Figure()
        for platform in PLATFORM_ORDER:
            subset = temp[temp["platform"] == platform]
            if subset.empty:
                continue
            fig.add_trace(
                go.Scatter(
                    x=subset[degree_col],
                    y=subset["followers"],
                    mode="markers",
                    name=PLATFORM_LABELS.get(platform, platform),
                    marker=dict(
                        color=PLATFORM_COLORS.get(platform, PRIMARY_COLOR),
                        size=10,
                        opacity=0.8,
                    ),
                    text=subset["username"],
                    customdata=subset[["username", "platform", "followers"]],
                    hovertemplate=(
                        "Username: %{customdata[0]}<br>"
                        "Platform: %{customdata[1]}<br>"
                        "Followers: %{customdata[2]:,}<br>"
                        "Degree: %{x:.4f}<extra></extra>"
                    ),
                )
            )

        if not fig.data:
            return _empty_figure("Tidak ada data scatter")

        fig.update_layout(
            xaxis_title="Degree Centrality",
            yaxis_title="Followers",
        )
        _apply_layout(fig, title or "Followers vs Degree Centrality")
        return fig
    except Exception:
        return _empty_figure("Gagal memuat scatter followers-degree")


def bar_chart_top_words(top_words: list, sentimen: str, title: str = "") -> go.Figure:
    """Horizontal bar chart top 15 kata terbanyak."""
    try:
        if not top_words:
            return _empty_figure("Tidak ada kata kunci")

        top = list(top_words)[:15]
        labels = [str(item[0]) for item in top]
        values = [float(item[1]) for item in top]
        color = SENTIMENT_COLORS.get(str(sentimen).lower().strip(), PRIMARY_COLOR)

        fig = go.Figure(
            go.Bar(
                x=values,
                y=labels,
                orientation="h",
                marker_color=color,
                text=values,
                textposition="outside",
                hovertemplate="%{y}: %{x}<extra></extra>",
            )
        )
        fig.update_layout(
            xaxis_title="Frekuensi",
            yaxis=dict(autorange="reversed"),
            height=max(320, len(labels) * 28),
        )
        sentimen_label = SENTIMENT_LABELS.get(str(sentimen).lower().strip(), sentimen)
        _apply_layout(fig, title or f"Top 15 Kata — {sentimen_label}")
        return fig
    except Exception:
        return _empty_figure("Gagal memuat chart top words")


def heatmap_topics(topics_data: list, title: str = "") -> go.Figure:
    """
    Heatmap hasil LDA Topic Modeling.

    Input topics_data: [{"label": str, "keywords": [str] | [(kata, bobot), ...]}]
    Baris = topik, kolom = peringkat kata (1, 2, 3, ...).
    """
    try:
        if not topics_data:
            return _empty_figure("Tidak ada data topik LDA")

        topic_labels: list[str] = []
        z_matrix: list[list[float]] = []
        text_matrix: list[list[str]] = []

        max_words = 0
        parsed_topics: list[tuple[str, list[tuple[str, float]]]] = []
        for topic in topics_data:
            label = str(topic.get("label", "Topik"))
            keywords = _parse_keyword_weights(topic.get("keywords", []))
            if not keywords:
                continue
            parsed_topics.append((label, keywords))
            max_words = max(max_words, len(keywords))

        if not parsed_topics or max_words == 0:
            return _empty_figure("Tidak ada kata kunci topik")

        x_labels = [f"#{i + 1}" for i in range(max_words)]

        for label, keywords in parsed_topics:
            topic_labels.append(label)
            weights = [kw[1] for kw in keywords]
            words = [kw[0] for kw in keywords]
            padded_weights = weights + [0.0] * (max_words - len(weights))
            padded_words = words + [""] * (max_words - len(words))
            z_matrix.append(padded_weights)
            text_matrix.append(padded_words)

        fig = go.Figure(
            go.Heatmap(
                z=z_matrix,
                x=x_labels,
                y=topic_labels,
                text=text_matrix,
                texttemplate="%{text}",
                textfont=dict(size=11),
                colorscale=[
                    [0.0, "rgba(29,161,242,0.15)"],
                    [0.5, "rgba(29,161,242,0.55)"],
                    [1.0, "rgba(13,71,161,0.95)"],
                ],
                hovertemplate="Topik: %{y}<br>Peringkat: %{x}<br>Kata: %{text}<br>Bobot: %{z:.3f}<extra></extra>",
                colorbar=dict(title="Bobot"),
            )
        )
        fig.update_layout(
            xaxis_title="Peringkat Kata",
            yaxis_title="Topik",
        )
        _apply_layout(fig, title or "Heatmap Topik LDA")
        return fig
    except Exception:
        return _empty_figure("Gagal memuat heatmap topik")


def gauge_confidence(score: float, label: str) -> go.Figure:
    """Gauge chart confidence score prediksi manual (rentang 0–1)."""
    try:
        value = float(score)
        value = max(0.0, min(1.0, value))

        if value < 0.5:
            bar_color = _GAUGE_RED
        elif value < 0.75:
            bar_color = _GAUGE_YELLOW
        else:
            bar_color = _GAUGE_GREEN

        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=value,
                number={"suffix": "", "font": {"size": 36}},
                title={"text": label, "font": {"size": 16}},
                gauge={
                    "axis": {"range": [0, 1], "tickwidth": 1},
                    "bar": {"color": bar_color},
                    "bgcolor": "rgba(0,0,0,0)",
                    "steps": [
                        {"range": [0, 0.5], "color": "rgba(244,67,54,0.15)"},
                        {"range": [0.5, 0.75], "color": "rgba(255,193,7,0.15)"},
                        {"range": [0.75, 1.0], "color": "rgba(76,175,80,0.15)"},
                    ],
                    "threshold": {
                        "line": {"color": ACCENT_COLOR, "width": 3},
                        "thickness": 0.8,
                        "value": value,
                    },
                },
            )
        )
        _apply_layout(fig)
        return fig
    except Exception:
        return _empty_figure("Gagal memuat gauge confidence")
