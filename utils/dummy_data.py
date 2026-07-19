"""Generator data dummy konsisten dengan hasil penelitian skripsi."""

import re

import numpy as np
import pandas as pd

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

