"""Konfigurasi versi Dashboard Analisis Telkom Group."""

# Metadata fase aktif.
# Pada fase berikutnya, cukup naikkan CURRENT_PHASE satu angka.
CURRENT_STAGE = 5
CURRENT_PHASE = 3

# Tahap 5 Fase 3 dimulai dari Versi 5.0.
# Karena itu, setiap kenaikan satu fase otomatis menaikkan versi minor 0.1.
_VERSION_MINOR = max(0, CURRENT_PHASE - 3)
DASHBOARD_VERSION = f"{CURRENT_STAGE}.{_VERSION_MINOR}"

PENELITI = "Aulia Rahmadiva Wardana"
INSTITUSI = "ULBI 2026"


def get_auth_footer_text() -> str:
    """Menghasilkan teks versi konsisten untuk halaman autentikasi."""
    return f"Versi {DASHBOARD_VERSION} | {PENELITI} | {INSTITUSI}"

def get_sidebar_footer_text() -> str:
    """Menghasilkan teks versi ringkas untuk footer sidebar."""
    return f"v{DASHBOARD_VERSION} · {INSTITUSI}"

