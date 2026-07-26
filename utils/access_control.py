"""Konfigurasi role dan hak akses dashboard Telkom Group.

Modul ini menjadi satu-satunya sumber aturan Role-Based Access Control (RBAC)
untuk sidebar, routing, autentikasi, profil, dan Admin Panel.
"""

from __future__ import annotations

ROLE_MANAGEMENT = "management"
ROLE_DATA_ANALYST = "data_analyst"
ROLE_SOCIAL_MEDIA_OFFICER = "social_media_officer"

DEFAULT_ROLE = ROLE_MANAGEMENT
VALID_ROLES = (
    ROLE_MANAGEMENT,
    ROLE_DATA_ANALYST,
    ROLE_SOCIAL_MEDIA_OFFICER,
)

ROLE_LABELS = {
    ROLE_MANAGEMENT: "Manajemen",
    ROLE_DATA_ANALYST: "Data Analis",
    ROLE_SOCIAL_MEDIA_OFFICER: "Sosmed Officer",
}

ROLE_ICONS = {
    ROLE_MANAGEMENT: "💼",
    ROLE_DATA_ANALYST: "🛡️",
    ROLE_SOCIAL_MEDIA_OFFICER: "📣",
}

ALL_DASHBOARD_ROUTES = (
    "Beranda",
    "Dataset",
    "Analisis Sentimen",
    "Analisis Topik",
    "Analisis Jaringan Sosial",
    "Rekomendasi",
    "Profil",
    "Admin Panel",
    "Tentang Penelitian",
)

ROLE_ROUTE_ACCESS = {
    ROLE_MANAGEMENT: (
        "Beranda",
        "Rekomendasi",
    ),
    ROLE_DATA_ANALYST: ALL_DASHBOARD_ROUTES,
    ROLE_SOCIAL_MEDIA_OFFICER: (
        "Beranda",
        "Analisis Jaringan Sosial",
        "Rekomendasi",
        "Profil",
        "Tentang Penelitian",
    ),
}

# Urutan digunakan tombol "Ubah Role" pada Admin Panel. Maksimal dua klik
# diperlukan untuk berpindah ke role mana pun tanpa menambah komponen UI baru.
ROLE_CYCLE = (
    ROLE_MANAGEMENT,
    ROLE_SOCIAL_MEDIA_OFFICER,
    ROLE_DATA_ANALYST,
)

_LEGACY_ROLE_MAP = {
    "admin": ROLE_DATA_ANALYST,
    "administrator": ROLE_DATA_ANALYST,
    "data analyst": ROLE_DATA_ANALYST,
    "data analis": ROLE_DATA_ANALYST,
    "data_analis": ROLE_DATA_ANALYST,
    "user": ROLE_MANAGEMENT,
    "researcher": ROLE_MANAGEMENT,
    "manajemen": ROLE_MANAGEMENT,
    "sosmed officer": ROLE_SOCIAL_MEDIA_OFFICER,
    "sosmed_officer": ROLE_SOCIAL_MEDIA_OFFICER,
    "social media officer": ROLE_SOCIAL_MEDIA_OFFICER,
}


def normalize_role(role: object, user_id: object | None = None) -> str:
    """Normalisasi role lama/asing menjadi salah satu role resmi.

    Akun utama ``user_id=1`` selalu dipertahankan sebagai Data Analis agar
    pengelolaan pengguna tidak kehilangan pemilik utama.
    """
    try:
        if int(user_id) == 1:
            return ROLE_DATA_ANALYST
    except (TypeError, ValueError):
        pass

    value = str(role or "").strip().lower()
    if value in VALID_ROLES:
        return value
    if value in _LEGACY_ROLE_MAP:
        return _LEGACY_ROLE_MAP[value]
    return DEFAULT_ROLE


def get_role_label(role: object, user_id: object | None = None) -> str:
    """Kembalikan label role Bahasa Indonesia untuk antarmuka."""
    normalized = normalize_role(role, user_id=user_id)
    return ROLE_LABELS[normalized]


def get_role_icon(role: object, user_id: object | None = None) -> str:
    """Kembalikan ikon sederhana sesuai role."""
    normalized = normalize_role(role, user_id=user_id)
    return ROLE_ICONS[normalized]


def get_allowed_routes(role: object, user_id: object | None = None) -> tuple[str, ...]:
    """Kembalikan daftar route yang boleh dibuka role tertentu."""
    normalized = normalize_role(role, user_id=user_id)
    return ROLE_ROUTE_ACCESS[normalized]


def can_access_route(
    role: object,
    route: object,
    user_id: object | None = None,
) -> bool:
    """Periksa izin membuka sebuah route dashboard."""
    route_name = str(route or "").strip()
    return route_name in get_allowed_routes(role, user_id=user_id)


def get_next_role(role: object) -> str:
    """Kembalikan role berikutnya untuk tombol siklus role Admin Panel."""
    normalized = normalize_role(role)
    try:
        index = ROLE_CYCLE.index(normalized)
    except ValueError:
        return DEFAULT_ROLE
    return ROLE_CYCLE[(index + 1) % len(ROLE_CYCLE)]
