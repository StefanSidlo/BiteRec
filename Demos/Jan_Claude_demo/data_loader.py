"""
BiteRec – Data Loader & Preprocessor
Loads Open Food Facts CSV in chunks (handles multi-GB files).
Cleaning approach based on the course notebook (off_nutriscore_01.ipynb):
  - Remove physically impossible values (nutrient > 100g per 100g)
  - 99th-percentile clipping on calories
  - Fill missing fiber/salt with 0 (common in OFF crowdsourced data)
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

NUTRI_MAP = {"a": 100, "b": 75, "c": 50, "d": 25, "e": 0, "not-applicable": 50}
ECO_MAP   = {"a-plus": 100, "a": 85, "b": 65, "c": 45, "d": 25, "e": 10, "f": 0,
             "not-applicable": 50, "unknown": np.nan}

# Nutrient columns that cannot exceed 100 g per 100 g (notebook step A)
CLIPPABLE = ["sugars_100g", "fat_100g", "saturated-fat_100g",
             "proteins_100g", "salt_100g", "fiber_100g"]

COLS = [
    "code", "product_name", "brands", "categories_en", "pnns_groups_1",
    "nutriscore_grade", "nutriscore_score",
    "environmental_score_grade", "environmental_score_score",
    "energy-kcal_100g", "fat_100g", "saturated-fat_100g",
    "carbohydrates_100g", "sugars_100g", "fiber_100g",
    "proteins_100g", "salt_100g",
    "allergens", "allergens_en", "traces_en",
    "labels_en", "origins_en", "countries_en",
    "ingredients_text", "url",
]


def load_data(csv_path: str, max_products: int = 50_000) -> pd.DataFrame:
    logger.info(f"Loading CSV from {csv_path}  (chunk mode, target ≤{max_products} products)…")

    header = pd.read_csv(csv_path, sep="\t", nrows=0, low_memory=False, on_bad_lines="skip")
    available_cols = [c for c in COLS if c in header.columns]
    missing = [c for c in COLS if c not in header.columns]
    if missing:
        logger.warning(f"Columns absent in this CSV (skipped): {missing}")

    chunks = []
    chunk_size = 100_000
    total_read = 0

    reader = pd.read_csv(
        csv_path, sep="\t", usecols=available_cols,
        low_memory=False, on_bad_lines="skip",
        chunksize=chunk_size, encoding="utf-8", encoding_errors="replace",
    )

    for chunk in reader:
        total_read += len(chunk)

        # ── Minimum required fields ──────────────────────────────────────────
        mask = (
            chunk["product_name"].notna() &
            chunk["proteins_100g"].notna() &
            chunk["fat_100g"].notna() &
            chunk["sugars_100g"].notna() &
            chunk["nutriscore_grade"].notna() &
            (~chunk["nutriscore_grade"].str.lower().isin(["unknown", "not-applicable"]))
        )
        good = chunk[mask].copy()

        # ── Notebook step A: remove physically impossible values ──────────────
        for col in CLIPPABLE:
            if col in good.columns:
                good[col] = pd.to_numeric(good[col], errors="coerce")
                good = good[good[col].isna() | (good[col] <= 100)]

        if len(good):
            chunks.append(good)

        collected = sum(len(c) for c in chunks)
        logger.info(f"  Read {total_read:,} rows total, kept {collected:,} good products…")
        if collected >= max_products:
            logger.info(f"  Reached target of {max_products} — stopping early.")
            break

    if not chunks:
        raise ValueError("No usable products found in the CSV.")

    df = pd.concat(chunks, ignore_index=True).head(max_products)
    logger.info(f"Raw usable rows: {len(df)}")

    # ── Notebook step B: 99th-percentile clipping on calories ───────────────
    if "energy-kcal_100g" in df.columns:
        df["energy-kcal_100g"] = pd.to_numeric(df["energy-kcal_100g"], errors="coerce")
        upper_kcal = df["energy-kcal_100g"].quantile(0.99)
        df = df[df["energy-kcal_100g"].isna() | (df["energy-kcal_100g"] <= upper_kcal)]

    # ── Notebook step C: target cleaning ────────────────────────────────────
    df["nutriscore_grade"] = df["nutriscore_grade"].str.lower().str.strip()

    # ── Numeric scores ───────────────────────────────────────────────────────
    df["health_score"] = df["nutriscore_grade"].map(NUTRI_MAP).fillna(50)

    if "environmental_score_grade" in df.columns:
        df["eco_score"] = df["environmental_score_grade"].str.lower().map(ECO_MAP)
    else:
        df["eco_score"] = np.nan

    median_eco = df["eco_score"].median()
    df["eco_score"] = df["eco_score"].fillna(median_eco if not np.isnan(median_eco) else 50)

    if "environmental_score_grade" in df.columns:
        df["environmental_score_grade"] = df["environmental_score_grade"].str.lower().fillna("unknown")
    else:
        df["environmental_score_grade"] = "unknown"

    # ── Allergen text ────────────────────────────────────────────────────────
    def merge_allergens(row):
        parts = []
        for col in ["allergens", "allergens_en", "traces_en"]:
            val = row.get(col)
            if pd.notna(val) and str(val).strip():
                parts.append(str(val).lower())
        return " ".join(parts)

    df["allergen_text"] = df.apply(merge_allergens, axis=1)

    # ── Notebook step: fillna(0) for fiber/salt, median for others ───────────
    zero_fill = ["fiber_100g", "salt_100g"]          # often missing = 0 in OFF
    median_fill = ["energy-kcal_100g", "fat_100g", "saturated-fat_100g",
                   "carbohydrates_100g", "sugars_100g", "proteins_100g"]
    for col in zero_fill:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    for col in median_fill:
        if col not in df.columns:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[col] = df[col].fillna(df[col].median())

    # ── Fill text columns ────────────────────────────────────────────────────
    for col in ["pnns_groups_1", "categories_en", "brands",
                "labels_en", "origins_en", "countries_en", "url"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("")

    df = df.reset_index(drop=True)
    logger.info(f"✅ Final dataset: {len(df)} products ready.")
    return df


def get_allergen_keywords(allergen_input: str) -> list:
    if not allergen_input:
        return []
    return [a.strip().lower() for a in allergen_input.replace(",", " ").split() if a.strip()]


def product_contains_allergen(allergen_text: str, allergen_keywords: list) -> bool:
    text = allergen_text.lower()
    return any(kw in text for kw in allergen_keywords)
