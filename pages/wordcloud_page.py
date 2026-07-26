"""Halaman WordCloud — visualisasi kata dominan, frekuensi, dan analisis topik."""

from __future__ import annotations

from collections import Counter
from io import BytesIO

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from wordcloud import WordCloud

from utils.chart_builder import SENTIMENT_LABELS, bar_chart_top_words
from utils.css_loader import render_coming_soon_card, render_data_badge, render_page_header
from utils.data_loader import (
    get_data_source_label,
    get_platform_filter,
    get_sentiment_file_signature,
    load_topic_data,
)
from utils.dummy_data import get_dummy_top_words
from utils.preprocessor import clean_text, prepare_for_wordcloud
from utils.topic_classifier import apply_topics, get_dominant_keywords, get_top_topics

# --- Konstanta layanan & visual ---
_LAYANAN_LIST = ["IndiHome", "IndiBiz", "Telkomsel"]
_READY_SERVICES = {"IndiHome"}
_PLATFORM_OPTIONS = {
    "twitter": "Twitter/X",
    "instagram": "Instagram",
    "tiktok": "TikTok",
}
_SENTIMENT_ORDER = ["positive", "neutral", "negative"]
_WC_STYLE = {
    "positive": {"colormap": "Greens", "background": "#F1F8E9", "icon": "😊"},
    "neutral": {"colormap": "Blues", "background": "#E3F2FD", "icon": "😐"},
    "negative": {"colormap": "Reds", "background": "#FFF3E0", "icon": "😠"},
}
_BRAND_WORDS = {"indihome", "indibiz", "telkomsel", "myindihome", "telkom"}


def _is_service_ready(layanan: str) -> bool:
    """Cek apakah layanan sudah siap untuk analisis WordCloud."""
    return layanan in _READY_SERVICES


@st.cache_data(show_spinner=False, persist="disk", max_entries=6)
def _prepare_dataframe_cached(layanan: str, file_signature: str) -> pd.DataFrame:
    """Muat subset ringan dan klasifikasikan topik satu kali per versi file."""
    del file_signature  # Menjadi cache key saat file sumber berubah.
    df = load_topic_data(layanan).copy()
    if df.empty:
        return df

    if "content_clean" not in df.columns and "content" in df.columns:
        df["content_clean"] = df["content"].astype(str).apply(clean_text)

    if "topic" not in df.columns:
        df = apply_topics(df)
    return df


def _prepare_dataframe(layanan: str) -> pd.DataFrame:
    """Muat DataFrame WordCloud dengan cache berdasarkan versi file sumber."""
    try:
        signature = get_sentiment_file_signature(layanan)
        return _prepare_dataframe_cached(layanan, signature)
    except Exception as exc:
        st.error(f"Gagal menyiapkan data WordCloud: {exc}")
        return pd.DataFrame()


def _filter_brand_words(text: str, show_brand: bool) -> str:
    """Hapus kata brand dari corpus jika toggle dimatikan."""
    try:
        if show_brand or not text:
            return text
        words = [w for w in str(text).split() if w.lower() not in _BRAND_WORDS]
        return " ".join(words)
    except Exception:
        return text


@st.cache_data(show_spinner=False, max_entries=36)
def _count_word_frequencies_cached(
    texts: tuple[str, ...],
    show_brand: bool,
) -> Counter:
    """Hitung frekuensi kata dari corpus immutable agar cache stabil."""
    counter: Counter = Counter()
    for raw in texts:
        cleaned = prepare_for_wordcloud(raw)
        cleaned = _filter_brand_words(cleaned, show_brand)
        counter.update(word for word in cleaned.split() if word)
    return counter


