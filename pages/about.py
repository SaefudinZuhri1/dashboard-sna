"""Halaman tentang proyek penelitian."""

import streamlit as st

from utils.css_loader import render_page_header


def render_about() -> None:
    """Menampilkan informasi penelitian, metodologi, dan referensi."""
    try:
        render_page_header("ℹ️ Tentang", "Informasi penelitian dan dashboard")

        st.subheader("Identitas Peneliti")
        st.markdown(
            """
            - **Nama:** Aulia Rahmadiva Wardana
            - **NPM:** 184220019
            - **Program Studi:** S1 Sains Data — Universitas Logistik dan Bisnis Internasional (ULBI) Bandung
            - **Dosen Pembimbing:** Woro Isti Rahayu, S.T., M.T.
            - **Dosen Penguji:** Dr. Riharsono Prastyantoro, S.Si., M.T.
            """
        )

        st.subheader("Judul Penelitian")
        st.markdown(
            """
            *Analisis Jaringan dan Sentimen Publik Terhadap Layanan Digital
            PT. Telekomunikasi Indonesia untuk Identifikasi Influencer di Media Sosial
            Menggunakan Social Network Analysis (SNA) dan IndoBERT*
            """
        )

        st.subheader("Metodologi Ringkas")
        st.markdown(
            """
            1. **Pengumpulan data** komentar media sosial (Twitter/X, Instagram, TikTok) periode Nov–Des 2025.
            2. **Analisis sentimen** menggunakan model IndoBERT fine-tuned untuk Bahasa Indonesia.
            3. **Social Network Analysis** untuk memetakan interaksi dan mengidentifikasi influencer.
            4. **Visualisasi & insight** melalui dashboard interaktif berbasis Streamlit.
            """
        )

        st.subheader("Tech Stack")
        st.markdown(
            """
            | Kategori | Teknologi |
            |----------|-----------|
            | Framework | Streamlit 1.35.0 |
            | Database | SQLite (users) |
            | NLP | Transformers 4.41.2, IndoBERT |
            | ML | PyTorch 2.3.0 (CPU) |
            | Visualisasi | Plotly 5.21.0, Matplotlib, WordCloud |
            | SNA | NetworkX 3.3, Pyvis 0.3.2 |
            | Data | Pandas 2.2.2 |
            """
        )

        st.subheader("Referensi Utama")
        st.markdown(
            """
            1. Devlin, J., et al. (2019). BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding. *NAACL*.
            2. Willy, H., et al. (2021). Indonesian BERT Sentiment Classification. HuggingFace Model Hub.
            3. Wasserman, S., & Faust, K. (1994). *Social Network Analysis: Methods and Applications*. Cambridge University Press.
            4. Liu, B. (2012). *Sentiment Analysis and Opinion Mining*. Morgan & Claypool.
            5. Borgatti, S. P., et al. (2009). Network Analysis in the Social Sciences. *Science*, 323(5916).
            6. Hutto, C., & Gilbert, E. (2014). VADER: A Parsimonious Rule-based Model for Sentiment Analysis. *ICWSM*.
            7. Krippendorff, K. (2018). *Content Analysis: An Introduction to Its Methodology*. SAGE Publications.
            """
        )

        st.subheader("Catatan Interpretasi Akademik")
        st.info(
            "Hasil analisis sentimen dan SNA pada dashboard ini bersifat **eksploratif** "
            "dan mencerminkan opini publik pada periode dan platform yang diteliti. "
            "Temuan tidak dapat digeneralisasi ke seluruh populasi pengguna Telkom Group. "
            "Identifikasi influencer berdasarkan metrik struktural jaringan (degree centrality) "
            "dan bukan merupakan rekomendasi endorsement resmi."
        )

        st.caption("Versi Dashboard: 1.0.0 | Terakhir diperbarui: Juni 2026")

    except Exception as e:
        st.error(f"Gagal memuat halaman tentang: {e}")
