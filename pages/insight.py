"""Kompatibilitas route lama untuk halaman insight penelitian."""

import streamlit as st

from pages.recommendation import render_recommendation


def render_insight() -> None:
    """Tampilkan halaman rekomendasi sebagai pengganti route insight lama."""
    try:
        render_recommendation()
    except Exception as exc:
        st.error(f"Halaman insight belum dapat ditampilkan: {exc}")
