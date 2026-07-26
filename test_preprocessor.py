"""Skrip uji cepat preprocessor — jalankan: python test_preprocessor.py"""

from utils.preprocessor import (
    STOPWORDS_ID,
    NORMALIZATION_MAP,
    batch_clean,
    clean_text,
    normalize_informal,
    prepare_for_wordcloud,
    remove_stopwords,
)

SAMPLE = "Min @indihome internet down bgt 😭 https://t.co/abc #gangguan"

if __name__ == "__main__":
    assert len(STOPWORDS_ID) >= 100, f"Stopword kurang: {len(STOPWORDS_ID)}"
    assert len(NORMALIZATION_MAP) >= 30, f"Normalisasi kurang: {len(NORMALIZATION_MAP)}"

    print(f"OK  STOPWORDS_ID = {len(STOPWORDS_ID)} kata")
    print(f"OK  NORMALIZATION_MAP = {len(NORMALIZATION_MAP)} pasang")

    cleaned = clean_text(SAMPLE)
    assert "http" not in cleaned and "@" not in cleaned
    print(f"OK  clean_text       -> {cleaned!r}")

    normalized = normalize_informal("yg gak stabil bgt")
    assert "yang" in normalized and "tidak" in normalized
    print(f"OK  normalize_informal -> {normalized!r}")

    no_sw = remove_stopwords("internet lambat tidak stabil")
    assert "tidak" not in no_sw.split()
    print(f"OK  remove_stopwords -> {no_sw!r}")

    wc = prepare_for_wordcloud(SAMPLE)
    assert "#" not in wc and len(wc) > 0
    print(f"OK  prepare_for_wordcloud -> {wc!r}")

    batch = batch_clean(["Internet lambat!", "Sinyal bagus 👍"])
    assert len(batch) == 2
    print(f"OK  batch_clean      -> {batch}")

    print("\nSemua uji preprocessor berhasil.")
