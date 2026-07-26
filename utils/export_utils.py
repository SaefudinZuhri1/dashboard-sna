"""Utilitas ekspor DataFrame dan visualisasi dashboard."""

from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Konversi DataFrame menjadi bytes CSV ber-encoding UTF-8 BOM."""
    try:
        if not isinstance(df, pd.DataFrame):
            raise TypeError("Data ekspor harus berupa pandas DataFrame.")
        return df.to_csv(index=False).encode("utf-8-sig")
    except Exception as exc:
        st.error(f"Gagal membuat file CSV: {exc}")
        return b""


def _sanitize_sheet_name(sheet_name: str) -> str:
    """Bersihkan nama sheet agar valid untuk file Excel."""
    try:
        cleaned = re.sub(r"[\\/*?:\[\]]", "_", str(sheet_name or "Data")).strip()
        return (cleaned or "Data")[:31]
    except Exception as exc:
        st.error(f"Nama sheet Excel tidak valid: {exc}")
        return "Data"


def df_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Data") -> bytes:
    """Konversi DataFrame menjadi bytes Excel menggunakan openpyxl."""
    try:
        if not isinstance(df, pd.DataFrame):
            raise TypeError("Data ekspor harus berupa pandas DataFrame.")

        buffer = io.BytesIO()
        valid_sheet_name = _sanitize_sheet_name(sheet_name)
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=valid_sheet_name, index=False)
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as exc:
        st.error(f"Gagal membuat file Excel: {exc}")
        return b""


def fig_to_png_bytes(fig: go.Figure) -> bytes:
    """Konversi figure Plotly menjadi bytes PNG menggunakan Kaleido."""
    try:
        if fig is None or not hasattr(fig, "to_image"):
            raise TypeError("Objek visualisasi bukan figure Plotly yang valid.")
        return fig.to_image("png")
    except Exception as exc:
        st.error(
            "Gagal membuat gambar PNG dari Plotly. Pastikan package kaleido "
            f"sudah terpasang. Detail: {exc}"
        )
        return b""


def wordcloud_to_bytes(wc_obj: Any) -> bytes:
    """Konversi objek WordCloud menjadi bytes PNG melalui BytesIO."""
    try:
        if wc_obj is None or not hasattr(wc_obj, "to_image"):
            raise TypeError("Objek WordCloud tidak valid atau belum dibuat.")

        image = wc_obj.to_image()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as exc:
        st.error(f"Gagal membuat gambar WordCloud: {exc}")
        return b""


def _normalize_download_filename(filename: str) -> str:
    """Buat nama dasar file download yang aman dan konsisten."""
    try:
        raw_name = Path(str(filename or "data")).stem
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", raw_name).strip("_")
        return safe_name or "data"
    except Exception as exc:
        st.error(f"Nama file download tidak valid: {exc}")
        return "data"


def add_download_section(df: pd.DataFrame, filename: str) -> None:
    """Render tombol Download CSV dan Download Excel dalam dua kolom."""
    try:
        if not isinstance(df, pd.DataFrame):
            raise TypeError("Data download harus berupa pandas DataFrame.")

        base_filename = _normalize_download_filename(filename)
        csv_bytes = df_to_csv_bytes(df)
        excel_bytes = df_to_excel_bytes(df)

        col_csv, col_excel = st.columns(2)
        with col_csv:
            st.download_button(
                label="⬇️ Download CSV",
                data=csv_bytes,
                file_name=f"{base_filename}.csv",
                mime="text/csv",
                use_container_width=True,
                disabled=not bool(csv_bytes),
                key=f"download_{base_filename}_csv",
            )

        with col_excel:
            st.download_button(
                label="⬇️ Download Excel",
                data=excel_bytes,
                file_name=f"{base_filename}.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                use_container_width=True,
                disabled=not bool(excel_bytes),
                key=f"download_{base_filename}_xlsx",
            )
    except Exception as exc:
        st.error(f"Bagian download belum dapat ditampilkan: {exc}")


# -----------------------------------------------------------------------------
# Fungsi kompatibilitas untuk halaman versi sebelumnya.
# Nama lama dipertahankan agar Dataset, WordCloud, dan SNA tidak mengalami
# import error ketika utils/export_utils.py diperbarui pada Fase 20.
# -----------------------------------------------------------------------------


def export_to_csv(df: pd.DataFrame, filename: str = "data") -> bytes:
    """Alias kompatibel untuk ekspor DataFrame ke CSV."""
    try:
        _ = filename
        return df_to_csv_bytes(df)
    except Exception as exc:
        st.error(f"Gagal mengekspor CSV: {exc}")
        return b""


def export_to_excel(
    df: pd.DataFrame,
    filename: str = "data",
    sheet_name: str = "Data",
) -> bytes:
    """Alias kompatibel untuk ekspor DataFrame ke Excel."""
    try:
        _ = filename
        return df_to_excel_bytes(df, sheet_name=sheet_name)
    except Exception as exc:
        st.error(f"Gagal mengekspor Excel: {exc}")
        return b""


def export_figure_to_png(fig: go.Figure) -> bytes | None:
    """Alias kompatibel untuk ekspor figure Plotly ke PNG."""
    try:
        png_bytes = fig_to_png_bytes(fig)
        return png_bytes or None
    except Exception as exc:
        st.error(f"Gagal mengekspor figure Plotly: {exc}")
        return None


def export_wordcloud_to_png(wc_image: Any) -> bytes:
    """Ekspor WordCloud atau figure Matplotlib lama menjadi bytes PNG."""
    try:
        if wc_image is None:
            raise TypeError("Objek WordCloud atau figure tidak tersedia.")

        if hasattr(wc_image, "to_image"):
            return wordcloud_to_bytes(wc_image)

        if hasattr(wc_image, "savefig"):
            buffer = io.BytesIO()
            facecolor = (
                wc_image.get_facecolor()
                if hasattr(wc_image, "get_facecolor")
                else None
            )
            save_kwargs = {
                "format": "png",
                "bbox_inches": "tight",
            }
            if facecolor is not None:
                save_kwargs["facecolor"] = facecolor
            wc_image.savefig(buffer, **save_kwargs)
            buffer.seek(0)
            return buffer.getvalue()

        raise TypeError("Format objek WordCloud tidak dikenali.")
    except Exception as exc:
        st.error(f"Gagal mengekspor WordCloud: {exc}")
        return b""


def get_export_filename(
    base: str,
    layanan: str | None = None,
    platform: str | None = None,
    ext: str = "csv",
) -> str:
    """Buat nama file ekspor yang informatif dan bertanggal."""
    try:
        parts = [_normalize_download_filename(base)]
        if layanan:
            parts.append(_normalize_download_filename(layanan).lower())
        if platform:
            parts.append(_normalize_download_filename(platform).lower())
        parts.append(datetime.now().strftime("%Y-%m"))

        clean_ext = re.sub(r"[^A-Za-z0-9]", "", str(ext or "csv")) or "csv"
        return f"{'_'.join(parts)}.{clean_ext.lower()}"
    except Exception as exc:
        st.error(f"Gagal membuat nama file ekspor: {exc}")
        return f"data_{datetime.now().strftime('%Y-%m')}.csv"


def render_download_buttons(
    df: pd.DataFrame,
    base_filename: str,
    key_prefix: str = "dl",
) -> None:
    """Render tombol download lama dengan kompatibilitas key widget."""
    try:
        safe_filename = _normalize_download_filename(base_filename)
        safe_key = _normalize_download_filename(key_prefix)
        csv_bytes = df_to_csv_bytes(df)
        excel_bytes = df_to_excel_bytes(df)

        col_csv, col_excel = st.columns(2)
        with col_csv:
            st.download_button(
                label="Download CSV",
                data=csv_bytes,
                file_name=get_export_filename(safe_filename, ext="csv"),
                mime="text/csv",
                key=f"{safe_key}_csv",
                disabled=not bool(csv_bytes),
            )
        with col_excel:
            st.download_button(
                label="Download Excel",
                data=excel_bytes,
                file_name=get_export_filename(safe_filename, ext="xlsx"),
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                key=f"{safe_key}_xlsx",
                disabled=not bool(excel_bytes),
            )
    except Exception as exc:
        st.error(f"Gagal menyiapkan file ekspor: {exc}")
