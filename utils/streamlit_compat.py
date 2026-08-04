"""Kompatibilitas renderer HTML untuk Streamlit versi terbaru.

Modul ini menjaga perilaku iframe lama tanpa memakai API yang sudah usang.
HTML yang diterima harus berasal dari kode internal proyek, bukan input pengguna.
"""

from __future__ import annotations

from typing import Literal

import streamlit as st


WidthValue = int | Literal["stretch", "content"]
HeightValue = int | Literal["stretch", "content"]


def _inject_overflow_style(html: str, *, scrolling: bool) -> str:
    """Tambahkan aturan scroll tanpa mengubah isi visual HTML."""
    overflow = "auto" if scrolling else "hidden"
    style = (
        '<style id="telkom-iframe-overflow-compat">'
        f'html,body{{overflow:{overflow} !important;}}'
        '</style>'
    )
    lowered = html.lower()
    closing_head = lowered.find("</head>")
    if closing_head >= 0:
        return f"{html[:closing_head]}{style}{html[closing_head:]}"
    return f"{style}{html}"


def render_html_iframe(
    html: str,
    *,
    width: WidthValue = "stretch",
    height: HeightValue = "content",
    scrolling: bool = False,
    tab_index: int | None = None,
):
    """Render HTML internal memakai ``st.iframe`` yang didukung Streamlit.

    Parameter sengaja menyerupai renderer lama agar patch tetap kecil dan
    seluruh tinggi, lebar, serta perilaku scroll komponen tidak berubah.
    """
    safe_html = _inject_overflow_style(str(html), scrolling=bool(scrolling))
    return st.iframe(
        safe_html,
        width=width,
        height=height,
        tab_index=tab_index,
    )
