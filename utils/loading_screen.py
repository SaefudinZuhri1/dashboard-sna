# utils/loading_screen.py
# PATCH STARTUP V5.1: perbaikan atribut HTML multiline tampil sebagai kode
# PATCH STARTUP V5: HTML compact untuk mencegah tag tampil mentah
# PATCH LOADING V2: startup dedent + action overlay halus
# PATCH UI: animasi startup full-screen tanpa teks
"""Utilitas layar loading global bertema Telkom untuk aplikasi Streamlit."""

from __future__ import annotations

import logging
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass
from html import escape
from textwrap import dedent
from typing import Iterable, Iterator

import streamlit as st

LOGGER = logging.getLogger(__name__)

SESSION_GLOBAL_ACTIVE = "_telkom_global_loading_active"

DEFAULT_LOADING_MESSAGES = (
    "Memuat data penelitian",
    "Mengambil informasi terbaru",
    "Menyusun komponen halaman",
    "Menyiapkan visualisasi",
    "Hampir selesai",
)

LOADING_CONFIG: dict[str, dict[str, object]] = {
    "Autentikasi": {
        "judul": "Menyiapkan Akses",
        "pesan": (
            "Memuat halaman autentikasi",
            "Menyiapkan formulir keamanan",
            "Memeriksa status sesi",
            "Menyiapkan akses dashboard",
        ),
    },
    "Beranda": {
        "judul": "Menyiapkan Beranda",
        "pesan": (
            "Memuat ringkasan penelitian",
            "Mengambil metrik utama",
            "Menghitung distribusi sentimen",
            "Menyiapkan tabel influencer",
            "Menyusun visualisasi beranda",
        ),
    },
    "Dataset": {
        "judul": "Menyiapkan Dataset",
        "pesan": (
            "Membaca dataset penelitian",
            "Mengambil data media sosial",
            "Menerapkan filter aktif",
            "Menyusun tabel dan ringkasan",
            "Menyiapkan grafik distribusi",
        ),
    },
    "Analisis Sentimen": {
        "judul": "Menyiapkan Analisis Sentimen",
        "pesan": (
            "Membaca hasil klasifikasi",
            "Menghitung distribusi sentimen",
            "Mengolah confidence score",
            "Menyusun contoh komentar",
            "Menyiapkan visualisasi sentimen",
        ),
    },
    "Analisis Topik": {
        "judul": "Menyiapkan Analisis Topik",
        "pesan": (
            "Membaca korpus komentar",
            "Membersihkan dan menormalkan teks",
            "Menghitung frekuensi kata",
            "Menyusun WordCloud",
            "Menyiapkan topik dominan",
        ),
    },
    "Analisis Jaringan Sosial": {
        "judul": "Menyiapkan Analisis Jaringan",
        "pesan": (
            "Membaca relasi antar akun",
            "Membangun graf jaringan",
            "Menghitung metrik sentralitas",
            "Mengurutkan influencer",
            "Menyiapkan visualisasi interaktif",
        ),
    },
    "Rekomendasi": {
        "judul": "Menyiapkan Rekomendasi",
        "pesan": (
            "Menggabungkan hasil analisis",
            "Membaca isu dominan",
            "Memetakan influencer utama",
            "Menyusun rekomendasi strategis",
            "Menyiapkan tampilan rekomendasi",
        ),
    },
    "Profil": {
        "judul": "Menyiapkan Profil",
        "pesan": (
            "Mengambil informasi akun",
            "Memeriksa foto profil",
            "Menyiapkan data pengguna",
            "Menyusun formulir profil",
        ),
    },
    "Admin Panel": {
        "judul": "Menyiapkan Admin Panel",
        "pesan": (
            "Mengambil daftar pengguna",
            "Memeriksa status data",
            "Menghitung statistik sistem",
            "Menyiapkan kontrol administrator",
        ),
    },
    "Tentang Penelitian": {
        "judul": "Menyiapkan Informasi Penelitian",
        "pesan": (
            "Memuat identitas penelitian",
            "Mengambil informasi metodologi",
            "Menyusun teknologi yang digunakan",
            "Menyiapkan informasi versi",
        ),
    },
}


def _is_dark_mode() -> bool:
    """Ambil status tema aktif tanpa mengganggu proses loading."""
    try:
        return bool(st.session_state.get("dark_mode", True))
    except Exception:
        return True


@dataclass
class LoadingHandle:
    """Simpan placeholder dan metadata untuk satu layar loading."""

    placeholder: object | None
    mulai_pada: float
    konteks: str
    global_scope: bool = False


def _normalisasi_pesan(pesan: Iterable[str] | None) -> list[str]:
    """Normalisasi daftar pesan dan pastikan minimal satu pesan tersedia."""
    hasil = [str(item).strip() for item in (pesan or DEFAULT_LOADING_MESSAGES)]
    hasil = [item for item in hasil if item]
    return hasil or list(DEFAULT_LOADING_MESSAGES)


