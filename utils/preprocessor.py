# utils/preprocessor.py
"""Pipeline pembersihan teks Bahasa Indonesia untuk IndoBERT dan WordCloud."""

from __future__ import annotations

import logging
import re

import emoji
import pandas as pd

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
    # Kata domain IndiBiz untuk WordCloud (sesuai Cell [12]/tahap lanjutan)
    "indibiz", "indibizid", "telkom", "internet",
}

# Stopword tambahan untuk WordCloud dan analisis topik pascasidang.
# Semua nilai disimpan lowercase agar pencocokan bersifat case-insensitive.
SERVICE_STOPWORDS = {
    "indihome", "telkomsel", "indibiz", "telkom", "tsel",
    "indihome_id", "telkomsel_id", "indibiz_id", "indihomecare",
    "myindihome", "mytelkomsel",
}

CONNECTOR_STOPWORDS = {
    "yang", "dan", "di", "ke", "dari", "ini", "itu", "dengan", "untuk",
    "pada", "adalah", "ada", "juga", "atau", "tapi", "tetapi", "karena",
    "jadi", "jika", "kalau", "sudah", "belum", "akan", "bisa", "dapat",
    "harus", "mau", "ingin", "punya", "lagi", "masih", "baru", "pun",
    "aja", "sih", "dong", "loh", "deh", "ya", "yah",
}

SOCIAL_MEDIA_STOPWORDS = {
    "min", "mimin", "admin", "kak", "bang", "mas", "mbak", "bro", "sis",
    "gan", "sob", "guys", "halo", "hai", "hi", "hello", "nih", "tuh",
    "gimana", "kenapa", "knp", "gmn",
}

NONSTANDARD_STOPWORDS = {
    "yg", "dg", "dgn", "utk", "lg", "jg", "tp", "dr", "pd", "krn",
    "gak", "ga", "ngga", "nggak", "banget", "bgt", "sangat", "sekali",
    "saya", "aku", "kamu", "anda", "dia", "mereka", "kami", "kita",
}

WORDCLOUD_FOCUS_WORDS = {
    # Positif
    "bagus", "baik", "murah", "cepat", "puas", "mantap", "oke", "lancar",
    "stabil",
    # Negatif
    "lambat", "gangguan", "mahal", "jelek", "lemot", "down", "rusak",
    "lama", "parah",
    # Netral dan istilah domain
    "paket", "kuota", "sinyal", "jaringan", "layanan", "internet", "wifi",
}

STOPWORDS_ID.update(
    SERVICE_STOPWORDS
    | CONNECTOR_STOPWORDS
    | SOCIAL_MEDIA_STOPWORDS
    | NONSTANDARD_STOPWORDS
)
# Kata fokus harus tetap tersedia untuk WordCloud, tabel frekuensi, dan LDA.
STOPWORDS_ID.difference_update(WORDCLOUD_FOCUS_WORDS)

