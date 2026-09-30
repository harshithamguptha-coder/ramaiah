"""Generate a wine-quality-shaped dataset (UCI Wine Quality column structure).

Shows what the Q-Compass output looks like for a very common dataset.
Seeded, so it regenerates identically.

    python samples/generate_wine.py
"""

from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

OUT = pathlib.Path(__file__).parent / "11_wine_quality.csv"

# Real UCI wine-quality-red column names, and the real class distribution
# (quality 3-9), which is heavily skewed toward 5 and 6.
COLUMNS = [
    "fixed_acidity", "volatile_acidity", "citric_acid", "residual_sugar",
    "chlorides", "free_sulfur_dioxide", "total_sulfur_dioxide", "density",
    "pH", "sulphates", "alcohol", "quality",
]
QUALITY_COUNTS = {3: 10, 4: 53, 5: 681, 6: 638, 7: 199, 8: 18, 9: 5}


def make(seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = sum(QUALITY_COUNTS.values())
    quality = np.repeat(list(QUALITY_COUNTS), list(QUALITY_COUNTS.values()))
    rng.shuffle(quality)
    latent = (quality - 5.4) * 0.55 + rng.normal(0, 0.9, n)

    frame = pd.DataFrame({
        "fixed_acidity": (7.4 + 0.7 * latent + rng.normal(0, 1.4, n)).round(3),
        "volatile_acidity": (0.53 - 0.035 * latent + rng.normal(0, 0.13, n)).round(3),
        "citric_acid": (0.34 + 0.03 * latent + rng.normal(0, 0.10, n)).round(3),
        "residual_sugar": (rng.lognormal(0.5, 0.9, n) + 2.0).round(2),
        "chlorides": (0.09 - 0.005 * latent + rng.normal(0, 0.02, n)).round(3),
        "free_sulfur_dioxide": rng.integers(3, 46, n),
        "total_sulfur_dioxide": rng.integers(6, 440, n),
        "density": (0.9973 - 0.0009 * latent + rng.normal(0, 0.002, n)).round(5),
        "pH": (3.31 - 0.012 * latent + rng.normal(0, 0.02, n)).round(3),
        "sulphates": (0.66 + 0.025 * latent + rng.normal(0, 0.11, n)).round(3),
        "alcohol": (10.3 + 0.45 * latent + rng.normal(0, 0.5, n)).round(3),
    })
    frame["quality"] = quality
    return frame[COLUMNS]


if __name__ == "__main__":
    f = make()
    f.to_csv(OUT, index=False)
    print(f"Wrote {OUT.name}: {len(f)} rows x {f.shape[1]} cols")
    print("\nquality distribution:")
    print(f["quality"].value_counts().sort_index().to_string())
    print(f"\nmissing values: {int(f.isna().sum().sum())}")