def _konfigurasi_loading(
    konteks: str,
    judul: str | None = None,
    pesan: Iterable[str] | None = None,
) -> tuple[str, list[str]]:
    """Ambil judul dan pesan loading berdasarkan konteks halaman."""
    konfigurasi = LOADING_CONFIG.get(konteks, {})
    judul_final = str(judul or konfigurasi.get("judul") or "Menyiapkan Dashboard")
    pesan_final = _normalisasi_pesan(
        pesan or konfigurasi.get("pesan")  # type: ignore[arg-type]
    )
    return judul_final, pesan_final


def _buat_html_loading(judul: str, pesan: Iterable[str]) -> str:
    """Bangun overlay loading CSS murni tanpa GIF, gambar, atau JavaScript."""
    daftar_pesan = _normalisasi_pesan(pesan)
    durasi_total = max(4.4, len(daftar_pesan) * 1.1)
    kelas_tema = "telkom-loading-dark" if _is_dark_mode() else "telkom-loading-light"

    pesan_html = "".join(
        (
            '<span class="telkom-loading-message-item" '
            f'style="animation-delay:{index * 1.1:.2f}s;">{escape(teks)}</span>'
        )
        for index, teks in enumerate(daftar_pesan)
    )

    return f"""
        <style>
            .telkom-loading-overlay,
            .telkom-loading-overlay * {{
                box-sizing: border-box;
            }}

            .telkom-loading-overlay {{
                align-items: center;
                background:
                    radial-gradient(circle at 50% 42%, rgba(229,57,53,.18), transparent 28%),
                    linear-gradient(rgba(255,255,255,.018) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255,255,255,.018) 1px, transparent 1px),
                    #0D0D0D;
                background-size: auto, 34px 34px, 34px 34px, auto;
                display: flex;
                inset: 0;
                justify-content: center;
                min-height: 100dvh;
                overflow: hidden;
                padding: 24px;
                position: fixed;
                width: 100vw;
                z-index: 2147483646;
            }}

            .telkom-loading-overlay::before,
            .telkom-loading-overlay::after {{
                border-radius: 999px;
                content: "";
                filter: blur(30px);
                opacity: .42;
                pointer-events: none;
                position: absolute;
            }}

            .telkom-loading-overlay::before {{
                background: rgba(229,57,53,.22);
                height: 220px;
                left: -80px;
                top: 12%;
                width: 220px;
            }}

            .telkom-loading-overlay::after {{
                background: rgba(183,28,28,.18);
                bottom: 8%;
                height: 260px;
                right: -100px;
                width: 260px;
            }}

            .telkom-loading-panel {{
                align-items: center;
                background: linear-gradient(180deg, rgba(26,26,26,.94), rgba(17,17,17,.96));
                border: 1px solid #2A2A2A;
                border-radius: 24px;
                box-shadow:
                    0 30px 90px rgba(0,0,0,.55),
                    0 0 0 1px rgba(229,57,53,.04) inset;
                display: flex;
                flex-direction: column;
                justify-content: center;
                max-width: 460px;
                min-height: 390px;
                overflow: hidden;
                padding: 42px 38px 34px;
                position: relative;
                text-align: center;
                width: min(92vw, 460px);
                z-index: 1;
            }}

            .telkom-loading-panel::before {{
                background: linear-gradient(90deg, transparent, #E53935, transparent);
                content: "";
                height: 2px;
                left: 18%;
                opacity: .95;
                position: absolute;
                right: 18%;
                top: 0;
            }}

            .telkom-loading-visual {{
                height: 142px;
                margin-bottom: 24px;
                position: relative;
                width: 142px;
            }}

            .telkom-loading-orbit {{
                animation: telkom-orbit-spin 2.2s linear infinite;
                border: 1px solid rgba(255,255,255,.14);
                border-radius: 50%;
                inset: 5px;
                position: absolute;
            }}

            .telkom-loading-orbit::after {{
                background: #E53935;
                border: 3px solid #171717;
                border-radius: 50%;
                box-shadow: 0 0 18px rgba(229,57,53,.78);
                content: "";
                height: 16px;
                left: 50%;
                position: absolute;
                top: -8px;
                transform: translateX(-50%);
                width: 16px;
            }}

            .telkom-loading-orbit.orbit-two {{
                animation-direction: reverse;
                animation-duration: 3s;
                border-color: rgba(229,57,53,.26);
                inset: 20px;
            }}

            .telkom-loading-orbit.orbit-two::after {{
                background: #FF6B67;
                height: 12px;
                top: -6px;
                width: 12px;
            }}

            .telkom-loading-orbit.orbit-three {{
                animation-duration: 1.6s;
                border-color: rgba(255,255,255,.10);
                inset: 34px;
            }}

            .telkom-loading-orbit.orbit-three::after {{
                background: #FFFFFF;
                box-shadow: 0 0 14px rgba(255,255,255,.55);
                height: 9px;
                top: -5px;
                width: 9px;
            }}

            .telkom-loading-core {{
                align-items: flex-end;
                animation: telkom-core-pulse 1.45s ease-in-out infinite;
                background: linear-gradient(145deg, #E53935, #B71C1C);
                border: 1px solid rgba(255,255,255,.20);
                border-radius: 20px;
                box-shadow:
                    0 16px 35px rgba(183,28,28,.34),
                    0 0 28px rgba(229,57,53,.24);
                display: flex;
                gap: 5px;
                height: 54px;
                justify-content: center;
                left: 50%;
                padding: 12px 14px;
                position: absolute;
                top: 50%;
                transform: translate(-50%, -50%);
                width: 54px;
            }}

            .telkom-loading-bar {{
                animation: telkom-bar-wave .9s ease-in-out infinite alternate;
                background: #FFFFFF;
                border-radius: 999px;
                display: block;
                height: 44%;
                opacity: .96;
                width: 5px;
            }}

            .telkom-loading-bar:nth-child(2) {{
                animation-delay: .14s;
                height: 72%;
            }}

            .telkom-loading-bar:nth-child(3) {{
                animation-delay: .28s;
                height: 100%;
            }}

            .telkom-loading-title {{
                color: #FFFFFF;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: clamp(1.22rem, 2.2vw, 1.55rem);
                font-weight: 800;
                letter-spacing: -.025em;
                line-height: 1.25;
                margin: 0;
            }}

            .telkom-loading-message {{
                height: 1.55rem;
                margin-top: 10px;
                min-width: min(78vw, 360px);
                position: relative;
            }}

            .telkom-loading-message-item {{
                animation: telkom-message-cycle {durasi_total:.2f}s linear infinite;
                animation-delay: 0s;
                color: #AAAAAA;
                font-family: 'Inter', sans-serif;
                font-size: .94rem;
                font-weight: 500;
                inset: 0;
                opacity: 0;
                position: absolute;
                transform: translateY(6px);
                white-space: nowrap;
            }}

            .telkom-loading-progress {{
                background: #242424;
                border: 1px solid #2F2F2F;
                border-radius: 999px;
                height: 6px;
                margin-top: 20px;
                overflow: hidden;
                position: relative;
                width: min(72vw, 290px);
            }}

            .telkom-loading-progress::after {{
                animation: telkom-progress-slide 1.25s cubic-bezier(.4,0,.2,1) infinite;
                background: linear-gradient(90deg, #B71C1C, #E53935, #FF6B67);
                border-radius: inherit;
                box-shadow: 0 0 16px rgba(229,57,53,.42);
                content: "";
                display: block;
                height: 100%;
                transform: translateX(-120%);
                width: 46%;
            }}

            .telkom-loading-brand {{
                color: #666666;
                font-family: 'Inter', sans-serif;
                font-size: 0.75rem /* FIX: minimum 12px agar terbaca di tablet */;
                font-weight: 700;
                letter-spacing: .18em;
                margin-top: 18px;
                text-transform: uppercase;
            }}

            /*
             * Tema terang hanya mengubah token visual loading.
             * Struktur, ukuran, animasi, dan urutan elemen tetap sama.
             */
            .telkom-loading-overlay.telkom-loading-light {{
                background:
                    radial-gradient(circle at 50% 42%, rgba(229,57,53,.12), transparent 28%),
                    linear-gradient(rgba(15,23,42,.045) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(15,23,42,.045) 1px, transparent 1px),
                    #F7F8FA;
                background-size: auto, 34px 34px, 34px 34px, auto;
            }}

            .telkom-loading-overlay.telkom-loading-light::before {{
                background: rgba(229,57,53,.14);
            }}

            .telkom-loading-overlay.telkom-loading-light::after {{
                background: rgba(29,161,242,.10);
            }}

            .telkom-loading-overlay.telkom-loading-light .telkom-loading-panel {{
                background: linear-gradient(180deg, rgba(255,255,255,.98), rgba(248,250,252,.98));
                border-color: rgba(148,163,184,.30);
                box-shadow:
                    0 30px 90px rgba(15,23,42,.14),
                    0 0 0 1px rgba(229,57,53,.05) inset;
            }}

            .telkom-loading-overlay.telkom-loading-light .telkom-loading-orbit {{
                border-color: rgba(15,23,42,.16);
            }}

            .telkom-loading-overlay.telkom-loading-light .telkom-loading-orbit::after {{
                border-color: #FFFFFF;
            }}

            .telkom-loading-overlay.telkom-loading-light .telkom-loading-orbit.orbit-two {{
                border-color: rgba(229,57,53,.28);
            }}

            .telkom-loading-overlay.telkom-loading-light .telkom-loading-orbit.orbit-three {{
                border-color: rgba(15,23,42,.12);
            }}

            .telkom-loading-overlay.telkom-loading-light .telkom-loading-orbit.orbit-three::after {{
                background: #475569;
                box-shadow: 0 0 14px rgba(71,85,105,.30);
            }}

            .telkom-loading-overlay.telkom-loading-light .telkom-loading-title {{
                background: none !important;
                background-clip: border-box !important;
                -webkit-background-clip: border-box !important;
                color: #111827 !important;
                -webkit-text-fill-color: #111827 !important;
                filter: none !important;
                mix-blend-mode: normal !important;
                opacity: 1 !important;
                visibility: visible !important;
            }}

            .telkom-loading-overlay.telkom-loading-light .telkom-loading-message-item {{
                color: #64748B !important;
            }}

            .telkom-loading-overlay.telkom-loading-light .telkom-loading-progress {{
                background: #E5E7EB;
                border-color: #D7DEE8;
            }}

            .telkom-loading-overlay.telkom-loading-light .telkom-loading-brand {{
                color: #64748B !important;
            }}

            @keyframes telkom-orbit-spin {{
                to {{ transform: rotate(360deg); }}
            }}

            @keyframes telkom-core-pulse {{
                0%, 100% {{ transform: translate(-50%, -50%) scale(.96); }}
                50% {{ transform: translate(-50%, -50%) scale(1.05); }}
            }}

            @keyframes telkom-bar-wave {{
                from {{ transform: scaleY(.55); }}
                to {{ transform: scaleY(1); }}
            }}

            @keyframes telkom-message-cycle {{
                0%, 15% {{ opacity: 1; transform: translateY(0); }}
                20%, 100% {{ opacity: 0; transform: translateY(-5px); }}
            }}

            @keyframes telkom-progress-slide {{
                0% {{ transform: translateX(-120%); }}
                55% {{ transform: translateX(120%); }}
                100% {{ transform: translateX(250%); }}
            }}

            @media (max-width: 640px) {{
                .telkom-loading-panel {{
                    min-height: 350px;
                    padding: 34px 22px 28px;
                }}

                .telkom-loading-visual {{
                    height: 124px;
                    width: 124px;
                }}

                .telkom-loading-message-item {{
                    font-size: .86rem;
                }}
            }}

            @media (prefers-reduced-motion: reduce) {{
                .telkom-loading-orbit,
                .telkom-loading-core,
                .telkom-loading-bar,
                .telkom-loading-progress::after {{
                    animation-duration: 4s !important;
                }}

                /*
                 * Jaga siklus pesan tetap mengikuti jumlah pesan.
                 * Durasi 4 detik lebih pendek daripada jeda pesan terakhir
                 * sehingga pesan pertama dapat berulang dan bertumpuk.
                 */
                .telkom-loading-message-item {{
                    animation-duration: {durasi_total:.2f}s !important;
                }}
            }}
        </style>
        <section class="telkom-loading-overlay {kelas_tema}" role="status" aria-live="polite">
            <div class="telkom-loading-panel">
                <div class="telkom-loading-visual" aria-hidden="true">
                    <span class="telkom-loading-orbit orbit-one"></span>
                    <span class="telkom-loading-orbit orbit-two"></span>
                    <span class="telkom-loading-orbit orbit-three"></span>
                    <span class="telkom-loading-core">
                        <i class="telkom-loading-bar"></i>
                        <i class="telkom-loading-bar"></i>
                        <i class="telkom-loading-bar"></i>
                    </span>
                </div>
                <h2 class="telkom-loading-title" style="color:#FFFFFF !important;-webkit-text-fill-color:#FFFFFF !important;opacity:1 !important;">{escape(judul)}</h2>
                <div class="telkom-loading-message">{pesan_html}</div>
                <div class="telkom-loading-progress" aria-hidden="true"></div>
                <div class="telkom-loading-brand">Telkom Group Analytics</div>
            </div>
        </section>
    """