# --- Normalisasi kata informal → formal ---
# Daftar wajib diselaraskan dengan preprocessing Cell [12] IndiBiz.
NORMALIZATION_MAP: dict[str, str] = {
    "gak": "tidak",
    "ga": "tidak",
    "gk": "tidak",
    "ngga": "tidak",
    "nggak": "tidak",
    "enggak": "tidak",
    "ngk": "tidak",
    "ng": "tidak",
    "tdk": "tidak",
    "g": "tidak",
    "yg": "yang",
    "jgn": "jangan",
    "bgt": "banget",
    "bangt": "banget",
    "bngt": "banget",
    "krn": "karena",
    "karna": "karena",
    "dg": "dengan",
    "dgn": "dengan",
    "utk": "untuk",
    "unt": "untuk",
    "spy": "supaya",
    "sdh": "sudah",
    "ud": "sudah",
    "udh": "sudah",
    "udah": "sudah",
    "sya": "saya",
    "sy": "saya",
    "aq": "aku",
    "gw": "aku",
    "gue": "aku",
    "lo": "kamu",
    "lu": "kamu",
    "km": "kamu",
    "tp": "tapi",
    "gmn": "bagaimana",
    "gimana": "bagaimana",
    "gmna": "bagaimana",
    "knp": "kenapa",
    "knapa": "kenapa",
    "msh": "masih",
    "blm": "belum",
    # Tambahan kompatibilitas preprocessing dashboard yang sudah ada.
    "aja": "saja",
    "bener": "benar",
    "trus": "terus",
    "truz": "terus",
    "emang": "memang",
    "emg": "memang",
    "kek": "seperti",
    "ky": "seperti",
    "kaya": "seperti",
    "abis": "habis",
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
    "sm": "sama",
    "dr": "dari",
    "klo": "kalau",
    "kl": "kalau",
    "jd": "jadi",
    "jg": "juga",
    "dh": "sudah",
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
        'yang tidak stabil banget'
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


def _is_missing_value(value: object) -> bool:
    """Periksa nilai kosong/NaN tanpa membuat error pada tipe data aneh."""
    try:
        missing = pd.isna(value)
        # Nilai skalar (bool/numpy.bool_) dapat langsung dikonversi.
        # Array/Series tidak dianggap satu nilai kosong.
        if hasattr(missing, "__len__"):
            return False
        return bool(missing)
    except Exception:
        return value is None


def _show_streamlit_error(message: str) -> None:
    """Tampilkan st.error bila Streamlit tersedia, lalu tetap tulis ke log."""
    logger.error(message)
    try:
        import streamlit as st

        st.error(message)
    except Exception:
        # Verifikasi terminal tetap dapat berjalan meskipun Streamlit tidak aktif.
        pass


def clean_text(text: str) -> str:
    """
    Bersihkan teks komentar media sosial untuk IndoBERT.

    Urutan pembersihan: URL, mention, HTML, emoji, karakter khusus, angka,
    lowercase, normalisasi kata informal, kemudian spasi berlebih.
    Stopword tidak dihapus karena konteks kalimat harus tetap tersedia untuk
    model transformer IndoBERT.
    """
    try:
        if _is_missing_value(text):
            return ""

        result = str(text)
        result = _URL_PATTERN.sub(" ", result)
        result = _MENTION_PATTERN.sub(" ", result)
        result = _HTML_PATTERN.sub(" ", result)
        try:
            result = emoji.replace_emoji(result, replace=" ")
        except Exception:
            result = result.encode("ascii", "ignore").decode("ascii")
        result = _NUMBER_PATTERN.sub(" ", result)
        result = result.lower()
        result = _SPECIAL_CHAR_PATTERN.sub(" ", result)
        result = normalize_informal(result)
        result = _WHITESPACE_PATTERN.sub(" ", result).strip()
        return result
    except Exception as exc:
        _show_streamlit_error(f"Gagal membersihkan teks untuk IndoBERT: {exc}")
        return ""

def remove_stopwords(text: str, custom: set | None = None) -> str:
    """
    Hapus stopword Indonesia dari teks yang sudah dibersihkan.

    Jika `custom` diberikan, digabung dengan STOPWORDS_ID.

    Contoh uji:
        >>> remove_stopwords("internet lambat tidak stabil")
        'lambat stabil'
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


def clean_for_wordcloud(
    text: str,
    custom_stopwords: set[str] | None = None,
) -> str:
    """Bersihkan teks untuk WordCloud, frekuensi kata, dan analisis topik.

    Fungsi ini menghapus URL, mention, HTML, angka, emoji, nama layanan, kata
    sambung, sapaan media sosial, dan singkatan tidak baku. Kata fokus sentimen
    serta istilah domain seperti ``sinyal``, ``jaringan``, dan ``internet`` tetap
    dipertahankan.
    """
    try:
        if _is_missing_value(text):
            return ""

        result = str(text).lower()
        result = _URL_PATTERN.sub(" ", result)
        result = _MENTION_PATTERN.sub(" ", result)
        result = _HTML_PATTERN.sub(" ", result)
        # Simbol hashtag dihapus, tetapi kata setelahnya tetap dipakai.
        result = result.replace("#", " ")
        try:
            result = emoji.replace_emoji(result, replace=" ")
        except Exception:
            result = result.encode("ascii", "ignore").decode("ascii")
        result = _NUMBER_PATTERN.sub(" ", result)
        result = _SPECIAL_CHAR_PATTERN.sub(" ", result)
        result = _WHITESPACE_PATTERN.sub(" ", result).strip()

        stopwords = set(STOPWORDS_ID)
        if custom_stopwords:
            stopwords.update(
                str(word).lower().strip()
                for word in custom_stopwords
                if str(word).strip()
            )

        cleaned_words: list[str] = []
        for raw_word in result.split():
            normalized_word = NORMALIZATION_MAP.get(raw_word, raw_word)
            if len(normalized_word) <= 2:
                continue
            if normalized_word in stopwords:
                continue
            cleaned_words.append(normalized_word)

        return " ".join(cleaned_words)
    except Exception as exc:
        _show_streamlit_error(f"Gagal membersihkan teks WordCloud: {exc}")
        return ""


def prepare_for_wordcloud(text: str) -> str:
    """Pertahankan API lama dengan meneruskan proses ke clean_for_wordcloud."""
    try:
        return clean_for_wordcloud(text)
    except Exception as exc:
        _show_streamlit_error(f"Gagal menyiapkan teks WordCloud: {exc}")
        return ""


def prepare_indibiz_indobert_dataframe(df_nov_indibiz: pd.DataFrame) -> pd.DataFrame:
    """Adaptasi Cell [12] IndiBiz pada sisi dashboard Streamlit.

    Fungsi ini tidak mengubah DataFrame asli. Hasil akhirnya memakai nama kolom
    kanonik dashboard dan menambahkan ``content_clean`` untuk tahap IndoBERT.
    """
    try:
        if not isinstance(df_nov_indibiz, pd.DataFrame):
            raise TypeError("Sumber data IndiBiz harus berupa pandas DataFrame.")
        if df_nov_indibiz.empty:
            return pd.DataFrame(
                columns=[
                    "date_created",
                    "platform",
                    "username",
                    "followers",
                    "content",
                    "content_clean",
                ]
            )

        df_bert = df_nov_indibiz.copy(deep=True)

        # Bersihkan tanda kutip satu pada awal/isi nilai string yang umum muncul
        # akibat ekspor CSV/Excel dari sumber penelitian.
        string_columns = [
            "specific_resource_type",
            "from_username",
            "content",
            "date_created",
        ]
        for column in string_columns:
            if column in df_bert.columns:
                df_bert[column] = (
                    df_bert[column]
                    .astype("string")
                    .str.replace("'", "", regex=False)
                    .str.strip()
                )

        required_source_columns = {
            "date_created",
            "specific_resource_type",
            "from_username",
            "followers",
            "content",
        }
        missing_columns = sorted(required_source_columns.difference(df_bert.columns))
        if missing_columns:
            raise ValueError(
                "Kolom wajib preprocessing IndiBiz belum lengkap: "
                + ", ".join(missing_columns)
            )

        # Hanya tiga platform penelitian yang dipertahankan.
        allowed_platforms = {"twitter", "instagram", "tiktok"}
        platform_normalized = (
            df_bert["specific_resource_type"]
            .astype("string")
            .str.lower()
            .str.strip()
            .replace(
                {
                    "x": "twitter",
                    "twitter/x": "twitter",
                    "twitter (x)": "twitter",
                    "ig": "instagram",
                }
            )
        )
        df_bert["specific_resource_type"] = platform_normalized
        df_bert = df_bert[
            df_bert["specific_resource_type"].isin(allowed_platforms)
        ].copy()

        # Sentimen bawaan tidak dipakai karena akan diprediksi ulang oleh IndoBERT.
        df_bert.drop(
            columns=["final_sentiment", "label", "emotion"],
            errors="ignore",
            inplace=True,
        )

        selected_columns = [
            "date_created",
            "specific_resource_type",
            "from_username",
            "followers",
            "content",
        ]
        df_bert = df_bert[selected_columns].copy()
        df_bert.rename(
            columns={
                "from_username": "username",
                "specific_resource_type": "platform",
            },
            inplace=True,
        )

        # Nilai followers yang tidak dapat dibaca dianggap 0 agar tidak crash.
        df_bert["followers"] = (
            pd.to_numeric(
                df_bert["followers"]
                .astype("string")
                .str.replace("'", "", regex=False)
                .str.replace(",", "", regex=False)
                .str.strip(),
                errors="coerce",
            )
            .fillna(0)
            .clip(lower=0, upper=2_147_483_647)
            .astype("int64")
        )

        # Buang isi kosong, teks "nan" hasil konversi, dan duplikat konten.
        df_bert["content"] = (
            df_bert["content"].astype("string").fillna("").str.strip()
        )
        df_bert = df_bert[
            df_bert["content"].ne("")
            & df_bert["content"].str.lower().ne("nan")
            & df_bert["content"].str.lower().ne("none")
        ].copy()
        df_bert.drop_duplicates(subset=["content"], keep="first", inplace=True)

        # Pembersihan teks untuk model IndoBERT; tidak melakukan stemming dan
        # tidak menghapus stopword agar konteks kalimat tetap dipertahankan.
        df_bert["content_clean"] = df_bert["content"].map(clean_text)
        df_bert = df_bert[df_bert["content_clean"].str.strip().ne("")].copy()

        return df_bert.reset_index(drop=True)
    except Exception as exc:
        _show_streamlit_error(f"Gagal melakukan preprocessing teks IndiBiz: {exc}")
        return pd.DataFrame()


def get_indibiz_preprocessing_summary(df_bert: pd.DataFrame) -> dict[str, object]:
    """Buat ringkasan jumlah data, distribusi platform, dan tiga contoh teks."""
    try:
        if not isinstance(df_bert, pd.DataFrame) or df_bert.empty:
            return {"total": 0, "platform": {}, "examples": []}

        platform_counts = (
            df_bert.get("platform", pd.Series(dtype="string"))
            .astype("string")
            .str.lower()
            .value_counts()
            .to_dict()
        )
        examples: list[dict[str, str]] = []
        for _, row in df_bert.head(3).iterrows():
            examples.append(
                {
                    "before": str(row.get("content", "")),
                    "after": str(row.get("content_clean", "")),
                }
            )
        return {
            "total": int(len(df_bert)),
            "platform": {str(key): int(value) for key, value in platform_counts.items()},
            "examples": examples,
        }
    except Exception as exc:
        _show_streamlit_error(f"Gagal membuat ringkasan preprocessing IndiBiz: {exc}")
        return {"total": 0, "platform": {}, "examples": []}



def clean_telkomsel_text(text: str) -> str:
    """Bersihkan teks Telkomsel sesuai kontrak preprocessing Tahap 4 Fase 2.

    Hashtag dihapus sebagai satu token penuh sebelum fungsi ``clean_text``
    dijalankan. Perilaku ``clean_text`` lama tidak diubah agar pipeline
    IndiHome dan IndiBiz tetap kompatibel.
    """
    try:
        if _is_missing_value(text):
            return ""
        without_hashtag = _HASHTAG_PATTERN.sub(" ", str(text))
        return clean_text(without_hashtag)
    except Exception as exc:
        _show_streamlit_error(f"Gagal membersihkan teks Telkomsel: {exc}")
        return ""


def _find_telkomsel_source_columns(columns: list[str]) -> dict[str, str]:
    """Petakan variasi nama kolom mentah ke kontrak Telkomsel."""
    try:
        from utils.telkomsel_config import RAW_COLUMN_ALIASES

        lookup = {str(column).strip().lower(): str(column) for column in columns}
        selected: dict[str, str] = {}
        for canonical, aliases in RAW_COLUMN_ALIASES.items():
            for alias in aliases:
                source = lookup.get(str(alias).lower())
                if source is not None:
                    selected[canonical] = source
                    break
        return selected
    except Exception as exc:
        _show_streamlit_error(f"Gagal memetakan kolom mentah Telkomsel: {exc}")
        return {}


def prepare_telkomsel_sentiment_dataframe(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Ubah data mentah Telkomsel menjadi delapan kolom preprocessing kanonik.

    Fungsi bekerja pada salinan DataFrame, memfilter kata ``telkomsel`` atau
    ``telkom`` pada teks asli, menormalkan platform dan tanggal, lalu membentuk
    ``cleaned_text``. Kolom label, score, dan topic sengaja dikosongkan karena
    akan diisi pada tahap IndoBERT dan topic modeling berikutnya.
    """
    try:
        from utils.telkomsel_config import (
            ALLOWED_PLATFORMS,
            OUTPUT_COLUMNS,
            PLATFORM_ALIASES,
        )

        if not isinstance(df_raw, pd.DataFrame):
            raise TypeError("Sumber data Telkomsel harus berupa pandas DataFrame.")
        if df_raw.empty:
            return pd.DataFrame(columns=list(OUTPUT_COLUMNS))

        source_columns = _find_telkomsel_source_columns(list(df_raw.columns))
        required = {"text", "platform", "date", "username"}
        missing = sorted(required.difference(source_columns))
        if missing:
            raise ValueError(
                "Kolom wajib data mentah Telkomsel belum lengkap: "
                + ", ".join(missing)
            )

        selected = [source_columns[name] for name in ("text", "platform", "date", "username")]
        work = df_raw[selected].copy(deep=True)
        work.rename(
            columns={
                source_columns["text"]: "text",
                source_columns["platform"]: "platform",
                source_columns["date"]: "date",
                source_columns["username"]: "username",
            },
            inplace=True,
        )

        for column in ("text", "platform", "date", "username"):
            work[column] = (
                work[column]
                .astype("string")
                .fillna("")
                .str.strip()
                .str.lstrip("'")
            )

        work = work[
            work["text"].ne("")
            & work["text"].str.lower().ne("nan")
            & work["text"].str.lower().ne("none")
        ].copy()

        # Filter wajib dilakukan pada teks asli sebelum pembersihan.
        keyword_mask = work["text"].str.contains(
            r"telkomsel|telkom",
            case=False,
            regex=True,
            na=False,
        )
        work = work[keyword_mask].copy()

        work["platform"] = (
            work["platform"]
            .str.lower()
            .str.strip()
            .replace(PLATFORM_ALIASES)
        )
        work = work[work["platform"].isin(ALLOWED_PLATFORMS)].copy()

        date_text = work["date"].str.replace(
            r"(\d{1,2})\.(\d{2})\.(\d{2})$",
            r"\1:\2:\3",
            regex=True,
        )
        parsed_date = pd.to_datetime(
            date_text,
            errors="coerce",
            dayfirst=True,
            format="mixed",
        )
        work["date"] = parsed_date
        work = work[work["date"].notna()].copy()
        work["date"] = work["date"].dt.strftime("%Y-%m-%d")

        work["cleaned_text"] = work["text"].map(clean_telkomsel_text)
        work = work[work["cleaned_text"].astype("string").str.strip().ne("")].copy()

        work["label"] = ""
        work["score"] = ""
        work["topic"] = ""

        result = work[list(OUTPUT_COLUMNS)].reset_index(drop=True)
        return result
    except Exception as exc:
        _show_streamlit_error(f"Gagal melakukan preprocessing data Telkomsel: {exc}")
        try:
            from utils.telkomsel_config import OUTPUT_COLUMNS

            return pd.DataFrame(columns=list(OUTPUT_COLUMNS))
        except Exception:
            return pd.DataFrame()


def get_telkomsel_preprocessing_summary(
    dataframe: pd.DataFrame,
    total_before_filter: int | None = None,
) -> dict[str, object]:
    """Ringkas hasil preprocessing Telkomsel untuk verifier dan UI status."""
    try:
        if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
            return {
                "total_before_filter": int(total_before_filter or 0),
                "total_after_filter": 0,
                "removed_rows": int(total_before_filter or 0),
                "platform": {},
                "examples": [],
            }

        after = int(len(dataframe))
        before = int(total_before_filter) if total_before_filter is not None else after
        platform_counts = (
            dataframe["platform"]
            .astype("string")
            .str.lower()
            .value_counts()
            .to_dict()
        )
        examples: list[dict[str, str]] = []
        for _, row in dataframe.head(3).iterrows():
            examples.append(
                {
                    "before": str(row.get("text", "")),
                    "after": str(row.get("cleaned_text", "")),
                }
            )
        return {
            "total_before_filter": before,
            "total_after_filter": after,
            "removed_rows": max(0, before - after),
            "platform": {str(key): int(value) for key, value in platform_counts.items()},
            "examples": examples,
        }
    except Exception as exc:
        _show_streamlit_error(f"Gagal membuat ringkasan preprocessing Telkomsel: {exc}")
        return {
            "total_before_filter": int(total_before_filter or 0),
            "total_after_filter": 0,
            "removed_rows": int(total_before_filter or 0),
            "platform": {},
            "examples": [],
        }

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
