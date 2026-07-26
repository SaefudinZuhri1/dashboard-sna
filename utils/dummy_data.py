"""Generator data dummy konsisten dengan hasil penelitian skripsi."""

import re

import numpy as np
import pandas as pd
import streamlit as st

np.random.seed(42)

# --- Baseline inti penelitian: 14 negatif, 11 positif, 5 netral ---
_NEGATIVE_COMMENTS = [
    "Jaringan telkomsel sering gangguan dan lambat",
    "kuota mahal tidak sebanding kualitas jaringan",
    "sinyal hilang 4 hari tidak ada solusi",
    "provider lain bagus telkomsel makin parah",
    "internet down saat listrik padam tidak cepat pulih",
    "jaringan indihome sering putus putus",
    "paket mahal tapi kecepatan tidak stabil",
    "sinyal lemah di daerah saya",
    "customer service lambat merespons keluhan",
    "wifi indihome jelek banget",
    "kuota habis cepat padahal jarang dipakai",
    "gangguan jaringan tidak ada kompensasi",
    "internet lemot saat jam sibuk",
    "telkomsel makin parah sinyalnya",
]

_POSITIVE_COMMENTS = [
    "hotline tanggap darurat sangat responsif dan helpful",
    "layanan pelanggan cepat ditangani terima kasih",
    "telkomsel keren dan sakti banget memang terbaik",
    "indihome stabil sejak dipasang",
    "teknisi datang tepat waktu profesional",
    "paket internet worth it kualitas bagus",
    "admin respon cepat di media sosial",
    "sinyal stabil di kantor",
    "puas dengan layanan indihome",
    "customer service ramah dan solutif",
    "internet cepat untuk work from home",
]

_NEUTRAL_COMMENTS = [
    "min paket internet ada yang murah tidak",
    "tolong aktifkan nomor saya sudah lama mati",
    "berapa harga paket indihome 50mbps",
    "apakah ada promo bulan ini",
    "info gangguan jaringan di area bandung",
]

_EXTRA_NEGATIVE = [
    "sinyal gangguan terus menerus tidak ada perbaikan",
    "kuota jelek habis cepat padahal jarang streaming",
    "indihome down lagi dari pagi sampai sore",
    "mahal banget dibanding provider lain starlink",
    "lambat parah saat WFH meeting sering putus",
    "gangguan jaringan tidak diberi kompensasi sama sekali",
    "wifi lemot banget di malam hari",
    "sinyal hilang di daerah pedesaan",
    "tagihan mahal tapi internet sering down",
]

_EXTRA_POSITIVE = [
    "layanan bagus cepat terimakasih sudah ditangani",
    "keren mantap indihome stabil terus",
    "teknisi ramah instalasi rapi terima kasih",
    "respon admin twitter sangat cepat helpful",
    "puas paket internetnya worth it banget",
    "sinyal bagus untuk kerja dan kuliah online",
    "customer service telkomsel sangat solutif",
    "instalasi indihome cepat profesional banget",
]

_EXTRA_NEUTRAL = [
    "cek tagihan indihome bulan ini berapa ya",
    "info promo paket internet november desember",
    "admin tolong bantu cek status gangguan area saya",
]

_CORE_USERNAMES = [
    "dewa_brahma", "bellaablee", "faishalfrss", "akri64", "dkdiki_",
    "sutardi.wasimin", "cobeyisyolkek", "matchalle", "jangzaokan",
    "riyanti.apg", "zidnyilma23", "riswanda822", "akakpro46", "roni..08",
    "yxxawx", "zahranurhakiki", "b3n1115", "moba_51", "triaa.ni",
    "gonjeng2gd", "pakidi_123", "kuntarineti", "tayo.gt_", "zyders_1",
    "rizkimaulana_rm", "SyafrizalJ79805", "netizen01", "netizen02",
    "netizen03", "netizen04",
]

_FOLLOWERS_MAP = {
    "dewa_brahma": 76,
    "bellaablee": 174,
    "matchalle": 9,
    "jangzaokan": 441,
    "cobeyisyolkek": 219,
    "SyafrizalJ79805": 0,
    "rizkimaulana_rm": 2,
    "pakidi_123": 212,
    "riyanti.apg": 250,
    "faishalfrss": 1060,
    "zidnyilma23": 847,
    "kuntarineti": 407,
    "akri64": 1110,
    "tayo.gt_": 100,
    "dkdiki_": 1588,
    "zyders_1": 6,
    "sutardi.wasimin": 1612,
    "riswanda822": 559,
    "akakpro46": 620,
    "triaa.ni": 43,
    "gonjeng2gd": 168,
    "yxxawx": 320,
    "zahranurhakiki": 890,
    "roni..08": 380,
    "b3n1115": 210,
    "moba_51": 145,
}

_PLATFORMS = ["twitter", "instagram", "tiktok"]

_SNA_EDGES = [
    # TikTok → indihome
    ("yxxawx", "indihome", "mention", 320, "tiktok"),
    ("zahranurhakiki", "indihome", "mention", 890, "tiktok"),
    ("roni..08", "indihome", "mention", 380, "tiktok"),
    ("b3n1115", "indihome", "mention", 210, "tiktok"),
    ("moba_51", "indihome", "mention", 145, "tiktok"),
    ("sutardi.wasimin", "indihome", "mention", 1612, "tiktok"),
    ("riswanda822", "indihome", "mention", 559, "tiktok"),
    ("akakpro46", "indihome", "mention", 620, "tiktok"),
    ("triaa.ni", "indihome", "mention", 43, "tiktok"),
    ("gonjeng2gd", "indihome", "mention", 168, "tiktok"),
    # Instagram → indihome
    ("rizkimaulana_rm", "indihome", "mention", 2, "instagram"),
    ("pakidi_123", "indihome", "mention", 212, "instagram"),
    ("riyanti.apg", "indihome", "mention", 250, "instagram"),
    ("faishalfrss", "indihome", "mention", 1060, "instagram"),
    ("zidnyilma23", "indihome", "reply", 847, "instagram"),
    ("kuntarineti", "indihome", "mention", 407, "instagram"),
    ("akri64", "indihome", "reply", 1110, "instagram"),
    ("tayo.gt_", "indihome", "mention", 100, "instagram"),
    ("dkdiki_", "indihome", "mention", 1588, "instagram"),
    ("zyders_1", "indihome", "mention", 6, "instagram"),
    # Twitter
    ("bellaablee", "telkomsel", "mention", 174, "twitter"),
    ("matchalle", "indihome", "mention", 9, "twitter"),
    ("jangzaokan", "indihome", "mention", 441, "twitter"),
    ("dewa_brahma", "telkomsel", "mention", 76, "twitter"),
    ("cobeyisyolkek", "telkomsel", "reply", 219, "twitter"),
    ("SyafrizalJ79805", "indihome", "reply", 0, "twitter"),
]