def _compact_html(markup: str) -> str:
    """Padatkan HTML agar parser Markdown tidak menampilkan atribut sebagai kode."""
    cleaned_markup = dedent(str(markup or "")).strip()

    # Satukan whitespace di dalam setiap tag pembuka/penutup.
    # Contoh:
    # <section
    #     class="..."
    #     role="status"
    # >
    # menjadi:
    # <section class="..." role="status">
    def _compact_tag(match):
        tag_content = re.sub(r"\s+", " ", match.group(1)).strip()
        return f"<{tag_content}>"

    cleaned_markup = re.sub(
        r"<([^<>]+)>",
        _compact_tag,
        cleaned_markup,
        flags=re.DOTALL,
    )

    # Hapus jeda kosong antartag.
    return re.sub(r">\s+<", "><", cleaned_markup).strip()


def _buat_html_loading_awal() -> str:
    """Bangun loading awal full-screen yang mengikuti tema aktif."""
    kelas_tema = "telkom-startup-dark" if _is_dark_mode() else "telkom-startup-light"
    return _compact_html(
        """
        <style>
            .telkom-startup-loader,
            .telkom-startup-loader * {
                box-sizing: border-box;
            }

            .telkom-startup-loader {
                align-items: center;
                animation: telkom-startup-fade-in 180ms ease-out both;
                background:
                    radial-gradient(
                        circle at 50% 50%,
                        rgba(229, 57, 53, 0.15),
                        transparent 25%
                    ),
                    #0D0D0D;
                display: flex;
                inset: 0;
                justify-content: center;
                min-height: 100dvh;
                overflow: hidden;
                position: fixed;
                width: 100vw;
                z-index: 2147483647;
            }

            .telkom-startup-loader::before {
                animation: telkom-startup-glow 2.2s ease-in-out infinite;
                background: rgba(229, 57, 53, 0.18);
                border-radius: 50%;
                content: "";
                filter: blur(46px);
                height: 210px;
                position: absolute;
                width: 210px;
            }

            .telkom-startup-visual {
                height: 148px;
                position: relative;
                width: 148px;
                z-index: 1;
            }

            .telkom-startup-orbit {
                animation: telkom-startup-spin 2.1s linear infinite;
                border: 1px solid rgba(255, 255, 255, 0.16);
                border-radius: 50%;
                inset: 4px;
                position: absolute;
            }

            .telkom-startup-orbit::after {
                background: #E53935;
                border: 3px solid #0D0D0D;
                border-radius: 50%;
                box-shadow: 0 0 20px rgba(229, 57, 53, 0.85);
                content: "";
                height: 16px;
                left: 50%;
                position: absolute;
                top: -8px;
                transform: translateX(-50%);
                width: 16px;
            }

            .telkom-startup-orbit.orbit-two {
                animation-direction: reverse;
                animation-duration: 2.9s;
                border-color: rgba(229, 57, 53, 0.30);
                inset: 20px;
            }

            .telkom-startup-orbit.orbit-two::after {
                background: #FF6B67;
                height: 12px;
                top: -6px;
                width: 12px;
            }

            .telkom-startup-orbit.orbit-three {
                animation-duration: 1.55s;
                border-color: rgba(255, 255, 255, 0.11);
                inset: 35px;
            }

            .telkom-startup-orbit.orbit-three::after {
                background: #FFFFFF;
                box-shadow: 0 0 14px rgba(255, 255, 255, 0.65);
                height: 9px;
                top: -5px;
                width: 9px;
            }

            .telkom-startup-core {
                align-items: flex-end;
                animation: telkom-startup-pulse 1.35s ease-in-out infinite;
                background: linear-gradient(145deg, #E53935, #B71C1C);
                border: 1px solid rgba(255, 255, 255, 0.22);
                border-radius: 20px;
                box-shadow:
                    0 16px 38px rgba(183, 28, 28, 0.38),
                    0 0 30px rgba(229, 57, 53, 0.28);
                display: flex;
                gap: 5px;
                height: 56px;
                justify-content: center;
                left: 50%;
                padding: 12px 14px;
                position: absolute;
                top: 50%;
                transform: translate(-50%, -50%);
                width: 56px;
            }

            .telkom-startup-bar {
                animation: telkom-startup-wave 0.85s ease-in-out infinite alternate;
                background: #FFFFFF;
                border-radius: 999px;
                display: block;
                height: 44%;
                opacity: 0.97;
                width: 5px;
            }

            .telkom-startup-bar:nth-child(2) {
                animation-delay: 0.13s;
                height: 72%;
            }

            .telkom-startup-bar:nth-child(3) {
                animation-delay: 0.26s;
                height: 100%;
            }

            .telkom-startup-loader.telkom-startup-light {
                background:
                    radial-gradient(
                        circle at 50% 50%,
                        rgba(229, 57, 53, 0.12),
                        transparent 25%
                    ),
                    #F7F8FA;
            }

            .telkom-startup-loader.telkom-startup-light::before {
                background: rgba(229, 57, 53, 0.13);
            }

            .telkom-startup-loader.telkom-startup-light .telkom-startup-orbit {
                border-color: rgba(15, 23, 42, 0.16);
            }

            .telkom-startup-loader.telkom-startup-light .telkom-startup-orbit::after {
                border-color: #F7F8FA;
            }

            .telkom-startup-loader.telkom-startup-light .telkom-startup-orbit.orbit-two {
                border-color: rgba(229, 57, 53, 0.30);
            }

            .telkom-startup-loader.telkom-startup-light .telkom-startup-orbit.orbit-three {
                border-color: rgba(15, 23, 42, 0.12);
            }

            .telkom-startup-loader.telkom-startup-light .telkom-startup-orbit.orbit-three::after {
                background: #475569;
                box-shadow: 0 0 14px rgba(71, 85, 105, 0.30);
            }

            @keyframes telkom-startup-spin {
                to {
                    transform: rotate(360deg);
                }
            }

            @keyframes telkom-startup-pulse {
                0%, 100% {
                    transform: translate(-50%, -50%) scale(0.96);
                }

                50% {
                    transform: translate(-50%, -50%) scale(1.05);
                }
            }

            @keyframes telkom-startup-wave {
                from {
                    transform: scaleY(0.52);
                }

                to {
                    transform: scaleY(1);
                }
            }

            @keyframes telkom-startup-glow {
                0%, 100% {
                    opacity: 0.55;
                    transform: scale(0.92);
                }

                50% {
                    opacity: 1;
                    transform: scale(1.08);
                }
            }

            @keyframes telkom-startup-fade-in {
                from {
                    opacity: 0;
                }

                to {
                    opacity: 1;
                }
            }

            @media (max-width: 640px) {
                .telkom-startup-visual {
                    height: 128px;
                    width: 128px;
                }
            }

            @media (prefers-reduced-motion: reduce) {
                .telkom-startup-orbit,
                .telkom-startup-core,
                .telkom-startup-bar,
                .telkom-startup-loader::before {
                    animation-duration: 4s !important;
                }
            }
        </style>

        <section class="telkom-startup-loader __STARTUP_THEME_CLASS__" role="status" aria-label="Memuat aplikasi">
            <div class="telkom-startup-visual" aria-hidden="true">
                <span class="telkom-startup-orbit orbit-one"></span>
                <span class="telkom-startup-orbit orbit-two"></span>
                <span class="telkom-startup-orbit orbit-three"></span>

                <span class="telkom-startup-core">
                    <span class="telkom-startup-bar"></span>
                    <span class="telkom-startup-bar"></span>
                    <span class="telkom-startup-bar"></span>
                </span>
            </div>
        </section>
        """
    ).replace("__STARTUP_THEME_CLASS__", kelas_tema)

