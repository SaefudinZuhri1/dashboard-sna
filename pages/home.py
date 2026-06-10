"""Halaman beranda dashboard penelitian skripsi."""

import streamlit as st

from utils.chart_builder import pie_chart_sentiment
from utils.css_loader import render_metric_card
from utils.data_loader import load_sentiment_data, load_sna_data
from utils.dummy_data import get_dummy_stats

# Layanan yang didukung dashboard
_LAYANAN_LIST = ["IndiHome", "IndiBiz", "Telkomsel"]


def _get_dashboard_stats() -> dict:
    """
    Hitung statistik ringkasan beranda dari data loader.

    Jika gagal, fallback ke get_dummy_stats().
    """
    try:
        total_data = 0
        total_sentiment = 0

        for layanan in _LAYANAN_LIST:
            df = load_sentiment_data(layanan)
            total_data += len(df)
            if not df.empty and "predicted_sentiment" in df.columns:
                total_sentiment += int(
                    df["predicted_sentiment"].notna().sum()
                )

        df_sna = load_sna_data()
        if df_sna.empty:
            nodes, edges = 0, 0
        else:
            nodes = len(set(df_sna["source"]) | set(df_sna["target"]))
            edges = len(df_sna)

        return {
            "total_data": total_data,
            "total_platform": 3,
            "total_sentiment": total_sentiment,
            "total_node": nodes,
            "total_edge": edges,
        }
    except Exception:
        try:
            dummy = get_dummy_stats()
            return {
                "total_data": dummy.get("total_data", 0),
                "total_platform": 3,
                "total_sentiment": dummy.get("total_data", 0),
                "total_node": dummy.get("total_node", 0),
                "total_edge": dummy.get("total_edge", 0),
            }
        except Exception as e:
            st.error(f"Gagal memuat statistik beranda: {e}")
            return {
                "total_data": 0,
                "total_platform": 3,
                "total_sentiment": 0,
                "total_node": 0,
                "total_edge": 0,
            }


