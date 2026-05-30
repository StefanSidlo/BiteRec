# =============================================================================
# BiteRec — Recommender
# Product search, allergen hard-filter (FR-04), and the two-alternative
# recommendation engine (FR-05): "Better for You" + "Better for Earth".
# =============================================================================

import logging
import numpy as np
import pandas as pd

from .config import (
    COMMON_ALLERGENS,
    MIN_PRODUCTS_FOR_RECOMMENDATION,
    MAX_SEARCH_RESULTS,
    DEFAULT_HEALTH_WEIGHT,
)
from .scoring import score_dataframe
from .data_loader import get_category_pool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Search index — built once at startup, O(1) per query
# ---------------------------------------------------------------------------

class SearchIndex:
    """
    Fast search index: caches lowercased name/brand Series so each query
    skips the .str.lower() step (the main cost on large datasets).
    After quality filtering the dataset is ~200-400k products, where
    str.contains runs in <100ms.
    """

    def __init__(self, df: pd.DataFrame):
        self._df           = df
        self._names_lower  = df["product_name"].fillna("").str.lower()
        self._brands_lower = df["brands"].fillna("").str.lower()

    def search(self, query: str, max_results: int = MAX_SEARCH_RESULTS) -> pd.DataFrame:
        q = query.strip().lower()
        if not q:
            return pd.DataFrame()

        name_hits  = self._names_lower.str.contains(q, regex=False, na=False)
        brand_hits = self._brands_lower.str.contains(q, regex=False, na=False)
        hits = name_hits | brand_hits

        if not hits.any():
            return pd.DataFrame()

        results = self._df[hits].copy()
        results["_sort"] = self._names_lower[hits].str.startswith(q).astype(int)
        results = results.sort_values("_sort", ascending=False).drop(columns="_sort")
        return results.head(max_results).reset_index(drop=True)


def build_search_index(df: pd.DataFrame) -> SearchIndex:
    """Call once after load_data(). Returns a SearchIndex ready to query."""
    logger.info("Building search index…")
    idx = SearchIndex(df)
    logger.info(f"Search index built over {len(df):,} products.")
    return idx


def search_product(df_or_index, query: str) -> pd.DataFrame:
    """
    Search by product name or brand.
    Accepts a SearchIndex (fast path) or a plain DataFrame (slow fallback).
    """
    if isinstance(df_or_index, SearchIndex):
        return df_or_index.search(query)

    # Fallback: plain DataFrame
    df = df_or_index
    q  = query.strip().lower()
    if not q:
        return pd.DataFrame()
    name_mask  = df["product_name"].str.lower().str.contains(q, na=False, regex=False)
    brand_mask = df["brands"].str.lower().str.contains(q, na=False, regex=False)
    results    = df[name_mask | brand_mask].copy()
    results["_sort"] = results["product_name"].str.lower().str.startswith(q).astype(int)
    results = results.sort_values("_sort", ascending=False).drop(columns="_sort")
    return results.head(MAX_SEARCH_RESULTS).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Allergen filter (FR-04 — hard constraint)
# ---------------------------------------------------------------------------

def apply_allergen_filter(df: pd.DataFrame, allergens: list[str]) -> pd.DataFrame:
    """
    Remove any product that contains (or may contain) a specified allergen.
    Hard constraint — cannot be overridden by any score.
    """
    if not allergens:
        return df

    keywords = _expand_allergen_keywords(allergens)
    if not keywords:
        return df

    pattern      = "|".join(keywords)
    allergen_col = df["allergens_en"].str.lower()
    traces_col   = df["traces_en"].str.lower()

    flagged = (
        allergen_col.str.contains(pattern, na=False, regex=True)
        | traces_col.str.contains(pattern, na=False, regex=True)
    )

    removed = flagged.sum()
    if removed:
        logger.info(f"Allergen filter removed {removed} products for: {allergens}")

    return df[~flagged].copy()


