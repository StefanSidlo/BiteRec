"""
BiteRec — scoring layer.

Turns raw product attributes into normalised 0–100 scores (higher is always
better) and combines them with a user-set health/eco weight (FR-03).

  - health_score : from the effective Nutri-Score grade (real or ML-predicted)
  - eco_score    : from the Eco-Score grade
  - combined_score = w * health + (1 - w) * eco

Also produces the concrete eco metrics (FR-08) and the radar-chart dimensions
(FR-07).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C


def _grade_score(grade: str, mapping: dict) -> float:
    return float(mapping.get(str(grade).strip().lower(), np.nan))


def add_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Add health_score, eco_score and an availability flag."""
    df = df.copy()
    df["health_score"] = df["effective_grade"].map(
        lambda g: _grade_score(g, C.NUTRI_GRADE_TO_SCORE)
    )
    df["eco_score"] = df[C.COL_ECOSCORE_GRADE].map(
        lambda g: _grade_score(g, C.ECO_GRADE_TO_SCORE)
    )
    # A product is recommendable if it has at least a health score.
    df["is_scorable"] = df["health_score"].notna()
    return df


def combined_score(health: float, eco: float, health_weight: float) -> float:
    """Weighted combination. Missing dimensions fall back to the other one."""
    w = health_weight
    h_ok, e_ok = not pd.isna(health), not pd.isna(eco)
    if h_ok and e_ok:
        return w * health + (1 - w) * eco
    if h_ok:
        return health
    if e_ok:
        return eco
    return float("nan")


def add_combined(df: pd.DataFrame, health_weight: float) -> pd.DataFrame:
    df = df.copy()
    df["combined_score"] = [
        combined_score(h, e, health_weight)
        for h, e in zip(df["health_score"], df["eco_score"])
    ]
    return df


# --------------------------------------------------------------------------- #
# Concrete eco metrics (FR-08)
# --------------------------------------------------------------------------- #
def estimate_co2_per_100g(row: pd.Series) -> float | None:
    """Estimate kg CO2e / 100 g from the Eco-Score grade (transparent proxy)."""
    grade = str(row.get(C.COL_ECOSCORE_GRADE, "")).strip().lower()
    return C.ECO_GRADE_TO_CO2.get(grade)


def co2_to_car_km(co2_kg: float) -> float:
    return co2_kg / C.CO2_KG_PER_CAR_KM


def concrete_eco_metrics(row: pd.Series) -> dict:
    """Relatable, non-abstract eco facts for one product."""
    out = {}
    co2 = estimate_co2_per_100g(row)
    if co2 is not None:
        out["co2_kg_per_100g"] = round(co2, 2)
        out["car_km_equivalent"] = round(co2_to_car_km(co2), 1)
    origin = str(row.get(C.COL_ORIGINS, "")).strip()
    if origin:
        out["origin"] = origin
    labels = str(row.get(C.COL_LABELS, "")).strip()
    if labels:
        out["labels"] = labels
    return out


# --------------------------------------------------------------------------- #
# Radar-chart dimensions (FR-07) — 6 axes, all normalised 0–100, higher better
# --------------------------------------------------------------------------- #
RADAR_AXES = [
    "Nutri-Score", "Eco-Score", "Protein",
    "Low sugar", "Low salt", "Low CO\u2082",
]


def _nutrient_to_score(value, good_high: bool, cap: float) -> float:
    """Map a nutrient value to 0–100. If good_high, more is better; else less."""
    if pd.isna(value):
        return 0.0
    norm = max(0.0, min(1.0, float(value) / cap))
    return round(100 * (norm if good_high else (1 - norm)), 1)


def radar_values(row: pd.Series) -> list[float]:
    health = row.get("health_score")
    eco = row.get("eco_score")
    co2 = estimate_co2_per_100g(row)
    co2_score = 0.0 if co2 is None else round(
        100 * (1 - min(1.0, co2 / max(C.ECO_GRADE_TO_CO2.values()))), 1
    )
    return [
        0.0 if pd.isna(health) else round(float(health), 1),
        0.0 if pd.isna(eco) else round(float(eco), 1),
        _nutrient_to_score(row.get("proteins_100g"), good_high=True, cap=30),
        _nutrient_to_score(row.get("sugars_100g"), good_high=False, cap=50),
        _nutrient_to_score(row.get("salt_100g"), good_high=False, cap=5),
        co2_score,
    ]
