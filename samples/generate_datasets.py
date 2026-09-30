"""Generate the Q-Compass test datasets.

Each file is built to exercise a specific branch of the analysis engine, so you
can confirm the engine is reacting to the *data* rather than to hard-coded
answers. Everything is seeded, so regenerating gives byte-identical files.

    python samples/generate_datasets.py
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd

OUT = pathlib.Path(__file__).parent


def save(name: str, frame: pd.DataFrame) -> None:
    path = OUT / name
    frame.to_csv(path, index=False)
    print(f"  {name:<34} {frame.shape[0]:>6,} rows x {frame.shape[1]:>3} cols")


def small_classification(n=300, seed=1):
    """D1 - small, clean, learnable binary classification. Expect Classical."""
    rng = np.random.default_rng(seed)
    f = pd.DataFrame(
        {
            "tenure_months": rng.integers(1, 72, n),
            "monthly_charge": rng.normal(60, 18, n).round(2),
            "avg_session_minutes": rng.normal(25, 8, n).round(2),
            "support_tickets": rng.integers(0, 6, n),
            "age": rng.integers(18, 75, n),
        }
    )
    risk = f["monthly_charge"] / 60 + f["support_tickets"] * 0.4
    f["is_churned"] = np.where(risk > 1.6, "Yes", "No")
    return f


def high_dimensional(n=800, d=64, seed=2):
    """D2 - 64 features, only every 8th informative. Expect Quantum Feature Selection."""
    rng = np.random.default_rng(seed)
    f = pd.DataFrame({f"feature_{i:02d}": rng.normal(size=n) for i in range(d)})
    signal = f[[f"feature_{i:02d}" for i in range(0, d, 8)]].sum(axis=1)
    f["target"] = np.where(signal + rng.normal(0, 0.4, n) > 0, "up", "down")
    return f


def optimization(n=400, seed=3):
    """D3 - no target at all; a scheduling/cost table. Expect QAOA + skipped classical."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "job_id": [f"J{i:04d}" for i in range(n)],
            "duration": rng.integers(1, 12, n),
            "machine": rng.integers(1, 6, n),
            "priority": rng.integers(1, 4, n),
            "cost": rng.random(n).round(4),
        }
    )


def regression(n=500, seed=4):
    """D4 - continuous target. Expect the regression metric path (R2 / RMSE)."""
    rng = np.random.default_rng(seed)
    area = rng.normal(1800, 500, n).round(1)
    rooms = rng.integers(1, 6, n)
    age = rng.integers(0, 90, n)
    noise = rng.normal(0, 25, n)
    f = pd.DataFrame({"area_sqft": area, "rooms": rooms, "age_years": age,
                      "has_garage": rng.choice([0, 1], n)})
    f["sale_price"] = (area * 120 + rooms * 9000 - age * 900 + noise).round(2)
    return f


def imbalanced(n=1200, seed=5):
    """D5 - ~4% positives. Expect a low majority baseline and an imbalance warning."""
    rng = np.random.default_rng(seed)
    f = pd.DataFrame(
        {
            "account_age_days": rng.integers(10, 3000, n),
            "monthly_volume": rng.lognormal(3, 1.1, n).round(2),
            "failed_payments_90d": rng.integers(0, 4, n),
            "support_contacts": rng.integers(0, 8, n),
        }
    )
    risk = f["failed_payments_90d"] * 1.4 + f["support_contacts"] * 0.35 + rng.normal(0, 0.5, n)
    f["is_fraud"] = np.where(risk > 3.2, "Yes", "No")
    return f


def messy(n=600, seed=6):
    """D6 - ID column, missing values, duplicates, mixed types. Expect warnings."""
    rng = np.random.default_rng(seed)
    f = pd.DataFrame(
        {
            "customer_id": [f"C{i:05d}" for i in range(n)],
            "age": rng.integers(18, 90, n),
            "income": rng.lognormal(10, 0.6, n).round(2),
            "region": rng.choice(["North", "South", "East", "West"], n),
            "plan": rng.choice(["Basic", "Pro", "Enterprise"], n, p=[0.6, 0.3, 0.1]),
        }
    )
    f.loc[rng.choice(n, 90, replace=False), "income"] = np.nan
    f.loc[rng.choice(n, 45, replace=False), "region"] = None
    f = pd.concat([f, f.sample(35, random_state=seed)], ignore_index=True)
    score = f["income"].fillna(f["income"].median()) / 1000 + f["age"] / 50
    f["churned"] = np.where(score + rng.normal(0, 0.6, len(f)) > 12, "Yes", "No")
    return f


def unsupervised(n=350, seed=7):
    """D7 - no target, no optimisation wording. Expect clustering / unknown."""
    rng = np.random.default_rng(seed)
    centres = np.array([[0.0, 0.0], [6.0, 6.0], [-6.0, 5.0]])
    assign = rng.integers(0, 3, n)
    f = pd.DataFrame(
        {
            "spend_score": centres[assign, 0] + rng.normal(0, 1.2, n),
            "frequency_score": centres[assign, 1] + rng.normal(0, 1.2, n),
            "basket_size": rng.integers(1, 15, n),
            "recency_days": rng.integers(1, 180, n),
        }
    )
    return f.round(3)


def single_class(n=120, seed=8):
    """D8 - degenerate: the label has one value. Expect a clean 'skipped', not a crash."""
    rng = np.random.default_rng(seed)
    f = pd.DataFrame({"a": rng.normal(size=n), "b": rng.normal(size=n)})
    f["label"] = ["only"] * n
    return f


def too_few_rows():
    """D9 - 6 rows. Expect 'insufficient samples' handled gracefully."""
    return pd.DataFrame({"a": [1, 2, 3, 4, 5, 6], "b": [2, 4, 6, 8, 10, 12], "label": ["p", "n", "p", "n", "p", "n"]})


def as_json(n=200, seed=9):
    """D10 - the same classification problem as a JSON array, to test that parser."""
    return small_classification(n, seed).to_dict(orient="records")


if __name__ == "__main__":
    print("Writing datasets to", OUT)
    save("01_small_classification.csv", small_classification())
    save("02_high_dimensional_features.csv", high_dimensional())
    save("03_scheduling_optimization.csv", optimization())
    save("04_regression_sale_price.csv", regression())
    save("05_imbalanced_fraud.csv", imbalanced())
    save("06_messy_customer_data.csv", messy())
    save("07_unsupervised_no_target.csv", unsupervised())
    save("08_single_class_edge.csv", single_class())
    save("09_too_few_rows.csv", too_few_rows())

    records = as_json()
    (OUT / "10_classification_records.json").write_text(
        json.dumps(records, indent=1), encoding="utf-8"
    )
    print(f"  {'10_classification_records.json':<34} {len(records):>6,} records")
    print("\nDone. Upload any of these from the Upload Dataset page.")