_TOP_WORDS = {
    "positive": [
        ("layanan", 18), ("bagus", 15), ("cepat", 14), ("terimakasih", 12),
        ("keren", 11), ("mantap", 10), ("stabil", 9), ("responsif", 9),
        ("helpful", 8), ("puas", 8), ("profesional", 7), ("sakti", 7),
        ("terbaik", 6), ("solutif", 6), ("worth", 5),
    ],
    "neutral": [
        ("paket", 14), ("internet", 13), ("cek", 11), ("tagihan", 10),
        ("info", 10), ("promo", 9), ("harga", 8), ("admin", 8),
        ("berapa", 7), ("bulan", 7), ("aktifkan", 6), ("nomor", 6),
        ("gangguan", 5), ("area", 5), ("tanya", 4),
    ],
    "negative": [
        ("sinyal", 22), ("gangguan", 20), ("lambat", 18), ("mahal", 16),
        ("kuota", 15), ("jelek", 14), ("down", 13), ("jaringan", 12),
        ("parah", 11), ("lemot", 10), ("hilang", 9), ("starlink", 8),
        ("putus", 8), ("provider", 7), ("kompensasi", 6),
    ],
}

_TOPICS = [
    {
        "topic_id": 1,
        "topik": "Gangguan Sinyal & Jaringan",
        "frekuensi": 10,
        "keywords": "sinyal, jaringan, gangguan, lambat, down",
        "contoh_komentar": "sinyal hilang 4 hari tidak ada solusi",
        "sentimen_dominan": "negative",
    },
    {
        "topic_id": 2,
        "topik": "Apresiasi Layanan & Brand",
        "frekuensi": 8,
        "keywords": "sakti, stabil, responsif, terbaik, puas",
        "contoh_komentar": "telkomsel keren dan sakti banget memang terbaik",
        "sentimen_dominan": "positive",
    },
    {
        "topic_id": 3,
        "topik": "Perbandingan dengan Provider Lain (Starlink)",
        "frekuensi": 4,
        "keywords": "starlink, provider lain, perbandingan, kompetitor",
        "contoh_komentar": "provider lain bagus telkomsel makin parah",
        "sentimen_dominan": "negative",
    },
    {
        "topic_id": 4,
        "topik": "Harga Kuota Mahal",
        "frekuensi": 4,
        "keywords": "mahal, kuota, harga, tagihan, tidak sebanding",
        "contoh_komentar": "kuota mahal tidak sebanding kualitas jaringan",
        "sentimen_dominan": "negative",
    },
    {
        "topic_id": 5,
        "topik": "Interaksi & Pertanyaan ke Admin",
        "frekuensi": 3,
        "keywords": "admin, tolong, aktifkan, info, bantuan",
        "contoh_komentar": "tolong aktifkan nomor saya sudah lama mati",
        "sentimen_dominan": "neutral",
    },
]


