"""Kontrak dan validasi output Google Colab untuk sentimen IndiHome."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

INDIHOME_CANONICAL_OUTPUT_NAME = "indihome_sentiment.csv"
INDIHOME_OUTPUT_CANDIDATES = (
    INDIHOME_CANONICAL_OUTPUT_NAME,
    "indihome_output_sentiment.csv",
    "output_sentiment_indihome.csv",
    "indihome_sentiment.csv.gz",
)
INDIHOME_RAW_SOURCE_CANDIDATES = (
    "Indihome November-Desember 2025 Gabungan.csv",
    "IndiHome November-Desember 2025 Gabungan.csv",
    "Indihome November-Desember 2025 Gabungan.xlsx",
    "IndiHome November-Desember 2025 Gabungan.xlsx",
)

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("date", "date_created", "created_at", "timestamp"),
    "platform": ("platform", "specific_resource_type", "source_platform"),
    "username": ("username", "from_username", "user", "screen_name"),
    "followers": ("followers", "follower_count", "followers_count"),
    "content": ("content", "text", "comment", "tweet_text", "caption"),
    "content_clean": ("content_clean", "cleaned_text"),
    "predicted_sentiment": (
        "predicted_sentiment",
        "final_sentiment",
        "sentiment",
        "label",
    ),
    "confidence": (
        "confidence",
        "confidence_score",
        "score",
        "sentiment_confidence_level",
    ),
}

REQUIRED_CANONICAL_COLUMNS = (
    "date",
    "platform",
    "username",
    "followers",
    "content",
    "predicted_sentiment",
    "confidence",
)
ALLOWED_PLATFORMS = {"twitter", "instagram", "tiktok"}
SENTIMENT_MAP = {
    "label_0": "positive",
    "positive": "positive",
    "positif": "positive",
    "label_1": "neutral",
    "neutral": "neutral",
    "netral": "neutral",
    "label_2": "negative",
    "negative": "negative",
    "negatif": "negative",
}


def resolve_indihome_output(data_dir: Path) -> Path | None:
    """Temukan output prediksi IndiHome yang aman dan tidak ambigu."""
    try:
        folder = Path(data_dir)
        if not folder.is_dir():
            return None
        by_lower = {
            path.name.casefold(): path
            for path in folder.iterdir()
            if path.is_file()
        }
        for filename in INDIHOME_OUTPUT_CANDIDATES:
            match = by_lower.get(filename.casefold())
            if match is not None:
                return match
        return None
    except Exception:
        return None


def resolve_indihome_raw_source(data_dir: Path) -> Path | None:
    """Temukan dataset mentah IndiHome hanya untuk diagnostik."""
    try:
        folder = Path(data_dir)
        if not folder.is_dir():
            return None
        by_lower = {
            path.name.casefold(): path
            for path in folder.iterdir()
            if path.is_file()
        }
        for filename in INDIHOME_RAW_SOURCE_CANDIDATES:
            match = by_lower.get(filename.casefold())
            if match is not None:
                return match
        return None
    except Exception:
        return None


def map_columns(columns: Iterable[Any]) -> dict[str, str]:
    """Petakan nama kolom sumber ke kontrak kanonik dashboard."""
    lookup = {str(column).strip().casefold(): str(column) for column in columns}
    mapped: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            source = lookup.get(alias.casefold())
            if source is not None:
                mapped[canonical] = source
                break
    return mapped


def detect_csv_format(path: Path) -> tuple[str, str, list[str]]:
    """Deteksi delimiter, encoding, dan header CSV secara defensif."""
    attempts = (
        (",", "utf-8-sig"),
        (";", "utf-8-sig"),
        ("\t", "utf-8-sig"),
        (",", "utf-8"),
        (";", "utf-8"),
        (",", "latin-1"),
        (";", "latin-1"),
    )
    errors: list[str] = []
    for delimiter, encoding in attempts:
        try:
            frame = pd.read_csv(
                path,
                sep=delimiter,
                encoding=encoding,
                nrows=0,
                compression="infer",
            )
            columns = [str(column).strip() for column in frame.columns]
            mapping = map_columns(columns)
            if all(column in mapping for column in REQUIRED_CANONICAL_COLUMNS):
                return delimiter, encoding, columns
        except Exception as exc:
            errors.append(f"{delimiter!r}/{encoding}: {exc}")
    detail = errors[-1] if errors else "header tidak dikenali"
    raise ValueError(f"CSV tidak memiliki kontrak output IndiHome yang valid. Detail: {detail}")


def inspect_indihome_output(
    path: Path,
    *,
    scan_rows: bool = True,
    chunksize: int = 50_000,
) -> dict[str, Any]:
    """Validasi skema dan isi output prediksi Google Colab IndiHome."""
    source = Path(path)
    result: dict[str, Any] = {
        "file_found": source.is_file(),
        "source_name": source.name,
        "source_path": str(source),
        "ready": False,
        "delimiter": None,
        "encoding": None,
        "columns": [],
        "missing_columns": [],
        "total_rows": 0,
        "valid_rows": 0,
        "invalid_platform_rows": 0,
        "invalid_sentiment_rows": 0,
        "invalid_confidence_rows": 0,
        "empty_content_rows": 0,
        "platform_counts": {},
        "sentiment_counts": {},
        "message": "",
    }
    if not source.is_file():
        result["message"] = "File output prediksi IndiHome tidak ditemukan."
        return result

    try:
        delimiter, encoding, columns = detect_csv_format(source)
        mapping = map_columns(columns)
        missing = [
            column for column in REQUIRED_CANONICAL_COLUMNS if column not in mapping
        ]
        result.update(
            {
                "delimiter": delimiter,
                "encoding": encoding,
                "columns": columns,
                "missing_columns": missing,
            }
        )
        if missing:
            result["message"] = "Kolom wajib belum lengkap: " + ", ".join(missing)
            return result
        if not scan_rows:
            result["ready"] = True
            result["message"] = "Header output prediksi IndiHome valid."
            return result

        usecols = list(dict.fromkeys(mapping.values()))
        platform_counts: dict[str, int] = {}
        sentiment_counts: dict[str, int] = {}
        total_rows = valid_rows = 0
        invalid_platform = invalid_sentiment = invalid_confidence = empty_content = 0

        for chunk in pd.read_csv(
            source,
            sep=delimiter,
            encoding=encoding,
            usecols=usecols,
            dtype="string",
            keep_default_na=False,
            na_filter=False,
            compression="infer",
            chunksize=max(1, int(chunksize)),
            low_memory=True,
        ):
            rename = {source_name: canonical for canonical, source_name in mapping.items()}
            chunk = chunk.rename(columns=rename)
            total_rows += len(chunk)

            platform = (
                chunk["platform"]
                .astype("string")
                .fillna("")
                .str.strip()
                .str.casefold()
                .replace(
                    {
                        "x": "twitter",
                        "twitter/x": "twitter",
                        "twitter (x)": "twitter",
                        "x/twitter": "twitter",
                        "ig": "instagram",
                        "tik tok": "tiktok",
                    }
                )
            )
            sentiment = (
                chunk["predicted_sentiment"]
                .astype("string")
                .fillna("")
                .str.strip()
                .str.casefold()
                .map(SENTIMENT_MAP)
            )
            confidence = pd.to_numeric(chunk["confidence"], errors="coerce")
            content = chunk["content"].astype("string").fillna("").str.strip()

            platform_ok = platform.isin(ALLOWED_PLATFORMS)
            sentiment_ok = sentiment.notna()
            confidence_ok = confidence.between(0.0, 1.0, inclusive="both")
            content_ok = content.ne("") & ~content.str.casefold().isin({"nan", "none"})
            row_ok = platform_ok & sentiment_ok & confidence_ok & content_ok

            invalid_platform += int((~platform_ok).sum())
            invalid_sentiment += int((~sentiment_ok).sum())
            invalid_confidence += int((~confidence_ok).sum())
            empty_content += int((~content_ok).sum())
            valid_rows += int(row_ok.sum())

            for key, value in platform[platform_ok].value_counts().items():
                platform_counts[str(key)] = platform_counts.get(str(key), 0) + int(value)
            for key, value in sentiment[sentiment_ok].value_counts().items():
                sentiment_counts[str(key)] = sentiment_counts.get(str(key), 0) + int(value)

        ready = (
            total_rows > 0
            and valid_rows > 0
            and invalid_platform == 0
            and invalid_sentiment == 0
            and invalid_confidence == 0
            and empty_content == 0
        )
        result.update(
            {
                "ready": ready,
                "total_rows": total_rows,
                "valid_rows": valid_rows,
                "invalid_platform_rows": invalid_platform,
                "invalid_sentiment_rows": invalid_sentiment,
                "invalid_confidence_rows": invalid_confidence,
                "empty_content_rows": empty_content,
                "platform_counts": platform_counts,
                "sentiment_counts": sentiment_counts,
                "message": (
                    "Output prediksi Google Colab IndiHome valid dan siap digunakan."
                    if ready
                    else "File terbaca, tetapi masih memiliki baris yang tidak valid."
                ),
            }
        )
        return result
    except Exception as exc:
        result["message"] = f"Gagal memvalidasi output IndiHome: {exc}"
        return result
