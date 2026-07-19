"""Pembacaan, preprocessing, validasi, dan penyimpanan data Telkomsel."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from utils.preprocessor import prepare_telkomsel_sentiment_dataframe
from utils.telkomsel_config import (
    CANONICAL_OUTPUT_FILE,
    OUTPUT_COLUMNS,
    RAW_COLUMN_ALIASES,
    validate_telkomsel_preprocessing_dataframe,
)

_SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def get_telkomsel_source_signature(source_path: str | Path) -> str:
    """Bentuk signature ukuran dan waktu ubah file untuk cache Streamlit."""
    try:
        path = Path(source_path).expanduser().resolve()
        stat = path.stat()
        return f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}"
    except Exception:
        return f"{source_path}:unknown"


def _select_source_columns(columns: list[str]) -> list[str]:
    """Pilih kolom minimum berdasarkan alias kontrak data Telkomsel."""
    lookup = {str(column).strip().lower(): str(column) for column in columns}
    selected: list[str] = []
    for aliases in RAW_COLUMN_ALIASES.values():
        for alias in aliases:
            source = lookup.get(str(alias).lower())
            if source is not None:
                selected.append(source)
                break
    return list(dict.fromkeys(selected))


def _read_telkomsel_csv(path: Path) -> pd.DataFrame:
    """Baca CSV dengan delimiter dan encoding defensif."""
    attempts = (
        (";", "utf-8-sig"),
        (",", "utf-8-sig"),
        ("\t", "utf-8-sig"),
        (";", "latin-1"),
        (",", "latin-1"),
    )
    errors: list[str] = []
    for delimiter, encoding in attempts:
        try:
            header = pd.read_csv(
                path,
                sep=delimiter,
                encoding=encoding,
                nrows=0,
            )
            usecols = _select_source_columns(list(header.columns))
            if len(usecols) < 4:
                continue
            return pd.read_csv(
                path,
                sep=delimiter,
                encoding=encoding,
                usecols=usecols,
                dtype="string",
                keep_default_na=False,
                na_filter=False,
                low_memory=True,
            )
        except Exception as error:
            errors.append(f"{delimiter!r}/{encoding}: {error}")
    raise ValueError(
        "CSV Telkomsel tidak dapat dibaca dengan delimiter yang didukung. "
        + " | ".join(errors[-2:])
    )


def _read_telkomsel_excel(path: Path) -> pd.DataFrame:
    """Baca sheet pertama yang memiliki empat kolom sumber wajib."""
    workbook = pd.ExcelFile(path)
    for sheet_name in workbook.sheet_names:
        try:
            header = pd.read_excel(workbook, sheet_name=sheet_name, nrows=0)
            usecols = _select_source_columns(list(header.columns))
            if len(usecols) < 4:
                continue
            return pd.read_excel(
                workbook,
                sheet_name=sheet_name,
                usecols=usecols,
                dtype="string",
            )
        except Exception:
            continue
    raise ValueError("Tidak ada sheet Excel yang memiliki kolom sumber Telkomsel lengkap.")


@st.cache_data(show_spinner=False, persist="disk", max_entries=4)
def load_telkomsel_raw_data(
    source_path: str,
    file_signature: str | None = None,
) -> pd.DataFrame:
    """Muat data mentah Telkomsel dari CSV atau Excel.

    ``file_signature`` menjadi cache key. Fungsi hanya membaca file dan tidak
    mengubah data sumber.
    """
    del file_signature
    try:
        path = Path(source_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"File sumber tidak ditemukan: {path}")
        if path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            raise ValueError(
                "Format file tidak didukung. Gunakan CSV, XLSX, atau XLS."
            )

        if path.suffix.lower() == ".csv":
            dataframe = _read_telkomsel_csv(path)
        else:
            dataframe = _read_telkomsel_excel(path)

        if dataframe.empty:
            raise ValueError("File sumber ditemukan, tetapi tidak memiliki baris data.")
        return dataframe
    except Exception as error:
        st.error(f"Gagal membaca data mentah Telkomsel: {error}")
        return pd.DataFrame()


def save_telkomsel_preprocessing_csv(
    dataframe: pd.DataFrame,
    output_path: str | Path,
) -> dict[str, object]:
    """Validasi lalu simpan output preprocessing dengan UTF-8-SIG."""
    result: dict[str, object] = {
        "saved": False,
        "path": str(output_path),
        "rows": 0,
        "message": "File belum disimpan.",
    }
    try:
        validation = validate_telkomsel_preprocessing_dataframe(dataframe)
        if not validation.get("ready"):
            result["message"] = str(validation.get("message"))
            st.error(result["message"])
            return result

        path = Path(output_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        dataframe[list(OUTPUT_COLUMNS)].to_csv(
            path,
            index=False,
            encoding="utf-8-sig",
        )
        result.update(
            {
                "saved": True,
                "path": str(path),
                "rows": int(len(dataframe)),
                "message": (
                    f"Berhasil menyimpan {len(dataframe):,} baris ke {path}."
                ),
            }
        )
        return result
    except Exception as error:
        result["message"] = f"Gagal menyimpan output preprocessing Telkomsel: {error}"
        st.error(result["message"])
        return result


def preprocess_telkomsel_source(
    source_path: str | Path,
    output_path: str | Path | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Jalankan alur baca, preprocessing, validasi, dan simpan secara modular."""
    try:
        source = Path(source_path).expanduser().resolve()
        signature = get_telkomsel_source_signature(source)
        raw = load_telkomsel_raw_data(str(source), signature)
        if raw.empty:
            return pd.DataFrame(columns=list(OUTPUT_COLUMNS)), {
                "saved": False,
                "path": "",
                "rows": 0,
                "message": "Data mentah tidak dapat diproses.",
            }

        processed = prepare_telkomsel_sentiment_dataframe(raw)
        destination = (
            Path(output_path).expanduser().resolve()
            if output_path is not None
            else source.parent / CANONICAL_OUTPUT_FILE
        )
        save_result = save_telkomsel_preprocessing_csv(processed, destination)
        return processed, save_result
    except Exception as error:
        st.error(f"Gagal menjalankan preprocessing Telkomsel: {error}")
        return pd.DataFrame(columns=list(OUTPUT_COLUMNS)), {
            "saved": False,
            "path": "",
            "rows": 0,
            "message": str(error),
        }
