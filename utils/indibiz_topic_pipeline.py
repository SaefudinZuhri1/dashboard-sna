"""Pipeline Analisis Topik IndiBiz untuk dashboard Streamlit.

Modul ini membentuk tepat lima topik utama dari seluruh komentar IndiBiz.
LDA tidak dipisahkan per sentimen. Sentimen hanya dipakai untuk merangkum
komposisi komentar di dalam masing-masing topik.

Notebook Google Colab dan data asli tidak ditulis atau diubah oleh modul ini.
"""

from __future__ import annotations

from collections import Counter
import re
from typing import Any

import pandas as pd
import streamlit as st
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer

from utils.preprocessor import STOPWORDS_ID
from utils.topic_classifier import (
    DEFAULT_TOPIC,
    SENTIMENT_LABELS_ID,
    classify_topics_fast,
    get_topic_keywords,
)

N_TOPICS = 5
N_WORDS = 8
MIN_DOCS = 10
RANDOM_STATE = 42

SENTIMENT_ORDER = ("positive", "neutral", "negative")
SENTIMENT_TIE_PRIORITY = {"negative": 2, "positive": 1, "neutral": 0}

INDIBIZ_BRAND_WORDS = {"indibiz", "indibizid", "indibiz_id", "telkom"}
INDIBIZ_DOMAIN_STOPWORDS = {"biznet", "layanan", "bisnis"}
STOPWORDS_INDIBIZ = set(STOPWORDS_ID) | INDIBIZ_BRAND_WORDS | INDIBIZ_DOMAIN_STOPWORDS

# Nama tema dibuat khusus untuk konteks percakapan IndiBiz. LDA tetap menjadi
# metode pembentuk kelompok; kamus ini hanya memberi nama manusiawi berdasarkan
# kata yang paling dominan di setiap kelompok.
INDIBIZ_SEMANTIC_THEMES: dict[str, tuple[str, ...]] = {
    "Harga, Tagihan & Paket": (
        "harga", "mahal", "murah", "tagihan", "biaya", "tarif", "bayar",
        "pembayaran", "invoice", "paket", "promo", "diskon", "cashback",
        "voucher", "bonus", "kuota", "berlangganan",
    ),
    "Pelayanan & Respons Admin": (
        "pelayanan", "admin", "cs", "customer service", "respon", "respons",
        "bantuan", "tolong", "keluhan", "komplain", "pengaduan", "dm",
        "tanggap", "solusi", "pelanggan",
    ),
    "Jaringan, Kecepatan & Koneksi": (
        "jaringan", "internet", "koneksi", "sinyal", "gangguan", "lambat",
        "lemot", "putus", "stabil", "kecepatan", "speed", "wifi", "modem",
        "router", "fiber", "download", "upload", "mbps",
    ),
    "Pemasangan, Aktivasi & Teknisi": (
        "pemasangan", "pasang", "instalasi", "aktivasi", "aktifasi", "teknisi",
        "petugas", "survey", "kabel", "router", "modem", "fiber", "relokasi",
        "kunjungan",
    ),
    "Aplikasi & Fitur Digital": (
        "aplikasi", "app", "login", "otp", "portal", "website", "fitur",
        "akun", "password", "transaksi", "error", "verifikasi", "dashboard",
        "notifikasi",
    ),
    "Promo, Event & Program": (
        "promo", "event", "acara", "webinar", "workshop", "program", "hadiah",
        "giveaway", "kuis", "lomba", "challenge", "jawaban", "jawabannya",
        "pemenang", "periode",
    ),
    "UMKM, Usaha & Digitalisasi": (
        "umkm", "usaha", "wirausaha", "pengusaha", "bisnis", "digitalisasi",
        "transformasi", "produktivitas", "sobiz", "merchant", "toko",
        "pelaku usaha", "solusi bisnis",
    ),
    "Apresiasi, Doa & Dukungan": (
        "terimakasih", "terima kasih", "makasih", "aamiin", "amin",
        "bismillah", "semangat", "sukses", "mantap", "bagus", "keren",
        "dukungan", "doa", "berkah", "selamat",
    ),
    "Pertanyaan & Informasi Produk": (
        "tanya", "pertanyaan", "info", "informasi", "bagaimana", "kapan",
        "dimana", "syarat", "daftar", "produk", "tersedia", "cara",
        "berapa", "apakah",
    ),
    "Perbandingan Provider": (
        "provider", "kompetitor", "biznet", "starlink", "myrepublic",
        "first media", "iconnet", "dibanding", "perbandingan", "alternatif",
        "pindah",
    ),
}

_URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_MENTION_PATTERN = re.compile(r"@\w+")
_HASHTAG_PATTERN = re.compile(r"#\w+")
_NON_WORD_PATTERN = re.compile(r"[^\w\s]")
_NUMBER_PATTERN = re.compile(r"\d+")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def _normalize_sentiment(value: Any) -> str:
    """Normalisasi label sentimen menjadi positive, neutral, atau negative."""
    key = str(value or "").strip().lower().lstrip("'")
    mapping = {
        "label_0": "positive",
        "positif": "positive",
        "positive": "positive",
        "label_1": "neutral",
        "netral": "neutral",
        "neutral": "neutral",
        "label_2": "negative",
        "negatif": "negative",
        "negative": "negative",
    }
    return mapping.get(key, "neutral")


def _stopwords_for_display(show_brand: bool) -> set[str]:
    """Bentuk stopword dengan mempertimbangkan toggle nama brand."""
    stopwords = set(STOPWORDS_INDIBIZ)
    if show_brand:
        stopwords -= INDIBIZ_BRAND_WORDS
    return stopwords


def clean_for_wordcloud(text: Any, show_brand: bool = False) -> str:
    """Bersihkan teks untuk WordCloud, Top Kata, dan LDA IndiBiz."""
    try:
        value = str(text or "").lower()
        value = _URL_PATTERN.sub("", value)
        value = _MENTION_PATTERN.sub("", value)
        value = _HASHTAG_PATTERN.sub("", value)
        value = _NON_WORD_PATTERN.sub(" ", value)
        value = _NUMBER_PATTERN.sub("", value)
        value = _WHITESPACE_PATTERN.sub(" ", value).strip()

        stopwords = _stopwords_for_display(show_brand)
        tokens = [
            token
            for token in value.split()
            if len(token) > 2 and token not in stopwords
        ]
        return " ".join(tokens)
    except Exception as error:
        st.error(f"Gagal membersihkan teks WordCloud IndiBiz: {error}")
        return ""


def _semantic_topic_name(
    assigned_texts: list[str],
    lda_words: list[str],
    used_labels: set[str],
) -> str:
    """Beri nama manusiawi pada satu kelompok LDA berdasarkan isi komentarnya."""
    try:
        corpus = " ".join(str(item or "").lower() for item in assigned_texts)
        corpus = _NON_WORD_PATTERN.sub(" ", corpus)
        corpus = _WHITESPACE_PATTERN.sub(" ", corpus).strip()
        token_counts = Counter(corpus.split())
        lda_word_set = {str(word).lower().strip() for word in lda_words if str(word).strip()}

        theme_scores: dict[str, float] = {}
        for theme_name, keywords in INDIBIZ_SEMANTIC_THEMES.items():
            score = 0.0
            for keyword in keywords:
                normalized = _WHITESPACE_PATTERN.sub(
                    " ", _NON_WORD_PATTERN.sub(" ", keyword.lower())
                ).strip()
                if not normalized:
                    continue
                parts = normalized.split()
                if len(parts) == 1:
                    occurrences = int(token_counts.get(parts[0], 0))
                    score += occurrences
                    if parts[0] in lda_word_set:
                        score += 18.0
                else:
                    occurrences = corpus.count(normalized)
                    score += occurrences * 3.0
                    if any(part in lda_word_set for part in parts):
                        score += 9.0
            theme_scores[theme_name] = score

        ranked = sorted(
            theme_scores.items(),
            key=lambda item: (-item[1], item[0]),
        )
        best_name, best_score = ranked[0] if ranked else ("Percakapan Umum", 0.0)

        # Bila kamus tidak menemukan tema, gunakan dua kata LDA teratas agar
        # label tetap informatif dan tidak kembali menjadi "Topik 1/2/3".
        if best_score <= 0:
            descriptors = [
                word.replace("_", " ").title()
                for word in lda_words
                if len(str(word).strip()) > 2
            ][:2]
            best_name = (
                f"Percakapan {' & '.join(descriptors)}"
                if descriptors
                else "Percakapan Umum"
            )

        if best_name not in used_labels:
            used_labels.add(best_name)
            return best_name

        # Dua komponen LDA bisa membahas tema besar yang sama. Tambahkan
        # pembeda dari kata LDA tanpa mengubah makna tema utamanya.
        descriptors = [
            word.replace("_", " ").title()
            for word in lda_words
            if len(str(word).strip()) > 2
        ]
        for descriptor_count in (2, 3, 1):
            suffix = " & ".join(descriptors[:descriptor_count])
            if not suffix:
                continue
            candidate = f"{best_name} — {suffix}"
            if candidate not in used_labels:
                used_labels.add(candidate)
                return candidate

        index = 2
        while f"{best_name} ({index})" in used_labels:
            index += 1
        candidate = f"{best_name} ({index})"
        used_labels.add(candidate)
        return candidate
    except Exception as error:
        st.error(f"Nama topik IndiBiz gagal dibentuk: {error}")
        fallback = "Percakapan Umum"
        if fallback not in used_labels:
            used_labels.add(fallback)
            return fallback
        index = 2
        while f"{fallback} ({index})" in used_labels:
            index += 1
        fallback = f"{fallback} ({index})"
        used_labels.add(fallback)
        return fallback