def tampilkan_loading_awal():
    """Tampilkan animasi loading awal tanpa teks selama pemeriksaan sesi."""
    placeholder = None

    try:
        placeholder = st.empty()
        placeholder.markdown(
            _buat_html_loading_awal(),
            unsafe_allow_html=True,
        )
    except Exception:
        LOGGER.exception("Loading awal aplikasi gagal ditampilkan")

    return placeholder



def _buat_html_loading_aksi(label: str = "Menganalisis komentar") -> str:
    """Bangun overlay aksi yang halus tanpa pergantian teks."""
    label_aman = escape(str(label or "Memproses"))
    kelas_tema = "telkom-action-dark" if _is_dark_mode() else "telkom-action-light"
    return _compact_html(
        f"""
        <style>
            .telkom-action-loader,
            .telkom-action-loader * {{
                box-sizing: border-box;
            }}

            .telkom-action-loader {{
                align-items: center;
                animation: telkom-action-fade-in 190ms ease-out both;
                backdrop-filter: blur(6px);
                -webkit-backdrop-filter: blur(6px);
                background: rgba(13, 13, 13, 0.78);
                display: flex;
                inset: 0;
                justify-content: center;
                padding: 24px;
                position: fixed;
                z-index: 2147483645;
            }}

            .telkom-action-panel {{
                align-items: center;
                animation: telkom-action-panel-in 210ms ease-out both;
                background:
                    radial-gradient(
                        circle at 50% 0%,
                        rgba(229, 57, 53, 0.16),
                        transparent 45%
                    ),
                    linear-gradient(180deg, #1B1B1B, #151515);
                border: 1px solid #343434;
                border-radius: 22px;
                box-shadow:
                    0 30px 80px rgba(0, 0, 0, 0.58),
                    0 0 0 1px rgba(229, 57, 53, 0.05) inset;
                display: flex;
                flex-direction: column;
                gap: 18px;
                justify-content: center;
                min-height: 220px;
                padding: 30px 36px;
                width: min(88vw, 330px);
            }}

            .telkom-action-visual {{
                height: 104px;
                position: relative;
                width: 104px;
            }}

            .telkom-action-ring {{
                animation: telkom-action-spin 1.35s linear infinite;
                border: 2px solid rgba(255, 255, 255, 0.12);
                border-radius: 50%;
                inset: 4px;
                position: absolute;
            }}

            .telkom-action-ring::after {{
                background: #E53935;
                border: 3px solid #171717;
                border-radius: 50%;
                box-shadow: 0 0 18px rgba(229, 57, 53, 0.82);
                content: "";
                height: 15px;
                left: 50%;
                position: absolute;
                top: -8px;
                transform: translateX(-50%);
                width: 15px;
            }}

            .telkom-action-ring.ring-two {{
                animation-direction: reverse;
                animation-duration: 2s;
                border-color: rgba(229, 57, 53, 0.26);
                inset: 20px;
            }}

            .telkom-action-core {{
                align-items: flex-end;
                animation: telkom-action-pulse 1.1s ease-in-out infinite;
                background: linear-gradient(145deg, #E53935, #B71C1C);
                border: 1px solid rgba(255, 255, 255, 0.20);
                border-radius: 16px;
                box-shadow: 0 12px 28px rgba(183, 28, 28, 0.36);
                display: flex;
                gap: 4px;
                height: 44px;
                justify-content: center;
                left: 50%;
                padding: 10px 11px;
                position: absolute;
                top: 50%;
                transform: translate(-50%, -50%);
                width: 44px;
            }}

            .telkom-action-core span {{
                animation: telkom-action-wave 0.75s ease-in-out infinite alternate;
                background: #FFFFFF;
                border-radius: 999px;
                display: block;
                height: 45%;
                width: 4px;
            }}

            .telkom-action-core span:nth-child(2) {{
                animation-delay: 0.12s;
                height: 72%;
            }}

            .telkom-action-core span:nth-child(3) {{
                animation-delay: 0.24s;
                height: 100%;
            }}

            .telkom-action-label {{
                color: #F5F5F5;
                font-family: "Inter", sans-serif;
                font-size: 0.92rem;
                font-weight: 700;
                letter-spacing: -0.01em;
                margin: 0;
                text-align: center;
            }}

            .telkom-action-loader.telkom-action-light {{
                background: rgba(247, 248, 250, 0.82);
            }}

            .telkom-action-loader.telkom-action-light .telkom-action-panel {{
                background:
                    radial-gradient(
                        circle at 50% 0%,
                        rgba(229, 57, 53, 0.12),
                        transparent 45%
                    ),
                    linear-gradient(180deg, #FFFFFF, #F8FAFC);
                border-color: rgba(148, 163, 184, 0.30);
                box-shadow:
                    0 30px 80px rgba(15, 23, 42, 0.16),
                    0 0 0 1px rgba(229, 57, 53, 0.05) inset;
            }}

            .telkom-action-loader.telkom-action-light .telkom-action-ring {{
                border-color: rgba(15, 23, 42, 0.15);
            }}

            .telkom-action-loader.telkom-action-light .telkom-action-ring::after {{
                border-color: #FFFFFF;
            }}

            .telkom-action-loader.telkom-action-light .telkom-action-ring.ring-two {{
                border-color: rgba(229, 57, 53, 0.28);
            }}

            .telkom-action-loader.telkom-action-light .telkom-action-label {{
                color: #111827 !important;
            }}

            @keyframes telkom-action-fade-in {{
                from {{
                    opacity: 0;
                }}

                to {{
                    opacity: 1;
                }}
            }}

            @keyframes telkom-action-panel-in {{
                from {{
                    opacity: 0;
                    transform: translateY(8px) scale(0.98);
                }}

                to {{
                    opacity: 1;
                    transform: translateY(0) scale(1);
                }}
            }}

            @keyframes telkom-action-spin {{
                to {{
                    transform: rotate(360deg);
                }}
            }}

            @keyframes telkom-action-pulse {{
                0%, 100% {{
                    transform: translate(-50%, -50%) scale(0.96);
                }}

                50% {{
                    transform: translate(-50%, -50%) scale(1.04);
                }}
            }}

            @keyframes telkom-action-wave {{
                from {{
                    transform: scaleY(0.5);
                }}

                to {{
                    transform: scaleY(1);
                }}
            }}
        </style>

        <section class="telkom-action-loader {kelas_tema}" role="status" aria-live="polite" aria-label="{label_aman}">
            <div class="telkom-action-panel">
                <div class="telkom-action-visual" aria-hidden="true">
                    <span class="telkom-action-ring ring-one"></span>
                    <span class="telkom-action-ring ring-two"></span>
                    <span class="telkom-action-core">
                        <span></span>
                        <span></span>
                        <span></span>
                    </span>
                </div>
                <p class="telkom-action-label">{label_aman}</p>
            </div>
        </section>
        """
    )


