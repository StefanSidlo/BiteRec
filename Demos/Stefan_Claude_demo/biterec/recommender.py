"""
BiteRec — recommendation engine ("Alternative Engine").

For a searched product it produces:
  - a "Better for You"   alternative (best health score in the same category)
  - a "Better for Earth" alternative (best eco score in the same category)
  - a primary pick (best combined score; surfaced when it beats the search on
    both dimensions simultaneously, per FR-05)

Allergens are applied as HARD constraints (FR-04 / UC-03): no product containing
a listed allergen is ever returned, regardless of score.
"""
from __future__ import annotations

import re
import pandas as pd

from . import config as C
from . import scoring


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
def search_products(df: pd.DataFrame, query: str, limit: int = 25) -> pd.DataFrame:
    """Case-insensitive substring search on the product name (FR-01)."""
    q = query.strip().lower()
    if not q:
        return df.iloc[0:0]
    mask = df[C.COL_NAME].str.lower().str.contains(re.escape(q), na=False)
    res = df[mask].copy()
    # Prefer products that are scorable and have a shorter (more specific) name.
    res["_name_len"] = res[C.COL_NAME].str.len()
    res = res.sort_values(["is_scorable", "_name_len"], ascending=[False, True])
    return res.drop(columns="_name_len").head(limit)


# --------------------------------------------------------------------------- #
# Allergen hard constraint
# --------------------------------------------------------------------------- #
def contains_allergen(row: pd.Series, allergens: list[str]) -> bool:
    if not allergens:
        return False
    haystack = " ".join(
        str(row.get(c, "")) for c in
        (C.COL_ALLERGENS, C.COL_ALLERGENS_EN, C.COL_TRACES, C.COL_INGREDIENTS)
    ).lower()
    return any(a.strip().lower() in haystack for a in allergens if a.strip())


def filter_allergens(df: pd.DataFrame, allergens: list[str]) -> pd.DataFrame:
    if not allergens:
        return df
    safe = df[~df.apply(lambda r: contains_allergen(r, allergens), axis=1)]
    return safe


# --------------------------------------------------------------------------- #
# Candidate pool (same food category)
# --------------------------------------------------------------------------- #
_NON_CATEGORIES = {"", "unknown", "not-applicable", "not applicable"}

# Keyword -> pnns group fallback, used when a product has no category metadata
# (the short export leaves ~80 % of categories blank/unknown).
_NAME_KEYWORD_PNNS = {
    "milk": "Milk and yogurt", "yogurt": "Milk and yogurt",
    "yoghurt": "Milk and yogurt", "cheese": "Cheese",
    "chocolate": "Sweets", "candy": "Sweets", "biscuit": "Biscuits and cakes",
    "cookie": "Biscuits and cakes", "cake": "Biscuits and cakes",
    "bread": "Bread", "juice": "Fruit juices", "soda": "Sweetened beverages",
    "water": "Waters and flavored waters", "chips": "Appetizers",
    "crisps": "Appetizers", "cereal": "Cereals", "pasta": "Cereals",
    "rice": "Cereals", "sauce": "Dressings and sauces", "soup": "Soups",
    "nuts": "Nuts", "fruit": "Fruits", "vegetable": "Vegetables",
}


def _category_keys(row: pd.Series) -> list[str]:
    """Ordered list of clean, specific category strings (most specific first)."""
    keys = []
    for col in (C.COL_PNNS, C.COL_MAIN_CATEGORY):
        val = str(row.get(col, "")).strip().lower()
        if val and val not in _NON_CATEGORIES:
            keys.append(val)
    cats = str(row.get(C.COL_CATEGORY, "")).strip().lower()
    if cats and cats not in _NON_CATEGORIES:
        keys.append(cats.split(",")[-1].strip())  # most specific token
    if not keys:  # name-keyword fallback
        name = str(row.get(C.COL_NAME, "")).lower()
        for kw, grp in _NAME_KEYWORD_PNNS.items():
            if kw in name:
                keys.append(grp.lower())
                break
    return keys


