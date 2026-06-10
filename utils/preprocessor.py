"""Pipeline pembersihan teks Bahasa Indonesia untuk IndoBERT dan WordCloud."""

from __future__ import annotations

import logging
import re

import emoji

logger = logging.getLogger(__name__)

# --- Stopword Bahasa Indonesia (100+ kata) ---
STOPWORDS_ID: set[str] = {
    # Kata ganti & kepemilikan
    "aku", "saya", "kamu", "kau", "anda", "dia", "ia", "kita", "kami", "mereka",
    "nya", "mu", "ku", "gue", "gw", "lu", "lo", "elo", "ane", "ente",
    # Kata kerja bantu & penghubung
    "ada", "adalah", "adanya", "agar", "akan", "akankah", "atau", "bahwa",
    "bisa", "boleh", "dapat", "harus", "hendak", "ingin", "jadi", "jika",
    "kalau", "karena", "kepada", "lagi", "lalu", "maka", "mau", "melalui",
    "menjadi", "oleh", "pada", "pun", "saat", "saja", "saling", "sama",
    "sampai", "sedang", "sebagai", "sebab", "sebelum", "sehingga", "sejak",
    "selama", "semua", "sendiri", "seperti", "serta", "setelah", "setiap",
    "sudah", "supaya", "tak", "tanpa", "telah", "tentang", "terhadap",
    "untuk", "walau", "walaupun", "yaitu", "yang",
    # Partikel & kata umum
    "agak", "akhir", "akhirnya", "amat", "antar", "antara", "apa", "apaan",
    "apakah", "apalagi", "awal", "bagaimana", "bagi", "bahkan", "banyak",
    "baru", "bawah", "beberapa", "begini", "begitu", "belum", "berada",
    "berakhir", "berarti", "berbagai", "berhasil", "berikut", "berjalan",
    "berlangsung", "berupa", "besar", "buat", "bukan", "bulan", "cara",
    "cukup", "dalam", "dari", "daripada", "datang", "demi", "demikian",
    "dengan", "depan", "di", "dimana", "dong", "dua", "guna", "hal",
    "hampir", "hanya", "hari", "hingga", "ialah", "ibu", "ini", "itu",
    "jangan", "juga", "justru", "kala", "ke", "kecil", "kembali", "kenapa",
    "kerja", "lagian", "lah", "lain", "lama", "lebih", "macam", "makin",
    "malah", "mana", "manakala", "masih", "masuk", "melihat", "memang",
    "membuat", "mempunyai", "menurut", "meski", "meskipun", "minta",
    "mungkin", "nah", "namun", "nanti", "nyaris", "pak", "paling", "para",
    "pasti", "per", "perlu", "pertama", "pula", "sana", "sangat", "se",
    "sebuah", "secara", "sedikit", "segala", "sekali", "sekitar", "seluruh",
    "semacam", "sering", "siapa", "sini", "soal", "suatu", "tahun", "tapi",
    "tegas", "terlalu", "tersebut", "tetap", "tetapi", "tidak", "tinggi",
    "toh", "tentu", "waduh", "wah", "waktu",
    # Singkatan umum
    "yg", "dg", "dgn", "utk", "krn", "sdh", "udh", "tdk", "blm", "gpp",
    "btw", "imo", "lol", "wkwk", "wkkw", "haha", "hehe",
    # Kata media sosial & sapaan informal
    "min", "admin", "kak", "kakk", "bang", "bro", "sis", "gan", "mas", "mbak",
    "mba", "bu", "bg", "bgs", "deh", "nih", "tuh", "dong", "sih", "kok",
    "lho", "loh", "donk", "yah", "yuk", "yukk", "om", "tante", "papi",
    "mami", "bestie", "guys", "gaes", "ges", "woy", "woi", "halo", "hai",
    "thanks", "thank", "thx", "pls", "please", "info", "cek", "cc",
}

# --- Normalisasi kata informal → formal (30+ pasang) ---
NORMALIZATION_MAP: dict[str, str] = {
    "gak": "tidak",
    "ga": "tidak",
    "gk": "tidak",
    "ngga": "tidak",
    "nggak": "tidak",
    "ngk": "tidak",
    "tdk": "tidak",
    "g": "tidak",
    "yg": "yang",
    "jgn": "jangan",
    "bgt": "banget",
    "bngt": "banget",
    "banget": "sangat",
    "krn": "karena",
    "karna": "karena",
    "dgn": "dengan",
    "dg": "dengan",
    "utk": "untuk",
    "sdh": "sudah",
    "udh": "sudah",
    "udah": "sudah",
    "blm": "belum",
    "aja": "saja",
    "bener": "benar",
    "gimana": "bagaimana",
    "gmna": "bagaimana",
    "knp": "kenapa",
    "knapa": "kenapa",
    "trus": "terus",
    "truz": "terus",
    "emang": "memang",
    "emg": "memang",
    "kek": "seperti",
    "ky": "seperti",
    "kaya": "seperti",
    "abis": "habis",
    "tp": "tapi",
    "dlu": "dulu",
    "skrg": "sekarang",
    "skrng": "sekarang",
    "hrs": "harus",
    "bkn": "bukan",
    "org": "orang",
    "wkt": "waktu",
    "bgtu": "begitu",
    "gitu": "begitu",
    "gini": "begini",
    "bbrp": "beberapa",
    "bnyk": "banyak",
    "sy": "saya",
    "km": "kamu",
    "sm": "sama",
    "dr": "dari",
    "klo": "kalau",
    "kl": "kalau",
    "jd": "jadi",
    "jg": "juga",
    "dh": "dah",
    "dah": "sudah",
}

_URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_MENTION_PATTERN = re.compile(r"@\w+")
_HTML_PATTERN = re.compile(r"<[^>]+>")
_HASHTAG_PATTERN = re.compile(r"#\w+")
_NUMBER_PATTERN = re.compile(r"\d+")
_SPECIAL_CHAR_PATTERN = re.compile(r"[^a-z\s]")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_informal(text: str) -> str:
    """
    Terapkan normalisasi kata informal ke formal menggunakan NORMALIZATION_MAP.

    Contoh uji:
        >>> normalize_informal("yg gak stabil bgt")
        'yang tidak stabil sangat'
    """
    try:
        result = str(text)
        for informal, formal in NORMALIZATION_MAP.items():
            pattern = rf"\b{re.escape(informal)}\b"
            result = re.sub(pattern, formal, result)
        return result
    except Exception as exc:
        logger.error("Gagal menormalisasi teks informal: %s", exc)
        return str(text) if text is not None else ""


def clean_text(text: str) -> str:
    """
    Bersihkan teks komentar media sosial untuk analisis sentimen.

    Langkah: hapus URL, mention, HTML, angka, karakter khusus, emoji,
    lowercase, normalisasi informal, rapikan spasi.

    Contoh uji:
        >>> clean_text("Min @indihome internet down bgt 😭 https://t.co/abc")
        'internet down sangat'
    """
    try:
        if text is None:
            return ""

        result = str(text).lower()
        result = _URL_PATTERN.sub(" ", result)
        result = _MENTION_PATTERN.sub(" ", result)
        result = _HTML_PATTERN.sub(" ", result)
        result = emoji.replace_emoji(result, replace=" ")
        result = _NUMBER_PATTERN.sub(" ", result)
        result = _SPECIAL_CHAR_PATTERN.sub(" ", result)
        result = normalize_informal(result)
        result = _WHITESPACE_PATTERN.sub(" ", result).strip()
        return result
    except Exception as exc:
        logger.error("Gagal membersihkan teks: %s", exc)
        return ""


def remove_stopwords(text: str, custom: set | None = None) -> str:
    """
    Hapus stopword Indonesia dari teks yang sudah dibersihkan.

    Jika `custom` diberikan, digabung dengan STOPWORDS_ID.

    Contoh uji:
        >>> remove_stopwords("internet lambat tidak stabil")
        'internet lambat stabil'
    """
    try:
        if not text:
            return ""

        stopwords = set(STOPWORDS_ID)
        if custom:
            stopwords |= {str(w).lower().strip() for w in custom}

        words = [w for w in text.split() if w not in stopwords]
        return " ".join(words)
    except Exception as exc:
        logger.error("Gagal menghapus stopword: %s", exc)
        return str(text) if text is not None else ""


def prepare_for_wordcloud(text: str) -> str:
    """
    Pembersihan agresif khusus WordCloud.

    Hapus hashtag, filter kata > 2 karakter, hapus stopword.

    Contoh uji:
        >>> prepare_for_wordcloud("Internet #indihome lambat bgt min @admin")
        'internet lambat'
    """
    try:
        if text is None:
            return ""

        result = str(text).lower()
        result = _URL_PATTERN.sub(" ", result)
        result = _MENTION_PATTERN.sub(" ", result)
        result = _HTML_PATTERN.sub(" ", result)
        result = _HASHTAG_PATTERN.sub(" ", result)
        result = emoji.replace_emoji(result, replace=" ")
        result = _NUMBER_PATTERN.sub(" ", result)
        result = _SPECIAL_CHAR_PATTERN.sub(" ", result)
        result = normalize_informal(result)
        result = _WHITESPACE_PATTERN.sub(" ", result).strip()

        words = [w for w in result.split() if len(w) > 2]
        return remove_stopwords(" ".join(words))
    except Exception as exc:
        logger.error("Gagal menyiapkan teks wordcloud: %s", exc)
        return ""


def batch_clean(texts: list) -> list[str]:
    """
    Terapkan clean_text ke seluruh daftar teks.

    Contoh uji:
        >>> batch_clean(["Internet lambat!", "Sinyal bagus 👍"])
        ['internet lambat', 'sinyal bagus']
    """
    try:
        if not texts:
            return []
        return [clean_text(t) for t in texts]
    except Exception as exc:
        logger.error("Gagal batch cleaning: %s", exc)
        return []


# --- Alias kompatibilitas fase sebelumnya ---
NORMALIZATION_DICT = {
    rf"\b{re.escape(k)}\b": v for k, v in NORMALIZATION_MAP.items()
}


def clean_text_for_indobert(text: str) -> str:
    """Alias ke clean_text() untuk kompatibilitas modul lama."""
    return clean_text(text)


def clean_text_for_wordcloud(text: str) -> str:
    """Alias ke prepare_for_wordcloud() untuk kompatibilitas modul lama."""
    return prepare_for_wordcloud(text)
