# utils/gemini_client.py
"""Klien Gemini API yang aman, tahan gangguan, dan bersih dari error secrets lokal."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
import logging
import os
import re
from pathlib import Path
from typing import Any

import streamlit as st

try:
    # Kompatibilitas dengan spesifikasi awal proyek. SDK aktif tetap google-genai
    # karena sudah digunakan dan diverifikasi pada Fase 10-11.
    import google.generativeai as genai  # type: ignore
except Exception:  # pragma: no cover - dependency legacy bersifat opsional
    genai = None

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

# Model utama dan cadangan dipertahankan dari patch yang sudah terbukti berhasil.
DEFAULT_MODEL_NAME = "gemini-3.5-flash"
FALLBACK_MODEL_NAMES = ("gemini-3.1-flash-lite",)
_PLACEHOLDER_KEYS = {
    "",
    "your_api_key_here",
    "masukkan_api_key_di_sini",
    "masukkan_api_key_anda_di_sini",
    "tempel_api_key_anda_di_sini",
}
_TRANSIENT_STATUS_CODES = {404, 408, 429, 500, 502, 503, 504}

# Status ini dibaca halaman rekomendasi tanpa pernah mengekspos API key.
GEMINI_AVAILABLE = False


@dataclass(frozen=True)
class GeminiTextResponse:
    """Respons teks sederhana beserta nama model yang benar-benar digunakan."""

    text: str
    model_name: str


@dataclass(frozen=True)
class GeminiModelAdapter:
    """Pembungkus Google GenAI Client agar antarmuka modul tetap kompatibel."""

    client: Any = field(compare=False, repr=False)
    model_name: str = DEFAULT_MODEL_NAME
    fallback_models: tuple[str, ...] = FALLBACK_MODEL_NAMES

    @property
    def cache_key(self) -> str:
        """Kembalikan identitas aman untuk kebutuhan cache Streamlit."""
        return "|".join((self.model_name, *self.fallback_models))

    @property
    def model_candidates(self) -> tuple[str, ...]:
        """Kembalikan urutan model utama dan model cadangan tanpa duplikasi."""
        candidates: list[str] = []
        for name in (self.model_name, *self.fallback_models):
            cleaned = _normalisasi_model_name(name)
            if cleaned and cleaned not in candidates:
                candidates.append(cleaned)
        return tuple(candidates)

    def generate_content(self, prompt: str) -> GeminiTextResponse:
        """Kirim prompt dan pindah model hanya untuk kegagalan yang layak dicoba ulang."""
        last_error: Exception | None = None

        for index, candidate in enumerate(self.model_candidates):
            try:
                response = self.client.models.generate_content(
                    model=candidate,
                    contents=prompt,
                )
                text = str(getattr(response, "text", "") or "").strip()
                if not text:
                    raise RuntimeError("Respons Gemini kosong")

                if index > 0:
                    LOGGER.warning(
                        "Model utama sedang tidak dapat melayani permintaan. "
                        "Permintaan berhasil menggunakan model cadangan %s.",
                        candidate,
                    )
                return GeminiTextResponse(text=text, model_name=candidate)
            except Exception as error:
                last_error = error
                has_next_model = index < len(self.model_candidates) - 1
                if has_next_model and _boleh_coba_model_cadangan(error):
                    LOGGER.warning(
                        "Permintaan ke model %s gagal sementara (%s). "
                        "Mencoba model cadangan.",
                        candidate,
                        type(error).__name__,
                    )
                    continue
                raise

        if last_error is not None:
            raise last_error
        raise RuntimeError("Tidak ada model Gemini yang tersedia")


def _normalisasi_api_key(value: Any) -> str:
    """Bersihkan nilai API key tanpa pernah menampilkannya ke log."""
    try:
        api_key = str(value or "").strip().strip('"').strip("'")
        if api_key.lower() in _PLACEHOLDER_KEYS:
            return ""
        return api_key
    except Exception:
        return ""


def _normalisasi_model_name(value: Any) -> str:
    """Bersihkan nama model dan gunakan model standar jika nilainya kosong."""
    try:
        model_name = str(value or "").strip().strip('"').strip("'")
        return model_name or DEFAULT_MODEL_NAME
    except Exception:
        return DEFAULT_MODEL_NAME


def _status_code_error(error: Exception) -> int | None:
    """Ambil kode status dari berbagai bentuk exception Google GenAI SDK."""
    for attribute in ("code", "status_code"):
        value = getattr(error, attribute, None)
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            continue

    response = getattr(error, "response", None)
    value = getattr(response, "status_code", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _boleh_coba_model_cadangan(error: Exception) -> bool:
    """Tentukan apakah kegagalan aman dicoba ulang menggunakan model cadangan."""
    status_code = _status_code_error(error)
    if status_code in _TRANSIENT_STATUS_CODES:
        return True

    error_name = type(error).__name__.lower()
    return any(
        marker in error_name
        for marker in ("servererror", "timeouterror", "connectionerror", "notfound")
    )


def _secret_file_candidates() -> tuple[Path, ...]:
    """Susun kandidat secrets.toml tanpa menggandakan lokasi yang sama."""
    raw_candidates = (
        PROJECT_ROOT / ".streamlit" / "secrets.toml",
        Path.cwd() / ".streamlit" / "secrets.toml",
        Path.home() / ".streamlit" / "secrets.toml",
    )
    unique: list[Path] = []
    seen: set[str] = set()

    for candidate in raw_candidates:
        try:
            resolved = candidate.expanduser().resolve()
        except Exception:
            resolved = candidate.expanduser()
        identity = str(resolved).lower()
        if identity not in seen:
            seen.add(identity)
            unique.append(resolved)
    return tuple(unique)


def _baca_toml(path: Path) -> dict[str, Any]:
    """Baca TOML memakai parser yang tersedia tanpa memicu pembaca secrets Streamlit."""
    text = path.read_text(encoding="utf-8-sig")

    try:
        import tomllib  # Python 3.11+

        data = tomllib.loads(text)
        return data if isinstance(data, dict) else {}
    except ModuleNotFoundError:
        pass
    except Exception:
        return {}

    try:
        import toml  # Dependency Streamlit pada Python 3.10

        data = toml.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return _baca_assignment_toml_sederhana(text)


def _baca_assignment_toml_sederhana(text: str) -> dict[str, Any]:
    """Fallback minimal untuk membaca GEMINI_API_KEY tingkat akar dari TOML."""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        if key.strip() != "GEMINI_API_KEY":
            continue

        value_text = raw_value.strip()
        try:
            if value_text.startswith(("\"", "'")):
                value = ast.literal_eval(value_text)
            else:
                value = value_text.split("#", 1)[0].strip()
        except Exception:
            value = value_text.strip().strip('"').strip("'")
        return {"GEMINI_API_KEY": value}
    return {}


def _cari_api_key_di_mapping(values: Any) -> str:
    """Cari GEMINI_API_KEY pada tingkat akar maupun bagian TOML bersarang."""
    if not isinstance(values, dict):
        return ""

    direct_value = _normalisasi_api_key(values.get("GEMINI_API_KEY", ""))
    if direct_value:
        return direct_value

    for nested_value in values.values():
        if isinstance(nested_value, dict):
            found = _cari_api_key_di_mapping(nested_value)
            if found:
                return found
    return ""


def _ambil_api_key_dari_secrets_file() -> str:
    """Baca secrets.toml secara langsung agar verifier beda folder tetap aman."""
    for path in _secret_file_candidates():
        if not path.is_file():
            continue
        try:
            values = _baca_toml(path)
            api_key = _cari_api_key_di_mapping(values)
            if api_key:
                return api_key
        except Exception as error:
            LOGGER.warning(
                "File secrets.toml tidak dapat dibaca (%s). Mencoba sumber berikutnya.",
                type(error).__name__,
            )
    return ""


def _baca_env_sederhana(path: Path) -> dict[str, str]:
    """Baca file .env tanpa ketergantungan tambahan seperti python-dotenv.

    Parser ini cukup untuk format KEY=VALUE yang digunakan dashboard. Nilai
    boleh ditulis dengan atau tanpa tanda kutip. Komentar dan baris kosong
    diabaikan. Isi rahasia tidak pernah dicetak ke log.
    """
    if not path.is_file():
        return {}

    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue

        value_text = raw_value.strip()
        try:
            if value_text.startswith(("\"", "'")):
                value = str(ast.literal_eval(value_text))
            else:
                value = value_text.split(" #", 1)[0].strip()
        except Exception:
            value = value_text.strip().strip("\"").strip("'")
        values[key] = value

    return values


def _ambil_api_key_dengan_sumber() -> tuple[str, str]:
    """Ambil API key dan nama sumber aman tanpa menampilkan nilai rahasia."""
    api_key = _ambil_api_key_dari_secrets_file()
    if api_key:
        return api_key, "Streamlit Secrets"

    try:
        values = _baca_env_sederhana(ENV_FILE)
        api_key = _normalisasi_api_key(values.get("GEMINI_API_KEY", ""))
        if api_key:
            return api_key, ".env"
    except Exception as error:
        LOGGER.warning(
            "File .env Gemini tidak dapat dibaca (%s).",
            type(error).__name__,
        )

    api_key = _normalisasi_api_key(os.getenv("GEMINI_API_KEY", ""))
    if api_key:
        return api_key, "environment variable"

    return "", "tidak ditemukan"


def _ambil_api_key() -> str:
    """Ambil API key dari secrets.toml, .env, atau environment variable."""
    api_key, _ = _ambil_api_key_dengan_sumber()
    return api_key


def get_gemini_key_source() -> str:
    """Kembalikan nama sumber API key secara aman tanpa membuka nilainya."""
    try:
        _, source = _ambil_api_key_dengan_sumber()
        return source
    except Exception:
        return "tidak ditemukan"


try:
    GEMINI_AVAILABLE = bool(_ambil_api_key())
except Exception:
    GEMINI_AVAILABLE = False


@st.cache_resource(show_spinner=False)
def init_gemini() -> GeminiModelAdapter | None:
    """Inisialisasi Google GenAI Client atau kembalikan None jika tidak tersedia."""
    global GEMINI_AVAILABLE

    try:
        api_key = _ambil_api_key()
        if not api_key:
            GEMINI_AVAILABLE = False
            LOGGER.warning(
                "GEMINI_API_KEY belum ditemukan. Dashboard tetap berjalan "
                "menggunakan mode fallback tanpa Gemini."
            )
            return None

        from google import genai as google_genai

        model_name = _normalisasi_model_name(
            os.getenv("GEMINI_MODEL", DEFAULT_MODEL_NAME)
        )
        client = google_genai.Client(api_key=api_key)
        GEMINI_AVAILABLE = True
        return GeminiModelAdapter(client=client, model_name=model_name)
    except Exception as error:
        GEMINI_AVAILABLE = False
        LOGGER.warning(
            "Gemini tidak dapat diinisialisasi (%s). Dashboard tetap memakai fallback.",
            type(error).__name__,
        )
        return None


@st.cache_data(
    ttl=300,
    show_spinner=False,
    hash_funcs={GeminiModelAdapter: lambda model: model.cache_key},
)
def _generate_recommendation_cached(
    model: GeminiModelAdapter,
    prompt: str,
) -> tuple[str, str]:
    """Panggil Gemini dan cache hanya respons yang benar-benar berhasil."""
    response = model.generate_content(prompt)
    return response.text, response.model_name


def generate_recommendation(
    model: GeminiModelAdapter | None,
    prompt: str,
    fallback_text: str = "",
) -> str:
    """Buat rekomendasi Gemini atau kembalikan teks fallback jika gagal."""
    try:
        if model is None:
            return str(fallback_text or "")

        prompt_bersih = str(prompt or "").strip()
        if not prompt_bersih:
            return str(fallback_text or "")

        hasil, _ = _generate_recommendation_cached(model, prompt_bersih)
        return hasil if hasil else str(fallback_text or "")
    except Exception as error:
        LOGGER.warning(
            "Permintaan rekomendasi Gemini gagal (%s). Menggunakan fallback lokal.",
            type(error).__name__,
        )
        return str(fallback_text or "")


def test_gemini_connection(
    prompt: str = "Balas tepat dengan satu kata: TERHUBUNG",
) -> dict[str, str | bool]:
    """Uji koneksi langsung dan kembalikan status aman tanpa API key."""
    try:
        model = init_gemini()
        if model is None:
            return {
                "success": False,
                "model": "",
                "source": get_gemini_key_source(),
                "message": "API key belum terbaca atau client belum tersedia.",
            }

        response = model.generate_content(str(prompt or "").strip())
        return {
            "success": bool(response.text),
            "model": response.model_name,
            "source": get_gemini_key_source(),
            "message": response.text,
        }
    except Exception as error:
        status_code = _status_code_error(error)
        code_text = str(status_code) if status_code is not None else "tanpa kode"
        return {
            "success": False,
            "model": "",
            "source": get_gemini_key_source(),
            "message": f"{type(error).__name__} ({code_text})",
        }


def is_gemini_available() -> bool:
    """Periksa apakah Google GenAI Client dapat diinisialisasi tanpa raise error."""
    try:
        return init_gemini() is not None
    except Exception as error:
        LOGGER.warning(
            "Pemeriksaan ketersediaan Gemini gagal (%s).",
            type(error).__name__,
        )
        return False


# -----------------------------------------------------------------------------
# TAHAP 4 | FASE 11 - GENERATOR IDE KONTEN MEDIA SOSIAL
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# TAHAP 4 | FASE 11 - GENERATOR IDE KONTEN MEDIA SOSIAL
# -----------------------------------------------------------------------------
CONTENT_IDEA_MODEL_NAME = "gemini-1.5-flash"
CONTENT_IDEA_TEMPERATURE = 0.7
CONTENT_IDEA_MAX_WORDS = 300
CONTENT_IDEA_MAX_OUTPUT_TOKENS = 1024
_CONTENT_IDEA_PROTOCOL_KEYS = (
    "JUDUL_KONTEN",
    "IDE_1",
    "IDE_2",
    "IDE_3",
    "CTA",
)

# Fallback statis untuk seluruh kombinasi sentimen dan platform. Setiap nilai
# berisi tiga ide lengkap agar halaman tetap berguna ketika API key kosong,
# kuota habis, respons kosong, atau koneksi internet bermasalah.
FALLBACK_IDEAS: dict[str, dict[str, str]] = {
    "positif": {
        "Instagram": (
            "1. Cerita Pelanggan — Buat carousel testimoni yang menampilkan pengalaman positif pelanggan secara ringkas dan autentik.\n"
            "2. Momen Terbaik Layanan — Tampilkan visual pencapaian layanan, respons cepat, atau manfaat yang paling dirasakan pengguna.\n"
            "3. Apresiasi Komunitas — Ajak audiens membagikan pengalaman terbaik mereka melalui komentar atau Stories."
        ),
        "TikTok": (
            "1. Reaksi Pelanggan — Buat video singkat yang merangkum pengalaman positif pengguna dengan gaya cepat dan natural.\n"
            "2. Tiga Manfaat Utama — Sajikan tiga manfaat layanan melalui transisi visual, teks layar, dan contoh penggunaan sehari-hari.\n"
            "3. Duet Pengalaman — Dorong pengguna membuat duet atau stitch berisi pengalaman terbaik mereka menggunakan layanan."
        ),
        "Twitter": (
            "1. Thread Apresiasi — Susun thread singkat berisi pengalaman positif pengguna dan manfaat layanan yang paling relevan.\n"
            "2. Kutipan Pelanggan — Bagikan kutipan pengguna dengan konteks yang jelas tanpa membuka data pribadi.\n"
            "3. Polling Pengalaman — Buat polling tentang fitur atau manfaat layanan yang paling disukai pelanggan."
        ),
    },
    "netral": {
        "Instagram": (
            "1. Panduan Praktis — Buat carousel langkah demi langkah untuk membantu pelanggan memahami fitur atau prosedur layanan.\n"
            "2. FAQ Ringkas — Sajikan pertanyaan yang paling sering muncul dalam format infografis yang mudah disimpan.\n"
            "3. Kenali Layanan — Jelaskan paket, manfaat, dan kanal bantuan dengan bahasa sederhana tanpa klaim berlebihan."
        ),
        "TikTok": (
            "1. Tutorial 30 Detik — Buat video langkah cepat untuk menggunakan fitur atau menyelesaikan kebutuhan umum pelanggan.\n"
            "2. Mitos atau Fakta — Jawab kebingungan pengguna melalui format mitos versus fakta yang mudah dipahami.\n"
            "3. Tanya Admin — Kumpulkan pertanyaan umum lalu jawab satu per satu dalam seri video pendek."
        ),
        "Twitter": (
            "1. Thread Penjelasan — Uraikan informasi layanan dalam beberapa cuitan pendek dengan urutan yang jelas.\n"
            "2. FAQ Harian — Jawab satu pertanyaan pelanggan setiap hari menggunakan bahasa langsung dan informatif.\n"
            "3. Polling Kebutuhan — Gunakan polling untuk mengetahui informasi layanan yang paling dibutuhkan audiens."
        ),
    },
    "negatif": {
        "Instagram": (
            "1. Konten Empati — Posting carousel yang mengakui keluhan pengguna dan menunjukkan langkah nyata perbaikan layanan.\n"
            "2. Behind The Scene — Video singkat proses teknisi turun lapangan menangani gangguan jaringan.\n"
            "3. FAQ Solusi Cepat — Infografis tips mandiri saat internet terasa lambat sebelum menghubungi CS."
        ),
        "TikTok": (
            "1. Respons Cepat — Buat video singkat yang mengakui masalah dan menjelaskan langkah aman yang dapat dilakukan pelanggan.\n"
            "2. Proses Penanganan — Tampilkan alur kerja tim dalam menangani keluhan tanpa menjanjikan waktu yang belum pasti.\n"
            "3. Tips Sebelum Lapor — Sajikan pemeriksaan dasar yang dapat dilakukan pengguna sebelum menghubungi layanan pelanggan."
        ),
        "Twitter": (
            "1. Thread Status Layanan — Sampaikan kondisi, wilayah terdampak, dan kanal pembaruan resmi secara berkala.\n"
            "2. Respons Empatik — Gunakan balasan singkat yang mengakui keluhan lalu arahkan pelanggan ke kanal bantuan aman.\n"
            "3. Klarifikasi Fakta — Jelaskan penyebab umum masalah dan langkah penanganan tanpa menyalahkan pengguna."
        ),
    },
}


def _fallback_sentiment_key(value: Any) -> str:
    """Ubah variasi label sentimen menjadi kunci fallback Bahasa Indonesia."""
    normalized = str(value or "").strip().casefold()
    mapping = {
        "positive": "positif",
        "positif": "positif",
        "neutral": "netral",
        "netral": "netral",
        "negative": "negatif",
        "negatif": "negatif",
    }
    return mapping.get(normalized, "netral")


def _fallback_platform_key(value: Any) -> str:
    """Ubah variasi nama platform menjadi kunci fallback yang tersedia."""
    normalized = str(value or "").strip().casefold()
    if "insta" in normalized:
        return "Instagram"
    if "tiktok" in normalized or "tik tok" in normalized:
        return "TikTok"
    return "Twitter"


def get_fallback_content_idea(
    layanan: str,
    platform: str,
    topik: str,
    sentimen: str,
) -> str:
    """Kembalikan fallback lengkap untuk halaman rekomendasi."""
    clean_layanan = _normalisasi_parameter_content_idea(layanan, "Telkom Group")
    clean_platform = _fallback_platform_key(platform)
    clean_topik = _normalisasi_parameter_content_idea(topik, "Topik Layanan")
    sentiment_key = _fallback_sentiment_key(sentimen)
    ideas = FALLBACK_IDEAS[sentiment_key][clean_platform]
    return (
        f"📌 JUDUL KONTEN: Respons {clean_layanan} untuk {clean_topik}\n\n"
        f"💡 IDE KONTEN:\n{ideas}\n\n"
        "🎯 CALL TO ACTION:\n"
        f"Ajak pelanggan mengikuti kanal resmi {clean_layanan} dan menggunakan kanal bantuan resmi bila memerlukan penanganan lanjutan."
    )


def _normalisasi_parameter_content_idea(value: Any, default: str) -> str:
    """Bersihkan parameter teks agar prompt dan fallback selalu memiliki nilai."""
    try:
        cleaned = str(value or "").strip()
        return cleaned or default
    except Exception:
        return default


def _normalisasi_keywords_content_idea(keywords: Any) -> list[str]:
    """Ubah kata kunci menjadi daftar ringkas tanpa nilai kosong dan duplikat."""
    try:
        if isinstance(keywords, str):
            raw_items = [item.strip() for item in keywords.split(",")]
        elif isinstance(keywords, (list, tuple, set)):
            raw_items = [str(item or "").strip() for item in keywords]
        else:
            raw_items = []

        hasil: list[str] = []
        seen: set[str] = set()
        for item in raw_items:
            if not item:
                continue
            identity = item.casefold()
            if identity in seen:
                continue
            seen.add(identity)
            hasil.append(item)
            if len(hasil) >= 12:
                break
        return hasil
    except Exception:
        return []


def _build_content_idea_fallback(
    topic_name: str,
    platform: str,
    layanan: str,
    sentiment: str = "netral",
) -> str:
    """Bangun fallback lokal dari FALLBACK_IDEAS tanpa koneksi Gemini."""
    return get_fallback_content_idea(
        layanan=layanan,
        platform=platform,
        topik=topic_name,
        sentimen=sentiment,
    )


def _build_content_idea_prompt(
    topic_name: str,
    keywords: list[str],
    platform: str,
    sentiment: str,
    layanan: str,
) -> str:
    """Susun prompt lima baris yang stabil dan mudah dibaca lintas versi SDK."""
    keyword_text = ", ".join(keywords) if keywords else "tidak ada kata kunci tambahan"
    return f"""
