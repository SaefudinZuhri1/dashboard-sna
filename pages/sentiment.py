"""Halaman analisis sentimen — overview, prediksi IndoBERT, dan contoh komentar."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.chart_builder import (
    SENTIMENT_COLORS,
    SENTIMENT_LABELS,
    bar_chart_confidence,
    bar_chart_sentiment,
    gauge_confidence,
    grouped_bar_platform_sentiment,
    pie_chart_sentiment,
    timeline_sentiment,
)
from utils.css_loader import (
    inject_platform_badge,
    render_coming_soon_card,
    render_data_badge,
    render_page_header,
)
from utils.data_loader import (
    get_data_source_label,
    get_date_range_filter,
    get_platform_filter,
    load_sentiment_data,
)
from utils.preprocessor import clean_text
from utils.topic_classifier import apply_topics

# --- Konstanta layanan & model ---
_LAYANAN_LIST = ["IndiHome", "IndiBiz", "Telkomsel"]
_READY_SERVICES = {"IndiHome"}
_MODEL_HF_NAME = "mdhugol/indonesia-bert-sentiment-classification"
_LABEL_TO_SENTIMENT = {
    "LABEL_0": "positive",
    "LABEL_1": "neutral",
    "LABEL_2": "negative",
    "label_0": "positive",
    "label_1": "neutral",
    "label_2": "negative",
}
_PLATFORM_OPTIONS = {
    "twitter": "Twitter/X",
    "instagram": "Instagram",
    "tiktok": "TikTok",
}
_HISTORY_KEY = "sentiment_prediction_history"
_MAX_HISTORY = 10


def _project_root() -> Path:
    """Kembalikan path root proyek."""
    return Path(__file__).resolve().parent.parent


def _is_service_ready(layanan: str) -> bool:
    """Cek apakah layanan sudah siap ditampilkan."""
    return layanan in _READY_SERVICES


def _resolve_model_path() -> str:
    """
    Tentukan path model IndoBERT.

    Prioritas: folder lokal models/indihome/, fallback ke HuggingFace Hub.
    """
    local_dir = _project_root() / "models" / "indihome"
    try:
        if local_dir.is_dir() and any(local_dir.iterdir()):
            return str(local_dir)
    except Exception:
        pass
    return _MODEL_HF_NAME


@st.cache_resource(show_spinner="Memuat model IndoBERT...")
def load_indihome_model():
    """
    Muat pipeline klasifikasi sentimen IndoBERT (cache resource).

    Returns:
        Pipeline HuggingFace sentiment-analysis atau None jika gagal.
    """
    try:
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            pipeline,
        )

        model_path = _resolve_model_path()
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = AutoModelForSequenceClassification.from_pretrained(model_path)
        return pipeline(
            "sentiment-analysis",
            model=model,
            tokenizer=tokenizer,
            return_all_scores=True,
            device=-1,
        )
    except Exception as exc:
        st.error(
            f"Gagal memuat model IndoBERT: {exc}. "
            "Pastikan folder models/indihome/ berisi model atau koneksi internet aktif."
        )
        return None


def predict_sentiment(text: str, classifier) -> dict | None:
    """
    Jalankan prediksi sentimen pada satu teks.

    Returns:
        Dict berisi label, label_id, confidence, dan probabilities.
    """
    try:
        if not text or not str(text).strip():
            raise ValueError("Teks komentar tidak boleh kosong.")
        if classifier is None:
            raise RuntimeError("Model IndoBERT belum dimuat.")

        cleaned = clean_text(str(text))
        if not cleaned:
            raise ValueError("Teks tidak valid setelah pembersihan.")

        raw_scores = classifier(cleaned[:512], truncation=True)
        scores = raw_scores[0] if raw_scores else []

        probabilities: dict[str, float] = {}
        for item in scores:
            label_key = str(item.get("label", "")).strip()
            sentiment_key = _LABEL_TO_SENTIMENT.get(label_key, label_key.lower())
            probabilities[sentiment_key] = float(item.get("score", 0.0))

        if not probabilities:
            raise RuntimeError("Model tidak mengembalikan skor probabilitas.")

        best_sentiment = max(probabilities, key=probabilities.get)
        return {
            "label": best_sentiment,
            "label_id": SENTIMENT_LABELS.get(best_sentiment, best_sentiment),
            "confidence": round(float(probabilities[best_sentiment]), 4),
            "probabilities": {
                k: round(v, 4) for k, v in probabilities.items()
            },
        }
    except Exception as exc:
        st.error(f"Prediksi gagal: {exc}")
        return None


def bar_chart_probabilities(probabilities: dict[str, float], title: str = "") -> go.Figure:
    """Bar chart horizontal probabilitas tiga kelas sentimen."""
    try:
        order = ["positive", "neutral", "negative"]
        labels = [SENTIMENT_LABELS.get(s, s) for s in order]
        values = [float(probabilities.get(s, 0.0)) for s in order]
        colors = [SENTIMENT_COLORS.get(s, "#1DA1F2") for s in order]

        fig = go.Figure(
            go.Bar(
                x=values,
                y=labels,
                orientation="h",
                marker_color=colors,
                text=[f"{v:.1%}" for v in values],
                textposition="outside",
                hovertemplate="%{y}: %{x:.3f}<extra></extra>",
            )
        )
        fig.update_layout(
            title=title or "Probabilitas per Kelas Sentimen",
            xaxis_title="Probabilitas",
            xaxis=dict(range=[0, 1]),
            yaxis=dict(autorange="reversed"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=40, r=20, t=50, b=40),
            height=260,
        )
        return fig
    except Exception:
        fig = go.Figure()
        fig.add_annotation(text="Gagal memuat chart probabilitas", showarrow=False)
        return fig


def _prepare_dataframe(layanan: str) -> pd.DataFrame:
    """Muat dan lengkapi DataFrame sentimen dengan kolom topic."""
    try:
        df = load_sentiment_data(layanan).copy()
        if df.empty:
            return df

        if "content_clean" not in df.columns and "content" in df.columns:
            df["content_clean"] = df["content"].astype(str).apply(clean_text)

        if "topic" not in df.columns:
            df = apply_topics(df)

        return df
    except Exception as exc:
        st.error(f"Gagal menyiapkan data sentimen: {exc}")
        return pd.DataFrame()


def _apply_filters(df: pd.DataFrame, platforms: list[str], date_range: tuple) -> pd.DataFrame:
    """Terapkan filter platform dan rentang tanggal."""
    try:
        filtered = get_platform_filter(df, platforms)
        if date_range and len(date_range) == 2:
            filtered = get_date_range_filter(filtered, date_range[0], date_range[1])
        return filtered
    except Exception as exc:
        st.error(f"Gagal menerapkan filter: {exc}")
        return df.copy()


def _render_sentiment_badge(sentiment: str) -> str:
    """Kembalikan HTML badge sentimen berwarna."""
    key = str(sentiment or "").lower().strip()
    css_class = {
        "positive": "badge-positive",
        "neutral": "badge-neutral",
        "negative": "badge-negative",
    }.get(key, "badge-unknown")
    label = SENTIMENT_LABELS.get(key, sentiment)
    return f'<span class="badge {css_class}">{label}</span>'


def _render_comment_card(row: pd.Series) -> None:
    """Render satu kartu komentar contoh."""
    try:
        username = str(row.get("username", "anonim"))
        platform = str(row.get("platform", "unknown"))
        content = str(row.get("content", ""))
        if len(content) > 100:
            content = content[:100] + "..."

        conf_col = "confidence_score" if "confidence_score" in row.index else "confidence"
        confidence = float(row.get(conf_col, 0.0))
        topic = str(row.get("topic", "Lainnya"))
        sentiment = str(row.get("predicted_sentiment", "neutral"))

        st.markdown(
            f"""
            <div class="metric-card" style="margin-bottom:0.75rem;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <strong>@{username}</strong>
                    {inject_platform_badge(platform)}
                </div>
                <p style="margin:0.6rem 0;font-size:0.9rem;">{content}</p>
                <div style="display:flex;gap:0.4rem;flex-wrap:wrap;align-items:center;">
                    {_render_sentiment_badge(sentiment)}
                    <span class="badge badge-ready">{confidence:.1%}</span>
                    <span class="badge badge-user">{topic}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Gagal menampilkan kartu komentar: {exc}")


