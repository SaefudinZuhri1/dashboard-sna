# utils/theme_manager.py
"""Pengelola tema dinamis untuk chart Plotly dashboard Telkom Group."""

from __future__ import annotations

from functools import wraps
from typing import Any

try:
    import streamlit as st
except Exception:  # pragma: no cover - fallback saat test tanpa Streamlit
    st = None


FONT_FAMILY = "Plus Jakarta Sans, Inter, DM Sans, sans-serif"
TRANSPARENT = "rgba(0,0,0,0)"

THEME_TOKENS = {
    "light": {
        "template": "plotly_white",
        "text": "#1F2937",
        "muted": "#64748B",
        "grid": "rgba(100,116,139,0.18)",
        "axis": "rgba(100,116,139,0.28)",
        "legend_bg": "rgba(255,255,255,0.88)",
        "legend_border": "rgba(100,116,139,0.20)",
        "hover_bg": "#FFFFFF",
        "hover_border": "rgba(229,57,53,0.28)",
    },
    "dark": {
        "template": "plotly_dark",
        "text": "#F8FAFC",
        "muted": "#A7B0BF",
        "grid": "rgba(42,54,72,0.74)",
        "axis": "rgba(167,176,191,0.28)",
        "legend_bg": "rgba(21,27,38,0.88)",
        "legend_border": "rgba(167,176,191,0.18)",
        "hover_bg": "#151B26",
        "hover_border": "rgba(229,57,53,0.36)",
    },
}


def _show_error(message: str) -> None:
    """Tampilkan error hanya ketika runtime Streamlit tersedia."""
    try:
        if st is not None:
            st.error(message)
    except Exception:
        return


def is_dark_mode() -> bool:
    """Ambil status tema aktif dari session state secara aman."""
    try:
        if st is None:
            return False
        return bool(st.session_state.get("dark_mode", False))
    except Exception as exc:
        _show_error(f"Status tema belum dapat dibaca: {exc}")
        return False


def get_theme_tokens(dark_mode: bool | None = None) -> dict[str, str]:
    """Kembalikan token warna Plotly untuk tema aktif."""
    try:
        resolved_dark_mode = is_dark_mode() if dark_mode is None else bool(dark_mode)
        theme_name = "dark" if resolved_dark_mode else "light"
        return dict(THEME_TOKENS[theme_name])
    except Exception as exc:
        _show_error(f"Konfigurasi warna chart belum dapat disiapkan: {exc}")
        return dict(THEME_TOKENS["light"])


def _adapt_annotation(annotation: Any, text_color: str) -> None:
    """Sesuaikan warna anotasi gelap atau terang tanpa mengubah posisinya."""
    try:
        current_color = str(getattr(annotation.font, "color", "") or "").lower()
        colors_to_replace = {
            "",
            "#ffffff",
            "#fff",
            "white",
            "#f8fafc",
            "#1f2937",
            "#111827",
            "#0f172a",
            "black",
            "#000000",
        }
        if current_color in colors_to_replace:
            annotation.font.color = text_color
        if not getattr(annotation.font, "family", None):
            annotation.font.family = FONT_FAMILY
    except Exception:
        return


def apply_plotly_theme(figure: Any, dark_mode: bool | None = None) -> Any:
    """Terapkan tema Plotly tanpa mengubah jenis chart, data, atau urutan visual."""
    try:
        if figure is None or not hasattr(figure, "update_layout"):
            return figure

        theme = get_theme_tokens(dark_mode)
        figure.update_layout(
            template=theme["template"],
            paper_bgcolor=TRANSPARENT,
            plot_bgcolor=TRANSPARENT,
            font={"family": FONT_FAMILY, "color": theme["text"]},
            title_font={"family": FONT_FAMILY, "color": theme["text"]},
            hoverlabel={
                "bgcolor": theme["hover_bg"],
                "bordercolor": theme["hover_border"],
                "font": {"family": FONT_FAMILY, "color": theme["text"]},
            },
            legend={
                "bgcolor": theme["legend_bg"],
                "bordercolor": theme["legend_border"],
                "font": {"family": FONT_FAMILY, "color": theme["text"]},
                "title": {"font": {"family": FONT_FAMILY, "color": theme["text"]}},
            },
        )

        figure.update_xaxes(
            gridcolor=theme["grid"],
            linecolor=theme["axis"],
            tickcolor=theme["muted"],
            color=theme["muted"],
            title_font={"family": FONT_FAMILY, "color": theme["muted"]},
            tickfont={"family": FONT_FAMILY, "color": theme["muted"]},
        )
        figure.update_yaxes(
            gridcolor=theme["grid"],
            linecolor=theme["axis"],
            tickcolor=theme["muted"],
            color=theme["muted"],
            title_font={"family": FONT_FAMILY, "color": theme["muted"]},
            tickfont={"family": FONT_FAMILY, "color": theme["muted"]},
        )

        if hasattr(figure, "for_each_annotation"):
            figure.for_each_annotation(
                lambda annotation: _adapt_annotation(annotation, theme["text"])
            )

        if getattr(figure.layout, "coloraxis", None):
            figure.update_coloraxes(
                colorbar={
                    "tickfont": {"family": FONT_FAMILY, "color": theme["muted"]},
                    "title": {
                        "font": {"family": FONT_FAMILY, "color": theme["muted"]}
                    },
                    "outlinecolor": theme["axis"],
                }
            )

        return figure
    except Exception as exc:
        _show_error(f"Tema chart belum dapat diterapkan: {exc}")
        return figure


def install_plotly_theme_adapter() -> None:
    """Pasang adaptor satu kali agar seluruh st.plotly_chart mengikuti tema aktif."""
    try:
        if st is None:
            return
        if getattr(st, "_telkom_plotly_theme_adapter_v1", False):
            return

        original_plotly_chart = st.plotly_chart

        @wraps(original_plotly_chart)
        def themed_plotly_chart(figure_or_data: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                themed_figure = apply_plotly_theme(figure_or_data)
                return original_plotly_chart(themed_figure, *args, **kwargs)
            except Exception as exc:
                _show_error(f"Chart belum dapat ditampilkan dengan tema aktif: {exc}")
                return original_plotly_chart(figure_or_data, *args, **kwargs)

        st.plotly_chart = themed_plotly_chart
        st._telkom_plotly_theme_adapter_v1 = True
    except Exception as exc:
        _show_error(f"Adaptor tema chart belum dapat dipasang: {exc}")