Anda adalah content strategist media sosial untuk layanan digital di Indonesia.
Buat ide konten berdasarkan konteks berikut:
- Layanan: {layanan}
- Platform: {platform}
- Sentimen dominan: {sentiment}
- Topik: {topic_name}
- Kata kunci: {keyword_text}

Gunakan Bahasa Indonesia yang natural, spesifik, aman, dan relevan dengan karakter {platform}.
Jangan membuat klaim teknis, angka, estimasi waktu perbaikan, atau janji layanan yang tidak diberikan.
Total isi maksimal {CONTENT_IDEA_MAX_WORDS} kata.

Keluarkan TEPAT lima baris berikut. Jangan gunakan JSON, Markdown, bullet tambahan, atau paragraf pembuka.
Jangan memakai karakter pemisah ||| di dalam isi.

JUDUL_KONTEN|||judul yang menarik dan ringkas
IDE_1|||ide pertama dengan deskripsi singkat
IDE_2|||ide kedua dengan deskripsi singkat
IDE_3|||ide ketiga dengan deskripsi singkat
CTA|||satu kalimat ajakan bertindak yang kuat
""".strip()


def _content_idea_model_candidates(model: GeminiModelAdapter) -> tuple[str, ...]:
    """Prioritaskan model spesifikasi, lalu gunakan model Fase 10 sebagai cadangan."""
    candidates: list[str] = []
    for name in (CONTENT_IDEA_MODEL_NAME, *model.model_candidates):
        cleaned = _normalisasi_model_name(name)
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)
    return tuple(candidates)


def _bersihkan_nilai_content_idea(value: Any, max_words: int) -> str:
    """Bersihkan satu field hasil Gemini dan batasi panjangnya secara aman."""
    try:
        text = str(value or "").strip()
        text = text.replace("```", "").replace("**", "").replace("__", "")
        text = re.sub(r"^[-•*#>\s]+", "", text)
        text = re.sub(r"\s+", " ", text).strip(" \t\r\n|:-")
        words = text.split()
        if len(words) > max_words:
            text = " ".join(words[:max_words]).rstrip(" ,.;:") + "…"
        return text
    except Exception:
        return ""


def _format_content_idea_canonical(title: Any, ideas: Any, cta: Any) -> str:
    """Ubah field terpisah menjadi format akhir Judul, tiga Ide, dan CTA."""
    try:
        clean_title = _bersihkan_nilai_content_idea(title, 24)
        clean_cta = _bersihkan_nilai_content_idea(cta, 40)
        raw_ideas = list(ideas) if isinstance(ideas, (list, tuple)) else []

        clean_ideas: list[str] = []
        seen: set[str] = set()
        for raw_item in raw_ideas:
            item = _bersihkan_nilai_content_idea(raw_item, 65)
            identity = item.casefold()
            if item and identity not in seen:
                seen.add(identity)
                clean_ideas.append(item)
            if len(clean_ideas) == 3:
                break

        if not clean_title or len(clean_ideas) != 3 or not clean_cta:
            return ""

        result = (
            f"📌 JUDUL KONTEN: {clean_title}\n\n"
            "💡 IDE KONTEN:\n"
            f"1. {clean_ideas[0]}\n"
            f"2. {clean_ideas[1]}\n"
            f"3. {clean_ideas[2]}\n\n"
            "🎯 CALL TO ACTION:\n"
            f"{clean_cta}"
        )
        if len(result.split()) > CONTENT_IDEA_MAX_WORDS:
            return ""
        return result
    except Exception:
        return ""


def _normalisasi_protocol_key(value: Any) -> str:
    """Samakan variasi nama field lima-baris dari respons model."""
    try:
        key = str(value or "").upper().strip()
        key = re.sub(r"[^A-Z0-9]+", "_", key).strip("_")
        aliases = {
            "JUDUL": "JUDUL_KONTEN",
            "TITLE": "JUDUL_KONTEN",
            "JUDUL_CONTENT": "JUDUL_KONTEN",
            "JUDUL_KONTEN": "JUDUL_KONTEN",
            "IDE_KONTEN_1": "IDE_1",
            "IDE_KONTEN_2": "IDE_2",
            "IDE_KONTEN_3": "IDE_3",
            "IDE1": "IDE_1",
            "IDE_01": "IDE_1",
            "IDE2": "IDE_2",
            "IDE_02": "IDE_2",
            "IDE3": "IDE_3",
            "IDE_03": "IDE_3",
            "CALL_TO_ACTION": "CTA",
            "CALLTOACTION": "CTA",
            "AJAKAN": "CTA",
        }
        return aliases.get(key, key)
    except Exception:
        return ""


def _parse_content_idea_protocol(text: Any) -> str:
    """Baca protokol lima baris dan toleransi baris yang terbungkus otomatis."""
    try:
        raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
        raw = raw.replace("```text", "").replace("```", "")
        # Jika model menaruh semua field pada satu baris, sisipkan pemisah baris.
        raw = re.sub(
            r"(?i)(?<!^)(?=(?:JUDUL[ _-]*(?:KONTEN)?|TITLE|IDE[ _-]*(?:KONTEN[ _-]*)?0?[123]|CTA|CALL[ _-]*TO[ _-]*ACTION|AJAKAN)\s*(?:\|{2,3}|:|=|-)+)",
            "\n",
            raw,
        )
        fields: dict[str, str] = {}
        current_key = ""

        for raw_line in raw.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            line = re.sub(r"^[#>*•\-\s]+", "", line).strip()

            match = re.match(
                r"^(JUDUL(?:[ _-]*KONTEN)?|TITLE|IDE[ _-]*(?:KONTEN[ _-]*)?0?[123]|CTA|CALL[ _-]*TO[ _-]*ACTION|AJAKAN)\s*(?:\|{2,3}|:|=|-)+\s*(.*)$",
                line,
                flags=re.IGNORECASE,
            )
            if match:
                key = _normalisasi_protocol_key(match.group(1))
                if key in _CONTENT_IDEA_PROTOCOL_KEYS:
                    current_key = key
                    fields[key] = match.group(2).strip()
                    continue

            if current_key:
                fields[current_key] = f"{fields.get(current_key, '')} {line}".strip()

        title = fields.get("JUDUL_KONTEN", "")
        ideas = [fields.get(f"IDE_{number}", "") for number in (1, 2, 3)]
        cta = fields.get("CTA", "")
        return _format_content_idea_canonical(title, ideas, cta)
    except Exception:
        return ""


def _parse_content_idea_markdown(text: Any) -> str:
    """Cadangan parser untuk respons yang tetap memakai format Markdown lama."""
    try:
        raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
        raw = raw.replace("```markdown", "").replace("```text", "").replace("```", "")
        raw = raw.replace("**", "").replace("__", "").replace("：", ":")
        lines = [re.sub(r"^[#>*\s]+", "", line).strip() for line in raw.splitlines()]

        title = ""
        cta = ""
        ideas: dict[int, str] = {}
        section = ""
        current_idea: int | None = None

        for line in lines:
            if not line:
                continue
            title_match = re.match(r"^(?:📌\s*)?JUDUL(?:\s+KONTEN)?\s*[:\-]\s*(.*)$", line, re.I)
            cta_match = re.match(r"^(?:🎯\s*)?(?:CALL\s+TO\s+ACTION|CTA)\s*[:\-]\s*(.*)$", line, re.I)
            idea_header = re.match(r"^(?:💡\s*)?IDE(?:\s+KONTEN)?\s*:?\s*$", line, re.I)
            numbered = re.match(r"^(?:IDE\s*)?([123])\s*[.)\-:]\s*(.+)$", line, re.I)

            if title_match:
                title = title_match.group(1).strip()
                section = "title"
                continue
            if idea_header:
                section = "ideas"
                continue
            if cta_match:
                cta = cta_match.group(1).strip()
                section = "cta"
                current_idea = None
                continue
            if numbered:
                current_idea = int(numbered.group(1))
                ideas[current_idea] = numbered.group(2).strip()
                section = "ideas"
                continue

            if section == "title" and not title:
                title = line
            elif section == "cta":
                cta = f"{cta} {line}".strip()
            elif section == "ideas" and current_idea in (1, 2, 3):
                ideas[current_idea] = f"{ideas.get(current_idea, '')} {line}".strip()

        return _format_content_idea_canonical(
            title,
            [ideas.get(number, "") for number in (1, 2, 3)],
            cta,
        )
    except Exception:
        return ""


def _parse_content_idea_json_simple(text: Any) -> str:
    """Cadangan ringan jika model tetap membalas JSON walau tidak diminta."""
    try:
        raw = str(text or "").strip().replace("```json", "").replace("```", "")
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return ""
        payload = json.loads(raw[start : end + 1])
        if not isinstance(payload, dict):
            return ""

        normalized = {str(key).casefold(): value for key, value in payload.items()}
        title = normalized.get("judul_konten") or normalized.get("judul") or normalized.get("title")
        ideas = normalized.get("ide_konten") or normalized.get("ide") or normalized.get("ideas")
        cta = normalized.get("call_to_action") or normalized.get("cta") or normalized.get("ajakan")

        if isinstance(ideas, dict):
            ideas = [
                ideas.get(str(number), ideas.get(number, ideas.get(f"ide_{number}", "")))
                for number in (1, 2, 3)
            ]
        return _format_content_idea_canonical(title, ideas, cta)
    except Exception:
        return ""


def _parse_content_idea_response(text: Any) -> str:
    """Parse protokol teks, format Markdown lama, atau JSON ringan."""
    for parser in (
        _parse_content_idea_protocol,
        _parse_content_idea_markdown,
        _parse_content_idea_json_simple,
    ):
        result = parser(text)
        if result:
            return result
    return ""


def _is_valid_content_idea_format(text: str) -> bool:
    """Pastikan output memuat Judul, tepat tiga Ide, CTA, dan maksimal 300 kata."""
    try:
        value = str(text or "").strip()
        required_headers = (
            "📌 JUDUL KONTEN:",
            "💡 IDE KONTEN:",
            "🎯 CALL TO ACTION:",
        )
        if not all(header in value for header in required_headers):
            return False

        numbered_lines = [
            line.strip()
            for line in value.splitlines()
            if re.match(r"^[123]\.\s+\S", line.strip())
        ]
        numbers = [line.split(".", 1)[0] for line in numbered_lines]
        if numbers != ["1", "2", "3"]:
            return False
        if len(value.split()) > CONTENT_IDEA_MAX_WORDS:
            return False

        forbidden = ("{\"", "{'", "judul_konten\"", "ide_konten\"", "```json")
        return not any(marker in value.casefold() for marker in forbidden)
    except Exception:
        return False


def _call_content_idea_model(
    model: GeminiModelAdapter,
    candidate: str,
    prompt: str,
) -> Any:
    """Panggil generateContent biasa tanpa structured schema yang sensitif versi."""
    from google.genai import types

    config = types.GenerateContentConfig(
        temperature=CONTENT_IDEA_TEMPERATURE,
        max_output_tokens=CONTENT_IDEA_MAX_OUTPUT_TOKENS,
    )
    return model.client.models.generate_content(
        model=candidate,
        contents=prompt,
        config=config,
    )


def _response_text_content_idea(response: Any) -> str:
    """Ambil teks dari response.text atau candidate parts lintas versi SDK."""
    try:
        text = str(getattr(response, "text", "") or "").strip()
        if text:
            return text
    except Exception:
        pass

    try:
        parts_text: list[str] = []
        for candidate in getattr(response, "candidates", None) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", None) or []:
                value = str(getattr(part, "text", "") or "").strip()
                if value:
                    parts_text.append(value)
        return "\n".join(parts_text).strip()
    except Exception:
        return ""


def _generate_content_idea_response(
    model: GeminiModelAdapter,
    prompt: str,
) -> GeminiTextResponse:
    """Coba setiap model dan terima hanya respons lima-baris yang valid."""
    last_error: Exception | None = None
    candidates = _content_idea_model_candidates(model)

    for index, candidate in enumerate(candidates):
        try:
            response = _call_content_idea_model(model, candidate, prompt)
            raw_text = _response_text_content_idea(response)
            if not raw_text:
                raise RuntimeError("Respons Gemini kosong")

            canonical = _parse_content_idea_response(raw_text)
            if not _is_valid_content_idea_format(canonical):
                raise ValueError("Respons Gemini tidak mengikuti protokol lima baris")

            if index > 0:
                LOGGER.warning(
                    "Model ide konten utama tidak tersedia. Permintaan berhasil "
                    "menggunakan model cadangan %s dengan protokol teks stabil.",
                    candidate,
                )
            return GeminiTextResponse(text=canonical, model_name=candidate)
        except Exception as error:
            last_error = error
            has_next_model = index < len(candidates) - 1
            if has_next_model and (
                _boleh_coba_model_cadangan(error)
                or isinstance(error, (ValueError, RuntimeError))
            ):
                LOGGER.warning(
                    "Permintaan ide konten ke model %s gagal atau formatnya belum "
                    "sesuai (%s). Mencoba model cadangan.",
                    candidate,
                    type(error).__name__,
                )
                continue
            raise

    if last_error is not None:
        raise last_error
    raise RuntimeError("Tidak ada model Gemini yang tersedia untuk ide konten")


def _show_content_idea_warning(message: str) -> None:
    """Tampilkan st.error hanya ketika fungsi berjalan di aplikasi Streamlit."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        if get_script_run_ctx(suppress_warning=True) is not None:
            st.warning(message)
    except Exception:
        return