def candidate_pool(df: pd.DataFrame, product: pd.Series) -> pd.DataFrame:
    keys = _category_keys(product)
    if not keys:
        return df.iloc[0:0]
    # Exact match on the cleaned pnns / main-category columns is the most
    # reliable grouping; fall back to a substring of the specific token.
    pnns = df[C.COL_PNNS].str.lower()
    main = df[C.COL_MAIN_CATEGORY].str.lower()
    mask = pnns.isin(keys) | main.isin(keys)
    for key in keys:
        if len(key) >= 4:
            mask = mask | df[C.COL_CATEGORY].str.lower().str.contains(
                re.escape(key), na=False)
    pool = df[mask].copy()
    pool = pool[pool[C.COL_CODE] != product.get(C.COL_CODE)]
    return pool


# --------------------------------------------------------------------------- #
# Filters (FR-02)
# --------------------------------------------------------------------------- #
def apply_nutritional_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply quick toggles and/or numeric slider thresholds.

    Recognised keys:
      booleans: high_protein, low_sugar, low_salt, organic
      numbers : min_protein, max_sugar, max_salt, max_fat (None = ignore)
    """
    out = df
    # Quick toggles.
    if filters.get("high_protein"):
        out = out[out["proteins_100g"].fillna(0) >= 10]
    if filters.get("low_sugar"):
        out = out[out["sugars_100g"].fillna(99) <= 5]
    if filters.get("low_salt"):
        out = out[out["salt_100g"].fillna(99) <= 0.3]
    if filters.get("organic"):
        out = out[out[C.COL_LABELS].str.lower().str.contains("organic", na=False)]
    # Numeric sliders (a missing nutrient value never fails the filter).
    if filters.get("min_protein"):
        out = out[out["proteins_100g"].fillna(0) >= filters["min_protein"]]
    if filters.get("max_sugar") is not None and filters["max_sugar"] < 100:
        out = out[out["sugars_100g"].fillna(0) <= filters["max_sugar"]]
    if filters.get("max_salt") is not None and filters["max_salt"] < 10:
        out = out[out["salt_100g"].fillna(0) <= filters["max_salt"]]
    if filters.get("max_fat") is not None and filters["max_fat"] < 100:
        out = out[out["fat_100g"].fillna(0) <= filters["max_fat"]]
    return out


# --------------------------------------------------------------------------- #
# The alternative engine
# --------------------------------------------------------------------------- #
def recommend(df: pd.DataFrame, product: pd.Series, health_weight: float,
              allergens: list[str], filters: dict | None = None) -> dict:
    """Return primary / better_health / better_eco picks for a product."""
    pool = candidate_pool(df, product)
    pool = filter_allergens(pool, allergens)
    if filters:
        pool = apply_nutritional_filters(pool, filters)
    pool = pool[pool["is_scorable"]]
    pool = scoring.add_combined(pool, health_weight)

    result = {"primary": None, "better_health": None, "better_eco": None,
              "pool_size": len(pool)}
    if pool.empty:
        return result

    p_health = product.get("health_score")
    p_eco = product.get("eco_score")

    # Better for You: highest health score, strictly better than the search.
    health_pool = pool[pool["health_score"] > (p_health if pd.notna(p_health) else -1)]
    if not health_pool.empty:
        result["better_health"] = health_pool.sort_values(
            "health_score", ascending=False).iloc[0]

    # Better for Earth: highest eco score, strictly better than the search.
    eco_pool = pool[pool["eco_score"] > (p_eco if pd.notna(p_eco) else -1)]
    if not eco_pool.empty:
        result["better_eco"] = eco_pool.sort_values(
            "eco_score", ascending=False).iloc[0]

    # Primary: best combined score. Surfaced as a "win-win" when it beats the
    # searched product on BOTH dimensions (FR-05).
    best = pool.sort_values("combined_score", ascending=False).iloc[0]
    beats_both = (
        pd.notna(p_health) and pd.notna(p_eco)
        and best["health_score"] >= p_health and best["eco_score"] >= p_eco
        and (best["health_score"] > p_health or best["eco_score"] > p_eco)
    )
    result["primary"] = best
    result["primary_is_winwin"] = bool(beats_both)
    return result