def _expand_allergen_keywords(allergens: list[str]) -> list[str]:
    keywords = set()
    for allergen in allergens:
        a = allergen.strip().lower()
        if a in COMMON_ALLERGENS:
            keywords.update(COMMON_ALLERGENS[a])
        else:
            keywords.add(a)
    return list(keywords)


# ---------------------------------------------------------------------------
# Two-alternative recommendation engine (FR-05)
# ---------------------------------------------------------------------------

class RecommendationResult:
    __slots__ = ("searched", "better_for_you", "better_for_earth", "win_win")

    def __init__(self, searched, better_for_you, better_for_earth, win_win=False):
        self.searched        = searched
        self.better_for_you  = better_for_you
        self.better_for_earth = better_for_earth
        self.win_win         = win_win


def recommend(
    df: pd.DataFrame,
    product_row: pd.Series,
    allergens: list[str],
    health_weight: float = DEFAULT_HEALTH_WEIGHT,
) -> RecommendationResult:
    """
    Find Better-for-You and Better-for-Earth alternatives.

    df must already have health_score and eco_score_val columns (pre-computed
    at startup). This function only filters and picks — never re-scores.
    """
    pool = get_category_pool(df, product_row, min_size=MIN_PRODUCTS_FOR_RECOMMENDATION)
    pool = apply_allergen_filter(pool, allergens)

    if len(pool) < 2:
        logger.warning("Pool too small after allergen filter; using full dataset.")
        pool = apply_allergen_filter(df, allergens)

    # Recalculate only combined_score (fast — just a weighted sum of existing columns)
    if "health_score" in pool.columns and "eco_score_val" in pool.columns:
        pool = pool.copy()
        pool["combined_score"] = (
            health_weight * pool["health_score"]
            + (1 - health_weight) * pool["eco_score_val"]
        )
    else:
        pool = score_dataframe(pool, health_weight)

    # Exclude the searched product
    code = product_row.get("code", None)
    name = product_row.get("product_name", "")
    if code and str(code) != "nan":
        pool = pool[pool["code"].astype(str) != str(code)]
    else:
        pool = pool[pool["product_name"] != name]

    if len(pool) == 0:
        return RecommendationResult(product_row, None, None)

    best_health_idx  = pool["health_score"].idxmax()
    better_for_you   = pool.loc[best_health_idx]

    best_eco_idx     = pool["eco_score_val"].idxmax()
    better_for_earth = pool.loc[best_eco_idx]

    win_win = best_health_idx == best_eco_idx

    return RecommendationResult(
        searched=product_row,
        better_for_you=better_for_you,
        better_for_earth=better_for_earth,
        win_win=win_win,
    )


def rerank_with_new_weight(
    result: RecommendationResult,
    df: pd.DataFrame,
    allergens: list[str],
    new_health_weight: float,
) -> RecommendationResult:
    return recommend(df, result.searched, allergens, health_weight=new_health_weight)


# ---------------------------------------------------------------------------
# Nutrient comparison helpers
# ---------------------------------------------------------------------------

def nutrient_delta(base: pd.Series, alternative: pd.Series, col: str):
    b = base.get(col)
    a = alternative.get(col)
    if pd.isna(b) or pd.isna(a) or float(b) == 0:
        return None
    return ((float(a) - float(b)) / float(b)) * 100


def key_differences(base: pd.Series, alt: pd.Series) -> list[dict]:
    cols = [
        ("proteins_100g",      "protein",       True),
        ("sugars_100g",        "sugar",          False),
        ("salt_100g",          "salt",           False),
        ("fat_100g",           "fat",            False),
        ("saturated-fat_100g", "saturated fat",  False),
        ("fiber_100g",         "fibre",          True),
        ("energy-kcal_100g",   "calories",       False),
    ]
    diffs = []
    for col, label, higher_is_better in cols:
        delta = nutrient_delta(base, alt, col)
        if delta is None or abs(delta) < 5:
            continue
        improved = (delta > 0) == higher_is_better
        diffs.append({"col": col, "label": label, "delta_pct": delta, "improved": improved})

    diffs.sort(key=lambda x: abs(x["delta_pct"]), reverse=True)
    return diffs[:3]
