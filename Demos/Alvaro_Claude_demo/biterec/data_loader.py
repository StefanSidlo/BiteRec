# =============================================================================
# BiteRec — Data Loader
# Uses DuckDB to query only the columns and rows we need from the 12 GB CSV,
# then cleans the result in pandas following the off_nutriscore_01.ipynb logic.
# =============================================================================

import os
import logging
import warnings
import numpy as np
import pandas as pd
import duckdb

from .config import CSV_CANDIDATES, REQUIRED_COLS, COL_ALIASES, NUTRIENT_BOUNDS

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=pd.errors.DtypeWarning)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def load_data(csv_path: str | None = None) -> pd.DataFrame:
    """
    Load and pre-process the Open Food Facts CSV using DuckDB.

    DuckDB reads only the columns we need via a SQL projection, making the
    12 GB file tractable without loading it entirely into RAM.

    Returns a clean pandas DataFrame ready for ML and scoring.
    """
    path = _resolve_path(csv_path)
    logger.info(f"Loading dataset from: {path}")

    df = _query_with_duckdb(path)
    df = _clean_grades(df)
    df = _clean_nutrients(df)
    df = _clean_text_columns(df)
    df = _drop_useless_rows(df)
    df = df.reset_index(drop=True)

    logger.info(f"Dataset ready: {len(df):,} products, {len(df.columns)} columns")
    return df


# ---------------------------------------------------------------------------
# DuckDB extraction
# ---------------------------------------------------------------------------

def _resolve_path(csv_path: str | None) -> str:
    if csv_path and os.path.exists(csv_path):
        return csv_path
    for candidate in CSV_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError(
        "Open Food Facts CSV not found. Place it at one of:\n"
        + "\n".join(f"  {c}" for c in CSV_CANDIDATES)
    )


def _query_with_duckdb(path: str) -> pd.DataFrame:
    """
    Use DuckDB to read only the columns we need from the CSV.

    DuckDB's read_csv_auto is extremely fast on large files because it:
      - Uses columnar projection (skips columns it doesn't need)
      - Reads the file in parallel chunks
      - Never loads the whole file into RAM

    We map canonical column names to any alias present in the file.
    """
    con = duckdb.connect(database=":memory:")

    # First, get the actual column names present in the file
    try:
        available_cols = con.execute(
            f"DESCRIBE SELECT * FROM read_csv_auto('{path}', sep='\\t', "
            f"ignore_errors=True, sample_size=100)"
        ).df()["column_name"].tolist()
    except Exception as e:
        logger.warning(f"DuckDB DESCRIBE failed ({e}); falling back to pandas header read")
        available_cols = _get_columns_pandas(path)

    # Build SELECT clause: canonical name or alias → quoted column AS canonical_name
    select_parts = []
    for col in REQUIRED_COLS:
        if col in available_cols:
            select_parts.append(f'"{col}"')
        else:
            # Try aliases
            found_alias = None
            for alias in COL_ALIASES.get(col, []):
                if alias in available_cols:
                    found_alias = alias
                    break
            if found_alias:
                select_parts.append(f'"{found_alias}" AS "{col}"')
            else:
                # Column missing entirely — will add as NaN later
                pass

    if not select_parts:
        raise RuntimeError("None of the required columns were found in the CSV.")

    query = f"""
        SELECT {', '.join(select_parts)}
        FROM read_csv_auto('{path}', sep='\\t', ignore_errors=True)
    """

    logger.info(f"DuckDB query: selecting {len(select_parts)} columns...")
    df = con.execute(query).df()
    con.close()

    # Add any completely missing columns as NaN
    for col in REQUIRED_COLS:
        if col not in df.columns:
            df[col] = np.nan

    return df[REQUIRED_COLS]


def _get_columns_pandas(path: str) -> list[str]:
    """Fallback: read just the header row with pandas."""
    return pd.read_csv(path, sep="\t", nrows=0, low_memory=False,
                       on_bad_lines="skip").columns.tolist()


# ---------------------------------------------------------------------------
# Cleaning — following off_nutriscore_01.ipynb logic
# ---------------------------------------------------------------------------

NUTRIENT_COLS = [
    "energy-kcal_100g", "sugars_100g", "fat_100g",
    "saturated-fat_100g", "proteins_100g", "salt_100g", "fiber_100g",
]