def mulai_loading_aksi(label: str = "Menganalisis komentar") -> LoadingHandle:
    """Tampilkan satu overlay lokal tanpa menumpuk overlay global yang aktif."""
    placeholder = None
    try:
        # Saat perpindahan halaman, router sudah menampilkan overlay global.
        # Jangan membuat overlay aksi kedua karena dua lapisan tersebut membuat
        # judul/pesan loading terlihat bertumpuk pada rerun yang sama.
        if bool(st.session_state.get(SESSION_GLOBAL_ACTIVE, False)):
            return LoadingHandle(
                placeholder=None,
                mulai_pada=time.monotonic(),
                konteks="Aksi",
                global_scope=False,
            )

        placeholder = st.empty()
        placeholder.markdown(
            _buat_html_loading_aksi(label),
            unsafe_allow_html=True,
        )
    except Exception:
        LOGGER.exception("Overlay loading aksi gagal ditampilkan")

    return LoadingHandle(
        placeholder=placeholder,
        mulai_pada=time.monotonic(),
        konteks="Aksi",
        global_scope=False,
    )


def selesaikan_loading_aksi(handle: LoadingHandle | None) -> None:
    """Tutup overlay aksi segera setelah proses selesai."""
    try:
        if handle is not None and handle.placeholder is not None:
            handle.placeholder.empty()
    except Exception:
        LOGGER.exception("Overlay loading aksi gagal ditutup")