def _compute_word_frequencies(
    df: pd.DataFrame,
    sentiment: str,
    show_brand: bool,
) -> Counter:
    """Hitung frekuensi kata per sentimen dengan cache berbasis corpus."""
    try:
        if df.empty or "predicted_sentiment" not in df.columns:
            return Counter()

        subset = df[df["predicted_sentiment"].astype(str).str.lower() == sentiment]
        content_col = "content" if "content" in subset.columns else "content_clean"
        texts = tuple(subset[content_col].fillna("").astype(str).tolist())
        return _count_word_frequencies_cached(texts, show_brand)
    except Exception as exc:
        st.error(f"Gagal menghitung frekuensi kata ({sentiment}): {exc}")
        return Counter()


def _get_top_words_list(
    df: pd.DataFrame,
    sentiment: str,
    show_brand: bool,
    top_n: int = 15,
) -> list[tuple[str, int]]:
    """Ambil daftar top N kata beserta frekuensinya."""
    try:
        freqs = _compute_word_frequencies(df, sentiment, show_brand)
        if freqs:
            return freqs.most_common(top_n)

        # Fallback dummy jika corpus kosong
        dummy = get_dummy_top_words().get(sentiment, [])
        return list(dummy)[:top_n]
    except Exception as exc:
        st.error(f"Gagal mengambil top words ({sentiment}): {exc}")
        return []


def _frequencies_to_corpus(word_freq: dict[str, int]) -> str:
    """Buat signature corpus ringkas dan deterministik untuk cache WordCloud."""
    try:
        return "|".join(
            f"{str(word)}:{max(0, int(count))}"
            for word, count in sorted(word_freq.items())
            if str(word).strip() and int(count) > 0
        )
    except Exception:
        return ""


@st.cache_data(
    show_spinner="Memproses WordCloud, mohon tunggu...",
    max_entries=24,
)
def _create_wordcloud_png(
    corpus: str,
    word_frequencies: tuple[tuple[str, int], ...],
    colormap: str,
    bg_color: str,
    max_words: int,
) -> bytes:
    """Buat PNG WordCloud dengan signature corpus sebagai cache key utama."""
    fig, ax = plt.subplots(figsize=(10, 5))  # FIX: rasio WordCloud 2:1 untuk semua viewport
    try:
        fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)
        frequencies = {
            str(word): max(0, int(count))
            for word, count in word_frequencies
            if str(word).strip() and int(count) > 0
        }

        if not corpus.strip() or not frequencies:
            ax.text(
                0.5,
                0.5,
                "Tidak ada data",
                ha="center",
                va="center",
                fontsize=14,
                color="#888888",
            )
            ax.axis("off")
        else:
            wc = WordCloud(
                width=800,
                height=400,
                background_color=bg_color,
                colormap=colormap,
                max_words=max_words,
                prefer_horizontal=0.7,
                collocations=False,
                min_font_size=12,  # FIX: ukuran kata minimum tetap terbaca di tablet
            ).generate_from_frequencies(frequencies)
            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")

        plt.tight_layout(pad=0)
        buffer = BytesIO()
        fig.savefig(
            buffer,
            format="png",
            bbox_inches="tight",
            facecolor=fig.get_facecolor(),
            dpi=120,
        )
        buffer.seek(0)
        return buffer.getvalue()
    finally:
        plt.close(fig)


def _sinkronkan_layanan_wordcloud() -> None:
    """Simpan pilihan layanan WordCloud sebagai layanan aktif global."""
    try:
        layanan = str(st.session_state.get("wc_layanan", "IndiHome")).strip()
        if layanan not in _LAYANAN_LIST:
            layanan = "IndiHome"
        st.session_state["active_service"] = layanan
    except Exception as exc:
        st.sidebar.error(f"Pilihan layanan belum dapat disimpan: {exc}")


