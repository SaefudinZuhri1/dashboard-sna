"""Halaman rekomendasi konten dan influencer berbasis SNA serta analisis topik."""

from __future__ import annotations

from html import escape

import networkx as nx
import pandas as pd
import streamlit as st

from utils.css_loader import (
    inject_platform_badge,
    render_coming_soon_card,
    render_data_badge,
    render_metric_card,
    render_page_header,
)
from utils.data_loader import (
    load_sentiment_data,
    load_sna_data,
    sentiment_file_exists,
    sna_file_exists,
)
from utils.dummy_data import get_dummy_influencer_data
from utils.preprocessor import clean_text
from utils.topic_classifier import apply_topics, get_dominant_keywords, get_top_topics

# Layanan yang tersedia pada fase ini.
LAYANAN_OPTIONS = ["IndiHome", "IndiBiz", "Telkomsel"]
READY_SERVICES = {"IndiHome"}
PLATFORMS = ("twitter", "instagram", "tiktok")

# Kata yang menandai akun resmi/brand agar tidak masuk ranking influencer individu.
BRAND_KEYWORDS = (
    "indihome",
    "indihomecare",
    "telkomsel",
    "telkomindonesia",
    "telkom",
    "indibiz",
)

PLATFORM_META = {
    "twitter": {"label": "Twitter/X", "icon": "🐦", "border": "#1DA1F2"},
    "instagram": {"label": "Instagram", "icon": "📸", "border": "#833AB4"},
    "tiktok": {"label": "TikTok", "icon": "🎵", "border": "#222222"},
}

# Fallback topik sesuai spesifikasi Fase 15.
DUMMY_POSITIVE_TOPICS = pd.DataFrame(
    [
        {"topik": "Apresiasi Kecepatan Internet", "jumlah_komentar": 45, "pct": 42.9},
        {"topik": "Layanan CS Responsif", "jumlah_komentar": 32, "pct": 30.5},
        {"topik": "Teknisi Cepat dan Profesional", "jumlah_komentar": 28, "pct": 26.7},
    ]
)
DUMMY_NEGATIVE_TOPICS = pd.DataFrame(
    [
        {"topik": "Keluhan Internet Lemot/Ngelag", "jumlah_komentar": 89, "pct": 42.4},
        {"topik": "Koneksi Putus-putus", "jumlah_komentar": 67, "pct": 31.9},
        {"topik": "Gangguan Total/Internet Mati", "jumlah_komentar": 54, "pct": 25.7},
    ]
)

DUMMY_TOPIC_KEYWORDS = {
    "Apresiasi Kecepatan Internet": ["cepat", "lancar", "stabil"],
    "Layanan CS Responsif": ["responsif", "cepat", "dibantu"],
    "Teknisi Cepat dan Profesional": ["teknisi", "profesional", "perbaikan"],
    "Keluhan Internet Lemot/Ngelag": ["lemot", "ngelag", "lambat"],
    "Koneksi Putus-putus": ["putus", "disconnect", "tidak stabil"],
    "Gangguan Total/Internet Mati": ["gangguan", "mati", "offline"],
}

CONTENT_TYPES = {
    ("twitter", "negative"): ["Thread Informatif", "Respons Keluhan", "Klarifikasi Cepat"],
    ("instagram", "positive"): [
        "Infografik Edukasi",
        "Testimonial Visual",
        "Carousel Cerita Positif",
    ],
    ("tiktok", "positive"): ["Video Pendek", "Behind-the-Scenes", "Edukasi Ringan"],
    ("tiktok", "negative"): ["Respons Kreatif", "Video Klarifikasi", "Edukasi Ringan"],
}

CONTENT_IDEAS = {
    ("twitter", "negative"): (
        "Susun thread singkat tentang \"{topic}\" yang memuat kondisi terkini, langkah "
        "troubleshooting, kanal bantuan resmi, dan ajakan mengirim detail pelanggan melalui DM."
    ),
    ("instagram", "positive"): (
        "Buat carousel visual untuk memperkuat \"{topic}\" melalui fakta layanan, kutipan "
        "pengalaman pelanggan, dan ajakan berbagi pengalaman positif."
    ),
    ("tiktok", "positive"): (
        "Produksi video 30–60 detik tentang \"{topic}\" dengan hook pada tiga detik pertama, "
        "cuplikan pengalaman nyata, dan penutup yang mudah dibagikan."
    ),
    ("tiktok", "negative"): (
        "Buat video respons kreatif mengenai \"{topic}\" yang menjelaskan penyebab, proses "
        "penanganan, dan langkah praktis pelanggan dengan bahasa ringan."
    ),
}


