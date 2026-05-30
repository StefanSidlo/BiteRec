# =============================================================================
# BiteRec — Scoring
# Computes health, eco, and combined scores for each product.
# Translates eco-metrics into concrete relatable units (FR-08).
# Builds the radar chart data structure (FR-07).
# =============================================================================

import numpy as np
import pandas as pd

from .config import (
    NUTRISCORE_ORDER,
    ECOSCORE_ORDER,
    CO2_BY_ECOSCORE,
    CAR_CO2_PER_KM,
    HEALTH_WEIGHTS,
    ECO_WEIGHTS,
    NUTRIENT_BOUNDS,
    DEFAULT_HEALTH_WEIGHT,
)

# ---------------------------------------------------------------------------
# Main scoring entry point
# ---------------------------------------------------------------------------

def score_dataframe(df: pd.DataFrame, health_weight: float = DEFAULT_HEALTH_WEIGHT) -> pd.DataFrame:
    """
    Add health_score, eco_score, and combined_score columns to df.

    All scores are in [0, 1] (higher = better).
    """
    df = df.copy()
    df["health_score"] = df.apply(_health_score, axis=1)
    df["eco_score_val"] = df.apply(_eco_score, axis=1)
    df["co2_g_per_100g"] = df.apply(_estimate_co2, axis=1)
    df["combined_score"] = (
        health_weight * df["health_score"]
        + (1 - health_weight) * df["eco_score_val"]
    )
    return df


def recompute_combined(df: pd.DataFrame, health_weight: float) -> pd.DataFrame:
    """Re-compute only the combined score (slider update — FR-03)."""
    df = df.copy()
    df["combined_score"] = (
        health_weight * df["health_score"]
        + (1 - health_weight) * df["eco_score_val"]
    )
    return df


# ---------------------------------------------------------------------------
# Health score
# ---------------------------------------------------------------------------

def _health_score(row: pd.Series) -> float:
    """
    Composite health score in [0, 1].
    Components:
      - Nutri-Score grade (50 %)
      - Protein content normalised (20 %)
      - Sugar penalty normalised (15 %)
      - Salt penalty normalised (15 %)
    """
    components = []
    weights = []

    # Nutri-Score component
    grade = str(row.get("nutriscore_grade", "unknown")).lower()
    if grade in NUTRISCORE_ORDER:
        ns_score = (NUTRISCORE_ORDER[grade] - 1) / 4  # 0..1
        components.append(ns_score)
        weights.append(HEALTH_WEIGHTS["nutriscore"])

    # Protein (higher = better)
    prot = _norm(row.get("proteins_100g"), *NUTRIENT_BOUNDS["proteins_100g"])
    if prot is not None:
        components.append(prot)
        weights.append(HEALTH_WEIGHTS["protein"])

    # Sugar penalty (lower = better → invert)
    sug = _norm(row.get("sugars_100g"), *NUTRIENT_BOUNDS["sugars_100g"])
    if sug is not None:
        components.append(1 - sug)
        weights.append(HEALTH_WEIGHTS["sugar_penalty"])

    # Salt penalty (lower = better → invert)
    salt = _norm(row.get("salt_100g"), *NUTRIENT_BOUNDS["salt_100g"])
    if salt is not None:
        components.append(1 - salt)
        weights.append(HEALTH_WEIGHTS["salt_penalty"])

    if not components:
        return 0.5  # neutral fallback

    return float(np.average(components, weights=weights))


# ---------------------------------------------------------------------------
# Eco score
# ---------------------------------------------------------------------------

def _eco_score(row: pd.Series) -> float:
    """
    Composite eco score in [0, 1].
    Components:
      - Eco-Score grade (60 %)
      - CO₂ penalty (25 %)
      - Organic bonus (15 %)
    """
    components = []
    weights = []

    # Eco-Score grade
    grade = str(row.get("ecoscore_grade", "unknown")).lower()
    if grade in ECOSCORE_ORDER:
        es = (ECOSCORE_ORDER[grade] - 1) / 4
        components.append(es)
        weights.append(ECO_WEIGHTS["ecoscore"])

    # CO₂ penalty (lower = better → invert, normalise to 0–2000 g/100g)
    co2 = _estimate_co2(row)
    co2_norm = 1 - min(co2 / 2000.0, 1.0)
    components.append(co2_norm)
    weights.append(ECO_WEIGHTS["co2_penalty"])

    # Organic bonus
    labels = str(row.get("labels_en", "")) + str(row.get("labels_tags", ""))
    is_organic = any(
        kw in labels.lower()
        for kw in ["organic", "bio", "en:organic", "fr:bio"]
    )
    components.append(1.0 if is_organic else 0.0)
    weights.append(ECO_WEIGHTS["organic_bonus"])

    return float(np.average(components, weights=weights))


