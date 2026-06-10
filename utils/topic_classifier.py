"""
Modul klasifikasi topik berbasis keyword matching untuk komentar IndiHome.

Mengelompokkan teks ke dalam topik dominan per sentimen (positif, netral, negatif)
menggunakan kamus kata kunci TOPICS.
"""

from __future__ import annotations

import re
from collections import Counter

import pandas as pd

# --- Pemetaan label sentimen ke kunci kanonik ---
SENTIMENT_KEYS = {
    "positive": "positive",
    "positif": "positive",
    "label_0": "positive",
    "neutral": "neutral",
    "netral": "neutral",
    "label_1": "neutral",
    "negative": "negative",
    "negatif": "negative",
    "label_2": "negative",
}

# --- Kamus topik: 12 topik per sentimen, masing-masing 15–20 kata kunci ---
TOPICS: dict[str, dict[str, list[str]]] = {
    "positive": {
        "Apresiasi Kecepatan Internet": [
            "cepat", "kencang", "ngebut", "kilat", "gesit", "laju", "deras",
            "speed", "kecepatan", "mbps", "download", "upload", "internet cepat",
            "koneksi cepat", "ngebut banget", "mantap cepat", "kenceng", "ngebut",
            "responsif", "lancar jaya",
        ],
        "Koneksi Stabil dan Handal": [
            "stabil", "stabil banget", "handal", "konsisten", "lancar", "mulus",
            "tidak putus", "anti putus", "solid", "mantap", "oke", "bagus",
            "koneksi stabil", "internet stabil", "wifi stabil", "sinyal stabil",
            "reliable", "terjamin", "aman", "nyaman",
        ],
        "Kepuasan Layanan CS": [
            "cs", "customer service", "layanan pelanggan", "responsif", "ramah",
            "solutif", "membantu", "tanggap", "cepat respon", "helpful",
            "pelayanan bagus", "cs bagus", "cs ramah", "cs cepat", "ditangani",
            "terima kasih cs", "puas cs", "admin ramah", "adm ramah", "cs mantap",
        ],
        "Teknisi Cepat dan Profesional": [
            "teknisi", "tukang pasang", "petugas", "teknisi cepat", "teknisi ramah",
            "profesional", "tepat waktu", "datang cepat", "instalasi rapi",
            "pemasangan rapi", "kerja rapi", "sopan", "sigap", "handal",
            "teknisi bagus", "teknisi profesional", "petugas ramah", "pasang cepat",
            "teknisi tanggap", "teknisi mantap",
        ],
        "Pemasangan Baru Lancar": [
            "pemasangan", "instalasi", "pasang baru", "pasang indihome", "aktivasi",
            "aktif", "terpasang", "berhasil pasang", "lancar pasang", "mudah pasang",
            "proses cepat", "pasang lancar", "instalasi lancar", "pasang wifi",
            "pasang inet", "pasang internet", "baru pasang", "sudah terpasang",
            "aktivasi lancar", "pemasangan lancar",
        ],
        "Harga Sesuai Kualitas": [
            "worth it", "sebanding", "sesuai", "worth", "value", "murah worth",
            "harga oke", "harga pas", "harga wajar", "sesuai kualitas",
            "murah bagus", "terjangkau", "hemat", "puas harga", "reasonable",
            "harga masuk akal", "murah meriah", "murah kualitas bagus",
            "harga cocok", "value for money",
        ],
        "Promo dan Paket Menarik": [
            "promo", "diskon", "paket", "penawaran", "bundling", "gratis",
            "hemat", "murah", "deal", "paket menarik", "promo menarik",
            "promo bagus", "ada promo", "paket bagus", "paket oke",
            "penawaran menarik", "promo mantap", "paket hemat", "promo hemat",
            "paket worth",
        ],
        "Aplikasi MyIndiHome Mudah Digunakan": [
            "myindihome", "aplikasi", "apps", "app", "mudah", "user friendly",
            "gampang", "praktis", "simple", "intuitif", "fitur lengkap",
            "aplikasi bagus", "app bagus", "my indihome", "aplikasi mudah",
            "apps mudah", "login mudah", "aplikasi lancar", "app lancar",
            "myindihome bagus",
        ],
        "Sinyal dan Coverage Bagus": [
            "sinyal", "coverage", "jangkauan", "sinyal bagus", "sinyal kuat",
            "sinyal stabil", "jangkauan luas", "area luas", "sinyal oke",
            "sinyal mantap", "coverage bagus", "sinyal full", "sinyal jernih",
            "sinyal terbaik", "sinyal mantul", "wifi kuat", "sinyal kuat banget",
            "jangkauan bagus", "sinyal memuaskan", "coverage mantap",
        ],
        "Masalah Cepat Diselesaikan": [
            "cepat selesai", "cepat ditangani", "cepat pulih", "cepat normal",
            "cepat diperbaiki", "sudah normal", "sudah pulih", "sudah oke",
            "masalah selesai", "gangguan selesai", "fixed", "teratasi",
            "beres", "solved", "cepat beres", "langsung normal", "cepat fix",
            "ditangani cepat", "perbaikan cepat", "recovery cepat",
        ],
        "Rekomendasi ke Orang Lain": [
            "rekomendasi", "rekomend", "recommended", "saranin", "saran",
            "cobain", "coba", "pake indihome", "pakai indihome", "worth dicoba",
            "bagus banget", "mantap banget", "keren banget", "the best",
            "terbaik", "juara", "top", "rekom banget", "saranin indihome",
            "wajib coba",
        ],
        "Layanan Memuaskan Secara Umum": [
            "puas", "memuaskan", "bagus", "mantap", "keren", "sakti", "terbaik",
            "oke banget", "mantul", "recommended", "love", "suka", "senang",
            "puas banget", "layanan bagus", "indihome bagus", "puas indihome",
            "puas layanan", "memuaskan banget", "overall bagus",
        ],
    },
    "neutral": {
        "Pertanyaan Info Paket / Harga": [
            "berapa harga", "harga", "paket", "info paket", "info harga",
            "berapa", "biaya", "tarif", "harga paket", "paket murah",
            "paket berapa", "harga berapa", "min harga", "min paket",
            "berapa biaya", "info biaya", "daftar paket", "pilihan paket",
            "paket tersedia", "harga promo",
        ],
        "Pertanyaan Cara Pemasangan Baru": [
            "cara pasang", "cara daftar", "cara berlangganan", "cara pemasangan",
            "bagaimana pasang", "gimana pasang", "syarat pasang", "prosedur",
            "cara instalasi", "daftar indihome", "pasang baru", "langganan baru",
            "cara apply", "cara order", "cara subscribe", "info pemasangan",
            "proses pasang", "cara aktifasi", "cara aktivasi", "cara pasang wifi",
        ],
        "Konfirmasi Gangguan di Area Tertentu": [
            "gangguan", "area", "wilayah", "lokasi", "daerah", "cek gangguan",
            "info gangguan", "status gangguan", "gangguan area", "maintenance",
            "pemeliharaan", "gangguan jaringan", "internet down area",
            "gangguan di", "wilayah saya", "daerah saya", "lokasi saya",
            "gangguan bandung", "gangguan jakarta", "konfirmasi gangguan",
        ],
        "Pertanyaan Fitur Aplikasi MyIndiHome": [
            "myindihome", "aplikasi", "app", "fitur", "cara pakai", "cara login",
            "cara bayar", "fitur aplikasi", "my indihome", "apps indihome",
            "cara cek tagihan", "cara cek", "fitur myindihome", "tutorial app",
            "cara setting", "cara ubah", "cara ganti", "fitur baru",
            "update aplikasi", "aplikasi error netral",
        ],
        "Laporan Gangguan (tanpa emosi kuat)": [
            "lapor gangguan", "laporan gangguan", "internet mati", "internet down",
            "tidak bisa akses", "gabisa akses", "koneksi putus", "gangguan jaringan",
            "wifi mati", "inet mati", "lapor masalah", "ada gangguan",
            "mengalami gangguan", "kendala jaringan", "kendala internet",
            "internet tidak jalan", "wifi tidak jalan", "lapor kendala",
            "signal hilang", "sinyal hilang",
        ],
        "Permintaan Bantuan ke Admin/CS": [
            "tolong", "bantu", "bantuan", "admin", "adm", "min", "mimin",
            "cs", "customer service", "hubungi", "contact", "dm", "inbox",
            "minta bantuan", "butuh bantuan", "tolong bantu", "min tolong",
            "adm tolong", "cs tolong", "bantu cek", "bantu proses",
        ],
        "Info Perpanjangan atau Pembayaran": [
            "tagihan", "bayar", "pembayaran", "perpanjang", "perpanjangan",
            "jatuh tempo", "due date", "invoice", "billing", "cek tagihan",
            "bayar tagihan", "cara bayar", "metode bayar", "transfer",
            "virtual account", "va", "autodebet", "perpanjang paket",
            "renewal", "renew",
        ],
        "Perbandingan Paket / Provider Lain": [
            "perbandingan", "banding", "vs", "dibanding", "provider lain",
            "starlink", "first media", "biznet", "iconnet", "myrepublic",
            "oxigen", "indihome vs", "lebih bagus", "lebih murah",
            "alternatif", "kompetitor", "pindah provider", "ganti provider",
            "provider mana", "bandingkan paket",
        ],
        "Pertanyaan Upgrade Kecepatan": [
            "upgrade", "naikkan", "tambah kecepatan", "upgrade paket",
            "upgrade speed", "naik paket", "paket lebih cepat", "upgrade mbps",
            "tambah mbps", "speed up", "naik speed", "upgrade indihome",
            "ganti paket", "ubah paket", "upgrade ke", "naik kecepatan",
            "tambah bandwidth", "upgrade bandwidth", "paket upgrade",
            "info upgrade",
        ],
        "Feedback Netral tentang Layanan": [
            "feedback", "masukan", "saran", "komentar", "pendapat", "review",
            "ulasan", "sharing", "pengalaman", "cerita", "pengalaman pakai",
            "sudah pakai", "baru pakai", "lumayan", "cukup", "standar",
            "biasa aja", "oke aja", "netral", "secara umum", "overall",
        ],
        "Pertanyaan Teknis Umum": [
            "cara setting", "cara reset", "cara restart", "modem", "router",
            "wifi", "password", "ssid", "ip address", "dns", "port",
            "kabel", "lan", "ont", "stb", "set top box", "teknis",
            "konfigurasi", "troubleshoot", "cara atur",
        ],
        "Menunggu Respon / Follow Up": [
            "menunggu", "nunggu", "belum ada respon", "belum dibalas",
            "belum ditanggapi", "follow up", "fu", "tindak lanjut", "update",
            "kapan respon", "kapan dibalas", "sudah lama", "berapa lama",
            "masih menunggu", "tolong respon", "mohon respon", "cepat respon",
            "belum selesai", "masih proses", "status permintaan",
        ],
    },
    "negative": {
        "Keluhan Internet Lemot / Ngelag": [
            "lemot", "lelet", "lambat", "lamban", "lemban", "ngelag", "lag",
            "lambat banget", "lemot banget", "lelet banget", "internet lemot",
            "wifi lemot", "inet lemot", "koneksi lambat", "speed lambat",
            "mbps rendah", "kecepatan lambat", "loading lama", "buffering",
            "pelan",
        ],
        "Koneksi Putus-putus / Tidak Stabil": [
            "putus", "putus putus", "putus-putus", "tidak stabil", "gak stabil",
            "ga stabil", "nggak stabil", "fluctuate", "on off", "on-off",
            "kadang mati", "sering putus", "koneksi putus", "wifi putus",
            "internet putus", "drop", "disconnect", "hilang sinyal", "sinyal ilang",
            "intermittent",
        ],
        "Gangguan Total / Internet Mati": [
            "mati", "down", "internet mati", "wifi mati", "inet mati",
            "gabisa", "gak bisa", "ga bisa", "nggak bisa", "tidak bisa",
            "no internet", "offline", "mati total", "mati dari", "down dari",
            "gangguan total", "mati semua", "internet down", "wifi down",
            "mati berjam",
        ],
        "Harga Mahal Tidak Sesuai Kualitas": [
            "mahal", "mahal banget", "kemahalan", "tidak sebanding", "ga sebanding",
            "gak sebanding", "nggak sebanding", "mahal tapi", "harga mahal",
            "mahal untuk", "overprice", "tidak worth", "ga worth", "gak worth",
            "mahal lemot", "mahal lambat", "mahal jelek", "byar pet", "bayar mahal",
            "tagihan mahal",
        ],
        "Teknisi Lambat / Tidak Kunjung Datang": [
            "teknisi lambat", "teknisi lelet", "teknisi tidak datang",
            "teknisi gak datang", "teknisi ga datang", "tidak kunjung",
            "belum datang", "lama datang", "janji tidak datang", "petugas lambat",
            "tukang lambat", "teknisi lama", "nunggu teknisi", "teknisi telat",
            "teknisi tidak kunjung", "petugas tidak datang", "teknisi ilang",
            "teknisi tidak responsif", "teknisi jelek", "teknisi parah",
        ],
        "CS Tidak Responsif / Tidak Membantu": [
            "cs lambat", "cs tidak responsif", "cs gak responsif", "cs ga responsif",
            "cs tidak membantu", "cs gak membantu", "cs jelek", "cs parah",
            "customer service lambat", "layanan lambat", "tidak ditanggapi",
            "tidak dibalas", "cs cuek", "cs tidak ramah", "cs tidak solutif",
            "cs tidak tanggap", "cs buruk", "pelayanan buruk", "cs tidak ada",
            "cs tidak membantu sama sekali",
        ],
        "Pemasangan Baru Lama / Bermasalah": [
            "pemasangan lama", "instalasi lama", "pasang lama", "proses lama",
            "belum terpasang", "belum pasang", "pemasangan bermasalah",
            "instalasi bermasalah", "pasang bermasalah", "aktivasi lama",
            "aktivasi gagal", "pasang gagal", "pemasangan gagal", "tunggu lama",
            "antri lama", "proses berbulan", "belum aktif", "belum jalan",
            "pasang tidak selesai", "instalasi tidak selesai",
        ],
        "Tagihan Bermasalah / Salah Tagih": [
            "tagihan salah", "salah tagih", "tagihan aneh", "tagihan membengkak",
            "tagihan tidak sesuai", "double tagihan", "tagihan dobel",
            "tagihan mahal", "tagihan tidak wajar", "billing salah",
            "invoice salah", "kena tagihan", "tagihan tidak jelas",
            "tagihan bermasalah", "tagihan error", "overcharge", "kelebihan tagih",
            "tagihan membohongi", "tagihan tidak masuk akal", "tagihan parah",
        ],
        "Aplikasi MyIndiHome Error": [
            "aplikasi error", "app error", "myindihome error", "aplikasi bug",
            "app bug", "aplikasi crash", "app crash", "aplikasi lemot",
            "aplikasi tidak bisa", "app tidak bisa", "login gagal",
            "aplikasi hang", "aplikasi force close", "myindihome bug",
            "aplikasi bermasalah", "app bermasalah", "aplikasi jelek",
            "myindihome tidak bisa", "aplikasi down", "app down",
        ],
        "Keluhan Tidak Ditanggapi / Diabaikan": [
            "tidak ditanggapi", "gak ditanggapi", "ga ditanggapi", "diabaikan",
            "tidak dibalas", "gak dibalas", "ga dibalas", "tidak ada respon",
            "gak ada respon", "ga ada respon", "komplain diabaikan",
            "laporan diabaikan", "tidak ada tindak lanjut", "gak ada tindak lanjut",
            "tidak diproses", "gak diproses", "diacuhkan", "tidak diurus",
            "gak diurus", "tidak ditangani", "gak ditangani",
        ],
        "Niat Pindah Provider": [
            "pindah provider", "ganti provider", "berhenti", "unsubscribe",
            "cabut", "putus berlangganan", "stop langganan", "cancel",
            "batal langganan", "pindah ke", "migrasi", "switch provider",
            "ganti ke starlink", "ganti ke biznet", "ganti ke first media",
            "tidak mau pakai lagi", "gak mau pakai lagi", "ga mau pakai lagi",
            "capek indihome", "muak indihome",
        ],
        "Kecewa dengan Promo / Paket": [
            "kecewa promo", "kecewa paket", "promo menipu", "promo palsu",
            "janji palsu", "tidak sesuai promo", "paket mengecewakan",
            "promo mengecewakan", "kecewa banget", "disappointed", "zonk",
            "tipu daya", "promo zonk", "paket zonk", "promo tidak sesuai",
            "janji tidak sesuai", "kecewa indihome", "kecewa layanan",
            "promo parah", "paket parah",
        ],
    },
}