def mulai_loading_global(
    konteks: str,
    judul: str | None = None,
    pesan: Iterable[str] | None = None,
) -> LoadingHandle:
    """Tampilkan overlay global untuk satu proses render halaman atau aksi."""
    placeholder = None
    try:
        judul_final, pesan_final = _konfigurasi_loading(konteks, judul, pesan)
        st.session_state[SESSION_GLOBAL_ACTIVE] = True
        placeholder = st.empty()
        placeholder.markdown(
            _buat_html_loading(judul_final, pesan_final),
            unsafe_allow_html=True,
        )
    except Exception:
        LOGGER.exception("Overlay loading global gagal ditampilkan untuk %s", konteks)

    return LoadingHandle(
        placeholder=placeholder,
        mulai_pada=time.monotonic(),
        konteks=konteks,
        global_scope=True,
    )


def selesaikan_loading_global(handle: LoadingHandle | None) -> None:
    """Tutup overlay global tanpa menambahkan jeda buatan pada aplikasi."""
    try:
        if handle is not None and handle.placeholder is not None:
            handle.placeholder.empty()
    except Exception:
        LOGGER.exception("Overlay loading global gagal ditutup")
    finally:
        try:
            st.session_state[SESSION_GLOBAL_ACTIVE] = False
        except Exception:
            LOGGER.exception("Status overlay global gagal dibersihkan")


