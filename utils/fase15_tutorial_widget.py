"""Widget HTML interaktif untuk tutorial Tahap 4 Fase 15."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


@st.cache_data(show_spinner=False, max_entries=2)
def _load_fase15_tutorial_html(file_signature: str) -> str:
    """Baca HTML tutorial dan perbarui cache saat file berubah."""
    del file_signature
    try:
        tutorial_path = (
            Path(__file__).resolve().parent.parent
            / "tutorial"
            / "Panduan_Interaktif_Fase_15_Analisis_Topik.html"
        )
        return tutorial_path.read_text(encoding="utf-8")
    except Exception as error:
        return f"""
        <div style="font-family:Inter,Arial;padding:18px;background:#171717;
                    color:#fff;border:1px solid #E53935;border-radius:14px">
          <b>Panduan Fase 15 belum dapat dibaca.</b><br>
          Periksa folder <code>tutorial</code>. Detail: {error}
        </div>
        """


def render_fase15_tutorial_widget() -> None:
    """Tampilkan tutorial interaktif pada halaman Analisis Topik."""
    try:
        tutorial_path = (
            Path(__file__).resolve().parent.parent
            / "tutorial"
            / "Panduan_Interaktif_Fase_15_Analisis_Topik.html"
        )
        signature = (
            f"{tutorial_path.stat().st_mtime_ns}:{tutorial_path.stat().st_size}"
            if tutorial_path.exists()
            else "missing"
        )
        with st.expander(
            "🧭 Panduan Interaktif Tahap 4 Fase 15",
            expanded=False,
        ):
            st.caption(
                "Panduan ini hanya membahas dashboard Streamlit. "
                "Notebook Google Colab tidak dibuka atau diubah."
            )
            components.html(
                _load_fase15_tutorial_html(signature),
                height=860,
                scrolling=True,
            )
    except Exception as error:
        st.error(f"Tutorial interaktif Fase 15 belum dapat ditampilkan: {error}")
