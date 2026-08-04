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


def _is_zero_dimension(value: object) -> bool:
    """Deteksi ukuran nol yang dahulu valid pada components.html."""
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value <= 0
    )


def _inject_hidden_iframe_cleanup(html: str) -> str:
    """Sembunyikan iframe utilitas tanpa menghentikan JavaScript di dalamnya.

    ``st.iframe`` hanya menerima ukuran piksel positif. Beberapa skrip internal
    proyek memakai ``height=0`` atau ``width=0`` karena hanya bertugas mengubah
    DOM halaman induk. Iframe tersebut dirender sebagai 1x1 piksel, lalu elemen
    pembungkusnya dirapatkan menjadi nol agar tidak mengubah layout dashboard.
    """
    cleanup_script = r"""
        <script id="telkom-hidden-iframe-cleanup-v1">
        (() => {
            try {
                const frame = window.frameElement;
                if (!frame) return;

                frame.setAttribute('aria-hidden', 'true');
                frame.setAttribute('tabindex', '-1');
                frame.style.position = 'absolute';
                frame.style.width = '1px';
                frame.style.height = '1px';
                frame.style.minWidth = '0';
                frame.style.minHeight = '0';
                frame.style.border = '0';
                frame.style.opacity = '0';
                frame.style.pointerEvents = 'none';

                const host = frame.closest('[data-testid="stElementContainer"]');
                if (host) {
                    host.style.position = 'relative';
                    host.style.width = '0';
                    host.style.height = '0';
                    host.style.minWidth = '0';
                    host.style.minHeight = '0';
                    host.style.margin = '0';
                    host.style.padding = '0';
                    host.style.overflow = 'hidden';
                }
            } catch (error) {
                console.debug('Iframe utilitas belum dapat dirapatkan:', error);
            }
        })();
        </script>
    """

    lowered = html.lower()
    closing_body = lowered.rfind("</body>")
    if closing_body >= 0:
        return f"{html[:closing_body]}{cleanup_script}{html[closing_body:]}"
    return f"{html}{cleanup_script}"


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

    API lama mengizinkan iframe utilitas berukuran nol. ``st.iframe`` baru
    mensyaratkan bilangan positif, sehingga ukuran nol dipetakan menjadi 1x1
    piksel dan dirapatkan kembali melalui JavaScript internal. Dengan cara ini,
    skrip startup, login, logout, auto-scroll, dan transisi tetap berjalan tanpa
    menambah ruang kosong pada antarmuka.
    """
    hidden_iframe = _is_zero_dimension(width) or _is_zero_dimension(height)

    safe_html = _inject_overflow_style(str(html), scrolling=bool(scrolling))
    if hidden_iframe:
        safe_html = _inject_hidden_iframe_cleanup(safe_html)

    effective_width: WidthValue = 1 if hidden_iframe else width
    effective_height: HeightValue = 1 if hidden_iframe else height
    effective_tab_index = -1 if hidden_iframe and tab_index is None else tab_index

    return st.iframe(
        safe_html,
        width=effective_width,
        height=effective_height,
        tab_index=effective_tab_index,
    )