def _clean_content(text: str) -> str:
    """Bersihkan teks komentar untuk kolom content_clean."""
    cleaned = re.sub(r"http\S+", "", text)
    cleaned = re.sub(r"[^\w\s]", " ", cleaned, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _random_dates(n: int) -> list[pd.Timestamp]:
    """Generate tanggal acak dalam periode November–Desember 2025."""
    start = pd.Timestamp("2025-11-01")
    end = pd.Timestamp("2025-12-31")
    days = (end - start).days
    offsets = np.random.randint(0, days + 1, size=n)
    return [start + pd.Timedelta(days=int(d)) for d in offsets]


def get_dummy_sentiment_data(layanan: str = "IndiHome") -> pd.DataFrame:
    """
    Kembalikan DataFrame sentimen dummy (50 baris).

    30 baris inti penelitian (14 negatif, 11 positif, 5 netral)
    ditambah 20 baris variasi dengan distribusi serupa.
    """
    try:
        core_contents = _NEGATIVE_COMMENTS + _POSITIVE_COMMENTS + _NEUTRAL_COMMENTS
        core_sentiments = (
            ["negative"] * 14 + ["positive"] * 11 + ["neutral"] * 5
        )
        extra_contents = _EXTRA_NEGATIVE + _EXTRA_POSITIVE + _EXTRA_NEUTRAL
        extra_sentiments = (
            ["negative"] * 9 + ["positive"] * 8 + ["neutral"] * 3
        )

        all_contents = core_contents + extra_contents
        all_sentiments = core_sentiments + extra_sentiments
        dates = _random_dates(len(all_contents))

        rows = []
        for i, (content, sentiment) in enumerate(zip(all_contents, all_sentiments)):
            username = _CORE_USERNAMES[i % len(_CORE_USERNAMES)]
            platform = _PLATFORMS[i % 3]
            followers = _FOLLOWERS_MAP.get(username, int(np.random.randint(50, 500)))

            rows.append({
                "date_created": dates[i],
                "layanan": layanan,
                "platform": platform,
                "username": username,
                "followers": followers,
                "content": content,
                "content_clean": _clean_content(content),
                "predicted_sentiment": sentiment,
                "confidence_score": round(float(np.random.uniform(0.65, 0.97)), 3),
            })

        return pd.DataFrame(rows)
    except Exception as exc:
        raise RuntimeError(f"Gagal membuat data sentimen dummy: {exc}") from exc


def get_dummy_sna_data() -> pd.DataFrame:
    """Kembalikan DataFrame edge list SNA sesuai node penelitian skripsi."""
    try:
        return pd.DataFrame(
            _SNA_EDGES,
            columns=["source", "target", "relationship", "followers", "platform"],
        )
    except Exception as exc:
        raise RuntimeError(f"Gagal membuat data SNA dummy: {exc}") from exc


def get_dummy_telkomsel_sna() -> pd.DataFrame:
    """Kembalikan fallback SNA khusus Telkomsel dari contoh metodologi skripsi.

    Data ini hanya menjaga halaman tetap dapat dibuka ketika file aktual belum
    ditempel. Seluruh edge diarahkan ke layanan Telkomsel dan tidak pernah
    ditulis ke file penelitian pengguna.
    """
    try:
        edges = [
            # TikTok, komentar menuju akun resmi Telkomsel.
            ("yxxawx", "telkomsel", "comment", 320, "tiktok"),
            ("zahranurhakiki", "telkomsel", "comment", 890, "tiktok"),
            ("roni..08", "telkomsel", "comment", 380, "tiktok"),
            ("b3n1115", "telkomsel", "comment", 210, "tiktok"),
            ("moba_51", "telkomsel", "comment", 145, "tiktok"),
            ("sutardi.wasimin", "telkomsel", "comment", 1612, "tiktok"),
            ("riswanda822", "telkomsel", "comment", 559, "tiktok"),
            ("akakpro46", "telkomsel", "comment", 620, "tiktok"),
            ("triaa.ni", "telkomsel", "comment", 43, "tiktok"),
            ("gonjeng2gd", "telkomsel", "comment", 168, "tiktok"),
            # Instagram, komentar menuju akun resmi Telkomsel.
            ("rizkimaulana_rm", "telkomsel", "comment", 2, "instagram"),
            ("pakidi_123", "telkomsel", "comment", 212, "instagram"),
            ("riyanti.apg", "telkomsel", "comment", 250, "instagram"),
            ("faishalfrss", "telkomsel", "comment", 1060, "instagram"),
            ("zidnyilma23", "telkomsel", "comment", 847, "instagram"),
            ("kuntarineti", "telkomsel", "comment", 407, "instagram"),
            ("akri64", "telkomsel", "comment", 1110, "instagram"),
            ("tayo.gt_", "telkomsel", "comment", 100, "instagram"),
            ("dkdiki_", "telkomsel", "comment", 1588, "instagram"),
            ("zyders_1", "telkomsel", "comment", 6, "instagram"),
            # Twitter/X, mention dan reply berarah.
            ("bellaablee", "telkomsel", "mention", 174, "twitter"),
            ("telkomsel", "bellaablee", "reply", 0, "twitter"),
            ("matchalle", "telkomsel", "mention", 9, "twitter"),
            ("telkomsel", "matchalle", "reply", 0, "twitter"),
            ("jangzaokan", "bellaablee", "reply", 441, "twitter"),
            ("dewa_brahma", "telkomsel", "mention", 76, "twitter"),
            ("telkomsel", "dewa_brahma", "reply", 0, "twitter"),
            ("dewa_brahma", "commuterline", "reply", 76, "twitter"),
            ("dewa_brahma", "ajengndita", "reply", 76, "twitter"),
            ("cobeyisyolkek", "telkomsel", "mention", 219, "twitter"),
            ("telkomsel", "cobeyisyolkek", "reply", 0, "twitter"),
            ("syafrizalj79805", "cobeyisyolkek", "reply", 0, "twitter"),
        ]
        dataframe = pd.DataFrame(
            edges,
            columns=["source", "target", "relationship", "followers", "platform"],
        )
        dataframe["layanan"] = "Telkomsel"
        return dataframe
    except Exception as exc:
        raise RuntimeError(f"Gagal membuat data SNA dummy Telkomsel: {exc}") from exc


def get_dummy_wordcloud_data() -> dict[str, str]:
    """Kembalikan corpus teks per sentimen untuk WordCloud."""
    try:
        return {
            "positive": (
                "layanan bagus cepat terimakasih keren mantap stabil responsif "
                "helpful puas profesional sakti terbaik solutif worth indihome "
                "telkomsel teknisi ramah instalasi rapi customer service tanggap"
            ),
            "neutral": (
                "paket internet cek tagihan info promo harga admin berapa bulan "
                "aktifkan nomor gangguan area tanya status layanan indihome "
                "telkomsel paket murah november desember pertanyaan bantuan"
            ),
            "negative": (
                "sinyal gangguan lambat mahal kuota jelek down jaringan parah "
                "lemot hilang starlink putus provider kompensasi indihome "
                "telkomsel wifi lemot tagihan mahal internet down sering putus "
                "customer service lambat tidak stabil kualitas buruk"
            ),
        }
    except Exception as exc:
        raise RuntimeError(f"Gagal membuat data WordCloud dummy: {exc}") from exc


def get_dummy_top_words() -> dict[str, list[tuple[str, int]]]:
    """Kembalikan 15 kata teratas beserta frekuensi per sentimen."""
    try:
        return {
            "positive": list(_TOP_WORDS["positive"]),
            "neutral": list(_TOP_WORDS["neutral"]),
            "negative": list(_TOP_WORDS["negative"]),
        }
    except Exception as exc:
        raise RuntimeError(f"Gagal membuat data top words dummy: {exc}") from exc


def get_dummy_stats() -> dict:
    """Kembalikan ringkasan statistik penelitian dari data dummy."""
    try:
        df_sent = get_dummy_sentiment_data("IndiHome")
        df_sna = get_dummy_sna_data()

        total = len(df_sent)
        counts = df_sent["predicted_sentiment"].value_counts()
        pos = int(counts.get("positive", 0))
        neu = int(counts.get("neutral", 0))
        neg = int(counts.get("negative", 0))

        nodes = set(df_sna["source"]) | set(df_sna["target"])
        edges = len(df_sna)
        n_nodes = len(nodes)
        density = round((2 * edges) / (n_nodes * (n_nodes - 1)), 4) if n_nodes > 1 else 0.0

        return {
            "total_data": total,
            "total_platform": int(df_sent["platform"].nunique()),
            "total_sentiment": int(df_sent["predicted_sentiment"].nunique()),
            "total_node": n_nodes,
            "total_edge": edges,
            "density": density,
            "pct_positive": round(pos / total * 100, 1),
            "pct_neutral": round(neu / total * 100, 1),
            "pct_negative": round(neg / total * 100, 1),
        }
    except Exception as exc:
        raise RuntimeError(f"Gagal menghitung statistik dummy: {exc}") from exc


def get_dummy_influencer_data() -> pd.DataFrame:
    """
    Kembalikan DataFrame influencer dengan metrik sentralitas jaringan.

    Berisi username dari penelitian skripsi beserta kategori peran.
    """
    try:
        df_sna = get_dummy_sna_data()

        out_degree: dict[str, int] = {}
        in_degree: dict[str, int] = {}
        platform_map: dict[str, str] = {}
        followers_map: dict[str, int] = {}

        for _, row in df_sna.iterrows():
            src, tgt = row["source"], row["target"]
            out_degree[src] = out_degree.get(src, 0) + 1
            in_degree[tgt] = in_degree.get(tgt, 0) + 1
            platform_map[src] = row["platform"]
            followers_map[src] = int(row["followers"])

        all_users = set(out_degree) | set(in_degree)
        max_degree = max(
            (out_degree.get(u, 0) + in_degree.get(u, 0) for u in all_users),
            default=1,
        )

        rows = []
        for username in sorted(all_users):
            out_d = out_degree.get(username, 0)
            in_d = in_degree.get(username, 0)
            total_d = out_d + in_d
            followers = followers_map.get(username, _FOLLOWERS_MAP.get(username, 0))
            centrality = round(total_d / max_degree, 4) if max_degree else 0.0

            if followers >= 1000 or (total_d >= 2 and followers >= 500):
                kategori = "Key Influencer"
            elif out_d >= 1 and in_d == 0:
                kategori = "Connector"
            else:
                kategori = "Secondary"

            rows.append({
                "username": username,
                "platform": platform_map.get(username, "unknown"),
                "followers": followers,
                "degree_centrality": centrality,
                "in_degree": in_d,
                "out_degree": out_d,
                "kategori": kategori,
            })

        df = pd.DataFrame(rows)
        priority = {"Key Influencer": 0, "Connector": 1, "Secondary": 2}
        return df.sort_values(
            by=["kategori", "followers"],
            key=lambda s: s.map(priority) if s.name == "kategori" else s,
            ascending=[True, False],
        ).reset_index(drop=True)
    except Exception as exc:
        raise RuntimeError(f"Gagal membuat data influencer dummy: {exc}") from exc


def get_dummy_topic_data() -> pd.DataFrame:
    """Kembalikan 5 topik dominan penelitian sebagai DataFrame."""
    try:
        return pd.DataFrame(_TOPICS)
    except Exception as exc:
        raise RuntimeError(f"Gagal membuat data topik dummy: {exc}") from exc


# --- Alias kompatibilitas fase sebelumnya ---
def get_dummy_wordcloud_texts() -> dict[str, str]:
    """Alias ke get_dummy_wordcloud_data() untuk kompatibilitas."""
    return get_dummy_wordcloud_data()


def get_dummy_topics() -> list[dict]:
    """Alias ke get_dummy_topic_data() dalam format list dict."""
    df = get_dummy_topic_data()
    return [
        {
            "topic_id": row["topic_id"],
            "name": row["topik"],
            "frequency": row["frekuensi"],
            "keywords": [k.strip() for k in row["keywords"].split(",")],
            "example_comments": [row["contoh_komentar"]],
        }
        for _, row in df.iterrows()
    ]

# ================================================================
# TAHAP 3 FASE 14 - DATA DUMMY KHUSUS INDIBIZ
# ================================================================
# Random generator memakai seed lokal. Hasil tetap konsisten pada setiap restart
# dan tidak memengaruhi generator dummy layanan lain.

INDIBIZ_SENTIMENT_REQUIRED_COLUMNS = [
    "username",
    "platform",
    "content",
    "predicted_sentiment",
    "confidence_score",
    "followers",
]
INDIBIZ_SNA_REQUIRED_COLUMNS = [
    "source",
    "target",
    "relationship",
    "followers",
    "platform",
]
INDIBIZ_TOPIC_REQUIRED_COLUMNS = ["sentiment", "topik", "keywords"]
INDIBIZ_TOP_KATA_REQUIRED_COLUMNS = ["sentiment", "rank", "kata", "frekuensi"]


def _validasi_dummy_indibiz(
    dataframe: pd.DataFrame,
    nama_data: str,
    jumlah_baris: int,
    kolom_wajib: list[str],
) -> pd.DataFrame:
    """Validasi kontrak dummy sebelum DataFrame dikirim ke dashboard."""
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError(f"{nama_data} bukan DataFrame.")
    if len(dataframe) != jumlah_baris:
        raise ValueError(
            f"{nama_data} harus berisi {jumlah_baris} baris, "
            f"tetapi ditemukan {len(dataframe)} baris."
        )
    missing = [column for column in kolom_wajib if column not in dataframe.columns]
    if missing:
        raise ValueError(f"Kolom {nama_data} belum lengkap: {', '.join(missing)}")
    return dataframe.reset_index(drop=True)


def get_dummy_indibiz_sentiment() -> pd.DataFrame:
    """Buat 50 komentar dummy IndiBiz dengan sentimen negatif lebih dominan."""
    try:
        rng = np.random.default_rng(1701)

        komentar_negatif = [
            "Internet IndiBiz sering putus saat toko sedang ramai pelanggan",
            "Kecepatan paket bisnis menurun pada jam operasional kantor",
            "Jaringan IndiBiz lambat dan menghambat transaksi kasir",
            "Gangguan internet belum selesai sejak pagi",
            "Harga paket bisnis terasa mahal dibanding kualitas jaringan",
            "Koneksi tidak stabil saat rapat daring dengan klien",
            "Layanan pelanggan lambat merespons tiket gangguan",
            "Proses perbaikan jaringan terlalu lama untuk kebutuhan usaha",
            "Internet sering terputus ketika mengunggah data penjualan",
            "Kecepatan unggah tidak sesuai paket yang dipilih",
            "Gangguan jaringan membuat sistem pembayaran tidak dapat digunakan",
            "Teknisi belum datang meskipun laporan sudah dibuat",
            "Tagihan meningkat tetapi kualitas koneksi tidak membaik",
            "WiFi bisnis sering hilang di beberapa ruangan kantor",
            "Koneksi IndiBiz lemot saat dipakai banyak perangkat",
            "Informasi estimasi perbaikan gangguan tidak jelas",
            "Internet mati mendadak dan mengganggu pelayanan pelanggan",
            "Paket bisnis kurang stabil untuk kegiatan live streaming",
            "Respons admin terhadap keluhan perusahaan masih lambat",
            "Jaringan sering bermasalah saat cuaca buruk",
            "Kecepatan internet tidak konsisten sepanjang hari",
            "Instalasi terlambat dari jadwal yang sudah disepakati",
            "Gangguan berulang membuat operasional UMKM terganggu",
            "Harga layanan belum sebanding dengan dukungan teknis",
        ]
        komentar_positif = [
            "Internet IndiBiz stabil untuk operasional toko setiap hari",
            "Teknisi datang tepat waktu dan instalasi dilakukan dengan rapi",
            "Kecepatan internet bisnis sesuai dengan paket yang dipilih",
            "Layanan pelanggan membantu menyelesaikan gangguan dengan cepat",
            "Koneksi stabil saat digunakan untuk rapat daring",
            "Paket IndiBiz membantu digitalisasi usaha kecil kami",
            "Proses pemasangan mudah dan informasinya jelas",
            "Internet lancar untuk sistem kasir dan pembayaran digital",
            "Admin responsif ketika kami meminta bantuan teknis",
            "Kualitas jaringan membaik setelah dilakukan pengecekan",
            "Paket bisnis cukup sesuai untuk kebutuhan kantor kecil",
            "Teknisi ramah dan menjelaskan penggunaan perangkat dengan baik",
            "Koneksi unggah stabil untuk pencadangan data perusahaan",
            "Pelayanan gangguan kali ini cepat dan solutif",
            "IndiBiz mendukung aktivitas penjualan daring tanpa kendala",
            "Jaringan tetap stabil meskipun digunakan banyak perangkat",
        ]
        komentar_netral = [
            "Berapa harga paket IndiBiz untuk usaha kecil",
            "Apakah IndiBiz tersedia di wilayah Bandung Timur",
            "Mohon informasi pilihan kecepatan internet bisnis",
            "Bagaimana cara mengecek status pemasangan IndiBiz",
            "Apakah ada paket khusus untuk kafe dan restoran",
            "Mohon informasi nomor layanan pelanggan IndiBiz",
            "Berapa lama proses instalasi setelah pendaftaran",
            "Apakah paket IndiBiz sudah termasuk perangkat router",
            "Saya ingin mengetahui promo IndiBiz bulan ini",
            "Bagaimana cara mengubah paket internet bisnis",
        ]

        konten = komentar_negatif + komentar_positif + komentar_netral
        sentimen = (
            ["negative"] * len(komentar_negatif)
            + ["positive"] * len(komentar_positif)
            + ["neutral"] * len(komentar_netral)
        )
        platform = ["twitter", "instagram", "tiktok"]
        tanggal_awal = pd.Timestamp("2025-11-01 08:00:00")

        rows = []
        for index, (content, label) in enumerate(zip(konten, sentimen), start=1):
            date_created = tanggal_awal + pd.Timedelta(
                days=(index * 5) % 61,
                hours=(index * 3) % 12,
            )
            rows.append(
                {
                    "username": f"pelaku_usaha_{index:02d}",
                    "platform": platform[(index - 1) % len(platform)],
                    "content": content,
                    "predicted_sentiment": label,
                    "confidence_score": round(float(rng.uniform(0.65, 0.99)), 3),
                    "followers": int(rng.integers(20, 25001)),
                    # Dua kolom kompatibilitas dipertahankan untuk timeline dan teks bersih.
                    "date_created": date_created,
                    "content_clean": _clean_content(content),
                }
            )

        dataframe = pd.DataFrame(rows)
        _validasi_dummy_indibiz(
            dataframe,
            "dummy sentimen IndiBiz",
            50,
            INDIBIZ_SENTIMENT_REQUIRED_COLUMNS,
        )
        if not dataframe["platform"].isin({"twitter", "instagram", "tiktok"}).all():
            raise ValueError("Platform dummy sentimen IndiBiz tidak valid.")
        if not dataframe["predicted_sentiment"].isin(
            {"positive", "neutral", "negative"}
        ).all():
            raise ValueError("Label dummy sentimen IndiBiz tidak valid.")
        if not dataframe["confidence_score"].between(0.65, 0.99).all():
            raise ValueError("Confidence dummy sentimen IndiBiz di luar rentang 0.65-0.99.")
        counts = dataframe["predicted_sentiment"].value_counts()
        if int(counts.get("negative", 0)) <= max(
            int(counts.get("positive", 0)), int(counts.get("neutral", 0))
        ):
            raise ValueError("Sentimen negatif dummy IndiBiz harus paling dominan.")
        return dataframe.reset_index(drop=True)
    except Exception as error:
        raise RuntimeError(f"Gagal membuat dummy sentimen IndiBiz: {error}") from error


def get_dummy_indibiz_sna() -> pd.DataFrame:
    """Buat 30 edge dummy SNA IndiBiz dengan node target utama indibiz."""
    try:
        sumber = [
            "usaha_kopi_bdg", "toko_makmur", "studio_kreatif", "klinik_sehat",
            "bengkel_jaya", "warung_digital", "kantor_hukum", "umkm_cantik",
            "gudang_online", "resto_nusantara", "agen_travel", "laundry_bersih",
            "percetakan_maju", "sekolah_mandiri", "apotek_sentosa", "hotel_mini",
            "konveksi_baru", "peternak_online", "toko_elektronik", "kafe_sudut",
            "indibiz", "admin_indibiz", "usaha_kopi_bdg", "studio_kreatif",
            "klinik_sehat", "toko_makmur", "resto_nusantara", "gudang_online",
            "umkm_cantik", "kafe_sudut",
        ]
        target = [
            "indibiz", "indibiz", "indibiz", "indibiz", "indibiz",
            "indibiz", "indibiz", "indibiz", "indibiz", "indibiz",
            "indibiz", "indibiz", "indibiz", "indibiz", "indibiz",
            "indibiz", "indibiz", "indibiz", "indibiz", "indibiz",
            "usaha_kopi_bdg", "toko_makmur", "admin_indibiz", "indibiz",
            "indibiz", "admin_indibiz", "indibiz", "indibiz",
            "indibiz", "indibiz",
        ]
        relationship = [
            "comment", "mention", "reply", "comment", "mention",
            "comment", "reply", "comment", "mention", "comment",
            "reply", "comment", "mention", "comment", "reply",
            "comment", "mention", "comment", "reply", "comment",
            "reply", "reply", "mention", "reply", "comment",
            "mention", "reply", "comment", "mention", "comment",
        ]
        platform = ["twitter", "instagram", "tiktok"] * 10
        followers = [
            1250, 840, 3100, 2250, 760, 1450, 980, 5400, 1320, 4150,
            1880, 670, 960, 3520, 2110, 1750, 2860, 730, 6200, 3900,
            125000, 18300, 1250, 3100, 2250, 840, 4150, 1320, 5400, 3900,
        ]

        dataframe = pd.DataFrame(
            {
                "source": sumber,
                "target": target,
                "relationship": relationship,
                "followers": followers,
                "platform": platform,
            },
            columns=INDIBIZ_SNA_REQUIRED_COLUMNS,
        )
        _validasi_dummy_indibiz(
            dataframe, "dummy SNA IndiBiz", 30, INDIBIZ_SNA_REQUIRED_COLUMNS
        )
        if not dataframe["relationship"].isin({"comment", "mention", "reply"}).all():
            raise ValueError("Relationship dummy SNA IndiBiz tidak valid.")
        if dataframe["target"].value_counts().idxmax() != "indibiz":
            raise ValueError("Node target utama dummy SNA harus indibiz.")
        return dataframe.reset_index(drop=True)
    except Exception as error:
        raise RuntimeError(f"Gagal membuat dummy SNA IndiBiz: {error}") from error


def get_dummy_indibiz_topics() -> pd.DataFrame:
    """Buat 15 baris topik IndiBiz: lima topik dikalikan tiga sentimen."""
    try:
        topik_dan_kata = {
            "gangguan jaringan": {
                "positive": "jaringan | pulih | stabil",
                "neutral": "jaringan | status | wilayah",
                "negative": "jaringan | lambat | gangguan",
            },
            "kecepatan internet": {
                "positive": "cepat | stabil | lancar",
                "neutral": "kecepatan | paket | perangkat",
                "negative": "lemot | lambat | tidak stabil",
            },
            "harga paket bisnis": {
                "positive": "harga | sesuai | manfaat",
                "neutral": "harga | paket | pilihan",
                "negative": "mahal | tagihan | tidak sebanding",
            },
            "layanan pelanggan": {
                "positive": "responsif | ramah | solutif",
                "neutral": "admin | informasi | bantuan",
                "negative": "lambat | tiket | tidak jelas",
            },
            "instalasi": {
                "positive": "teknisi | cepat | rapi",
                "neutral": "jadwal | pemasangan | perangkat",
                "negative": "terlambat | teknisi | menunggu",
            },
        }

        rows = []
        for topik, kata_per_sentimen in topik_dan_kata.items():
            for sentiment in ("positive", "neutral", "negative"):
                rows.append(
                    {
                        "sentiment": sentiment,
                        "topik": topik,
                        "keywords": kata_per_sentimen[sentiment],
                    }
                )
        dataframe = pd.DataFrame(rows, columns=INDIBIZ_TOPIC_REQUIRED_COLUMNS)
        _validasi_dummy_indibiz(
            dataframe, "dummy topik IndiBiz", 15, INDIBIZ_TOPIC_REQUIRED_COLUMNS
        )
        if dataframe["topik"].nunique() != 5:
            raise ValueError("Dummy topik IndiBiz harus memiliki tepat lima topik.")
        if not dataframe["keywords"].str.contains(r"\s\|\s", regex=True).all():
            raise ValueError("Keywords dummy topik harus dipisahkan dengan ' | '.")
        return dataframe.reset_index(drop=True)
    except Exception as error:
        raise RuntimeError(f"Gagal membuat dummy topik IndiBiz: {error}") from error


def get_dummy_indibiz_top_kata() -> pd.DataFrame:
    """Buat 45 baris top kata IndiBiz: 15 kata untuk setiap sentimen."""
    try:
        kata_per_sentimen = {
            "positive": [
                ("stabil", 34), ("cepat", 31), ("lancar", 29), ("membantu", 27),
                ("responsif", 25), ("teknisi", 23), ("rapi", 21), ("solutif", 19),
                ("sesuai", 18), ("mudah", 17), ("bagus", 16), ("usaha", 15),
                ("digital", 14), ("pelayanan", 13), ("puas", 12),
            ],
            "neutral": [
                ("paket", 30), ("harga", 28), ("informasi", 26), ("indibiz", 24),
                ("internet", 22), ("bisnis", 20), ("wilayah", 18), ("promo", 17),
                ("instalasi", 16), ("router", 15), ("kecepatan", 14), ("layanan", 13),
                ("daftar", 12), ("status", 11), ("kantor", 10),
            ],
            "negative": [
                ("gangguan", 42), ("lambat", 39), ("jaringan", 37), ("lemot", 34),
                ("mahal", 31), ("putus", 29), ("teknisi", 26), ("tagihan", 24),
                ("instalasi", 22), ("menunggu", 20), ("tidak", 19), ("stabil", 18),
                ("respons", 16), ("operasional", 15), ("terlambat", 14),
            ],
        }

        rows = []
        for sentiment in ("positive", "neutral", "negative"):
            for rank, (kata, frekuensi) in enumerate(kata_per_sentimen[sentiment], start=1):
                rows.append(
                    {
                        "sentiment": sentiment,
                        "rank": rank,
                        "kata": kata,
                        "frekuensi": frekuensi,
                    }
                )
        dataframe = pd.DataFrame(rows, columns=INDIBIZ_TOP_KATA_REQUIRED_COLUMNS)
        _validasi_dummy_indibiz(
            dataframe,
            "dummy top kata IndiBiz",
            45,
            INDIBIZ_TOP_KATA_REQUIRED_COLUMNS,
        )
        per_sentiment = dataframe.groupby("sentiment").size().to_dict()
        if per_sentiment != {"negative": 15, "neutral": 15, "positive": 15}:
            raise ValueError("Setiap sentimen harus memiliki tepat 15 kata.")
        return dataframe.reset_index(drop=True)
    except Exception as error:
        raise RuntimeError(f"Gagal membuat dummy top kata IndiBiz: {error}") from error

# ============================================================================
# TAHAP 5 | FASE 9 - MODE DEMO / PRESENTASI SIDANG
# ============================================================================
# Generator berikut bersifat deterministik dan tidak membaca file, model ML,
# internet, atau API eksternal. Seluruh data hanya hidup di memori aplikasi.

_DEMO_SERVICE_SEEDS = {
    "IndiHome": 5101,
    "IndiBiz": 5201,
    "Telkomsel": 5301,
}

_DEMO_SERVICE_PROFILES = {
    "IndiHome": {
        "brand": "IndiHome",
        "brand_node": "indihome",
        "product": "internet rumah",
        "technical": "WiFi dan jaringan fiber",
        "billing": "tagihan bulanan",
        "support": "teknisi IndiHome",
    },
    "IndiBiz": {
        "brand": "IndiBiz",
        "brand_node": "indibiz",
        "product": "internet bisnis",
        "technical": "koneksi kantor dan jaringan bisnis",
        "billing": "invoice layanan bisnis",
        "support": "tim dukungan IndiBiz",
    },
    "Telkomsel": {
        "brand": "Telkomsel",
        "brand_node": "telkomsel",
        "product": "paket data seluler",
        "technical": "sinyal dan jaringan seluler",
        "billing": "pulsa dan tagihan paket",
        "support": "customer care Telkomsel",
    },
}

_DEMO_FIRST_NAMES = (
    "adi", "ayu", "bima", "citra", "dani", "dinda", "eka", "fajar",
    "fitri", "galih", "hana", "indah", "joko", "kiki", "laila", "mega",
    "nanda", "putri", "raka", "rani", "rizky", "salsa", "tio", "wahyu",
    "yoga", "zaki", "amanda", "bagas", "dewi", "farhan",
)

_DEMO_CITIES = (
    "bandung", "jakarta", "surabaya", "medan", "makassar", "semarang",
    "yogyakarta", "denpasar", "palembang", "balikpapan",
)

_DEMO_TOP_INFLUENCERS = {
    "IndiHome": (
        ("rumahdigital.id", "instagram", 48200),
        ("teknologikita", "twitter", 36750),
        ("wifi.harian", "tiktok", 32100),
        ("keluargadaring", "instagram", 28600),
        ("suarapelanggan", "twitter", 24150),
        ("gadgetpraktis", "tiktok", 19800),
        ("kerjadari.rumah", "instagram", 16300),
        ("internetupdate", "twitter", 12750),
        ("tipsrouter", "tiktok", 9400),
        ("digitalbandung", "instagram", 7200),
    ),
    "IndiBiz": (
        ("umkmbertumbuh", "instagram", 49600),
        ("bisnisdigital.id", "twitter", 42100),
        ("usahapraktis", "tiktok", 38600),
        ("komunitasumkm", "instagram", 33750),
        ("operasionalbisnis", "twitter", 29100),
        ("tokonaikkelas", "tiktok", 24300),
        ("solusikantor", "instagram", 18700),
        ("bisnisupdate", "twitter", 14950),
        ("teknologi.umkm", "tiktok", 11200),
        ("wirausahabandung", "instagram", 8300),
    ),
    "Telkomsel": (
        ("mobileupdate.id", "instagram", 50000),
        ("sinyalnusantara", "twitter", 45800),
        ("gadgetharian", "tiktok", 39900),
        ("komunitasdigital", "instagram", 35200),
        ("infokuota", "twitter", 30750),
        ("teknologisingkat", "tiktok", 26600),
        ("jelajahinternet", "instagram", 21400),
        ("jaringanupdate", "twitter", 17100),
        ("tipsponsel", "tiktok", 12800),
        ("digitalmakassar", "instagram", 9100),
    ),
}


def _normalisasi_demo_service(layanan: str) -> str:
    """Pastikan nama layanan demo selalu salah satu dari tiga layanan aktif."""
    text = str(layanan or "IndiHome").strip().casefold()
    mapping = {
        "indihome": "IndiHome",
        "indibiz": "IndiBiz",
        "telkomsel": "Telkomsel",
    }
    return mapping.get(text, "IndiHome")


def _demo_usernames(layanan: str, jumlah: int = 130) -> list[str]:
    """Buat daftar username realistis dan deterministik untuk satu layanan."""
    service = _normalisasi_demo_service(layanan)
    top_names = [item[0] for item in _DEMO_TOP_INFLUENCERS[service]]
    generated: list[str] = []
    for index in range(max(0, int(jumlah) - len(top_names))):
        first = _DEMO_FIRST_NAMES[index % len(_DEMO_FIRST_NAMES)]
        city = _DEMO_CITIES[(index // len(_DEMO_FIRST_NAMES)) % len(_DEMO_CITIES)]
        generated.append(f"{first}_{city}_{index + 1:03d}")
    return (top_names + generated)[:jumlah]


def _demo_comment_pool(layanan: str) -> dict[str, list[str]]:
    """Bangun sedikitnya 50 komentar unik yang relevan untuk satu layanan."""
    service = _normalisasi_demo_service(layanan)
    profile = _DEMO_SERVICE_PROFILES[service]
    brand = profile["brand"]
    product = profile["product"]
    technical = profile["technical"]
    billing = profile["billing"]
    support = profile["support"]

    negative = [
        f"{technical.capitalize()} sering putus saat jam sibuk, mohon {brand} segera memperbaikinya.",
        f"Sudah tiga hari {product} tidak stabil dan laporan saya belum mendapat kepastian.",
        f"Harga {product} naik tetapi kualitasnya masih sering lambat dan tidak konsisten.",
        f"Gangguan {technical} membuat pekerjaan dan rapat daring saya terhenti.",
        f"{billing.capitalize()} terasa mahal karena kualitas layanan belum sebanding.",
        f"Saya sudah menghubungi {support}, tetapi kendalanya belum selesai sampai sekarang.",
        f"Provider lain di wilayah saya lebih stabil dibandingkan {brand} minggu ini.",
        f"Koneksi hilang mendadak setiap malam dan perangkat harus direstart berkali-kali.",
        f"Informasi gangguan kurang jelas, pelanggan hanya diminta menunggu tanpa estimasi.",
        f"Kecepatan turun jauh dari paket yang dibayar ketika banyak perangkat terhubung.",
        f"Layanan terputus setelah hujan dan pemulihannya terlalu lama.",
        f"Aplikasi layanan sulit dibuka saat saya perlu mengecek status gangguan.",
        f"Permintaan teknisi sudah dibuat tetapi jadwal kunjungan terus berubah.",
        f"Saya kecewa karena keluhan yang sama berulang setiap pekan.",
        f"Kualitas jaringan di area pinggiran masih lemah dan sering kehilangan koneksi.",
        f"Tagihan tetap penuh padahal layanan mengalami gangguan cukup lama.",
        f"Respons admin cepat di awal, tetapi tindak lanjut teknisnya lambat.",
        f"Koneksi tidak cukup stabil untuk mengunggah file besar dan video konferensi.",
        f"Paket terlihat menarik, tetapi performa aktualnya belum sesuai promosi.",
        f"Mohon evaluasi kualitas {brand} di wilayah saya karena gangguan makin sering.",
    ]

    positive = [
        f"{technical.capitalize()} hari ini stabil dan kecepatannya sesuai paket, terima kasih {brand}.",
        f"{support.capitalize()} merespons cepat dan memberikan solusi yang mudah diikuti.",
        f"Teknisi datang tepat waktu, ramah, dan menjelaskan penyebab gangguan dengan jelas.",
        f"Proses aktivasi {product} berjalan lancar tanpa kendala berarti.",
        f"Saya puas karena laporan gangguan diselesaikan pada hari yang sama.",
        f"Koneksi stabil untuk bekerja, belajar, dan menonton video bersama keluarga.",
        f"Informasi pemeliharaan disampaikan dengan jelas sehingga pelanggan bisa bersiap.",
        f"Paket yang saya gunakan cukup seimbang antara harga, kuota, dan kualitas.",
        f"Admin media sosial {brand} membantu mengecek tiket dengan cepat.",
        f"Setelah perbaikan, kualitas jaringan jauh lebih baik dan jarang terputus.",
        f"Aplikasi layanan memudahkan saya memantau penggunaan dan pembayaran.",
        f"Pelayanan pelanggan sopan, tidak berbelit, dan solusinya tepat.",
        f"Kecepatan unggah cukup bagus untuk rapat daring dan berbagi dokumen.",
        f"Saya mengapresiasi pembaruan status gangguan yang diberikan secara berkala.",
        f"Instalasi rapi dan petugas memastikan semua perangkat dapat terhubung.",
        f"Promo paket bulan ini membantu menghemat biaya penggunaan internet.",
        f"Jaringan tetap stabil meskipun digunakan beberapa perangkat sekaligus.",
        f"Terima kasih {brand}, layanan di area saya semakin konsisten dibanding bulan lalu.",
    ]

    neutral = [
        f"Apakah ada jadwal pemeliharaan {technical} di wilayah Bandung minggu ini?",
        f"Mohon informasi pilihan {product} yang cocok untuk penggunaan harian.",
        f"Bagaimana cara mengecek rincian {billing} melalui aplikasi resmi?",
        f"Apakah pelanggan bisa mengubah paket tanpa mengganti nomor atau perangkat?",
        f"Saya ingin mengetahui estimasi waktu pemasangan layanan baru di alamat saya.",
        f"Admin, mohon bantu cek status tiket gangguan yang sudah dibuat kemarin.",
        f"Apakah ada promo {product} untuk periode November sampai Desember 2025?",
        f"Berapa jumlah perangkat yang disarankan untuk paket yang saya gunakan?",
        f"Mohon informasi kanal resmi untuk menyampaikan keluhan teknis.",
        f"Apakah kualitas layanan berbeda untuk setiap wilayah dan jam penggunaan?",
        f"Saya sedang membandingkan paket {brand} dengan provider lain sebelum berlangganan.",
        f"Bagaimana prosedur pengajuan kompensasi ketika terjadi gangguan cukup lama?",
    ]
    return {"negative": negative, "positive": positive, "neutral": neutral}


@st.cache_data(show_spinner=False, max_entries=12)
def get_demo_sentiment(layanan: str = "IndiHome") -> pd.DataFrame:
    """Kembalikan 500 baris sentimen demo dengan distribusi 40/35/25 persen."""
    try:
        service = _normalisasi_demo_service(layanan)
        rng = np.random.default_rng(_DEMO_SERVICE_SEEDS[service])
        pools = _demo_comment_pool(service)
        labels = np.array(
            ["negative"] * 200 + ["positive"] * 175 + ["neutral"] * 125,
            dtype=object,
        )
        rng.shuffle(labels)
        usernames = _demo_usernames(service, 130)
        top_followers = {
            name: followers
            for name, _, followers in _DEMO_TOP_INFLUENCERS[service]
        }
        top_platform = {
            name: platform
            for name, platform, _ in _DEMO_TOP_INFLUENCERS[service]
        }
        start = pd.Timestamp("2025-11-01 00:00:00")
        total_seconds = int((pd.Timestamp("2025-12-31 23:59:59") - start).total_seconds())
        rows: list[dict[str, object]] = []
        label_offsets = {"negative": 0, "positive": 0, "neutral": 0}

        for index, label in enumerate(labels.tolist()):
            username = usernames[index % len(usernames)]
            pool = pools[label]
            content = pool[label_offsets[label] % len(pool)]
            label_offsets[label] += 1
            platform = top_platform.get(
                username,
                ("twitter", "instagram", "tiktok")[(index + rng.integers(0, 3)) % 3],
            )
            followers = top_followers.get(username, int(rng.integers(10, 18_500)))
            confidence = round(float(rng.uniform(0.75, 0.98)), 4)
            date_created = start + pd.Timedelta(seconds=int(rng.integers(0, total_seconds + 1)))
            engagement = max(1, int(round((followers ** 0.52) * rng.uniform(0.8, 3.4))))
            rows.append(
                {
                    "date_created": date_created,
                    "date": date_created,
                    "layanan": service,
                    "platform": platform,
                    "username": username,
                    "followers": int(followers),
                    "content": content,
                    "content_clean": _clean_content(content),
                    "predicted_sentiment": label,
                    "confidence_score": confidence,
                    "confidence": confidence,
                    "engagement": engagement,
                    "like": int(engagement * 0.68),
                    "comment": max(1, int(engagement * 0.20)),
                    "share": max(0, int(engagement * 0.12)),
                }
            )

        dataframe = pd.DataFrame(rows)
        return dataframe.sort_values("date_created", ascending=False).reset_index(drop=True)
    except Exception as exc:
        raise RuntimeError(f"Gagal membuat data sentimen Mode Demo {layanan}: {exc}") from exc


@st.cache_data(show_spinner=False, max_entries=12)
def get_demo_sna(layanan: str = "IndiHome") -> pd.DataFrame:
    """Kembalikan 190 edge demo dengan sedikitnya 120 node pengguna unik."""
    try:
        service = _normalisasi_demo_service(layanan)
        profile = _DEMO_SERVICE_PROFILES[service]
        brand = profile["brand_node"]
        rng = np.random.default_rng(_DEMO_SERVICE_SEEDS[service] + 101)
        usernames = _demo_usernames(service, 120)
        top_followers = {
            name: followers
            for name, _, followers in _DEMO_TOP_INFLUENCERS[service]
        }
        top_platform = {
            name: platform
            for name, platform, _ in _DEMO_TOP_INFLUENCERS[service]
        }
        follower_map = {
            username: int(top_followers.get(username, rng.integers(10, 50_001)))
            for username in usernames
        }
        platform_map = {
            username: top_platform.get(
                username,
                ("twitter", "instagram", "tiktok")[index % 3],
            )
            for index, username in enumerate(usernames)
        }
        edges: list[dict[str, object]] = []

        for index, username in enumerate(usernames):
            platform = platform_map[username]
            relationship = (
                "comment"
                if platform in {"instagram", "tiktok"}
                else ("mention" if index % 2 == 0 else "reply")
            )
            edges.append(
                {
                    "source": username,
                    "target": brand,
                    "relationship": relationship,
                    "followers": follower_map[username],
                    "platform": platform,
                    "layanan": service,
                    "weight": int(rng.integers(1, 8)),
                }
            )

        # Tambahkan hubungan antarpengguna agar graf tidak hanya hub-and-spoke.
        for index in range(70):
            source = usernames[index % len(usernames)]
            target = usernames[(index * 7 + 13) % len(usernames)]
            if source == target:
                target = usernames[(index * 7 + 14) % len(usernames)]
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "relationship": "reply" if index % 2 == 0 else "mention",
                    "followers": follower_map[source],
                    "platform": platform_map[source],
                    "layanan": service,
                    "weight": int(rng.integers(1, 5)),
                }
            )
        return pd.DataFrame(edges).reset_index(drop=True)
    except Exception as exc:
        raise RuntimeError(f"Gagal membuat data SNA Mode Demo {layanan}: {exc}") from exc


@st.cache_data(show_spinner=False, max_entries=12)
def get_demo_topics(layanan: str = "IndiHome") -> list[dict[str, object]]:
    """Kembalikan 15 topik demo: masing-masing lima positif, netral, negatif."""
    service = _normalisasi_demo_service(layanan)
    profile = _DEMO_SERVICE_PROFILES[service]
    brand = profile["brand"].casefold()
    technical = profile["technical"].casefold()
    billing = profile["billing"].casefold()
    topics = {
        "positive": [
            ("Kualitas Jaringan Stabil", ["stabil", "lancar", "cepat", technical]),
            ("Pelayanan Pelanggan Responsif", ["responsif", "cepat", "ramah", "solutif"]),
            ("Teknisi Profesional", ["teknisi", "tepat waktu", "rapi", "profesional"]),
            ("Paket Sesuai Kebutuhan", ["paket", "sesuai", "hemat", "worth it"]),
            ("Apresiasi Brand", [brand, "terima kasih", "puas", "keren"]),
        ],
        "neutral": [
            ("Informasi Paket", ["info", "paket", "harga", "promo"]),
            ("Status Gangguan", ["status", "gangguan", "estimasi", "wilayah"]),
            ("Cara Pembayaran", [billing, "bayar", "aplikasi", "rincian"]),
            ("Ketersediaan Layanan", ["tersedia", "alamat", "cakupan", "pemasangan"]),
            ("Pertanyaan kepada Admin", ["admin", "mohon cek", "bantu", "tiket"]),
        ],
        "negative": [
            ("Gangguan Jaringan", ["gangguan", "putus", "down", technical]),
            ("Kecepatan Lambat", ["lambat", "lemot", "turun", "jam sibuk"]),
            ("Harga Tidak Sebanding", ["mahal", billing, "tidak sebanding", "naik"]),
            ("Respons Penanganan Lambat", ["belum selesai", "menunggu", "lambat", "keluhan"]),
            ("Perbandingan Provider", ["provider lain", "lebih stabil", "kompetitor", "kecewa"]),
        ],
    }
    records: list[dict[str, object]] = []
    for sentiment, values in topics.items():
        for rank, (label, keywords) in enumerate(values, start=1):
            records.append(
                {
                    "label": label,
                    "keywords": keywords,
                    "sentiment": sentiment,
                    "layanan": service,
                    "rank": rank,
                }
            )
    return records


@st.cache_data(show_spinner=False, max_entries=12)
def get_demo_influencers(layanan: str = "IndiHome") -> pd.DataFrame:
    """Kembalikan 10 influencer demo dengan metrik jaringan realistis."""
    try:
        service = _normalisasi_demo_service(layanan)
        rows: list[dict[str, object]] = []
        for rank, (username, platform, followers) in enumerate(
            _DEMO_TOP_INFLUENCERS[service], start=1
        ):
            degree_centrality = round(max(0.04, 0.42 - (rank - 1) * 0.035), 4)
            in_degree = max(2, 19 - rank)
            out_degree = max(2, 15 - rank)
            network_edges = in_degree + out_degree
            recommendation_score = round(max(0.52, 0.97 - (rank - 1) * 0.045), 4)
            rows.append(
                {
                    "username": username,
                    "username_key": username.casefold(),
                    "platform": platform,
                    "followers": int(followers),
                    "degree_centrality": degree_centrality,
                    "in_degree": in_degree,
                    "out_degree": out_degree,
                    "degree": network_edges,
                    "network_edges": network_edges,
                    "interaksi": network_edges * 6 + rank * 3,
                    "content_count": 4 + (rank % 3),
                    "relevant_content_count": 3 + (rank % 3),
                    "content_engagement": max(25, int(followers * (0.008 + rank * 0.0003))),
                    "dominant_topic": "Gangguan Jaringan" if rank % 3 == 0 else "Kualitas Layanan",
                    "content_topics": "Gangguan Jaringan|Kualitas Layanan|Bantuan Pelanggan",
                    "recommendation_score": recommendation_score,
                    "recommendation_rank": rank,
                    "selection_basis": "Jaringan + konten sample",
                    "kategori": "Hybrid Influencer" if rank <= 3 else "Reach Influencer",
                    "teridentifikasi": True,
                    "layanan": service,
                }
            )
        return pd.DataFrame(rows)
    except Exception as exc:
        raise RuntimeError(f"Gagal membuat influencer Mode Demo {layanan}: {exc}") from exc


def get_demo_prediction(text: str, layanan: str = "IndiHome") -> dict[str, object]:
    """Klasifikasi lokal ringan untuk prediksi manual tanpa memuat IndoBERT."""
    raw_text = str(text or "").strip()
    if not raw_text:
        raise ValueError("Teks komentar masih kosong.")
    cleaned = _clean_content(raw_text)
    positive_words = {
        "bagus", "cepat", "stabil", "puas", "ramah", "membantu", "mantap",
        "lancar", "terima kasih", "responsif", "profesional", "solutif",
    }
    negative_words = {
        "lambat", "lemot", "gangguan", "putus", "mahal", "kecewa", "jelek",
        "down", "hilang", "parah", "belum selesai", "tidak stabil",
    }
    positive_score = sum(1 for word in positive_words if word in cleaned)
    negative_score = sum(1 for word in negative_words if word in cleaned)
    if negative_score > positive_score:
        winner = "negative"
        probabilities = {"positive": 0.06, "neutral": 0.12, "negative": 0.82}
    elif positive_score > negative_score:
        winner = "positive"
        probabilities = {"positive": 0.84, "neutral": 0.11, "negative": 0.05}
    else:
        winner = "neutral"
        probabilities = {"positive": 0.18, "neutral": 0.68, "negative": 0.14}
    return {
        "label": winner,
        "label_id": {"positive": "Positif", "neutral": "Netral", "negative": "Negatif"}[winner],
        "confidence": float(probabilities[winner]),
        "probabilities": probabilities,
        "cleaned_text": cleaned,
        "layanan": _normalisasi_demo_service(layanan),
    }

