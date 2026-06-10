"""Utilitas ekspor data dan visualisasi."""

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def export_to_csv(df: pd.DataFrame, filename: str) -> bytes:
    """Konversi DataFrame ke bytes CSV dengan UTF-8 BOM."""
    return df.to_csv(index=False).encode("utf-8-sig")


def export_to_excel(df: pd.DataFrame, filename: str, sheet_name: str = "Data") -> bytes:
    """Konversi DataFrame ke bytes Excel."""
    from io import BytesIO
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    return buffer.getvalue()


def export_figure_to_png(fig: go.Figure) -> bytes | None:
    """Export Plotly figure ke PNG bytes."""
    try:
        return fig.to_image(format="png")
    except Exception:
        return None


def export_wordcloud_to_png(wc_image) -> bytes:
    """Konversi WordCloud matplotlib figure ke PNG bytes."""
    from io import BytesIO
    buffer = BytesIO()
    wc_image.savefig(buffer, format="png", bbox_inches="tight")
    buffer.seek(0)
    return buffer.getvalue()


def get_export_filename(
    base: str, layanan: str = None, platform: str = None, ext: str = "csv"
) -> str:
    """Generate nama file ekspor yang informatif."""
    parts = [base]
    if layanan:
        parts.append(layanan.lower().replace(" ", "_"))
    if platform:
        parts.append(platform.lower())
    parts.append(datetime.now().strftime("%Y-%m"))
    return f"{'_'.join(parts)}.{ext}"


def render_download_buttons(df: pd.DataFrame, base_filename: str, key_prefix: str = "dl") -> None:
    """Render tombol download CSV dan Excel."""
    try:
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="Download CSV",
                data=export_to_csv(df, base_filename),
                file_name=get_export_filename(base_filename, ext="csv"),
                mime="text/csv",
                key=f"{key_prefix}_csv",
            )
        with col2:
            st.download_button(
                label="Download Excel",
                data=export_to_excel(df, base_filename),
                file_name=get_export_filename(base_filename, ext="xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{key_prefix}_xlsx",
            )
    except Exception as e:
        st.error(f"Gagal menyiapkan file ekspor: {e}")
