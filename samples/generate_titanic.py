"""Generate a Titanic-shaped dataset (891 rows, 12 columns, 'Survived' target).

Used to test target detection when the target column is NOT called "target"
or "label" - the name only makes sense in the context of the problem statement.

    python samples/generate_titanic.py
"""

from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

OUT = pathlib.Path(__file__).parent / "13_titanic.csv"

COLUMNS = ["PassengerId", "Survived", "Pclass", "Name", "Sex", "Age", "SibSp",
           "Parch", "Ticket", "Fare", "Cabin", "Embarked"]
FIRST = ["John", "Mary", "William", "Anna", "Charles", "Elizabeth", "George", "Sarah"]
LAST = ["Andersson", "Smith", "Brown", "Davies", "Wilson", "Taylor", "Jones", "Murphy"]


def make(n: int = 891, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    pclass = rng.choice([1, 2, 3], n, p=[0.25, 0.25, 0.5])
    sex = rng.choice(["male", "female"], n, p=[0.65, 0.35])
    # Survival depends on class and sex, as in the real data.
    logit = (1.6 * (sex == "female")) - 0.55 * pclass + rng.normal(0, 0.7, n)
    survived = (logit > 0).astype(int)

    age = np.round(rng.gamma(6.0, 5.0, n) + 1, 1)
    fare = np.round(rng.lognormal(0.4, 0.9, n) * (4 - pclass) * 6, 4)
    return pd.DataFrame({
        "PassengerId": np.arange(1, n + 1),
        "Survived": survived,
        "Pclass": pclass,
        "Name": [f"{FIRST[i % 8]}, {LAST[i % 8]}. {100 + i}" for i in range(n)],
        "Sex": sex,
        "Age": age,
        "SibSp": rng.integers(0, 4, n),
        "Parch": rng.integers(0, 4, n),
        "Ticket": [f"PC {17000 + i}" for i in range(n)],
        "Fare": fare,
        "Cabin": np.where(rng.random(n) < 0.25,
                         [f"C{rng.integers(1, 100)}" for _ in range(n)], ""),
        "Embarked": rng.choice(["S", "C", "Q"], n, p=[0.7, 0.2, 0.1]),
    })[COLUMNS]


if __name__ == "__main__":
    f = make()
    f.to_csv(OUT, index=False)
    print(f"Wrote {OUT.name}: {len(f)} rows x {f.shape[1]} cols")
    print("columns:", list(f.columns))
    print("Survived values:", f["Survived"].value_counts().to_dict())
    print("unique per column:", {c: int(f[c].nunique()) for c in f.columns})
