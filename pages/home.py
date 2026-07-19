# pages/home.py
"""Halaman Beranda tiga layanan Telkom Group dengan visualisasi interaktif."""
from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any
import inspect
import logging
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.loading_screen import (
    batalkan_layar_loading,
    mulai_layar_loading,
    mulai_loading_aksi,
    selesaikan_layar_loading,
    selesaikan_loading_aksi,
)
from utils.data_loader import (
    load_indibiz_sentiment,
    load_sentiment_data,
    load_sna_data,
    load_telkomsel_sentiment,
    sentiment_file_exists,
    sna_file_exists,
)
from utils.dummy_data import (
    get_dummy_indibiz_sentiment,
    get_dummy_sentiment_data,
    get_dummy_sna_data,
)

PLATFORM_ORDER = ["twitter", "instagram", "tiktok"]
PLATFORM_LABELS = {
    "twitter": "Twitter/X",
    "instagram": "Instagram",
    "tiktok": "TikTok",
}
SENTIMENT_ORDER = ["positive", "neutral", "negative"]
SENTIMENT_LABELS = {
    "positive": "Positif",
    "neutral": "Netral",
    "negative": "Negatif",
}
SENTIMENT_COLORS = {
    "positive": "#4CAF50",
    "neutral": "#FF9800",
    "negative": "#F44336",
}
LOGGER = logging.getLogger(__name__)
STATE_LOADING_SELESAI = "home_v5_loading_selesai"
STATE_INFLUENCER_FILTER_LOADING = "home_v5_influencer_filter_loading"
STATE_GUIDE_NAVIGATION = "home_v5_guide_navigation"
INFLUENCER_FILTER_MIN_SECONDS = 0.55

_DIALOG_DECORATOR = getattr(st, "dialog", None)
if _DIALOG_DECORATOR is None:
    _DIALOG_DECORATOR = st.experimental_dialog

BRAND_ALIASES = {
    "indihome",
    "indihomecare",
    "myindihome",
    "indibiz",
    "indibizid",
    "telkomsel",
    "telkomselcare",
    "telkomindonesia",
    "telkom",
}



def _supports_parameter(callback: Any, parameter: str) -> bool:
    """Periksa dukungan parameter API Streamlit lintas versi."""
    try:
        return parameter in inspect.signature(callback).parameters
    except (TypeError, ValueError):
        return False


def _service_container(key: str, *, height: int | None = None):
    """Buat container layanan dengan tinggi seragam secara native.

    Parameter ``height`` hanya dikirim jika versi Streamlit yang dipakai
    mendukungnya. Dengan begitu kartu tetap kompatibel pada versi lama tanpa
    memaksa seluruh elemen anak memakai tinggi 100 persen melalui CSS.
    """
    kwargs: dict[str, Any] = {"border": True}
    if _supports_parameter(st.container, "key"):
        kwargs["key"] = key
    if height is not None and _supports_parameter(st.container, "height"):
        kwargs["height"] = int(height)
    return st.container(**kwargs)


def _service_columns(spec: Any, gap: str | None = None):
    """Buat kolom layanan tanpa memaksa parameter yang belum didukung."""
    kwargs: dict[str, Any] = {}
    if gap and _supports_parameter(st.columns, "gap"):
        kwargs["gap"] = gap
    return st.columns(spec, **kwargs)


def _service_button(label: str, *, stretch: bool = True, **kwargs: Any) -> bool:
    """Render tombol layanan dengan fallback width lintas versi Streamlit."""
    if stretch:
        if _supports_parameter(st.button, "width"):
            kwargs["width"] = "stretch"
        elif _supports_parameter(st.button, "use_container_width"):
            kwargs["use_container_width"] = True
    return bool(st.button(label, **kwargs))


def _service_plotly_chart(figure: go.Figure, **kwargs: Any) -> Any:
    """Render chart layanan dengan fallback width lintas versi Streamlit."""
    if _supports_parameter(st.plotly_chart, "width"):
        kwargs["width"] = "stretch"
    elif _supports_parameter(st.plotly_chart, "use_container_width"):
        kwargs["use_container_width"] = True
    return st.plotly_chart(figure, **kwargs)


def _service_dataframe(data: pd.DataFrame, **kwargs: Any) -> Any:
    """Render tabel fallback dengan lebar kompatibel lintas versi Streamlit."""
    if _supports_parameter(st.dataframe, "width"):
        kwargs["width"] = "stretch"
    elif _supports_parameter(st.dataframe, "use_container_width"):
        kwargs["use_container_width"] = True
    return st.dataframe(data, **kwargs)

def _is_dark_mode() -> bool:
    """Ambil status tema dari session state secara aman."""
    try:
        return bool(st.session_state.get("dark_mode", True))
    except Exception:
        return True


def _chart_text_color() -> str:
    """Tentukan warna teks chart agar terbaca pada kedua tema."""
    return "#FFFFFF" if _is_dark_mode() else "#1F2937"