def _empty_payload(df: pd.DataFrame | None = None) -> tuple[
    pd.DataFrame,
    dict[str, dict[str, int]],
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    """Kembalikan struktur payload kosong yang kompatibel dengan halaman."""
    frame = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if "topic" not in frame.columns:
        frame["topic"] = pd.Series(dtype="object")
    if "topic_method" not in frame.columns:
        frame["topic_method"] = pd.Series(dtype="object")
    if "topic_note" not in frame.columns:
        frame["topic_note"] = pd.Series(dtype="object")
    frequency_map = {sentiment: {} for sentiment in SENTIMENT_ORDER}
    return frame, frequency_map, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


def _prepare_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Validasi dan normalisasi kolom minimal untuk pipeline IndiBiz."""
    if df is None or df.empty:
        return pd.DataFrame()

    result = df.copy()
    if "content" not in result.columns:
        if "content_clean" in result.columns:
            result["content"] = result["content_clean"]
        else:
            raise ValueError("Kolom 'content' tidak ditemukan pada data IndiBiz.")
    if "predicted_sentiment" not in result.columns:
        raise ValueError("Kolom 'predicted_sentiment' tidak ditemukan pada data IndiBiz.")
    if "platform" not in result.columns:
        result["platform"] = "lainnya"

    result["content"] = result["content"].fillna("").astype(str).str.strip()
    result["predicted_sentiment"] = result["predicted_sentiment"].map(
        _normalize_sentiment
    )
    result["platform"] = (
        result["platform"].fillna("lainnya").astype(str).str.lower().str.strip()
    )
    result = result[result["content"].ne("")].reset_index(drop=True)
    return result


def _build_frequency_map(
    frame: pd.DataFrame,
    show_brand: bool,
) -> tuple[pd.DataFrame, dict[str, Counter[str]]]:
    """Tambahkan teks bersih dan hitung frekuensi kata per sentimen."""
    result = frame.copy()
    result["text_for_wc"] = result["content"].map(
        lambda value: clean_for_wordcloud(value, show_brand=show_brand)
    )

    frequency_map: dict[str, Counter[str]] = {}
    for sentiment in SENTIMENT_ORDER:
        corpus = " ".join(
            result.loc[
                result["predicted_sentiment"].eq(sentiment), "text_for_wc"
            ].astype(str)
        )
        frequency_map[sentiment] = Counter(
            token for token in corpus.split() if token
        )
    return result, frequency_map


def _dominant_sentiment(series: pd.Series) -> str:
    """Tentukan sentimen dominan dengan tie-break konsisten."""
    counts = series.map(_normalize_sentiment).value_counts()
    if counts.empty:
        return "neutral"
    return max(
        counts.index,
        key=lambda sentiment: (
            int(counts[sentiment]),
            SENTIMENT_TIE_PRIORITY.get(str(sentiment), -1),
        ),
    )


def _build_summary_from_result(
    result: pd.DataFrame,
    metadata_by_topic: dict[str, dict[str, Any]],
    top_n: int = N_TOPICS,
) -> pd.DataFrame:
    """Bangun ringkasan topik total, bukan lima topik per sentimen."""
    columns = [
        "topik",
        "jumlah_komentar",
        "persentase",
        "sentimen_dominan",
        "contoh_komentar",
        "kata_kunci",
        "metode",
        "catatan",
    ]
    if result is None or result.empty or "topic" not in result.columns:
        return pd.DataFrame(columns=columns)

    total = max(1, len(result))
    rows: list[dict[str, Any]] = []
    for topic_name, group in result.groupby("topic", sort=False, dropna=False):
        topic_label = str(topic_name or DEFAULT_TOPIC).strip()
        if not topic_label:
            continue

        count = int(len(group))
        non_empty = group["content"].fillna("").astype(str)
        non_empty = non_empty[non_empty.str.strip().ne("")]
        example = "—"
        if not non_empty.empty:
            example = str(non_empty.loc[non_empty.str.len().idxmax()]).strip()
            if len(example) > 220:
                example = example[:217].rstrip() + "..."

        metadata = metadata_by_topic.get(topic_label, {})
        rows.append(
            {
                "topik": topic_label,
                "jumlah_komentar": count,
                "persentase": round(count / total * 100.0, 1),
                "sentimen_dominan": _dominant_sentiment(
                    group["predicted_sentiment"]
                ),
                "contoh_komentar": example,
                "kata_kunci": str(metadata.get("kata_kunci", "—")),
                "metode": str(metadata.get("metode", "")),
                "catatan": str(metadata.get("catatan", "")),
            }
        )

    return (
        pd.DataFrame(rows, columns=columns)
        .sort_values(["jumlah_komentar", "topik"], ascending=[False, True])
        .head(max(1, int(top_n)))
        .reset_index(drop=True)
    )


def _fallback_global_topics(
    result: pd.DataFrame,
    reason: str,
) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    """Fallback global yang tetap menghasilkan maksimal lima topik total."""
    fallback = result.copy()
    raw_topics = classify_topics_fast(fallback["content"].astype(str).tolist())
    counts = Counter(raw_topics)
    selected_names = [name for name, _ in counts.most_common(N_TOPICS)]
    if not selected_names:
        selected_names = [DEFAULT_TOPIC]

    replacement = selected_names[-1]
    fallback["topic"] = [
        topic if topic in selected_names else replacement for topic in raw_topics
    ]
    fallback["topic_method"] = "Fallback kata kunci"
    fallback["topic_note"] = reason

    metadata: dict[str, dict[str, Any]] = {}
    for topic_name in selected_names:
        keywords = get_topic_keywords(topic_name, limit=N_WORDS)
        metadata[topic_name] = {
            "kata_kunci": ", ".join(keywords) if keywords else "—",
            "metode": "Fallback kata kunci",
            "catatan": reason,
        }
    return fallback, metadata


def _lda_topics_global(
    result: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    """Latih satu model LDA global dan bentuk tepat lima topik total."""
    valid_mask = result["text_for_wc"].astype(str).str.strip().ne("")
    valid_documents = result.loc[valid_mask, "text_for_wc"].astype(str).tolist()

    if len(valid_documents) < MIN_DOCS:
        return _fallback_global_topics(
            result,
            (
                f"Dokumen bersih hanya {len(valid_documents)}; LDA membutuhkan "
                f"minimal {MIN_DOCS} dokumen secara keseluruhan."
            ),
        )

    try:
        vectorizer = CountVectorizer(
            max_df=0.95,
            min_df=1,
            max_features=5_000,
            token_pattern=r"(?u)\b[a-zA-Z_][a-zA-Z_]+\b",
        )
        valid_document_term = vectorizer.fit_transform(valid_documents)
        feature_names = vectorizer.get_feature_names_out()

        if valid_document_term.shape[1] < N_TOPICS:
            return _fallback_global_topics(
                result,
                "Kosakata bersih belum cukup untuk membentuk lima topik LDA.",
            )

        model = LatentDirichletAllocation(
            n_components=N_TOPICS,
            random_state=RANDOM_STATE,
            learning_method="batch",
            max_iter=20,
        )
        model.fit(valid_document_term)

        # Semua komentar, termasuk teks sangat pendek, tetap dimasukkan ke salah
        # satu dari lima topik. Tidak dibuat topik keenam "Teks Tidak Cukup".
        all_document_term = vectorizer.transform(
            result["text_for_wc"].fillna("").astype(str).tolist()
        )
        all_topic_distribution = model.transform(all_document_term)
        raw_assignments = all_topic_distribution.argmax(axis=1)
        assignment_counts = Counter(int(item) for item in raw_assignments)

        # LDA dapat menghasilkan satu komponen yang tidak menjadi pilihan utama
        # dokumen mana pun. Agar bagian "Top 5 Topik" benar-benar berisi lima
        # topik, pindahkan dokumen bersih yang probabilitasnya paling kuat ke
        # komponen kosong. Dokumen hanya dipindahkan dari topik yang memiliki
        # lebih dari satu anggota sehingga tidak menciptakan topik kosong baru.
        valid_positions = [
            position
            for position, is_valid in enumerate(valid_mask.tolist())
            if bool(is_valid)
        ]
        empty_components = [
            component_id
            for component_id in range(N_TOPICS)
            if assignment_counts.get(component_id, 0) == 0
        ]
        moved_positions: set[int] = set()
        for empty_component in empty_components:
            candidates = sorted(
                valid_positions,
                key=lambda position: float(
                    all_topic_distribution[position, empty_component]
                ),
                reverse=True,
            )
            for position in candidates:
                current_component = int(raw_assignments[position])
                if position in moved_positions:
                    continue
                if assignment_counts.get(current_component, 0) <= 1:
                    continue
                raw_assignments[position] = empty_component
                assignment_counts[current_component] -= 1
                assignment_counts[empty_component] += 1
                moved_positions.add(position)
                break

        ordered_component_ids = [
            component_id
            for component_id, _ in sorted(
                assignment_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]
        # n_components selalu lima. Tambahkan komponen tanpa assignment ke akhir
        # agar metadata tetap tepat lima topik.
        ordered_component_ids.extend(
            component_id
            for component_id in range(N_TOPICS)
            if component_id not in ordered_component_ids
        )

        component_words: dict[int, list[str]] = {}
        for component_id in ordered_component_ids:
            top_indices = model.components_[component_id].argsort()[-N_WORDS:][::-1]
            component_words[component_id] = [
                str(feature_names[index]) for index in top_indices
            ]

        used_labels: set[str] = set()
        component_to_label: dict[int, str] = {}
        for component_id in ordered_component_ids:
            assigned_positions = [
                position
                for position, assignment in enumerate(raw_assignments)
                if int(assignment) == int(component_id)
            ]
            assigned_texts = [
                str(result.iloc[position].get("content", ""))
                for position in assigned_positions
            ]
            component_to_label[component_id] = _semantic_topic_name(
                assigned_texts=assigned_texts,
                lda_words=component_words.get(component_id, []),
                used_labels=used_labels,
            )

        enriched = result.copy()
        enriched["topic"] = [
            component_to_label[int(component_id)]
            for component_id in raw_assignments
        ]
        enriched["topic_method"] = "LDA"
        enriched["topic_note"] = (
            f"LDA global {N_TOPICS} topik · {N_WORDS} kata kunci · "
            f"random_state={RANDOM_STATE}"
        )

        metadata: dict[str, dict[str, Any]] = {}
        for component_id in ordered_component_ids:
            words = component_words.get(component_id, [])
            label = component_to_label[component_id]
            metadata[label] = {
                "kata_kunci": ", ".join(words),
                "metode": "LDA",
                "catatan": (
                    f"{len(valid_documents)} dokumen bersih · "
                    f"{valid_document_term.shape[1]} kata unik"
                ),
            }
        return enriched, metadata
    except ValueError as error:
        return _fallback_global_topics(
            result,
            f"LDA global tidak dapat dibentuk: {error}",
        )
    except Exception as error:
        st.error(f"LDA IndiBiz gagal dijalankan: {error}")
        return _fallback_global_topics(
            result,
            "Terjadi kendala teknis saat menjalankan LDA global.",
        )


def _build_matrix(result: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    """Bangun matriks platform × lima topik untuk heatmap Plotly."""
    if result.empty or summary.empty:
        return pd.DataFrame()

    selected_topics = summary["topik"].astype(str).tolist()
    filtered = result[result["topic"].isin(selected_topics)].copy()
    if filtered.empty:
        return pd.DataFrame()

    matrix = pd.crosstab(filtered["platform"], filtered["topic"])
    matrix = matrix.reindex(columns=selected_topics, fill_value=0)
    preferred_platforms = ["twitter", "instagram", "tiktok"]
    ordered_rows = [item for item in preferred_platforms if item in matrix.index]
    ordered_rows.extend(item for item in matrix.index if item not in ordered_rows)
    return matrix.reindex(ordered_rows, fill_value=0)


def _build_frequency_table(
    frequency_map: dict[str, Counter[str]],
) -> pd.DataFrame:
    """Bangun tabel frekuensi gabungan dan sentimen dominan."""
    combined: Counter[str] = Counter()
    for counter in frequency_map.values():
        combined.update(counter)

    rows: list[dict[str, Any]] = []
    for rank, (word, count) in enumerate(combined.most_common(), start=1):
        sentiment_counts = {
            sentiment: int(frequency_map[sentiment].get(word, 0))
            for sentiment in SENTIMENT_ORDER
        }
        dominant = max(
            SENTIMENT_ORDER,
            key=lambda sentiment: (
                sentiment_counts[sentiment],
                SENTIMENT_TIE_PRIORITY[sentiment],
            ),
        )
        rows.append(
            {
                "Rank": rank,
                "Kata": word,
                "Frekuensi": int(count),
                "Sentimen Dominan": SENTIMENT_LABELS_ID[dominant],
            }
        )
    return pd.DataFrame(rows)


def build_indibiz_topic_payload(
    df: pd.DataFrame,
    show_brand: bool = False,
) -> tuple[
    pd.DataFrame,
    dict[str, dict[str, int]],
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    """Bangun WordCloud, Top Kata, dan tepat lima topik global IndiBiz."""
    try:
        result = _prepare_frame(df)
        if result.empty:
            return _empty_payload(result)

        result, frequency_map = _build_frequency_map(result, show_brand=show_brand)
        result, metadata_by_topic = _lda_topics_global(result)
        summary = _build_summary_from_result(
            result,
            metadata_by_topic,
            top_n=N_TOPICS,
        )
        matrix = _build_matrix(result, summary)
        frequency_table = _build_frequency_table(frequency_map)

        return (
            result,
            {key: dict(value) for key, value in frequency_map.items()},
            summary,
            matrix,
            frequency_table,
        )
    except Exception as error:
        st.error(f"Gagal membangun Analisis Topik IndiBiz: {error}")
        return _empty_payload(df)


def build_indibiz_stable_filtered_payload(
    df: pd.DataFrame,
    platforms: tuple[str, ...] | list[str],
    sentiment_filter: str = "all",
    show_brand: bool = False,
) -> tuple[
    pd.DataFrame,
    dict[str, dict[str, int]],
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    """Latih lima topik pada data penuh, lalu terapkan filter tampilan."""
    try:
        full_result, _, full_summary, _, _ = build_indibiz_topic_payload(
            df,
            show_brand=show_brand,
        )
        if full_result.empty:
            return _empty_payload(full_result)

        selected_platforms = {
            str(item).strip().lower()
            for item in platforms
            if str(item).strip()
        }
        if selected_platforms:
            mask = full_result["platform"].isin(selected_platforms)
        else:
            mask = pd.Series(False, index=full_result.index)

        normalized_sentiment = str(sentiment_filter or "all").strip().lower()
        if normalized_sentiment != "all":
            mask &= full_result["predicted_sentiment"].eq(normalized_sentiment)

        filtered = full_result.loc[mask].copy().reset_index(drop=True)
        if filtered.empty:
            return _empty_payload(filtered)

        filtered, frequency_map = _build_frequency_map(
            filtered,
            show_brand=show_brand,
        )

        metadata_by_topic: dict[str, dict[str, Any]] = {}
        if full_summary is not None and not full_summary.empty:
            for _, row in full_summary.iterrows():
                metadata_by_topic[str(row.get("topik", ""))] = {
                    "kata_kunci": str(row.get("kata_kunci", "—")),
                    "metode": str(row.get("metode", "")),
                    "catatan": str(row.get("catatan", "")),
                }

        summary = _build_summary_from_result(
            filtered,
            metadata_by_topic,
            top_n=N_TOPICS,
        )
        matrix = _build_matrix(filtered, summary)
        frequency_table = _build_frequency_table(frequency_map)

        return (
            filtered,
            {key: dict(value) for key, value in frequency_map.items()},
            summary,
            matrix,
            frequency_table,
        )
    except Exception as error:
        st.error(f"Gagal menerapkan filter topik IndiBiz: {error}")
        return _empty_payload(df)
