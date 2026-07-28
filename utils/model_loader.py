# utils/model_loader.py
"""Loader terpusat IndoBERT dari HuggingFace Hub untuk lokal dan cloud."""

from __future__ import annotations

from typing import Any

import streamlit as st
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL_NAME = "mdhugol/indonesia-bert-sentiment-classification"

LABEL_MAP = {
    "LABEL_0": "positive",
    "LABEL_1": "neutral",
    "LABEL_2": "negative",
}


@st.cache_resource(show_spinner=False)
def load_indobert() -> tuple[Any | None, Any | None, Any | None]:
    """
    Muat model IndoBERT langsung dari HuggingFace Hub.

    Cache resource memastikan tokenizer dan model hanya dibuat satu kali pada
    proses Streamlit yang sama. HuggingFace menyimpan hasil download pada cache
    pengguna, bukan pada folder ``models/`` di dalam proyek.
    """
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)
        model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
        model.eval()

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
        return tokenizer, model, device
    except Exception as exc:
        st.error(
            "Gagal memuat model IndoBERT dari HuggingFace Hub. "
            "Pastikan koneksi internet tersedia saat pemuatan pertama dan "
            f"dependency transformers/torch sudah terpasang. Detail: {exc}"
        )
        return None, None, None


def predict_sentiment_batch(texts: list, batch_size: int = 32) -> list[dict[str, Any]]:
    """Prediksi sentimen batch menggunakan IndoBERT dari HuggingFace Hub."""
    try:
        daftar_teks = [str(text or "").strip() for text in list(texts or [])]
        if not daftar_teks:
            return []

        tokenizer, model, device = load_indobert()
        if model is None or tokenizer is None or device is None:
            return [
                {"sentiment": "unknown", "confidence": 0.0}
                for _ in daftar_teks
            ]

        ukuran_batch = max(1, int(batch_size or 32))
        results: list[dict[str, Any]] = []

        for start in range(0, len(daftar_teks), ukuran_batch):
            batch = daftar_teks[start : start + ukuran_batch]
            batch_aman = [text if text else "teks kosong" for text in batch]
            inputs = tokenizer(
                batch_aman,
                return_tensors="pt",
                truncation=True,
                padding=True,
                max_length=128,
            )
            inputs = {key: value.to(device) for key, value in inputs.items()}

            with torch.no_grad():
                outputs = model(**inputs)
                probabilities = torch.softmax(outputs.logits, dim=-1)
                prediction_ids = torch.argmax(probabilities, dim=-1)

            for position, original_text in enumerate(batch):
                if not original_text:
                    results.append({"sentiment": "neutral", "confidence": 0.0})
                    continue

                prediction_index = int(prediction_ids[position].item())
                confidence = float(
                    probabilities[position][prediction_index].item()
                )
                label = LABEL_MAP.get(
                    f"LABEL_{prediction_index}",
                    "unknown",
                )
                results.append(
                    {
                        "sentiment": label,
                        "confidence": round(confidence, 4),
                    }
                )

        return results
    except Exception as exc:
        st.error(f"Prediksi sentimen batch IndoBERT gagal: {exc}")
        jumlah_teks = len(list(texts or []))
        return [
            {"sentiment": "unknown", "confidence": 0.0}
            for _ in range(jumlah_teks)
        ]
