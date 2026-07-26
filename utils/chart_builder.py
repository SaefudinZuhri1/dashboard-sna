"""Builder chart Plotly reusable untuk dashboard analitik Telkom Group.

Modul ini berisi fungsi-fungsi pembuat grafik yang aman dipakai ulang oleh
halaman Streamlit. Semua grafik memakai background transparan supaya menyatu
dengan tema gelap dashboard, serta mengembalikan figure kosong jika data atau
kolom belum tersedia agar aplikasi tidak crash.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go

try:
    import streamlit as st
except Exception:  # pragma: no cover - fallback saat utilitas diuji tanpa Streamlit
    st = None



def _cache_data_safe(**kwargs):
    """Gunakan cache Streamlit saat tersedia, atau identity decorator saat test."""
    if st is None:
        return lambda function: function
    return st.cache_data(**kwargs)

# -----------------------------------------------------------------------------
# Konstanta warna dan label dashboard
# -----------------------------------------------------------------------------
COLORS = {
    "positive": "#4CAF50",
    "neutral": "#FF9800",
    "negative": "#F44336",
    "twitter": "#1DA1F2",
    "instagram": "#833AB4",
    "tiktok": "#E53935",
    "primary": "#E53935",
    "secondary": "#FF5252",
    "primary_dark": "#B71C1C",
    "bg_main": "#0D0D0D",
    "bg_card": "#1A1A1A",
    "bg_app": "#0B0F17",
    "border": "#2A2A2A",
    "border_soft": "#2A3648",
    "text": "#FFFFFF",
    "text_soft": "#F8FAFC",
    "muted": "#AAAAAA",
    "muted_soft": "#A7B0BF",
}

SENTIMENT_COLORS = {
    "positive": COLORS["positive"],
    "neutral": COLORS["neutral"],
    "negative": COLORS["negative"],
}

PLATFORM_COLORS = {
    "twitter": COLORS["twitter"],
    "x": COLORS["twitter"],
    "instagram": COLORS["instagram"],
    "tiktok": COLORS["tiktok"],
}

PRIMARY_COLOR = COLORS["primary"]
ACCENT_COLOR = COLORS["primary"]
FONT_FAMILY = "Plus Jakarta Sans, Syne, DM Sans, sans-serif"

SENTIMENT_ORDER = ["positive", "neutral", "negative"]
SENTIMENT_LABELS = {
    "positive": "Positif",
    "positif": "Positif",
    "neutral": "Netral",
    "netral": "Netral",
    "negative": "Negatif",
    "negatif": "Negatif",
}

_SENTIMENT_NORMALISATION = {
    "positive": "positive",
    "positif": "positive",
    "pos": "positive",
    "label_0": "positive",
    "neutral": "neutral",
    "netral": "neutral",
    "neu": "neutral",
    "label_1": "neutral",
    "negative": "negative",
    "negatif": "negative",
    "neg": "negative",
    "label_2": "negative",
}

PLATFORM_ORDER = ["twitter", "instagram", "tiktok"]
PLATFORM_LABELS = {
    "twitter": "Twitter/X",
    "x": "Twitter/X",
    "instagram": "Instagram",
    "tiktok": "TikTok",
}

_PLATFORM_NORMALISATION = {
    "twitter": "twitter",
    "x": "twitter",
    "twitter/x": "twitter",
    "instagram": "instagram",
    "ig": "instagram",
    "tiktok": "tiktok",
    "tik tok": "tiktok",
    "tik-tok": "tiktok",
}

_DATE_COLUMNS = ("date", "date_created", "created_at", "tanggal", "waktu", "timestamp")
_SENTIMENT_COLUMNS = ("predicted_sentiment", "sentiment", "label", "sentimen", "hasil_sentimen")
_PLATFORM_COLUMNS = ("platform", "source_platform", "media", "sumber_platform")

_GAUGE_RED = COLORS["negative"]
_GAUGE_YELLOW = "#FFC107"
_GAUGE_GREEN = COLORS["positive"]


# -----------------------------------------------------------------------------
# Helper aman untuk tema dan data
# -----------------------------------------------------------------------------
def _show_error(message: str, exc: Exception | None = None) -> None:
    """Tampilkan pesan error Streamlit tanpa memaksa modul bergantung pada UI."""
    try:
        if st is not None:
            detail = f" Detail: {exc}" if exc else ""
            st.error(f"{message}{detail}")
    except Exception:
        # Jika Streamlit belum siap, abaikan agar fungsi tetap mengembalikan figure.
        pass


def _is_dark_mode() -> bool:
    """Ambil status mode gelap dari session Streamlit secara aman."""
    try:
        if st is None:
            return True
        return bool(st.session_state.get("dark_mode", True))
    except Exception:
        return True


def _chart_theme() -> dict[str, str]:
    """Siapkan warna chart sesuai mode dashboard saat ini."""
    if _is_dark_mode():
        return {
            "template": "plotly_dark",
            "text": COLORS["text_soft"],
            "muted": COLORS["muted_soft"],
            "grid": "rgba(42,54,72,0.74)",
            "axis": "rgba(167,176,191,0.28)",
            "legend_bg": "rgba(26,26,26,0.82)",
            "hover_bg": "#151B26",
            "hover_border": "rgba(229,57,53,0.36)",
        }
    return {
        "template": "plotly_white",
        "text": "#1F2937",
        "muted": "#64748B",
        "grid": "rgba(100,116,139,0.18)",
        "axis": "rgba(100,116,139,0.28)",
        "legend_bg": "rgba(255,255,255,0.86)",
        "hover_bg": "#FFFFFF",
        "hover_border": "rgba(229,57,53,0.28)",
    }


def _apply_layout(
    fig: go.Figure,
    title: str = "",
    *,
    height: int | None = None,
    show_legend: bool = True,
    x_grid: bool = False,
    y_grid: bool = True,
) -> go.Figure:
    """Terapkan layout Plotly transparan dan konsisten di seluruh dashboard."""
    try:
        theme = _chart_theme()
        layout_kwargs: dict[str, Any] = {
            "template": theme["template"],
            "font": {"family": FONT_FAMILY, "color": theme["text"]},
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "uirevision": "telkom-dashboard-v18",
            "margin": {"l": 42, "r": 24, "t": 58 if title else 24, "b": 44},
            "hoverlabel": {
                "bgcolor": theme["hover_bg"],
                "bordercolor": theme["hover_border"],
                "font": {"family": FONT_FAMILY, "color": theme["text"]},
            },
            "legend": {
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
                "bgcolor": theme["legend_bg"],
                "bordercolor": COLORS["border"],
                "borderwidth": 1,
                "font": {"color": theme["text"], "size": 12},
                "visible": show_legend,
            },
        }
        if title:
            layout_kwargs["title"] = {
                "text": title,
                "x": 0.0,
                "xanchor": "left",
                "font": {"family": FONT_FAMILY, "color": theme["text"], "size": 17},
            }
        if height:
            layout_kwargs["height"] = height

        fig.update_layout(**layout_kwargs)
        fig.update_xaxes(
            showgrid=x_grid,
            gridcolor=theme["grid"],
            zeroline=False,
            tickcolor=theme["muted"],
            color=theme["muted"],
            linecolor=theme["axis"],
            title_font={"color": theme["muted"], "family": FONT_FAMILY},
            tickfont={"color": theme["muted"], "family": FONT_FAMILY},
        )
        fig.update_yaxes(
            showgrid=y_grid,
            gridcolor=theme["grid"],
            zeroline=False,
            tickcolor=theme["muted"],
            color=theme["muted"],
            linecolor=theme["axis"],
            title_font={"color": theme["muted"], "family": FONT_FAMILY},
            tickfont={"color": theme["muted"], "family": FONT_FAMILY},
        )
        fig.update_traces(textfont={"family": FONT_FAMILY}, selector=dict(type="bar"))
        fig.update_traces(textfont={"family": FONT_FAMILY, "color": "#FFFFFF"}, selector=dict(type="pie"))
        return fig
    except Exception as exc:
        _show_error("Gaya chart belum dapat diterapkan.", exc)
        return fig


def _empty_figure(message: str = "Data tidak tersedia", title: str = "", height: int = 360) -> go.Figure:
    """Kembalikan figure kosong dengan pesan yang mudah dipahami."""
    fig = go.Figure()
    try:
        fig.add_annotation(
            text=message,
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"family": FONT_FAMILY, "size": 14, "color": COLORS["muted"]},
        )
        return _apply_layout(fig, title, height=height, show_legend=False)
    except Exception:
        return fig


def _first_existing_column(df: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    """Cari nama kolom pertama yang tersedia dari daftar kandidat."""
    try:
        lower_map = {str(col).lower(): col for col in df.columns}
        for candidate in candidates:
            if candidate in df.columns:
                return candidate
            if candidate.lower() in lower_map:
                return str(lower_map[candidate.lower()])
        return None
    except Exception:
        return None


def _resolve_sentiment_col(df: pd.DataFrame) -> str:
    """Temukan kolom sentimen pada DataFrame."""
    col = _first_existing_column(df, _SENTIMENT_COLUMNS)
    if col:
        return col
    raise KeyError("Kolom sentimen tidak ditemukan.")


def _resolve_platform_col(df: pd.DataFrame) -> str:
    """Temukan kolom platform pada DataFrame."""
    col = _first_existing_column(df, _PLATFORM_COLUMNS)
    if col:
        return col
    raise KeyError("Kolom platform tidak ditemukan.")


def _resolve_date_col(df: pd.DataFrame) -> str:
    """Temukan kolom tanggal pada DataFrame."""
    col = _first_existing_column(df, _DATE_COLUMNS)
    if col:
        return col
    raise KeyError("Kolom tanggal tidak ditemukan.")


def _normalise_sentiment(value: Any) -> str:
    """Normalisasi nilai sentimen ke positive, neutral, atau negative."""
    key = str(value or "").strip().lower()
    return _SENTIMENT_NORMALISATION.get(key, key)


def _normalise_platform(value: Any) -> str:
    """Normalisasi nilai platform ke twitter, instagram, atau tiktok."""
    key = str(value or "").strip().lower()
    return _PLATFORM_NORMALISATION.get(key, key)


@_cache_data_safe(show_spinner=False, max_entries=64)
def _count_sentiment(df: pd.DataFrame) -> pd.DataFrame:
    """Hitung jumlah komentar per sentimen dengan urutan tetap."""
    sent_col = _resolve_sentiment_col(df)
    temp = df[[sent_col]].copy()
    temp["sentiment"] = temp[sent_col].map(_normalise_sentiment)
    counts = (
        temp["sentiment"]
        .value_counts()
        .reindex(SENTIMENT_ORDER, fill_value=0)
        .reset_index()
    )
    counts.columns = ["sentiment", "count"]
    counts["label"] = counts["sentiment"].map(SENTIMENT_LABELS)
    counts["color"] = counts["sentiment"].map(SENTIMENT_COLORS)
    return counts


@_cache_data_safe(show_spinner=False, max_entries=64)
def _coerce_words(words_data: Any) -> pd.DataFrame:
    """Ubah input kata/frekuensi menjadi DataFrame standar."""
    try:
        if words_data is None:
            return pd.DataFrame(columns=["word", "value"])

        if isinstance(words_data, pd.DataFrame):
            word_col = _first_existing_column(words_data, ("word", "kata", "term", "keyword"))
            value_col = _first_existing_column(words_data, ("value", "count", "frequency", "frekuensi", "jumlah"))
            if word_col and value_col:
                result = words_data[[word_col, value_col]].copy()
                result.columns = ["word", "value"]
            else:
                result = words_data.reset_index().iloc[:, :2].copy()
                result.columns = ["word", "value"]
        elif isinstance(words_data, dict):
            result = pd.DataFrame(list(words_data.items()), columns=["word", "value"])
        else:
            result = pd.DataFrame(list(words_data), columns=["word", "value"])

        result["word"] = result["word"].astype(str).str.strip()
        result["value"] = pd.to_numeric(result["value"], errors="coerce")
        result = result.dropna(subset=["value"])
        result = result[result["word"].ne("")]
        result = result.sort_values("value", ascending=False).head(15)
        return result
    except Exception as exc:
        _show_error("Data kata belum dapat dibaca.", exc)
        return pd.DataFrame(columns=["word", "value"])


@_cache_data_safe(show_spinner=False, max_entries=64)
def _parse_keyword_weights(keywords: list[Any]) -> list[tuple[str, float]]:
    """Ubah daftar kata kunci menjadi pasangan (kata, bobot)."""
    if not keywords:
        return []

    parsed: list[tuple[str, float]] = []
    for idx, item in enumerate(keywords):
        try:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                word = str(item[0]).strip()
                weight = float(item[1])
            else:
                word = str(item).strip()
                weight = max(1.0 - idx * 0.08, 0.1)
            if word:
                parsed.append((word, weight))
        except Exception:
            continue
    return parsed


def _format_metric_name(name: str) -> str:
    """Ubah nama kolom metrik menjadi label yang enak dibaca."""
    label_map = {
        "degree_centrality": "Degree Centrality",
        "degree": "Degree",
        "in_degree": "In-Degree",
        "out_degree": "Out-Degree",
        "followers": "Followers",
        "density": "Density",
        "average_degree": "Average Degree",
        "avg_degree": "Average Degree",
        "node_count": "Jumlah Node",
        "nodes": "Jumlah Node",
        "edge_count": "Jumlah Edge",
        "edges": "Jumlah Edge",
    }
    return label_map.get(name, str(name).replace("_", " ").title())


# -----------------------------------------------------------------------------
# Fungsi wajib Fase 13
# -----------------------------------------------------------------------------
def create_sentiment_pie(df: pd.DataFrame, title: str = "Persentase Sentimen") -> go.Figure:
    """Buat donut chart persentase sentimen positif, netral, dan negatif."""
    try:
        if df is None or df.empty:
            return _empty_figure("Data sentimen belum tersedia", title)

        # Hitung sentimen, lalu buang kategori bernilai nol agar donut tidak penuh label kosong.
        counts = _count_sentiment(df)
        visible_counts = counts[counts["count"] > 0].copy()
        if visible_counts.empty:
            return _empty_figure("Data sentimen belum tersedia", title)

        # Tentukan sentimen dominan untuk teks di tengah donut.
        dominant_row = visible_counts.sort_values("count", ascending=False).iloc[0]
        total = int(visible_counts["count"].sum())
        dominant_pct = (float(dominant_row["count"]) / total * 100) if total else 0.0

        fig = go.Figure(
            go.Pie(
                labels=visible_counts["label"],
                values=visible_counts["count"],
                hole=0.66,
                sort=False,
                direction="clockwise",
                marker={
                    "colors": visible_counts["color"],
                    "line": {"color": "rgba(13,13,13,0.88)", "width": 3},
                },
                textinfo="percent",
                textposition="inside",
                hovertemplate=(
                    "<b>%{label}</b><br>Jumlah: %{value:,} komentar<br>Persentase: %{percent}<extra></extra>"
                ),
            )
        )
        fig.add_annotation(
            text=f"<b>{dominant_row['label']}</b><br><span style='font-size:12px'>{dominant_pct:.1f}% dominan</span>",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={
                "family": FONT_FAMILY,
                "size": 17,
                "color": SENTIMENT_COLORS.get(str(dominant_row["sentiment"]), PRIMARY_COLOR),
            },
        )
        return _apply_layout(fig, title, height=390, show_legend=True)
    except Exception as exc:
        _show_error("Donut chart sentimen gagal dibuat.", exc)
        return _empty_figure("Donut chart sentimen gagal dibuat", title)


def create_sentiment_bar(df: pd.DataFrame, title: str = "Sentimen per Platform") -> go.Figure:
    """Buat grouped bar chart sentimen per platform media sosial."""
    try:
        if df is None or df.empty:
            return _empty_figure("Data platform dan sentimen belum tersedia", title)

        # Ambil kolom penting secara defensif agar mendukung beberapa versi dataset.
        sent_col = _resolve_sentiment_col(df)
        platform_col = _resolve_platform_col(df)
        temp = df[[platform_col, sent_col]].copy()
        temp["platform"] = temp[platform_col].map(_normalise_platform)
        temp["sentiment"] = temp[sent_col].map(_normalise_sentiment)
        temp = temp[temp["sentiment"].isin(SENTIMENT_ORDER)]

        if temp.empty:
            return _empty_figure("Data platform dan sentimen belum tersedia", title)

        grouped = temp.groupby(["platform", "sentiment"], dropna=False).size().reset_index(name="count")
        platform_order = [item for item in PLATFORM_ORDER if item in set(grouped["platform"])]
        platform_order.extend([item for item in grouped["platform"].unique() if item not in platform_order])
        x_labels = [PLATFORM_LABELS.get(item, str(item).title()) for item in platform_order]

        fig = go.Figure()
        for sentiment in SENTIMENT_ORDER:
            values: list[int] = []
            for platform in platform_order:
                subset = grouped[(grouped["platform"] == platform) & (grouped["sentiment"] == sentiment)]
                values.append(int(subset["count"].iloc[0]) if not subset.empty else 0)

            fig.add_trace(
                go.Bar(
                    x=x_labels,
                    y=values,
                    name=SENTIMENT_LABELS.get(sentiment, sentiment.title()),
                    marker={"color": SENTIMENT_COLORS.get(sentiment, PRIMARY_COLOR), "line": {"width": 0}},
                    text=[f"{value:,}" if value else "" for value in values],
                    textposition="outside",
                    cliponaxis=False,
                    hovertemplate=(
                        "%{x}<br>Sentimen: "
                        + SENTIMENT_LABELS.get(sentiment, sentiment.title())
                        + "<br>Jumlah: %{y:,}<extra></extra>"
                    ),
                )
            )

        fig.update_layout(
            barmode="group",
            bargap=0.28,
            bargroupgap=0.08,
            xaxis_title="Platform",
            yaxis_title="Jumlah Komentar",
        )
        return _apply_layout(fig, title, height=410, show_legend=True)
    except Exception as exc:
        _show_error("Grouped bar chart sentimen gagal dibuat.", exc)
        return _empty_figure("Grouped bar chart sentimen gagal dibuat", title)


def create_trend_line(df: pd.DataFrame, title: str = "Tren Sentimen dari Waktu ke Waktu") -> go.Figure:
    """Buat line chart tren sentimen berdasarkan tanggal."""
    try:
        if df is None or df.empty:
            return _empty_figure("Data tren waktu belum tersedia", title, height=410)

        # Konversi tanggal dan sentimen dengan aman.
        sent_col = _resolve_sentiment_col(df)
        date_col = _resolve_date_col(df)
        temp = df[[date_col, sent_col]].copy()
        temp["date"] = pd.to_datetime(temp[date_col], errors="coerce")
        temp["sentiment"] = temp[sent_col].map(_normalise_sentiment)
        temp = temp.dropna(subset=["date"])
        temp = temp[temp["sentiment"].isin(SENTIMENT_ORDER)]
        if temp.empty:
            return _empty_figure("Data tren waktu belum tersedia", title, height=410)

        temp["tanggal"] = temp["date"].dt.normalize()
        daily = temp.groupby(["tanggal", "sentiment"]).size().unstack(fill_value=0).sort_index()
        if daily.empty:
            return _empty_figure("Data tren waktu belum tersedia", title, height=410)

        # Lengkapi tanggal kosong supaya garis tren terlihat kontinu.
        full_range = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
        daily = daily.reindex(full_range, fill_value=0)

        fig = go.Figure()
        for sentiment in SENTIMENT_ORDER:
            values = daily[sentiment] if sentiment in daily.columns else pd.Series(0, index=daily.index)
            fig.add_trace(
                go.Scatter(
                    x=daily.index,
                    y=values,
                    name=SENTIMENT_LABELS.get(sentiment, sentiment.title()),
                    mode="lines+markers",
                    line={"color": SENTIMENT_COLORS.get(sentiment, PRIMARY_COLOR), "width": 2.8},
                    marker={
                        "size": 7,
                        "color": SENTIMENT_COLORS.get(sentiment, PRIMARY_COLOR),
                        "line": {"color": "rgba(13,13,13,0.92)", "width": 1},
                    },
                    hovertemplate=(
                        "%{x|%d %b %Y}<br>"
                        + SENTIMENT_LABELS.get(sentiment, sentiment.title())
                        + ": %{y:,} komentar<extra></extra>"
                    ),
                )
            )

        fig.update_layout(
            hovermode="x unified",
            xaxis_title="Tanggal",
            yaxis_title="Jumlah Komentar",
        )
        fig.update_xaxes(tickformat="%d %b")
        return _apply_layout(fig, title, height=430, show_legend=True)
    except Exception as exc:
        _show_error("Line chart tren sentimen gagal dibuat.", exc)
        return _empty_figure("Line chart tren sentimen gagal dibuat", title, height=410)


def create_top_words_bar(words_dict: Any, sentiment: str, title: str = "Top Kata Dominan") -> go.Figure:
    """Buat horizontal bar chart kata paling sering muncul sesuai sentimen."""
    try:
        words_df = _coerce_words(words_dict)
        if words_df.empty:
            return _empty_figure("Kata dominan belum tersedia", title)

        # Urutan dibalik agar kata terbesar muncul di bagian paling atas chart horizontal.
        plot_df = words_df.sort_values("value", ascending=True)
        sentiment_key = _normalise_sentiment(sentiment)
        bar_color = SENTIMENT_COLORS.get(sentiment_key, PRIMARY_COLOR)

        fig = go.Figure(
            go.Bar(
                x=plot_df["value"],
                y=plot_df["word"],
                orientation="h",
                marker={"color": bar_color, "line": {"color": "rgba(255,255,255,0.12)", "width": 1}},
                text=[f"{value:g}" for value in plot_df["value"]],
                textposition="outside",
                cliponaxis=False,
                hovertemplate="Kata: %{y}<br>Frekuensi: %{x}<extra></extra>",
            )
        )
        fig.update_layout(
            xaxis_title="Frekuensi",
            yaxis_title="Kata",
            height=max(340, len(plot_df) * 32 + 130),
            showlegend=False,
        )
        return _apply_layout(fig, title, show_legend=False, x_grid=True, y_grid=False)
    except Exception as exc:
        _show_error("Bar chart kata dominan gagal dibuat.", exc)
        return _empty_figure("Bar chart kata dominan gagal dibuat", title)


def create_network_stats_bar(df: pd.DataFrame, title: str = "Metrik Jaringan Sosial") -> go.Figure:
    """Buat bar chart metrik jaringan sosial seperti degree dan centrality."""
    try:
        if df is None or df.empty:
            return _empty_figure("Data metrik jaringan belum tersedia", title)

        metric_df: pd.DataFrame
        lower_cols = {str(col).lower(): col for col in df.columns}

        # Format 1: DataFrame sudah berbentuk metric-value.
        metric_col = lower_cols.get("metric") or lower_cols.get("metrik") or lower_cols.get("indikator")
        value_col = lower_cols.get("value") or lower_cols.get("nilai") or lower_cols.get("count") or lower_cols.get("jumlah")
        if metric_col and value_col:
            metric_df = df[[metric_col, value_col]].copy()
            metric_df.columns = ["metric", "value"]
        else:
            # Format 2: DataFrame berisi banyak kolom numerik; ambil kandidat utama.
            candidates = [
                "degree_centrality",
                "degree",
                "in_degree",
                "out_degree",
                "followers",
                "density",
                "average_degree",
                "avg_degree",
                "node_count",
                "nodes",
                "edge_count",
                "edges",
            ]
            rows: list[dict[str, Any]] = []
            for col in candidates:
                actual_col = lower_cols.get(col)
                if not actual_col:
                    continue
                values = pd.to_numeric(df[actual_col], errors="coerce").dropna()
                if values.empty:
                    continue
                if len(df) == 1 or col in {"density", "average_degree", "avg_degree", "node_count", "nodes", "edge_count", "edges"}:
                    value = float(values.iloc[0])
                elif col == "followers":
                    value = float(values.max())
                else:
                    value = float(values.mean())
                rows.append({"metric": _format_metric_name(col), "value": value})
            metric_df = pd.DataFrame(rows)

        if metric_df.empty:
            return _empty_figure("Kolom metrik jaringan belum ditemukan", title)

        metric_df["value"] = pd.to_numeric(metric_df["value"], errors="coerce")
        metric_df = metric_df.dropna(subset=["value"])
        metric_df["metric"] = metric_df["metric"].astype(str).map(_format_metric_name)
        if metric_df.empty:
            return _empty_figure("Nilai metrik jaringan belum valid", title)

        fig = go.Figure(
            go.Bar(
                x=metric_df["metric"],
                y=metric_df["value"],
                marker={
                    "color": PRIMARY_COLOR,
                    "line": {"color": COLORS["secondary"], "width": 1},
                },
                text=[f"{value:,.3f}" if abs(value) < 10 else f"{value:,.0f}" for value in metric_df["value"]],
                textposition="outside",
                cliponaxis=False,
                hovertemplate="Metrik: %{x}<br>Nilai: %{y}<extra></extra>",
            )
        )
        fig.update_layout(
            xaxis_title="Metrik",
            yaxis_title="Nilai",
            bargap=0.28,
            showlegend=False,
        )
        return _apply_layout(fig, title, height=390, show_legend=False)
    except Exception as exc:
        _show_error("Bar chart metrik jaringan gagal dibuat.", exc)
        return _empty_figure("Bar chart metrik jaringan gagal dibuat", title)


def create_heatmap(matrix_df: pd.DataFrame, title: str = "Heatmap") -> go.Figure:
    """Buat heatmap Plotly dengan colorscale yang cocok untuk background gelap."""
    try:
        if matrix_df is None or matrix_df.empty:
            return _empty_figure("Data heatmap belum tersedia", title, height=390)

        # Pastikan seluruh isi heatmap berupa angka agar Plotly tidak error.
        matrix = matrix_df.copy()
        numeric_matrix = matrix.apply(pd.to_numeric, errors="coerce").fillna(0)
        if numeric_matrix.empty:
            return _empty_figure("Data heatmap belum tersedia", title, height=390)

        z_values = numeric_matrix.to_numpy(dtype=float)
        x_labels = [str(item) for item in numeric_matrix.columns]
        y_labels = [str(item) for item in numeric_matrix.index]

        fig = go.Figure(
            go.Heatmap(
                z=z_values,
                x=x_labels,
                y=y_labels,
                colorscale=[
                    [0.0, "rgba(229,57,53,0.08)"],
                    [0.30, "rgba(229,57,53,0.32)"],
                    [0.65, "rgba(255,82,82,0.72)"],
                    [1.0, "rgba(255,176,32,0.96)"],
                ],
                hovertemplate="Baris: %{y}<br>Kolom: %{x}<br>Nilai: %{z}<extra></extra>",
                colorbar={
                    "title": "Nilai",
                    "tickfont": {"color": _chart_theme()["muted"]},
                    "titlefont": {"color": _chart_theme()["muted"]},
                },
                xgap=2,
                ygap=2,
            )
        )
        fig.update_layout(xaxis_title="Kolom", yaxis_title="Baris")
        return _apply_layout(fig, title, height=max(390, len(y_labels) * 42 + 160), show_legend=False, x_grid=False, y_grid=False)
    except Exception as exc:
        _show_error("Heatmap gagal dibuat.", exc)
        return _empty_figure("Heatmap gagal dibuat", title, height=390)


# -----------------------------------------------------------------------------
# Fungsi lama tetap dipertahankan agar halaman sebelumnya tidak rusak
# -----------------------------------------------------------------------------
def bar_chart_sentiment(df: pd.DataFrame, title: str = "Distribusi Sentimen") -> go.Figure:
    """Buat bar chart vertikal jumlah komentar per sentimen."""
    try:
        if df is None or df.empty:
            return _empty_figure("Data sentimen belum tersedia", title)

        counts = _count_sentiment(df)
        fig = go.Figure(
            go.Bar(
                x=counts["label"],
                y=counts["count"],
                marker={"color": counts["color"], "line": {"width": 0}},
                text=[f"{value:,}" if value else "" for value in counts["count"]],
                textposition="outside",
                cliponaxis=False,
                hovertemplate="Sentimen: %{x}<br>Jumlah: %{y:,}<extra></extra>",
            )
        )
        fig.update_layout(xaxis_title="Sentimen", yaxis_title="Jumlah Komentar", showlegend=False)
        return _apply_layout(fig, title, height=380, show_legend=False)
    except Exception as exc:
        _show_error("Bar chart sentimen gagal dibuat.", exc)
        return _empty_figure("Bar chart sentimen gagal dibuat", title)


def pie_chart_sentiment(df: pd.DataFrame, title: str = "Persentase Sentimen") -> go.Figure:
    """Buat donut chart persentase sentimen."""
    return create_sentiment_pie(df, title)


def bar_chart_confidence(df: pd.DataFrame, title: str = "Rata-rata Confidence per Sentimen") -> go.Figure:
    """Buat bar chart rata-rata confidence score per sentimen."""
    try:
        if df is None or df.empty:
            return _empty_figure("Data confidence belum tersedia", title)

        sent_col = _resolve_sentiment_col(df)
        confidence_col = _first_existing_column(df, ("confidence", "score", "probability", "probabilitas"))
        if not confidence_col:
            return _empty_figure("Kolom confidence belum tersedia", title)

        temp = df[[sent_col, confidence_col]].copy()
        temp["sentiment"] = temp[sent_col].map(_normalise_sentiment)
        temp["confidence"] = pd.to_numeric(temp[confidence_col], errors="coerce")
        temp = temp.dropna(subset=["confidence"])
        temp = temp[temp["sentiment"].isin(SENTIMENT_ORDER)]
        if temp.empty:
            return _empty_figure("Data confidence belum tersedia", title)

        grouped = temp.groupby("sentiment")["confidence"].mean().reindex(SENTIMENT_ORDER, fill_value=0).reset_index()
        grouped["label"] = grouped["sentiment"].map(SENTIMENT_LABELS)
        grouped["color"] = grouped["sentiment"].map(SENTIMENT_COLORS)

        fig = go.Figure(
            go.Bar(
                x=grouped["label"],
                y=grouped["confidence"],
                marker={"color": grouped["color"], "line": {"width": 0}},
                text=[f"{value:.3f}" if value else "" for value in grouped["confidence"]],
                textposition="outside",
                cliponaxis=False,
                hovertemplate="Sentimen: %{x}<br>Rata-rata confidence: %{y:.3f}<extra></extra>",
            )
        )
        fig.update_layout(xaxis_title="Sentimen", yaxis_title="Rata-rata Confidence", showlegend=False)
        fig.update_yaxes(range=[0, 1])
        return _apply_layout(fig, title, height=380, show_legend=False)
    except Exception as exc:
        _show_error("Bar chart confidence gagal dibuat.", exc)
        return _empty_figure("Bar chart confidence gagal dibuat", title)


def timeline_sentiment(df: pd.DataFrame, title: str = "Tren Sentimen per Tanggal") -> go.Figure:
    """Buat line chart jumlah komentar per sentimen per tanggal."""
    return create_trend_line(df, title)


def bar_chart_platform(df: pd.DataFrame, title: str = "Distribusi per Platform") -> go.Figure:
    """Buat bar chart distribusi jumlah komentar per platform."""
    try:
        if df is None or df.empty:
            return _empty_figure("Data platform belum tersedia", title)

        platform_col = _resolve_platform_col(df)
        temp = df[[platform_col]].copy()
        temp["platform"] = temp[platform_col].map(_normalise_platform)
        counts = temp["platform"].value_counts().reset_index()
        counts.columns = ["platform", "count"]
        platform_order = [item for item in PLATFORM_ORDER if item in set(counts["platform"])]
        platform_order.extend([item for item in counts["platform"].tolist() if item not in platform_order])
        counts = counts.set_index("platform").reindex(platform_order).reset_index()
        counts["label"] = counts["platform"].map(lambda item: PLATFORM_LABELS.get(item, str(item).title()))
        counts["color"] = counts["platform"].map(lambda item: PLATFORM_COLORS.get(item, PRIMARY_COLOR))

        fig = go.Figure(
            go.Bar(
                x=counts["label"],
                y=counts["count"],
                marker={"color": counts["color"], "line": {"width": 0}},
                text=[f"{value:,}" if value else "" for value in counts["count"]],
                textposition="outside",
                cliponaxis=False,
                hovertemplate="Platform: %{x}<br>Jumlah: %{y:,}<extra></extra>",
            )
        )
        fig.update_layout(xaxis_title="Platform", yaxis_title="Jumlah Komentar", showlegend=False)
        return _apply_layout(fig, title, height=380, show_legend=False)
    except Exception as exc:
        _show_error("Bar chart platform gagal dibuat.", exc)
        return _empty_figure("Bar chart platform gagal dibuat", title)


def grouped_bar_platform_sentiment(df: pd.DataFrame, title: str = "Platform per Sentimen") -> go.Figure:
    """Buat grouped bar chart platform yang dikelompokkan per sentimen."""
    return create_sentiment_bar(df, title)


def scatter_followers_degree(df_nodes: pd.DataFrame, title: str = "Followers vs Degree Centrality") -> go.Figure:
    """Buat scatter plot degree centrality dibandingkan followers."""
    try:
        if df_nodes is None or df_nodes.empty:
            return _empty_figure("Data node SNA belum tersedia", title)

        degree_col = _first_existing_column(df_nodes, ("degree_centrality", "degree"))
        followers_col = _first_existing_column(df_nodes, ("followers", "follower", "jumlah_followers"))
        username_col = _first_existing_column(df_nodes, ("username", "node", "source", "akun"))
        platform_col = _first_existing_column(df_nodes, ("platform", "platform_group", "media"))
        missing = [name for name, col in {
            "degree": degree_col,
            "followers": followers_col,
            "username": username_col,
            "platform": platform_col,
        }.items() if not col]
        if missing:
            return _empty_figure(f"Kolom belum tersedia: {', '.join(missing)}", title)

        temp = df_nodes[[degree_col, followers_col, username_col, platform_col]].copy()
        temp.columns = ["degree", "followers", "username", "platform"]
        temp["degree"] = pd.to_numeric(temp["degree"], errors="coerce")
        temp["followers"] = pd.to_numeric(temp["followers"], errors="coerce")
        temp["platform"] = temp["platform"].map(_normalise_platform)
        temp = temp.dropna(subset=["degree", "followers"])
        if temp.empty:
            return _empty_figure("Data scatter belum tersedia", title)

        fig = go.Figure()
        platform_order = [item for item in PLATFORM_ORDER if item in set(temp["platform"])]
        platform_order.extend([item for item in temp["platform"].unique() if item not in platform_order])
        for platform in platform_order:
            subset = temp[temp["platform"] == platform]
            fig.add_trace(
                go.Scatter(
                    x=subset["degree"],
                    y=subset["followers"],
                    mode="markers",
                    name=PLATFORM_LABELS.get(platform, str(platform).title()),
                    marker={
                        "color": PLATFORM_COLORS.get(platform, PRIMARY_COLOR),
                        "size": 11,
                        "opacity": 0.85,
                        "line": {"color": "rgba(255,255,255,0.18)", "width": 1},
                    },
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

        fig.update_layout(xaxis_title="Degree Centrality", yaxis_title="Followers")
        return _apply_layout(fig, title, height=410, show_legend=True)
    except Exception as exc:
        _show_error("Scatter followers-degree gagal dibuat.", exc)
        return _empty_figure("Scatter followers-degree gagal dibuat", title)


def bar_chart_top_words(top_words: Any, sentimen: str, title: str = "Top 15 Kata") -> go.Figure:
    """Buat horizontal bar chart top words versi lama."""
    return create_top_words_bar(top_words, sentimen, title)


def heatmap_topics(topics_data: list[dict[str, Any]], title: str = "Heatmap Topik LDA") -> go.Figure:
    """Buat heatmap topik dari daftar label dan kata kunci."""
    try:
        if not topics_data:
            return _empty_figure("Data topik belum tersedia", title)

        topic_labels: list[str] = []
        z_matrix: list[list[float]] = []
        text_matrix: list[list[str]] = []
        max_words = 0
        parsed_topics: list[tuple[str, list[tuple[str, float]]]] = []

        # Ubah setiap topik menjadi daftar kata berbobot.
        for topic in topics_data:
            label = str(topic.get("label") or topic.get("name") or "Topik")
            keywords = _parse_keyword_weights(topic.get("keywords", []))
            if not keywords:
                continue
            parsed_topics.append((label, keywords))
            max_words = max(max_words, len(keywords))

        if not parsed_topics or max_words == 0:
            return _empty_figure("Kata kunci topik belum tersedia", title)

        x_labels = [f"#{i + 1}" for i in range(max_words)]
        for label, keywords in parsed_topics:
            topic_labels.append(label)
            weights = [float(weight) for _, weight in keywords]
            words = [word for word, _ in keywords]
            z_matrix.append(weights + [0.0] * (max_words - len(weights)))
            text_matrix.append(words + [""] * (max_words - len(words)))

        fig = go.Figure(
            go.Heatmap(
                z=z_matrix,
                x=x_labels,
                y=topic_labels,
                text=text_matrix,
                texttemplate="%{text}",
                textfont={"family": FONT_FAMILY, "size": 11, "color": "#FFFFFF"},
                colorscale=[
                    [0.0, "rgba(29,161,242,0.12)"],
                    [0.45, "rgba(229,57,53,0.48)"],
                    [1.0, "rgba(255,82,82,0.94)"],
                ],
                hovertemplate="Topik: %{y}<br>Peringkat: %{x}<br>Kata: %{text}<br>Bobot: %{z:.3f}<extra></extra>",
                colorbar={"title": "Bobot"},
                xgap=2,
                ygap=2,
            )
        )
        fig.update_layout(xaxis_title="Peringkat Kata", yaxis_title="Topik")
        return _apply_layout(fig, title, height=max(390, len(topic_labels) * 48 + 160), show_legend=False, x_grid=False, y_grid=False)
    except Exception as exc:
        _show_error("Heatmap topik gagal dibuat.", exc)
        return _empty_figure("Heatmap topik gagal dibuat", title)


def gauge_confidence(score: float, label: str) -> go.Figure:
    """Buat gauge chart confidence score prediksi manual pada rentang 0–1."""
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
                number={"font": {"family": FONT_FAMILY, "size": 36, "color": _chart_theme()["text"]}},
                title={"text": label, "font": {"family": FONT_FAMILY, "size": 16, "color": _chart_theme()["text"]}},
                gauge={
                    "axis": {"range": [0, 1], "tickwidth": 1, "tickcolor": _chart_theme()["muted"]},
                    "bar": {"color": bar_color},
                    "bgcolor": "rgba(0,0,0,0)",
                    "bordercolor": COLORS["border"],
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
        return _apply_layout(fig, height=330, show_legend=False)
    except Exception as exc:
        _show_error("Gauge confidence gagal dibuat.", exc)
        return _empty_figure("Gauge confidence gagal dibuat")


__all__ = [
    "COLORS",
    "SENTIMENT_COLORS",
    "PLATFORM_COLORS",
    "PRIMARY_COLOR",
    "ACCENT_COLOR",
    "SENTIMENT_ORDER",
    "SENTIMENT_LABELS",
    "PLATFORM_ORDER",
    "PLATFORM_LABELS",
    "create_sentiment_pie",
    "create_sentiment_bar",
    "create_trend_line",
    "create_top_words_bar",
    "create_network_stats_bar",
    "create_heatmap",
    "bar_chart_sentiment",
    "pie_chart_sentiment",
    "bar_chart_confidence",
    "timeline_sentiment",
    "bar_chart_platform",
    "grouped_bar_platform_sentiment",
    "scatter_followers_degree",
    "bar_chart_top_words",
    "heatmap_topics",
    "gauge_confidence",
]
