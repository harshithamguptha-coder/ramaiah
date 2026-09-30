"""Generate a SEMICOLON-delimited Wine Quality file (UCI winequality-white shape).

This is the exact case that broke the naive comma parser: ';' delimiter, 12
columns, ~4898 rows, 'quality' as the target.

    python samples/generate_wine_semicolon.py
"""

from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

OUT = pathlib.Path(__file__).parent / "12_wine_quality_semicolon.csv"

COLUMNS = [
    "fixed_acidity", "volatile_acidity", "citric_acid", "residual_sugar",
    "chlorides", "free_sulfur_dioxide", "total_sulfur_dioxide", "density",
    "pH", "sulphates", "alcohol", "quality",
]
# Real winequality-white class distribution.
QUALITY_COUNTS = {3: 30, 4: 163, 5: 1457, 6: 2198, 7: 880, 8: 175, 9: 5}


def make(seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = sum(QUALITY_COUNTS.values())
    quality = np.repeat(list(QUALITY_COUNTS), list(QUALITY_COUNTS.values()))
    rng.shuffle(quality)
    latent = (quality - 5.5) * 0.4 + rng.normal(0, 0.9, n)
    return pd.DataFrame({
        "fixed_acidity": (6.8 + 0.5 * latent + rng.normal(0, 1.4, n)).round(3),
        "volatile_acidity": (0.39 - 0.02 * latent + rng.normal(0, 0.1, n)).round(3),
        "citric_acid": (0.31 + 0.02 * latent + rng.normal(0, 0.1, n)).round(3),
        "residual_sugar": (rng.lognormal(1.0, 1.1, n) + 2.0).round(2),
        "chlorides": (0.08 - 0.003 * latent + rng.normal(0, 0.02, n)).round(3),
        "free_sulfur_dioxide": rng.integers(3, 46, n),
        "total_sulfur_dioxide": rng.integers(6, 440, n),
        "density": (0.9971 - 0.0004 * latent + rng.normal(0, 0.002, n)).round(5),
        "pH": (3.33 - 0.008 * latent + rng.normal(0, 0.02, n)).round(3),
        "sulphates": (0.49 + 0.015 * latent + rng.normal(0, 0.1, n)).round(3),
        "alcohol": (10.6 + 0.35 * latent + rng.normal(0, 0.5, n)).round(3),
        "quality": quality,
    })[COLUMNS]


if __name__ == "__main__":
    f = make()
    # sep=';' is the whole point of this file.
    f.to_csv(OUT, sep=";", index=False)
    head = OUT.read_text(encoding="utf-8").splitlines()[0]
    print(f"Wrote {OUT.name}: {len(f)} rows x {f.shape[1]} cols")
    print(f"First header: {head[:70]}...")
    print("Delimiters in header: semicolons =", head.count(";"), "| commas =", head.count(","))