def _init_prediction_history() -> None:
    """Inisialisasi riwayat prediksi di session state."""
    if _HISTORY_KEY not in st.session_state:
        st.session_state[_HISTORY_KEY] = []


def _append_prediction_history(text: str, result: dict) -> None:
    """Simpan prediksi terbaru (maksimal 10 entri)."""
    try:
        _init_prediction_history()
        entry = {
            "waktu": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            "teks": text[:80] + ("..." if len(text) > 80 else ""),
            "sentimen": result.get("label_id", result.get("label", "-")),
            "confidence": result.get("confidence", 0.0),
        }
        st.session_state[_HISTORY_KEY].insert(0, entry)
        st.session_state[_HISTORY_KEY] = st.session_state[_HISTORY_KEY][:_MAX_HISTORY]
    except Exception as exc:
        st.error(f"Gagal menyimpan riwayat prediksi: {exc}")


def _render_tab_overview(layanan: str) -> None:
    """Tab 1 — Overview distribusi dan tren sentimen."""
    try:
        if not _is_service_ready(layanan):
            render_coming_soon_card(layanan, "Overview analisis sentimen")
            return

        df_raw = _prepare_dataframe(layanan)
        if df_raw.empty:
            st.warning("Data sentimen kosong untuk layanan ini.")
            return

        col_badge, col_info = st.columns([1, 3])
        with col_badge:
            is_real = get_data_source_label(layanan) == "📁 Data Real"
            render_data_badge(is_real)
        with col_info:
            st.caption(f"Sumber: {get_data_source_label(layanan)} · Total {len(df_raw):,} baris")

        with st.expander("🔎 Filter Data", expanded=True):
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                available_platforms = sorted(
                    df_raw["platform"].dropna().astype(str).str.lower().unique().tolist()
                )
                platform_labels = [
                    _PLATFORM_OPTIONS.get(p, p) for p in available_platforms
                ]
                selected_labels = st.multiselect(
                    "Platform",
                    options=platform_labels,
                    default=platform_labels,
                    key="sentiment_filter_platform",
                )
                label_to_key = {v: k for k, v in _PLATFORM_OPTIONS.items()}
                selected_platforms = [
                    label_to_key.get(lbl, lbl.lower()) for lbl in selected_labels
                ]

            with f_col2:
                date_series = pd.to_datetime(
                    df_raw.get("date_created", df_raw.get("date")),
                    errors="coerce",
                ).dropna()
                min_date = date_series.min().date()
                max_date = date_series.max().date()
                date_range = st.date_input(
                    "Rentang Tanggal",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date,
                    key="sentiment_filter_date",
                )

        if isinstance(date_range, tuple) and len(date_range) == 2:
            df = _apply_filters(df_raw, selected_platforms, date_range)
        else:
            df = _apply_filters(df_raw, selected_platforms, (min_date, max_date))

        if df.empty:
            st.warning("Tidak ada data setelah filter diterapkan.")
            return

        st.markdown(f"**Menampilkan {len(df):,} komentar** setelah filter")

        # Row 1 — 3 chart distribusi
        c1, c2, c3 = st.columns(3)
        with c1:
            st.plotly_chart(
                bar_chart_sentiment(df, "Jumlah Komentar per Sentimen"),
                use_container_width=True,
            )
        with c2:
            st.plotly_chart(
                pie_chart_sentiment(df, "Persentase Sentimen"),
                use_container_width=True,
            )
        with c3:
            st.plotly_chart(
                bar_chart_confidence(df, "Rata-rata Confidence"),
                use_container_width=True,
            )

        # Row 2 — Timeline
        st.plotly_chart(
            timeline_sentiment(df, "Timeline Sentimen per Tanggal"),
            use_container_width=True,
        )

        # Row 3 — Grouped bar platform
        st.plotly_chart(
            grouped_bar_platform_sentiment(df, "Distribusi Sentimen per Platform"),
            use_container_width=True,
        )
    except Exception as exc:
        st.error(f"Gagal menampilkan overview sentimen: {exc}")