DEFAULT_TOPIC = "Lainnya"


def _normalize_sentiment(sentiment: str) -> str:
    """Ubah label sentimen ke kunci kanonik positive/neutral/negative."""
    key = str(sentiment or "").lower().strip()
    return SENTIMENT_KEYS.get(key, key)


def _count_keyword_matches(text: str, keywords: list[str]) -> int:
    """Hitung jumlah kata kunci yang cocok dalam teks."""
    if not text:
        return 0

    count = 0
    for keyword in keywords:
        kw = str(keyword).lower().strip()
        if not kw:
            continue
        # Kata pendek pakai word boundary agar tidak salah match
        if len(kw) <= 3:
            pattern = rf"(?<!\w){re.escape(kw)}(?!\w)"
            if re.search(pattern, text):
                count += 1
        elif kw in text:
            count += 1
    return count


def classify_topic(text: str, sentiment: str) -> str:
    """
    Klasifikasikan teks ke topik dominan berdasarkan kata kunci dan sentimen.

    Args:
        text: Teks komentar (disarankan content_clean).
        sentiment: Label sentimen (positive/neutral/negative atau label_0/1/2).

    Returns:
        Nama topik dengan match terbanyak, atau "Lainnya" jika tidak ada match.
    """
    try:
        if not text or not str(text).strip():
            return DEFAULT_TOPIC

        sent_key = _normalize_sentiment(sentiment)
        topic_map = TOPICS.get(sent_key, {})
        if not topic_map:
            return DEFAULT_TOPIC

        text_lower = str(text).lower().strip()
        best_topic = DEFAULT_TOPIC
        best_count = 0

        # Iterasi berurutan → tie-break: topik pertama di list menang
        for topic_name, keywords in topic_map.items():
            match_count = _count_keyword_matches(text_lower, keywords)
            if match_count > best_count:
                best_count = match_count
                best_topic = topic_name

        return best_topic if best_count > 0 else DEFAULT_TOPIC

    except Exception:
        return DEFAULT_TOPIC