def _inject_home_css() -> None:
    """Sisipkan CSS khusus halaman Beranda dengan prefix home-v5-."""
    try:
        st.markdown(
            """
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');

                .home-v5-page {
                    color: var(--app-text);
                    padding-top: 0.35rem;
                }

                .home-v5-hero {
                    background:
                        radial-gradient(circle at 92% 10%, rgba(255, 255, 255, 0.14), transparent 32%),
                        linear-gradient(135deg, #B71C1C 0%, #E53935 54%, #F05A56 100%);
                    border: 1px solid rgba(255, 255, 255, 0.10);
                    border-radius: 12px;
                    box-shadow: 0 12px 30px rgba(183, 28, 28, 0.20);
                    box-sizing: border-box;
                    color: #FFFFFF;
                    margin: 0 0 1.5rem 0;
                    overflow: hidden;
                    padding: 2rem;
                    position: relative;
                    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.22);
                }

                .home-v5-hero::before {
                    background: linear-gradient(90deg, rgba(255,255,255,0.22), rgba(255,255,255,0));
                    content: '';
                    height: 1px;
                    left: 0;
                    position: absolute;
                    right: 0;
                    top: 0;
                }

                .home-v5-hero::after {
                    background: radial-gradient(circle, rgba(255,255,255,0.16), transparent 68%);
                    content: '';
                    height: 240px;
                    pointer-events: none;
                    position: absolute;
                    right: -72px;
                    top: -110px;
                    width: 240px;
                }

                .home-v5-hero h1 {
                    align-items: center;
                    color: #FFFFFF !important;
                    display: flex;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.55rem, 2.6vw, 1.95rem);
                    font-weight: 800;
                    gap: 0.65rem;
                    line-height: 1.2;
                    margin: 0;
                    position: relative;
                    z-index: 1;
                }

                .home-v5-hero p {
                    color: rgba(255, 255, 255, 0.94) !important;
                    font-family: 'Inter', sans-serif;
                    font-size: 1rem;
                    font-weight: 500;
                    margin: 0.75rem 0 1rem 0;
                    position: relative;
                    z-index: 1;
                }

                .home-v5-badges,
                .home-v5-source-row {
                    display: flex;
                    flex-wrap: wrap;
                    align-items: center;
                    gap: 0.5rem;
                }

                .home-v5-badge {
                    border-radius: 999px;
                    color: #FFFFFF;
                    display: inline-flex;
                    align-items: center;
                    gap: 0.3rem;
                    font-size: 0.72rem;
                    font-weight: 700;
                    letter-spacing: 0.02em;
                    line-height: 1;
                    padding: 0.42rem 0.68rem;
                    white-space: nowrap;
                }

                .home-v5-badge-active { background: #4CAF50; }
                .home-v5-badge-soon { background: #424242; }
                .home-v5-badge-real { background: rgba(76, 175, 80, 0.18); color: #4CAF50; border: 1px solid rgba(76, 175, 80, 0.45); }
                .home-v5-badge-dummy { background: rgba(255, 152, 0, 0.18); color: #FF9800; border: 1px solid rgba(255, 152, 0, 0.45); }

                .home-v5-hero .home-v5-badges,
                .home-v5-hero .home-v5-source-row {
                    position: relative;
                    z-index: 1;
                }

                .home-v5-hero .home-v5-badge {
                    backdrop-filter: blur(8px);
                    border: 1px solid rgba(255, 255, 255, 0.22);
                    box-shadow: 0 5px 14px rgba(95, 10, 10, 0.18);
                    color: #FFFFFF !important;
                    text-shadow: none;
                }

                .home-v5-hero .home-v5-badge-active {
                    background: rgba(76, 175, 80, 0.92);
                }

                .home-v5-hero .home-v5-badge-soon {
                    background: rgba(24, 24, 27, 0.38);
                }

                .home-v5-hero .home-v5-badge-real {
                    background: rgba(16, 73, 37, 0.42);
                    border-color: rgba(187, 247, 208, 0.28);
                }

                .home-v5-hero .home-v5-badge-dummy {
                    background: rgba(120, 53, 15, 0.42);
                    border-color: rgba(253, 186, 116, 0.34);
                }

                .home-v5-section-title {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1.05rem;
                    font-weight: 700;
                    margin: 1.2rem 0 0.75rem 0;
                }

                /*
                 * Ringkasan utama dirender sebagai satu CSS Grid agar lima kartu
                 * selalu memiliki lebar dan tinggi yang sama pada satu baris.
                 * Isi kartu memakai flex-column sehingga keterangan bawah sejajar.
                 */
                .home-v5-metric-grid {
                    align-items: stretch;
                    display: grid;
                    gap: 0.9rem;
                    grid-template-columns: repeat(5, minmax(0, 1fr));
                    margin: 0;
                    width: 100%;
                }

                .home-v5-metric-card {
                    background:
                        radial-gradient(circle at 92% 5%, rgba(229, 57, 53, 0.08), transparent 31%),
                        var(--app-card);
                    border: 1px solid var(--app-border);
                    border-left: 3px solid var(--app-primary);
                    border-radius: 12px;
                    box-sizing: border-box;
                    display: flex;
                    flex-direction: column;
                    height: 100%;
                    min-height: 232px;
                    min-width: 0;
                    overflow: hidden;
                    padding: 1.05rem 1.08rem;
                    position: relative;
                    transition: box-shadow 0.2s ease, transform 0.2s ease, border-color 0.2s ease;
                    width: 100%;
                }

                .home-v5-metric-card:hover {
                    border-color: rgba(229, 57, 53, 0.68);
                    box-shadow: 0 18px 34px rgba(0, 0, 0, 0.18), 0 0 22px rgba(229, 57, 53, 0.16);
                    transform: translateY(-3px);
                }

                .home-v5-metric-label {
                    align-items: flex-start;
                    color: var(--app-muted);
                    display: flex;
                    font-size: 0.8rem;
                    font-weight: 700;
                    line-height: 1.38;
                    margin: 0;
                    min-height: 2.25rem;
                    width: 100%;
                }

                .home-v5-metric-value-wrap {
                    align-items: flex-start;
                    display: flex;
                    flex: 1 1 auto;
                    min-height: 0;
                    padding: 0.48rem 0 0.68rem;
                    width: 100%;
                }

                .home-v5-metric-value {
                    color: var(--home-v5-value-color, var(--app-text));
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.52rem, 1.95vw, 2.05rem) !important;
                    font-weight: 800;
                    letter-spacing: -0.035em;
                    line-height: 1.12;
                    max-width: 100%;
                    overflow-wrap: anywhere;
                    white-space: normal;
                    word-break: normal;
                }

                .home-v5-metric-card--platform .home-v5-metric-value {
                    font-size: clamp(1.24rem, 1.52vw, 1.62rem) !important;
                    letter-spacing: -0.03em;
                    white-space: nowrap;
                    line-height: 1.12;
                }

                /*
                 * Rentang tanggal memakai dua baris pendek. Ukurannya dikunci
                 * dengan !important agar tidak ditimpa CSS global proyek.
                 */
                .home-v5-metric-card--date .home-v5-metric-value-wrap {
                    align-items: center;
                    padding: 0.22rem 0 0.68rem;
                }

                .home-v5-metric-card--date .home-v5-metric-value {
                    align-items: flex-start;
                    display: flex;
                    flex-direction: column;
                    font-size: 1rem !important;
                    gap: 0.16rem;
                    justify-content: center;
                    letter-spacing: 0;
                    line-height: 1.08;
                    max-width: 100%;
                    overflow: hidden;
                    width: 100%;
                }

                .home-v5-metric-date-line {
                    align-items: baseline;
                    display: flex;
                    flex-wrap: nowrap;
                    gap: 0.3rem;
                    max-width: 100%;
                    min-width: 0;
                    white-space: nowrap;
                }

                .home-v5-metric-date-main {
                    display: inline-block;
                    font-size: clamp(1.02rem, 1.18vw, 1.2rem) !important;
                    font-weight: 800;
                    letter-spacing: -0.025em;
                    line-height: 1.08;
                    min-width: 0;
                }

                .home-v5-metric-date-year {
                    display: inline-block;
                    font-size: clamp(0.78rem, 0.86vw, 0.88rem) !important;
                    font-weight: 700;
                    letter-spacing: 0;
                    line-height: 1.08;
                    min-width: 0;
                    opacity: 0.82;
                }

                .home-v5-metric-date-separator {
                    display: block;
                    font-size: 0.82rem !important;
                    font-weight: 700;
                    line-height: 1;
                    opacity: 0.58;
                }

                .home-v5-metric-subtext {
                    color: var(--app-muted);
                    font-size: 0.77rem;
                    line-height: 1.42;
                    margin-top: auto;
                    min-height: 2.25rem;
                    width: 100%;
                }

                .home-v5-service-section-head {
                    align-items: flex-end;
                    display: flex;
                    gap: 1rem;
                    justify-content: space-between;
                    margin: 1.35rem 0 0.8rem 0;
                }

                .home-v5-service-section-kicker {
                    align-items: center;
                    color: var(--app-primary);
                    display: inline-flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.68rem;
                    font-weight: 800;
                    gap: 0.38rem;
                    letter-spacing: 0.11em;
                    margin-bottom: 0.28rem;
                    text-transform: uppercase;
                }

                .home-v5-service-section-kicker::before {
                    background: var(--app-primary);
                    border-radius: 999px;
                    content: '';
                    height: 6px;
                    width: 6px;
                }

                .home-v5-service-section-title {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.2rem, 2vw, 1.45rem);
                    font-weight: 800;
                    letter-spacing: -0.03em;
                    line-height: 1.2;
                    margin: 0;
                }

                .home-v5-service-section-copy {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.77rem;
                    line-height: 1.45;
                    max-width: 360px;
                    text-align: right;
                }

                /*
                 * Layout Status Layanan memakai satu baris flex yang meregangkan
                 * tiga kolom. Hanya wrapper kartu dan blok vertikal utamanya yang
                 * menjadi flex. Chart, metric card, dan elemen turunan lain tetap
                 * memakai alur normal agar tidak saling menimpa.
                 */
                div[data-testid="stHorizontalBlock"]:has(.home-v5-service-card-marker) {
                    align-items: stretch !important;
                }

                div[data-testid="stHorizontalBlock"]:has(.home-v5-service-card-marker)
                    > div[data-testid="stColumn"] {
                    align-self: stretch !important;
                    display: flex !important;
                    flex-direction: column !important;
                }

                div[data-testid="stHorizontalBlock"]:has(.home-v5-service-card-marker)
                    > div[data-testid="stColumn"]
                    > div[data-testid="stVerticalBlockBorderWrapper"] {
                    flex: 1 1 auto !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card-marker) {
                    background:
                        radial-gradient(circle at 92% 4%, rgba(229, 57, 53, 0.10), transparent 28%),
                        linear-gradient(155deg, color-mix(in srgb, var(--app-card) 96%, white 4%), var(--app-card));
                    border: 1px solid var(--app-border) !important;
                    border-radius: 18px !important;
                    box-shadow: 0 16px 38px rgba(0, 0, 0, 0.12);
                    display: flex !important;
                    flex: 1 1 auto !important;
                    flex-direction: column !important;
                    min-height: 0;
                    overflow: hidden;
                    padding: 1rem !important;
                    position: relative;
                    transition: border-color 0.22s ease, box-shadow 0.22s ease, transform 0.22s ease;
                    width: 100%;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card-marker)::before {
                    background: linear-gradient(90deg, var(--home-v5-service-accent, #E53935), transparent 72%);
                    content: '';
                    height: 3px;
                    left: 0;
                    position: absolute;
                    right: 0;
                    top: 0;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card-marker):hover {
                    border-color: color-mix(in srgb, var(--home-v5-service-accent, #E53935) 50%, var(--app-border)) !important;
                    box-shadow: 0 20px 48px rgba(0, 0, 0, 0.18), 0 0 0 1px color-mix(in srgb, var(--home-v5-service-accent, #E53935) 16%, transparent);
                    transform: translateY(-3px);
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card--indihome) {
                    --home-v5-service-accent: #E53935;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card--indibiz) {
                    --home-v5-service-accent: #EF8354;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card--telkomsel) {
                    --home-v5-service-accent: #D71920;
                }

                .home-v5-service-card-marker {
                    display: none;
                }

                /* Blok vertikal utama membagi kartu menjadi body dan footer. */
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card-marker)
                    > div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .home-v5-service-card-marker) {
                    display: flex !important;
                    flex: 1 1 auto !important;
                    flex-direction: column !important;
                    min-height: 0 !important;
                    width: 100% !important;
                }

                .home-v5-service-head {
                    align-items: flex-start;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.72rem;
                    justify-content: space-between;
                    margin-bottom: 0.82rem;
                    min-width: 0;
                }

                .home-v5-service-head--stacked {
                    justify-content: flex-start;
                }

                .home-v5-service-identity {
                    align-items: center;
                    display: flex;
                    flex: 1 1 180px;
                    gap: 0.7rem;
                    min-width: 0;
                }

                .home-v5-service-copy-block {
                    flex: 1 1 auto;
                    min-width: 0;
                }

                .home-v5-service-logo {
                    align-items: center;
                    background: color-mix(in srgb, var(--home-v5-logo-color, #E53935) 13%, transparent);
                    border: 1px solid color-mix(in srgb, var(--home-v5-logo-color, #E53935) 32%, transparent);
                    border-radius: 13px;
                    color: var(--home-v5-logo-color, #E53935);
                    display: inline-flex;
                    flex: 0 0 auto;
                    height: 44px;
                    justify-content: center;
                    width: 44px;
                }

                .home-v5-service-logo svg {
                    height: 22px;
                    width: 22px;
                }

                .home-v5-service-name {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1rem;
                    font-weight: 800;
                    letter-spacing: -0.02em;
                    line-height: 1.2;
                }

                .home-v5-service-type {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.69rem;
                    line-height: 1.35;
                    margin-top: 0.14rem;
                }

                .home-v5-service-status {
                    align-items: center;
                    border-radius: 999px;
                    box-sizing: border-box;
                    display: inline-flex;
                    flex: 0 0 auto;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.62rem;
                    font-weight: 800;
                    gap: 0.34rem;
                    letter-spacing: 0.035em;
                    line-height: 1;
                    max-width: 100%;
                    padding: 0.42rem 0.62rem;
                    text-transform: uppercase;
                    white-space: nowrap;
                }

                .home-v5-service-status--inline {
                    margin-top: 0.48rem;
                    width: fit-content;
                }

                .home-v5-service-status::before {
                    border-radius: 999px;
                    content: '';
                    height: 6px;
                    width: 6px;
                }

                .home-v5-service-status--active {
                    background: rgba(76, 175, 80, 0.13);
                    border: 1px solid rgba(76, 175, 80, 0.38);
                    color: #62CF68;
                }

                .home-v5-service-status--active::before {
                    background: #4CAF50;
                    box-shadow: 0 0 0 4px rgba(76, 175, 80, 0.12);
                }

                .home-v5-service-status--soon {
                    background: color-mix(in srgb, var(--app-muted) 11%, transparent);
                    border: 1px solid color-mix(in srgb, var(--app-muted) 26%, transparent);
                    color: var(--app-muted);
                }

                .home-v5-service-status--soon::before {
                    background: var(--app-muted);
                }

                .home-v5-service-summary {
                    --home-v5-hover-accent: #E53935;
                    align-items: center;
                    background: color-mix(in srgb, var(--app-secondary) 76%, transparent);
                    border: 1px solid var(--app-border);
                    border-radius: 12px;
                    color: var(--app-muted);
                    display: flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.72rem;
                    gap: 0.5rem;
                    justify-content: space-between;
                    margin-bottom: 0.72rem;
                    overflow: hidden;
                    padding: 0.62rem 0.72rem;
                    position: relative;
                    transition: background 0.26s ease, border-color 0.26s ease, box-shadow 0.26s ease, transform 0.26s ease;
                    will-change: transform;
                }

                .home-v5-service-summary::after {
                    background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--home-v5-hover-accent) 72%, white 8%), transparent);
                    bottom: 0;
                    content: '';
                    height: 2px;
                    left: -35%;
                    opacity: 0;
                    position: absolute;
                    transition: left 0.38s ease, opacity 0.26s ease;
                    width: 58%;
                }

                .home-v5-service-summary:hover {
                    background: color-mix(in srgb, var(--app-secondary) 84%, var(--home-v5-hover-accent) 6%);
                    border-color: color-mix(in srgb, var(--home-v5-hover-accent) 52%, var(--app-border));
                    box-shadow:
                        0 12px 28px color-mix(in srgb, var(--home-v5-hover-accent) 17%, transparent),
                        0 0 0 1px color-mix(in srgb, var(--home-v5-hover-accent) 12%, transparent);
                    transform: translateY(-2px);
                }

                .home-v5-service-summary:hover::after {
                    left: 78%;
                    opacity: 1;
                }

                .home-v5-service-summary strong {
                    color: var(--app-text);
                    font-size: 0.72rem;
                    font-weight: 700;
                    transition: color 0.26s ease;
                }

                .home-v5-service-summary:hover strong {
                    color: color-mix(in srgb, var(--home-v5-hover-accent) 74%, var(--app-text));
                }

                .home-v5-service-stats {
                    display: grid;
                    gap: 0.58rem;
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                    margin: 0 0 0.72rem 0;
                }

                .home-v5-service-stat {
                    --home-v5-stat-accent: #E53935;
                    background: linear-gradient(145deg, color-mix(in srgb, var(--app-secondary) 90%, white 10%), var(--app-secondary));
                    border: 1px solid var(--app-border);
                    border-radius: 13px;
                    overflow: hidden;
                    padding: 0.72rem;
                    position: relative;
                    transition: background 0.26s ease, border-color 0.26s ease, box-shadow 0.26s ease, transform 0.26s ease;
                    will-change: transform;
                }

                .home-v5-service-stat::after {
                    background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--home-v5-stat-accent) 75%, white 8%), transparent);
                    content: '';
                    height: 2px;
                    left: -42%;
                    opacity: 0;
                    position: absolute;
                    right: auto;
                    top: 0;
                    transition: left 0.38s ease, opacity 0.26s ease;
                    width: 62%;
                }

                .home-v5-service-stat--data {
                    --home-v5-stat-accent: #42A5F5;
                }

                .home-v5-service-stat--influencer {
                    --home-v5-stat-accent: #FFB300;
                }

                .home-v5-service-stat:hover {
                    background: linear-gradient(
                        145deg,
                        color-mix(in srgb, var(--app-secondary) 87%, var(--home-v5-stat-accent) 13%),
                        color-mix(in srgb, var(--app-secondary) 95%, var(--home-v5-stat-accent) 5%)
                    );
                    border-color: color-mix(in srgb, var(--home-v5-stat-accent) 54%, var(--app-border));
                    box-shadow:
                        0 13px 30px color-mix(in srgb, var(--home-v5-stat-accent) 18%, transparent),
                        0 0 0 1px color-mix(in srgb, var(--home-v5-stat-accent) 12%, transparent);
                    transform: translateY(-3px);
                }

                .home-v5-service-stat:hover::after {
                    left: 76%;
                    opacity: 1;
                }

                .home-v5-service-stat-label {
                    align-items: center;
                    color: var(--app-muted);
                    display: flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.67rem;
                    gap: 0.34rem;
                    margin-bottom: 0.34rem;
                }

                .home-v5-service-stat-label svg {
                    height: 13px;
                    width: 13px;
                }

                .home-v5-service-stat strong {
                    color: var(--app-text);
                    display: block;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1.05rem;
                    font-variant-numeric: tabular-nums;
                    font-weight: 800;
                    letter-spacing: -0.03em;
                    line-height: 1.15;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card--indihome) div[data-testid="stPlotlyChart"] {
                    background: color-mix(in srgb, var(--app-secondary) 56%, transparent);
                    border: 1px solid var(--app-border);
                    border-radius: 14px;
                    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
                    overflow: hidden;
                    position: relative;
                    transition: background 0.28s ease, border-color 0.28s ease, box-shadow 0.28s ease, transform 0.28s ease;
                    will-change: transform;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card--indihome) div[data-testid="stPlotlyChart"]:hover {
                    background: color-mix(in srgb, var(--app-secondary) 86%, #E53935 5%);
                    border-color: color-mix(in srgb, #E53935 48%, var(--app-border));
                    box-shadow:
                        0 16px 36px rgba(229, 57, 53, 0.18),
                        0 0 0 1px rgba(229, 57, 53, 0.12);
                    transform: translateY(-3px);
                }

                /*
                 * Plotly fullscreen memakai lapisan tersendiri. Pastikan seluruh
                 * kanvas tetap mengikuti tema agar tidak berkedip putih saat resize.
                 */
                div[data-testid="stPlotlyChart"],
                div[data-testid="stPlotlyChart"] > div,
                div[data-testid="stPlotlyChart"] .js-plotly-plot,
                div[data-testid="stPlotlyChart"] .plot-container,
                div[data-testid="stPlotlyChart"] .svg-container {
                    background: var(--app-card) !important;
                }

                div[data-testid="stPlotlyChart"]:fullscreen,
                div[data-testid="stPlotlyChart"]:fullscreen > div,
                div[data-testid="stPlotlyChart"]:fullscreen .js-plotly-plot,
                div[data-testid="stPlotlyChart"]:fullscreen .plot-container,
                div[data-testid="stPlotlyChart"]:fullscreen .svg-container,
                div[data-testid="stFullScreenFrame"],
                div[data-testid="stFullScreenFrame"] > div {
                    background: var(--app-card) !important;
                }

                div[data-testid="stPlotlyChart"] .modebar {
                    background: color-mix(in srgb, var(--app-card) 88%, transparent) !important;
                    border-radius: 8px !important;
                    padding: 2px 4px !important;
                }

                .home-v5-service-chart-title {
                    align-items: flex-start;
                    color: var(--app-text);
                    display: flex;
                    flex-direction: column;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.80rem;
                    font-weight: 750;
                    gap: 0.16rem;
                    justify-content: center;
                    line-height: 1.28;
                    margin: 0.08rem 0 0 0;
                    min-height: 64px;
                }

                .home-v5-service-chart-title span {
                    color: var(--app-muted);
                    display: block;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.64rem;
                    font-weight: 500;
                    line-height: 1.2;
                }

                .home-v5-chart-control-copy {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.62rem;
                    line-height: 1.45;
                    margin: -0.15rem 0 0.35rem 0;
                }

                /*
                 * Tooltip bantuan tombol Streamlit.
                 * Streamlit merender tooltip pada portal di luar wrapper tombol,
                 * sehingga warna perlu diatur langsung pada elemen tooltip.
                 */
                div[data-testid="stTooltipContent"],
                div[data-baseweb="tooltip"],
                div[role="tooltip"] {
                    background: #161D2A !important;
                    border: 1px solid rgba(229, 57, 53, 0.38) !important;
                    border-radius: 10px !important;
                    box-shadow:
                        0 14px 34px rgba(0, 0, 0, 0.38),
                        0 0 0 1px rgba(229, 57, 53, 0.06) !important;
                    color: #F7F8FC !important;
                    font-family: 'Inter', sans-serif !important;
                    font-size: 0.72rem !important;
                    line-height: 1.45 !important;
                    max-width: min(320px, calc(100vw - 28px)) !important;
                }

                div[data-testid="stTooltipContent"] > div,
                div[data-baseweb="tooltip"] > div,
                div[role="tooltip"] > div {
                    background: #161D2A !important;
                    border-radius: 10px !important;
                }

                div[data-testid="stTooltipContent"] *,
                div[data-baseweb="tooltip"] *,
                div[role="tooltip"] * {
                    color: #F7F8FC !important;
                    font-family: 'Inter', sans-serif !important;
                    opacity: 1 !important;
                    text-shadow: none !important;
                }

                /* Tombol kontrol donut: dua baris stabil, netral saat diam, berwarna saat hover. */
                .st-key-home_v5_toggle_donut_size {
                    align-items: center;
                    display: flex;
                    justify-content: flex-end;
                    min-height: 64px;
                    width: 100%;
                }

                .st-key-home_v5_toggle_donut_size button,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card--indihome)
                    div[data-testid="stButton"] > button[kind="secondary"],
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card--indihome)
                    div[data-testid="stButton"] > button[data-testid="stBaseButton-secondary"] {
                    align-items: center !important;
                    background: color-mix(in srgb, var(--app-secondary) 48%, transparent) !important;
                    border: 1px solid color-mix(in srgb, var(--app-border) 88%, #E53935 12%) !important;
                    border-radius: 12px !important;
                    box-shadow: none !important;
                    color: var(--app-muted) !important;
                    display: inline-flex !important;
                    font-family: 'Inter', sans-serif !important;
                    font-size: 0.70rem !important;
                    font-weight: 700 !important;
                    justify-content: center !important;
                    line-height: 1.30 !important;
                    margin-left: auto !important;
                    min-height: 64px !important;
                    min-width: 112px !important;
                    max-width: 124px !important;
                    padding: 0.56rem 0.72rem !important;
                    text-align: center !important;
                    transition:
                        background 0.22s ease,
                        border-color 0.22s ease,
                        box-shadow 0.22s ease,
                        color 0.22s ease,
                        transform 0.22s ease !important;
                    width: 100% !important;
                }

                .st-key-home_v5_toggle_donut_size button > div,
                .st-key-home_v5_toggle_donut_size button p,
                .st-key-home_v5_toggle_donut_size button span,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card--indihome)
                    div[data-testid="stButton"] > button p,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card--indihome)
                    div[data-testid="stButton"] > button span {
                    color: inherit !important;
                    hyphens: none !important;
                    line-height: 1.30 !important;
                    margin: 0 !important;
                    max-width: none !important;
                    text-align: center !important;
                    white-space: pre !important;
                    word-break: normal !important;
                    overflow-wrap: normal !important;
                    width: 100% !important;
                }

                .st-key-home_v5_toggle_donut_size button:hover,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card--indihome)
                    div[data-testid="stButton"] > button[kind="secondary"]:hover,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card--indihome)
                    div[data-testid="stButton"] > button[data-testid="stBaseButton-secondary"]:hover {
                    background: linear-gradient(
                        135deg,
                        color-mix(in srgb, #E53935 18%, var(--app-secondary)),
                        color-mix(in srgb, #42A5F5 11%, var(--app-secondary))
                    ) !important;
                    border-color: rgba(229, 57, 53, 0.72) !important;
                    box-shadow:
                        0 9px 24px rgba(229, 57, 53, 0.18),
                        0 0 0 1px rgba(229, 57, 53, 0.08) !important;
                    color: var(--app-text) !important;
                    transform: translateY(-2px);
                }

                .st-key-home_v5_toggle_donut_size button:active,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card--indihome)
                    div[data-testid="stButton"] > button[kind="secondary"]:active,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card--indihome)
                    div[data-testid="stButton"] > button[data-testid="stBaseButton-secondary"]:active {
                    box-shadow: 0 4px 12px rgba(229, 57, 53, 0.12) !important;
                    transform: translateY(0) scale(0.98);
                }

                .st-key-home_v5_toggle_donut_size button:focus-visible,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card--indihome)
                    div[data-testid="stButton"] > button[kind="secondary"]:focus-visible,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card--indihome)
                    div[data-testid="stButton"] > button[data-testid="stBaseButton-secondary"]:focus-visible {
                    border-color: rgba(229, 57, 53, 0.82) !important;
                    box-shadow: 0 0 0 3px rgba(229, 57, 53, 0.16) !important;
                    outline: none !important;
                }

                .home-v5-sentiment-legend {
                    display: grid;
                    gap: 0.46rem;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    margin: 0.50rem 0 0.78rem 0;
                    width: 100%;
                }

                .home-v5-sentiment-item {
                    align-items: center;
                    background: linear-gradient(
                        145deg,
                        color-mix(in srgb, var(--app-secondary) 90%, white 4%),
                        color-mix(in srgb, var(--app-secondary) 98%, transparent)
                    );
                    border: 1px solid var(--app-border);
                    border-radius: 11px;
                    box-sizing: border-box;
                    display: flex;
                    gap: 0.46rem;
                    min-height: 64px;
                    min-width: 0;
                    overflow: hidden;
                    padding: 0.52rem 0.48rem;
                }

                .home-v5-sentiment-dot {
                    aspect-ratio: 1 / 1;
                    background: var(--home-v5-dot-color);
                    border-radius: 50%;
                    box-shadow: 0 0 0 3px color-mix(in srgb, var(--home-v5-dot-color) 16%, transparent);
                    flex: 0 0 10px;
                    height: 10px;
                    min-height: 10px;
                    min-width: 10px;
                    width: 10px;
                }

                .home-v5-sentiment-text {
                    display: flex;
                    flex-direction: column;
                    gap: 0.12rem;
                    min-width: 0;
                }

                .home-v5-sentiment-item span:not(.home-v5-sentiment-dot) {
                    color: var(--app-text);
                    display: block;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.62rem;
                    font-weight: 700;
                    line-height: 1.18;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }

                .home-v5-sentiment-item strong {
                    color: var(--app-muted);
                    display: block;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.68rem;
                    font-variant-numeric: tabular-nums;
                    font-weight: 700;
                    line-height: 1.18;
                    white-space: nowrap;
                }

                .home-v5-coming-panel {
                    align-items: center;
                    background:
                        radial-gradient(circle at 50% 0%, color-mix(in srgb, var(--home-v5-service-accent) 13%, transparent), transparent 45%),
                        color-mix(in srgb, var(--app-secondary) 58%, transparent);
                    border: 1px dashed color-mix(in srgb, var(--app-muted) 30%, transparent);
                    border-radius: 15px;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    min-height: 292px;
                    padding: 1rem;
                    text-align: center;
                }

                .home-v5-coming-icon {
                    align-items: center;
                    background: color-mix(in srgb, var(--home-v5-service-accent) 13%, transparent);
                    border: 1px solid color-mix(in srgb, var(--home-v5-service-accent) 28%, transparent);
                    border-radius: 18px;
                    color: var(--home-v5-service-accent);
                    display: flex;
                    height: 58px;
                    justify-content: center;
                    margin-bottom: 0.82rem;
                    width: 58px;
                }

                .home-v5-coming-icon svg {
                    height: 27px;
                    width: 27px;
                }

                .home-v5-coming-title {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.9rem;
                    font-weight: 800;
                    line-height: 1.35;
                    margin-bottom: 0.36rem;
                }

                .home-v5-service-copy {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.72rem;
                    line-height: 1.55;
                    max-width: 245px;
                }

                .home-v5-coming-features {
                    display: grid;
                    gap: 0.42rem;
                    grid-template-columns: 1fr;
                    margin: 0.7rem 0 0.78rem 0;
                }

                .home-v5-coming-feature {
                    align-items: center;
                    background: color-mix(in srgb, var(--app-secondary) 70%, transparent);
                    border: 1px solid var(--app-border);
                    border-radius: 10px;
                    color: var(--app-muted);
                    display: flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.66rem;
                    gap: 0.46rem;
                    padding: 0.48rem 0.58rem;
                }

                .home-v5-coming-feature svg {
                    color: var(--home-v5-service-accent);
                    flex: 0 0 auto;
                    height: 14px;
                    width: 14px;
                }

                .home-v5-coming-roadmap {
                    align-items: center;
                    color: var(--app-muted);
                    display: flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.62rem;
                    gap: 0.42rem;
                    margin: 0.15rem 0 0.72rem 0;
                }

                .home-v5-coming-roadmap::before {
                    background: var(--home-v5-service-accent);
                    border-radius: 999px;
                    content: '';
                    height: 5px;
                    width: 5px;
                }

                /*
                 * Dorong CTA terakhir ke dasar card memakai margin-top:auto.
                 * Anchor tidak diberi tinggi agar tidak menciptakan ruang berbeda
                 * pada IndiHome, IndiBiz, dan Telkomsel.
                 */
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card-marker)
                    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .home-v5-service-card-marker)
                    > div[data-testid="stElementContainer"]:has(.home-v5-service-footer-anchor) {
                    flex: 0 0 0 !important;
                    height: 0 !important;
                    margin: auto 0 0 0 !important;
                    min-height: 0 !important;
                    overflow: hidden !important;
                    padding: 0 !important;
                }

                .home-v5-service-footer-anchor {
                    display: block;
                    height: 0;
                    min-height: 0;
                    width: 100%;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card-marker)
                    div[data-testid="stElementContainer"]:has(.stButton) {
                    display: flex !important;
                    justify-content: center !important;
                    width: 100% !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card-marker) .stButton {
                    display: flex;
                    justify-content: center;
                    margin-top: 0 !important;
                    padding-top: 0.42rem;
                    width: 100%;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card-marker) .stButton button {
                    border-radius: 11px;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.74rem;
                    font-weight: 750;
                    min-height: 42px;
                    margin-left: auto !important;
                    margin-right: auto !important;
                    width: 100% !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card--indihome) .stButton button {
                    background: linear-gradient(120deg, #B71C1C, #E53935, #F05A56);
                    border: 0;
                    box-shadow: 0 9px 22px rgba(229, 57, 53, 0.22);
                    color: #FFFFFF;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card--indihome) .stButton button:hover {
                    box-shadow: 0 12px 28px rgba(229, 57, 53, 0.31);
                    transform: translateY(-1px);
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card-marker) .stButton button:disabled {
                    background: color-mix(in srgb, var(--app-secondary) 88%, transparent);
                    border: 1px solid var(--app-border);
                    color: var(--app-muted);
                    opacity: 0.72;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card-marker) .stButton button p,
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card-marker) .stButton button span {
                    text-align: center !important;
                }

                .home-v5-overview-chart-head {
                    align-items: center;
                    display: flex;
                    gap: 0.75rem;
                    justify-content: space-between;
                    margin-bottom: 0.55rem;
                }

                .home-v5-overview-chart-head .home-v5-card-title {
                    margin-bottom: 0;
                }

                .st-key-home_v5_toggle_platform_chart_size button {
                    align-items: center !important;
                    background: color-mix(in srgb, var(--app-secondary) 64%, transparent) !important;
                    border: 1px solid color-mix(in srgb, var(--app-border) 84%, #E53935 16%) !important;
                    border-radius: 11px !important;
                    box-shadow: none !important;
                    color: var(--app-muted) !important;
                    display: inline-flex !important;
                    font-family: 'Inter', sans-serif !important;
                    font-size: 0.70rem !important;
                    font-weight: 700 !important;
                    justify-content: center !important;
                    line-height: 1.25 !important;
                    min-height: 38px !important;
                    min-width: 112px !important;
                    padding: 0.45rem 0.72rem !important;
                    text-align: center !important;
                    transition: background 0.22s ease, border-color 0.22s ease, box-shadow 0.22s ease, color 0.22s ease, transform 0.22s ease !important;
                    white-space: normal !important;
                }

                .st-key-home_v5_toggle_platform_chart_size button:hover {
                    background: linear-gradient(135deg, rgba(229, 57, 53, 0.18), rgba(66, 165, 245, 0.12)) !important;
                    border-color: rgba(229, 57, 53, 0.72) !important;
                    box-shadow: 0 10px 24px rgba(229, 57, 53, 0.16) !important;
                    color: var(--app-text) !important;
                    transform: translateY(-2px);
                }

                .st-key-home_v5_toggle_platform_chart_size button p,
                .st-key-home_v5_toggle_platform_chart_size button span {
                    color: inherit !important;
                    line-height: 1.25 !important;
                    margin: 0 !important;
                    text-align: center !important;
                }

                .home-v5-platform-chart-note {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.68rem;
                    line-height: 1.45;
                    margin: 0.2rem 0 0.55rem 0;
                }

                @keyframes homeV5PlatformGlowFlow {
                    0% { transform: translate3d(-14%, -6%, 0) rotate(0deg); opacity: 0.45; }
                    50% { transform: translate3d(8%, 4%, 0) rotate(7deg); opacity: 0.9; }
                    100% { transform: translate3d(-14%, -6%, 0) rotate(0deg); opacity: 0.45; }
                }

                @keyframes homeV5PlatformChipFloat {
                    0%, 100% { transform: translateY(0); }
                    50% { transform: translateY(-4px); }
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-platform-shell-marker) {
                    background:
                        radial-gradient(circle at 88% 12%, rgba(66, 165, 245, 0.18), transparent 24%),
                        radial-gradient(circle at 18% 0%, rgba(229, 57, 53, 0.15), transparent 20%),
                        linear-gradient(135deg, rgba(17, 24, 39, 0.96), rgba(10, 18, 38, 0.98));
                    border: 1px solid rgba(66, 165, 245, 0.28) !important;
                    border-radius: 20px !important;
                    box-shadow: 0 18px 36px rgba(1, 8, 23, 0.32), inset 0 1px 0 rgba(255,255,255,0.03);
                    overflow: hidden;
                    position: relative;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-platform-shell-marker)::before {
                    animation: homeV5PlatformGlowFlow 11s ease-in-out infinite;
                    background: linear-gradient(115deg, rgba(229, 57, 53, 0.12), rgba(255, 152, 0, 0.10), rgba(66, 165, 245, 0.14));
                    content: '';
                    filter: blur(20px);
                    inset: -22% -8% auto auto;
                    height: 220px;
                    pointer-events: none;
                    position: absolute;
                    width: 340px;
                    z-index: 0;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-platform-shell-marker):hover {
                    border-color: rgba(66, 165, 245, 0.42) !important;
                    box-shadow: 0 22px 46px rgba(1, 8, 23, 0.42), 0 0 0 1px rgba(66, 165, 245, 0.14) inset;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-platform-shell-marker)
                    > div[data-testid="stVerticalBlock"] {
                    gap: 0.45rem;
                    position: relative;
                    z-index: 1;
                }

                .home-v5-platform-shell-marker {
                    display: none;
                }

                .home-v5-platform-hero {
                    align-items: flex-start;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 1rem;
                    justify-content: space-between;
                    margin-bottom: 0.15rem;
                }

                .home-v5-platform-kicker {
                    align-items: center;
                    color: #F8BBD0;
                    display: inline-flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.7rem;
                    font-weight: 800;
                    gap: 0.4rem;
                    letter-spacing: 0.22em;
                    margin-bottom: 0.55rem;
                    text-transform: uppercase;
                }

                .home-v5-platform-kicker::before {
                    background: linear-gradient(135deg, #E53935, #42A5F5);
                    border-radius: 999px;
                    box-shadow: 0 0 0 5px rgba(229, 57, 53, 0.12);
                    content: '';
                    display: inline-block;
                    height: 10px;
                    width: 10px;
                }

                .home-v5-platform-hero-title {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.15rem, 2vw, 1.42rem);
                    font-weight: 800;
                    line-height: 1.15;
                    margin: 0;
                }

                .home-v5-platform-hero-copy {
                    color: rgba(229, 231, 235, 0.82);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.86rem;
                    line-height: 1.6;
                    margin: 0.45rem 0 0 0;
                    max-width: 44rem;
                }

                .home-v5-platform-highlights {
                    display: grid;
                    gap: 0.72rem;
                    grid-template-columns: repeat(4, minmax(0, 1fr));
                    margin: 0.55rem 0 0.35rem;
                }

                .home-v5-platform-highlight-card {
                    align-items: center;
                    animation: homeV5PlatformChipFloat 7.5s ease-in-out infinite;
                    animation-delay: var(--home-v5-chip-delay, 0s);
                    background: linear-gradient(135deg, rgba(17, 24, 39, 0.76), rgba(30, 41, 59, 0.68));
                    border: 1px solid color-mix(in srgb, var(--home-v5-platform-color, #42A5F5) 48%, rgba(255,255,255,0.12));
                    border-radius: 16px;
                    box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
                    display: flex;
                    gap: 0.7rem;
                    min-height: 74px;
                    overflow: hidden;
                    padding: 0.78rem 0.88rem;
                    position: relative;
                    transition: transform 0.26s ease, box-shadow 0.26s ease, border-color 0.26s ease;
                }

                .home-v5-platform-highlight-card::after {
                    background: linear-gradient(135deg, color-mix(in srgb, var(--home-v5-platform-color, #42A5F5) 18%, transparent), transparent 68%);
                    content: '';
                    inset: 0;
                    pointer-events: none;
                    position: absolute;
                }

                .home-v5-platform-highlight-card:hover {
                    border-color: color-mix(in srgb, var(--home-v5-platform-color, #42A5F5) 88%, white 12%);
                    box-shadow: 0 14px 28px color-mix(in srgb, var(--home-v5-platform-color, #42A5F5) 16%, rgba(2,6,23,0.34));
                    transform: translateY(-3px);
                }

                .home-v5-platform-highlight-card--dominant {
                    background: linear-gradient(135deg, rgba(107, 15, 15, 0.42), rgba(30, 41, 59, 0.68));
                }

                .home-v5-platform-highlight-dot {
                    background: var(--home-v5-platform-color, #42A5F5);
                    border-radius: 50%;
                    box-shadow: 0 0 0 6px color-mix(in srgb, var(--home-v5-platform-color, #42A5F5) 16%, transparent);
                    flex: 0 0 12px;
                    height: 12px;
                    position: relative;
                    width: 12px;
                    z-index: 1;
                }

                .home-v5-platform-highlight-text {
                    display: grid;
                    gap: 0.12rem;
                    position: relative;
                    z-index: 1;
                }

                .home-v5-platform-highlight-text span {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.69rem;
                    font-weight: 600;
                    line-height: 1.35;
                }

                .home-v5-platform-highlight-text strong {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.92rem;
                    font-weight: 800;
                    line-height: 1.25;
                }

                .home-v5-platform-toolbar {
                    align-items: center;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.55rem;
                    margin: 0.1rem 0 0.2rem;
                }

                .home-v5-platform-toolbar-badge {
                    align-items: center;
                    background: rgba(15, 23, 42, 0.72);
                    border: 1px solid rgba(148, 163, 184, 0.18);
                    border-radius: 999px;
                    color: rgba(226, 232, 240, 0.9);
                    display: inline-flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.69rem;
                    font-weight: 700;
                    gap: 0.42rem;
                    padding: 0.4rem 0.62rem;
                }

                .home-v5-platform-toolbar-badge::before {
                    background: var(--home-v5-platform-badge-accent, #42A5F5);
                    border-radius: 999px;
                    content: '';
                    display: inline-block;
                    height: 8px;
                    width: 8px;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-platform-shell-marker)
                    div[data-testid="stElementContainer"]:has(.stButton) {
                    display: flex;
                    justify-content: flex-end;
                }

                .st-key-home_v5_toggle_platform_chart_size button {
                    align-items: center !important;
                    background: linear-gradient(135deg, rgba(14, 24, 46, 0.92), rgba(27, 44, 82, 0.9)) !important;
                    border: 1px solid rgba(66, 165, 245, 0.45) !important;
                    border-radius: 14px !important;
                    box-shadow: 0 10px 24px rgba(30, 64, 175, 0.18) !important;
                    color: #F8FAFC !important;
                    display: inline-flex !important;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif !important;
                    font-size: 0.8rem !important;
                    font-weight: 800 !important;
                    justify-content: center !important;
                    letter-spacing: 0.01em !important;
                    line-height: 1.2 !important;
                    min-height: 44px !important;
                    min-width: 144px !important;
                    padding: 0.58rem 0.86rem !important;
                    text-align: center !important;
                    transition: transform 0.24s ease, box-shadow 0.24s ease, border-color 0.24s ease, background 0.24s ease !important;
                    white-space: normal !important;
                }

                .st-key-home_v5_toggle_platform_chart_size button:hover {
                    background: linear-gradient(135deg, rgba(30, 64, 175, 0.95), rgba(59, 130, 246, 0.92)) !important;
                    border-color: rgba(147, 197, 253, 0.82) !important;
                    box-shadow: 0 14px 30px rgba(30, 64, 175, 0.28) !important;
                    color: #FFFFFF !important;
                    transform: translateY(-2px);
                }

                .st-key-home_v5_toggle_platform_chart_size button p,
                .st-key-home_v5_toggle_platform_chart_size button span {
                    color: inherit !important;
                    line-height: 1.25 !important;
                    margin: 0 !important;
                    text-align: center !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-platform-shell-marker) [data-testid="stPlotlyChart"] {
                    background: linear-gradient(180deg, rgba(15, 23, 42, 0.86), rgba(11, 18, 32, 0.96));
                    border: 1px solid rgba(148, 163, 184, 0.14);
                    border-radius: 18px;
                    box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
                    overflow: hidden;
                    padding: 0.25rem 0.35rem 0.15rem;
                }

                @media (max-width: 1080px) {
                    .home-v5-platform-highlights {
                        grid-template-columns: repeat(2, minmax(0, 1fr));
                    }
                }

                @media (max-width: 640px) {
                    .home-v5-platform-hero {
                        gap: 0.7rem;
                    }

                    .home-v5-platform-highlights {
                        grid-template-columns: minmax(0, 1fr);
                    }
                }

                .home-v5-influencer-multiplatform-v42 {
                    display: none;
                }

                .home-v5-influencer-overview {
                    align-items: center;
                    background: color-mix(in srgb, var(--app-secondary) 72%, transparent);
                    border: 1px solid var(--app-border);
                    border-radius: 13px;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.55rem;
                    justify-content: space-between;
                    margin: 0 0 0.9rem 0;
                    padding: 0.72rem 0.82rem;
                }

                .home-v5-influencer-overview-copy {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.72rem;
                    line-height: 1.45;
                }

                .home-v5-influencer-overview-platforms {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.42rem;
                }

                .home-v5-influencer-overview-platform {
                    align-items: center;
                    background: color-mix(in srgb, var(--app-card) 86%, transparent);
                    border: 1px solid var(--app-border);
                    border-radius: 999px;
                    color: var(--app-text);
                    display: inline-flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.66rem;
                    font-weight: 700;
                    gap: 0.38rem;
                    padding: 0.35rem 0.56rem;
                    white-space: nowrap;
                }

                .home-v5-influencer-overview-platform::before {
                    background: var(--home-v5-platform-accent);
                    border-radius: 50%;
                    content: '';
                    height: 7px;
                    width: 7px;
                }

                .home-v5-platform-influencer-heading {
                    align-items: center;
                    display: flex;
                    gap: 0.65rem;
                    margin: 0.35rem 0 0.65rem 0;
                }

                .home-v5-platform-influencer-dot {
                    background: var(--home-v5-platform-accent, var(--app-primary));
                    border-radius: 50%;
                    box-shadow: 0 0 0 4px color-mix(in srgb, var(--home-v5-platform-accent, var(--app-primary)) 18%, transparent);
                    flex: 0 0 10px;
                    height: 10px;
                    width: 10px;
                }

                .home-v5-platform-influencer-heading strong {
                    color: var(--app-text);
                    display: block;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.9rem;
                    font-weight: 800;
                    line-height: 1.25;
                }

                .home-v5-platform-influencer-heading span:not(.home-v5-platform-influencer-dot) {
                    color: var(--app-muted);
                    display: block;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.66rem;
                    line-height: 1.35;
                    margin-top: 0.1rem;
                }

                .home-v5-platform-influencer-divider {
                    background: linear-gradient(90deg, transparent, var(--app-border), transparent);
                    height: 1px;
                    margin: 1.15rem 0;
                    width: 100%;
                }

                .home-v5-card-title {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1rem;
                    font-weight: 700;
                    margin-bottom: 0.45rem;
                }

                .home-v5-table-wrap {
                    border: 1px solid var(--app-border);
                    border-radius: 10px;
                    overflow-x: auto;
                    width: 100%;
                }

                .home-v5-table {
                    border-collapse: collapse;
                    min-width: 620px;
                    width: 100%;
                }

                .home-v5-table th {
                    background: var(--app-secondary);
                    border-bottom: 1px solid var(--app-border);
                    color: var(--app-text);
                    font-size: 0.76rem;
                    font-weight: 700;
                    padding: 0.72rem 0.65rem;
                    text-align: left;
                }

                .home-v5-table td {
                    border-bottom: 1px solid var(--app-border);
                    color: var(--app-text);
                    font-size: 0.78rem;
                    padding: 0.72rem 0.65rem;
                    vertical-align: middle;
                }

                .home-v5-table tbody tr:nth-child(even) {
                    background: color-mix(in srgb, var(--app-card) 88%, var(--app-text) 12%);
                }

                .home-v5-table tbody tr:nth-child(odd) {
                    background: var(--app-card);
                }

                .home-v5-table tbody tr:last-child td {
                    border-bottom: 0;
                }

                .home-v5-platform-pill {
                    background: var(--app-secondary);
                    border: 1px solid var(--app-border);
                    border-radius: 999px;
                    color: var(--app-text);
                    display: inline-block;
                    font-size: 0.69rem;
                    padding: 0.25rem 0.48rem;
                    white-space: nowrap;
                }

                .home-v5-influencer-panel {
                    background: color-mix(in srgb, var(--app-card) 96%, white 4%);
                    border: 1px solid var(--app-border);
                    border-radius: 14px;
                    margin-top: 0.45rem;
                    padding: 0.9rem;
                }

                .home-v5-influencer-meta {
                    align-items: center;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.55rem;
                    justify-content: space-between;
                    margin-bottom: 0.72rem;
                }

                .home-v5-influencer-rule {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.68rem;
                    line-height: 1.4;
                }

                .home-v5-category-pill {
                    border: 1px solid var(--app-border);
                    border-radius: 999px;
                    display: inline-flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.66rem;
                    font-weight: 700;
                    line-height: 1;
                    padding: 0.34rem 0.52rem;
                    white-space: nowrap;
                }

                .home-v5-category-pill--structural {
                    background: rgba(66, 165, 245, 0.13);
                    border-color: rgba(66, 165, 245, 0.34);
                    color: #64B5F6;
                }

                .home-v5-category-pill--reach {
                    background: rgba(255, 179, 0, 0.13);
                    border-color: rgba(255, 179, 0, 0.34);
                    color: #FFC247;
                }

                .home-v5-category-pill--participant {
                    background: color-mix(in srgb, var(--app-muted) 11%, transparent);
                    color: var(--app-muted);
                }

                div[data-testid="stTabs"] [data-baseweb="tab-list"] {
                    background: color-mix(in srgb, var(--app-secondary) 70%, transparent);
                    border: 1px solid var(--app-border);
                    border-radius: 12px;
                    gap: 0.35rem;
                    padding: 0.3rem;
                }

                div[data-testid="stTabs"] button[data-baseweb="tab"] {
                    border-radius: 9px;
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.76rem;
                    font-weight: 700;
                    min-height: 38px;
                    padding: 0.45rem 0.85rem;
                }

                div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
                    background: linear-gradient(120deg, rgba(183, 28, 28, 0.88), rgba(229, 57, 53, 0.88));
                    color: #FFFFFF;
                }

                div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
                    display: none;
                }

                .home-v5-info-card {
                    background: var(--app-card);
                    border: 1px solid var(--app-border);
                    border-radius: 10px;
                    margin-top: 0.5rem;
                    padding: 1.5rem;
                }

                .home-v5-info-title {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1.05rem;
                    font-weight: 700;
                    line-height: 1.45;
                    margin-bottom: 1rem;
                }

                .home-v5-info-grid {
                    display: grid;
                    gap: 0.75rem 1.25rem;
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }

                .home-v5-info-item span {
                    color: var(--app-muted);
                    display: block;
                    font-size: 0.72rem;
                    font-weight: 600;
                    margin-bottom: 0.15rem;
                    text-transform: uppercase;
                }

                .home-v5-info-item strong,
                .home-v5-info-item div {
                    color: var(--app-text);
                    font-size: 0.82rem;
                    font-weight: 500;
                    line-height: 1.5;
                }

                @media (max-width: 940px) and (min-width: 761px) {
                    .home-v5-metric-grid {
                        grid-template-columns: repeat(3, minmax(0, 1fr));
                    }
                }

                @media (max-width: 760px) {
                    .home-v5-page { padding-top: 0.45rem; }
                    .home-v5-hero {
                        border-radius: 16px;
                        padding: 1.45rem 1rem 1.2rem 1rem;
                    }
                    .home-v5-hero::after {
                        left: 1rem;
                        right: 1rem;
                    }
                    .home-v5-info-grid { grid-template-columns: 1fr; }
                    .home-v5-metric-grid {
                        gap: 0.75rem;
                        grid-template-columns: 1fr;
                    }
                    .home-v5-metric-card {
                        min-height: 190px;
                    }
                    .home-v5-metric-card--date .home-v5-metric-value {
                        font-size: clamp(1.08rem, 5.2vw, 1.32rem);
                    }
                    .home-v5-service-section-head {
                        align-items: flex-start;
                        flex-direction: column;
                        gap: 0.32rem;
                    }
                    .home-v5-service-section-copy {
                        max-width: none;
                        text-align: left;
                    }
                    .home-v5-service-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                    .home-v5-sentiment-legend { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.36rem; }
                    .home-v5-service-head { gap: 0.58rem; }
                    .home-v5-service-identity { flex-basis: 100%; }
                    .home-v5-service-status--inline { margin-top: 0.42rem; }
                    div[data-testid="stHorizontalBlock"]:has(.home-v5-service-card-marker) {
                        align-items: initial !important;
                    }

                    div[data-testid="stHorizontalBlock"]:has(.home-v5-service-card-marker)
                        > div[data-testid="stColumn"] {
                        display: block !important;
                    }

                    div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card-marker) {
                        display: block !important;
                        min-height: auto !important;
                    }

                    div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card-marker)
                        > div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .home-v5-service-card-marker) {
                        display: block !important;
                    }

                    div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card-marker)
                        > div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .home-v5-service-card-marker)
                        > div[data-testid="stElementContainer"]:has(.home-v5-service-footer-anchor) {
                        margin-top: 0 !important;
                    }
                }


                /* Fase 15: kartu IndiBiz aktif dengan metrik dan mini bar chart. */
                .home-v5-service-status--dummy {
                    background: color-mix(in srgb, #FF9800 14%, transparent);
                    border: 1px solid color-mix(in srgb, #FF9800 34%, transparent);
                    color: #FFB74D;
                }

                .home-v5-service-status--dummy::before {
                    background: #FF9800;
                    box-shadow: 0 0 0 4px rgba(255, 152, 0, 0.12);
                }

                .home-v5-service-stat--total-indibiz {
                    --home-v5-stat-accent: #EF8354;
                }

                .home-v5-service-stat--positive {
                    --home-v5-stat-accent: #4CAF50;
                }

                .home-v5-service-stat--neutral {
                    --home-v5-stat-accent: #FF9800;
                }

                .home-v5-service-stat--negative {
                    --home-v5-stat-accent: #F44336;
                }

                .home-v5-service-stat--positive strong { color: #66BB6A; }
                .home-v5-service-stat--neutral strong { color: #FFB74D; }
                .home-v5-service-stat--negative strong { color: #EF5350; }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card--indibiz) div[data-testid="stPlotlyChart"] {
                    background: color-mix(in srgb, var(--app-secondary) 56%, transparent);
                    border: 1px solid var(--app-border);
                    border-radius: 14px;
                    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
                    overflow: hidden;
                    position: relative;
                    transition: background 0.28s ease, border-color 0.28s ease, box-shadow 0.28s ease, transform 0.28s ease;
                    will-change: transform;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card--indibiz) div[data-testid="stPlotlyChart"]:hover {
                    background: color-mix(in srgb, var(--app-secondary) 86%, #EF8354 5%);
                    border-color: color-mix(in srgb, #EF8354 48%, var(--app-border));
                    box-shadow:
                        0 16px 36px rgba(239, 131, 84, 0.18),
                        0 0 0 1px rgba(239, 131, 84, 0.12);
                    transform: translateY(-3px);
                }


                /* Fase 15.5: penyamaan tinggi dan posisi CTA yang aman.
                   Tinggi utama diberikan lewat API native st.container(height=...).
                   CSS ini hanya menjadi fallback dan tidak mengubah tinggi elemen anak,
                   sehingga isi kartu tidak saling menimpa. */
                @media (min-width: 761px) {
                    div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-service-card-marker)
                        > div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .home-v5-service-card-marker)
                        > div[data-testid="stElementContainer"]:has(.home-v5-service-footer-anchor) {
                        margin-top: auto !important;
                    }
                }


                .home-v5-ready-note {
                    align-items: center;
                    background: rgba(76, 175, 80, 0.11);
                    border: 1px solid rgba(76, 175, 80, 0.34);
                    border-radius: 10px;
                    color: #69D56F;
                    display: flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.68rem;
                    font-weight: 700;
                    gap: 0.42rem;
                    margin: 0.55rem 0 0.72rem 0;
                    padding: 0.55rem 0.65rem;
                }

                .home-v5-ready-note::before {
                    content: '✓';
                    font-size: 0.82rem;
                    font-weight: 900;
                }

                .home-v5-visual-card {
                    background: color-mix(in srgb, var(--app-card) 96%, white 4%);
                    border: 1px solid var(--app-border);
                    border-radius: 16px;
                    min-height: 100%;
                    padding: 0.9rem 0.95rem 0.55rem 0.95rem;
                    transition: border-color 0.22s ease, box-shadow 0.22s ease, transform 0.22s ease;
                }

                .home-v5-visual-card:hover {
                    border-color: rgba(229, 57, 53, 0.48);
                    box-shadow: 0 16px 36px rgba(0, 0, 0, 0.16), 0 0 0 1px rgba(229, 57, 53, 0.08);
                    transform: translateY(-2px);
                }

                .home-v5-visual-card-title {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.92rem;
                    font-weight: 800;
                    line-height: 1.3;
                    margin-bottom: 0.15rem;
                }

                .home-v5-visual-card-copy {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.68rem;
                    line-height: 1.45;
                    margin-bottom: 0.25rem;
                }


                /* Fase 9 Frontend v1.7 — visualisasi gabungan interaktif. */
                .home-v5-viz-hero {
                    --home-v5-viz-red: #E53935;
                    --home-v5-viz-orange: #FF9800;
                    --home-v5-viz-blue: #42A5F5;
                    background:
                        radial-gradient(circle at 8% 18%, rgba(229, 57, 53, 0.20), transparent 28%),
                        radial-gradient(circle at 86% 8%, rgba(66, 165, 245, 0.18), transparent 28%),
                        linear-gradient(135deg, color-mix(in srgb, var(--app-card) 94%, #E53935 6%), color-mix(in srgb, var(--app-card) 96%, #42A5F5 4%));
                    border: 1px solid color-mix(in srgb, var(--app-border) 74%, #E53935 26%);
                    border-radius: 20px;
                    box-shadow: 0 18px 44px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(229, 57, 53, 0.05);
                    isolation: isolate;
                    margin: 0 0 1rem 0;
                    overflow: hidden;
                    padding: 1.05rem 1.15rem;
                    position: relative;
                }

                .home-v5-viz-hero::before {
                    animation: home-v5-viz-aurora 8s ease-in-out infinite alternate;
                    background: linear-gradient(100deg, transparent 8%, rgba(255,255,255,0.08) 44%, transparent 72%);
                    content: '';
                    inset: 0;
                    pointer-events: none;
                    position: absolute;
                    transform: translateX(-65%);
                    z-index: -1;
                }

                .home-v5-viz-hero::after {
                    background: linear-gradient(90deg, #E53935 0%, #FF9800 50%, #42A5F5 100%);
                    bottom: 0;
                    content: '';
                    height: 3px;
                    left: 0;
                    position: absolute;
                    right: 0;
                }

                .home-v5-viz-hero-main {
                    align-items: flex-end;
                    display: flex;
                    gap: 1rem;
                    justify-content: space-between;
                }

                .home-v5-viz-kicker {
                    align-items: center;
                    color: #FF8A80;
                    display: inline-flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.64rem;
                    font-weight: 800;
                    gap: 0.42rem;
                    letter-spacing: 0.11em;
                    margin-bottom: 0.42rem;
                    text-transform: uppercase;
                }

                .home-v5-viz-pulse {
                    animation: home-v5-viz-pulse 1.7s ease-out infinite;
                    background: #FF5252;
                    border-radius: 999px;
                    box-shadow: 0 0 0 0 rgba(255, 82, 82, 0.46);
                    height: 7px;
                    width: 7px;
                }

                .home-v5-viz-title {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.2rem, 2.1vw, 1.52rem);
                    font-weight: 800;
                    letter-spacing: -0.035em;
                    line-height: 1.18;
                    margin: 0;
                }

                .home-v5-viz-copy {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.74rem;
                    line-height: 1.5;
                    margin: 0.38rem 0 0 0;
                    max-width: 660px;
                }

                .home-v5-viz-actions {
                    align-items: center;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.42rem;
                    justify-content: flex-end;
                    max-width: 360px;
                }

                .home-v5-viz-chip {
                    align-items: center;
                    background: color-mix(in srgb, var(--app-secondary) 78%, transparent);
                    border: 1px solid color-mix(in srgb, var(--app-border) 76%, white 8%);
                    border-radius: 999px;
                    color: var(--app-muted);
                    display: inline-flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.61rem;
                    font-weight: 700;
                    gap: 0.34rem;
                    padding: 0.38rem 0.55rem;
                    white-space: nowrap;
                }

                .home-v5-viz-chip svg {
                    color: #FF6B67;
                    height: 13px;
                    width: 13px;
                }

                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker) {
                    align-items: stretch !important;
                    gap: 1rem !important;
                }

                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    > div[data-testid="stColumn"] {
                    --home-v5-viz-accent: #E53935;
                    --home-v5-viz-accent-soft: rgba(229, 57, 53, 0.16);
                    animation: home-v5-viz-card-in 0.68s cubic-bezier(.2,.75,.25,1) both;
                    background:
                        radial-gradient(circle at 88% 7%, var(--home-v5-viz-accent-soft), transparent 30%),
                        linear-gradient(155deg, color-mix(in srgb, var(--app-card) 96%, white 4%), var(--app-card));
                    border: 1px solid color-mix(in srgb, var(--app-border) 76%, var(--home-v5-viz-accent) 24%);
                    border-radius: 22px;
                    box-shadow: 0 18px 42px rgba(0, 0, 0, 0.14);
                    isolation: isolate;
                    overflow: hidden;
                    padding: 1rem 1rem 0.55rem 1rem;
                    position: relative;
                    transition: border-color 0.28s ease, box-shadow 0.28s ease, background 0.28s ease;
                }

                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    > div[data-testid="stColumn"]:nth-child(2) {
                    animation-delay: 0.10s;
                }

                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    > div[data-testid="stColumn"]:has(.home-v5-combined-card-marker--donut) {
                    --home-v5-viz-accent: #FF9800;
                    --home-v5-viz-accent-soft: rgba(255, 152, 0, 0.16);
                }

                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    > div[data-testid="stColumn"]:has(.home-v5-combined-card-marker--bar) {
                    --home-v5-viz-accent: #42A5F5;
                    --home-v5-viz-accent-soft: rgba(66, 165, 245, 0.16);
                }

                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    > div[data-testid="stColumn"]::before {
                    background: linear-gradient(90deg, transparent, var(--home-v5-viz-accent), transparent);
                    content: '';
                    height: 2px;
                    left: -55%;
                    opacity: 0;
                    position: absolute;
                    top: 0;
                    transition: left 0.55s ease, opacity 0.3s ease;
                    width: 52%;
                    z-index: 2;
                }

                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    > div[data-testid="stColumn"]:hover {
                    border-color: color-mix(in srgb, var(--home-v5-viz-accent) 64%, var(--app-border));
                    box-shadow:
                        0 24px 52px color-mix(in srgb, var(--home-v5-viz-accent) 16%, rgba(0,0,0,0.20)),
                        0 0 0 1px color-mix(in srgb, var(--home-v5-viz-accent) 15%, transparent),
                        inset 0 0 32px color-mix(in srgb, var(--home-v5-viz-accent) 5%, transparent);
                }

                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    > div[data-testid="stColumn"]:hover::before {
                    left: 102%;
                    opacity: 1;
                }

                .home-v5-combined-card-marker {
                    display: none;
                }

                .home-v5-combined-card-head {
                    align-items: flex-start;
                    display: flex;
                    gap: 0.72rem;
                    justify-content: space-between;
                    min-height: 72px;
                    position: relative;
                    z-index: 1;
                }

                .home-v5-combined-card-identity {
                    align-items: center;
                    display: flex;
                    gap: 0.72rem;
                    min-width: 0;
                }

                .home-v5-combined-card-icon {
                    align-items: center;
                    background: color-mix(in srgb, var(--home-v5-viz-accent) 13%, transparent);
                    border: 1px solid color-mix(in srgb, var(--home-v5-viz-accent) 34%, transparent);
                    border-radius: 14px;
                    color: var(--home-v5-viz-accent);
                    display: inline-flex;
                    flex: 0 0 auto;
                    height: 42px;
                    justify-content: center;
                    transition: background 0.28s ease, box-shadow 0.28s ease, transform 0.28s ease;
                    width: 42px;
                }

                .home-v5-combined-card-icon svg {
                    height: 21px;
                    width: 21px;
                }

                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    > div[data-testid="stColumn"]:hover .home-v5-combined-card-icon {
                    background: color-mix(in srgb, var(--home-v5-viz-accent) 22%, transparent);
                    box-shadow: 0 0 24px color-mix(in srgb, var(--home-v5-viz-accent) 26%, transparent);
                    transform: rotate(-4deg) scale(1.06);
                }

                .home-v5-combined-card-title {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.95rem;
                    font-weight: 800;
                    letter-spacing: -0.025em;
                    line-height: 1.25;
                    margin: 0;
                }

                .home-v5-combined-card-copy {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.67rem;
                    line-height: 1.42;
                    margin-top: 0.18rem;
                    max-width: 410px;
                }

                .home-v5-combined-card-badge {
                    align-items: center;
                    background: color-mix(in srgb, var(--home-v5-viz-accent) 12%, transparent);
                    border: 1px solid color-mix(in srgb, var(--home-v5-viz-accent) 34%, transparent);
                    border-radius: 999px;
                    color: color-mix(in srgb, var(--home-v5-viz-accent) 82%, white 18%);
                    display: inline-flex;
                    flex: 0 0 auto;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.58rem;
                    font-weight: 800;
                    gap: 0.32rem;
                    letter-spacing: 0.045em;
                    padding: 0.36rem 0.52rem;
                    text-transform: uppercase;
                }

                .home-v5-combined-card-badge::before {
                    animation: home-v5-viz-pulse 1.8s ease-out infinite;
                    background: var(--home-v5-viz-accent);
                    border-radius: 999px;
                    content: '';
                    height: 5px;
                    width: 5px;
                }

                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    > div[data-testid="stColumn"] div[data-testid="stPlotlyChart"],
                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    > div[data-testid="stColumn"] div[data-testid="stPlotlyChart"] > div,
                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    > div[data-testid="stColumn"] .js-plotly-plot,
                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    > div[data-testid="stColumn"] .plot-container,
                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    > div[data-testid="stColumn"] .svg-container {
                    background: transparent !important;
                }

                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    > div[data-testid="stColumn"] div[data-testid="stPlotlyChart"] {
                    border: 0 !important;
                    border-radius: 16px;
                    margin-top: 0.15rem;
                    overflow: hidden;
                    transform: translateZ(0);
                }

                /*
                 * Plotly tidak ditransformasi/filter saat hover. Transform pada
                 * kanvas SVG menyebabkan hit-area bergerak di bawah pointer dan
                 * memicu enter/leave berulang (flicker). Efek interaksi cukup
                 * diberikan pada border, glow card, dan opacity modebar.
                 */
                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    > div[data-testid="stColumn"] div[data-testid="stPlotlyChart"] {
                    backface-visibility: hidden;
                    contain: paint;
                }

                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    .modebar {
                    background: color-mix(in srgb, var(--app-card) 90%, transparent) !important;
                    border: 1px solid var(--app-border);
                    border-radius: 10px !important;
                    box-shadow: 0 8px 22px rgba(0,0,0,0.18);
                    opacity: 0.42;
                    padding: 3px 5px !important;
                    transition: opacity 0.18s ease, border-color 0.18s ease;
                }

                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    div[data-testid="stPlotlyChart"]:hover .modebar,
                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    .modebar:focus-within {
                    border-color: color-mix(in srgb, var(--home-v5-viz-accent) 48%, var(--app-border));
                    opacity: 1;
                }

                /* Nonaktifkan fullscreen bawaan Streamlit hanya pada dua chart ini. */
                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    button[title*="fullscreen" i],
                div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                    button[aria-label*="fullscreen" i] {
                    display: none !important;
                }

                .st-key-home_v5_fullscreen_donut,
                .st-key-home_v5_fullscreen_bar {
                    align-items: flex-start;
                    display: flex;
                    justify-content: flex-end;
                    min-width: 0;
                    padding-top: 0.05rem;
                    width: 100%;
                }

                .st-key-home_v5_fullscreen_donut button,
                .st-key-home_v5_fullscreen_bar button {
                    background: color-mix(in srgb, var(--home-v5-viz-accent) 13%, var(--app-card)) !important;
                    border: 1px solid color-mix(in srgb, var(--home-v5-viz-accent) 42%, var(--app-border)) !important;
                    border-radius: 11px !important;
                    box-shadow: none !important;
                    box-sizing: border-box !important;
                    color: color-mix(in srgb, var(--home-v5-viz-accent) 82%, white 18%) !important;
                    font-family: 'Inter', sans-serif !important;
                    font-size: 0.64rem !important;
                    font-weight: 800 !important;
                    line-height: 1 !important;
                    max-width: 100% !important;
                    min-height: 40px !important;
                    min-width: 126px !important;
                    overflow: hidden !important;
                    padding: 0.42rem 0.52rem !important;
                    transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease !important;
                    white-space: nowrap !important;
                    width: auto !important;
                }

                .st-key-home_v5_fullscreen_donut button p,
                .st-key-home_v5_fullscreen_bar button p,
                .st-key-home_v5_fullscreen_donut button [data-testid="stMarkdownContainer"],
                .st-key-home_v5_fullscreen_bar button [data-testid="stMarkdownContainer"] {
                    align-items: center !important;
                    display: flex !important;
                    font-family: 'Inter', sans-serif !important;
                    font-size: 0.64rem !important;
                    font-weight: 800 !important;
                    justify-content: center !important;
                    line-height: 1 !important;
                    margin: 0 !important;
                    min-width: 0 !important;
                    overflow: hidden !important;
                    text-overflow: clip !important;
                    white-space: nowrap !important;
                }

                .st-key-home_v5_fullscreen_donut button:hover,
                .st-key-home_v5_fullscreen_bar button:hover {
                    background: color-mix(in srgb, var(--home-v5-viz-accent) 22%, var(--app-card)) !important;
                    border-color: color-mix(in srgb, var(--home-v5-viz-accent) 72%, var(--app-border)) !important;
                    box-shadow: 0 0 20px color-mix(in srgb, var(--home-v5-viz-accent) 20%, transparent) !important;
                }

                /* Dialog custom benar-benar memenuhi viewport dan hanya memuat satu chart. */
                div[data-testid="stDialog"]:has(.home-v5-fullscreen-title),
                div[data-baseweb="modal"]:has(.home-v5-fullscreen-title) {
                    inset: 0 !important;
                    margin: 0 !important;
                    padding: 0 !important;
                    position: fixed !important;
                }

                div[data-testid="stDialog"]:has(.home-v5-fullscreen-title) [role="dialog"],
                div[data-baseweb="modal"]:has(.home-v5-fullscreen-title) [role="dialog"] {
                    background:
                        radial-gradient(circle at 86% 4%, rgba(66,165,245,0.12), transparent 30%),
                        radial-gradient(circle at 10% 96%, rgba(255,152,0,0.10), transparent 32%),
                        #0D1119 !important;
                    border: 0 !important;
                    border-radius: 0 !important;
                    box-shadow: none !important;
                    height: 100dvh !important;
                    inset: 0 !important;
                    margin: 0 !important;
                    max-height: 100dvh !important;
                    max-width: 100vw !important;
                    min-height: 100dvh !important;
                    overflow: hidden !important;
                    padding: 0 !important;
                    position: fixed !important;
                    transform: none !important;
                    width: 100vw !important;
                }

                div[data-testid="stDialog"]:has(.home-v5-fullscreen-title) [data-testid="stDialogHeader"],
                div[data-baseweb="modal"]:has(.home-v5-fullscreen-title) [data-testid="stDialogHeader"] {
                    background: transparent !important;
                    border: 0 !important;
                    height: 0 !important;
                    margin: 0 !important;
                    min-height: 0 !important;
                    padding: 0 !important;
                    position: absolute !important;
                    right: 0 !important;
                    top: 0 !important;
                    width: 0 !important;
                    z-index: 1000 !important;
                }

                div[data-testid="stDialog"]:has(.home-v5-fullscreen-title) [data-testid="stDialogHeader"] h2,
                div[data-testid="stDialog"]:has(.home-v5-fullscreen-title) [data-testid="stDialogHeader"] p,
                div[data-baseweb="modal"]:has(.home-v5-fullscreen-title) [data-testid="stDialogHeader"] h2,
                div[data-baseweb="modal"]:has(.home-v5-fullscreen-title) [data-testid="stDialogHeader"] p {
                    display: none !important;
                }

                div[data-testid="stDialog"]:has(.home-v5-fullscreen-title) button[aria-label="Close"],
                div[data-baseweb="modal"]:has(.home-v5-fullscreen-title) button[aria-label="Close"] {
                    background: #202631 !important;
                    border: 1px solid #354052 !important;
                    border-radius: 11px !important;
                    color: #FFFFFF !important;
                    height: 42px !important;
                    position: fixed !important;
                    right: 16px !important;
                    top: 14px !important;
                    width: 42px !important;
                    z-index: 1002 !important;
                }

                div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.home-v5-fullscreen-title),
                div[data-baseweb="modal"] div[data-testid="stVerticalBlock"]:has(.home-v5-fullscreen-title) {
                    gap: 0.30rem !important;
                    height: 100dvh !important;
                    margin: 0 !important;
                    max-height: 100dvh !important;
                    overflow: hidden !important;
                    padding: 8px 18px 10px !important;
                    width: 100vw !important;
                }

                .home-v5-fullscreen-heading {
                    display: flex;
                    flex: 0 0 auto;
                    flex-direction: column;
                    gap: 0.22rem;
                    margin: 0 0 4px;
                    padding-right: 58px;
                }

                .home-v5-fullscreen-title {
                    color: #FFFFFF !important;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.15rem, 2vw, 1.62rem);
                    font-weight: 800;
                    letter-spacing: -0.025em;
                    line-height: 1.15;
                    margin: 0;
                }

                .home-v5-fullscreen-hint {
                    color: #9AA6B8;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.74rem;
                    line-height: 1.4;
                    margin: 0;
                }

                div[data-testid="stDialog"]:has(.home-v5-fullscreen-title) [data-testid="stPlotlyChart"],
                div[data-baseweb="modal"]:has(.home-v5-fullscreen-title) [data-testid="stPlotlyChart"] {
                    background: #141A25 !important;
                    border: 1px solid #2B3A50 !important;
                    border-radius: 16px !important;
                    height: calc(100dvh - 96px) !important;
                    margin: 0 !important;
                    min-height: 460px !important;
                    overflow: hidden !important;
                    width: 100% !important;
                }

                div[data-testid="stDialog"]:has(.home-v5-fullscreen-title) [data-testid="stPlotlyChart"] > div,
                div[data-testid="stDialog"]:has(.home-v5-fullscreen-title) [data-testid="stPlotlyChart"] .js-plotly-plot,
                div[data-testid="stDialog"]:has(.home-v5-fullscreen-title) [data-testid="stPlotlyChart"] .plot-container,
                div[data-testid="stDialog"]:has(.home-v5-fullscreen-title) [data-testid="stPlotlyChart"] .svg-container,
                div[data-baseweb="modal"]:has(.home-v5-fullscreen-title) [data-testid="stPlotlyChart"] > div,
                div[data-baseweb="modal"]:has(.home-v5-fullscreen-title) [data-testid="stPlotlyChart"] .js-plotly-plot,
                div[data-baseweb="modal"]:has(.home-v5-fullscreen-title) [data-testid="stPlotlyChart"] .plot-container,
                div[data-baseweb="modal"]:has(.home-v5-fullscreen-title) [data-testid="stPlotlyChart"] .svg-container {
                    height: 100% !important;
                    width: 100% !important;
                }

                @media (max-height: 720px) {
                    div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.home-v5-fullscreen-title),
                    div[data-baseweb="modal"] div[data-testid="stVerticalBlock"]:has(.home-v5-fullscreen-title) {
                        overflow-y: auto !important;
                        padding-top: 4px !important;
                    }

                    div[data-testid="stDialog"]:has(.home-v5-fullscreen-title) [data-testid="stPlotlyChart"],
                    div[data-baseweb="modal"]:has(.home-v5-fullscreen-title) [data-testid="stPlotlyChart"] {
                        height: 620px !important;
                        min-height: 620px !important;
                    }
                }

                div[data-testid="stDialog"]:has(.home-v5-fullscreen-title)
                    button[title*="fullscreen" i],
                div[data-testid="stDialog"]:has(.home-v5-fullscreen-title)
                    button[aria-label*="fullscreen" i],
                div[data-baseweb="modal"]:has(.home-v5-fullscreen-title)
                    button[title*="fullscreen" i],
                div[data-baseweb="modal"]:has(.home-v5-fullscreen-title)
                    button[aria-label*="fullscreen" i] {
                    display: none !important;
                }

                @keyframes home-v5-viz-card-in {
                    from { opacity: 0; transform: translateY(20px) scale(0.985); }
                    to { opacity: 1; transform: translateY(0) scale(1); }
                }

                @keyframes home-v5-viz-aurora {
                    from { transform: translateX(-65%); }
                    to { transform: translateX(70%); }
                }

                @keyframes home-v5-viz-pulse {
                    0% { box-shadow: 0 0 0 0 color-mix(in srgb, currentColor 42%, transparent); }
                    70% { box-shadow: 0 0 0 7px transparent; }
                    100% { box-shadow: 0 0 0 0 transparent; }
                }

                @media (max-width: 920px) {
                    .home-v5-viz-hero-main {
                        align-items: flex-start;
                        flex-direction: column;
                    }
                    .home-v5-viz-actions {
                        justify-content: flex-start;
                        max-width: none;
                    }
                    div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                        > div[data-testid="stColumn"] {
                        padding: 0.88rem 0.88rem 0.45rem 0.88rem;
                    }
                }

                @media (max-width: 640px) {
                    .home-v5-viz-hero { padding: 0.9rem; }
                    .home-v5-viz-actions { display: none; }
                    .home-v5-combined-card-head { min-height: auto; }
                    .home-v5-combined-card-badge { display: none; }
                }

                @media (prefers-reduced-motion: reduce) {
                    .home-v5-viz-hero::before,
                    .home-v5-viz-pulse,
                    .home-v5-combined-card-badge::before,
                    div[data-testid="stHorizontalBlock"]:has(.home-v5-combined-card-marker)
                        > div[data-testid="stColumn"] {
                        animation: none !important;
                    }
                }

                .home-v5-guide-grid {
                    display: grid;
                    gap: 0.75rem;
                    grid-template-columns: repeat(4, minmax(0, 1fr));
                    margin-top: 0.55rem;
                }

                .home-v5-guide-item {
                    background: color-mix(in srgb, var(--app-card) 96%, white 4%);
                    border: 1px solid var(--app-border);
                    border-radius: 14px;
                    min-height: 150px;
                    padding: 0.9rem;
                    position: relative;
                    transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
                }

                .home-v5-guide-item:hover {
                    border-color: rgba(229, 57, 53, 0.48);
                    box-shadow: 0 12px 28px rgba(229, 57, 53, 0.10);
                    transform: translateY(-3px);
                }

                .home-v5-guide-number {
                    align-items: center;
                    background: linear-gradient(135deg, #B71C1C, #E53935);
                    border-radius: 10px;
                    color: #FFFFFF;
                    display: inline-flex;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.78rem;
                    font-weight: 800;
                    height: 30px;
                    justify-content: center;
                    margin-bottom: 0.7rem;
                    width: 30px;
                }

                .home-v5-guide-item strong {
                    color: var(--app-text);
                    display: block;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.82rem;
                    font-weight: 800;
                    line-height: 1.35;
                    margin-bottom: 0.35rem;
                }

                .home-v5-guide-item span {
                    color: var(--app-muted);
                    display: block;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.69rem;
                    line-height: 1.5;
                }

                @media (max-width: 1050px) {
                    .home-v5-guide-grid {
                        grid-template-columns: repeat(2, minmax(0, 1fr));
                    }
                }

                @media (max-width: 680px) {
                    .home-v5-guide-grid {
                        grid-template-columns: 1fr;
                    }
                }


                /* ==========================================================
                   TOP 5 INFLUENCER — FRONTEND INTERAKTIF V2.3
                   ========================================================== */
                @keyframes homeV5InfluencerAura {
                    0%, 100% { transform: translate3d(-8%, -5%, 0) scale(1); opacity: 0.42; }
                    50% { transform: translate3d(8%, 7%, 0) scale(1.08); opacity: 0.82; }
                }

                @keyframes homeV5InfluencerEnter {
                    from { opacity: 0; transform: translateY(10px); }
                    to { opacity: 1; transform: translateY(0); }
                }

                @keyframes homeV5InfluencerPulse {
                    0%, 100% { box-shadow: 0 0 0 0 rgba(255, 193, 7, 0.26); }
                    50% { box-shadow: 0 0 0 7px rgba(255, 193, 7, 0); }
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-influencer-section-marker) {
                    background:
                        radial-gradient(circle at 92% 8%, rgba(37, 244, 238, 0.12), transparent 24%),
                        radial-gradient(circle at 8% 0%, rgba(225, 48, 108, 0.13), transparent 23%),
                        linear-gradient(145deg, rgba(15, 23, 42, 0.98), rgba(9, 15, 29, 0.99));
                    border: 1px solid rgba(96, 165, 250, 0.24) !important;
                    border-radius: 22px !important;
                    box-shadow: 0 22px 46px rgba(2, 6, 23, 0.32), inset 0 1px 0 rgba(255,255,255,0.035);
                    overflow: hidden;
                    position: relative;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-influencer-section-marker)::before {
                    animation: homeV5InfluencerAura 12s ease-in-out infinite;
                    background: linear-gradient(120deg, rgba(66,165,245,0.15), rgba(225,48,108,0.12), rgba(37,244,238,0.11));
                    border-radius: 50%;
                    content: '';
                    filter: blur(28px);
                    height: 280px;
                    pointer-events: none;
                    position: absolute;
                    right: -90px;
                    top: -120px;
                    width: 420px;
                    z-index: 0;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-influencer-section-marker)
                    > div[data-testid="stVerticalBlock"] {
                    gap: 0.75rem;
                    position: relative;
                    z-index: 1;
                }

                .home-v5-influencer-section-marker {
                    display: none;
                }

                .home-v5-influencer-overview-v23 {
                    animation: homeV5InfluencerEnter 0.46s ease both;
                    background:
                        linear-gradient(130deg, rgba(30, 41, 59, 0.82), rgba(15, 23, 42, 0.72)),
                        radial-gradient(circle at 100% 0%, rgba(66, 165, 245, 0.16), transparent 30%);
                    border: 1px solid rgba(148, 163, 184, 0.18);
                    border-radius: 18px;
                    overflow: hidden;
                    padding: 1rem 1.05rem;
                    position: relative;
                }

                .home-v5-influencer-overview-v23::after {
                    background: linear-gradient(90deg, #42A5F5, #E1306C, #25F4EE);
                    content: '';
                    height: 3px;
                    left: 0;
                    position: absolute;
                    right: 0;
                    top: 0;
                }

                .home-v5-influencer-overview-head-v23 {
                    align-items: flex-start;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.85rem;
                    justify-content: space-between;
                }

                .home-v5-influencer-eyebrow-v23 {
                    align-items: center;
                    color: #93C5FD;
                    display: inline-flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.68rem;
                    font-weight: 800;
                    gap: 0.42rem;
                    letter-spacing: 0.18em;
                    text-transform: uppercase;
                }

                .home-v5-influencer-eyebrow-v23::before {
                    background: linear-gradient(135deg, #42A5F5, #25F4EE);
                    border-radius: 999px;
                    box-shadow: 0 0 0 5px rgba(66,165,245,0.10);
                    content: '';
                    height: 9px;
                    width: 9px;
                }

                .home-v5-influencer-overview-title-v23 {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.02rem, 1.8vw, 1.28rem);
                    font-weight: 800;
                    line-height: 1.25;
                    margin-top: 0.48rem;
                }

                .home-v5-influencer-overview-copy-v23 {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.79rem;
                    line-height: 1.55;
                    margin-top: 0.35rem;
                    max-width: 48rem;
                }

                .home-v5-influencer-live-v23 {
                    align-items: center;
                    background: rgba(22, 101, 52, 0.24);
                    border: 1px solid rgba(74, 222, 128, 0.34);
                    border-radius: 999px;
                    color: #86EFAC;
                    display: inline-flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.68rem;
                    font-weight: 800;
                    gap: 0.42rem;
                    padding: 0.42rem 0.65rem;
                    white-space: nowrap;
                }

                .home-v5-influencer-live-v23::before {
                    background: #4ADE80;
                    border-radius: 50%;
                    box-shadow: 0 0 0 4px rgba(74,222,128,0.12);
                    content: '';
                    height: 8px;
                    width: 8px;
                }

                .home-v5-influencer-summary-grid-v23 {
                    display: grid;
                    gap: 0.72rem;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    margin-top: 0.9rem;
                }

                .home-v5-influencer-summary-card-v23 {
                    background: linear-gradient(135deg, rgba(15, 23, 42, 0.78), rgba(30, 41, 59, 0.7));
                    border: 1px solid color-mix(in srgb, var(--home-v5-inf-accent) 44%, rgba(148,163,184,0.18));
                    border-radius: 15px;
                    min-height: 92px;
                    overflow: hidden;
                    padding: 0.8rem 0.86rem;
                    position: relative;
                    transition: border-color 0.24s ease, box-shadow 0.24s ease, transform 0.24s ease;
                }

                .home-v5-influencer-summary-card-v23::after {
                    background: linear-gradient(135deg, color-mix(in srgb, var(--home-v5-inf-accent) 18%, transparent), transparent 66%);
                    content: '';
                    inset: 0;
                    pointer-events: none;
                    position: absolute;
                }

                .home-v5-influencer-summary-card-v23:hover {
                    border-color: color-mix(in srgb, var(--home-v5-inf-accent) 82%, white 18%);
                    box-shadow: 0 12px 26px color-mix(in srgb, var(--home-v5-inf-accent) 16%, rgba(2,6,23,0.34));
                    transform: translateY(-3px);
                }

                .home-v5-influencer-summary-top-v23 {
                    align-items: center;
                    display: flex;
                    gap: 0.55rem;
                    position: relative;
                    z-index: 1;
                }

                .home-v5-influencer-summary-icon-v23 {
                    align-items: center;
                    background: color-mix(in srgb, var(--home-v5-inf-accent) 18%, rgba(15,23,42,0.84));
                    border: 1px solid color-mix(in srgb, var(--home-v5-inf-accent) 48%, transparent);
                    border-radius: 11px;
                    color: var(--home-v5-inf-accent);
                    display: inline-flex;
                    flex: 0 0 34px;
                    font-family: 'Plus Jakarta Sans', sans-serif;
                    font-size: 0.7rem;
                    font-weight: 800;
                    height: 34px;
                    justify-content: center;
                }

                .home-v5-influencer-summary-label-v23 {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.68rem;
                    font-weight: 700;
                }

                .home-v5-influencer-summary-number-v23 {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 1rem;
                    font-weight: 800;
                    line-height: 1.25;
                }

                .home-v5-influencer-summary-leader-v23 {
                    color: color-mix(in srgb, var(--home-v5-inf-accent) 72%, white 28%);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.7rem;
                    font-weight: 700;
                    margin-top: 0.52rem;
                    overflow: hidden;
                    position: relative;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                    z-index: 1;
                }

                .st-key-home_v5_influencer_platform_focus [role="radiogroup"] {
                    background: rgba(15, 23, 42, 0.72);
                    border: 1px solid rgba(148, 163, 184, 0.16);
                    border-radius: 14px;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.42rem;
                    padding: 0.4rem;
                }

                .st-key-home_v5_influencer_platform_focus label {
                    background: rgba(30, 41, 59, 0.74);
                    border: 1px solid rgba(148, 163, 184, 0.15);
                    border-radius: 10px;
                    min-height: 38px;
                    padding: 0.44rem 0.72rem !important;
                    transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
                }

                .st-key-home_v5_influencer_platform_focus label:hover {
                    background: linear-gradient(135deg, rgba(66,165,245,0.18), rgba(225,48,108,0.12));
                    border-color: rgba(96,165,250,0.46);
                    box-shadow: 0 8px 18px rgba(30,64,175,0.12);
                    transform: translateY(-1px);
                }

                .st-key-home_v5_influencer_platform_focus label:has(input:checked) {
                    background: linear-gradient(135deg, rgba(37,99,235,0.94), rgba(66,165,245,0.88));
                    border-color: rgba(147,197,253,0.82);
                    box-shadow: 0 10px 22px rgba(37,99,235,0.24);
                }

                .st-key-home_v5_influencer_platform_focus label p,
                .st-key-home_v5_influencer_platform_focus label span {
                    color: var(--app-text) !important;
                    font-family: 'Inter', sans-serif !important;
                    font-size: 0.72rem !important;
                    font-weight: 800 !important;
                }

                .home-v5-platform-influencer-heading-v23 {
                    align-items: center;
                    animation: homeV5InfluencerEnter 0.42s ease both;
                    background: linear-gradient(90deg, color-mix(in srgb, var(--home-v5-platform-accent) 13%, transparent), transparent 72%);
                    border-left: 3px solid var(--home-v5-platform-accent);
                    border-radius: 0 13px 13px 0;
                    display: flex;
                    gap: 0.72rem;
                    margin: 0.4rem 0 0.62rem;
                    padding: 0.66rem 0.78rem;
                }

                .home-v5-platform-influencer-badge-v23 {
                    align-items: center;
                    background: color-mix(in srgb, var(--home-v5-platform-accent) 17%, rgba(15,23,42,0.88));
                    border: 1px solid color-mix(in srgb, var(--home-v5-platform-accent) 48%, transparent);
                    border-radius: 11px;
                    color: var(--home-v5-platform-accent);
                    display: inline-flex;
                    flex: 0 0 38px;
                    font-family: 'Plus Jakarta Sans', sans-serif;
                    font-size: 0.72rem;
                    font-weight: 800;
                    height: 38px;
                    justify-content: center;
                }

                .home-v5-platform-influencer-heading-v23 strong {
                    color: var(--app-text);
                    display: block;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.95rem;
                    font-weight: 800;
                    line-height: 1.25;
                }

                .home-v5-platform-influencer-heading-v23 span:not(.home-v5-platform-influencer-badge-v23) {
                    color: var(--app-muted);
                    display: block;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.68rem;
                    line-height: 1.35;
                    margin-top: 0.12rem;
                }

                .home-v5-influencer-panel-v23 {
                    animation: homeV5InfluencerEnter 0.5s ease both;
                    background: linear-gradient(145deg, rgba(22, 31, 48, 0.96), rgba(13, 20, 34, 0.98));
                    border: 1px solid color-mix(in srgb, var(--home-v5-table-accent) 34%, rgba(148,163,184,0.18));
                    border-radius: 18px;
                    box-shadow: inset 0 1px 0 rgba(255,255,255,0.035);
                    overflow: hidden;
                    padding: 0.92rem 0.92rem 1.34rem;
                    position: relative;
                    transition: border-color 0.24s ease, box-shadow 0.24s ease;
                }

                .home-v5-influencer-panel-v23:hover {
                    border-color: color-mix(in srgb, var(--home-v5-table-accent) 58%, rgba(255,255,255,0.2));
                    box-shadow: 0 16px 34px rgba(2,6,23,0.28);
                }

                .home-v5-influencer-meta-v23 {
                    align-items: center;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.55rem;
                    justify-content: space-between;
                    margin-bottom: 0.78rem;
                }

                .home-v5-influencer-platform-chip-v23 {
                    align-items: center;
                    background: color-mix(in srgb, var(--home-v5-table-accent) 15%, rgba(15,23,42,0.9));
                    border: 1px solid color-mix(in srgb, var(--home-v5-table-accent) 48%, transparent);
                    border-radius: 999px;
                    color: color-mix(in srgb, var(--home-v5-table-accent) 75%, white 25%);
                    display: inline-flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.68rem;
                    font-weight: 800;
                    gap: 0.4rem;
                    padding: 0.38rem 0.58rem;
                }

                .home-v5-influencer-platform-chip-v23::before {
                    background: var(--home-v5-table-accent);
                    border-radius: 50%;
                    content: '';
                    height: 8px;
                    width: 8px;
                }

                .home-v5-influencer-rule-v23 {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.68rem;
                    font-weight: 650;
                }

                .home-v5-influencer-table-wrap-v23 {
                    border: 1px solid rgba(148, 163, 184, 0.16);
                    border-radius: 14px;
                    margin-bottom: 0.24rem;
                    margin-top: -0.08rem;
                    overflow-x: auto;
                    transform: translateY(-0.08rem);
                    width: 100%;
                }

                .home-v5-influencer-table-v23 {
                    border-collapse: separate;
                    border-spacing: 0;
                    min-width: 780px;
                    width: 100%;
                }

                .home-v5-influencer-table-v23 th {
                    background: linear-gradient(180deg, rgba(35, 49, 73, 0.98), rgba(28, 40, 61, 0.98));
                    border-bottom: 1px solid rgba(148, 163, 184, 0.18);
                    color: #E2E8F0;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.69rem;
                    font-weight: 800;
                    letter-spacing: 0.035em;
                    padding: 0.76rem 0.72rem;
                    text-align: left;
                    text-transform: uppercase;
                }

                .home-v5-influencer-table-v23 td {
                    border-bottom: 1px solid rgba(148, 163, 184, 0.11);
                    color: var(--app-text);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.77rem;
                    padding: 0.7rem 0.72rem;
                    transition: background 0.2s ease, box-shadow 0.2s ease;
                    vertical-align: middle;
                }

                .home-v5-influencer-table-v23 tbody tr:nth-child(odd) td {
                    background: rgba(15, 23, 42, 0.54);
                }

                .home-v5-influencer-table-v23 tbody tr:nth-child(even) td {
                    background: rgba(30, 41, 59, 0.58);
                }

                .home-v5-influencer-table-v23 tbody tr:hover td {
                    background: color-mix(in srgb, var(--home-v5-table-accent) 12%, rgba(30,41,59,0.86));
                    box-shadow: inset 0 1px 0 color-mix(in srgb, var(--home-v5-table-accent) 18%, transparent), inset 0 -1px 0 color-mix(in srgb, var(--home-v5-table-accent) 16%, transparent);
                }

                .home-v5-rank-medal-v23 {
                    align-items: center;
                    background: rgba(51, 65, 85, 0.88);
                    border: 1px solid rgba(148, 163, 184, 0.22);
                    border-radius: 11px;
                    color: #E2E8F0;
                    display: inline-flex;
                    font-family: 'Plus Jakarta Sans', sans-serif;
                    font-size: 0.72rem;
                    font-weight: 800;
                    height: 32px;
                    justify-content: center;
                    width: 32px;
                }

                .home-v5-rank-medal-v23--1 {
                    animation: homeV5InfluencerPulse 2.4s ease-in-out infinite;
                    background: linear-gradient(135deg, #F59E0B, #FCD34D);
                    border-color: rgba(254, 243, 199, 0.78);
                    color: #422006;
                }

                .home-v5-rank-medal-v23--2 {
                    background: linear-gradient(135deg, #94A3B8, #E2E8F0);
                    border-color: rgba(241,245,249,0.72);
                    color: #1E293B;
                }

                .home-v5-rank-medal-v23--3 {
                    background: linear-gradient(135deg, #B45309, #F59E0B);
                    border-color: rgba(253,230,138,0.62);
                    color: #FFF7ED;
                }

                .home-v5-account-cell-v23 {
                    align-items: center;
                    display: flex;
                    gap: 0.58rem;
                }

                .home-v5-account-avatar-v23 {
                    align-items: center;
                    background: color-mix(in srgb, var(--home-v5-table-accent) 17%, rgba(15,23,42,0.9));
                    border: 1px solid color-mix(in srgb, var(--home-v5-table-accent) 45%, transparent);
                    border-radius: 10px;
                    color: color-mix(in srgb, var(--home-v5-table-accent) 76%, white 24%);
                    display: inline-flex;
                    flex: 0 0 32px;
                    font-size: 0.72rem;
                    font-weight: 900;
                    height: 32px;
                    justify-content: center;
                }

                .home-v5-account-cell-v23 strong {
                    color: #F8FAFC;
                    font-size: 0.78rem;
                    font-weight: 800;
                }

                .home-v5-number-chip-v23 {
                    align-items: center;
                    background: rgba(15, 23, 42, 0.62);
                    border: 1px solid rgba(148, 163, 184, 0.15);
                    border-radius: 9px;
                    color: #E2E8F0;
                    display: inline-flex;
                    font-size: 0.72rem;
                    font-weight: 800;
                    padding: 0.32rem 0.48rem;
                }

                .home-v5-interaction-metric-v23 {
                    display: grid;
                    gap: 0.35rem;
                    min-width: 112px;
                }

                .home-v5-interaction-metric-v23 strong {
                    color: #F8FAFC;
                    font-size: 0.75rem;
                    font-weight: 800;
                }

                .home-v5-interaction-track-v23 {
                    background: rgba(148, 163, 184, 0.12);
                    border-radius: 999px;
                    height: 5px;
                    overflow: hidden;
                    width: 100%;
                }

                .home-v5-interaction-track-v23 i {
                    background: linear-gradient(90deg, var(--home-v5-table-accent), color-mix(in srgb, var(--home-v5-table-accent) 55%, white 45%));
                    border-radius: inherit;
                    display: block;
                    height: 100%;
                    min-width: 4px;
                    transition: width 0.4s ease;
                }

                .home-v5-influencer-divider-v23 {
                    background: linear-gradient(90deg, transparent, rgba(96,165,250,0.22), rgba(225,48,108,0.18), transparent);
                    height: 1px;
                    margin: 1rem 0;
                    width: 100%;
                }

                @media (max-width: 980px) {
                    .home-v5-influencer-summary-grid-v23 {
                        grid-template-columns: minmax(0, 1fr);
                    }
                }



                /* ==========================================================
                   PANDUAN + INFORMASI PENELITIAN — INTERAKTIF V2.5
                   ========================================================== */
                @keyframes homeV5GuideBeam {
                    0% { transform: translateX(-120%); opacity: 0; }
                    22% { opacity: 0.8; }
                    55% { opacity: 0.45; }
                    100% { transform: translateX(260%); opacity: 0; }
                }

                @keyframes homeV5GuideIconPulse {
                    0%, 100% { transform: translateY(0) scale(1); }
                    50% { transform: translateY(-3px) scale(1.04); }
                }

                @keyframes homeV5ResearchAura {
                    0%, 100% { transform: translate3d(-8%, -5%, 0) scale(1); opacity: 0.38; }
                    50% { transform: translate3d(8%, 7%, 0) scale(1.08); opacity: 0.75; }
                }

                .home-v5-section-intro-v25 {
                    align-items: flex-end;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.8rem;
                    justify-content: space-between;
                    margin: 0.15rem 0 0.85rem;
                }

                .home-v5-section-intro-v25 > div:first-child {
                    min-width: min(100%, 540px);
                }

                .home-v5-section-kicker-v25 {
                    align-items: center;
                    color: #FF8A80;
                    display: inline-flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.68rem;
                    font-weight: 800;
                    gap: 0.4rem;
                    letter-spacing: 0.2em;
                    margin-bottom: 0.45rem;
                    text-transform: uppercase;
                }

                .home-v5-section-kicker-v25::before {
                    background: linear-gradient(135deg, #E53935, #FF9800);
                    border-radius: 50%;
                    box-shadow: 0 0 0 5px rgba(229, 57, 53, 0.12);
                    content: '';
                    height: 9px;
                    width: 9px;
                }

                .home-v5-section-heading-v25 {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.2rem, 2.2vw, 1.5rem);
                    font-weight: 800;
                    line-height: 1.2;
                    margin: 0;
                }

                .home-v5-section-copy-v25 {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.79rem;
                    line-height: 1.55;
                    margin-top: 0.38rem;
                    max-width: 46rem;
                }

                .home-v5-section-badge-v25 {
                    align-items: center;
                    background: linear-gradient(135deg, rgba(229,57,53,0.14), rgba(66,165,245,0.12));
                    border: 1px solid rgba(229,57,53,0.22);
                    border-radius: 999px;
                    color: var(--app-text);
                    display: inline-flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.69rem;
                    font-weight: 750;
                    gap: 0.42rem;
                    padding: 0.42rem 0.68rem;
                    white-space: nowrap;
                }

                .home-v5-section-badge-v25::before {
                    background: #4CAF50;
                    border-radius: 50%;
                    box-shadow: 0 0 0 4px rgba(76,175,80,0.12);
                    content: '';
                    height: 8px;
                    width: 8px;
                }

                div[data-testid="stHorizontalBlock"]:has(.home-v5-guide-card-marker-v25) {
                    align-items: stretch;
                    gap: 0.78rem;
                }

                div[data-testid="stHorizontalBlock"]:has(.home-v5-guide-card-marker-v25)
                    > div[data-testid="stColumn"] {
                    box-sizing: border-box !important;
                    display: flex !important;
                    flex: 1 1 0 !important;
                    max-width: none !important;
                    min-width: 0 !important;
                    width: 0 !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card-marker-v25) {
                    background:
                        radial-gradient(circle at 88% 8%, color-mix(in srgb, var(--home-v5-guide-accent, #E53935) 18%, transparent), transparent 30%),
                        linear-gradient(145deg, rgba(25, 34, 50, 0.98), rgba(14, 22, 36, 0.98));
                    border: 1px solid color-mix(in srgb, var(--home-v5-guide-accent, #E53935) 36%, rgba(148,163,184,0.18)) !important;
                    border-radius: 18px !important;
                    box-shadow: 0 14px 30px rgba(2, 8, 23, 0.22), inset 0 1px 0 rgba(255,255,255,0.03);
                    display: flex;
                    min-height: 255px;
                    overflow: hidden;
                    position: relative;
                    transition: border-color 0.28s ease, box-shadow 0.28s ease, transform 0.28s ease;
                    width: 100%;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card-marker-v25)::before {
                    animation: homeV5GuideBeam 7.8s ease-in-out infinite;
                    background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--home-v5-guide-accent, #E53935) 72%, white 28%), transparent);
                    content: '';
                    height: 2px;
                    left: 0;
                    position: absolute;
                    top: 0;
                    width: 38%;
                    z-index: 2;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card--2) { --home-v5-guide-accent: #FF9800; }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card--3) { --home-v5-guide-accent: #42A5F5; }
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card--4) { --home-v5-guide-accent: #4CAF50; }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card-marker-v25):hover {
                    border-color: color-mix(in srgb, var(--home-v5-guide-accent, #E53935) 78%, white 22%) !important;
                    box-shadow: 0 20px 40px color-mix(in srgb, var(--home-v5-guide-accent, #E53935) 15%, rgba(2,8,23,0.38));
                    transform: translateY(-5px);
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card-marker-v25)
                    > div[data-testid="stVerticalBlock"] {
                    display: flex;
                    flex: 1 1 auto;
                    gap: 0.35rem;
                    height: 100%;
                    position: relative;
                    z-index: 1;
                }

                .home-v5-guide-card-marker-v25 { display: none; }

                .home-v5-guide-content-v25 {
                    display: flex;
                    flex: 1 1 auto;
                    flex-direction: column;
                    min-height: 156px;
                }

                .home-v5-guide-head-v25 {
                    align-items: center;
                    display: flex;
                    gap: 0.65rem;
                    justify-content: space-between;
                    margin-bottom: 0.75rem;
                }

                .home-v5-guide-icon-v25 {
                    align-items: center;
                    animation: homeV5GuideIconPulse 5.8s ease-in-out infinite;
                    background: linear-gradient(135deg, color-mix(in srgb, var(--home-v5-guide-accent, #E53935) 78%, black 22%), var(--home-v5-guide-accent, #E53935));
                    border: 1px solid color-mix(in srgb, var(--home-v5-guide-accent, #E53935) 82%, white 18%);
                    border-radius: 14px;
                    box-shadow: 0 10px 22px color-mix(in srgb, var(--home-v5-guide-accent, #E53935) 20%, transparent);
                    color: #FFFFFF;
                    display: inline-flex;
                    font-size: 1rem;
                    height: 42px;
                    justify-content: center;
                    width: 42px;
                }

                .home-v5-guide-step-v25 {
                    align-items: center;
                    background: color-mix(in srgb, var(--home-v5-guide-accent, #E53935) 15%, transparent);
                    border: 1px solid color-mix(in srgb, var(--home-v5-guide-accent, #E53935) 42%, transparent);
                    border-radius: 999px;
                    color: color-mix(in srgb, var(--home-v5-guide-accent, #E53935) 72%, white 28%);
                    display: inline-flex;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.68rem;
                    font-weight: 800;
                    padding: 0.32rem 0.52rem;
                }

                .home-v5-guide-title-v25 {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.94rem;
                    font-weight: 800;
                    line-height: 1.3;
                    margin-bottom: 0.34rem;
                }

                .home-v5-guide-copy-v25 {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.72rem;
                    line-height: 1.55;
                }

                .home-v5-guide-micro-v25 {
                    align-items: center;
                    color: color-mix(in srgb, var(--home-v5-guide-accent, #E53935) 68%, white 32%);
                    display: flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.66rem;
                    font-weight: 700;
                    gap: 0.35rem;
                    margin-top: auto;
                    padding-top: 0.75rem;
                }

                .home-v5-guide-micro-v25::before {
                    background: var(--home-v5-guide-accent, #E53935);
                    border-radius: 999px;
                    content: '';
                    height: 5px;
                    width: 18px;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card-marker-v25) .stButton {
                    margin-top: auto;
                    padding-top: 0.35rem;
                    width: 100%;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card-marker-v25) .stButton button {
                    background: linear-gradient(135deg, color-mix(in srgb, var(--home-v5-guide-accent, #E53935) 72%, #111827 28%), var(--home-v5-guide-accent, #E53935)) !important;
                    border: 1px solid color-mix(in srgb, var(--home-v5-guide-accent, #E53935) 82%, white 18%) !important;
                    border-radius: 12px !important;
                    box-shadow: 0 10px 22px color-mix(in srgb, var(--home-v5-guide-accent, #E53935) 18%, transparent) !important;
                    color: #FFFFFF !important;
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif !important;
                    font-size: 0.72rem !important;
                    font-weight: 800 !important;
                    min-height: 40px !important;
                    transition: transform 0.22s ease, box-shadow 0.22s ease, filter 0.22s ease !important;
                    width: 100% !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card-marker-v25) .stButton button:hover {
                    box-shadow: 0 14px 28px color-mix(in srgb, var(--home-v5-guide-accent, #E53935) 26%, transparent) !important;
                    filter: brightness(1.08);
                    transform: translateY(-2px);
                }


                /* Patch v2.8 — tinggi mengikuti isi terpanjang, tanpa ruang kosong berlebihan. */
                div[data-testid="stHorizontalBlock"]:has(.home-v5-guide-card-marker-v25) {
                    align-items: stretch !important;
                    display: flex !important;
                    width: 100% !important;
                }

                div[data-testid="stHorizontalBlock"]:has(.home-v5-guide-card-marker-v25)
                    > div[data-testid="stColumn"] {
                    align-self: stretch !important;
                    box-sizing: border-box !important;
                    display: flex !important;
                    flex: 1 1 0 !important;
                    max-width: none !important;
                    min-width: 0 !important;
                    width: 0 !important;
                }

                div[data-testid="stHorizontalBlock"]:has(.home-v5-guide-card-marker-v25)
                    > div[data-testid="stColumn"]
                    > div[data-testid="stVerticalBlock"] {
                    display: flex !important;
                    flex: 1 1 auto !important;
                    flex-direction: column !important;
                    width: 100% !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card-marker-v25) {
                    align-self: stretch !important;
                    box-sizing: border-box !important;
                    display: flex !important;
                    flex: 1 1 auto !important;
                    height: auto !important;
                    max-height: none !important;
                    min-height: 356px !important;
                    width: 100% !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card-marker-v25)
                    > div[data-testid="stVerticalBlock"] {
                    box-sizing: border-box !important;
                    display: flex !important;
                    flex: 1 1 auto !important;
                    flex-direction: column !important;
                    min-height: 0 !important;
                    width: 100% !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card-marker-v25)
                    div[data-testid="stElementContainer"]:has(.home-v5-guide-content-v25),
                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card-marker-v25)
                    div[data-testid="stMarkdownContainer"]:has(.home-v5-guide-content-v25) {
                    display: flex !important;
                    flex: 1 1 auto !important;
                    min-height: 0 !important;
                    width: 100% !important;
                }

                .home-v5-guide-content-v25 {
                    box-sizing: border-box !important;
                    display: flex !important;
                    flex: 1 1 auto !important;
                    flex-direction: column !important;
                    min-height: 0 !important;
                    width: 100% !important;
                }

                .home-v5-guide-copy-v25 {
                    flex: 1 1 auto !important;
                    min-height: 6.15rem !important;
                }

                .home-v5-guide-micro-v25 {
                    margin-top: auto !important;
                    padding-top: 0.7rem !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card-marker-v25)
                    div[data-testid="stElementContainer"]:has(.stButton) {
                    flex: 0 0 auto !important;
                    margin-top: auto !important;
                    padding-top: 0.62rem !important;
                    width: 100% !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card-marker-v25) .stButton {
                    margin-top: 0 !important;
                    padding-top: 0 !important;
                    width: 100% !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card-marker-v25) .stButton button {
                    height: 52px !important;
                    max-height: 52px !important;
                    min-height: 52px !important;
                    width: 100% !important;
                }

                @media (max-width: 1180px) {
                    div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card-marker-v25) {
                        min-height: 386px !important;
                    }
                }

                @media (max-width: 760px) {
                    div[data-testid="stHorizontalBlock"]:has(.home-v5-guide-card-marker-v25)
                        > div[data-testid="stColumn"] {
                        flex: 1 1 100% !important;
                        width: 100% !important;
                    }

                    div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card-marker-v25) {
                        height: auto !important;
                        max-height: none !important;
                        min-height: 0 !important;
                    }

                    .home-v5-guide-copy-v25 {
                        min-height: 0 !important;
                    }
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-research-marker-v25) {
                    background:
                        radial-gradient(circle at 88% 10%, rgba(66,165,245,0.17), transparent 26%),
                        radial-gradient(circle at 12% 88%, rgba(229,57,53,0.13), transparent 24%),
                        linear-gradient(145deg, rgba(18,27,44,0.98), rgba(10,18,31,0.99));
                    border: 1px solid rgba(98, 139, 210, 0.28) !important;
                    border-radius: 22px !important;
                    box-shadow: 0 20px 44px rgba(1,8,23,0.34), inset 0 1px 0 rgba(255,255,255,0.04);
                    overflow: hidden;
                    position: relative;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-research-marker-v25)::before {
                    animation: homeV5ResearchAura 12s ease-in-out infinite;
                    background: linear-gradient(135deg, rgba(229,57,53,0.16), rgba(255,152,0,0.10), rgba(66,165,245,0.17));
                    border-radius: 50%;
                    content: '';
                    filter: blur(28px);
                    height: 270px;
                    pointer-events: none;
                    position: absolute;
                    right: -80px;
                    top: -120px;
                    width: 360px;
                    z-index: 0;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-research-marker-v25)
                    > div[data-testid="stVerticalBlock"] {
                    gap: 0.55rem;
                    position: relative;
                    z-index: 1;
                }

                .home-v5-research-marker-v25 { display: none; }

                .home-v5-research-hero-v25 {
                    align-items: center;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 1rem;
                    justify-content: space-between;
                    margin-bottom: 0.45rem;
                }

                .home-v5-research-identity-v25 {
                    align-items: center;
                    display: flex;
                    gap: 0.85rem;
                    min-width: min(100%, 520px);
                }

                .home-v5-research-icon-v25 {
                    align-items: center;
                    background: linear-gradient(135deg, #B71C1C, #E53935 48%, #42A5F5);
                    border: 1px solid rgba(255,255,255,0.12);
                    border-radius: 17px;
                    box-shadow: 0 12px 28px rgba(229,57,53,0.22);
                    color: #FFFFFF;
                    display: inline-flex;
                    flex: 0 0 54px;
                    font-size: 1.35rem;
                    height: 54px;
                    justify-content: center;
                    width: 54px;
                }

                .home-v5-research-title-v25 {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: clamp(1.08rem, 2vw, 1.34rem);
                    font-weight: 800;
                    line-height: 1.32;
                }

                .home-v5-research-subtitle-v25 {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.74rem;
                    line-height: 1.5;
                    margin-top: 0.3rem;
                }

                .home-v5-research-status-v25 {
                    align-items: center;
                    background: rgba(76,175,80,0.11);
                    border: 1px solid rgba(76,175,80,0.32);
                    border-radius: 999px;
                    color: #81C784;
                    display: inline-flex;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.7rem;
                    font-weight: 800;
                    gap: 0.42rem;
                    padding: 0.44rem 0.68rem;
                    white-space: nowrap;
                }

                .home-v5-research-status-v25::before {
                    background: #4CAF50;
                    border-radius: 50%;
                    box-shadow: 0 0 0 5px rgba(76,175,80,0.12);
                    content: '';
                    height: 8px;
                    width: 8px;
                }

                .home-v5-research-grid-v25 {
                    display: grid;
                    gap: 0.72rem;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    margin: 0.65rem 0 0.35rem;
                }

                .home-v5-research-tile-v25 {
                    background: linear-gradient(145deg, rgba(26,37,57,0.82), rgba(13,22,36,0.88));
                    border: 1px solid color-mix(in srgb, var(--home-v5-research-accent, #42A5F5) 35%, rgba(148,163,184,0.16));
                    border-radius: 15px;
                    min-height: 104px;
                    overflow: hidden;
                    padding: 0.82rem 0.88rem;
                    position: relative;
                    transition: border-color 0.25s ease, box-shadow 0.25s ease, transform 0.25s ease;
                }

                .home-v5-research-tile-v25::after {
                    background: linear-gradient(135deg, color-mix(in srgb, var(--home-v5-research-accent, #42A5F5) 13%, transparent), transparent 66%);
                    content: '';
                    inset: 0;
                    pointer-events: none;
                    position: absolute;
                }

                .home-v5-research-tile-v25:hover {
                    border-color: color-mix(in srgb, var(--home-v5-research-accent, #42A5F5) 75%, white 25%);
                    box-shadow: 0 14px 26px color-mix(in srgb, var(--home-v5-research-accent, #42A5F5) 14%, rgba(2,8,23,0.25));
                    transform: translateY(-4px);
                }

                .home-v5-research-tile-label-v25 {
                    color: var(--app-muted);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.65rem;
                    font-weight: 800;
                    letter-spacing: 0.08em;
                    position: relative;
                    text-transform: uppercase;
                    z-index: 1;
                }

                .home-v5-research-tile-value-v25 {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.8rem;
                    font-weight: 750;
                    line-height: 1.48;
                    margin-top: 0.38rem;
                    position: relative;
                    z-index: 1;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-research-marker-v25) [data-testid="stExpander"] {
                    background: rgba(15,23,42,0.64);
                    border: 1px solid rgba(148,163,184,0.16);
                    border-radius: 14px;
                    overflow: hidden;
                }

                div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-research-marker-v25) [data-testid="stExpander"] summary {
                    color: var(--app-text);
                    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                    font-size: 0.76rem;
                    font-weight: 800;
                }

                .home-v5-method-flow-v25 {
                    display: grid;
                    gap: 0.55rem;
                    grid-template-columns: repeat(4, minmax(0, 1fr));
                    margin: 0.25rem 0 0.2rem;
                }

                .home-v5-method-step-v25 {
                    background: rgba(17,24,39,0.76);
                    border: 1px solid rgba(148,163,184,0.14);
                    border-radius: 12px;
                    color: var(--app-text);
                    font-family: 'Inter', sans-serif;
                    font-size: 0.68rem;
                    font-weight: 700;
                    line-height: 1.45;
                    padding: 0.68rem;
                    text-align: center;
                    transition: background 0.22s ease, border-color 0.22s ease, transform 0.22s ease;
                }

                .home-v5-method-step-v25:hover {
                    background: linear-gradient(135deg, rgba(229,57,53,0.12), rgba(66,165,245,0.12));
                    border-color: rgba(66,165,245,0.34);
                    transform: translateY(-2px);
                }

                @media (max-width: 1040px) {
                    .home-v5-research-grid-v25 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                    .home-v5-method-flow-v25 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                }

                @media (max-width: 760px) {
                    .home-v5-research-grid-v25 { grid-template-columns: 1fr; }
                    .home-v5-method-flow-v25 { grid-template-columns: 1fr; }
                    .home-v5-research-identity-v25 { align-items: flex-start; }
                }

                @media (prefers-reduced-motion: reduce) {
                    div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-guide-card-marker-v25)::before,
                    .home-v5-guide-icon-v25,
                    div[data-testid="stVerticalBlockBorderWrapper"]:has(.home-v5-research-marker-v25)::before {
                        animation: none !important;
                    }
                }

            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        st.error("Gaya halaman Beranda belum dapat dimuat.")


def _normalize_platform(value: Any) -> str:
    """Normalisasi variasi nama platform ke tiga platform penelitian."""
    try:
        raw = str(value or "").strip().lower().lstrip("'")
        aliases = {
            "x": "twitter",
            "twitter/x": "twitter",
            "twitter": "twitter",
            "ig": "instagram",
            "instagram": "instagram",
            "tik tok": "tiktok",
            "tiktok": "tiktok",
        }
        return aliases.get(raw, raw)
    except Exception:
        return ""


def _normalize_sentiment(value: Any) -> str:
    """Normalisasi label sentimen Indonesia, Inggris, dan label model."""
    try:
        raw = str(value or "").strip().lower().lstrip("'")
        aliases = {
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
        return aliases.get(raw, "neutral")
    except Exception:
        return "neutral"


def _find_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    """Cari nama kolom pertama yang cocok tanpa membedakan kapitalisasi."""
    try:
        columns = {str(column).strip().lower(): str(column) for column in df.columns}
        for alias in aliases:
            if alias.lower() in columns:
                return columns[alias.lower()]
        return None
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def _prepare_sentiment_dataframe(
    df: pd.DataFrame,
    layanan: str = "IndiHome",
) -> pd.DataFrame:
    """Validasi dan normalisasi dataset sentimen untuk kebutuhan Beranda."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError(f"Dataset sentimen {layanan} kosong atau tidak valid.")

    platform_col = _find_column(
        df,
        ["platform", "specific_resource_type", "source_platform"],
    )
    sentiment_col = _find_column(
        df,
        ["predicted_sentiment", "sentiment", "label", "final_sentiment"],
    )
    username_col = _find_column(df, ["username", "user", "author", "screen_name"])
    date_col = _find_column(
        df,
        ["date_created", "date", "created_at", "timestamp", "datetime"],
    )
    content_col = _find_column(
        df,
        ["content", "text", "full_text", "comment", "cleaned_text"],
    )

    if platform_col is None:
        raise ValueError(f"Kolom platform {layanan} tidak ditemukan.")
    if sentiment_col is None:
        raise ValueError(f"Kolom sentimen {layanan} tidak ditemukan.")

    result = pd.DataFrame(
        {
            "platform": df[platform_col].apply(_normalize_platform),
            "sentiment": df[sentiment_col].apply(_normalize_sentiment),
            "username": (
                df[username_col].astype(str).str.strip().str.lstrip("'").str.lstrip("@")
                if username_col is not None
                else pd.Series([""] * len(df), index=df.index, dtype="object")
            ),
            "date": (
                pd.to_datetime(df[date_col], errors="coerce")
                if date_col is not None
                else pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
            ),
            "content": (
                df[content_col].astype(str)
                if content_col is not None
                else pd.Series([""] * len(df), index=df.index, dtype="object")
            ),
        }
    )
    result["layanan"] = str(layanan).strip().title().replace("Indihome", "IndiHome").replace("Indibiz", "IndiBiz")
    result = result[
        result["platform"].isin(PLATFORM_ORDER)
        & result["sentiment"].isin(SENTIMENT_ORDER)
    ].copy()
    if result.empty:
        raise ValueError(
            f"Tidak ada data {layanan} yang valid untuk Twitter/X, Instagram, atau TikTok."
        )
    return result.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_indihome_data() -> pd.DataFrame:
    """Muat data IndiHome untuk Beranda dengan fallback dummy realistis."""
    try:
        loaded = load_sentiment_data("IndiHome")
        if (
            not isinstance(loaded, pd.DataFrame)
            or loaded.empty
            or not sentiment_file_exists("IndiHome")
        ):
            loaded = get_dummy_sentiment_data("IndiHome")
        prepared = _prepare_sentiment_dataframe(loaded, "IndiHome")
        if prepared.empty:
            raise ValueError("Hasil normalisasi IndiHome kosong.")
        return prepared
    except Exception as error:
        # Tidak memakai LOGGER.exception karena traceback panjang membingungkan
        # pengguna nonteknis dan bukan error fatal untuk halaman.
        LOGGER.warning("Fallback data IndiHome di Beranda digunakan: %s", error)
        st.warning("Data IndiHome aktual belum valid. Beranda memakai data dummy sementara.")
        try:
            fallback = get_dummy_sentiment_data("IndiHome")
            prepared = _prepare_sentiment_dataframe(fallback, "IndiHome")
            if not prepared.empty:
                return prepared
        except Exception as fallback_error:
            LOGGER.warning("Fallback kedua IndiHome gagal: %s", fallback_error)
        return pd.DataFrame(
            [
                {
                    "platform": "twitter",
                    "sentiment": "neutral",
                    "username": "pengguna",
                    "date": pd.Timestamp("2025-11-01"),
                    "content": "Data sementara IndiHome",
                    "layanan": "IndiHome",
                }
            ]
        )


@st.cache_data(show_spinner=False)
def load_indibiz_data() -> pd.DataFrame:
    """Muat data IndiBiz untuk Beranda dengan fallback dummy realistis."""
    try:
        loaded = load_indibiz_sentiment()
        if not sentiment_file_exists("IndiBiz"):
            loaded = get_dummy_indibiz_sentiment()
        return _prepare_sentiment_dataframe(loaded, "IndiBiz")
    except Exception as error:
        LOGGER.exception("Gagal memuat data IndiBiz di Beranda: %s", error)
        st.error("Data IndiBiz gagal dimuat. Beranda memakai data dummy IndiBiz.")
        try:
            return _prepare_sentiment_dataframe(
                get_dummy_indibiz_sentiment(), "IndiBiz"
            )
        except Exception:
            return pd.DataFrame(
                columns=["platform", "sentiment", "username", "date", "content", "layanan"]
            )


@st.cache_data(show_spinner=False)
def load_telkomsel_data() -> pd.DataFrame:
    """Muat data Telkomsel untuk Beranda dengan fallback dummy realistis."""
    try:
        loaded = load_telkomsel_sentiment()
        if not sentiment_file_exists("Telkomsel"):
            loaded = get_dummy_sentiment_data("Telkomsel")
        return _prepare_sentiment_dataframe(loaded, "Telkomsel")
    except Exception as error:
        LOGGER.exception("Gagal memuat data Telkomsel di Beranda: %s", error)
        st.error("Data Telkomsel gagal dimuat. Beranda memakai data dummy Telkomsel.")
        try:
            return _prepare_sentiment_dataframe(
                get_dummy_sentiment_data("Telkomsel"), "Telkomsel"
            )
        except Exception:
            return pd.DataFrame(
                columns=["platform", "sentiment", "username", "date", "content", "layanan"]
            )


@st.cache_data(show_spinner=False)
def load_all_data() -> pd.DataFrame:
    """Gabungkan IndiHome, IndiBiz, dan Telkomsel memakai pd.concat()."""
    try:
        df_indihome = load_indihome_data()
        df_indibiz = load_indibiz_data()
        df_telkomsel = load_telkomsel_data()
        df_all = pd.concat(
            [df_indihome, df_indibiz, df_telkomsel],
            ignore_index=True,
        )
        if df_all.empty:
            raise ValueError("Gabungan data tiga layanan kosong.")
        return df_all.reset_index(drop=True)
    except Exception as error:
        LOGGER.exception("Gagal menggabungkan data tiga layanan: %s", error)
        st.error("Data gabungan gagal disiapkan. Beranda menggunakan fallback dummy.")
        frames = []
        for service_name, dummy_frame in (
            ("IndiHome", get_dummy_sentiment_data("IndiHome")),
            ("IndiBiz", get_dummy_indibiz_sentiment()),
            ("Telkomsel", get_dummy_sentiment_data("Telkomsel")),
        ):
            try:
                frames.append(_prepare_sentiment_dataframe(dummy_frame, service_name))
            except Exception:
                continue
        if not frames:
            return pd.DataFrame(
                columns=["platform", "sentiment", "username", "date", "content", "layanan"]
            )
        return pd.concat(frames, ignore_index=True)


def _load_home_sentiment_data() -> tuple[pd.DataFrame, bool, str]:
    """Kompatibilitas loader lama: mengembalikan data IndiHome."""
    dataframe = load_indihome_data()
    is_real = bool(sentiment_file_exists("IndiHome"))
    return dataframe, is_real, "Data Aktual" if is_real else "Data Dummy"


def _normalize_username(value: Any) -> str:
    """Bersihkan username dari apostrof, spasi, dan awalan @."""
    try:
        return str(value or "").strip().lstrip("'").strip().lstrip("@").strip()
    except Exception:
        return ""


def _is_brand_account(username: str) -> bool:
    """Tentukan apakah username merupakan akun brand penelitian."""
    try:
        normalized = "".join(character for character in username.lower() if character.isalnum())
        return normalized in BRAND_ALIASES
    except Exception:
        return False


@st.cache_data(show_spinner=False)
def _prepare_influencer_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Hitung degree, interaksi, followers, dan kategori influencer dari edge list."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError("Dataset SNA kosong atau tidak valid.")

    required = {
        "source": _find_column(df, ["source", "vertex1", "from_username", "user_from"]),
        "target": _find_column(df, ["target", "vertex2", "to_username", "user_to"]),
        "platform": _find_column(df, ["platform", "specific_resource_type"]),
        "followers": _find_column(df, ["followers", "follower_count", "followers_count"]),
    }
    missing = [name for name, column in required.items() if column is None]
    if missing:
        raise ValueError(f"Kolom SNA belum lengkap: {', '.join(missing)}.")

    work = pd.DataFrame(
        {
            "source": df[required["source"]].apply(_normalize_username),
            "target": df[required["target"]].apply(_normalize_username),
            "platform": df[required["platform"]].apply(_normalize_platform),
            "followers": pd.to_numeric(df[required["followers"]], errors="coerce").fillna(0),
        }
    )
    invalid = {"", "nan", "none", "null"}
    work = work[
        ~work["source"].str.lower().isin(invalid)
        & ~work["target"].str.lower().isin(invalid)
        & work["platform"].isin(PLATFORM_ORDER)
    ].copy()
    if work.empty:
        raise ValueError("Edge SNA yang valid tidak tersedia.")

    source_stats = (
        work.groupby("source", as_index=False)
        .agg(
            out_degree=("target", "nunique"),
            outgoing_interactions=("target", "size"),
            followers=("followers", "max"),
            platform=("platform", "first"),
        )
        .rename(columns={"source": "username"})
    )
    target_stats = (
        work.groupby("target", as_index=False)
        .agg(
            in_degree=("source", "nunique"),
            incoming_interactions=("source", "size"),
            target_platform=("platform", "first"),
        )
        .rename(columns={"target": "username"})
    )
    nodes = source_stats.merge(target_stats, on="username", how="outer")
    nodes["platform"] = nodes["platform"].fillna(nodes["target_platform"])
    nodes["followers"] = pd.to_numeric(nodes["followers"], errors="coerce").fillna(0).clip(lower=0)
    nodes["out_degree"] = pd.to_numeric(nodes["out_degree"], errors="coerce").fillna(0).astype(int)
    nodes["in_degree"] = pd.to_numeric(nodes["in_degree"], errors="coerce").fillna(0).astype(int)
    nodes["outgoing_interactions"] = (
        pd.to_numeric(nodes["outgoing_interactions"], errors="coerce").fillna(0).astype(int)
    )
    nodes["incoming_interactions"] = (
        pd.to_numeric(nodes["incoming_interactions"], errors="coerce").fillna(0).astype(int)
    )
    nodes["degree"] = nodes["out_degree"] + nodes["in_degree"]
    nodes["interaksi"] = nodes["outgoing_interactions"] + nodes["incoming_interactions"]
    nodes["followers"] = nodes["followers"].astype(int)
    nodes = nodes[
        nodes["platform"].isin(PLATFORM_ORDER)
        & ~nodes["username"].apply(_is_brand_account)
    ].copy()
    nodes["kategori"] = "Akun Partisipan"

    for platform in PLATFORM_ORDER:
        mask = nodes["platform"] == platform
        subset = nodes.loc[mask]
        if subset.empty:
            continue
        if platform == "twitter":
            threshold = float(subset["degree"].mean())
            nodes.loc[mask & (nodes["degree"] > threshold), "kategori"] = (
                "Structural Influencer"
            )
        else:
            threshold = float(subset["followers"].mean())
            nodes.loc[mask & (nodes["followers"] > threshold), "kategori"] = (
                "Reach Influencer"
            )

    nodes["teridentifikasi"] = nodes["kategori"].isin(
        ["Structural Influencer", "Reach Influencer"]
    )
    nodes = nodes.sort_values(
        ["teridentifikasi", "interaksi", "followers", "username"],
        ascending=[False, False, False, True],
    )
    return nodes[
        [
            "username",
            "platform",
            "followers",
            "interaksi",
            "degree",
            "in_degree",
            "out_degree",
            "kategori",
            "teridentifikasi",
        ]
    ].reset_index(drop=True)


def _load_home_influencer_data() -> tuple[pd.DataFrame, bool, str]:
    """Muat dan olah data SNA, lalu gunakan dummy bila proses gagal."""
    try:
        loaded = load_sna_data()
        prepared = _prepare_influencer_dataframe(loaded)
        is_real = bool(sna_file_exists())
        status = "Data Aktual" if is_real else "Data Dummy"
        return prepared, is_real, status
    except Exception:
        st.error(
            "Data influencer belum dapat dimuat. "
            "Beranda menggunakan data dummy."
        )
        try:
            dummy = _prepare_influencer_dataframe(get_dummy_sna_data())
            return dummy, False, "Data Dummy"
        except Exception:
            columns = [
                "username",
                "platform",
                "followers",
                "interaksi",
                "degree",
                "in_degree",
                "out_degree",
                "kategori",
                "teridentifikasi",
            ]
            return pd.DataFrame(columns=columns), False, "Data Dummy"


def _format_number(value: Any) -> str:
    """Format angka besar menjadi K atau M untuk tabel ringkas."""
    try:
        number = float(value)
        if number >= 1_000_000:
            formatted = f"{number / 1_000_000:.1f}M"
        elif number >= 1_000:
            formatted = f"{number / 1_000:.1f}K"
        else:
            formatted = f"{number:.0f}"
        return formatted.replace(".0K", "K").replace(".0M", "M")
    except Exception:
        return "0"


def _calculate_metrics(
    sentiment_df: pd.DataFrame,
    influencer_df: pd.DataFrame,
) -> dict[str, Any]:
    """Hitung KPI Beranda dari gabungan tiga layanan."""
    try:
        total = int(len(sentiment_df))
        counts = (
            sentiment_df["sentiment"].value_counts()
            if total
            else pd.Series(dtype="int64")
        )
        dominant_key = str(counts.idxmax()) if not counts.empty else "neutral"
        platform_counts = (
            sentiment_df["platform"].value_counts()
            if total
            else pd.Series(dtype="int64")
        )
        top_platform_key = (
            str(platform_counts.idxmax()) if not platform_counts.empty else "twitter"
        )
        valid_users = (
            sentiment_df["username"].astype(str).str.strip()
            if "username" in sentiment_df.columns
            else pd.Series(dtype="object")
        )
        unique_users = int(
            valid_users[~valid_users.str.lower().isin(["", "nan", "none", "null"])].nunique()
        )
        valid_dates = (
            pd.to_datetime(sentiment_df["date"], errors="coerce").dropna()
            if "date" in sentiment_df.columns
            else pd.Series(dtype="datetime64[ns]")
        )
        if valid_dates.empty:
            date_range = "Nov–Des 2025"
        else:
            date_min = valid_dates.min().strftime("%d %b %Y")
            date_max = valid_dates.max().strftime("%d %b %Y")
            date_range = date_min if date_min == date_max else f"{date_min}–{date_max}"

        influencer_count = (
            int(influencer_df["teridentifikasi"].sum())
            if not influencer_df.empty and "teridentifikasi" in influencer_df.columns
            else 0
        )
        services_count = (
            int(sentiment_df["layanan"].nunique())
            if "layanan" in sentiment_df.columns
            else 0
        )
        return {
            "total_data": total,
            "unique_users": unique_users,
            "dominant_sentiment": SENTIMENT_LABELS.get(dominant_key, "Netral"),
            "dominant_color": SENTIMENT_COLORS.get(dominant_key, "#FF9800"),
            "top_platform": PLATFORM_LABELS.get(top_platform_key, top_platform_key.title()),
            "date_range": date_range,
            "services_count": services_count,
            "positive_pct": (int(counts.get("positive", 0)) / total * 100) if total else 0.0,
            "neutral_pct": (int(counts.get("neutral", 0)) / total * 100) if total else 0.0,
            "negative_pct": (int(counts.get("negative", 0)) / total * 100) if total else 0.0,
            "influencer_count": influencer_count,
        }
    except Exception as error:
        LOGGER.exception("Gagal menghitung metrik Beranda: %s", error)
        st.error("Metrik ringkasan belum dapat dihitung.")
        return {
            "total_data": 0,
            "unique_users": 0,
            "dominant_sentiment": "Netral",
            "dominant_color": "#FF9800",
            "top_platform": "Belum tersedia",
            "date_range": "Nov–Des 2025",
            "services_count": 3,
            "positive_pct": 0.0,
            "neutral_pct": 0.0,
            "negative_pct": 0.0,
            "influencer_count": 0,
        }


def _source_badge(label: str, is_real: bool) -> str:
    """Bangun HTML badge status sumber data."""
    css_class = "home-v5-badge-real" if is_real else "home-v5-badge-dummy"
    icon = "●" if is_real else "▲"
    return (
        f'<span class="home-v5-badge {css_class}">'
        f'{icon} {escape(label)}: {"Data Aktual" if is_real else "Data Dummy"}'
        "</span>"
    )


def _render_hero(service_status: dict[str, bool], sna_real: bool) -> None:
    """Render hero dengan ketiga layanan berstatus Ready."""
    try:
        source_badges = "".join(
            _source_badge(service, bool(service_status.get(service, False)))
            for service in ("IndiHome", "IndiBiz", "Telkomsel")
        ) + _source_badge("SNA", sna_real)
        st.markdown(
            f"""
            <div class="home-v5-page">
                <section class="home-v5-hero">
                    <h1><span aria-hidden="true">📊</span> Dashboard Analisis Sentimen &amp; SNA</h1>
                    <p>Layanan Digital PT Telkom Indonesia — 3 Layanan | 3 Platform. Ringkasan ini menggabungkan data IndiHome, IndiBiz, dan Telkomsel untuk mendukung analisis penelitian.</p>
                    <div class="home-v5-badges">
                        <span class="home-v5-badge home-v5-badge-active">✅ IndiHome READY</span>
                        <span class="home-v5-badge home-v5-badge-active">✅ IndiBiz READY</span>
                        <span class="home-v5-badge home-v5-badge-active">✅ Telkomsel READY</span>
                    </div>
                    <div class="home-v5-source-row" style="margin-top:0.7rem;">
                        {source_badges}
                    </div>
                </section>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as error:
        LOGGER.exception("Hero Beranda gagal dirender: %s", error)
        st.error("Hero Beranda belum dapat ditampilkan.")


def _build_metric_card_html(
    label: str,
    value: str,
    subtext: str,
    color: str | None = None,
    variant: str = "default",
) -> str:
    """Bangun HTML kartu metrik yang aman dan dapat disejajarkan oleh CSS Grid."""
    try:
        allowed_colors = {
            "#E53935",
            "#4CAF50",
            "#F44336",
            "#FF9800",
            "#42A5F5",
            "#EF8354",
            "#D71920",
        }
        safe_color = color if color in allowed_colors else "var(--app-text)"
        safe_variant = (
            variant if variant in {"default", "platform", "date"} else "default"
        )
        variant_class_map = {
            "default": "",
            "platform": " home-v5-metric-card--platform",
            "date": " home-v5-metric-card--date",
        }
        variant_class = variant_class_map[safe_variant]

        if safe_variant == "date":
            normalized_value = str(value).replace("—", "–")
            date_parts = [part.strip() for part in normalized_value.split("–", 1)]

            def _format_date_line(date_text: str) -> str:
                tokens = date_text.split()
                if len(tokens) >= 3:
                    main_text = " ".join(tokens[:-1])
                    year_text = tokens[-1]
                    return (
                        '<span class="home-v5-metric-date-line">'
                        f'<span class="home-v5-metric-date-main">{escape(main_text)}</span>'
                        f'<span class="home-v5-metric-date-year">{escape(year_text)}</span>'
                        '</span>'
                    )
                return (
                    '<span class="home-v5-metric-date-line">'
                    f'<span class="home-v5-metric-date-main">{escape(date_text)}</span>'
                    '</span>'
                )

            if len(date_parts) == 2 and all(date_parts):
                value_html = (
                    _format_date_line(date_parts[0])
                    + '<span class="home-v5-metric-date-separator">—</span>'
                    + _format_date_line(date_parts[1])
                )
            else:
                value_html = _format_date_line(str(value))
        else:
            value_html = escape(str(value))

        # HTML sengaja dibuat satu baris tanpa indentasi/baris kosong.
        # Streamlit Markdown dapat menganggap tag HTML kedua dan seterusnya
        # sebagai blok kode apabila terdapat whitespace antartag.
        return (
            f'<div class="home-v5-metric-card{variant_class}" '
            f'style="--home-v5-value-color:{safe_color};">'
            f'<div class="home-v5-metric-label">{escape(label)}</div>'
            '<div class="home-v5-metric-value-wrap">'
            f'<div class="home-v5-metric-value">{value_html}</div>'
            '</div>'
            f'<div class="home-v5-metric-subtext">{escape(subtext)}</div>'
            '</div>'
        )
    except Exception as error:
        LOGGER.exception("HTML kartu metrik gagal dibuat: %s", error)
        return ""


def _render_metric_card(
    label: str,
    value: str,
    subtext: str,
    color: str | None = None,
    variant: str = "default",
) -> None:
    """Render satu kartu metrik; dipertahankan untuk kompatibilitas internal."""
    try:
        st.markdown(
            _build_metric_card_html(label, value, subtext, color, variant),
            unsafe_allow_html=True,
        )
    except Exception as error:
        LOGGER.exception("Kartu metrik gagal dirender: %s", error)
        st.error("Kartu metrik belum dapat ditampilkan.")


def _render_metrics(metrics: dict[str, Any]) -> None:
    """Render lima KPI gabungan dalam grid yang sama lebar dan sama tinggi."""
    try:
        st.markdown(
            '<div class="home-v5-section-title">Ringkasan Utama — 3 Layanan</div>',
            unsafe_allow_html=True,
        )

        cards_html = "".join(
            [
                _build_metric_card_html(
                    "Total Komentar",
                    f"{int(metrics['total_data']):,}".replace(",", "."),
                    "Gabungan 3 layanan",
                    "#E53935",
                ),
                _build_metric_card_html(
                    "Pengguna Unik",
                    f"{int(metrics['unique_users']):,}".replace(",", "."),
                    "Berdasarkan username",
                    "#E53935",
                ),
                _build_metric_card_html(
                    "Sentimen Dominan",
                    str(metrics["dominant_sentiment"]),
                    "Dari seluruh komentar",
                    str(metrics["dominant_color"]),
                ),
                _build_metric_card_html(
                    "Platform Terbanyak",
                    str(metrics["top_platform"]),
                    "Volume komentar tertinggi",
                    "#42A5F5",
                    "platform",
                ),
                _build_metric_card_html(
                    "Rentang Data",
                    str(metrics["date_range"]),
                    "Periode penelitian",
                    "#E53935",
                    "date",
                ),
            ]
        )
        # Grid juga dibuat sebagai satu string HTML rapat agar seluruh kartu
        # dirender sebagai HTML, bukan ditampilkan sebagai teks kode.
        metric_grid_html = f'<div class="home-v5-metric-grid">{cards_html}</div>'
        st.markdown(metric_grid_html, unsafe_allow_html=True)
    except Exception as error:
        LOGGER.exception("KPI Beranda gagal dirender: %s", error)
        st.error("Ringkasan utama belum dapat ditampilkan.")


def _sentiment_counts(sentiment_df: pd.DataFrame) -> list[int]:
    """Ambil jumlah sentimen sesuai urutan warna chart."""
    try:
        counts = sentiment_df["sentiment"].value_counts()
        return [int(counts.get(item, 0)) for item in SENTIMENT_ORDER]
    except Exception:
        return [0, 0, 0]


def _build_donut_chart(
    sentiment_df: pd.DataFrame,
    expanded: bool = False,
) -> go.Figure:
    """Buat donut Plotly gabungan yang interaktif dan beranimasi."""
    values = _sentiment_counts(sentiment_df)
    total = int(sum(values))
    labels = [SENTIMENT_LABELS[item] for item in SENTIMENT_ORDER]
    colors = [SENTIMENT_COLORS[item] for item in SENTIMENT_ORDER]
    text_color = _chart_text_color()

    figure = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.56,
                sort=False,
                direction="clockwise",
                rotation=90,
                pull=[0.018, 0.018, 0.018],
                marker={
                    "colors": colors,
                    "line": {"color": "rgba(255,255,255,0.14)", "width": 2},
                },
                texttemplate="<b>%{percent:.1%}</b>",
                textposition="inside",
                textfont={
                    "family": "Plus Jakarta Sans, Inter, sans-serif",
                    "color": "#FFFFFF",
                    "size": 12,
                },
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    "%{value:,} komentar<br>"
                    "Proporsi %{percent:.1%}<extra></extra>"
                ),
                hoverlabel={
                    "bgcolor": "#141A25",
                    "bordercolor": "rgba(255,255,255,0.18)",
                    "font": {"family": "Inter, sans-serif", "color": "#FFFFFF", "size": 12},
                },
            )
        ]
    )

    figure.update_layout(
        autosize=True,
        height=445 if expanded else 385,
        margin={"l": 8, "r": 8, "t": 24, "b": 58},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, sans-serif", "color": text_color, "size": 11},
        legend={
            "orientation": "h",
            "x": 0.5,
            "xanchor": "center",
            "y": -0.08,
            "font": {"family": "Inter, sans-serif", "color": text_color, "size": 11},
            "bgcolor": "rgba(0,0,0,0)",
            "itemclick": "toggle",
            "itemdoubleclick": "toggleothers",
        },
        annotations=[
            {
                "text": (
                    f"<span style='font-size:20px'><b>{total:,}</b></span>"
                    "<br><span style='font-size:10px;letter-spacing:1px'>KOMENTAR</span>"
                ).replace(",", "."),
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {
                    "family": "Plus Jakarta Sans, Inter, sans-serif",
                    "size": 18,
                    "color": text_color,
                },
                "align": "center",
            }
        ],
        transition={"duration": 520, "easing": "cubic-in-out"},
        uirevision="home_fase9_combined_donut_v19",
    )
    return figure


@st.cache_data(show_spinner=False)
def _prepare_indibiz_home_sentiment_data(df: pd.DataFrame) -> pd.DataFrame:
    """Kompatibilitas: normalisasi data IndiBiz menggunakan skema Beranda baru."""
    return _prepare_sentiment_dataframe(df, "IndiBiz")


def _load_home_indibiz_sentiment_data() -> tuple[pd.DataFrame, bool, str]:
    """Kompatibilitas loader lama: mengembalikan data IndiBiz."""
    dataframe = load_indibiz_data()
    is_real = bool(sentiment_file_exists("IndiBiz"))
    return dataframe, is_real, "Data Aktual" if is_real else "Data Dummy"


def _load_home_telkomsel_sentiment_data() -> tuple[pd.DataFrame, bool, str]:
    """Muat data Telkomsel beserta status sumbernya untuk Beranda."""
    dataframe = load_telkomsel_data()
    is_real = bool(sentiment_file_exists("Telkomsel"))
    return dataframe, is_real, "Data Aktual" if is_real else "Data Dummy"


def _calculate_indibiz_home_metrics(df: pd.DataFrame) -> dict[str, float | int]:
    """Hitung total dan persentase tiga kelas sentimen untuk satu layanan."""
    try:
        total = int(len(df))
        counts = df["sentiment"].value_counts() if total else pd.Series(dtype="int64")
        return {
            "total": total,
            "positive_count": int(counts.get("positive", 0)),
            "neutral_count": int(counts.get("neutral", 0)),
            "negative_count": int(counts.get("negative", 0)),
            "positive_pct": (float(counts.get("positive", 0)) / total * 100) if total else 0.0,
            "neutral_pct": (float(counts.get("neutral", 0)) / total * 100) if total else 0.0,
            "negative_pct": (float(counts.get("negative", 0)) / total * 100) if total else 0.0,
        }
    except Exception as error:
        LOGGER.exception("Gagal menghitung metrik layanan: %s", error)
        return {
            "total": 0,
            "positive_count": 0,
            "neutral_count": 0,
            "negative_count": 0,
            "positive_pct": 0.0,
            "neutral_pct": 0.0,
            "negative_pct": 0.0,
        }


def _build_indibiz_mini_bar_chart(
    metrics: dict[str, float | int],
    accent: str = "#E53935",
    revision_key: str = "home_fase9_service_mini_bar",
) -> go.Figure:
    """Buat mini bar chart transparan untuk kartu satu layanan."""
    labels = ["Positif", "Netral", "Negatif"]
    counts = [
        int(metrics.get("positive_count", 0)),
        int(metrics.get("neutral_count", 0)),
        int(metrics.get("negative_count", 0)),
    ]
    percentages = [
        float(metrics.get("positive_pct", 0.0)),
        float(metrics.get("neutral_pct", 0.0)),
        float(metrics.get("negative_pct", 0.0)),
    ]
    text_color = _chart_text_color()
    maximum = max(counts) if counts else 0

    figure = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=counts,
                marker={
                    "color": [
                        SENTIMENT_COLORS["positive"],
                        SENTIMENT_COLORS["neutral"],
                        SENTIMENT_COLORS["negative"],
                    ],
                    "line": {"width": 0},
                },
                customdata=percentages,
                text=[f"{value:.1f}%" for value in percentages],
                textposition="outside",
                textfont={"color": text_color, "size": 10},
                cliponaxis=False,
                hovertemplate=(
                    "<b>%{x}</b><br>Jumlah: %{y:,}<br>Persentase: "
                    "%{customdata:.1f}%<extra></extra>"
                ),
            )
        ]
    )
    figure.update_layout(
        autosize=True,
        height=190,
        margin={"l": 8, "r": 8, "t": 24, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        bargap=0.38,
        font={"family": "Inter, sans-serif", "color": text_color, "size": 10},
        xaxis={
            "showgrid": False,
            "zeroline": False,
            "tickfont": {"color": text_color, "size": 9},
            "fixedrange": True,
        },
        yaxis={
            "visible": False,
            "showgrid": False,
            "zeroline": False,
            "fixedrange": True,
            "range": [0, max(maximum * 1.32, 1)],
        },
        hoverlabel={
            "bgcolor": "#17171B" if _is_dark_mode() else "#FFFFFF",
            "bordercolor": accent,
            "font": {"color": "#FFFFFF" if _is_dark_mode() else "#111827"},
        },
        transition={"duration": 0},
        uirevision=revision_key,
    )
    return figure


def _service_icon_svg(service_key: str) -> str:
    """Kembalikan ikon SVG ringan untuk setiap kartu layanan."""
    icons = {
        "indihome": """<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><path d='M3 11.5 12 4l9 7.5'></path><path d='M5.5 10.5V20h13v-9.5'></path><path d='M9.5 20v-6h5v6'></path></svg>""",
        "indibiz": """<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><rect x='3' y='7' width='18' height='13' rx='2'></rect><path d='M8 7V5.5A1.5 1.5 0 0 1 9.5 4h5A1.5 1.5 0 0 1 16 5.5V7'></path><path d='M3 12.5c5.2 2.2 12.8 2.2 18 0'></path><path d='M10 13h4'></path></svg>""",
        "telkomsel": """<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><rect x='7' y='2.5' width='10' height='19' rx='2'></rect><path d='M10 5h4M11 18.5h2'></path><path d='M9.5 9.5h5M9.5 12h5M9.5 14.5h3'></path></svg>""",
    }
    return icons.get(service_key, icons["indihome"])


def _open_service_sentiment(service_name: str) -> None:
    """Arahkan pengguna ke halaman Analisis Sentimen layanan terpilih."""
    try:
        st.session_state["selected_page"] = "Analisis Sentimen"
        st.session_state["page"] = "Analisis Sentimen"
        st.session_state["sent_v7_service_selector"] = service_name
        # Minta app.py memindahkan highlight sidebar secara eksplisit pada
        # rerun berikutnya. Jangan menghapus state widget option-menu karena
        # komponen dapat tetap mempertahankan pilihan visual lama di browser.
        st.session_state["_sidebar_force_route"] = "Analisis Sentimen"
        st.rerun()
    except Exception as error:
        LOGGER.exception("Navigasi Analisis Sentimen %s gagal: %s", service_name, error)
        st.error(f"Halaman Analisis Sentimen {service_name} belum dapat dibuka.")


def _render_service_cards(
    indihome_df: pd.DataFrame,
    indibiz_df: pd.DataFrame,
    telkomsel_df: pd.DataFrame,
    service_status: dict[str, bool],
) -> None:
    """Render tiga kartu layanan Ready dengan struktur dan tinggi yang seragam."""
    try:
        st.markdown(
            """
            <div class="home-v5-service-section-head">
                <div>
                    <div class="home-v5-service-section-kicker">Portfolio Layanan</div>
                    <h2 class="home-v5-service-section-title">Status Layanan</h2>
                </div>
                <div class="home-v5-service-section-copy">
                    Ketiga layanan telah aktif dan memakai data sentimen masing-masing.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        services = [
            {
                "name": "IndiHome",
                "key": "indihome",
                "type": "Internet Rumah & Digital Lifestyle",
                "accent": "#E53935",
                "data": indihome_df,
            },
            {
                "name": "IndiBiz",
                "key": "indibiz",
                "type": "Solusi Digital Bisnis",
                "accent": "#EF8354",
                "data": indibiz_df,
            },
            {
                "name": "Telkomsel",
                "key": "telkomsel",
                "type": "Seluler & Layanan Digital",
                "accent": "#D71920",
                "data": telkomsel_df,
            },
        ]
        columns = _service_columns(3, gap="medium")

        for column, service in zip(columns, services):
            metrics = _calculate_indibiz_home_metrics(service["data"])
            source_label = (
                "Data Aktual" if service_status.get(service["name"], False) else "Data Dummy"
            )
            with column:
                with _service_container(f"home_fase9_service_{service['key']}"):
                    st.markdown(
                        f"""
                        <div class="home-v5-service-card-marker home-v5-service-card--{service['key']}"></div>
                        <div class="home-v5-service-head" style="--home-v5-logo-color:{service['accent']};">
                            <div class="home-v5-service-identity">
                                <div class="home-v5-service-logo" aria-hidden="true">{_service_icon_svg(service['key'])}</div>
                                <div>
                                    <div class="home-v5-service-name">{escape(service['name'])}</div>
                                    <div class="home-v5-service-type">{escape(service['type'])}</div>
                                </div>
                            </div>
                            <span class="home-v5-service-status home-v5-service-status--active">✅ Ready</span>
                        </div>
                        <div class="home-v5-service-summary" style="--home-v5-hover-accent:{service['accent']};">
                            <span>Platform tersedia</span>
                            <strong>Twitter/X · Instagram · TikTok</strong>
                        </div>
                        <div class="home-v5-ready-note">Periode data November–Desember 2025 · {escape(source_label)}</div>
                        <div class="home-v5-service-stats">
                            <div class="home-v5-service-stat home-v5-service-stat--data">
                                <div class="home-v5-service-stat-label">Total Komentar</div>
                                <strong>{int(metrics['total']):,}</strong>
                            </div>
                            <div class="home-v5-service-stat home-v5-service-stat--positive">
                                <div class="home-v5-service-stat-label">Positif</div>
                                <strong>{float(metrics['positive_pct']):.1f}%</strong>
                            </div>
                            <div class="home-v5-service-stat home-v5-service-stat--neutral">
                                <div class="home-v5-service-stat-label">Netral</div>
                                <strong>{float(metrics['neutral_pct']):.1f}%</strong>
                            </div>
                            <div class="home-v5-service-stat home-v5-service-stat--negative">
                                <div class="home-v5-service-stat-label">Negatif</div>
                                <strong>{float(metrics['negative_pct']):.1f}%</strong>
                            </div>
                        </div>
                        <div class="home-v5-service-chart-title">
                            Distribusi Sentimen
                            <span>{escape(service['name'])} · {escape(source_label)}</span>
                        </div>
                        """.replace(",", "."),
                        unsafe_allow_html=True,
                    )
                    try:
                        _service_plotly_chart(
                            _build_indibiz_mini_bar_chart(
                                metrics,
                                accent=service["accent"],
                                revision_key=f"home_fase9_{service['key']}_mini_bar",
                            ),
                            config={
                                "displayModeBar": False,
                                "displaylogo": False,
                                "responsive": True,
                                "staticPlot": False,
                                "scrollZoom": False,
                            },
                            key=f"home_fase9_chart_{service['key']}",
                        )
                    except Exception as error:
                        LOGGER.exception("Mini chart %s gagal: %s", service["name"], error)
                        st.error(f"Grafik {service['name']} belum dapat ditampilkan.")

                    st.markdown(
                        '<div class="home-v5-service-footer-anchor"></div>',
                        unsafe_allow_html=True,
                    )
                    if _service_button(
                        f"Buka Analisis {service['name']}",
                        key=f"home_fase9_open_{service['key']}",
                        type="primary",
                    ):
                        _open_service_sentiment(service["name"])
    except Exception as error:
        LOGGER.exception("Gagal merender Status Layanan: %s", error)
        st.error("Status layanan belum dapat ditampilkan.")


def _build_service_comparison_chart(sentiment_df: pd.DataFrame) -> go.Figure:
    """Buat grouped/stacked bar interaktif untuk tiga layanan."""
    service_order = ["IndiHome", "IndiBiz", "Telkomsel"]
    grouped = (
        sentiment_df.groupby(["layanan", "sentiment"])
        .size()
        .unstack(fill_value=0)
        .reindex(index=service_order, columns=SENTIMENT_ORDER, fill_value=0)
    )
    service_totals = grouped.sum(axis=1).replace(0, 1)
    text_color = _chart_text_color()

    def compact_number(value: int) -> str:
        number = int(value)
        if abs(number) >= 1_000_000:
            return f"{number / 1_000_000:.1f}M".replace(".0M", "M")
        if abs(number) >= 1_000:
            return f"{number / 1_000:.1f}K".replace(".0K", "K")
        return str(number)

    figure = go.Figure()
    for sentiment in SENTIMENT_ORDER:
        values = grouped[sentiment].astype(int).tolist()
        shares = (grouped[sentiment] / service_totals * 100).round(1).tolist()
        figure.add_trace(
            go.Bar(
                name=SENTIMENT_LABELS[sentiment],
                x=service_order,
                y=values,
                customdata=shares,
                text=[compact_number(item) if item > 0 else "" for item in values],
                textposition="outside",
                textfont={
                    "family": "Plus Jakarta Sans, Inter, sans-serif",
                    "color": text_color,
                    "size": 10,
                },
                cliponaxis=False,
                marker={
                    "color": SENTIMENT_COLORS[sentiment],
                    "line": {"color": "rgba(255,255,255,0.16)", "width": 1.2},
                },
                hovertemplate=(
                    f"<b>{SENTIMENT_LABELS[sentiment]}</b><br>"
                    "%{x}<br>"
                    "%{y:,} komentar<br>"
                    "%{customdata:.1f}% dari layanan<extra></extra>"
                ),
                hoverlabel={
                    "bgcolor": "#141A25",
                    "bordercolor": SENTIMENT_COLORS[sentiment],
                    "font": {"family": "Inter, sans-serif", "color": "#FFFFFF", "size": 12},
                },
            )
        )

    figure.update_layout(
        barmode="group",
        bargap=0.28,
        bargroupgap=0.10,
        autosize=True,
        height=385,
        margin={"l": 28, "r": 14, "t": 50, "b": 52},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, sans-serif", "color": text_color, "size": 11},
        legend={
            "orientation": "h",
            "x": 0.0,
            "xanchor": "left",
            "y": 1.10,
            "bgcolor": "rgba(0,0,0,0)",
            "itemclick": "toggle",
            "itemdoubleclick": "toggleothers",
        },
        xaxis={
            "title": None,
            "showgrid": False,
            "zeroline": False,
            "tickfont": {
                "family": "Plus Jakarta Sans, Inter, sans-serif",
                "color": text_color,
                "size": 11,
            },
        },
        yaxis={
            "title": {"text": "Jumlah Komentar", "font": {"color": text_color, "size": 11}},
            "showgrid": True,
            "gridcolor": "rgba(148,163,184,0.13)",
            "griddash": "dot",
            "zeroline": False,
            "tickfont": {"color": text_color, "size": 10},
            "rangemode": "tozero",
        },
        hovermode="x unified",
        hoverlabel={
            "bgcolor": "#141A25",
            "bordercolor": "rgba(66,165,245,0.42)",
            "font": {"family": "Inter, sans-serif", "color": "#FFFFFF", "size": 11},
        },
        transition={"duration": 520, "easing": "cubic-in-out"},
        uirevision="home_fase9_service_comparison_v19",
    )
    return figure


def _build_platform_chart(
    sentiment_df: pd.DataFrame,
    expanded: bool = False,
) -> go.Figure:
    """Buat grouped bar platform gabungan tiga layanan dengan tampilan lebih atraktif."""
    grouped = (
        sentiment_df.groupby(["platform", "sentiment"])
        .size()
        .unstack(fill_value=0)
        .reindex(index=PLATFORM_ORDER, columns=SENTIMENT_ORDER, fill_value=0)
    )

    platform_totals = grouped.sum(axis=1).replace(0, 1)
    platform_labels = [PLATFORM_LABELS[item] for item in PLATFORM_ORDER]
    text_color = _chart_text_color()
    grid_color = "rgba(148,163,184,0.12)"
    figure = go.Figure()

    for sentiment in SENTIMENT_ORDER:
        values = grouped[sentiment].astype(int).tolist()
        shares = (grouped[sentiment] / platform_totals * 100).round(1).tolist()
        figure.add_trace(
            go.Bar(
                name=SENTIMENT_LABELS[sentiment],
                y=platform_labels,
                x=values,
                customdata=shares,
                orientation="h",
                marker={
                    "color": SENTIMENT_COLORS[sentiment],
                    "line": {"color": "rgba(255,255,255,0.10)", "width": 1.0},
                    "opacity": 0.96,
                },
                text=[_format_number(item) if int(item) > 0 else "" for item in values],
                textfont={"family": "Plus Jakarta Sans, Inter, sans-serif", "size": 11, "color": text_color},
                textposition="outside",
                cliponaxis=False,
                hovertemplate=(
                    f"<b>{SENTIMENT_LABELS[sentiment]}</b><br>"
                    "%{y}: %{x:,} komentar<br>"
                    "Porsi platform: %{customdata:.1f}%<extra></extra>"
                ),
            )
        )

    figure.update_layout(
        barmode="group",
        bargap=0.23,
        bargroupgap=0.12,
        autosize=True,
        height=680 if expanded else 500,
        margin={"l": 22, "r": 22, "t": 38, "b": 84},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, sans-serif", "color": text_color, "size": 12},
        hoverlabel={
            "bgcolor": "rgba(15,23,42,0.96)",
            "bordercolor": "rgba(255,255,255,0.12)",
            "font": {"family": "Inter, sans-serif", "size": 12, "color": "#F8FAFC"},
        },
        legend={
            "orientation": "h",
            "x": 0.5,
            "xanchor": "center",
            "y": 1.11,
            "yanchor": "bottom",
            "title": None,
            "bgcolor": "rgba(0,0,0,0)",
            "font": {"size": 11, "color": text_color},
        },
        xaxis={
            "title": {"text": "Jumlah Komentar", "font": {"color": text_color, "size": 11}},
            "showgrid": True,
            "gridcolor": grid_color,
            "gridwidth": 1,
            "zeroline": False,
            "tickfont": {"color": text_color, "size": 11},
        },
        yaxis={
            "title": None,
            "showgrid": False,
            "zeroline": False,
            "tickfont": {"color": text_color, "size": 13},
            "categoryorder": "array",
            "categoryarray": platform_labels,
        },
        hovermode="y unified",
        transition={"duration": 280, "easing": "cubic-in-out"},
        uirevision="home_fase9_platform_chart_v21",
    )
    return figure

def _render_platform_fallback(sentiment_df: pd.DataFrame) -> None:
    """Tampilkan tabel ringkas jika chart platform gagal dirender."""
    try:
        fallback = (
            sentiment_df.groupby(["platform", "sentiment"])
            .size()
            .unstack(fill_value=0)
            .reindex(index=PLATFORM_ORDER, columns=SENTIMENT_ORDER, fill_value=0)
            .reset_index()
        )
        fallback["platform"] = fallback["platform"].map(PLATFORM_LABELS)
        fallback = fallback.rename(
            columns={
                "platform": "Platform",
                "positive": "Positif",
                "neutral": "Netral",
                "negative": "Negatif",
            }
        )
        st.dataframe(fallback, hide_index=True, use_container_width=True)
    except Exception:
        st.error("Ringkasan distribusi platform belum dapat ditampilkan.")


def _platform_influencer_sort_columns(platform: str) -> tuple[list[str], list[bool]]:
    """Tentukan prioritas ranking influencer untuk setiap platform."""
    if platform == "twitter":
        return ["interaksi", "degree", "followers", "username"], [False, False, False, True]
    return ["interaksi", "followers", "degree", "username"], [False, False, False, True]


def _category_pill(category: Any) -> str:
    """Bangun badge kategori influencer yang aman untuk tabel HTML."""
    raw = str(category or "").strip()
    normalized = raw.lower()
    if "structural" in normalized:
        css_class = "home-v5-category-pill--structural"
        label = "Influencer Struktural"
    elif "reach" in normalized:
        css_class = "home-v5-category-pill--reach"
        label = "Influencer Jangkauan"
    else:
        css_class = "home-v5-category-pill--participant"
        label = "Akun Partisipan"
    return f'<span class="home-v5-category-pill {css_class}">{escape(label)}</span>'


def _render_platform_influencer_table(
    influencer_df: pd.DataFrame,
    platform: str,
) -> int:
    """Render Top 5 satu platform dalam tabel visual interaktif."""
    try:
        platform_data = influencer_df[
            influencer_df["platform"].astype(str).str.lower().eq(platform)
        ].copy()
        if platform_data.empty:
            st.info(f"Data influencer {PLATFORM_LABELS[platform]} belum tersedia.")
            return 0

        identified = platform_data[platform_data["teridentifikasi"]].copy()
        ranking_source = identified if not identified.empty else platform_data
        sort_columns, ascending = _platform_influencer_sort_columns(platform)
        top_five = ranking_source.sort_values(sort_columns, ascending=ascending).head(5)

        if top_five.empty:
            st.info(f"Belum ada akun {PLATFORM_LABELS[platform]} yang dapat diranking.")
            return 0

        rule = (
            "Ranking utama: interaksi dan degree jaringan."
            if platform == "twitter"
            else "Ranking utama: interaksi dan jumlah followers."
        )
        fallback_note = "" if not identified.empty else " · memakai akun paling aktif"
        accent_map = {"twitter": "#42A5F5", "instagram": "#E1306C", "tiktok": "#25F4EE"}
        accent = accent_map.get(platform, "#42A5F5")
        max_interactions = max(float(top_five["interaksi"].max()), 1.0)

        rows: list[str] = []
        for rank, row in enumerate(top_five.itertuples(index=False), start=1):
            username = escape(str(row.username))
            followers = escape(_format_number(row.followers))
            interactions = escape(_format_number(row.interaksi))
            category = _category_pill(row.kategori)
            progress = max(4.0, min(100.0, float(row.interaksi) / max_interactions * 100.0))
            rank_class = f" home-v5-rank-medal-v23--{rank}" if rank <= 3 else ""
            rows.append(
                "<tr>"
                f'<td><span class="home-v5-rank-medal-v23{rank_class}">{rank}</span></td>'
                f'<td><div class="home-v5-account-cell-v23"><span class="home-v5-account-avatar-v23">@</span><strong>@{username}</strong></div></td>'
                f'<td><span class="home-v5-number-chip-v23">{followers}</span></td>'
                f'<td><div class="home-v5-interaction-metric-v23"><strong>{interactions}</strong><span class="home-v5-interaction-track-v23"><i style="width:{progress:.1f}%;"></i></span></div></td>'
                f'<td>{category}</td>'
                "</tr>"
            )

        panel_html = (
            f'<div class="home-v5-influencer-panel-v23" style="--home-v5-table-accent:{accent};">'
            '<div class="home-v5-influencer-meta-v23">'
            f'<span class="home-v5-influencer-platform-chip-v23">{escape(PLATFORM_LABELS[platform])}</span>'
            f'<span class="home-v5-influencer-rule-v23">{escape(rule + fallback_note)}</span>'
            '</div>'
            '<div class="home-v5-influencer-table-wrap-v23">'
            '<table class="home-v5-influencer-table-v23">'
            '<thead><tr><th>Peringkat</th><th>Akun</th><th>Followers</th><th>Interaksi</th><th>Kategori</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody>'
            '</table></div></div>'
        )
        st.markdown(panel_html, unsafe_allow_html=True)
        return int(len(top_five))
    except Exception as error:
        LOGGER.exception(
            "Gagal merender Top 5 influencer platform %s: %s", platform, error
        )
        st.error(
            f"Top 5 influencer {PLATFORM_LABELS.get(platform, platform)} belum dapat ditampilkan."
        )
        return 0

def _queue_influencer_platform_loading() -> None:
    """Siapkan overlay loading custom sebelum filter platform influencer dirender ulang."""
    try:
        selected_label = str(
            st.session_state.get("home_v5_influencer_platform_focus", "Semua")
        ).strip() or "Semua"
        label_target = (
            "semua platform"
            if selected_label == "Semua"
            else f"platform {selected_label}"
        )
        st.session_state[STATE_INFLUENCER_FILTER_LOADING] = (
            f"Menyiapkan Top 5 Influencer {label_target}..."
        )
    except Exception:
        st.session_state.pop(STATE_INFLUENCER_FILTER_LOADING, None)


# HOTFIX V4.2: tiga tabel influencer platform selalu dirender terpisah dan sekaligus.
def _render_influencer_tables(influencer_df: pd.DataFrame, is_real: bool) -> None:
    """Render ranking influencer interaktif untuk Twitter/X, Instagram, dan TikTok."""
    filter_loading_handle = None
    filter_loading_started = 0.0
    try:
        loading_label = st.session_state.pop(STATE_INFLUENCER_FILTER_LOADING, None)
        if loading_label:
            filter_loading_handle = mulai_loading_aksi(str(loading_label))
            filter_loading_started = time.monotonic()

        if influencer_df.empty:
            st.info("Data influencer belum tersedia.")
            return

        source_label = "Data Aktual" if is_real else "Data Dummy"
        platform_sections = [
            ("twitter", "Twitter/X", "#42A5F5", "X"),
            ("instagram", "Instagram", "#E1306C", "IG"),
            ("tiktok", "TikTok", "#25F4EE", "TT"),
        ]

        summary_cards: list[str] = []
        for platform, label, accent, short_icon in platform_sections:
            platform_data = influencer_df[
                influencer_df["platform"].astype(str).str.lower().eq(platform)
            ].copy()
            available_count = int(len(platform_data))
            leader = "Belum tersedia"
            if not platform_data.empty:
                sort_columns, ascending = _platform_influencer_sort_columns(platform)
                leader_row = platform_data.sort_values(sort_columns, ascending=ascending).iloc[0]
                leader = f"@{str(leader_row.get('username', '')).strip()} · {_format_number(leader_row.get('interaksi', 0))} interaksi"
            available_label = f"{available_count:,}".replace(",", ".")
            summary_cards.append(
                f'<div class="home-v5-influencer-summary-card-v23" style="--home-v5-inf-accent:{accent};">'
                '<div class="home-v5-influencer-summary-top-v23">'
                f'<span class="home-v5-influencer-summary-icon-v23">{short_icon}</span>'
                '<div>'
                f'<div class="home-v5-influencer-summary-label-v23">{escape(label)}</div>'
                f'<div class="home-v5-influencer-summary-number-v23">{available_label} akun</div>'
                '</div></div>'
                f'<div class="home-v5-influencer-summary-leader-v23">Teratas · {escape(leader)}</div>'
                '</div>'
            )

        overview_html = (
            '<div class="home-v5-influencer-overview-v23">'
            '<div class="home-v5-influencer-overview-head-v23">'
            '<div>'
            '<div class="home-v5-influencer-eyebrow-v23">Influence Intelligence</div>'
            '<div class="home-v5-influencer-overview-title-v23">Peta aktor paling berpengaruh lintas platform</div>'
            '<div class="home-v5-influencer-overview-copy-v23">Ranking menggabungkan kekuatan interaksi, posisi jaringan, dan potensi jangkauan. Pilih platform untuk memfokuskan tabel tanpa kehilangan konteks perbandingan.</div>'
            '</div>'
            f'<span class="home-v5-influencer-live-v23">{escape(source_label)}</span>'
            '</div>'
            f'<div class="home-v5-influencer-summary-grid-v23">{"".join(summary_cards)}</div>'
            '</div>'
        )

        with _service_container("home_v5_influencer_section_card"):
            st.markdown('<div class="home-v5-influencer-section-marker"></div>', unsafe_allow_html=True)
            st.markdown(overview_html, unsafe_allow_html=True)

            focus_label = st.radio(
                "Fokus platform influencer",
                ["Semua", "Twitter/X", "Instagram", "TikTok"],
                horizontal=True,
                key="home_v5_influencer_platform_focus",
                label_visibility="collapsed",
                help="Pilih Semua untuk menampilkan tiga ranking, atau pilih satu platform untuk fokus.",
                on_change=_queue_influencer_platform_loading,
            )
            focus_map = {"Twitter/X": "twitter", "Instagram": "instagram", "TikTok": "tiktok"}
            selected_platform = focus_map.get(str(focus_label))
            visible_sections = [
                item for item in platform_sections
                if selected_platform is None or item[0] == selected_platform
            ]

            for index, (platform, label, accent, short_icon) in enumerate(visible_sections):
                available_count = int(
                    influencer_df["platform"].astype(str).str.lower().eq(platform).sum()
                )
                available_label = f"{available_count:,}".replace(",", ".")
                heading_html = (
                    f'<div class="home-v5-platform-influencer-heading-v23" style="--home-v5-platform-accent:{accent};">'
                    f'<span class="home-v5-platform-influencer-badge-v23">{short_icon}</span>'
                    '<div>'
                    f'<strong>Top 5 Influencer {escape(label)}</strong>'
                    f'<span>{available_label} akun tersedia · arahkan kursor ke baris untuk menyorot kandidat</span>'
                    '</div></div>'
                )
                st.markdown(heading_html, unsafe_allow_html=True)
                _render_platform_influencer_table(influencer_df, platform)

                if index < len(visible_sections) - 1:
                    st.markdown('<div class="home-v5-influencer-divider-v23"></div>', unsafe_allow_html=True)
    except Exception as error:
        LOGGER.exception("Gagal merender tabel influencer per platform: %s", error)
        st.error("Tabel Top 5 Influencer per platform belum dapat ditampilkan.")
    finally:
        if filter_loading_handle is not None:
            try:
                elapsed = time.monotonic() - filter_loading_started
                remaining = INFLUENCER_FILTER_MIN_SECONDS - elapsed
                if remaining > 0:
                    time.sleep(remaining)
            except Exception:
                pass
            selesaikan_loading_aksi(filter_loading_handle)

def _render_combined_chart_fullscreen(
    title: str,
    figure: go.Figure,
    chart_type: str,
    chart_key: str,
    filename: str,
) -> None:
    """Tampilkan satu chart gabungan dalam dialog fullscreen yang stabil."""
    try:
        st.markdown(
            (
                '<div class="home-v5-fullscreen-heading">'
                f'<div class="home-v5-fullscreen-title">{escape(title)}</div>'
                '<div class="home-v5-fullscreen-hint">Arahkan kursor untuk melihat detail dan klik legenda untuk menampilkan atau menyembunyikan kelas sentimen.</div>'
                '</div>'
            ),
            unsafe_allow_html=True,
        )

        fullscreen_figure = go.Figure(figure)
        if chart_type == "donut":
            fullscreen_figure.update_layout(
                autosize=True,
                height=700,
                margin={"l": 28, "r": 28, "t": 18, "b": 66},
                legend={
                    "orientation": "h",
                    "x": 0.5,
                    "xanchor": "center",
                    "y": -0.035,
                    "font": {
                        "family": "Inter, sans-serif",
                        "color": "#FFFFFF",
                        "size": 14,
                    },
                    "bgcolor": "rgba(0,0,0,0)",
                    "itemclick": "toggle",
                    "itemdoubleclick": "toggleothers",
                },
                uirevision="home_fase9_combined_donut_fullscreen_v20",
            )
        else:
            fullscreen_figure.update_layout(
                autosize=True,
                height=700,
                margin={"l": 68, "r": 28, "t": 58, "b": 56},
                legend={
                    "orientation": "h",
                    "x": 0.0,
                    "xanchor": "left",
                    "y": 1.025,
                    "font": {
                        "family": "Inter, sans-serif",
                        "color": "#FFFFFF",
                        "size": 14,
                    },
                    "bgcolor": "rgba(0,0,0,0)",
                    "itemclick": "toggle",
                    "itemdoubleclick": "toggleothers",
                },
                uirevision="home_fase9_service_comparison_fullscreen_v20",
            )

        fullscreen_figure.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            transition={"duration": 360, "easing": "cubic-in-out"},
        )
        _service_plotly_chart(
            fullscreen_figure,
            config={
                "displayModeBar": True,
                "displaylogo": False,
                "responsive": True,
                "scrollZoom": True,
                "doubleClick": "reset",
                "toImageButtonOptions": {
                    "format": "png",
                    "filename": filename,
                    "scale": 2,
                },
            },
            key=chart_key,
        )
    except Exception as error:
        LOGGER.exception("Fullscreen chart gabungan gagal: %s", error)
        st.error(
            "Grafik belum dapat dibuka dalam layar penuh. "
            "Tutup tampilan ini lalu coba kembali."
        )


def _render_overview(
    sentiment_df: pd.DataFrame,
    influencer_df: pd.DataFrame,
    influencer_real: bool,
) -> None:
    """Render visualisasi gabungan, platform, dan tabel influencer."""
    try:
        st.markdown(
            (
                '<section class="home-v5-viz-hero">'
                '<div class="home-v5-viz-hero-main">'
                '<div>'
                '<div class="home-v5-viz-kicker"><span class="home-v5-viz-pulse"></span>Visualisasi Interaktif</div>'
                '<h2 class="home-v5-viz-title">Visualisasi Gabungan — 3 Layanan</h2>'
                '<p class="home-v5-viz-copy">Eksplorasi pola sentimen IndiHome, IndiBiz, dan Telkomsel. Arahkan kursor untuk melihat detail, klik legenda untuk menyaring sentimen, atau buka grafik dalam layar penuh.</p>'
                '</div>'
                '<div class="home-v5-viz-actions">'
                '<span class="home-v5-viz-chip">'
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>'
                'Hover detail</span>'
                '<span class="home-v5-viz-chip">'
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 18 6-6-6-6"/></svg>'
                'Klik legenda</span>'
                '<span class="home-v5-viz-chip">'
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v12m0 0 4-4m-4 4-4-4"/><path d="M5 20h14"/></svg>'
                'Unduh PNG</span>'
                '</div>'
                '</div>'
                '</section>'
            ),
            unsafe_allow_html=True,
        )
        donut_figure = _build_donut_chart(sentiment_df)
        comparison_figure = _build_service_comparison_chart(sentiment_df)

        left_col, right_col = st.columns(2, gap="medium")
        with left_col:
            st.markdown(
                '<div class="home-v5-combined-card-marker home-v5-combined-card-marker--donut"></div>',
                unsafe_allow_html=True,
            )
            donut_head_col, donut_action_col = st.columns([3.55, 1.45], gap="small")
            with donut_head_col:
                st.markdown(
                    (
                        '<div class="home-v5-combined-card-head">'
                        '<div class="home-v5-combined-card-identity">'
                        '<span class="home-v5-combined-card-icon">'
                        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-9-9v9Z"/><path d="M12 3a9 9 0 0 1 9 9h-9Z"/></svg>'
                        '</span>'
                        '<div><div class="home-v5-combined-card-title">Distribusi Sentimen Gabungan</div>'
                        '<div class="home-v5-combined-card-copy">Arahkan kursor untuk melihat jumlah dan persentase. Klik legenda untuk menyaring irisan sentimen.</div></div>'
                        '</div>'
                        '</div>'
                    ),
                    unsafe_allow_html=True,
                )
            with donut_action_col:
                if _service_button(
                    "⛶ Layar Penuh",
                    key="home_v5_fullscreen_donut",
                    help="Buka hanya donut chart dalam tampilan layar penuh.",
                ):
                    _render_combined_chart_fullscreen(
                        "Distribusi Sentimen Gabungan — 3 Layanan",
                        donut_figure,
                        "donut",
                        "home_fase9_combined_donut_fullscreen_chart_v20",
                        "sentimen_gabungan_3_layanan_fullscreen",
                    )
            _service_plotly_chart(
                donut_figure,
                config={
                    "displayModeBar": False,
                    "displaylogo": False,
                    "responsive": True,
                    "scrollZoom": False,
                    "doubleClick": "reset",
                    "toImageButtonOptions": {
                        "format": "png",
                        "filename": "sentimen_gabungan_3_layanan",
                        "scale": 2,
                    },
                },
                key="home_fase9_combined_donut_chart_v19",
            )
        with right_col:
            st.markdown(
                '<div class="home-v5-combined-card-marker home-v5-combined-card-marker--bar"></div>',
                unsafe_allow_html=True,
            )
            bar_head_col, bar_action_col = st.columns([3.55, 1.45], gap="small")
            with bar_head_col:
                st.markdown(
                    (
                        '<div class="home-v5-combined-card-head">'
                        '<div class="home-v5-combined-card-identity">'
                        '<span class="home-v5-combined-card-icon">'
                        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 20V10h4v10H4Zm6 0V4h4v16h-4Zm6 0v-7h4v7h-4Z"/></svg>'
                        '</span>'
                        '<div><div class="home-v5-combined-card-title">Perbandingan Sentimen per Layanan</div>'
                        '<div class="home-v5-combined-card-copy">Bandingkan tiga kelas sentimen pada setiap layanan. Klik legenda untuk menampilkan atau menyembunyikan kelas.</div></div>'
                        '</div>'
                        '</div>'
                    ),
                    unsafe_allow_html=True,
                )
            with bar_action_col:
                if _service_button(
                    "⛶ Layar Penuh",
                    key="home_v5_fullscreen_bar",
                    help="Buka hanya bar chart dalam tampilan layar penuh.",
                ):
                    _render_combined_chart_fullscreen(
                        "Perbandingan Sentimen per Layanan",
                        comparison_figure,
                        "bar",
                        "home_fase9_service_comparison_fullscreen_chart_v20",
                        "perbandingan_sentimen_per_layanan_fullscreen",
                    )
            _service_plotly_chart(
                comparison_figure,
                config={
                    "displayModeBar": False,
                    "displaylogo": False,
                    "responsive": True,
                    "scrollZoom": False,
                    "doubleClick": "reset",
                    "toImageButtonOptions": {
                        "format": "png",
                        "filename": "perbandingan_sentimen_per_layanan",
                        "scale": 2,
                    },
                },
                key="home_fase9_service_comparison_chart_v19",
            )

        st.markdown(
            '<div class="home-v5-section-title" style="margin-top:1.3rem;">Overview Data per Platform</div>',
            unsafe_allow_html=True,
        )
        platform_expanded = bool(
            st.session_state.get("home_v5_platform_chart_expanded", False)
        )
        platform_totals = (
            sentiment_df.groupby("platform")
            .size()
            .reindex(PLATFORM_ORDER, fill_value=0)
        )
        platform_palette = {
            "twitter": "#42A5F5",
            "instagram": "#E1306C",
            "tiktok": "#25F4EE",
        }
        dominant_platform = (
            platform_totals.idxmax() if int(platform_totals.sum()) > 0 else PLATFORM_ORDER[0]
        )
        dominant_platform_label = PLATFORM_LABELS.get(dominant_platform, "Twitter/X")
        dominant_platform_total = int(platform_totals.get(dominant_platform, 0))
        dominant_sentiment = (
            sentiment_df["sentiment"].value_counts().reindex(SENTIMENT_ORDER, fill_value=0).idxmax()
            if not sentiment_df.empty
            else "neutral"
        )
        dominant_sentiment_label = SENTIMENT_LABELS.get(dominant_sentiment, "Netral")
        # HTML harus berupa satu rangkaian rapat tanpa indentasi awal. Streamlit
        # dapat membaca baris yang diawali empat spasi sebagai blok kode Markdown.
        platform_cards: list[str] = [
            (
                '<div class="home-v5-platform-highlight-card home-v5-platform-highlight-card--dominant" '
                'style="--home-v5-platform-color:#E53935; --home-v5-chip-delay:0s;">'
                '<span class="home-v5-platform-highlight-dot"></span>'
                '<div class="home-v5-platform-highlight-text">'
                '<span>Platform paling dominan</span>'
                f'<strong>{escape(dominant_platform_label)} · {_format_number(dominant_platform_total)}</strong>'
                '</div>'
                '</div>'
            )
        ]
        for index, platform in enumerate(PLATFORM_ORDER, start=1):
            platform_label = escape(PLATFORM_LABELS.get(platform, platform.title()))
            platform_total_label = _format_number(int(platform_totals.get(platform, 0)))
            platform_color = platform_palette.get(platform, "#42A5F5")
            platform_cards.append(
                (
                    '<div class="home-v5-platform-highlight-card" '
                    f'style="--home-v5-platform-color:{platform_color}; '
                    f'--home-v5-chip-delay:{index * 0.12}s;">'
                    '<span class="home-v5-platform-highlight-dot"></span>'
                    '<div class="home-v5-platform-highlight-text">'
                    f'<span>{platform_label}</span>'
                    f'<strong>{platform_total_label} komentar</strong>'
                    '</div>'
                    '</div>'
                )
            )

        toolbar_badges = ''.join([
            '<span class="home-v5-platform-toolbar-badge" style="--home-v5-platform-badge-accent:#42A5F5;">Hover interaktif</span>',
            '<span class="home-v5-platform-toolbar-badge" style="--home-v5-platform-badge-accent:#FF9800;">Sentimen dominan · ' + escape(dominant_sentiment_label) + '</span>',
            '<span class="home-v5-platform-toolbar-badge" style="--home-v5-platform-badge-accent:#4CAF50;">Klik legenda untuk fokus data</span>',
        ])

        with _service_container("home_v5_platform_overview_card"):
            st.markdown('<div class="home-v5-platform-shell-marker"></div>', unsafe_allow_html=True)
            st.markdown(
                (
                    '<div class="home-v5-platform-hero">'
                    '<div>'
                    '<div class="home-v5-platform-kicker">Pulse Analitik</div>'
                    '<div class="home-v5-platform-hero-title">Distribusi Sentimen per Platform</div>'
                    '<div class="home-v5-platform-hero-copy">Lihat penyebaran sentimen dari Twitter/X, Instagram, dan TikTok dalam satu panel yang lebih hidup. Arahkan kursor ke batang untuk melihat detail komentar dan bagikan grafik melalui mode pembesaran.</div>'
                    '</div>'
                    '</div>'
                    '<div class="home-v5-platform-highlights">' + ''.join(platform_cards).strip() + '</div>'
                ).strip(),
                unsafe_allow_html=True,
            )
            toolbar_col, control_col = _service_columns([3.0, 1.0], gap="small")
            with toolbar_col:
                st.markdown(
                    '<div class="home-v5-platform-toolbar">' + toolbar_badges + '</div>',
                    unsafe_allow_html=True,
                )
            with control_col:
                control_label = "Perkecil grafik" if platform_expanded else "Perbesar grafik"
                if _service_button(
                    control_label,
                    key="home_v5_toggle_platform_chart_size",
                    help="Ubah tinggi grafik distribusi sentimen per platform.",
                ):
                    st.session_state["home_v5_platform_chart_expanded"] = not platform_expanded
                    st.rerun()

            st.markdown(
                '<div class="home-v5-platform-chart-note">Batang berwarna akan berubah secara halus saat ukuran grafik diperbesar. Gunakan hover dan legenda untuk mengeksplorasi distribusi sentimen pada setiap platform.</div>',
                unsafe_allow_html=True,
            )
            _service_plotly_chart(
                _build_platform_chart(sentiment_df, expanded=platform_expanded),
                config={
                    "displayModeBar": "hover",
                    "displaylogo": False,
                    "responsive": True,
                    "toImageButtonOptions": {
                        "format": "png",
                        "filename": "distribusi_sentimen_per_platform_3_layanan",
                        "scale": 2,
                    },
                },
                key=(
                    "home_fase9_platform_expanded_v21"
                    if platform_expanded
                    else "home_fase9_platform_compact_v21"
                ),
            )

        st.markdown(
            '<div class="home-v5-card-title" style="margin-top:1.15rem;">'
            'Top 5 Influencer — Twitter/X, Instagram, dan TikTok'
            '</div>',
            unsafe_allow_html=True,
        )
        _render_influencer_tables(influencer_df, influencer_real)
    except Exception as error:
        LOGGER.exception("Gagal merender Overview Data: %s", error)
        st.error("Overview data belum dapat ditampilkan.")



def _queue_guide_navigation(page_name: str, loading_label: str) -> None:
    """Antrekan navigasi kartu panduan agar custom loading tampil lebih dulu."""
    try:
        st.session_state[STATE_GUIDE_NAVIGATION] = {
            "page": str(page_name),
            "label": str(loading_label),
        }
    except Exception as error:
        LOGGER.exception("Gagal menyiapkan navigasi panduan: %s", error)


def _process_guide_navigation() -> bool:
    """Jalankan custom loading lalu pindahkan route ke halaman tujuan."""
    payload = st.session_state.pop(STATE_GUIDE_NAVIGATION, None)
    if not isinstance(payload, dict):
        return False

    page_name = str(payload.get("page", "Beranda")).strip() or "Beranda"
    loading_label = str(payload.get("label", "Membuka halaman dashboard...")).strip()
    loading_handle = None
    started_at = 0.0
    try:
        loading_handle = mulai_loading_aksi(loading_label)
        started_at = time.monotonic()
        st.session_state["selected_page"] = page_name
        st.session_state["page"] = page_name
        st.session_state["_sidebar_force_route"] = page_name
        elapsed = time.monotonic() - started_at
        if elapsed < 0.55:
            time.sleep(0.55 - elapsed)
        selesaikan_loading_aksi(loading_handle)
        st.rerun()
    except Exception as error:
        LOGGER.exception("Navigasi panduan ke %s gagal: %s", page_name, error)
        if loading_handle is not None:
            try:
                selesaikan_loading_aksi(loading_handle)
            except Exception:
                pass
        st.error(f"Halaman {page_name} belum dapat dibuka.")
    return True

def _render_usage_guide() -> None:
    """Render panduan penggunaan dalam kartu interaktif yang dapat bernavigasi."""
    try:
        if _process_guide_navigation():
            return

        intro_html = (
            '<div class="home-v5-section-intro-v25">'
            '<div><div class="home-v5-section-kicker-v25">Jalur Eksplorasi</div>'
            '<div class="home-v5-section-heading-v25">Panduan Penggunaan Dashboard</div>'
            '<div class="home-v5-section-copy-v25">Ikuti empat langkah singkat untuk memilih data, menerapkan filter, membaca jaringan, lalu mengekspor hasil penelitian. Setiap kartu dapat diklik untuk langsung membuka halaman terkait.</div></div>'
            '<span class="home-v5-section-badge-v25">4 langkah interaktif</span>'
            '</div>'
        )
        st.markdown(intro_html, unsafe_allow_html=True)

        guide_items = [
            {
                "step": "01",
                "class": "home-v5-guide-card--1",
                "icon": "◈",
                "title": "Pilih layanan",
                "copy": "Mulai dari Dataset untuk memilih IndiHome, IndiBiz, atau Telkomsel dan melihat sumber data yang aktif.",
                "micro": "Awali analisis dari data",
                "button": "Buka Dataset",
                "page": "Dataset",
                "loading": "Membuka halaman Dataset dan menyiapkan pilihan layanan...",
            },
            {
                "step": "02",
                "class": "home-v5-guide-card--2",
                "icon": "⌁",
                "title": "Terapkan filter",
                "copy": "Atur platform, periode, dan kelas sentimen agar seluruh visualisasi mengikuti fokus analisis Anda.",
                "micro": "Filter sinkron lintas visual",
                "button": "Buka Analisis Sentimen",
                "page": "Analisis Sentimen",
                "loading": "Membuka Analisis Sentimen dan menyiapkan filter interaktif...",
            },
            {
                "step": "03",
                "class": "home-v5-guide-card--3",
                "icon": "⌘",
                "title": "Baca jaringan",
                "copy": "Gunakan Social Network Analysis untuk memahami struktur interaksi, degree, dan akun influencer.",
                "micro": "Temukan aktor jaringan",
                "button": "Buka SNA",
                "page": "Social Network Analysis",
                "loading": "Membuka Social Network Analysis dan menyiapkan jaringan...",
            },
            {
                "step": "04",
                "class": "home-v5-guide-card--4",
                "icon": "⇩",
                "title": "Unduh hasil",
                "copy": "Gunakan tombol ekspor pada tabel atau toolbar Plotly untuk menyimpan data dan visualisasi penelitian.",
                "micro": "Simpan CSV, Excel, atau PNG",
                "button": "Lihat Data untuk Diekspor",
                "page": "Dataset",
                "loading": "Membuka Dataset dan menyiapkan hasil yang dapat diekspor...",
            },
        ]

        columns = _service_columns([1, 1, 1, 1], gap="small")
        for index, (column, item) in enumerate(zip(columns, guide_items), start=1):
            with column:
                with _service_container(f"home_v5_guide_card_{index}"):
                    marker_html = (
                        f'<div class="home-v5-guide-card-marker-v25 {item["class"]}"></div>'
                    )
                    content_html = (
                        '<div class="home-v5-guide-content-v25">'
                        '<div class="home-v5-guide-head-v25">'
                        f'<span class="home-v5-guide-icon-v25">{item["icon"]}</span>'
                        f'<span class="home-v5-guide-step-v25">Langkah {item["step"]}</span>'
                        '</div>'
                        f'<div class="home-v5-guide-title-v25">{escape(item["title"])}</div>'
                        f'<div class="home-v5-guide-copy-v25">{escape(item["copy"])}</div>'
                        f'<div class="home-v5-guide-micro-v25">{escape(item["micro"])}</div>'
                        '</div>'
                    )
                    st.markdown(marker_html + content_html, unsafe_allow_html=True)
                    _service_button(
                        item["button"],
                        key=f"home_v5_guide_button_{index}",
                        on_click=_queue_guide_navigation,
                        args=(item["page"], item["loading"]),
                        help=f"Buka halaman {item['page']}.",
                    )
    except Exception as error:
        LOGGER.exception("Panduan penggunaan gagal dirender: %s", error)
        st.error("Panduan penggunaan belum dapat ditampilkan.")

def _render_research_information() -> None:
    """Render informasi penelitian dalam panel berwarna dan interaktif."""
    try:
        intro_html = (
            '<div class="home-v5-section-intro-v25" style="margin-top:1.4rem;">'
            '<div><div class="home-v5-section-kicker-v25">Research Identity</div>'
            '<div class="home-v5-section-heading-v25">Informasi Penelitian</div>'
            '<div class="home-v5-section-copy-v25">Ringkasan identitas akademik, metode, institusi, dan periode data yang menjadi dasar dashboard.</div></div>'
            '<span class="home-v5-section-badge-v25">ULBI Bandung · 2026</span>'
            '</div>'
        )
        st.markdown(intro_html, unsafe_allow_html=True)

        research_tiles = [
            ("Peneliti", "Aulia Rahmadiva Wardana", "#E53935"),
            ("NPM", "184220019", "#FF9800"),
            ("Pembimbing", "Woro Isti Rahayu, S.T., M.T.", "#42A5F5"),
            ("Metode", "Social Network Analysis (SNA) dan IndoBERT", "#7E57C2"),
            ("Institusi", "S1 Sains Data · Universitas Logistik dan Bisnis Internasional", "#26A69A"),
            ("Periode Data", "November–Desember 2025", "#4CAF50"),
        ]
        tiles_html = ''.join(
            (
                f'<div class="home-v5-research-tile-v25" style="--home-v5-research-accent:{accent};">'
                f'<div class="home-v5-research-tile-label-v25">{escape(label)}</div>'
                f'<div class="home-v5-research-tile-value-v25">{escape(value)}</div>'
                '</div>'
            )
            for label, value, accent in research_tiles
        )

        with _service_container("home_v5_research_information_card"):
            st.markdown('<div class="home-v5-research-marker-v25"></div>', unsafe_allow_html=True)
            hero_html = (
                '<div class="home-v5-research-hero-v25">'
                '<div class="home-v5-research-identity-v25">'
                '<span class="home-v5-research-icon-v25">⌬</span>'
                '<div><div class="home-v5-research-title-v25">Analisis Jaringan dan Sentimen Publik terhadap Layanan Digital Telkom Group</div>'
                '<div class="home-v5-research-subtitle-v25">Skripsi S1 Sains Data yang mengintegrasikan analisis sentimen, struktur jaringan sosial, identifikasi influencer, serta rekomendasi berbasis data.</div></div>'
                '</div>'
                '<span class="home-v5-research-status-v25">Penelitian aktif</span>'
                '</div>'
                f'<div class="home-v5-research-grid-v25">{tiles_html}</div>'
            )
            st.markdown(hero_html, unsafe_allow_html=True)

            with st.expander("Lihat alur metodologi penelitian", expanded=False):
                flow_html = (
                    '<div class="home-v5-method-flow-v25">'
                    '<div class="home-v5-method-step-v25">1 · Data percakapan<br>Twitter/X, Instagram, TikTok</div>'
                    '<div class="home-v5-method-step-v25">2 · Analisis sentimen<br>IndoBERT</div>'
                    '<div class="home-v5-method-step-v25">3 · Analisis jaringan<br>NetworkX + Pyvis</div>'
                    '<div class="home-v5-method-step-v25">4 · Insight penelitian<br>Influencer + rekomendasi</div>'
                    '</div>'
                )
                st.markdown(flow_html, unsafe_allow_html=True)
                st.caption(
                    "Dashboard menyajikan hasil penelitian untuk tiga layanan: IndiHome, IndiBiz, dan Telkomsel pada periode November–Desember 2025."
                )
    except Exception as error:
        LOGGER.exception("Informasi penelitian gagal dirender: %s", error)
        st.error("Informasi penelitian belum dapat ditampilkan.")

def render_home() -> None:
    """Render Beranda tiga layanan Telkom Group yang seluruhnya Ready."""
    loading_placeholder = None
    try:
        _inject_home_css()
        loading_placeholder = mulai_layar_loading(
            STATE_LOADING_SELESAI,
            (
                "Memuat Data IndiHome",
                "Memuat Data IndiBiz",
                "Memuat Data Telkomsel",
                "Menggabungkan Statistik",
                "Menyiapkan Visualisasi",
            ),
        )

        indihome_df = load_indihome_data()
        indibiz_df = load_indibiz_data()
        telkomsel_df = load_telkomsel_data()
        all_sentiment_df = load_all_data()
        influencer_df, influencer_real, _ = _load_home_influencer_data()

        service_status = {
            "IndiHome": bool(sentiment_file_exists("IndiHome")),
            "IndiBiz": bool(sentiment_file_exists("IndiBiz")),
            "Telkomsel": bool(sentiment_file_exists("Telkomsel")),
        }
        metrics = _calculate_metrics(all_sentiment_df, influencer_df)

        _render_hero(service_status, influencer_real)
        _render_metrics(metrics)
        _render_service_cards(
            indihome_df,
            indibiz_df,
            telkomsel_df,
            service_status,
        )
        _render_overview(all_sentiment_df, influencer_df, influencer_real)
        _render_usage_guide()
        _render_research_information()
        selesaikan_layar_loading(loading_placeholder, STATE_LOADING_SELESAI)
    except Exception as error:
        LOGGER.exception("Halaman Beranda gagal dimuat: %s", error)
        batalkan_layar_loading(loading_placeholder, STATE_LOADING_SELESAI)
        st.error(
            "Halaman Beranda belum dapat dimuat sepenuhnya. "
            "Silakan muat ulang aplikasi."
        )