@contextmanager
def layar_loading(
    konteks: str,
    judul: str | None = None,
    pesan: Iterable[str] | None = None,
) -> Iterator[LoadingHandle]:
    """Bungkus proses render atau aksi menggunakan overlay loading global."""
    handle = mulai_loading_global(konteks, judul=judul, pesan=pesan)
    try:
        yield handle
    finally:
        selesaikan_loading_global(handle)


# ---------------------------------------------------------------------------
# Kompatibilitas untuk integrasi lama pada pages/home.py dan pages/dataset.py.
# App utama sekarang memakai overlay global. Ketika overlay global aktif,
# pemanggilan lama ini tidak menampilkan overlay kedua.
# ---------------------------------------------------------------------------

def mulai_layar_loading(
    state_key: str,
    pesan: Iterable[str] | None = None,
):
    """Tampilkan loading satu kali ketika halaman dijalankan di luar router global."""
    try:
        if bool(st.session_state.get(SESSION_GLOBAL_ACTIVE, False)):
            return None
        if bool(st.session_state.get(state_key, False)):
            return None

        handle = mulai_loading_global(
            konteks="Halaman",
            judul="Menyiapkan Dashboard",
            pesan=pesan,
        )
        handle.global_scope = False
        return handle
    except Exception:
        LOGGER.exception("Layar loading kompatibilitas gagal untuk %s", state_key)
        return None


def selesaikan_layar_loading(placeholder, state_key: str) -> None:
    """Tutup loading kompatibilitas dan tandai halaman telah selesai dimuat."""
    try:
        st.session_state[state_key] = True
        if isinstance(placeholder, LoadingHandle):
            selesaikan_loading_global(placeholder)
        elif placeholder is not None:
            placeholder.empty()
    except Exception:
        LOGGER.exception("Layar loading kompatibilitas gagal ditutup untuk %s", state_key)


def batalkan_layar_loading(placeholder, state_key: str) -> None:
    """Tutup loading kompatibilitas tanpa menyimpan status keberhasilan."""
    try:
        st.session_state.pop(state_key, None)
        if isinstance(placeholder, LoadingHandle):
            selesaikan_loading_global(placeholder)
        elif placeholder is not None:
            placeholder.empty()
    except Exception:
        LOGGER.exception("Layar loading kompatibilitas gagal dibatalkan untuk %s", state_key)