def _render_sidebar_filters() -> tuple[str, list[str], int, bool]:
    """Render filter di sidebar dan kembalikan nilai yang dipilih."""
    try:
        st.sidebar.markdown("### ☁️ Filter WordCloud")

        if st.session_state.get("_active_service_sync_target") == "WordCloud":
            layanan_global = str(st.session_state.get("active_service", "IndiHome")).strip()
            if layanan_global not in _LAYANAN_LIST:
                layanan_global = "IndiHome"
            st.session_state["wc_layanan"] = layanan_global
            st.session_state.pop("_active_service_sync_target", None)

        layanan = st.sidebar.selectbox(
            "Layanan",
            options=_LAYANAN_LIST,
            index=0,
            key="wc_layanan",
            on_change=_sinkronkan_layanan_wordcloud,
        )

        df_preview = _prepare_dataframe(layanan) if _is_service_ready(layanan) else pd.DataFrame()
        available = (
            sorted(df_preview["platform"].dropna().astype(str).str.lower().unique().tolist())
            if not df_preview.empty and "platform" in df_preview.columns
            else list(_PLATFORM_OPTIONS.keys())
        )
        label_map = {_PLATFORM_OPTIONS.get(p, p): p for p in available}
        platform_labels = list(label_map.keys())

        selected_labels = st.sidebar.multiselect(
            "Platform",
            options=platform_labels,
            default=platform_labels,
            key="wc_platform",
        )
        selected_platforms = [label_map[lbl] for lbl in selected_labels]

        max_words = st.sidebar.slider(
            "Maksimum kata (max_words)",
            min_value=50,
            max_value=200,
            value=100,
            step=10,
            key="wc_max_words",
        )

        show_brand = st.sidebar.toggle(
            "Tampilkan nama brand",
            value=True,
            key="wc_show_brand",
            help="Jika dimatikan, kata 'indihome' dan brand terkait dihapus dari corpus.",
        )

        return layanan, selected_platforms, max_words, show_brand
    except Exception as exc:
        st.sidebar.error(f"Gagal memuat filter: {exc}")
        return "IndiHome", list(_PLATFORM_OPTIONS.keys()), 100, True


def _render_tab_wordcloud(
    df: pd.DataFrame,
    max_words: int,
    show_brand: bool,
) -> None:
    """Tab 1 — Tiga WordCloud per sentimen dengan download PNG."""
    try:
        cols = st.columns(3)

        for idx, sentiment in enumerate(_SENTIMENT_ORDER):
            style = _WC_STYLE[sentiment]
            label = SENTIMENT_LABELS.get(sentiment, sentiment)
            freqs = _compute_word_frequencies(df, sentiment, show_brand)
            comment_count = len(df[df["predicted_sentiment"] == sentiment]) if not df.empty else 0

            with cols[idx]:
                st.markdown(f"### {style['icon']} {label}")

                # Corpus menjadi cache key sehingga WordCloud tidak dihitung ulang
                # ketika pengguna kembali ke filter yang sama.
                limited_freq = dict(freqs.most_common(max_words))
                corpus = _frequencies_to_corpus(limited_freq)
                png_bytes = _create_wordcloud_png(
                    corpus,
                    tuple(sorted(limited_freq.items())),
                    colormap=style["colormap"],
                    bg_color=style["background"],
                    max_words=max_words,
                )

                st.image(png_bytes, width="stretch")
                st.caption(f"📊 {comment_count:,} komentar")

                st.download_button(
                    label="⬇️ Download PNG",
                    data=png_bytes,
                    file_name=f"wordcloud_{sentiment}.png",
                    mime="image/png",
                    key=f"wc_download_{sentiment}",
                    use_container_width=True,
                )
    except Exception as exc:
        st.error(f"Gagal menampilkan tab WordCloud: {exc}")


def _render_tab_top_words(df: pd.DataFrame, show_brand: bool) -> None:
    """Tab 2 — Horizontal bar chart top 15 kata per sentimen."""
    try:
        cols = st.columns(3)

        for idx, sentiment in enumerate(_SENTIMENT_ORDER):
            label = SENTIMENT_LABELS.get(sentiment, sentiment)
            top_words = _get_top_words_list(df, sentiment, show_brand, top_n=15)

            with cols[idx]:
                st.markdown(f"### {label}")
                figur = bar_chart_top_words(
                    top_words, sentiment, f"Top 15 — {label}"
                )
                if figur is not None:
                    st.plotly_chart(
                        figur,
                        use_container_width=True,
                        key=f"wc_top_words_chart_{sentiment}",
                    )
                else:
                    st.warning("Grafik tidak dapat ditampilkan.")
    except Exception as exc:
        st.error(f"Gagal menampilkan tab top words: {exc}")


