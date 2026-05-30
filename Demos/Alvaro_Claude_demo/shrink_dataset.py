"""
shrink_dataset.py
=================
Reduces the full Open Food Facts CSV (~12 GB) to a ~20 MB sample
suitable for uploading to GitHub.

Run from the project root:
    python shrink_dataset.py

Output: data/openfoodfacts_20MB.csv  (~20 MB, tab-separated)
"""

import os
import sys
import logging
import duckdb
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

INPUT_CANDIDATES = [
    "data/en.openfoodfacts.org.products.csv",
    "data/openfoodfacts.csv",
    "data/openfoodfacts_short.csv",
]

OUTPUT_PATH   = "data/openfoodfacts_20MB.csv"
TARGET_MB     = 20
TARGET_BYTES  = TARGET_MB * 1024 * 1024

# Only keep columns the app actually uses (drops ~150 irrelevant columns)
KEEP_COLS = [
    "code",
    "product_name",
    "brands",
    "categories_en",
    "countries_en",
    "image_url",
    "energy-kcal_100g",
    "fat_100g",
    "saturated-fat_100g",
    "carbohydrates_100g",
    "sugars_100g",
    "fiber_100g",
    "proteins_100g",
    "salt_100g",
    "sodium_100g",
    "nutriscore_grade",
    "nutriscore_score",
    "ecoscore_grade",
    "ecoscore_score",
    "carbon-footprint-from-known-ingredients_product",
    "packaging_tags",
    "origins_tags",
    "manufacturing_places",
    "allergens_en",
    "traces_en",
    "labels_en",
    "labels_tags",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_input() -> str:
    for path in INPUT_CANDIDATES:
        if os.path.exists(path):
            return path
    print("❌  Could not find the OFF CSV. Place it at one of:")
    for p in INPUT_CANDIDATES:
        print(f"    {p}")
    sys.exit(1)


def is_latin_enough(s: str, threshold: float = 0.6) -> bool:
    if not s:
        return False
    ascii_count = sum(1 for c in s if ord(c) < 256)
    return ascii_count / len(s) >= threshold


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    input_path = find_input()
    input_size_gb = os.path.getsize(input_path) / (1024 ** 3)
    log.info(f"Input:  {input_path}  ({input_size_gb:.1f} GB)")
    log.info(f"Target: {OUTPUT_PATH}  (~{TARGET_MB} MB)")

    # ── Step 1: Read only the columns we need via DuckDB ──────────────────
    log.info("\n[1/5] Reading columns with DuckDB...")
    con = duckdb.connect(":memory:")

    # Discover which of our desired columns actually exist in this CSV
    available = con.execute(
        f"DESCRIBE SELECT * FROM read_csv_auto('{input_path}', sep='\\t', "
        f"ignore_errors=True, sample_size=200)"
    ).df()["column_name"].tolist()

    cols_to_read = [c for c in KEEP_COLS if c in available]
    missing = [c for c in KEEP_COLS if c not in available]
    if missing:
        log.info(f"  Columns not in CSV (will be added as empty): {missing}")

    select_clause = ", ".join(f'"{c}"' for c in cols_to_read)
    df = con.execute(f"""
        SELECT {select_clause}
        FROM read_csv_auto('{input_path}', sep='\\t', ignore_errors=True)
    """).df()
    con.close()

    log.info(f"  Loaded {len(df):,} rows × {len(df.columns)} columns")

    # Add missing columns as empty strings
    for c in missing:
        df[c] = ""
    df = df[KEEP_COLS]

    # ── Step 2: Quality filters ────────────────────────────────────────────
    log.info("\n[2/5] Applying quality filters...")
    before = len(df)

    # Must have a product name
    df = df[df["product_name"].fillna("").str.len() > 0]

    # Must have at least 3 non-zero nutrient values
    nutrient_cols = ["energy-kcal_100g", "fat_100g", "proteins_100g",
                     "sugars_100g", "salt_100g"]
    for c in nutrient_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[(df[nutrient_cols] > 0).sum(axis=1) >= 3]

    # Drop non-Latin product names (Arabic, CJK, Cyrillic-only, etc.)
    df = df[df["product_name"].apply(is_latin_enough)]

    # Drop exact duplicate product names
    df = df.drop_duplicates(subset=["product_name"], keep="first")

    # Drop impossible nutrient values
    for col in ["sugars_100g", "fat_100g", "saturated-fat_100g",
                "proteins_100g", "salt_100g", "fiber_100g"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df[df[col].isna() | (df[col] <= 100)]

    log.info(f"  {before:,} → {len(df):,} products after quality filter")

    # ── Step 3: Stratified sample to hit ~50 MB ────────────────────────────
    log.info("\n[3/5] Stratified sampling...")

    # Estimate bytes per row from a small sample
    sample_small = df.head(1000)
    sample_csv   = sample_small.to_csv(sep="\t", index=False)
    bytes_per_row = len(sample_csv.encode("utf-8")) / len(sample_small)
    header_bytes  = len(df.columns.__str__().encode("utf-8"))
    max_rows      = int((TARGET_BYTES - header_bytes) / bytes_per_row)

    log.info(f"  ~{bytes_per_row:.0f} bytes/row → keeping {max_rows:,} rows for {TARGET_MB} MB")

    if len(df) <= max_rows:
        log.info("  Dataset already small enough — keeping all rows.")
        df_out = df
    else:
        # Stratify by nutriscore_grade so we keep a balanced grade distribution
        df["_grade"] = df["nutriscore_grade"].fillna("unknown").str.lower()
        df["_grade"] = df["_grade"].where(df["_grade"].isin(list("abcde")), "unknown")

        grade_counts = df["_grade"].value_counts()
        total        = len(df)
        sampled_parts = []

        for grade, count in grade_counts.items():
            proportion  = count / total
            n_for_grade = max(1, int(max_rows * proportion))
            part        = df[df["_grade"] == grade].sample(
                min(n_for_grade, count), random_state=42
            )
            sampled_parts.append(part)

        df_out = pd.concat(sampled_parts).drop(columns=["_grade"])
        df_out = df_out.sample(frac=1, random_state=42).reset_index(drop=True)

    # ── Step 4: Write output ───────────────────────────────────────────────
    log.info(f"\n[4/5] Writing {OUTPUT_PATH}...")
    os.makedirs("data", exist_ok=True)
    df_out.to_csv(OUTPUT_PATH, sep="\t", index=False)

    # ── Step 5: Report ─────────────────────────────────────────────────────
    actual_mb = os.path.getsize(OUTPUT_PATH) / (1024 ** 2)
    log.info(f"\n[5/5] Done!")
    log.info(f"  Rows:    {len(df_out):,}")
    log.info(f"  Columns: {len(df_out.columns)}")
    log.info(f"  Size:    {actual_mb:.1f} MB")
    log.info(f"  Output:  {OUTPUT_PATH}")

    # Grade distribution
    grade_col = df_out["nutriscore_grade"].fillna("unknown").str.lower()
    grade_col = grade_col.where(grade_col.isin(list("abcde")), "unknown")
    log.info("\n  Nutri-Score grade distribution:")
    for g, n in grade_col.value_counts().sort_index().items():
        bar = "█" * int(n / len(df_out) * 40)
        log.info(f"    {g.upper()}  {bar} {n:,} ({n/len(df_out)*100:.1f}%)")

if __name__ == "__main__":
    main()
