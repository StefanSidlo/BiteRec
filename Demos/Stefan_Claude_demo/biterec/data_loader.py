"""
BiteRec — data loading & cleaning.

Reads the (tab-delimited) Open Food Facts export, keeps only the columns the
platform needs, and applies the cleaning / clipping rules recommended in the
team's ML notebook (impossible nutrient values are removed or capped).
"""
from __future__ import annotations

import html
import pandas as pd

from . import config as C


def _find_csv() -> str:
    """Locate the data file inside data/, trying the known filenames."""
    for name in C.CSV_CANDIDATES:
        path = C.DATA_DIR / name
        if path.exists():
            return str(path)
    raise FileNotFoundError(
        f"No data file found in {C.DATA_DIR}. Place the Open Food Facts CSV "
        f"there and name it one of: {', '.join(C.CSV_CANDIDATES)}"
    )


# Columns we read from the raw file (keeps memory low on the big export).
_USECOLS = [
    C.COL_CODE, C.COL_NAME, C.COL_BRANDS, C.COL_CATEGORY, C.COL_MAIN_CATEGORY,
    C.COL_PNNS, C.COL_ORIGINS, C.COL_LABELS, C.COL_COUNTRIES, C.COL_IMAGE,
    C.COL_IMAGE_FULL, C.COL_URL, C.COL_INGREDIENTS, C.COL_ALLERGENS,
    C.COL_ALLERGENS_EN, C.COL_TRACES, C.COL_NUTRISCORE_GRADE,
    C.COL_ECOSCORE_GRADE, C.COL_ECOSCORE_SCORE, C.COL_NOVA, C.COL_ADDITIVES,
] + C.NUTRIENT_FEATURES


def load_raw() -> pd.DataFrame:
    """Load the raw export, keeping only useful columns."""
    path = _find_csv()
    df = pd.read_csv(
        path,
        sep=C.CSV_DELIMITER,
        usecols=lambda c: c in _USECOLS,
        dtype=str,
        on_bad_lines="skip",
        low_memory=False,
    )
    return df


def _clean_text(series: pd.Series) -> pd.Series:
    return series.fillna("").map(lambda s: html.unescape(str(s)).strip())


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Clean text fields, coerce nutrients to numbers and clip impossible values."""
    df = df.copy()

    # --- text fields ---
    for col in [C.COL_NAME, C.COL_BRANDS, C.COL_CATEGORY, C.COL_MAIN_CATEGORY,
                C.COL_PNNS, C.COL_ORIGINS, C.COL_LABELS, C.COL_COUNTRIES,
                C.COL_INGREDIENTS, C.COL_ALLERGENS, C.COL_ALLERGENS_EN,
                C.COL_TRACES]:
        if col in df:
            df[col] = _clean_text(df[col])
        else:
            df[col] = ""

    # Image / URL columns: keep as clean strings (don't unescape URLs).
    for col in (C.COL_IMAGE, C.COL_IMAGE_FULL, C.COL_URL):
        if col in df:
            df[col] = df[col].fillna("").astype(str).str.strip()
        else:
            df[col] = ""

    # Drop rows with no usable product name.
    df = df[df[C.COL_NAME].str.len() > 1].copy()

    # --- grades: lowercase, normalise unknown/blank ---
    df[C.COL_NUTRISCORE_GRADE] = (
        df[C.COL_NUTRISCORE_GRADE].fillna("").str.strip().str.lower()
    )
    df[C.COL_ECOSCORE_GRADE] = (
        df[C.COL_ECOSCORE_GRADE].fillna("").str.strip().str.lower()
    )

    # --- numeric nutrients ---
    for col in C.NUTRIENT_FEATURES:
        if col not in df:
            df[col] = pd.NA
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Clip / drop physically impossible values (cleaning rule from the notebook).
    # A nutrient gram value cannot exceed 100 g per 100 g of product.
    gram_cols = [c for c in C.NUTRIENT_FEATURES if c != "energy-kcal_100g"]
    for col in gram_cols:
        df.loc[(df[col] < 0) | (df[col] > 100), col] = pd.NA
    # Energy: clip to a sane 0–1000 kcal/100 g window.
    df.loc[(df["energy-kcal_100g"] < 0) | (df["energy-kcal_100g"] > 1000),
           "energy-kcal_100g"] = pd.NA

    # Eco numeric score & additives.
    df[C.COL_ECOSCORE_SCORE] = pd.to_numeric(df[C.COL_ECOSCORE_SCORE], errors="coerce")
    df[C.COL_ADDITIVES] = pd.to_numeric(df[C.COL_ADDITIVES], errors="coerce")
    df[C.COL_NOVA] = pd.to_numeric(df[C.COL_NOVA], errors="coerce")

    # Flag: does this row have a complete nutrient profile?
    df["has_full_nutrients"] = df[C.NUTRIENT_FEATURES].notna().all(axis=1)

    df = df.reset_index(drop=True)
    return df


def load() -> pd.DataFrame:
    """Public entry point: load + clean."""
    return clean(load_raw())