def _render_topic_card(
    topic_row: pd.Series,
    df: pd.DataFrame,
    sentiment: str,
    max_count: int,
) -> None:
    """Render kartu satu topik dengan progress bar dan badge kata kunci."""
    try:
        topic_name = str(topic_row.get("topik", "Lainnya"))
        count = int(topic_row.get("jumlah_komentar", 0))
        pct = float(topic_row.get("pct", 0.0))
        progress_val = min(count / max(max_count, 1), 1.0)

        keywords = get_dominant_keywords(df, topic_name, sentiment)[:3]
        badges_html = "".join(
            f'<span class="badge badge-user" style="margin-right:4px;">{kw}</span>'
            for kw in keywords
        ) or '<span class="badge badge-unknown">—</span>'

        st.markdown(
            f"""
            <div class="metric-card" style="margin-bottom:0.75rem;">
                <strong>{topic_name}</strong><br>
                <span style="color:#888;font-size:0.85rem;">
                    {count:,} komentar · {pct:.1f}%
                </span>
                <div style="margin:0.5rem 0;">{badges_html}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.progress(progress_val, text=f"{count} komentar")
    except Exception as exc:
        st.error(f"Gagal menampilkan kartu topik: {exc}")


def _render_tab_topics(df: pd.DataFrame) -> None:
    """Tab 3 — Analisis topik positif dan negatif."""
    try:
        col_pos, col_neg = st.columns(2)

        with col_pos:
            st.subheader("😊 Topik Positif")
            top_pos = get_top_topics(df, "positive", top_n=5)
            if top_pos.empty:
                st.caption("Tidak ada topik positif.")
            else:
                max_count = int(top_pos["jumlah_komentar"].max())
                for _, row in top_pos.iterrows():
                    _render_topic_card(row, df, "positive", max_count)

        with col_neg:
            st.subheader("😠 Topik Negatif")
            top_neg = get_top_topics(df, "negative", top_n=5)
            if top_neg.empty:
                st.caption("Tidak ada topik negatif.")
            else:
                max_count = int(top_neg["jumlah_komentar"].max())
                for _, row in top_neg.iterrows():
                    _render_topic_card(row, df, "negative", max_count)
    except Exception as exc:
        st.error(f"Gagal menampilkan analisis topik: {exc}")


def render_wordcloud() -> None:
    """Entry point halaman WordCloud."""
    try:
        render_page_header(
            "☁️ WordCloud & Analisis Kata",
            "Visualisasi kata dominan dan topik per sentimen",
        )

        layanan, platforms, max_words, show_brand = _render_sidebar_filters()

        if not _is_service_ready(layanan):
            render_coming_soon_card(layanan, "WordCloud & analisis kata")
            return

        df = _prepare_dataframe(layanan)
        df = get_platform_filter(df, platforms)

        col_badge, col_info = st.columns([1, 4])
        with col_badge:
            is_real = get_data_source_label(layanan) == "📁 Data Real"
            render_data_badge(is_real)
        with col_info:
            st.caption(
                f"Sumber: {get_data_source_label(layanan)} · "
                f"{len(df):,} komentar · max_words={max_words} · "
                f"Brand: {'tampil' if show_brand else 'disembunyikan'}"
            )

        if df.empty:
            st.info("Tidak ada data untuk filter ini.")
            return

        tab_wc, tab_top, tab_topic = st.tabs(
            ["☁️ WordCloud", "📊 Top 15 Kata", "🏷️ Analisis Topik"]
        )

        with tab_wc:
            _render_tab_wordcloud(df, max_words, show_brand)

        with tab_top:
            _render_tab_top_words(df, show_brand)

        with tab_topic:
            _render_tab_topics(df)

    except Exception as exc:
        st.error(f"Gagal memuat halaman WordCloud: {exc}")
