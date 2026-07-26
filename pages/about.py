"""Halaman Tentang Penelitian untuk dashboard Telkom Group.

File ini hanya berisi tampilan halaman. Tidak ada proses analitik berat,
load CSV, atau load model ML pada halaman ini.
"""

from __future__ import annotations

from html import escape

import streamlit as st



_RESEARCH_TITLE = (
    "Analisis Jaringan dan Sentimen Publik Terhadap Layanan Digital "
    "PT. Telekomunikasi Indonesia untuk Identifikasi Influencer "
    "di Media Sosial Menggunakan SNA dan IndoBERT"
)

_ABSTRACT_ID = """
Media sosial menjadi ruang utama bagi masyarakat dalam menyampaikan opini dan
pengalaman terhadap layanan digital yang berpotensi memengaruhi citra perusahaan.
PT Telkom Indonesia sebagai perusahaan telekomunikasi strategis menghadapi
tantangan dalam memahami sentimen publik serta peran akun berpengaruh dalam
penyebaran informasi. Penelitian ini bertujuan untuk mengidentifikasi influencer
kunci dan menganalisis sentimen publik terhadap layanan digital PT Telkom
Indonesia, khususnya IndiHome, IndiBiz, dan Telkomsel, pada media sosial Twitter
(X), Instagram, dan TikTok. Identifikasi influencer dilakukan menggunakan
pendekatan Social Network Analysis (SNA) pada Twitter berbasis relasi mention,
reply, dan retweet, serta berdasarkan tingkat interaksi dan jangkauan akun pada
Instagram dan TikTok. Hasil analisis menunjukkan bahwa akun sutardi.wasimin di
TikTok dan faishalfrss di Instagram memiliki potensi jangkauan informasi yang
besar, sementara akun dewa_brahma di Twitter memiliki peran struktural penting
dalam jaringan percakapan meskipun jumlah pengikutnya relatif lebih rendah.
Analisis sentimen menggunakan model IndoBERT menunjukkan bahwa percakapan
publik didominasi oleh 14 sentimen negatif, 11 sentimen positif, dan 5 sentimen
netral dari total 30 komentar, dengan isu dominan berupa gangguan sinyal dan
kualitas jaringan internet. Berdasarkan temuan tersebut, penelitian ini menyimpulkan
bahwa peningkatan kualitas jaringan serta strategi komunikasi berbasis kolaborasi
dengan influencer kunci diperlukan untuk meningkatkan efektivitas layanan dan
membangun kepercayaan publik terhadap layanan Telkomsel.
""".strip()

_ABSTRACT_EN = """
Social media has become a primary platform for the public to express opinions and
share experiences regarding digital services, which can significantly influence
corporate reputation. As a strategic telecommunications company, PT Telkom
Indonesia faces challenges in understanding public sentiment and identifying
influential accounts involved in information dissemination. This study aims to
identify key influencers and analyze public sentiment toward PT Telkom Indonesia's
digital services, specifically IndiHome, IndiBiz, and Telkomsel, across Twitter (X),
Instagram, and TikTok. Influencer identification was conducted using a Social
Network Analysis (SNA) approach on Twitter based on mention, reply, and retweet
relationships, while on Instagram and TikTok it was based on account interaction
levels and reach. The results indicate that sutardi.wasimin on TikTok and
faishalfrss on Instagram have high information dissemination potential due to their
large audience reach, whereas dewa_brahma on Twitter plays a structurally
significant role in the conversation network despite having fewer followers.
Sentiment analysis using the IndoBERT model shows that public discussions are
dominated by 14 negative sentiments, followed by 11 positive sentiments and 5
neutral sentiments out of 30 user comments, with the dominant issue related to
signal disruption and internet network quality. These findings conclude that
improving network quality and implementing influencer-based communication
strategies are essential to enhance service effectiveness and strengthen public trust
in Telkomsel's digital services.
""".strip()

_METHOD_STEPS = [
    {
        "number": "01",
        "icon": "📥",
        "title": "Pengumpulan Data",
        "items": [
            "Scraping via Apify untuk Instagram dan TikTok",
            "Crawling manual Python untuk Twitter/X",
            "Data disiapkan dalam format CSV penelitian",
        ],
    },
    {
        "number": "02",
        "icon": "🕸️",
        "title": "Social Network Analysis",
        "items": [
            "NetworkX untuk konstruksi graf berarah",
            "Degree Centrality dan followers scoring",
            "Visualisasi jaringan interaktif menggunakan Pyvis",
        ],
    },
    {
        "number": "03",
        "icon": "🧠",
        "title": "Analisis Sentimen",
        "items": [
            "Preprocessing teks Bahasa Indonesia",
            "Model IndoBERT dari HuggingFace",
            "Klasifikasi positif, netral, dan negatif",
        ],
    },
    {
        "number": "04",
        "icon": "💡",
        "title": "Rekomendasi Strategis",
        "items": [
            "Identifikasi isu dominan percakapan publik",
            "Pemetaan influencer per layanan dan platform",
            "Strategi konten dan komunikasi digital",
        ],
    },
]

_TECH_STACK = [
    ("🐍", "Python"),
    ("🎈", "Streamlit"),
    ("🕸️", "NetworkX"),
    ("🌐", "Pyvis"),
    ("🤗", "HuggingFace"),
    ("📊", "Plotly"),
    ("🗃️", "SQLite"),
    ("🔐", "bcrypt"),
]


# -----------------------------------------------------------------------------
# Helper tampilan
# -----------------------------------------------------------------------------