@st.cache_data
def _load_topic_source(layanan: str) -> pd.DataFrame:
    """Muat data sentimen dan tambahkan hasil klasifikasi topik."""
    try:
        df = load_sentiment_data(layanan).copy()
        if df.empty:
            return pd.DataFrame()

        if "content_clean" not in df.columns:
            if "content" not in df.columns:
                raise ValueError("Kolom 'content' tidak ditemukan pada data sentimen.")
            df["content_clean"] = df["content"].astype(str).apply(clean_text)

        if "topic" not in df.columns:
            df = apply_topics(df)
        return df
    except Exception as exc:
        st.error(f"Gagal menyiapkan data topik: {exc}")
        return pd.DataFrame()


@st.cache_data
def calculate_top_influencers(df_sna: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Hitung tiga influencer teratas pada setiap platform dari data SNA."""
    try:
        empty_result = {platform: pd.DataFrame() for platform in PLATFORMS}
        if df_sna is None or df_sna.empty:
            return empty_result

        required = {"source", "target", "followers", "platform"}
        missing = sorted(required.difference(df_sna.columns))
        if missing:
            raise ValueError(f"Kolom SNA belum lengkap: {', '.join(missing)}")

        work = df_sna.copy()
        work["source"] = work["source"].astype(str).str.strip().str.lstrip("@")
        work["target"] = work["target"].astype(str).str.strip().str.lstrip("@")
        work["platform"] = work["platform"].astype(str).str.lower().str.strip()
        work["followers"] = pd.to_numeric(work["followers"], errors="coerce").fillna(0)
        work = work[
            work["source"].ne("")
            & work["target"].ne("")
            & work["source"].str.lower().ne("nan")
            & work["target"].str.lower().ne("nan")
        ].copy()

        result: dict[str, pd.DataFrame] = {}
        for platform in PLATFORMS:
            platform_df = work[work["platform"] == platform].copy()
            if platform_df.empty:
                result[platform] = pd.DataFrame()
                continue

            followers_map = (
                platform_df.groupby("source", as_index=True)["followers"].max().to_dict()
            )

            if platform == "twitter":
                # Centrality dihitung dari graf lengkap. Akun resmi baru dikeluarkan saat ranking.
                graph = nx.from_pandas_edgelist(
                    platform_df,
                    source="source",
                    target="target",
                    create_using=nx.DiGraph(),
                )
                centrality = nx.degree_centrality(graph) if graph.number_of_nodes() > 1 else {}

                rows = []
                for username in graph.nodes:
                    if _is_brand_account(username):
                        continue
                    rows.append(
                        {
                            "username": str(username),
                            "followers": int(followers_map.get(username, 0)),
                            "degree_centrality": float(centrality.get(username, 0.0)),
                            "platform": platform,
                            "role": "Structural",
                        }
                    )

                ranked = pd.DataFrame(rows)
                if not ranked.empty:
                    ranked = ranked.sort_values(
                        ["degree_centrality", "followers", "username"],
                        ascending=[False, False, True],
                    )
            else:
                candidates = platform_df[
                    ~platform_df["source"].apply(_is_brand_account)
                ].copy()
                ranked = (
                    candidates.groupby("source", as_index=False)["followers"]
                    .max()
                    .rename(columns={"source": "username"})
                )
                if not ranked.empty:
                    ranked["degree_centrality"] = 0.0
                    ranked["platform"] = platform
                    ranked["role"] = "Reach"
                    ranked = ranked.sort_values(
                        ["followers", "username"],
                        ascending=[False, True],
                    )

            result[platform] = ranked.head(3).reset_index(drop=True)

        return result
    except Exception as exc:
        st.error(f"Gagal menghitung top influencer: {exc}")
        return {platform: pd.DataFrame() for platform in PLATFORMS}


def _is_brand_account(username: str) -> bool:
    """Periksa apakah username merupakan akun resmi/brand Telkom Group."""
    try:
        normalized = str(username).lower().strip().lstrip("@")
        return any(keyword in normalized for keyword in BRAND_KEYWORDS)
    except Exception:
        return False


def _dummy_influencers() -> dict[str, pd.DataFrame]:
    """Bangun fallback influencer yang konsisten dengan baseline penelitian."""
    baseline = {
        "twitter": [
            ("dewa_brahma", 76, 0.138, "Structural"),
            ("bellaablee", 174, 0.103, "Structural"),
            ("cobeyisyolkek", 219, 0.103, "Structural"),
        ],
        "instagram": [
            ("dkdiki_", 1588, 0.0, "Reach"),
            ("akri64", 1110, 0.0, "Reach"),
            ("faishalfrss", 1060, 0.0, "Reach"),
        ],
        "tiktok": [
            ("sutardi.wasimin", 1612, 0.0, "Reach"),
            ("akakpro46", 620, 0.0, "Reach"),
            ("riswanda822", 559, 0.0, "Reach"),
        ],
    }

    try:
        # Tetap validasi sumber dummy proyek agar fallback mengikuti kontrak modul yang ada.
        get_dummy_influencer_data()
    except Exception:
        # Baseline lokal tetap tersedia jika modul dummy mengalami gangguan.
        pass

    result: dict[str, pd.DataFrame] = {}
    for platform, rows in baseline.items():
        result[platform] = pd.DataFrame(
            [
                {
                    "username": username,
                    "followers": followers,
                    "degree_centrality": degree,
                    "platform": platform,
                    "role": role,
                }
                for username, followers, degree, role in rows
            ]
        )
    return result


def _complete_with_fallback(
    calculated: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """Lengkapi ranking yang kurang dari tiga akun menggunakan data dummy."""
    try:
        fallback = _dummy_influencers()
        completed: dict[str, pd.DataFrame] = {}

        for platform in PLATFORMS:
            primary = calculated.get(platform, pd.DataFrame())
            if primary is None:
                primary = pd.DataFrame()

            existing = (
                set(primary["username"].astype(str))
                if not primary.empty and "username" in primary.columns
                else set()
            )
            additions = fallback[platform][
                ~fallback[platform]["username"].astype(str).isin(existing)
            ]
            combined = pd.concat([primary, additions], ignore_index=True)
            completed[platform] = combined.head(3).reset_index(drop=True)

        return completed
    except Exception as exc:
        st.error(f"Gagal menyiapkan fallback influencer: {exc}")
        return _dummy_influencers()


def _get_top_topic_data(
    layanan: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Ambil data sumber beserta tiga topik positif dan negatif teratas."""
    try:
        source_df = _load_topic_source(layanan)

        # Saat file asli tidak tersedia, gunakan baseline fallback yang disepakati.
        if not sentiment_file_exists(layanan):
            return (
                source_df,
                DUMMY_POSITIVE_TOPICS.copy(),
                DUMMY_NEGATIVE_TOPICS.copy(),
            )

        positive = (
            get_top_topics(source_df, "positive", top_n=5)
            if not source_df.empty
            else pd.DataFrame()
        )
        negative = (
            get_top_topics(source_df, "negative", top_n=5)
            if not source_df.empty
            else pd.DataFrame()
        )

        def complete_topics(topics: pd.DataFrame, fallback: pd.DataFrame) -> pd.DataFrame:
            """Lengkapi topik aktual hingga tiga baris dan abaikan kategori Lainnya."""
            if topics is None or topics.empty:
                return fallback.copy()
            filtered = topics[
                topics["topik"].astype(str).str.lower().str.strip().ne("lainnya")
            ].copy()
            existing = set(filtered["topik"].astype(str))
            additions = fallback[~fallback["topik"].astype(str).isin(existing)]
            return pd.concat([filtered, additions], ignore_index=True).head(3)

        return (
            source_df,
            complete_topics(positive, DUMMY_POSITIVE_TOPICS).reset_index(drop=True),
            complete_topics(negative, DUMMY_NEGATIVE_TOPICS).reset_index(drop=True),
        )
    except Exception as exc:
        st.error(f"Gagal mengambil topik dominan: {exc}")
        return (
            pd.DataFrame(),
            DUMMY_POSITIVE_TOPICS.copy(),
            DUMMY_NEGATIVE_TOPICS.copy(),
        )


def _content_type(platform: str, sentiment: str, index: int) -> str:
    """Pilih jenis konten sesuai platform, sentimen, dan urutan rekomendasi."""
    try:
        options = CONTENT_TYPES.get((platform, sentiment), ["Konten Media Sosial"])
        return options[index % len(options)]
    except Exception:
        return "Konten Media Sosial"


def _content_idea(platform: str, sentiment: str, topic: str) -> str:
    """Buat ide konten deskriptif berdasarkan platform dan topik."""
    try:
        template = CONTENT_IDEAS.get(
            (platform, sentiment),
            "Buat konten yang relevan dan mudah dipahami mengenai \"{topic}\".",
        )
        return template.format(topic=topic)
    except Exception:
        return f'Buat konten yang relevan mengenai "{topic}".'


def generate_recommendations(
    influencers: dict[str, pd.DataFrame],
    top_positive_topics: pd.DataFrame,
    top_negative_topics: pd.DataFrame,
) -> list[dict]:
    """Hasilkan rekomendasi konten sesuai aturan matching pada Fase 15."""
    try:
        recommendations: list[dict] = []
        positive_records = top_positive_topics.to_dict("records")
        negative_records = top_negative_topics.to_dict("records")

        # Twitter: tiga influencer struktural dipasangkan dengan tiga topik negatif.
        twitter_df = influencers.get("twitter", pd.DataFrame())
        for index, (_, influencer) in enumerate(twitter_df.head(3).iterrows()):
            if not negative_records:
                break
            topic = str(negative_records[index % len(negative_records)]["topik"])
            recommendations.append(
                {
                    "platform": "twitter",
                    "influencer": str(influencer.get("username", "")),
                    "followers": int(influencer.get("followers", 0)),
                    "content_type": _content_type("twitter", "negative", index),
                    "topic": topic,
                    "topic_sentiment": "negative",
                    "content_idea": _content_idea("twitter", "negative", topic),
                    "strategy": "Respons/Klarifikasi",
                }
            )

        # Instagram: tiga akun dengan reach tinggi dipasangkan dengan topik positif.
        instagram_df = influencers.get("instagram", pd.DataFrame())
        for index, (_, influencer) in enumerate(instagram_df.head(3).iterrows()):
            if not positive_records:
                break
            topic = str(positive_records[index % len(positive_records)]["topik"])
            recommendations.append(
                {
                    "platform": "instagram",
                    "influencer": str(influencer.get("username", "")),
                    "followers": int(influencer.get("followers", 0)),
                    "content_type": _content_type("instagram", "positive", index),
                    "topic": topic,
                    "topic_sentiment": "positive",
                    "content_idea": _content_idea("instagram", "positive", topic),
                    "strategy": "Amplifikasi",
                }
            )

        # TikTok: influencer pertama untuk topik positif, dua berikutnya untuk topik negatif.
        tiktok_df = influencers.get("tiktok", pd.DataFrame())
        assignments = []
        if positive_records:
            assignments.append(("positive", positive_records[0]))
        assignments.extend(
            ("negative", topic_record) for topic_record in negative_records[:2]
        )

        for index, (_, influencer) in enumerate(tiktok_df.head(3).iterrows()):
            if index >= len(assignments):
                break
            sentiment, topic_record = assignments[index]
            topic = str(topic_record["topik"])
            recommendations.append(
                {
                    "platform": "tiktok",
                    "influencer": str(influencer.get("username", "")),
                    "followers": int(influencer.get("followers", 0)),
                    "content_type": _content_type("tiktok", sentiment, index),
                    "topic": topic,
                    "topic_sentiment": sentiment,
                    "content_idea": _content_idea("tiktok", sentiment, topic),
                    "strategy": (
                        "Amplifikasi" if sentiment == "positive" else "Respons/Klarifikasi"
                    ),
                }
            )

        return recommendations
    except Exception as exc:
        st.error(f"Gagal menghasilkan rekomendasi: {exc}")
        return []


def _format_username(username: str) -> str:
    """Tambahkan simbol @ pada username dan amankan teks untuk HTML."""
    try:
        value = str(username).strip().lstrip("@") or "unknown"
        return f"@{escape(value)}"
    except Exception:
        return "@unknown"


def _count_unique_influencers(influencers: dict[str, pd.DataFrame]) -> int:
    """Hitung jumlah influencer unik dari seluruh platform."""
    try:
        usernames: set[str] = set()
        for platform_df in influencers.values():
            if platform_df is not None and not platform_df.empty:
                usernames.update(platform_df["username"].astype(str).tolist())
        return len(usernames)
    except Exception:
        return 0


def _render_influencer_card(row: pd.Series, platform: str) -> None:
    """Tampilkan satu kartu influencer."""
    try:
        meta = PLATFORM_META[platform]
        username = _format_username(row.get("username", ""))
        followers = int(row.get("followers", 0))
        degree = float(row.get("degree_centrality", 0.0))
        role = escape(str(row.get("role", "Reach")))
        degree_html = f" · Degree: {degree:.3f}" if platform == "twitter" else ""

        st.markdown(
            f"""
            <div class="metric-card" style="border-left:4px solid {meta['border']};">
                <strong>{username}</strong><br>
                <span style="color:#888;font-size:0.85rem;">
                    Followers: {followers:,}{degree_html}
                </span><br>
                <span class="badge badge-user" style="margin-top:0.45rem;">
                    🏷️ Peran: {role}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Gagal menampilkan kartu influencer: {exc}")


def _topic_keywords(
    source_df: pd.DataFrame,
    topic_name: str,
    sentiment: str,
) -> list[str]:
    """Ambil tiga kata kunci dominan atau fallback kata kunci topik."""
    try:
        keywords = get_dominant_keywords(source_df, topic_name, sentiment)[:3]
        if keywords:
            return keywords
        return DUMMY_TOPIC_KEYWORDS.get(topic_name, ["layanan", "pelanggan", "internet"])[:3]
    except Exception:
        return DUMMY_TOPIC_KEYWORDS.get(topic_name, ["layanan", "pelanggan", "internet"])[:3]


def _render_topic_column(
    topics: pd.DataFrame,
    source_df: pd.DataFrame,
    sentiment: str,
    title: str,
    subtitle: str,
) -> None:
    """Tampilkan daftar topik, progress bar, dan badge kata kunci."""
    try:
        st.markdown(f"#### {title}")
        st.caption(subtitle)

        if topics is None or topics.empty:
            st.info("Belum ada topik yang dapat ditampilkan.")
            return

        max_count = max(int(topics["jumlah_komentar"].max()), 1)
        for _, row in topics.iterrows():
            topic_name = str(row.get("topik", "Topik Layanan"))
            count = int(row.get("jumlah_komentar", 0))
            progress_value = min(max(count / max_count, 0.0), 1.0)
            keywords = _topic_keywords(source_df, topic_name, sentiment)
            badges = " ".join(
                f'<span class="badge badge-user">{escape(str(keyword))}</span>'
                for keyword in keywords
            )

            st.markdown(
                f"""
                <div class="metric-card" style="margin-bottom:0.45rem;">
                    <strong>{escape(topic_name)}</strong><br>
                    <span style="color:#888;font-size:0.85rem;">{count:,} komentar</span>
                    <div style="margin-top:0.55rem;">{badges}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.progress(progress_value, text=f"{count:,} komentar")
    except Exception as exc:
        st.error(f"Gagal menampilkan topik: {exc}")


def _render_recommendation_card(recommendation: dict) -> None:
    """Tampilkan satu kartu rekomendasi konten."""
    try:
        platform = str(recommendation.get("platform", "twitter")).lower()
        meta = PLATFORM_META.get(platform, PLATFORM_META["twitter"])
        strategy = str(recommendation.get("strategy", "Respons/Klarifikasi"))
        strategy_html = (
            '<span class="badge badge-positive">🟢 Amplifikasi</span>'
            if strategy == "Amplifikasi"
            else '<span class="badge badge-negative">🔴 Respons/Klarifikasi</span>'
        )

        st.markdown(
            f"""
            <div class="metric-card" style="border-top:3px solid {meta['border']};">
                <div style="margin-bottom:0.55rem;">
                    {inject_platform_badge(platform)} {meta['icon']}
                </div>
                <strong>{_format_username(recommendation.get('influencer', ''))}</strong>
                <span style="color:#888;font-size:0.85rem;">
                    · {int(recommendation.get('followers', 0)):,} followers
                </span><br><br>
                {strategy_html}<br><br>
                <span style="color:#888;font-size:0.82rem;">Topik yang diangkat</span><br>
                <strong>{escape(str(recommendation.get('topic', '—')))}</strong><br><br>
                <span style="color:#888;font-size:0.82rem;">Jenis konten</span><br>
                <span class="badge badge-user">
                    {escape(str(recommendation.get('content_type', '—')))}
                </span><br><br>
                <span style="color:#888;font-size:0.82rem;">Ide konten</span><br>
                <span style="font-size:0.9rem;line-height:1.5;">
                    {escape(str(recommendation.get('content_idea', '—')))}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Gagal menampilkan rekomendasi konten: {exc}")


def _render_narrative(
    influencers: dict[str, pd.DataFrame],
    positive_topics: pd.DataFrame,
    negative_topics: pd.DataFrame,
) -> None:
    """Tampilkan narasi rekomendasi strategis otomatis dalam tiga paragraf."""
    try:
        twitter_top = influencers["twitter"].iloc[0]
        instagram_top = influencers["instagram"].iloc[0]
        negative_top = negative_topics.iloc[0]
        positive_top = positive_topics.iloc[0]

        twitter_username = _format_username(twitter_top["username"])
        twitter_degree = float(twitter_top["degree_centrality"])
        instagram_username = _format_username(instagram_top["username"])
        negative_name = escape(str(negative_top["topik"]))
        negative_count = int(negative_top["jumlah_komentar"])
        positive_name = escape(str(positive_top["topik"]))

        paragraph_1 = (
            f"Akun Twitter {twitter_username} direkomendasikan sebagai influencer struktural utama "
            f"karena memiliki degree centrality tertinggi sebesar {twitter_degree:.3f}. Posisi tersebut "
            f"membuat akun ini relevan untuk membantu klarifikasi cepat, menyebarkan thread informatif, "
            f"dan menjawab pertanyaan publik dalam jaringan percakapan yang diamati."
        )
        paragraph_2 = (
            f"Prioritas respons perlu diarahkan pada topik <strong>{negative_name}</strong> yang tercatat "
            f"sebanyak {negative_count:,} komentar. Strategi yang disarankan adalah menggabungkan thread "
            f"klarifikasi di Twitter dengan video respons singkat di TikTok agar informasi penanganan "
            f"gangguan dapat menjangkau pengguna secara cepat dan mudah dipahami."
        )
        paragraph_3 = (
            f"Untuk memperkuat persepsi positif, topik <strong>{positive_name}</strong> dapat diamplifikasi "
            f"melalui konten visual bersama {instagram_username}. Format carousel, infografik edukasi, "
            f"dan testimonial pelanggan dapat digunakan untuk memperluas jangkauan narasi positif "
            f"mengenai layanan IndiHome."
        )

        with st.expander("📋 Baca Narasi Rekomendasi Strategis"):
            st.markdown(paragraph_1, unsafe_allow_html=True)
            st.markdown(paragraph_2, unsafe_allow_html=True)
            st.markdown(paragraph_3, unsafe_allow_html=True)
    except Exception as exc:
        st.error(f"Gagal menampilkan narasi rekomendasi: {exc}")


def _render_indihome_page(layanan: str) -> None:
    """Render enam bagian halaman rekomendasi untuk layanan IndiHome."""
    try:
        # Muat data SNA dan topik, lalu aktifkan fallback bila hasil tidak lengkap.
        sna_is_real = sna_file_exists()
        sna_df = load_sna_data()
        calculated = (
            calculate_top_influencers(sna_df)
            if sna_is_real
            else {platform: pd.DataFrame() for platform in PLATFORMS}
        )
        influencers = _complete_with_fallback(calculated)
        topic_source, positive_topics, negative_topics = _get_top_topic_data(layanan)
        recommendations = generate_recommendations(
            influencers,
            positive_topics,
            negative_topics,
        )

        # Penanda sumber data untuk mencegah salah interpretasi data dummy sebagai hasil aktual.
        source_col_1, source_col_2 = st.columns(2)
        with source_col_1:
            st.caption("Sumber data SNA")
            render_data_badge(sna_is_real)
        with source_col_2:
            st.caption("Sumber data sentimen/topik")
            render_data_badge(sentiment_file_exists(layanan))

        st.divider()

        # BAGIAN 2 — Metric Cards.
        dominant_positive = str(positive_topics.iloc[0]["topik"])
        dominant_negative = str(negative_topics.iloc[0]["topik"])
        metric_1, metric_2, metric_3 = st.columns(3)
        with metric_1:
            render_metric_card(
                "Total Influencer Teridentifikasi",
                str(_count_unique_influencers(influencers)),
                icon="🎯",
            )
        with metric_2:
            render_metric_card("Topik Positif Dominan", dominant_positive, icon="📢")
        with metric_3:
            render_metric_card("Topik Negatif Dominan", dominant_negative, icon="⚠️")

        st.divider()

        # BAGIAN 3 — Top Influencer per Platform.
        st.subheader("👥 Top Influencer per Platform")
        platform_columns = st.columns(3)
        for column, platform in zip(platform_columns, PLATFORMS):
            meta = PLATFORM_META[platform]
            with column:
                st.markdown(
                    f"""
                    <div style="font-weight:700;border-bottom:3px solid {meta['border']};
                    padding-bottom:0.4rem;margin-bottom:0.7rem;">
                        {meta['icon']} {meta['label']}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                for _, influencer in influencers[platform].iterrows():
                    _render_influencer_card(influencer, platform)

        st.divider()

        # BAGIAN 4 — Topik yang Perlu Diangkat.
        st.subheader("📋 Topik yang Perlu Diangkat")
        positive_col, negative_col = st.columns(2)
        with positive_col:
            _render_topic_column(
                positive_topics,
                topic_source,
                "positive",
                "🟢 Top 3 Topik Positif",
                "Konten untuk Diperkuat",
            )
        with negative_col:
            _render_topic_column(
                negative_topics,
                topic_source,
                "negative",
                "🔴 Top 3 Topik Negatif",
                "Isu yang Perlu Direspons",
            )

        st.divider()

        # BAGIAN 5 — Rekomendasi Konten.
        st.subheader("💡 Rekomendasi Konten")
        if not recommendations:
            st.info("Belum ada rekomendasi konten yang dapat ditampilkan.")
        else:
            recommendation_columns = st.columns(3)
            for index, recommendation in enumerate(recommendations):
                with recommendation_columns[index % 3]:
                    _render_recommendation_card(recommendation)

        st.divider()

        # BAGIAN 6 — Narasi Rekomendasi.
        _render_narrative(influencers, positive_topics, negative_topics)
    except Exception as exc:
        st.error(f"Gagal memuat rekomendasi IndiHome: {exc}")


def render_recommendation() -> None:
    """Entry point halaman Rekomendasi Konten dan Influencer."""
    try:
        # BAGIAN 1 — Header dan selector layanan.
        render_page_header(
            "🎯 Rekomendasi Konten & Influencer",
            "Berdasarkan hasil SNA dan Analisis Topik IndiHome",
        )
        layanan = st.selectbox(
            "Pilih Layanan",
            options=LAYANAN_OPTIONS,
            index=0,
            key="recommendation_service_selector",
            help="IndiHome sudah tersedia. IndiBiz dan Telkomsel masih Coming Soon.",
        )

        if layanan not in READY_SERVICES:
            render_coming_soon_card(layanan, "Rekomendasi konten & influencer")
            return

        _render_indihome_page(layanan)
    except Exception as exc:
        st.error(f"Gagal memuat halaman rekomendasi: {exc}")