# ---------------------------------------------------------------------------
# CO₂ estimation
# ---------------------------------------------------------------------------

def _estimate_co2(row: pd.Series) -> float:
    """
    Estimate CO₂ g per 100 g product.
    Uses measured value if available, otherwise falls back to Eco-Score proxy.
    """
    measured = row.get("carbon-footprint-from-known-ingredients_product")
    try:
        if measured is not None and not pd.isna(measured) and float(measured) > 0:
            return float(measured)
    except (TypeError, ValueError):
        pass

    grade = str(row.get("ecoscore_grade", "unknown")).lower()
    return CO2_BY_ECOSCORE.get(grade, CO2_BY_ECOSCORE["unknown"])


# ---------------------------------------------------------------------------
# Concrete eco-metric conversions (FR-08)
# ---------------------------------------------------------------------------

def co2_to_car_km(co2_g_per_100g: float) -> str:
    """Convert CO₂ per 100 g to 'equivalent km driven by car'."""
    km = co2_g_per_100g / CAR_CO2_PER_KM
    if km < 0.1:
        return "< 0.1 km of car driving per 100 g"
    return f"~{km:.1f} km of car driving per 100 g"


def origin_to_distance(row: pd.Series, user_country: str = "France") -> str | None:
    """
    Rough 'locally sourced' label based on origin tags.
    Returns None if origin data is missing.
    """
    origins = str(row.get("origins_tags", "")).lower()
    manufacturing = str(row.get("manufacturing_places", "")).lower()
    combined = origins + " " + manufacturing

    local_keywords = ["france", "germany", "spain", "italy", "netherlands",
                      "belgium", "united kingdom", "austria", "switzerland",
                      "en:european-union", "europe"]
    if not combined.strip():
        return None
    for kw in local_keywords:
        if kw in combined:
            return "Produced in Europe 🌱"
    return "Imported from outside Europe"


def is_organic(row: pd.Series) -> bool:
    labels = str(row.get("labels_en", "")) + str(row.get("labels_tags", ""))
    return any(
        kw in labels.lower()
        for kw in ["organic", "bio", "en:organic", "fr:bio"]
    )


# ---------------------------------------------------------------------------
# Radar chart data (FR-07)
# ---------------------------------------------------------------------------

RADAR_DIMENSIONS = [
    ("Nutri-Score", "nutriscore_grade"),
    ("Eco-Score", "ecoscore_grade"),
    ("Protein", "proteins_100g"),
    ("Low Sugar", "sugars_100g"),
    ("Low Salt", "salt_100g"),
    ("Low CO₂", "co2_g_per_100g"),
]


def radar_values(row: pd.Series) -> dict[str, float]:
    """
    Return a dict of dimension → normalised score [0, 1] for the radar chart.
    """
    result = {}

    # Grade-based dimensions (higher grade letter = lower score → invert)
    for dim_name, col in [("Nutri-Score", "nutriscore_grade"), ("Eco-Score", "ecoscore_grade")]:
        grade = str(row.get(col, "unknown")).lower()
        order = NUTRISCORE_ORDER if "nutri" in col else ECOSCORE_ORDER
        result[dim_name] = (order.get(grade, 0) - 1) / 4 if grade in order else 0.5

    # Protein (higher = better)
    result["Protein"] = _norm(row.get("proteins_100g"), 0, 35) or 0.0

    # Low Sugar (lower sugar = higher score)
    result["Low Sugar"] = 1 - (_norm(row.get("sugars_100g"), 0, 60) or 0.5)

    # Low Salt (lower salt = higher score)
    result["Low Salt"] = 1 - (_norm(row.get("salt_100g"), 0, 5) or 0.5)

    # Low CO₂
    co2 = row.get("co2_g_per_100g", CO2_BY_ECOSCORE["unknown"])
    result["Low CO₂"] = 1 - min(float(co2) / 2000.0, 1.0)

    return result


def build_radar_df(products: list[tuple[str, pd.Series]]) -> pd.DataFrame:
    """
    Build a tidy DataFrame suitable for Plotly radar chart.

    Parameters
    ----------
    products : list of (label, row)
        e.g. [("Searched", row1), ("Better for You", row2), ("Better for Earth", row3)]
    """
    records = []
    for label, row in products:
        vals = radar_values(row)
        for dim, val in vals.items():
            records.append({"Product": label, "Dimension": dim, "Score": val})
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _norm(value, lo: float, hi: float) -> float | None:
    """Min-max normalise to [0, 1]; return None if value is NaN."""
    if value is None or pd.isna(value):
        return None
    return float(np.clip((float(value) - lo) / (hi - lo + 1e-9), 0.0, 1.0))