@st.cache_data(
    ttl=300,
    show_spinner=False,
    max_entries=128,
    hash_funcs={
        list: lambda _value: "keywords-diabaikan-dari-cache-key",
        tuple: lambda _value: "keywords-diabaikan-dari-cache-key",
    },
)
def generate_content_idea(
    topic_name: str,
    keywords: list,
    platform: str,
    sentiment: str,
    layanan: str,
) -> str:
    """
    Generate ide konten media sosial via Gemini API.

    Params:
      topic_name : str  — nama topik, contoh: "Gangguan Jaringan"
      keywords   : list — daftar kata kunci topik
      platform   : str  — platform target: Twitter / Instagram / TikTok
      sentiment  : str  — sentimen dominan: Positif / Negatif / Netral
      layanan    : str  — layanan Telkom: IndiHome / IndiBiz / Telkomsel

    Return:
      str — ide konten dalam Bahasa Indonesia, maksimal sekitar 300 kata.

    Fallback:
      str — template statis jika API gagal atau API key tidak tersedia.
    """
    clean_topic = _normalisasi_parameter_content_idea(topic_name, "Topik Layanan")
    clean_platform = _normalisasi_parameter_content_idea(platform, "Media Sosial")
    clean_sentiment = _normalisasi_parameter_content_idea(sentiment, "Netral")
    clean_layanan = _normalisasi_parameter_content_idea(layanan, "Telkom Group")
    clean_keywords = _normalisasi_keywords_content_idea(keywords)

    fallback_text = _build_content_idea_fallback(
        topic_name=clean_topic,
        platform=clean_platform,
        layanan=clean_layanan,
        sentiment=clean_sentiment,
    )

    try:
        model = init_gemini()
        if model is None:
            return fallback_text

        prompt = _build_content_idea_prompt(
            topic_name=clean_topic,
            keywords=clean_keywords,
            platform=clean_platform,
            sentiment=clean_sentiment,
            layanan=clean_layanan,
        )
        response = _generate_content_idea_response(model, prompt)
        if not _is_valid_content_idea_format(response.text):
            LOGGER.warning(
                "Respons Gemini belum memenuhi format lima baris. "
                "Menggunakan fallback lokal."
            )
            return fallback_text
        return response.text
    except Exception as error:
        status_code = _status_code_error(error)
        status_text = f", kode {status_code}" if status_code is not None else ""
        LOGGER.warning(
            "Permintaan ide konten Gemini gagal (%s%s). Menggunakan fallback lokal.",
            type(error).__name__,
            status_text,
        )
        _show_content_idea_warning(
            "Gemini belum dapat menghasilkan ide konten. Dashboard tetap aman "
            "dan menampilkan ide fallback lokal."
        )
        return fallback_text