def _inject_about_css() -> None:
    """Menyisipkan CSS khusus halaman Tentang Penelitian."""
    try:
        st.markdown(
            """
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');

                .about-v2-page {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    padding-bottom: 1.5rem;
                }

                @keyframes aboutV2TopGradient {
                    0% { background-position: 0% 50%; }
                    50% { background-position: 100% 50%; }
                    100% { background-position: 0% 50%; }
                }

                @keyframes aboutV2TopFloat {
                    0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
                    50% { transform: translate3d(0, -10px, 0) scale(1.03); }
                }

                @keyframes aboutV2TopScan {
                    0% { transform: translateX(-120%); opacity: 0; }
                    18% { opacity: 0.65; }
                    48% { opacity: 0.20; }
                    100% { transform: translateX(120%); opacity: 0; }
                }

                @keyframes aboutV2TopPulse {
                    0%, 100% { box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.24); transform: scale(1); }
                    50% { box-shadow: 0 0 0 12px rgba(255, 255, 255, 0); transform: scale(1.08); }
                }

                @keyframes aboutV2TopOrbit {
                    from { transform: rotate(0deg) translateX(8px) rotate(0deg); }
                    to { transform: rotate(360deg) translateX(8px) rotate(-360deg); }
                }

                @keyframes aboutV2TopShine {
                    0% { transform: translateX(-130%) skewX(-18deg); opacity: 0; }
                    18% { opacity: 0.42; }
                    42% { opacity: 0.08; }
                    100% { transform: translateX(150%) skewX(-18deg); opacity: 0; }
                }

                @keyframes aboutV2TopEntry {
                    from { opacity: 0; transform: translateY(12px); }
                    to { opacity: 1; transform: translateY(0); }
                }

                .about-v2-top-hero {
                    animation: aboutV2TopGradient 12s ease infinite, aboutV2TopEntry 0.5s ease both;
                    background:
                        radial-gradient(circle at 12% 15%, rgba(255, 255, 255, 0.18), transparent 18%),
                        radial-gradient(circle at 86% 18%, rgba(255, 152, 0, 0.26), transparent 22%),
                        radial-gradient(circle at 72% 92%, rgba(29, 161, 242, 0.26), transparent 28%),
                        linear-gradient(135deg, #070A12 0%, #141B2D 22%, #5E0F18 46%, #B71C1C 66%, #FF5252 100%);
                    background-size: 220% 220%;
                    border: 1px solid rgba(255, 255, 255, 0.16);
                    border-radius: 24px;
                    box-shadow:
                        0 24px 60px rgba(183, 28, 28, 0.24),
                        inset 0 1px 0 rgba(255, 255, 255, 0.18);
                    box-sizing: border-box;
                    color: #FFFFFF;
                    cursor: pointer;
                    isolation: isolate;
                    margin: 0.1rem 0 1.45rem 0;
                    overflow: hidden;
                    padding: clamp(1.35rem, 3.4vw, 2.35rem);
                    position: relative;
                    transition: border-color 0.28s ease, box-shadow 0.28s ease, filter 0.28s ease, transform 0.28s ease;
                }

                .about-v2-top-hero:focus,
                .about-v2-top-hero:hover {
                    border-color: rgba(255, 255, 255, 0.34);
                    box-shadow:
                        0 28px 72px rgba(229, 57, 53, 0.34),
                        0 0 0 1px rgba(255, 255, 255, 0.08),
                        inset 0 1px 0 rgba(255, 255, 255, 0.22);
                    filter: saturate(1.08);
                    transform: translateY(-3px) scale(1.004);
                    outline: none;
                }

                .about-v2-top-hero:active {
                    box-shadow:
                        0 18px 48px rgba(229, 57, 53, 0.28),
                        inset 0 1px 0 rgba(255, 255, 255, 0.18);
                    transform: translateY(-1px) scale(0.996);
                }

                .about-v2-top-hero::before {
                    animation: aboutV2TopScan 4.4s ease-in-out infinite;
                    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.26), transparent);
                    content: '';
                    height: 100%;
                    left: 0;
                    pointer-events: none;
                    position: absolute;
                    top: 0;
                    width: 46%;
                    z-index: -1;
                }

                .about-v2-top-hero::after {
                    background-image:
                        linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px);
                    background-size: 34px 34px;
                    content: '';
                    inset: 0;
                    mask-image: linear-gradient(90deg, transparent, #000 35%, #000 85%, transparent);
                    opacity: 0.28;
                    pointer-events: none;
                    position: absolute;
                    z-index: -2;
                }

                .about-v2-top-orb {
                    animation: aboutV2TopFloat 6.5s ease-in-out infinite;
                    border-radius: 999px;
                    filter: blur(1px);
                    opacity: 0.72;
                    pointer-events: none;
                    position: absolute;
                    z-index: -1;
                }

                .about-v2-top-orb-one {
                    background: radial-gradient(circle, rgba(255,82,82,0.72), transparent 70%);
                    height: 220px;
                    right: -70px;
                    top: -76px;
                    width: 220px;
                }

                .about-v2-top-orb-two {
                    animation-delay: -2.2s;
                    background: radial-gradient(circle, rgba(29,161,242,0.38), transparent 70%);
                    bottom: -88px;
                    height: 260px;
                    left: 40%;
                    width: 260px;
                }

                .about-v2-top-grid {
                    align-items: center;
                    display: grid;
                    gap: clamp(1rem, 3vw, 2.1rem);
                    grid-template-columns: minmax(0, 1fr) minmax(245px, 0.34fr);
                    position: relative;
                    z-index: 1;
                }

                .about-v2-top-eyebrow {
                    align-items: center;
                    background: rgba(255, 255, 255, 0.12);
                    border: 1px solid rgba(255, 255, 255, 0.20);
                    border-radius: 999px;
                    color: rgba(255, 255, 255, 0.92);
                    display: inline-flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 900;
                    gap: 0.45rem;
                    letter-spacing: 0.08em;
                    margin-bottom: 0.88rem;
                    padding: 0.48rem 0.78rem;
                    text-transform: uppercase;
                    transition: background 0.24s ease, transform 0.24s ease;
                }

                .about-v2-top-hero:hover .about-v2-top-eyebrow {
                    background: rgba(255, 255, 255, 0.17);
                    transform: translateY(-2px);
                }

                .about-v2-top-info-dot {
                    align-items: center;
                    animation: aboutV2TopPulse 2.4s ease-in-out infinite;
                    background: rgba(255, 255, 255, 0.16);
                    border: 1px solid rgba(255, 255, 255, 0.48);
                    border-radius: 999px;
                    display: inline-flex;
                    height: 23px;
                    justify-content: center;
                    width: 23px;
                }

                .about-v2-top-title {
                    color: #FFFFFF !important;
                    font-size: clamp(1.72rem, 4.2vw, 3.55rem);
                    font-weight: 900;
                    letter-spacing: -0.06em;
                    line-height: 0.98;
                    margin: 0;
                    max-width: 820px;
                    text-shadow: 0 12px 28px rgba(0, 0, 0, 0.34);
                }

                .about-v2-top-title span {
                    background: linear-gradient(90deg, #FFFFFF 0%, #FFE2E2 40%, #FFCDD2 70%, #FFFFFF 100%);
                    -webkit-background-clip: text;
                    background-clip: text;
                    color: transparent;
                    display: inline-block;
                }

                .about-v2-top-subtitle {
                    color: rgba(255, 255, 255, 0.88) !important;
                    font-family: 'Inter', sans-serif;
                    font-size: clamp(0.92rem, 1.35vw, 1.08rem);
                    font-weight: 600;
                    line-height: 1.68;
                    margin: 0.92rem 0 0 0;
                    max-width: 790px;
                }

                .about-v2-top-chips {
                    align-items: center;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.55rem;
                    margin-top: 1.15rem;
                }

                .about-v2-top-chip {
                    align-items: center;
                    background: rgba(255, 255, 255, 0.11);
                    border: 1px solid rgba(255, 255, 255, 0.18);
                    border-radius: 999px;
                    color: #FFFFFF;
                    display: inline-flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 900;
                    gap: 0.38rem;
                    overflow: hidden;
                    padding: 0.54rem 0.78rem;
                    position: relative;
                    transition: background 0.24s ease, border-color 0.24s ease, box-shadow 0.24s ease, transform 0.24s ease;
                }

                .about-v2-top-chip::after {
                    animation: aboutV2TopShine 5s ease-in-out infinite;
                    background: rgba(255, 255, 255, 0.36);
                    content: '';
                    height: 140%;
                    left: 0;
                    position: absolute;
                    top: -20%;
                    width: 34%;
                }

                .about-v2-top-chip:nth-child(2)::after { animation-delay: 0.55s; }
                .about-v2-top-chip:nth-child(3)::after { animation-delay: 1.1s; }
                .about-v2-top-chip:nth-child(4)::after { animation-delay: 1.65s; }

                .about-v2-top-chip:hover {
                    background: rgba(255, 255, 255, 0.18);
                    border-color: rgba(255, 255, 255, 0.34);
                    box-shadow: 0 10px 22px rgba(0, 0, 0, 0.18);
                    transform: translateY(-3px) scale(1.02);
                }

                .about-v2-top-visual {
                    align-items: center;
                    display: flex;
                    justify-content: center;
                    min-height: 174px;
                    position: relative;
                }

                .about-v2-radar-card {
                    background: rgba(7, 10, 18, 0.38);
                    border: 1px solid rgba(255, 255, 255, 0.18);
                    border-radius: 22px;
                    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.22);
                    height: 164px;
                    overflow: hidden;
                    position: relative;
                    transition: transform 0.28s ease, border-color 0.28s ease;
                    width: 230px;
                }

                .about-v2-top-hero:hover .about-v2-radar-card {
                    border-color: rgba(255, 255, 255, 0.34);
                    transform: rotate(-1.2deg) translateY(-4px);
                }

                .about-v2-radar-ring,
                .about-v2-radar-ring::before,
                .about-v2-radar-ring::after {
                    border: 1px solid rgba(255, 255, 255, 0.16);
                    border-radius: 999px;
                    content: '';
                    position: absolute;
                }

                .about-v2-radar-ring {
                    height: 126px;
                    left: 52px;
                    top: 18px;
                    width: 126px;
                }

                .about-v2-radar-ring::before {
                    height: 84px;
                    left: 20px;
                    top: 20px;
                    width: 84px;
                }

                .about-v2-radar-ring::after {
                    height: 42px;
                    left: 41px;
                    top: 41px;
                    width: 42px;
                }

                .about-v2-radar-node {
                    animation: aboutV2TopOrbit 7s linear infinite;
                    background: #FFFFFF;
                    border-radius: 999px;
                    box-shadow: 0 0 18px rgba(255, 255, 255, 0.88);
                    height: 9px;
                    left: 111px;
                    position: absolute;
                    top: 77px;
                    transform-origin: center;
                    width: 9px;
                }

                .about-v2-radar-node:nth-child(3) {
                    animation-delay: -2.4s;
                    background: #FFCDD2;
                }

                .about-v2-radar-node:nth-child(4) {
                    animation-delay: -4.8s;
                    background: #90CAF9;
                }

                .about-v2-mini-status {
                    align-items: center;
                    backdrop-filter: blur(12px);
                    background: rgba(255, 255, 255, 0.13);
                    border: 1px solid rgba(255, 255, 255, 0.22);
                    border-radius: 16px;
                    bottom: 2px;
                    color: #FFFFFF;
                    display: inline-flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 900;
                    gap: 0.42rem;
                    padding: 0.6rem 0.74rem;
                    position: absolute;
                    right: 0;
                    transition: transform 0.24s ease, background 0.24s ease;
                }

                .about-v2-top-hero:hover .about-v2-mini-status {
                    background: rgba(255, 255, 255, 0.18);
                    transform: translateY(-5px);
                }

                .about-v2-interaction-hint {
                    color: rgba(255, 255, 255, 0.72);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    letter-spacing: 0.06em;
                    margin-top: 0.74rem;
                    text-transform: uppercase;
                }

                .about-v2-section-head {
                    align-items: flex-end;
                    display: flex;
                    gap: 1rem;
                    justify-content: space-between;
                    margin: 1.35rem 0 0.8rem 0;
                }

                .about-v2-kicker {
                    align-items: center;
                    color: var(--app-primary);
                    display: inline-flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    gap: 0.38rem;
                    letter-spacing: 0.11em;
                    margin-bottom: 0.28rem;
                    text-transform: uppercase;
                }

                .about-v2-kicker::before {
                    background: var(--app-primary);
                    border-radius: 999px;
                    box-shadow: 0 0 0 4px rgba(229, 57, 53, 0.12);
                    content: '';
                    height: 6px;
                    width: 6px;
                }

                .about-v2-section-title {
                    color: var(--app-text);
                    font-size: clamp(1.18rem, 2vw, 1.45rem);
                    font-weight: 800;
                    letter-spacing: -0.03em;
                    line-height: 1.2;
                    margin: 0;
                }

                .about-v2-section-copy {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.78rem;
                    line-height: 1.5;
                    max-width: 420px;
                    text-align: right;
                }

                .about-v2-hero {
                    background:
                        radial-gradient(circle at 92% 12%, rgba(255, 255, 255, 0.15), transparent 30%),
                        radial-gradient(circle at 10% 92%, rgba(183, 28, 28, 0.28), transparent 28%),
                        linear-gradient(135deg, #171923 0%, #B71C1C 48%, #E53935 100%);
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 18px;
                    box-shadow: 0 18px 42px rgba(183, 28, 28, 0.24);
                    box-sizing: border-box;
                    color: #FFFFFF;
                    margin: 0.75rem 0 1.35rem 0;
                    overflow: hidden;
                    padding: clamp(1.35rem, 3vw, 2.2rem);
                    position: relative;
                    transition: border-color 0.28s ease, box-shadow 0.28s ease, transform 0.28s ease;
                }

                .about-v2-hero::before {
                    background: linear-gradient(90deg, rgba(255,255,255,0.30), rgba(255,255,255,0));
                    content: '';
                    height: 1px;
                    left: 0;
                    position: absolute;
                    right: 0;
                    top: 0;
                }

                .about-v2-hero::after {
                    background: radial-gradient(circle, rgba(255,255,255,0.16), transparent 68%);
                    content: '';
                    height: 260px;
                    pointer-events: none;
                    position: absolute;
                    right: -88px;
                    top: -116px;
                    width: 260px;
                }

                .about-v2-hero:hover {
                    border-color: rgba(255, 255, 255, 0.28);
                    box-shadow: 0 22px 56px rgba(229, 57, 53, 0.30), 0 0 0 1px rgba(255,255,255,0.07);
                    transform: translateY(-2px);
                }

                .about-v2-hero-label {
                    align-items: center;
                    background: rgba(255, 255, 255, 0.12);
                    border: 1px solid rgba(255, 255, 255, 0.22);
                    border-radius: 999px;
                    color: #FFFFFF;
                    display: inline-flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    gap: 0.42rem;
                    letter-spacing: 0.08em;
                    margin-bottom: 1rem;
                    padding: 0.48rem 0.78rem;
                    position: relative;
                    text-transform: uppercase;
                    z-index: 1;
                }

                .about-v2-hero-title {
                    color: #FFFFFF !important;
                    font-size: clamp(1.35rem, 3vw, 2.2rem);
                    font-style: italic;
                    font-weight: 800;
                    letter-spacing: -0.04em;
                    line-height: 1.28;
                    margin: 0;
                    max-width: 1120px;
                    position: relative;
                    text-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
                    z-index: 1;
                }

                .about-v2-hero-badges {
                    align-items: center;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.55rem;
                    margin-top: 1.1rem;
                    position: relative;
                    z-index: 1;
                }

                .about-v2-pill {
                    align-items: center;
                    border-radius: 999px;
                    display: inline-flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    gap: 0.35rem;
                    line-height: 1;
                    padding: 0.52rem 0.75rem;
                    transition: border-color 0.24s ease, box-shadow 0.24s ease, transform 0.24s ease, background 0.24s ease;
                    white-space: nowrap;
                }

                .about-v2-pill:hover {
                    transform: translateY(-2px);
                }

                .about-v2-pill-red {
                    background: rgba(229, 57, 53, 0.16);
                    border: 1px solid rgba(229, 57, 53, 0.42);
                    color: #FFB4B4;
                }

                .about-v2-pill-green {
                    background: rgba(76, 175, 80, 0.15);
                    border: 1px solid rgba(76, 175, 80, 0.42);
                    color: #72D878;
                }

                .about-v2-pill-yellow {
                    background: rgba(255, 152, 0, 0.14);
                    border: 1px solid rgba(255, 152, 0, 0.38);
                    color: #FFB74D;
                }

                .about-v2-pill-blue {
                    background: rgba(66, 165, 245, 0.13);
                    border: 1px solid rgba(66, 165, 245, 0.36);
                    color: #90CAF9;
                }

                .about-v2-card {
                    background:
                        linear-gradient(145deg, color-mix(in srgb, var(--app-card) 92%, #FFFFFF 4%), var(--app-card));
                    border: 1px solid var(--app-border);
                    border-radius: 16px;
                    box-sizing: border-box;
                    color: var(--app-text);
                    min-height: 100%;
                    overflow: hidden;
                    padding: 1rem;
                    position: relative;
                    transition: border-color 0.26s ease, box-shadow 0.26s ease, transform 0.26s ease, background 0.26s ease;
                    will-change: transform;
                }

                .about-v2-card::after {
                    background: linear-gradient(90deg, transparent, rgba(229, 57, 53, 0.85), transparent);
                    content: '';
                    height: 2px;
                    left: -46%;
                    opacity: 0;
                    position: absolute;
                    top: 0;
                    transition: left 0.42s ease, opacity 0.26s ease;
                    width: 68%;
                }

                .about-v2-card:hover {
                    border-color: rgba(229, 57, 53, 0.60);
                    box-shadow: 0 18px 42px rgba(0, 0, 0, 0.22), 0 0 0 1px rgba(229, 57, 53, 0.12);
                    transform: translateY(-3px);
                }

                .about-v2-card:hover::after {
                    left: 78%;
                    opacity: 1;
                }

                .about-v2-profile-card {
                    align-items: center;
                    display: grid;
                    gap: 1rem;
                    grid-template-columns: auto 1fr;
                    padding: 1.1rem;
                }

                .about-v2-avatar {
                    align-items: center;
                    background:
                        radial-gradient(circle at 30% 25%, rgba(255,255,255,0.18), transparent 34%),
                        linear-gradient(135deg, #B71C1C, #E53935);
                    border: 2px solid rgba(255, 255, 255, 0.16);
                    border-radius: 999px;
                    box-shadow: 0 12px 26px rgba(229, 57, 53, 0.18);
                    color: #FFFFFF;
                    display: flex;
                    font-size: 1rem;
                    font-weight: 900;
                    height: 64px;
                    justify-content: center;
                    letter-spacing: 0.04em;
                    min-width: 64px;
                    width: 64px;
                }

                .about-v2-profile-role {
                    color: var(--app-primary);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                    font-weight: 800;
                    letter-spacing: 0.08em;
                    margin-bottom: 0.25rem;
                    text-transform: uppercase;
                }

                .about-v2-profile-name {
                    color: var(--app-text);
                    font-size: 1.02rem;
                    font-weight: 800;
                    letter-spacing: -0.02em;
                    line-height: 1.22;
                    margin-bottom: 0.45rem;
                }

                .about-v2-meta-grid {
                    display: grid;
                    gap: 0.42rem;
                }

                .about-v2-meta-line {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.76rem;
                    line-height: 1.42;
                }

                .about-v2-meta-line strong {
                    color: var(--app-text);
                    font-weight: 700;
                }

                .about-v2-method-card {
                    min-height: 230px;
                    margin-bottom: 1.45rem;
                    padding: 1.05rem;
                }

                .about-v2-method-row-gap {
                    height: 1.55rem;
                }

                .about-v2-method-top {
                    align-items: center;
                    display: flex;
                    gap: 0.75rem;
                    margin-bottom: 0.8rem;
                }

                .about-v2-step-number {
                    align-items: center;
                    background: rgba(229, 57, 53, 0.14);
                    border: 1px solid rgba(229, 57, 53, 0.32);
                    border-radius: 14px;
                    color: var(--app-primary);
                    display: flex;
                    font-size: 0.82rem;
                    font-weight: 900;
                    height: 46px;
                    justify-content: center;
                    min-width: 46px;
                    width: 46px;
                }

                .about-v2-method-icon {
                    font-size: 1.25rem;
                    line-height: 1;
                }

                .about-v2-method-title {
                    color: var(--app-text);
                    font-size: 0.98rem;
                    font-weight: 800;
                    letter-spacing: -0.02em;
                    margin: 0;
                }

                .about-v2-method-list {
                    display: grid;
                    gap: 0.55rem;
                    margin: 0;
                    padding: 0;
                }

                .about-v2-method-item {
                    align-items: flex-start;
                    background: color-mix(in srgb, var(--app-secondary) 78%, transparent);
                    border: 1px solid var(--app-border);
                    border-radius: 12px;
                    color: var(--app-muted);
                    display: flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.76rem;
                    gap: 0.48rem;
                    line-height: 1.42;
                    padding: 0.62rem 0.68rem;
                    transition: border-color 0.24s ease, color 0.24s ease, transform 0.24s ease, background 0.24s ease;
                }

                .about-v2-method-item:hover {
                    background: rgba(229, 57, 53, 0.07);
                    border-color: rgba(229, 57, 53, 0.32);
                    color: var(--app-text);
                    transform: translateX(3px);
                }

                .about-v2-check {
                    color: var(--app-primary);
                    flex: 0 0 auto;
                    font-weight: 900;
                    margin-top: 0.02rem;
                }

                .about-v2-badge-panel {
                    background: var(--app-card);
                    border: 1px solid var(--app-border);
                    border-radius: 16px;
                    padding: 1rem;
                }

                .about-v2-badge-title {
                    color: var(--app-text);
                    font-size: 0.92rem;
                    font-weight: 800;
                    margin-bottom: 0.65rem;
                }

                .about-v2-badge-row {
                    align-items: center;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.55rem;
                }

                .about-v2-tech-row-gap {
                    height: clamp(1rem, 2.4vw, 1.55rem);
                }

                .about-v2-tech-card {
                    align-items: center;
                    display: flex;
                    gap: 0.86rem;
                    min-height: 88px;
                    padding: 0.95rem;
                    margin-bottom: 0.65rem;
                }

                .about-v2-tech-icon {
                    align-items: center;
                    background: rgba(229, 57, 53, 0.12);
                    border: 1px solid rgba(229, 57, 53, 0.26);
                    border-radius: 14px;
                    display: flex;
                    font-size: 1.18rem;
                    height: 44px;
                    justify-content: center;
                    min-width: 44px;
                    width: 44px;
                }

                .about-v2-tech-name {
                    color: var(--app-text);
                    font-size: 0.86rem;
                    font-weight: 800;
                    line-height: 1.25;
                }

                .about-v2-abstract-note {
                    background: rgba(229, 57, 53, 0.08);
                    border: 1px solid rgba(229, 57, 53, 0.24);
                    border-radius: 14px;
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.82rem;
                    line-height: 1.65;
                    margin: 0.45rem 0.9rem 1.15rem 0.9rem;
                    padding: 1rem 1.1rem;
                }

                .about-v2-abstract-box {
                    background: var(--app-card);
                    border: 1px solid var(--app-border);
                    border-radius: 16px;
                    color: var(--app-text);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.9rem;
                    line-height: 1.78;
                    margin: 1rem 0.95rem 0.85rem 0.95rem;
                    padding: 1.35rem 1.45rem;
                    text-align: justify;
                }

                .about-v2-footer {
                    background:
                        radial-gradient(circle at 15% 0%, rgba(229, 57, 53, 0.18), transparent 34%),
                        var(--app-card);
                    border: 1px solid var(--app-border);
                    border-left: 4px solid var(--app-primary);
                    border-radius: 16px;
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.83rem;
                    font-weight: 700;
                    margin-top: 1.25rem;
                    padding: 1rem 1.1rem;
                    text-align: center;
                }

                .about-v2-footer strong {
                    color: var(--app-text);
                }

                [data-testid="stExpander"] {
                    background: var(--app-card);
                    border: 1px solid var(--app-border);
                    border-radius: 16px;
                    overflow: hidden;
                    transition: border-color 0.25s ease, box-shadow 0.25s ease;
                }

                [data-testid="stExpander"] details > div {
                    padding: 1rem 1.05rem 1.25rem 1.05rem !important;
                }

                [data-testid="stExpander"] [data-testid="stTabs"] {
                    margin-top: 0.45rem;
                }

                [data-testid="stExpander"] [data-testid="stTabs"] div[role="tablist"] {
                    padding-left: 0.55rem;
                    padding-right: 0.55rem;
                }

                [data-testid="stExpander"]:hover {
                    border-color: rgba(229, 57, 53, 0.48);
                    box-shadow: 0 14px 34px rgba(229, 57, 53, 0.10);
                }

                [data-testid="stExpander"] summary {
                    color: var(--app-text) !important;
                    font-weight: 800;
                }

                [data-testid="stTabs"] button {
                    border-radius: 999px !important;
                    color: var(--app-muted) !important;
                    font-weight: 800 !important;
                }

                [data-testid="stTabs"] button[aria-selected="true"] {
                    background: rgba(229, 57, 53, 0.14) !important;
                    color: var(--app-primary) !important;
                }

                @media (max-width: 880px) {
                    .about-v2-top-hero {
                        border-radius: 18px;
                        padding: 1.25rem;
                    }

                    .about-v2-top-grid {
                        grid-template-columns: 1fr;
                    }

                    .about-v2-top-visual {
                        display: none;
                    }

                    .about-v2-top-title {
                        font-size: clamp(1.55rem, 12vw, 2.5rem);
                    }

                    .about-v2-interaction-hint {
                        font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                        line-height: 1.5;
                    }

                    .about-v2-section-head {
                        align-items: flex-start;
                        flex-direction: column;
                    }

                    .about-v2-section-copy {
                        max-width: 100%;
                        text-align: left;
                    }

                    .about-v2-profile-card {
                        align-items: flex-start;
                        grid-template-columns: 1fr;
                    }
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Gaya halaman Tentang Penelitian belum dapat dimuat: {exc}")


def _render_section_header(kicker: str, title: str, copy: str | None = None) -> None:
    """Menampilkan judul kecil untuk setiap section."""
    try:
        safe_kicker = escape(kicker)
        safe_title = escape(title)
        safe_copy = escape(copy or "")
        copy_html = f'<div class="about-v2-section-copy">{safe_copy}</div>' if copy else ""
        st.markdown(
            f"""
            <div class="about-v2-section-head">
                <div>
                    <div class="about-v2-kicker">{safe_kicker}</div>
                    <h2 class="about-v2-section-title">{safe_title}</h2>
                </div>
                {copy_html}
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Judul bagian belum dapat ditampilkan: {exc}")


def _render_top_banner() -> None:
    """Menampilkan banner pembuka yang interaktif dan beranimasi."""
    try:
        st.markdown(
            """
            <div class="about-v2-top-hero" role="banner" tabindex="0" aria-label="Banner Tentang Penelitian">
                <div class="about-v2-top-orb about-v2-top-orb-one"></div>
                <div class="about-v2-top-orb about-v2-top-orb-two"></div>
                <div class="about-v2-top-grid">
                    <div class="about-v2-top-content">
                        <div class="about-v2-top-eyebrow">
                            <span class="about-v2-top-info-dot">ⓘ</span>
                            Dashboard Skripsi Telkom Group
                        </div>
                        <h1 class="about-v2-top-title"><span>Tentang</span><br>Penelitian</h1>
                        <p class="about-v2-top-subtitle">
                            Identitas penelitian, metodologi, layanan, platform, teknologi,
                            dan abstrak skripsi disajikan dalam satu halaman ringkas,
                            modern, dan mudah dipahami.
                        </p>
                        <div class="about-v2-top-chips">
                            <span class="about-v2-top-chip">🕸️ SNA</span>
                            <span class="about-v2-top-chip">🧠 IndoBERT</span>
                            <span class="about-v2-top-chip">📊 Sentimen</span>
                            <span class="about-v2-top-chip">📡 Telkom Group</span>
                        </div>
                        <div class="about-v2-interaction-hint">Arahkan kursor atau klik banner untuk melihat efek animasi</div>
                    </div>
                    <div class="about-v2-top-visual" aria-hidden="true">
                        <div class="about-v2-radar-card">
                            <div class="about-v2-radar-ring"></div>
                            <div class="about-v2-radar-node"></div>
                            <div class="about-v2-radar-node"></div>
                            <div class="about-v2-radar-node"></div>
                        </div>
                        <div class="about-v2-mini-status">✅ IndiHome Ready</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Banner Tentang Penelitian belum dapat ditampilkan: {exc}")


def _render_hero() -> None:
    """Menampilkan hero card utama berisi judul penelitian."""
    try:
        st.markdown(
            f"""
            <div class="about-v2-hero">
                <div class="about-v2-hero-label">📡 Tentang Penelitian</div>
                <h1 class="about-v2-hero-title">“{escape(_RESEARCH_TITLE)}”</h1>
                <div class="about-v2-hero-badges">
                    <span class="about-v2-pill about-v2-pill-red">🎓 Skripsi S1 Sains Data</span>
                    <span class="about-v2-pill about-v2-pill-blue">🏛️ ULBI Bandung</span>
                    <span class="about-v2-pill about-v2-pill-green">📅 2026</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Hero halaman belum dapat ditampilkan: {exc}")


def _render_identity_card(
    avatar: str,
    role: str,
    name: str,
    rows: list[tuple[str, str]],
) -> None:
    """Menampilkan card identitas peneliti atau pembimbing."""
    try:
        rows_html = "".join(
            f'<div class="about-v2-meta-line"><strong>{escape(label)}:</strong> {escape(value)}</div>'
            for label, value in rows
        )
        st.markdown(
            f"""
            <div class="about-v2-card about-v2-profile-card">
                <div class="about-v2-avatar">{escape(avatar)}</div>
                <div>
                    <div class="about-v2-profile-role">{escape(role)}</div>
                    <div class="about-v2-profile-name">{escape(name)}</div>
                    <div class="about-v2-meta-grid">{rows_html}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Kartu identitas belum dapat ditampilkan: {exc}")


def _render_research_people() -> None:
    """Menampilkan informasi peneliti dan dosen pembimbing."""
    try:
        _render_section_header(
            "Identitas",
            "Peneliti & Pembimbing",
            "Avatar dibuat dari inisial nama agar halaman tetap ringan dan tidak bergantung pada file foto.",
        )
        col_left, col_right = st.columns(2, gap="large")
        with col_left:
            _render_identity_card(
                avatar="AR",
                role="Peneliti",
                name="Aulia Rahmadiva Wardana",
                rows=[
                    ("NPM", "184220019"),
                    ("Prodi", "S1 Sains Data — ULBI Bandung"),
                ],
            )
        with col_right:
            _render_identity_card(
                avatar="WI",
                role="Dosen Pembimbing",
                name="Woro Isti Rahayu, S.T., M.T.",
                rows=[
                    ("Peran", "Dosen Pembimbing"),
                    ("Institusi", "ULBI Bandung"),
                ],
            )
    except Exception as exc:
        st.error(f"Informasi peneliti dan pembimbing belum dapat ditampilkan: {exc}")


def _render_method_step(step: dict[str, object]) -> None:
    """Menampilkan satu step metodologi."""
    try:
        items = step.get("items", [])
        items_html = "".join(
            f"""
            <div class="about-v2-method-item">
                <span class="about-v2-check">✓</span>
                <span>{escape(str(item))}</span>
            </div>
            """
            for item in items
        )
        st.markdown(
            f"""
            <div class="about-v2-card about-v2-method-card">
                <div class="about-v2-method-top">
                    <div class="about-v2-step-number">{escape(str(step.get('number', '')))}</div>
                    <div>
                        <div class="about-v2-method-icon">{escape(str(step.get('icon', '')))}</div>
                        <h3 class="about-v2-method-title">{escape(str(step.get('title', '')))}</h3>
                    </div>
                </div>
                <div class="about-v2-method-list">{items_html}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Step metodologi belum dapat ditampilkan: {exc}")


def _render_methodology() -> None:
    """Menampilkan metodologi dalam grid 2x2."""
    try:
        _render_section_header(
            "Metodologi",
            "Alur Analisis Penelitian",
            "Empat tahap utama yang menghubungkan pengumpulan data, SNA, IndoBERT, dan rekomendasi strategis.",
        )
        for row_start in range(0, len(_METHOD_STEPS), 2):
            if row_start > 0:
                st.markdown('<div class="about-v2-method-row-gap"></div>', unsafe_allow_html=True)

            columns = st.columns(2, gap="large")
            for column, step in zip(columns, _METHOD_STEPS[row_start : row_start + 2]):
                with column:
                    _render_method_step(step)
    except Exception as exc:
        st.error(f"Metodologi penelitian belum dapat ditampilkan: {exc}")


def _render_services_and_platforms() -> None:
    """Menampilkan badge layanan dan platform media sosial."""
    try:
        _render_section_header(
            "Cakupan",
            "Layanan & Platform",
            "Status layanan ditampilkan jujur agar pengguna tidak salah membaca fitur yang sudah tersedia.",
        )
        col_services, col_platforms = st.columns([1.15, 0.85], gap="large")
        with col_services:
            st.markdown(
                """
                <div class="about-v2-badge-panel">
                    <div class="about-v2-badge-title">Layanan yang dianalisis</div>
                    <div class="about-v2-badge-row">
                        <span class="about-v2-pill about-v2-pill-green">IndiHome ✅ tersedia</span>
                        <span class="about-v2-pill about-v2-pill-yellow">IndiBiz ⏳ dalam pengembangan</span>
                        <span class="about-v2-pill about-v2-pill-yellow">Telkomsel ⏳ dalam pengembangan</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col_platforms:
            st.markdown(
                """
                <div class="about-v2-badge-panel">
                    <div class="about-v2-badge-title">Platform media sosial</div>
                    <div class="about-v2-badge-row">
                        <span class="about-v2-pill about-v2-pill-blue">Twitter/X</span>
                        <span class="about-v2-pill about-v2-pill-red">Instagram</span>
                        <span class="about-v2-pill about-v2-pill-red">TikTok</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    except Exception as exc:
        st.error(f"Badge layanan dan platform belum dapat ditampilkan: {exc}")


def _render_tech_stack() -> None:
    """Menampilkan tech stack minimal delapan item."""
    try:
        _render_section_header(
            "Teknologi",
            "Tech Stack Dashboard",
            "Komponen utama yang dipakai untuk membangun dashboard penelitian berbasis Streamlit.",
        )
        for row_start in range(0, len(_TECH_STACK), 4):
            if row_start > 0:
                st.markdown('<div class="about-v2-tech-row-gap"></div>', unsafe_allow_html=True)

            columns = st.columns(4, gap="large")
            for column, (icon, name) in zip(columns, _TECH_STACK[row_start : row_start + 4]):
                with column:
                    st.markdown(
                        f"""
                        <div class="about-v2-card about-v2-tech-card">
                            <div class="about-v2-tech-icon">{escape(icon)}</div>
                            <div class="about-v2-tech-name">{escape(name)}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
    except Exception as exc:
        st.error(f"Tech stack belum dapat ditampilkan: {exc}")


def _render_abstract() -> None:
    """Menampilkan abstrak dalam expander dan dua tab bahasa."""
    try:
        _render_section_header(
            "Abstrak",
            "Ringkasan Penelitian",
            "Klik expander untuk membaca abstrak Bahasa Indonesia atau versi English.",
        )
        with st.expander("📄 Lihat Abstrak", expanded=False):
            st.markdown(
                """
                <div class="about-v2-abstract-note">
                    Gunakan tab di bawah ini untuk berpindah bahasa. Isi abstrak disimpan
                    di dalam expander agar halaman tetap ringkas saat pertama kali dibuka.
                </div>
                """,
                unsafe_allow_html=True,
            )
            tab_id, tab_en = st.tabs(["ID Bahasa Indonesia", "EN English"])
            with tab_id:
                st.markdown(
                    f'<div class="about-v2-abstract-box">{escape(_ABSTRACT_ID)}</div>',
                    unsafe_allow_html=True,
                )
            with tab_en:
                st.markdown(
                    f'<div class="about-v2-abstract-box">{escape(_ABSTRACT_EN)}</div>',
                    unsafe_allow_html=True,
                )
    except Exception as exc:
        st.error(f"Abstrak penelitian belum dapat ditampilkan: {exc}")


def _render_footer() -> None:
    """Menampilkan footer halaman."""
    try:
        st.markdown(
            """
            <div class="about-v2-footer">
                © 2026 <strong>Aulia Rahmadiva Wardana</strong> · NPM <strong>184220019</strong> · ULBI Bandung · Versi <strong>v2.0</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Footer halaman belum dapat ditampilkan: {exc}")


# -----------------------------------------------------------------------------
# Fungsi utama yang dipanggil oleh app.py
# -----------------------------------------------------------------------------

def render_about() -> None:
    """Render seluruh halaman Tentang Penelitian."""
    try:
        _inject_about_css()
        st.markdown('<div class="about-v2-page">', unsafe_allow_html=True)
        _render_top_banner()
        _render_hero()
        _render_research_people()
        _render_methodology()
        _render_services_and_platforms()
        _render_tech_stack()
        _render_abstract()
        st.markdown("</div>", unsafe_allow_html=True)
    except Exception as exc:
        st.error(f"Halaman Tentang Penelitian gagal dimuat: {exc}")