def _render_banner_header() -> None:
    """Tampilkan banner gradient dengan judul penelitian dan identitas peneliti."""
    try:
        st.markdown(
            """
            <div class="banner-header">
                <h1>📡 Analisis Jaringan dan Sentimen Publik Terhadap Layanan Digital
                PT. Telekomunikasi Indonesia untuk Identifikasi Influencer di Media Sosial
                Menggunakan Social Network Analysis (SNA) dan IndoBERT</h1>
                <p>Aulia Rahmadiva Wardana · NPM 184220019 · S1 Sains Data · ULBI Bandung 2026</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as e:
        st.error(f"Gagal menampilkan banner: {e}")


def _render_deskripsi_tujuan() -> None:
    """Tampilkan deskripsi singkat dan tujuan penelitian dalam 2 kolom."""
    try:
        col_kiri, col_kanan = st.columns(2)

        with col_kiri:
            st.subheader("📋 Deskripsi Penelitian")
            st.markdown(
                """
                Penelitian ini menganalisis opini publik terhadap layanan digital
                **Telkom Group** (IndiHome, IndiBiz, Telkomsel) melalui komentar
                di media sosial **Twitter/X**, **Instagram**, dan **TikTok**
                periode **November–Desember 2025**.

                Kombinasi **Social Network Analysis (SNA)** dan model **IndoBERT**
                digunakan untuk memetakan interaksi pengguna serta mengklasifikasi
                sentimen guna mengidentifikasi **influencer** potensial.
                """
            )

        with col_kanan:
            st.subheader("🎯 Tujuan Penelitian")
            st.markdown(
                """
                1. Menganalisis **distribusi sentimen** publik terhadap layanan digital Telkom Group.
                2. Memetakan **jaringan interaksi** pengguna media sosial menggunakan SNA.
                3. Mengidentifikasi **influencer potensial** berdasarkan sentimen dan sentralitas jaringan.
                """
            )
    except Exception as e:
        st.error(f"Gagal menampilkan deskripsi & tujuan: {e}")


def _render_metodologi_cards() -> None:
    """Tampilkan 2 kartu metodologi: SNA dan IndoBERT."""
    try:
        st.subheader("🔬 Metodologi")
        col_sna, col_bert = st.columns(2)

        with col_sna:
            st.markdown(
                """
                <div class="metric-card" style="border-left: 4px solid #1DA1F2;">
                    <div style="font-size:2rem;">🕸️</div>
                    <strong>Social Network Analysis (SNA)</strong><br><br>
                    <span style="color:#888;">
                    Memetakan hubungan antar pengguna (mention, reply, retweet)
                    untuk menghitung <em>degree centrality</em>, in/out-degree,
                    dan mengidentifikasi node influencer dalam jaringan.
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_bert:
            st.markdown(
                """
                <div class="metric-card" style="border-left: 4px solid #E53935;">
                    <div style="font-size:2rem;">🤖</div>
                    <strong>IndoBERT Sentiment Classification</strong><br><br>
                    <span style="color:#888;">
                    Model <code>mdhugol/indonesia-bert-sentiment-classification</code>
                    mengklasifikasi komentar menjadi <strong>positif</strong>,
                    <strong>netral</strong>, atau <strong>negatif</strong>
                    dengan skor confidence.
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    except Exception as e:
        st.error(f"Gagal menampilkan kartu metodologi: {e}")


def _render_metric_cards(stats: dict) -> None:
    """Tampilkan 4 kartu metrik KPI utama."""
    try:
        st.subheader("📈 Ringkasan Data")
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            render_metric_card(
                "Total Data",
                f"{stats['total_data']:,}",
                delta="Semua layanan",
                icon="📊",
            )
        with c2:
            render_metric_card(
                "Total Platform",
                str(stats["total_platform"]),
                delta="Twitter, IG, TikTok",
                icon="🌐",
            )
        with c3:
            render_metric_card(
                "Sentimen Terklasifikasi",
                f"{stats['total_sentiment']:,}",
                delta="IndoBERT",
                icon="😊",
            )
        with c4:
            render_metric_card(
                "Node + Edge SNA",
                f"{stats['total_node']} + {stats['total_edge']}",
                delta=f"{stats['total_edge']} relasi",
                icon="🔗",
            )
    except Exception as e:
        st.error(f"Gagal menampilkan kartu metrik: {e}")


def _render_model_status() -> None:
    """Tampilkan status ketersediaan model per layanan."""
    try:
        st.subheader("🧠 Status Model")
        m1, m2, m3 = st.columns(3)

        with m1:
            st.markdown(
                """
                <div class="metric-card" style="border-left: 4px solid #4CAF50;">
                    <span class="badge badge-ready">🟢 Model Siap</span><br><br>
                    <strong>IndiHome</strong><br>
                    <span style="color:#888;">Analisis sentimen & SNA tersedia.</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Lihat Analisis", key="btn_lihat_analisis_indihome", use_container_width=True):
                st.info(
                    "Pilih menu **Analisis Sentimen** atau **Analisis Jaringan Sosial** "
                    "di sidebar kiri untuk melihat hasil IndiHome."
                )

        with m2:
            st.markdown(
                """
                <div class="metric-card" style="border-left: 4px solid #9E9E9E; opacity: 0.65;">
                    <span class="badge badge-soon">🟡 Coming Soon</span><br><br>
                    <strong>IndiBiz</strong><br>
                    <span style="color:#888;">Model sedang dalam pengembangan.</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.button(
                "Belum Tersedia",
                key="btn_indibiz_soon",
                disabled=True,
                use_container_width=True,
            )

        with m3:
            st.markdown(
                """
                <div class="metric-card" style="border-left: 4px solid #9E9E9E; opacity: 0.65;">
                    <span class="badge badge-soon">🟡 Coming Soon</span><br><br>
                    <strong>Telkomsel</strong><br>
                    <span style="color:#888;">Model sedang dalam pengembangan.</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.button(
                "Belum Tersedia",
                key="btn_telkomsel_soon",
                disabled=True,
                use_container_width=True,
            )
    except Exception as e:
        st.error(f"Gagal menampilkan status model: {e}")


def _render_preview_chart() -> None:
    """Tampilkan pie chart kecil distribusi sentimen IndiHome."""
    try:
        st.subheader("👁️ Pratinjau Sentimen IndiHome")
        df_indihome = load_sentiment_data("IndiHome")
        fig = pie_chart_sentiment(df_indihome, title="Distribusi Sentimen IndiHome")
        fig.update_layout(height=320, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Gagal menampilkan pratinjau chart: {e}")


def _render_timeline() -> None:
    """Tampilkan timeline sederhana tahapan penelitian."""
    try:
        st.subheader("🗓️ Timeline Penelitian")
        st.markdown(
            """
            <div class="metric-card">
                <div style="display:flex; justify-content:space-between; align-items:center;
                            flex-wrap:wrap; gap:0.5rem; text-align:center;">
                    <div style="flex:1; min-width:100px;">
                        <div style="font-size:1.4rem;">📅</div>
                        <strong>Oktober</strong><br>
                        <span style="color:#888; font-size:0.85rem;">Pengumpulan Data</span>
                    </div>
                    <div style="color:#1DA1F2; font-size:1.2rem;">→</div>
                    <div style="flex:1; min-width:100px;">
                        <div style="font-size:1.4rem;">🔍</div>
                        <strong>November</strong><br>
                        <span style="color:#888; font-size:0.85rem;">Analisis Sentimen & SNA</span>
                    </div>
                    <div style="color:#1DA1F2; font-size:1.2rem;">→</div>
                    <div style="flex:1; min-width:100px;">
                        <div style="font-size:1.4rem;">📊</div>
                        <strong>Desember</strong><br>
                        <span style="color:#888; font-size:0.85rem;">Pembangunan Dashboard</span>
                    </div>
                    <div style="color:#1DA1F2; font-size:1.2rem;">→</div>
                    <div style="flex:1; min-width:100px;">
                        <div style="font-size:1.4rem;">📝</div>
                        <strong>Januari</strong><br>
                        <span style="color:#888; font-size:0.85rem;">Penyusunan Laporan</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as e:
        st.error(f"Gagal menampilkan timeline: {e}")


def render_home() -> None:
    """Menampilkan halaman beranda dengan KPI dan ringkasan penelitian."""
    try:
        _render_banner_header()
        _render_deskripsi_tujuan()
        _render_metodologi_cards()

        stats = _get_dashboard_stats()
        _render_metric_cards(stats)
        _render_model_status()
        _render_preview_chart()
        _render_timeline()

    except Exception as e:
        st.error(f"Gagal memuat halaman beranda: {e}")