def apply_topics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Terapkan klasifikasi topik ke seluruh baris DataFrame.

    Args:
        df: DataFrame dengan kolom content_clean dan predicted_sentiment.

    Returns:
        DataFrame dengan kolom baru 'topic'.
    """
    try:
        if df is None or df.empty:
            return df.copy() if df is not None else pd.DataFrame()

        result = df.copy()
        required = ("content_clean", "predicted_sentiment")
        missing = [col for col in required if col not in result.columns]
        if missing:
            raise ValueError(f"Kolom wajib tidak ditemukan: {', '.join(missing)}")

        result["topic"] = result.apply(
            lambda row: classify_topic(
                row.get("content_clean", ""),
                row.get("predicted_sentiment", ""),
            ),
            axis=1,
        )
        return result

    except Exception as exc:
        raise RuntimeError(f"Gagal menerapkan klasifikasi topik: {exc}") from exc


def get_top_topics(
    df: pd.DataFrame,
    sentimen: str,
    top_n: int = 5,
) -> pd.DataFrame:
    """
    Ambil topik teratas berdasarkan jumlah komentar untuk satu sentimen.

    Args:
        df: DataFrame dengan kolom topic, predicted_sentiment, content/content_clean.
        sentimen: Sentimen yang difilter (positive/neutral/negative).
        top_n: Jumlah topik teratas yang dikembalikan.

    Returns:
        DataFrame kolom: topik, jumlah_komentar, pct, contoh_komentar.
    """
    try:
        empty_cols = ["topik", "jumlah_komentar", "pct", "contoh_komentar"]
        if df is None or df.empty:
            return pd.DataFrame(columns=empty_cols)

        work = df.copy()
        if "topic" not in work.columns:
            work = apply_topics(work)

        sent_key = _normalize_sentiment(sentimen)
        work = work[
            work["predicted_sentiment"]
            .astype(str)
            .str.lower()
            .str.strip()
            .map(lambda x: SENTIMENT_KEYS.get(x, x)) == sent_key
        ]

        if work.empty:
            return pd.DataFrame(columns=empty_cols)

        content_col = "content" if "content" in work.columns else "content_clean"
        total = len(work)

        rows = []
        grouped = work.groupby("topic", sort=False)
        for topic_name, group in grouped:
            count = len(group)
            pct = round(count / total * 100, 1) if total else 0.0
            sample = ""
            if content_col in group.columns and not group.empty:
                sample = str(group[content_col].iloc[0])
            rows.append({
                "topik": topic_name,
                "jumlah_komentar": count,
                "pct": pct,
                "contoh_komentar": sample,
            })

        result = (
            pd.DataFrame(rows)
            .sort_values("jumlah_komentar", ascending=False)
            .head(top_n)
            .reset_index(drop=True)
        )
        return result

    except Exception as exc:
        raise RuntimeError(f"Gagal mengambil topik teratas: {exc}") from exc


def get_dominant_keywords(
    df: pd.DataFrame,
    topic: str,
    sentimen: str,
) -> list[str]:
    """
    Kembalikan kata kunci dominan yang benar-benar muncul di komentar suatu topik.

    Args:
        df: DataFrame dengan kolom topic, predicted_sentiment, content_clean.
        topic: Nama topik yang ingin dianalisis.
        sentimen: Sentimen terkait topik tersebut.

    Returns:
        Daftar maksimal 5 kata kunci dominan (urut frekuensi tertinggi).
    """
    try:
        if df is None or df.empty or not topic:
            return []

        work = df.copy()
        if "topic" not in work.columns:
            work = apply_topics(work)

        sent_key = _normalize_sentiment(sentimen)
        subset = work[
            (work["topic"] == topic)
            & (
                work["predicted_sentiment"]
                .astype(str)
                .str.lower()
                .str.strip()
                .map(lambda x: SENTIMENT_KEYS.get(x, x)) == sent_key
            )
        ]

        if subset.empty or "content_clean" not in subset.columns:
            return []

        corpus = " ".join(subset["content_clean"].astype(str).tolist()).lower()
        keywords = TOPICS.get(sent_key, {}).get(topic, [])
        if not keywords:
            return []

        freq: Counter[str] = Counter()
        for kw in keywords:
            kw_lower = str(kw).lower().strip()
            if not kw_lower:
                continue
            if len(kw_lower) <= 3:
                pattern = rf"(?<!\w){re.escape(kw_lower)}(?!\w)"
                matches = len(re.findall(pattern, corpus))
            else:
                matches = corpus.count(kw_lower)
            if matches > 0:
                freq[kw_lower] = matches

        return [word for word, _ in freq.most_common(5)]

    except Exception:
        return []


if __name__ == "__main__":
    # --- Contoh penggunaan modul ---
    import sys
    from pathlib import Path

    # Agar import utils.* berfungsi saat dijalankan langsung
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from utils.dummy_data import get_dummy_sentiment_data
    from utils.preprocessor import clean_text

    print("=" * 60)
    print("DEMO: utils/topic_classifier.py")
    print("=" * 60)

    # Muat data dummy dan bersihkan teks
    df_demo = get_dummy_sentiment_data("IndiHome")
    df_demo["content_clean"] = df_demo["content"].apply(clean_text)

    # Klasifikasi topik per baris
    df_demo = apply_topics(df_demo)
    print(f"\nTotal baris: {len(df_demo)}")
    print(f"Kolom topic ditambahkan: {'topic' in df_demo.columns}")
    print("\nContoh 5 baris pertama:")
    print(df_demo[["content", "predicted_sentiment", "topic"]].head().to_string(index=False))

    # Topik teratas per sentimen
    for sent in ("positive", "neutral", "negative"):
        top = get_top_topics(df_demo, sent, top_n=3)
        print(f"\n--- Top 3 Topik ({sent}) ---")
        if top.empty:
            print("  (tidak ada data)")
        else:
            print(top.to_string(index=False))

    # Kata kunci dominan untuk satu topik
    if not df_demo.empty:
        sample_topic = df_demo["topic"].iloc[0]
        sample_sent = df_demo["predicted_sentiment"].iloc[0]
        kws = get_dominant_keywords(df_demo, sample_topic, sample_sent)
        print(f"\nKata kunci dominan topik '{sample_topic}':")
        print(f"  {kws if kws else '(tidak ada match)'}")

    # Uji classify_topic langsung
    contoh = classify_topic(
        "wifi indihome lemot banget sering ngelag",
        "negative",
    )
    print(f"\nclassify_topic contoh: '{contoh}'")
    print("\nDemo selesai.")