# -----------------------------------------------------------------------------
# TAHAP 4 | FASE 12 - RELEVANSI DATA DAN STATUS FALLBACK
# -----------------------------------------------------------------------------

def check_data_relevance(sample_text: str) -> bool:
    """Periksa relevansi teks secara real-time; kegagalan tidak memblokir pengguna."""
    try:
        clean_text = str(sample_text or "").strip()
        if not clean_text:
            return True

        model = init_gemini()
        if model is None:
            return True

        prompt = (
            "Apakah teks ini berkaitan dengan layanan IndiHome, IndiBiz, atau "
            "Telkomsel PT Telkom Indonesia? Jawab hanya dengan satu kata: YA "
            f"atau TIDAK.\n\nTeks: {clean_text[:1500]}"
        )
        response = model.generate_content(prompt)
        answer = str(response.text or "").strip().upper()
        return bool(re.search(r"\bYA\b", answer))
    except Exception as error:
        LOGGER.warning(
            "Pemeriksaan relevansi Gemini gagal (%s). Teks diasumsikan relevan.",
            type(error).__name__,
        )
        return True


def get_gemini_runtime_status() -> dict[str, Any]:
    """Sediakan status aman untuk UI tanpa menampilkan nilai API key."""
    try:
        available = bool(is_gemini_available())
        return {
            "available": available,
            "source": get_gemini_key_source(),
            "mode": "online" if available else "offline",
        }
    except Exception:
        return {
            "available": False,
            "source": "tidak ditemukan",
            "mode": "offline",
        }