def _clean_nutrients(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean nutrient columns following the notebook's three-step approach:

    A. Logical constraints — no single nutrient can exceed 100 g per 100 g.
       Rows with impossible values are dropped (not just clipped) to avoid
       biasing the ML model with dirty data.

    B. Statistical clipping — calories are clipped at the 99th percentile
       to remove extreme outliers (e.g. someone entering 10,000 kcal).

    C. Imputation — NaN filled with 0 for nutrients that are often left
       blank in OFF when the real value is zero (fibre, salt, etc.).
    """
    # Coerce all to numeric first
    all_nutrient_cols = NUTRIENT_COLS + [
        "carbohydrates_100g", "sodium_100g",
        "carbon-footprint-from-known-ingredients_product",
    ]
    for col in all_nutrient_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # A. Logical constraints: drop rows with any nutrient > 100 g/100g
    #    (except energy which is in kcal, handled separately)
    logical_cols = ["sugars_100g", "fat_100g", "saturated-fat_100g",
                    "proteins_100g", "salt_100g", "fiber_100g"]
    for col in logical_cols:
        if col in df.columns:
            df = df[df[col].isna() | (df[col] <= 100)]

    # B. Statistical clipping for energy (99th percentile, as per notebook)
    if "energy-kcal_100g" in df.columns:
        upper_kcal = df["energy-kcal_100g"].quantile(0.99)
        df = df[df["energy-kcal_100g"].isna() | (df["energy-kcal_100g"] <= upper_kcal)]

    # C. Fill NaN with 0 for nutrient columns (common in OFF for zero values)
    for col in logical_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0)
    if "energy-kcal_100g" in df.columns:
        df["energy-kcal_100g"] = df["energy-kcal_100g"].fillna(0)

    # Additional clip for remaining columns using config bounds (safety net)
    for col, (lo, hi) in NUTRIENT_BOUNDS.items():
        if col in df.columns:
            df[col] = df[col].clip(lower=lo, upper=hi)

    return df


def _clean_grades(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise Nutri-Score and Eco-Score grades.
    Following the notebook: keep only single-character grades, uppercase,
    then convert to lowercase for internal consistency.
    """
    for col in ("nutriscore_grade", "ecoscore_grade"):
        if col not in df.columns:
            df[col] = "unknown"
            continue
        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
            .str.lower()
        )
        # Keep only valid single-letter grades
        df[col] = df[col].where(df[col].isin(list("abcde")), other="unknown")

    for col in ("nutriscore_score", "ecoscore_score"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def _clean_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip and fill text fields."""
    text_cols = [
        "product_name", "brands", "categories_en", "countries_en",
        "allergens_en", "traces_en", "labels_en", "labels_tags",
        "packaging_tags", "origins_tags", "manufacturing_places",
    ]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()
    return df


def _drop_useless_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove rows useless for recommendations.

    Filters (in order of impact):
    1. No product name
    2. Fewer than 3 non-zero nutrients
    3. Name mostly non-Latin characters (Arabic, CJK, Cyrillic-only, etc.)
    4. Exact duplicate product names
    """
    before = len(df)

    # 1. Must have a name
    df = df[df["product_name"].str.len() > 0].copy()

    # 2. At least 3 non-zero nutrient values
    key_cols = ["energy-kcal_100g", "fat_100g", "proteins_100g",
                "sugars_100g", "salt_100g"]
    existing = [c for c in key_cols if c in df.columns]
    if existing:
        df = df[(df[existing] > 0).sum(axis=1) >= 3]

    # 3. Keep only products whose names are >=60% Latin/ASCII characters
    #    (removes Arabic, CJK, Cyrillic-only entries; keeps ES/EN/FR/DE/IT)
    def is_latin_enough(name):
        if not name:
            return False
        ascii_chars = sum(1 for c in name if ord(c) < 256)
        return ascii_chars / len(name) >= 0.6

    df = df[df["product_name"].apply(is_latin_enough)]

    # 4. Drop exact duplicate product names
    df = df.drop_duplicates(subset=["product_name"], keep="first")

    after = len(df)
    logger.info(f"Quality filter: {before:,} -> {after:,} products ({before - after:,} removed)")
    return df


# ---------------------------------------------------------------------------
# Category pool helper
# ---------------------------------------------------------------------------

def get_category_pool(df: pd.DataFrame, product_row: pd.Series, min_size: int = 10) -> pd.DataFrame:
    """Return products in the same broad category as product_row."""
    cat = str(product_row.get("categories_en", ""))
    if not cat:
        return df

    first_cat = cat.split(",")[0].strip().lower()
    if not first_cat:
        return df

    mask = df["categories_en"].str.lower().str.contains(first_cat, na=False, regex=False)
    pool = df[mask]
    return pool if len(pool) >= min_size else df