def _render_tab_prediction(layanan: str) -> None:
    """Tab 2 — Prediksi manual menggunakan IndoBERT."""
    try:
        if not _is_service_ready(layanan):
            render_coming_soon_card(layanan, "Prediksi manual IndoBERT")
            return

        st.info(
            "Menggunakan model **mdhugol/indonesia-bert-sentiment-classification** "
            "(LABEL_0=Positif · LABEL_1=Netral · LABEL_2=Negatif)."
        )

        user_text = st.text_area(
            "Masukkan teks komentar",
            height=120,
            placeholder="Contoh: layanan indihome bagus dan internetnya stabil",
            key="sentiment_manual_input",
        )

        if st.button("🔍 Prediksi Sentimen", type="primary", key="btn_predict_sentiment"):
            with st.spinner("Sedang menganalisis sentimen..."):
                classifier = load_indihome_model()
                result = predict_sentiment(user_text, classifier)

            if result:
                _append_prediction_history(user_text, result)

                st.markdown("#### Hasil Prediksi")
                st.markdown(
                    f"<div style='margin:0.5rem 0;'>{_render_sentiment_badge(result['label'])}</div>",
                    unsafe_allow_html=True,
                )

                g1, g2 = st.columns([1, 1])
                with g1:
                    st.plotly_chart(
                        gauge_confidence(
                            result["confidence"],
                            f"Confidence — {result['label_id']}",
                        ),
                        use_container_width=True,
                    )
                with g2:
                    st.plotly_chart(
                        bar_chart_probabilities(result["probabilities"]),
                        use_container_width=True,
                    )

        _init_prediction_history()
        history = st.session_state.get(_HISTORY_KEY, [])
        st.markdown("#### Riwayat Prediksi (10 terakhir)")
        if history:
            st.dataframe(
                pd.DataFrame(history),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("Belum ada prediksi. Ketik teks lalu klik tombol prediksi.")
    except Exception as exc:
        st.error(f"Gagal menampilkan tab prediksi: {exc}")


def _render_tab_examples(layanan: str) -> None:
    """Tab 3 — Contoh komentar per kelas sentimen."""
    try:
        if not _is_service_ready(layanan):
            render_coming_soon_card(layanan, "Contoh komentar")
            return

        df = _prepare_dataframe(layanan)
        if df.empty:
            st.warning("Data komentar tidak tersedia.")
            return

        conf_col = "confidence_score" if "confidence_score" in df.columns else "confidence"
        if conf_col in df.columns:
            df = df.sort_values(conf_col, ascending=False)

        col_pos, col_neu, col_neg = st.columns(3)
        sentiment_columns = [
            ("positive", "Positif", col_pos),
            ("neutral", "Netral", col_neu),
            ("negative", "Negatif", col_neg),
        ]

        for sentiment_key, title, col in sentiment_columns:
            with col:
                st.subheader(f"😊 {title}" if sentiment_key == "positive" else (
                    f"😐 {title}" if sentiment_key == "neutral" else f"😠 {title}"
                ))
                subset = df[df["predicted_sentiment"] == sentiment_key].head(5)
                if subset.empty:
                    st.caption("Tidak ada contoh komentar.")
                    continue
                for _, row in subset.iterrows():
                    _render_comment_card(row)
    except Exception as exc:
        st.error(f"Gagal menampilkan contoh komentar: {exc}")


def render_sentiment() -> None:
    """Entry point halaman analisis sentimen."""
    try:
        render_page_header(
            "🎯 Analisis Sentimen",
            "Distribusi sentimen publik dan prediksi manual IndoBERT",
        )

        layanan = st.selectbox(
            "Pilih Layanan",
            options=_LAYANAN_LIST,
            index=0,
            key="sentiment_layanan_selector",
            help="IndiHome sudah tersedia. IndiBiz dan Telkomsel akan segera hadir.",
        )

        tab_overview, tab_predict, tab_examples = st.tabs(
            ["📊 Overview Sentimen", "🤖 Prediksi Manual", "💬 Contoh Komentar"]
        )

        with tab_overview:
            _render_tab_overview(layanan)

        with tab_predict:
            _render_tab_prediction(layanan)

        with tab_examples:
            _render_tab_examples(layanan)

    except Exception as exc:
        st.error(f"Gagal memuat halaman sentimen: {exc}")
